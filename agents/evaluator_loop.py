from typing import Tuple, Optional
from core.llm import crear_modelo
from domain.schemas import VeredictoClinico
from guardrails.evaluator import corrector_volante_por_codigo

PROMPT_GENERADOR_VOLANTE = (
    "Eres un asistente de prescripción diagnóstica hospitalaria. Redacta una propuesta formal de volante indicando:\n"
    "- Sospecha diagnóstica principal.\n"
    "- Servicio de destino (cardiologia, neumologia, traumatologia o general).\n"
    "- Prueba solicitada (debe coincidir con el nombre oficial del catálogo).\n"
    "- Prioridad (urgente, preferente u ordinaria).\n"
    "- Fuente o cita médica de referencia que sustente la indicación.\n"
    "Responde de forma concisa y estructurada en un solo párrafo."
)

PROMPT_JUEZ_CLINICO = (
    "Eres un auditor médico estricto. Evalúa si la prueba médica y la prioridad propuestas "
    "son clínicamente coherentes con los síntomas descritos por el paciente. Si no guardan "
    "relación o están injustificadas, emite una crítica breve en una sola frase."
)

_juez_llm = crear_modelo(temperatura=0).with_structured_output(
    VeredictoClinico, method="json_schema"
)


def generar_borrador_volante(
    motivo_consulta: str,
    propuesta_anterior: Optional[str] = None,
    critica: Optional[str] = None
) -> str:
    """Generador: Redacta o corrige la propuesta de volante a partir de la sintomatología."""
    mensajes = [
        {"role": "system", "content": PROMPT_GENERADOR_VOLANTE},
        {"role": "user", "content": f"Motivo de consulta del paciente: {motivo_consulta}"}
    ]
    if critica and propuesta_anterior:
        mensajes.append({
            "role": "user",
            "content": f"Tu propuesta anterior fue:\n{propuesta_anterior}\n\nCorrígela atendiendo estrictamente a esta crítica:\n{critica}"
        })
    respuesta = crear_modelo().invoke(mensajes)
    return str(getattr(respuesta, "content", respuesta))


def evaluar_borrador_volante(motivo_consulta: str, propuesta: str) -> Tuple[bool, str]:
    """Evaluador en dos etapas: primero filtro determinista por código; si pasa, revisión del juez LLM."""
    ok_codigo, critica_codigo = corrector_volante_por_codigo(propuesta)
    if not ok_codigo:
        return False, critica_codigo

    veredicto = _juez_llm.invoke([
        {"role": "system", "content": PROMPT_JUEZ_CLINICO},
        {"role": "user", "content": f"Síntomas: {motivo_consulta}\nPropuesta de volante: {propuesta}"}
    ])
    return veredicto.indicacion_coherente, (veredicto.critica or "")


def optimizar_volante(motivo_consulta: str, max_iteraciones: int = 3) -> Tuple[str, bool]:
    """Bucle Evaluador-Optimizador acotado."""
    propuesta = generar_borrador_volante(motivo_consulta)
    for i in range(1, max_iteraciones + 1):
        aceptada, critica = evaluar_borrador_volante(motivo_consulta, propuesta)
        if aceptada:
            return propuesta, True
        if i < max_iteraciones:
            propuesta = generar_borrador_volante(motivo_consulta, propuesta, critica)
    return propuesta, False