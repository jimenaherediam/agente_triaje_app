from typing import Literal, Optional
from pydantic import BaseModel, Field


# Tipos clínicos restringidos
EspecialidadMedica = Literal["cardiologia", "neumologia", "traumatologia", "general"]
PrioridadTriaje = Literal["urgente", "preferente", "ordinaria"]


class ClasificacionTriaje(BaseModel):
    """Esquema de salida estructurada para el enrutador hospitalario."""
    motivo: str = Field(
        ...,
        description="Justificación clínica de la especialidad elegida en una sola frase breve."
    )
    categoria: EspecialidadMedica = Field(
        ...,
        description="Especialidad hospitalaria de destino según la sintomatología predominante."
    )


class PropuestaVolante(BaseModel):
    """Estructura completa de un volante médico prescrito por el agente."""
    nhc: str = Field(..., description="Número de Historia Clínica del paciente.")
    sospecha_diagnostica: str = Field(..., description="Impresión diagnóstica principal.")
    servicio: EspecialidadMedica = Field(..., description="Servicio hospitalario de destino.")
    prueba: str = Field(..., description="Nombre exacto de la prueba solicitada según catálogo.")
    prioridad: PrioridadTriaje = Field(..., description="Grado de prioridad de la indicación.")
    justificacion: str = Field(..., description="Justificación médica y cita bibliográfica/guía de soporte.")


class VeredictoClinico(BaseModel):
    """Esquema de juicio del Evaluador-Optimizador sobre la coherencia de la prueba."""
    indicacion_coherente: bool = Field(
        ...,
        description="True si la prueba diagnóstica y su prioridad son clínicamente coherentes con los síntomas."
    )
    critica: Optional[str] = Field(
        default="",
        description="Crítica concisa (menos de 25 palabras) con las correcciones requeridas; vacía si es correcto."
    )