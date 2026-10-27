import streamlit as st
import requests

st.set_page_config(page_title="Triaje Clínico Agéntico", layout="wide", page_icon="🏥")

API_BASE = "http://127.0.0.1:8000"

st.title("🏥 Sistema de Triaje Clínico & Supervisión Médica")
st.caption("Arquitectura agéntica con enrutamiento hospitalario, guardrails deterministas y supervisión HITL (RIA Art. 14)")

# Variables de sesión para persistir el estado entre re-renders
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []
if "caso_pendiente_hitl" not in st.session_state:
    st.session_state.caso_pendiente_hitl = None
if "trazas_recientes" not in st.session_state:
    st.session_state.trazas_recientes = []

# Disposición en 3 columnas
col_paciente, col_medico, col_trazas = st.columns([1.2, 1.2, 1.1], gap="medium")
# ==========================================
# COLUMNA 1: MENSAJE DEL PACIENTE
# ==========================================
with col_paciente:
    st.subheader("👤 Consulta del Paciente")
    nhc = st.text_input("NHC (Nº Historia)", value="PAC-8921")
    
    pregunta = st.text_area(
        "Motivo de consulta / Síntomas:",
        height=140,
        placeholder="Describe el cuadro clínico (ej: Paciente varón de 64 años refiere disnea de esfuerzo progresiva de 3 semanas, ortopnea y edemas maleolares bilaterales. Se ausculta soplo sistólico...)"
    )

    if st.button("Enviar a Triaje Clínico", type="primary", use_container_width=True):
        if not pregunta.strip():
            st.warning("Por favor, introduce los síntomas del paciente.")
        else:
            with st.spinner("El agente está clasificando el caso, consultando protocolos y determinando la prueba..."):
                payload = {"nhc": nhc, "pregunta": pregunta}
                try:
                    r = requests.post(f"{API_BASE}/api/triaje", json=payload, timeout=35)
                    data = r.json()
                    
                    st.session_state.historial_chat.append({
                        "paciente": pregunta,
                        "respuesta": data.get("respuesta_especialista") or data.get("resultado_final")
                    })
                    
                    st.session_state.trazas_recientes.append({
                        "nhc": nhc,
                        "categoria": data.get("categoria"),
                        "motivo_triaje": data.get("motivo_triaje"),
                        "skills_usadas":data.get("skills_usadas", []),
                        "prueba_agente": data.get("prueba_decidida_por_agente"),
                        "error_guardrail": data.get("error_guardrail"),
                        "requiere_supervision": data.get("requiere_supervision")
                    })

                    if data.get("requiere_supervision"):
                        st.session_state.caso_pendiente_hitl = {
                            "thread_id": data["thread_id"],
                            "nhc": nhc,
                            "categoria": data["categoria"],
                            "prueba": data.get("prueba_decidida_por_agente"),
                            "sintomas": pregunta
                        }
                    else:
                        st.session_state.caso_pendiente_hitl = None

                except Exception as e:
                    st.error(f"Error conectando a la API: {e}")

    st.divider()
    st.markdown("#### Historial de consultas")
    for msg in reversed(st.session_state.historial_chat):
        with st.chat_message("user"):
            st.write(msg["paciente"])
        with st.chat_message("assistant"):
            st.write(msg["respuesta"])

# ==========================================
# COLUMNA 2: SUPERVISIÓN FACULTATIVA (HITL)
# ==========================================
with col_medico:
    st.subheader("🩺 Consola Médica (HITL)")
    caso = st.session_state.caso_pendiente_hitl
    
    if caso:
        st.warning("⚠️ **ACCIÓN SENSIBLE PENDIENTE DE RATIFICACIÓN MÉDICA**")
        st.info(
            f"**NHC:** {caso['nhc']}\n\n"
            f"**Servicio Asignado:** {str(caso['categoria']).upper()}\n\n"
            f"**Prueba Propuesta:** {caso['prueba'].upper()}\n\n"
            f"**Cuadro Clínico:** {caso['sintomas']}"
        )
        
        c_apr, c_rec = st.columns(2)
        with c_apr:
            if st.button("✅ Firmar y Emitir", type="primary", use_container_width=True):
                with st.spinner("Registrando en EHR..."):
                    try:
                        r = requests.post(
                            f"{API_BASE}/api/decision",
                            json={"thread_id": caso["thread_id"], "aprobado": True},
                            timeout=15
                        )
                        if r.status_code == 200:
                            st.success("¡Volante emitido y registrado con éxito!")
                            st.session_state.caso_pendiente_hitl = None
                            st.rerun()
                        else:
                            st.error(f"Error en API ({r.status_code}): {r.text}")
                    except Exception as err:
                        st.error(f"Fallo de conexión: {err}")
        with c_rec:
            if st.button("❌ Denegar Volante", use_container_width=True):
                r = requests.post(
                    f"{API_BASE}/api/decision",
                    json={"thread_id": caso["thread_id"], "aprobado": False}
                )
                if r.status_code == 200:
                    st.error("Prescripción denegada por el facultativo.")
                    st.session_state.caso_pendiente_hitl = None
                    st.rerun()
    else:
        st.success("Bandeja limpia: No hay prescripciones pendientes de supervisión.")
        st.caption("Las pruebas que vulneran guardrails técnicos (duplicidad o catálogo) son filtradas por código antes de molestar al médico.")

    st.divider()
    st.markdown("#### Base de Datos EHR (Volantes Formalizados)")
    try:
        r_db = requests.get(f"{API_BASE}/api/volantes", timeout=5)
        volantes = r_db.json().get("volantes", [])
        if volantes:
            st.dataframe(volantes, use_container_width=True)
        else:
            st.caption("Aún no se han emitido volantes firmados.")
    except Exception:
        st.caption("No se pudo cargar la base de datos del EHR.")

# ==========================================
# COLUMNA 3: INSPECTOR DE TRAZAS Y ESTADO
# ==========================================
with col_trazas:
    st.subheader("🔍 Trazabilidad & Guardrails")
    
    if st.session_state.trazas_recientes:
        for i, traza in enumerate(reversed(st.session_state.trazas_recientes[-5:]), 1):
            with st.expander(f"Traza #{len(st.session_state.trazas_recientes) - i + 1} - {traza.get('categoria', 'N/A').upper()}", expanded=(i == 1)):
                st.write(f"**Especialidad Enrutada:** `{traza.get('categoria')}`")
                st.write(f"**Motivo Enrutador:** {traza.get('motivo_triaje')}")
                
                # Visualización de Skills clínicas
                skills = traza.get("skills_usadas", [])
                if skills:
                    st.markdown("**🧠 Skills Clínicas Activadas:**")
                    for s in skills:
                        st.info(f"📄 `{s}` (cargada dinámicamente desde Markdown)")
                else:
                    st.caption("ℹ️ No se requirió carga de skills procedurales externas.")

                if traza.get("error_guardrail"):
                    st.error(f"**Guardrail Activado:** {traza['error_guardrail']}")
                else:
                    st.success("**Guardrail Determinista:** Superado (Catálogo OK y sin duplicidad <30 días)")
                
                st.write(f"**Escalado a HITL:** `{'SÍ' if traza.get('requiere_supervision') else 'NO'}`")
    else:
        st.caption("Envía una consulta para visualizar el árbol de decisiones del grafo y los filtros deterministas.")