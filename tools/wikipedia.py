import re
import requests
from typing import List, Dict, Union, Tuple, Optional
from langchain_core.tools import tool

CABECERAS_WIKIPEDIA = {
    "User-Agent": "AsistenteTriajeClinico/1.0 (Entorno local; devcontainer) python-requests"
}


def _api_wikipedia(reintentos: int = 2, **parametros) -> Tuple[Optional[dict], Optional[str]]:
    """Consulta la API pública de MediaWiki con reintentos para fallos transitorios."""
    for intento in range(reintentos + 1):
        try:
            r = requests.get(
                "https://es.wikipedia.org/w/api.php",
                headers=CABECERAS_WIKIPEDIA,
                timeout=15,
                params={"format": "json", "utf8": 1, **parametros}
            )
            if r.status_code == 200:
                return r.json(), None
            error = f"ERROR HTTP {r.status_code}: {r.text[:150]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                return None, error
        except requests.RequestException as e:
            error = f"ERROR de red: {type(e).__name__}: {str(e)[:150]}"
    return None, error


@tool
def buscar_wikipedia(consulta: str) -> List[Dict[str, str]]:
    """Busca en Wikipedia articulos medicos y clinicos; devuelve hasta 3 articulos (titulo y fragmento)."""
    datos, error = _api_wikipedia(action="query", list="search", srsearch=consulta, srlimit=3)
    if error:
        return [{"error": error}]
    
    resultados = datos.get("query", {}).get("search", [])
    return [
        {
            "titulo": s["title"],
            "fragmento": re.sub(r"<[^>]+>", "", s["snippet"]).strip()
        }
        for s in resultados
    ]


@tool
def extracto_wikipedia(titulo: str) -> str:
    """Devuelve la introduccion clinica o concepto del articulo de Wikipedia con ese titulo exacto."""
    datos, error = _api_wikipedia(
        action="query",
        prop="extracts",
        titles=titulo,
        exintro=1,
        explaintext=1,
        redirects=1
    )
    if error:
        return error
    
    paginas = datos.get("query", {}).get("pages", {})
    if not paginas:
        return f"No se encontró información para '{titulo}'."
    
    pagina = next(iter(paginas.values()))
    extracto = pagina.get("extract", "")
    
    # Recorte defensivo de tokens
    if extracto:
        return extracto[:1500]
    return f"No existe ningún artículo médico titulado '{titulo}'."