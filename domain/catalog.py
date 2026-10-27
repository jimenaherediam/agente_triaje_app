import unicodedata
from typing import Dict, List


def normalizar_texto(texto: str) -> str:
    """Elimina tildes, diacríticos y convierte a minúsculas para comparaciones deterministas."""
    if not texto:
        return ""
    s = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


# Cartera de servicios y pruebas diagnósticas oficiales del centro hospitalario
CATALOGO_PRUEBAS: Dict[str, List[str]] = {
    "cardiologia": [
        "electrocardiograma",
        "ecocardiograma transtoracico",
        "ergometria",
        "holter ecg 24h"
    ],
    "neumologia": [
        "radiografia de torax",
        "espirometria forzada",
        "tac toracico",
        "gasometria arterial"
    ],
    "traumatologia": [
        "radiografia simple",
        "resonancia magnetica articular",
        "ecografia musculoesqueletica"
    ],
    "general": [
        "analitica sanguinea completa",
        "analitica de orina",
        "ecografia abdominal"
    ]
}


def obtener_pruebas_servicio(servicio: str) -> List[str]:
    """Devuelve la lista de pruebas oficiales para un servicio hospitalario dado."""
    s_norm = normalizar_texto(servicio)
    return CATALOGO_PRUEBAS.get(s_norm, [])


def es_prueba_valida(servicio: str, prueba: str) -> bool:
    """Verifica si una prueba concreta forma parte de la cartera del servicio."""
    s_norm = normalizar_texto(servicio)
    p_norm = normalizar_texto(prueba)
    
    pruebas_admitidas = obtener_pruebas_servicio(s_norm)
    return any(normalizar_texto(p) in p_norm for p in pruebas_admitidas)