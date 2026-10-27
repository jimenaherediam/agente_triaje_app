from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any
from domain.catalog import normalizar_texto, es_prueba_valida

# Simulación del historial clínico del paciente (en producción se consulta el EHR/HIS)
HISTORIAL_PACIENTE_DB: List[Dict[str, Any]] = [
    {
        "nhc": "PAC-8921",
        "servicio": "cardiologia",
        "prueba": "electrocardiograma",
        "fecha": datetime.now() - timedelta(days=12)  # Realizada hace 12 días (< 30 días)
    },
    {
        "nhc": "PAC-8921",
        "servicio": "traumatologia",
        "prueba": "radiografia simple",
        "fecha": datetime.now() - timedelta(days=45)  # Realizada hace 45 días (> 30 días, permitida)
    }
]


def registrar_prueba_historial(nhc: str, servicio: str, prueba: str) -> None:
    """Añade una prueba realizada al historial para alimentar futuras comprobaciones."""
    HISTORIAL_PACIENTE_DB.append({
        "nhc": nhc.strip().upper(),
        "servicio": normalizar_texto(servicio),
        "prueba": normalizar_texto(prueba),
        "fecha": datetime.now()
    })


def guardrail_prescripcion_clinica(
    nhc: str,
    servicio: str,
    prueba: str,
    dias_limite_duplicidad: int = 30
) -> Tuple[bool, str]:
    """
    Barrera determinista por código:
    1. Valida que la prueba pertenezca a la cartera de servicios oficial.
    2. Evita la duplicidad de pruebas diagnósticas idénticas en menos de N días.
    """
    nhc_norm = nhc.strip().upper()
    s_norm = normalizar_texto(servicio)
    p_norm = normalizar_texto(prueba)

    # 1. Validación de cartera oficial de servicios
    if not es_prueba_valida(s_norm, p_norm):
        return (
            False,
            f"GUARDRAIL BLOQUEO: La prueba '{prueba}' no pertenece a la cartera "
            f"oficial del servicio '{servicio}'."
        )

    # 2. Control de duplicidad temporal en el historial
    fecha_limite = datetime.now() - timedelta(days=dias_limite_duplicidad)
    for registro in HISTORIAL_PACIENTE_DB:
        if registro["nhc"] == nhc_norm and registro["servicio"] == s_norm:
            if normalizar_texto(registro["prueba"]) in p_norm and registro["fecha"] > fecha_limite:
                dias_transcurridos = (datetime.now() - registro["fecha"]).days
                return (
                    False,
                    f"GUARDRAIL ALERTA DUPLICIDAD: La prueba '{prueba}' ya fue realizada hace "
                    f"{dias_transcurridos} días (límite de seguridad: {dias_limite_duplicidad} días). "
                    f"Requiere justificación facultativa expresa."
                )

    return True, "GUARDRAIL SUPERADO: Prescripción conforme a normas técnicas."