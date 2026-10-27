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
from tools.skills_loader import catalogo_skills


# 1. Definición del Estado del Grafo Clínico
class EstadoTriajeHospitalario(TypedDict, total=False):
    nhc: str
    pregunta: str
    categoria: Optional[str]
    motivo_triaje: Optional[str]
    respuesta_especialista: Optional[str]
    mensajes: Optional[List[Any]]           # <-- Clave para almacenar las trazas y tool_calls
    volante_propuesto: Optional[dict]
    error_guardrail: Optional[str]
    aprobacion_medica: Optional[bool]
    resultado_final: Optional[str]


# 2. Inicialización del modelo base
llm = crear_modelo()


# 3. Función auxiliar para construir el prompt enriquecido con las skills
def construir_prompt_especialista(servicio: str) -> str:
    catalogo = catalogo_skills()
    skills_txt = "\n".join([f"- {k}: {v}" for k, v in catalogo.items()])
    
    return f"""Eres un médico consultor del servicio de {servicio.upper()}.
Dispones exclusivamente de estas herramientas y protocolos clínicos (skills):
{skills_txt}

NORMAS DE OBLIGADO CUMPLIMIENTO:
1. SI EL USUARIO PIDE UNA FICHA ENCICLOPÉDICA, DEFINICIÓN, CONCEPTO MÉDICO O EXPLICACIÓN:
   - TIENES PROHIBIDO responder de memoria.
   - Es OBLIGATORIO que tu primera acción sea llamar a la herramienta `load_skill` con el argumento `nombre="ficha-enciclopedica"`.
2. SI EL CASO ES UN DOLOR TORÁCICO AGUDO O SOSPECHA DE INFARTO/SCACEST:
   - Es OBLIGATORIO llamar a la herramienta `load_skill` con el argumento `nombre="protocolo-scacest"`.
3. Solo tras recibir la información de las herramientas o skills redactarás tu respuesta final.
"""


# 4. Fábrica de Agentes Especialistas
def crear_agente_especialista(servicio: str):
    prompt_sistema = construir_prompt_especialista(servicio)
    # create_agent vincula las herramientas (load_skill, wikipedia) con el LLM
    return create_agent(
        llm,
        tools=HERRAMIENTAS_CONSULTA,
        system_prompt=prompt_sistema,
        middleware=[
            ModelCallLimitMiddleware(run_limit=5),
            ToolCallLimitMiddleware(run_limit=5)
        ]
    )


# Preinstanciamos los agentes por servicio
AGENTES = {
    "cardiologia": crear_agente_especialista("cardiologia"),
    "neumologia": crear_agente_especialista("neumologia"),
    "traumatologia": crear_agente_especialista("traumatologia"),
    "general": crear_agente_especialista("general")
}


# ==========================================
# NODOS DEL GRAFO
# ==========================================
ESPECIALIDADES_VALIDAS = {"cardiologia", "neumologia", "traumatologia", "general"}

async def nodo_clasificar(estado: EstadoTriajeHospitalario) -> Dict[str, Any]:
    """Nodo 1: Clasifica la consulta hacia el servicio médico competente."""
    clasificacion = await clasificar_motivo_triaje(estado["pregunta"])
    
    cat_raw = getattr(clasificacion, "categoria", "general")
    motivo_raw = getattr(clasificacion, "motivo", "")
    
    if hasattr(cat_raw, "value"):
        cat_str = str(cat_raw.value).lower().strip()
    else:
        cat_str = str(cat_raw).lower().strip()
        
    motivo_str = str(motivo_raw).strip()

    # Si por error el LLM los devolvió invertidos:
    if cat_str not in ESPECIALIDADES_VALIDAS and motivo_str.lower() in ESPECIALIDADES_VALIDAS:
        cat_str, motivo_str = motivo_str.lower(), cat_str
    elif cat_str not in ESPECIALIDADES_VALIDAS:
        cat_str = "general"

    return {
        "categoria": cat_str,
        "motivo_triaje": motivo_str
    }


async def nodo_especialista(estado: EstadoTriajeHospitalario) -> Dict[str, Any]:
    """Nodo 2: El agente especialista analiza el caso y ejecuta las tools/skills necesarias."""
    categoria = estado.get("categoria", "general")
    agente = AGENTES.get(categoria, AGENTES["general"])
    
    # Invocamos al agente
    resultado = await agente.ainvoke({"messages": [("user", estado["pregunta"])]})
    
    # Extraer mensajes y respuesta según el tipo de objeto devuelto por create_agent
    mensajes = resultado.get("messages", [])
    
    # Si messages es una lista, el último suele ser la respuesta textual del LLM
    if mensajes:
        texto_salida = mensajes[-1].content
    else:
        texto_salida = resultado.get("output", str(resultado))

    return {
        "respuesta_especialista": texto_salida,
        "mensajes": mensajes   # Guardamos los mensajes en el estado para extraer las skills
    }


# ==========================================
# CONSTRUCCIÓN DEL GRAFO
# ==========================================

workflow = StateGraph(EstadoTriajeHospitalario)

# Añadir nodos
workflow.add_node("clasificar", nodo_clasificar)
workflow.add_node("especialista", nodo_especialista)

# Conexiones
workflow.add_edge(START, "clasificar")
workflow.add_edge("clasificar", "especialista")
workflow.add_edge("especialista", END)

# Checkpointer en memoria para persistir hilos
memoria = InMemorySaver()
grafo_triaje_app = workflow.compile(checkpointer=memoria)