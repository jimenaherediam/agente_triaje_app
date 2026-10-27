from pydantic import BaseModel, Field
from domain.schemas import EspecialidadMedica
from core.llm import crear_modelo

class ClasificacionTriaje(BaseModel):
    categoria: EspecialidadMedica = Field(
        ..., 
        description="Especialidad de destino: 'cardiologia', 'neumologia', 'traumatologia' o 'general'"
    )
    motivo: str = Field(
        ..., 
        description="Breve justificación clínica de por qué se asigna a esta especialidad"
    )

PROMPT_ROUTER = """Eres el sistema de triaje hospitalario de urgencias.
Tu ÚNICA tarea es clasificar el motivo de consulta del paciente en una de estas 4 especialidades:
- cardiologia: dolor torácico, palpitaciones, síncope, insuficiencia cardíaca, sospecha de infarto o SCACEST.
- neumologia: disnea respiratoria, tos persistente, expectoración, patología pulmonar.
- traumatologia: fracturas, esguinces, dolor articular, traumatismos óseos, lesiones ligamentosas.
- general: síntomas inespecíficos, consultas enciclopédicas, analíticas generales.

Clasifica de forma estricta según el síntoma predominante.
"""

async def clasificar_motivo_triaje(pregunta: str) -> ClasificacionTriaje:
    llm = crear_modelo()
    llm_estructurado = llm.with_structured_output(ClasificacionTriaje)
    
    # Invocamos pasando el contexto del sistema
    resultado = await llm_estructurado.ainvoke([
        {"role": "system", "content": PROMPT_ROUTER},
        {"role": "user", "content": pregunta}
    ])
    return resultado