import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.workflows import grafo_triaje_app, EstadoTriajeHospitalario
from domain.catalog import CATALOGO_PRUEBAS, normalizar_texto
from guardrails.code_guards import guardrail_prescripcion_clinica, registrar_prueba_historial
from tools.clinical_ehr import emitir_volante_ehr, obtener_volantes_emitidos

app = FastAPI(title="API Triaje Clínico Autónomo")

# Diccionario de casos que esperan firma médica: thread_id -> datos_volante
CASOS_PENDIENTES_MEDICO = {}

MAPEO_PRUEBAS = {
    "cardiologia": {
        "ecocardiograma transtoracico": ["ecocardiograma", "ecocardio", "eco transtoracico"],
        "electrocardiograma": ["electrocardiograma", "ecg", "ekg", "trazado electrocardiografico"],
        "ergometria": ["ergometria", "prueba de esfuerzo"],
        "holter ecg 24h": ["holter"]
    },
    "neumologia": {
        "radiografia de torax": ["radiografia de torax", "rx torax", "placa de torax"],
        "espirometria forzada": ["espirometria"],
        "tac toracico": ["tac", "tc toracico", "angio-tc"],
        "gasometria arterial": ["gasometria"]
    },
    "traumatologia": {
        "radiografia simple": ["radiografia", "rx simple", "placa"],
        "resonancia magnetica articular": ["resonancia", "rm articular", "rnm"],
        "ecografia musculoesqueletica": ["ecografia musculoesqueletica", "eco articular"]
    },
    "general": {
        "analitica sanguinea completa": ["analitica sanguinea", "analitica de sangre", "hemograma", "analitica"],
        "analitica de orina": ["analitica de orina", "sedimento de orina"],
        "ecografia abdominal": ["ecografia abdominal", "eco abdominal"]
    }
}


def _inferir_prueba(texto: str, categoria: str) -> Optional[str]:
    t_norm = normalizar_texto(texto)
    mapeo = MAPEO_PRUEBAS.get(categoria, {})
    for prueba_oficial, sinonimos in mapeo.items():
        for s in sinonimos:
            if normalizar_texto(s) in t_norm:
                return prueba_oficial
    for p in CATALOGO_PRUEBAS.get(categoria, []):
        if normalizar_texto(p) in t_norm:
            return p
    return None

def _extraer_skills_usadas(mensajes: list) -> list[str]:
    """Inspecciona los mensajes para registrar skills y herramientas consultadas."""
    skills_invocadas = []
    for msg in mensajes:
        # 1. Detección en tool_calls de AIMessage
        tool_calls = getattr(msg, "tool_calls", []) or []
        for call in tool_calls:
            nombre_tool = call.get("name", "")
            args = call.get("args", {})
            
            if nombre_tool == "load_skill":
                s = args.get("nombre")
                if s and s not in skills_invocadas:
                    skills_invocadas.append(s)
            elif nombre_tool in ["buscar_wikipedia", "extracto_wikipedia"]:
                if "ficha-enciclopedica" not in skills_invocadas:
                    skills_invocadas.append("ficha-enciclopedica (Wikipedia)")
        
        # 2. Detección en ToolMessage de retorno
        nombre_tool_msg = getattr(msg, "name", "")
        if nombre_tool_msg == "load_skill":
            contenido = str(getattr(msg, "content", ""))
            for conocida in ["ficha-enciclopedica", "protocolo-scacest"]:
                if conocida in contenido and conocida not in skills_invocadas:
                    skills_invocadas.append(conocida)
                    
    return skills_invocadas

class ConsultaTriajeRequest(BaseModel):
    nhc: str = Field(default="PAC-8921")
    pregunta: str = Field(..., description="Motivo de consulta del paciente")
    thread_id: Optional[str] = None


class DecisionMedicoRequest(BaseModel):
    thread_id: str
    aprobado: bool


@app.post("/api/triaje")
async def iniciar_triaje(req: ConsultaTriajeRequest):
    thread_id = req.thread_id or f"hilo-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    # 1. El agente especialista analiza y redacta su dictamen clínico
    estado_inicial: EstadoTriajeHospitalario = {
        "nhc": req.nhc,
        "pregunta": req.pregunta
    }
    res = await grafo_triaje_app.ainvoke(estado_inicial, config=config)
    
    categoria = res.get("categoria", "general")
    dictamen = res.get("respuesta_especialista", "")
    
    # 2. El agente decide la prueba en su dictamen
    prueba_decidida = _inferir_prueba(dictamen, categoria)
    
    error_guardrail = None
    requiere_supervision = False
    volante = None

    if prueba_decidida:
        # 3. Comprobación de guardrails deterministas por código
        valido, motivo = guardrail_prescripcion_clinica(
            nhc=req.nhc,
            servicio=categoria,
            prueba=prueba_decidida
        )
        
        if not valido:
            # Freno de código: Duplicidad o fuera de catálogo
            error_guardrail = motivo
            requiere_supervision = False
        else:
            # Pasa guardrails técnicos -> Se escala a la consola del facultativo
            requiere_supervision = True
            volante = {
                "nhc": req.nhc,
                "servicio": categoria,
                "prueba": prueba_decidida,
                "prioridad": "urgente" if any(k in dictamen.lower() for k in ["urgente", "inmediat", "emergencia"]) else "preferente",
                "justificacion": dictamen
            }
            # Guardamos el caso en la bandeja de espera del médico
            CASOS_PENDIENTES_MEDICO[thread_id] = volante
    
    # 1. Recuperar los mensajes devueltos por el grafo
    mensajes = res.get("mensajes")
    if not mensajes:
        snapshot = grafo_triaje_app.get_state(config)
        mensajes = snapshot.values.get("mensajes", [])

    skills_usadas = _extraer_skills_usadas(mensajes)

    return {
        "thread_id": thread_id,
        "categoria": categoria,
        "motivo_triaje": res.get("motivo_triaje"),
        "respuesta_especialista": dictamen,
        "skills_usadas": skills_usadas,
        "prueba_decidida_por_agente": prueba_decidida,
        "error_guardrail": error_guardrail,
        "requiere_supervision": requiere_supervision,
        "volante_propuesto": volante,
        "resultado_final": dictamen
    }


@app.post("/api/decision")
async def resolver_decision_medica(req: DecisionMedicoRequest):
    volante = CASOS_PENDIENTES_MEDICO.get(req.thread_id)
    if not volante:
        raise HTTPException(status_code=400, detail="No hay prescripciones pendientes para este paciente.")

    if req.aprobado:
        # 1. Se formaliza y registra en la base de datos del EHR
        mensaje_ehr = emitir_volante_ehr.invoke(volante)
        
        # 2. NUEVO: Se añade al historial clínico para que el guardrail detecte duplicidades futuras
        registrar_prueba_historial(
            nhc=volante["nhc"],
            servicio=volante["servicio"],
            prueba=volante["prueba"]
        )
        
        del CASOS_PENDIENTES_MEDICO[req.thread_id]
        return {
            "thread_id": req.thread_id,
            "estado": "APROBADO",
            "mensaje": mensaje_ehr
        }
    else:
        del CASOS_PENDIENTES_MEDICO[req.thread_id]
        return {
            "thread_id": req.thread_id,
            "estado": "DENEGADO",
            "mensaje": "Prescripción rechazada por el facultativo."
        }


@app.get("/api/volantes")
def listar_volantes():
    return {"volantes": obtener_volantes_emitidos()}