from typing import Tuple
from domain.catalog import normalizar_texto, CATALOGO_PRUEBAS, es_prueba_valida


def corrector_volante_por_codigo(respuesta: str) -> Tuple[bool, str]:
    """
    Evalúa si un texto de volante cumple los requisitos mínimos obligatorios
    sin intervención de un LLM:
    - Debe incluir cita médica o fuente de referencia.
    - Debe identificar exactamente un servicio oficial.
    - La prueba debe estar catalogada dentro de ese servicio.
    - Debe asignar una prioridad válida (urgente, preferente, ordinaria).
    """
    resp_norm = normalizar_texto(respuesta)

    # 1. Cita médica explícita
    palabras_clave_fuente = ("fuente:", "guia", "protocolo", "wikipedia", "referencia", "segun")
    if not any(f in resp_norm for f in palabras_clave_fuente):
        return False, "Falta incluir la fuente o cita clínica de referencia (ej. Wikipedia o guía clínica)."

    # 2. Un único servicio clínico asignado
    servicios_encontrados = [s for s in CATALOGO_PRUEBAS if s in resp_norm]
    if len(servicios_encontrados) != 1:
        return (
            False,
            f"Debe indicar exactamente un servicio hospitalario válido "
            f"({', '.join(CATALOGO_PRUEBAS.keys())}). Encontrados: {servicios_encontrados or 'ninguno'}."
        )
    servicio = servicios_encontrados[0]

    # 3. Prueba dentro del catálogo del servicio
    if not es_prueba_valida(servicio, resp_norm):
        pruebas_servicio = ", ".join(CATALOGO_PRUEBAS[servicio])
        return (
            False,
            f"La prueba solicitada no está en el catálogo de {servicio}. "
            f"Opciones admitidas: {pruebas_servicio}."
        )

    # 4. Nivel de prioridad normalizado
    prioridades_admitidas = ("urgente", "preferente", "ordinaria")
    if not any(p in resp_norm for p in prioridades_admitidas):
        return False, "Debe fijar una prioridad normalizada válida (urgente, preferente u ordinaria)."

    return True, "Volante formalmente correcto según normativa de código."