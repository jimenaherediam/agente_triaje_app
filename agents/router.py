from core.llm import crear_modelo
from domain.schemas import ClasificacionTriaje

PROMPT_ENRUTADOR_CLINICO = (
    "Eres un médico coordinador de triaje hospitalario. Clasifica el motivo de consulta del paciente "
    "en una única especialidad de destino:\n"
    "- cardiologia: dolor precordial/retroesternal, dolor torácico postural (pericarditis), palpitaciones, síncope, sospecha coronaria o arritmias.\n"
    "- neumologia: disnea, tos crónica persistente, hemoptisis, ruidos respiratorios, dolor pleurítico respiratorio puro.\n"
    "- traumatologia: fracturas, esguinces, dolor articular mecánico, traumatismos óseos o deformidades.\n"
    "- general: fiebre sin foco, malestar general, astenia, epigastralgia, alteraciones analíticas inespecíficas.\n"
    "Responde obligatoriamente cumpliendo el esquema JSON indicado."
)

# Modelo con temperatura 0 para máxima consistencia determinista
_modelo_clasificador = crear_modelo(temperatura=0).with_structured_output(
    ClasificacionTriaje, method="json_schema"
)


async def clasificar_motivo_triaje(motivo_consulta: str) -> ClasificacionTriaje:
    """Clasifica el motivo de consulta del paciente en una especialidad médica mediante Pydantic."""
    return await _modelo_clasificador.ainvoke([
        {"role": "system", "content": PROMPT_ENRUTADOR_CLINICO},
        {"role": "user", "content": motivo_consulta}
    ])