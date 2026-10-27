from datetime import datetime
from typing import List, Dict, Any
from langchain_core.tools import tool

# Base de datos simulada de volantes formalizados en el hospital
REGISTRO_EHR_DB: List[Dict[str, Any]] = []


@tool
def emitir_volante_ehr(
    nhc: str,
    servicio: str,
    prueba: str,
    prioridad: str,
    justificacion: str
) -> str:
    """Acción sensible: Registra formalmente el volante médico de prueba diagnóstica en el EHR hospitalario."""
    nuevo_registro = {
        "id": len(REGISTRO_EHR_DB) + 1,
        "nhc": nhc.strip().upper(),
        "servicio": servicio.strip().lower(),
        "prueba": prueba.strip().lower(),
        "prioridad": prioridad.strip().lower(),
        "justificacion": justificacion.strip(),
        "fecha_creacion": datetime.now().isoformat()
    }
    REGISTRO_EHR_DB.append(nuevo_registro)
    return (
        f"Volante formalizado con éxito en el sistema EHR. "
        f"ID de prescripción: {nuevo_registro['id']} | Servicio: {nuevo_registro['servicio'].upper()} | "
        f"Prueba: {nuevo_registro['prueba'].upper()}."
    )


def obtener_volantes_emitidos() -> List[Dict[str, Any]]:
    """Consulta administrativa de los volantes registrados."""
    return list(REGISTRO_EHR_DB)