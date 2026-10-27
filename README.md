# 🏥 Sistema Agéntico de Triaje Clínico & Prescripción Diagnóstica

Sistema asistencial de Inteligencia Artificial agéntica basado en modelos abiertos locales (**Ollama**) y orquestado mediante **LangChain** y **LangGraph**. El sistema implementa enrutamiento clínico multiespecialidad, revelación progresiva de conocimiento (*skills*), barreras técnicas de seguridad deterministas (*guardrails*) y supervisión humana obligatoria (*Human-in-the-Loop*) conforme a los requisitos del Artículo 14 del Reglamento de Inteligencia Artificial (RIA) de la UE para sistemas de alto riesgo.

---

## 📋 Tabla de Contenidos

1. [Arquitectura del Sistema](#-arquitectura-del-sistema)
2. [Garantías y Mecanismos de Seguridad](#-garantías-y-mecanismos-de-seguridad)
3. [Estructura del Proyecto](#-estructura-del-proyecto)
4. [Requisitos Previos](#-requisitos-previos)
5. [Instalación y Despliegue](#-instalación-y-despliegue)
   - [Opción A: Con Dev Containers en VS Code (Recomendada)](#opción-a-con-dev-containers-en-vs-code-recomendada)
   - [Opción B: Entorno Virtual Local](#opción-b-entorno-virtual-local)
6. [Guía de Uso y Casos de Prueba](#-guía-de-uso-y-casos-de-prueba)
7. [API Endpoints](#-api-endpoints)

---

## 🧠 Arquitectura del Sistema

El sistema abandona el enfoque de agente monolítico en favor de un flujo de trabajo modular orquestado por un grafo de estados (`StateGraph` de LangGraph):
![Diagrama de Arquitectura de la Aplicación](/arquitectura.png)
### Componentes Principales

1. **Enrutador Clínico (`agents/router.py`):** Clasifica deterministamente el motivo de consulta mediante salida estructurada (`json_schema`) hacia una de las 4 especialidades: `cardiologia`, `neumologia`, `traumatologia` o `general`.
2. **Revelación Progresiva de Conocimiento (*Skills*):** Las guías clínicas completas (`skills/*/SKILL.md`) no saturan el prompt inicial. El agente solo recibe un catálogo de nombres/descripciones y carga el protocolo detallado mediante la herramienta `load_skill` únicamente si el caso lo amerita.
3. **Agentes Especialistas (`agents/workflows.py`):** Instancias acotadas con autonomía limitada (máximo de llamadas al modelo y a herramientas) respaldadas por consultas a fuentes externas (`tools/wikipedia.py`).

---

## 🛡️ Garantías y Mecanismos de Seguridad

* **Separación Estricta entre Decisión y Ejecución:** El modelo de lenguaje nunca ejecuta acciones de base de datos directamente; solo emite intenciones en formato texto/JSON. La ejecución real reside en el runtime de Python.
* **Guardrails Deterministas por Código (`guardrails/code_guards.py`):**
  - **Validación de Cartera:** Rechaza peticiones fuera del catálogo oficial de la especialidad (ej. una resonancia cerebral solicitada a cardiología).
  - **Filtro de No-Duplicidad:** Bloquea automáticamente pruebas idénticas realizadas en los últimos 30 días para el mismo NHC, evitando la fatiga de alertas del personal médico.
* **Supervisión Facultativa (*Human-in-the-Loop* - HITL):** Ningún volante con impacto clínico o legal accede a la base de datos sin la ratificación explícita de un médico.

---

## 📂 Estructura del Proyecto

```text
app_triaje/
├── core/
│   ├── config.py              # Variables de entorno, host de Ollama y rutas
│   └── llm.py                 # Factoría y healthcheck de ChatOllama
├── domain/
│   ├── schemas.py             # Modelos Pydantic (ClasificacionTriaje, Volante, etc.)
│   └── catalog.py             # Cartera hospitalaria y normalización de texto
├── tools/
│   ├── wikipedia.py           # Herramientas de consulta médica con recorte defensivo
│   ├── skills_loader.py       # Carga dinámica bajo demanda de SKILL.md
│   └── clinical_ehr.py        # Herramienta sensible de registro en EHR
├── guardrails/
│   ├── code_guards.py         # Filtros deterministas por código (catálogo y <30 días)
│   └── evaluator.py           # Criterios del evaluador de volantes
├── agents/
│   ├── router.py              # Clasificador estructurado por especialidades
│   ├── evaluator_loop.py      # Patrón Evaluador-Optimizador
│   └── workflows.py           # StateGraph de LangGraph
├── skills/                    # Protocolos clínicos procedurales en Markdown
│   ├── protocolo-scacest/
│   ├── generacion-volante/
│   └── ficha-enciclopedica/
├── api/
│   └── main.py                # Endpoints FastAPI y gestión del flujo HITL
├── frontend/
│   └── app.py                 # Panel de 3 columnas en Streamlit
├── requirements.txt           # Dependencias fijadas del proyecto
└── README.md
```

---

## 📦 Requisitos Previos

1. **Ollama** instalado en la máquina anfitriona con el modelo descargado:
   ```bash
   ollama pull qwen3.5:4b   # O el modelo qwen que utilices
   ```
2. Asegurar que Ollama escuche en todas las interfaces para permitir peticiones desde Docker/contenedores:
   - **Linux / macOS:** Arrancar con `OLLAMA_HOST=0.0.0.0:11434 ollama serve`
   - **Windows:** Configurar la variable de entorno de sistema `OLLAMA_HOST=0.0.0.0:11434`

---

## 🚀 Instalación y Despliegue

### Opción A: Con Dev Containers en VS Code (Recomendada)

1. Abre la carpeta del proyecto en **VS Code**.
2. Cuando aparezca el aviso emergente, pulsa en **Reopen in Container** (o abre la paleta `Cmd+Shift+P` / `Ctrl+Shift+P` y ejecuta `Dev Containers: Rebuild and Reopen in Container`).
3. Abre dos terminales integradas dentro de VS Code:

   - **Terminal 1 (Backend API):**
     ```bash
     python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
     ```

   - **Terminal 2 (Frontend Streamlit):**
     ```bash
     python -m streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
     ```

4. Accede en tu navegador a: **`http://localhost:8501`**.

---

### Opción B: Entorno Virtual Local

```bash
# 1. Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate   # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Lanzar FastAPI
uvicorn api.main:app --port 8000 --reload &

# 4. Lanzar Streamlit
streamlit run frontend/app.py --server.port 8501
```

---

## 🧪 Guía de Uso y Casos de Prueba

La interfaz cuenta con 3 áreas: **Consulta del Paciente**, **Consola Médica (HITL)** y **Trazabilidad & Guardrails**.

### Caso 1: Flujo Normal con Supervisión Facultativa (Éxito)
* **NHC:** `PAC-8921`
* **Síntomas:**
  > *Paciente varón de 64 años refiere disnea de esfuerzo progresiva de 3 semanas, ortopnea y edemas maleolares bilaterales. Se ausculta soplo sistólico en foco aórtico.*
* **Comportamiento esperado:**
  - El enrutador clasifica a `cardiologia`.
  - El especialista determina que la indicación es un **ecocardiograma transtorácico**.
  - Supera los guardrails de código (está en catálogo y no tiene estudios previos recientes).
  - Aparece la alerta amarilla en la **Consola Médica**. Al pulsar **"Firmar y Emitir"**, se registra en la base de datos EHR.

### Caso 2: Bloqueo Inmediato por Duplicidad (< 30 días)
* **NHC:** `PAC-8921`
* **Síntomas:** Vuelve a enviar inmediatamente los mismos síntomas del Caso 1 para el mismo paciente tras haber firmado la prueba.
* **Comportamiento esperado:**
  - El guardrail detecta que el ecocardiograma se realizó hace 0 días.
  - La columna de trazas muestra la alerta roja de **duplicidad temporal**.
  - La consola médica permanece limpia (el código frena la solicitud sin molestar al médico).

### Caso 3: Consulta de Traumatología
* **NHC:** `PAC-8921`
* **Síntomas:**
  > *Paciente varón de 24 años acude tras sufrir una torsión brusca de rodilla derecha jugando al fútbol. Refiere chasquido audible, dolor agudo, impotencia funcional y derrame articular.*
* **Comportamiento esperado:**
  - El enrutador asigna a `traumatologia`.
  - Recomienda radiografía o resonancia articular.
  - La prueba pasa a supervisión facultativa para su firma.

---

## 📡 API Endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/triaje` | Inicia el flujo del grafo, evalúa guardrails y determina si requiere supervisión médica. |
| `POST` | `/api/decision` | Resuelve la decisión facultativa (`approve` / `reject`) y persiste en el EHR. |
| `GET` | `/api/volantes` | Devuelve el listado de volantes formalizados en el hospital. |

---
