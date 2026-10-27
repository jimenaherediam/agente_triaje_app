from tools.wikipedia import buscar_wikipedia, extracto_wikipedia
from tools.skills_loader import load_skill, catalogo_skills
from tools.clinical_ehr import emitir_volante_ehr, obtener_volantes_emitidos

# Herramientas de solo lectura (seguras)
HERRAMIENTAS_CONSULTA = [buscar_wikipedia, extracto_wikipedia, load_skill]

# Herramientas de escritura (sensibles)
HERRAMIENTAS_ESCRITURA = [emitir_volante_ehr]

__all__ = [
    "buscar_wikipedia",
    "extracto_wikipedia",
    "load_skill",
    "catalogo_skills",
    "emitir_volante_ehr",
    "obtener_volantes_emitidos",
    "HERRAMIENTAS_CONSULTA",
    "HERRAMIENTAS_ESCRITURA"
]