import re
from pathlib import Path
from typing import Dict, Tuple
from langchain_core.tools import tool
from core.config import SKILLS_DIR


def leer_skill(ruta_fichero: Path) -> Tuple[Dict[str, str], str]:
    """Separa la cabecera YAML (entre ---) del cuerpo de instrucciones de un SKILL.md."""
    contenido = ruta_fichero.read_text(encoding="utf-8")
    partes = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", contenido, re.DOTALL)
    if not partes:
        raise ValueError(f"{ruta_fichero}: Formato inválido. Debe contener cabecera entre líneas '---'.")
    
    cabecera_lineas = partes.group(1).splitlines()
    cabecera = dict(
        linea.split(":", 1)
        for linea in cabecera_lineas
        if ":" in linea
    )
    cabecera_limpia = {k.strip(): v.strip() for k, v in cabecera.items()}
    cuerpo = partes.group(2).strip()
    return cabecera_limpia, cuerpo


def catalogo_skills() -> Dict[str, str]:
    """Devuelve un diccionario {nombre_skill: descripcion} con las skills disponibles en disco."""
    catalogo = {}
    if not SKILLS_DIR.exists():
        return catalogo

    for ruta in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        try:
            cabecera, _ = leer_skill(ruta)
            nombre = cabecera.get("name", ruta.parent.name)
            descripcion = cabecera.get("description", "")
            catalogo[nombre] = descripcion
        except Exception:
            continue
    return catalogo


@tool
def load_skill(nombre: str) -> str:
    """Carga las instrucciones completas de una skill clínica. 
    Llámala cuando la petición encaje con la descripción de un protocolo especializado."""
    disponibles = catalogo_skills()
    if nombre not in disponibles:
        return f"ERROR: No existe la skill '{nombre}'. Skills clínicas disponibles: {', '.join(disponibles.keys())}."
    
    ruta_skill = SKILLS_DIR / nombre / "SKILL.md"
    try:
        _, cuerpo = leer_skill(ruta_skill)
        return cuerpo
    except Exception as e:
        return f"ERROR al leer la skill '{nombre}': {e}"