from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

from core.llm import crear_modelo
from domain.catalog import normalizar_texto
from domain.schemas import EspecialidadMedica
from tools import HERRAMIENTAS_CONSULTA, emitir_volante_ehr
from guardrails import guardrail_prescripcion_clinica
from agents.router import clasificar_motivo_triaje


# 1. Definición del Estado global del Grafo
class EstadoTriajeHospitalario(TypedDict, total=False):
    nhc: str
    pregunta: str
    categoria: EspecialidadMedica
    motivo_triaje: str
    respuesta_especialista: str
    volante_propuesto: Optional[Dict[str, str]]
    error_guardrail: Optional[str]
    aprobacion_medica: Optional[bool]
    resultado_final: str


# 2. Factoría de agentes especialistas con herramientas de consulta
def _crear_especialista(especialidad: str, instrucciones: str):
    return create_agent(
        model=crear_modelo(),
        tools=HERRAMIENTAS_CONSULTA,
        system_prompt=instrucciones,
        middleware=[
            ModelCallLimitMiddleware(run_limit=4, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=2, exit_behavior="end")
        ]
    )


AGENTES_ESPECIALISTAS = {
    "cardiologia": _crear_especialista(
        "cardiologia",
        "Eres un facultativo especialista en Cardiología. Analiza la sospecha clínica de patología "
        "cardiovascular. Justifica con fuentes fiables y propón la prueba adecuada. Responde en español en tres frases como máximo."
    ),
    "neumologia": _crear_especialista(
        "neumologia",
        "Eres un facultativo especialista en Neumología. Analiza síntomas respiratorios. "
        "Fundamenta la indicación y propón la prueba adecuada. Responde en español en tres frases como máximo."
    ),
    "traumatologia": _crear_especialista(
        "traumatologia",
        "Eres un facultativo especialista en Traumatología. Analiza lesiones osteoarticulares y fracturas. "
        "Propón la prueba pertinente. Responde en español en tres frases como máximo."
    ),
    "general": _crear_especialista(
        "general",
        "Eres un facultativo de Medicina Interna y Atención General. Analiza cuadros inespecíficos. "
        "Propón la prueba inicial. Responde en español en tres frases como máximo."
    )
}


# 3. Nodos del Grafo
async def nodo_clasificar(estado: EstadoTriajeHospitalario) -> Dict[str, Any]:
    """Nodo 1: Clasifica la consulta para decidir la rama clínica."""
    clasificacion = await clasificar_motivo_triaje(estado["pregunta"])
    return {
        "categoria": clasificacion.categoria,
        "motivo_triaje": clasificacion.motivo
    }


def generar_nodo_especialista(especialidad: str):
    """Nodos 2-5: Ejecuta el especialista hospitalario correspondiente."""
    async def _nodo(estado: EstadoTriajeHospitalario) -> Dict[str, Any]:
        agente = AGENTES_ESPECIALISTAS[especialidad]
        res = await agente.ainvoke({"messages": [{"role": "user", "content": estado["pregunta"]}]})
        return {"respuesta_especialista": str(res["messages"][-1].content)}
    return _nodo


async def nodo_guardrail(estado: EstadoTriajeHospitalario) -> Dict[str, Any]:
    """Nodo 6: Aplica guardrails de código antes de autorizar o escalar."""
    volante = estado.get("volante_propuesto")
    if not volante:
        # Si no hay intención de volante sensible, finaliza directamente
        return {"resultado_final": estado["respuesta_especialista"]}

    valido, motivo = guardrail_prescripcion_clinica(
        nhc=estado.get("nhc", "PAC-DEFAULT"),
        servicio=volante.get("servicio", estado["categoria"]),
        prueba=volante.get("prueba", "")
    )
    if not valido:
        return {
            "error_guardrail": motivo,
            "resultado_final": f"BLOQUEO TÉCNICO: {motivo}"
        }
    return {"error_guardrail": None}


async def nodo_supervision_hitl(estado: EstadoTriajeHospitalario) -> Dict[str, Any]:
    """Nodo 7: Ejecuta la acción sensible si la aprobación médica fue positiva."""
    if not estado.get("aprobacion_medica"):
        return {"resultado_final": "ACCION DENEGADA: El facultativo responsable rechazó la emisión del volante."}

    volante = estado.get("volante_propuesto") or {}
    
    # Fallback seguro al servicio clasificado si no venía explícito en el dict
    servicio_final = volante.get("servicio") or estado.get("categoria") or "general"
    prueba_final = volante.get("prueba", "")
    prioridad_final = volante.get("prioridad", "ordinaria")
    justificacion_final = volante.get("justificacion", estado.get("pregunta", "Indicada por triaje clínico"))

    resultado_ehr = emitir_volante_ehr.invoke({
        "nhc": estado.get("nhc", "PAC-DEFAULT"),
        "servicio": servicio_final,
        "prueba": prueba_final,
        "prioridad": prioridad_final,
        "justificacion": justificacion_final
    })
    return {"resultado_final": f"{estado.get('respuesta_especialista', '')}\n\n[SISTEMA]: {resultado_ehr}"}

# 4. Construcción y ensamblado del StateGraph
def construir_grafo_triaje():
    workflow = StateGraph(EstadoTriajeHospitalario)

    # Registro de nodos
    workflow.add_node("clasificar_triaje", nodo_clasificar)
    for esp in AGENTES_ESPECIALISTAS:
        workflow.add_node(esp, generar_nodo_especialista(esp))
        workflow.add_edge(esp, "guardrail_seguridad")

    workflow.add_node("guardrail_seguridad", nodo_guardrail)
    workflow.add_node("supervision_hitl", nodo_supervision_hitl)

    # Conexiones y aristas condicionales
    workflow.add_edge(START, "clasificar_triaje")
    workflow.add_conditional_edges(
        "clasificar_triaje",
        lambda estado: estado["categoria"],
        {esp: esp for esp in AGENTES_ESPECIALISTAS}
    )

    # Decisión post-guardrail
    def ruta_post_guardrail(estado: EstadoTriajeHospitalario) -> str:
        if estado.get("error_guardrail") or not estado.get("volante_propuesto"):
            return END
        return "supervision_hitl"

    workflow.add_conditional_edges(
        "guardrail_seguridad",
        ruta_post_guardrail,
        {"supervision_hitl": "supervision_hitl", END: END}
    )
    workflow.add_edge("supervision_hitl", END)

    # Compilación con punto de control en memoria
    return workflow.compile(
        checkpointer=InMemorySaver(),
        interrupt_before=["supervision_hitl"]  # Pausa antes de ejecutar la escritura para que el médico decida
    )


grafo_triaje_app = construir_grafo_triaje()