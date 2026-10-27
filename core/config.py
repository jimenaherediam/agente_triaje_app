import os
from pathlib import Path

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Conexión con Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

# Modelo descargado en tu Ollama local
MODELO_OLLAMA = os.getenv("MODELO_OLLAMA", "qwen3.5:4b")

# Parámetros de inferencia clínica
TEMPERATURA = 0.2          # Baja para respuestas médicas estables y reproducibles
NUM_CTX = 8192             # Ventana de contexto adecuada para el contenedor
MAX_TOKENS_SALIDA = 512    # Límite por generación para evitar divagaciones

# Rutas de datos
SKILLS_DIR = BASE_DIR / "skills"