import requests
from langchain_ollama import ChatOllama
from core.config import (
    OLLAMA_HOST,
    MODELO_OLLAMA,
    TEMPERATURA,
    NUM_CTX,
    MAX_TOKENS_SALIDA
)


def comprobar_conexion_ollama() -> bool:
    """Verifica si el servidor Ollama responde desde dentro del Dev Container."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/version", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def crear_modelo(temperatura: float = None) -> ChatOllama:
    """
    Instancia el cliente de chat de LangChain sobre Ollama.
    reasoning=False evita que gaste tokens en bucles de pensamiento libre.
    """
    if not comprobar_conexion_ollama():
        raise ConnectionError(
            f"No se puede conectar con Ollama en '{OLLAMA_HOST}'.\n"
            "Asegúrate de que Ollama está en ejecución en tu ordenador y de que "
            "acepta conexiones externas (OLLAMA_HOST=0.0.0.0:11434)."
        )

    temp = TEMPERATURA if temperatura is None else temperatura

    return ChatOllama(
        model=MODELO_OLLAMA,
        base_url=OLLAMA_HOST,
        temperature=temp,
        num_ctx=NUM_CTX,
        num_predict=MAX_TOKENS_SALIDA,
        reasoning=False,
        keep_alive="30m"
    )


if __name__ == "__main__":
    # Test rápido de ejecución directa
    print(f"Probando conexión con Ollama en {OLLAMA_HOST}...")
    try:
        llm = crear_modelo()
        respuesta = llm.invoke("Responde únicamente con la palabra: LISTO")
        print("Respuesta del modelo:", respuesta.content.strip())
    except Exception as e:
        print("Error al inicializar el modelo:", e)