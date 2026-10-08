import os
import re
import streamlit as st
from datetime import datetime

# Version 2.2 - Agregacion Anual y Trimestral consolidada

# -------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO
# -------------------------------------------------------------
st.set_page_config(
    page_title="Agente Master de Inteligencia Operativa V2",
    page_icon="🤖",
    layout="wide"
)

# Estilo CSS de alto contraste y refinamiento visual
st.markdown("""
<style>
/* Borde oscuro y visible para todos los inputs */
.stTextInput input, 
div[data-baseweb="input"], 
div[data-baseweb="base-input"] {
    background-color: #ffffff !important;
    border: 2px solid #334155 !important;
    border-radius: 8px !important;
    color: #0f172a !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05) !important;
}

.stTextInput input:hover, 
div[data-baseweb="input"]:hover {
    border-color: #0f172a !important;
}

.stTextInput input:focus, 
div[data-baseweb="input"]:focus-within {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25) !important;
}

.stTextInput label {
    font-weight: 600 !important;
    color: #1e293b !important;
}

.module-badge {
    display: inline-block;
    padding: 3px 8px;
    margin: 2px;
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #334155;
}

/* Evitar el efecto de pantalla grisada/desvanecida mientras Streamlit procesa una consulta */
div[data-stale="true"],
div[data-testid="stChatMessage"][data-stale="true"],
.stElementContainer[data-stale="true"],
div[data-testid="stVerticalBlock"] > div[data-stale="true"] {
    opacity: 1 !important;
    filter: none !important;
    transition: none !important;
}
</style>
""", unsafe_allow_html=True)

AVATAR_PATH = "bot_avatar.png" if os.path.exists("bot_avatar.png") else "🤖"

# -------------------------------------------------------------
# 2. AUTENTICACIÓN EN DOS PASOS
# -------------------------------------------------------------
from core.auth import (
    render_login,
    cerrar_sesion,
    render_admin_users_manager,
    render_presence_indicator,
    PASSWORD_ADMIN
)
from core.database_redis import (
    cargar_historial_usuario,
    guardar_historial_usuario,
    obtener_fecha_base,
    get_presencia_global
)
from core.graficos import dibujar_grafico
from core.exportador_pdf import render_boton_descarga_pdf
from core.motor_gemini import (
    obtener_cliente_gemini,
    obtener_frase_spinner,
    consultar_gemini
)
from core import gestor_modulos

if not render_login(avatar_path="bot_avatar.png"):
    st.stop()

# -------------------------------------------------------------
# 3. DESCUBRIMIENTO DE MÓDULOS Y BASES DE DATOS
# -------------------------------------------------------------
modulos = gestor_modulos.listar_modulos()
if not modulos:
    st.error("No se encontraron módulos disponibles en la carpeta 'modulos/'.")
    st.stop()

modulo_ids = [m["id"] for m in modulos]

# -------------------------------------------------------------
# 4. BARRA LATERAL (SIDEBAR): MONITOR MULTI-BASE Y ADMIN
# -------------------------------------------------------------
with st.sidebar:
    if os.path.exists("bot_avatar.png"):
        st.image("bot_avatar.png", width=65)

    st.markdown(f"👤 **Usuario:** `{st.session_state.get('user_display', 'Anónimo')}`")
    
    # Indicador de analistas activos en tiempo real
    render_presence_indicator()

    # Verificación de Gemini API Key en el servidor
    from core.database_redis import obtener_secreto
    api_key_actual = obtener_secreto("GEMINI_API_KEY", "") or st.session_state.get("gemini_api_key_manual", "")
    if not api_key_actual:
        st.divider()
        st.warning("⚠️ Falta configurar Gemini API Key en el servidor.")
        # Solo un administrador autenticado puede configurar la clave en tiempo de ejecución
        if st.session_state.get("admin_authenticated", False):
            key_input = st.text_input("Ingresar Gemini API Key (Admin):", type="password", key="input_api_key_sidebar", placeholder="AIzaSy...")
            if key_input:
                st.session_state.gemini_api_key_manual = key_input
                try:
                    import re
                    sec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
                    if os.path.exists(sec_path):
                        with open(sec_path, "r", encoding="utf-8") as f:
                            c_sec = f.read()
                        c_sec = re.sub(r'GEMINI_API_KEY\s*=\s*".*?"', f'GEMINI_API_KEY = "{key_input}"', c_sec)
                        with open(sec_path, "w", encoding="utf-8") as f:
                            f.write(c_sec)
                except Exception:
                    pass
                st.rerun()

    st.divider()

    # Estado de las 4 bases de datos conectadas con desplegables de métricas
    st.markdown("### 🗂️ Bases de Datos Conectadas")
    for i, m in enumerate(modulos):
        mid = m["id"]
        fecha_m = obtener_fecha_base(mid)
        icono = m.get("icono", "📊")
        nombre = m.get("nombre", mid)
        metricas = m.get("metricas", [])

        # Fecha de actualización pegada al cuadrante de este módulo, con separación del anterior
        m_top = "4px" if i == 0 else "18px"
        st.markdown(
            f"""<div style="margin-top: {m_top}; margin-bottom: -10px; font-size: 0.77rem; color: #475569; font-weight: 500;">
                🕒 Act: <span style="color: #0369a1; background: #e0f2fe; padding: 1px 6px; border-radius: 4px; font-weight: 600;">{fecha_m}</span>
            </div>""",
            unsafe_allow_html=True
        )
        with st.expander(f"{icono} {nombre}", expanded=False):
            if m.get("descripcion"):
                st.caption(f"*{m['descripcion']}*")
            if metricas:
                st.markdown("**📈 Métricas disponibles:**")
                for met in metricas:
                    st.markdown(f"• `{met}`")

    st.caption("⚡ **Powered by Mauro. R** &nbsp;|&nbsp; `v2.2`")
    st.divider()

    # Botones de control
    if st.button("🗑️ Nueva conversación", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": f"¡Hola **{st.session_state.user_display}**! Soy tu Agente Master de Inteligencia Operativa. Tengo acceso simultáneo a las 4 bases: **NPS**, **TMO**, **Transferencias** y **SPL**.\n\nPuedes hacerme cualquier consulta y accederé automáticamente al módulo o combinación de datos necesaria.",
                "chart": None,
                "modulos_usados": None
            }
        ]
        guardar_historial_usuario(st.session_state.current_user, "unificado", st.session_state.messages)
        st.rerun()

    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        cerrar_sesion()

    # ---------------------------------------------------------
    # PANEL DE ADMINISTRACIÓN MULTI-BASE
    # ---------------------------------------------------------
    st.divider()
    with st.expander("🔒 Panel de Administrador"):
        if not st.session_state.get("admin_authenticated", False):
            clave_admin = st.text_input("Contraseña de administrador:", type="password", key="admin_key_input")
            if st.button("Acceder como Admin", use_container_width=True):
                if not PASSWORD_ADMIN:
                    st.error("⚠️ Falta configurar 'ADMIN_PASSWORD' en .streamlit/secrets.toml")
                elif clave_admin == PASSWORD_ADMIN:
                    st.session_state.admin_authenticated = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
        else:
            st.success("Acceso de Administrador concedido.")
            if st.button("🔒 Volver y Bloquear Panel", use_container_width=True):
                st.session_state.admin_authenticated = False
                st.rerun()

            st.write("---")
            st.markdown("##### 📤 Actualizar Base de Datos")
            mod_destino_id = st.selectbox(
                "Selecciona base a actualizar:",
                options=modulo_ids,
                format_func=lambda mid: next(f"{m['icono']} {m['nombre']}" for m in modulos if m['id'] == mid),
                key="admin_modulo_target"
            )

            archivo_subido = st.file_uploader(
                f"Cargar nuevo Excel para {mod_destino_id.upper()}",
                type=["xlsx", "xls", "csv"],
                key="admin_file_uploader"
            )

            if archivo_subido is not None:
                if st.button("Confirmar y Guardar Base 💾", type="primary", use_container_width=True):
                    ok, msg = gestor_modulos.guardar_dataset_modulo(mod_destino_id, archivo_subido)
                    if ok:
                        st.success(f"✅ Base actualizada con éxito.")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {msg}")

            # Gestión de usuarios
            render_admin_users_manager()

# -------------------------------------------------------------
# 5. HISTORIAL DE MENSAJES UNIFICADO
# -------------------------------------------------------------
user_id = st.session_state.current_user

if "messages" not in st.session_state:
    historial_previo = cargar_historial_usuario(user_id, "unificado")
    if historial_previo:
        st.session_state.messages = historial_previo
    else:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": f"¡Hola **{st.session_state.user_display}**! Soy tu Agente Master de Inteligencia Operativa.\n\nTengo acceso simultáneo a todas las bases operativas:\n* 🌟 **NPS y Satisfacción**\n* ⏱️ **TMO y Tiempos**\n* 🔀 **Transferencias y Desvíos**\n* 🎯 **SPL y Reiteración**\n\nHazme cualquier consulta y accederé automáticamente a la base de datos o combinación de métricas correspondiente.",
                "chart": None,
                "modulos_usados": None
            }
        ]

if "ultimo_modulo_activo" not in st.session_state:
    st.session_state.ultimo_modulo_activo = None

# -------------------------------------------------------------
# 6. ENCABEZADO PRINCIPAL DE LA APLICACIÓN
# -------------------------------------------------------------
col_av, col_head = st.columns([0.08, 0.92], vertical_alignment="center")
with col_av:
    if os.path.exists("bot_avatar.png"):
        st.image("bot_avatar.png", width=65)
    else:
        st.markdown("## 🤖")
with col_head:
    st.title("Agente Master de Inteligencia Operativa")
    st.caption("Arquitectura V2 Multi-Módulo &nbsp;|&nbsp; Enrutamiento inteligente entre NPS, TMO, Transferencias y SPL &nbsp;|&nbsp; 🏷️ **v2.2**")

def es_tabla_compacta(texto_bloque1):
    """
    Determina si la tabla tiene 4 columnas o menos para validar si hay suficiente
    espacio en blanco a la derecha y colocar el Bloque 2 y 3 al lado.
    Si tiene más de 4 columnas, la tabla es ancha y debe ocupar ancho completo.
    """
    for linea in texto_bloque1.split("\n"):
        strip = linea.strip()
        if strip.startswith("|") and strip.endswith("|"):
            cols = [c.strip() for c in strip.split("|")[1:-1]]
            if cols and not any("---" in c for c in cols):
                return len(cols) <= 4
    return True

def render_contenido_asistente(content, chart=None, key_chart=None, modulos_usados=None, key_pdf=None):
    """
    Renderiza la respuesta del asistente de forma adaptable:
    - Si la tabla de datos tiene espacio en blanco lateral (<= 4 columnas):
      Ubica el BLOQUE 1 a la izquierda (55%) y BLOQUES 2 y 3 a la derecha (45%).
    - Si la tabla es ancha por cantidad de datos/columnas (> 4 columnas):
      Ubica el BLOQUE 2 y 3 debajo a ancho completo.
    - Gráfico Plotly interactivo por debajo a ancho completo.
    - Botón de descarga ejecutiva en PDF corporativo oficial.
    """
    if not content:
        return

    match_b2 = re.search(r'(?i)(?:###\s*)?(?:\*\*)?BLOQUE\s*2', content)
    if match_b2:
        idx_b2 = match_b2.start()
        bloque_izq = content[:idx_b2].strip()
        bloque_der = content[idx_b2:].strip()

        if es_tabla_compacta(bloque_izq):
            col_izq, col_der = st.columns([0.55, 0.45], gap="large")
            with col_izq:
                st.markdown(bloque_izq)
            with col_der:
                st.markdown(bloque_der)
        else:
            st.markdown(content)
    else:
        st.markdown(content)

    if chart:
        dibujar_grafico(chart, key=key_chart)

    # Botón corporativo para exportar y descargar el reporte oficial en PDF
    if "BLOQUE" in content or chart:
        render_boton_descarga_pdf(
            content=content,
            chart=chart,
            usuario=st.session_state.get("user_display", "Usuario"),
            modulos_usados=modulos_usados,
            key=key_pdf or f"btn_pdf_{key_chart or 'live'}"
        )

# Renderizar historial de chat
for idx, msg in enumerate(st.session_state.messages):
    avatar_ico = AVATAR_PATH if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar_ico):
        if msg.get("modulos_usados"):
            badges = "".join([f"<span class='module-badge'>{m}</span>" for m in msg["modulos_usados"]])
            st.markdown(f"<div style='margin-bottom: 6px;'>{badges}</div>", unsafe_allow_html=True)
        if msg["role"] == "assistant":
            render_contenido_asistente(
                msg["content"],
                chart=msg.get("chart"),
                key_chart=f"hist_chart_{idx}",
                modulos_usados=msg.get("modulos_usados"),
                key_pdf=f"hist_pdf_{idx}"
            )
        else:
            st.markdown(msg["content"])

# -------------------------------------------------------------
# 7. CONSULTAS SUGERIDAS MULTIDOMINIO
# -------------------------------------------------------------
consultas_sugeridas = [
    "Necesito el evolutivo de %NPS y %Resolución a nivel canal con gráfico de líneas.",
    "Comparame en gráfico de barras el TMO Total por Proveedor a nivel general.",
    "¿Cuáles fueron las tasas de transferencias 1L, 2L y totales a nivel canal?",
    "Evolutivo de tasas de SPL 7D, 48hs y 30m a nivel canal."
]

def on_click_sugerida(texto_consulta):
    st.session_state["consulta_pendiente"] = texto_consulta

st.markdown("**Búsquedas rápidas sugeridas:**")
cols_sug = st.columns(len(consultas_sugeridas))
for i, ej in enumerate(consultas_sugeridas):
    cols_sug[i].button(
        f"Consulta {i+1}",
        help=ej,
        key=f"btn_consulta_sug_{i+1}",
        use_container_width=True,
        on_click=on_click_sugerida,
        args=(ej,)
    )

# -------------------------------------------------------------
# 8. ENTRADA DE CONSULTA Y ENRUTAMIENTO INTELIGENTE
# -------------------------------------------------------------
chat_val = st.chat_input("Escribe tu consulta operativa (NPS, TMO, Transferencias, SPL o combinadas)...")
user_query = chat_val or st.session_state.pop("consulta_pendiente", None)

if user_query:
    historial_previo_turnos = list(st.session_state.messages)

    st.session_state.messages.append({
        "role": "user",
        "content": user_query,
        "chart": None,
        "modulos_usados": None
    })
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant", avatar=AVATAR_PATH):
        frase_spinner = obtener_frase_spinner()
        respuesta_texto = None
        chart_data = None
        err_gemini = None
        nombres_modulos = []
        client = None

        with st.status(f"🤖 {frase_spinner}", expanded=True) as status_box:
            # 1. Enrutamiento automático con memoria conversacional
            modulos_detectados_ids = gestor_modulos.enrutar_consulta(
                user_query=user_query,
                modulos_disponibles=modulos,
                historial_mensajes=historial_previo_turnos,
                ultimo_modulo=st.session_state.get("ultimo_modulo_activo")
            )
            # Guardar el módulo activo para preguntas de seguimiento
            st.session_state["ultimo_modulo_activo"] = modulos_detectados_ids
            status_box.write("🔍 **Enrutando consulta:** Identificando bases de datos y dimensiones...")

            # Construir texto de contexto previo para preservar filtros de entidades (PCRC/Proveedor)
            contexto_previo_txt = ""
            if historial_previo_turnos:
                ult_user_msgs = [m.get("content", "") for m in historial_previo_turnos if m.get("role") == "user"]
                if ult_user_msgs:
                    contexto_previo_txt = ult_user_msgs[-1]

            # Construir historial conversacional reciente para Gemini (últimos 4 mensajes)
            historial_conversacion_txt = ""
            if historial_previo_turnos:
                ultimos_msgs = [m for m in historial_previo_turnos if m.get("content")][-4:]
                lineas_h = []
                for m in ultimos_msgs:
                    rol = "Usuario" if m.get("role") == "user" else "Asistente"
                    c = (m.get("content") or "").strip()
                    if m.get("role") == "assistant":
                        primeras = [l.strip() for l in c.split("\n") if l.strip() and not l.startswith("| :---")][:4]
                        c_res = " | ".join(primeras)
                        if len(c_res) > 350:
                            c_res = c_res[:350] + "..."
                        lineas_h.append(f"{rol}: {c_res}")
                    else:
                        lineas_h.append(f"{rol}: {c}")
                if lineas_h:
                    historial_conversacion_txt = "\n".join(lineas_h)
            
            # 2. Cargar datos y prompts de los módulos involucrados de forma optimizada
            contextos_tablas = []
            instrucciones_modulos = []

            tablas_por_modulo = {}
            for mid in modulos_detectados_ids:
                mod_info = gestor_modulos.obtener_modulo(mid)
                if mod_info:
                    tablas_dict, meta = gestor_modulos.cargar_tablas_modulo(mid)
                    if tablas_dict is not None:
                        tablas_por_modulo[mid] = tablas_dict
                        txt_tablas = gestor_modulos.generar_contexto_modulo(
                            mod_info,
                            tablas_dict,
                            user_query=user_query,
                            contexto_previo=contexto_previo_txt
                        )
                        cfg = mod_info["config"]
                        nombres_modulos.append(f"{cfg.get('icono', '')} {cfg.get('nombre', mid)}")
                        contextos_tablas.append(f"=== BASE DE DATOS / MÓDULO: {cfg.get('nombre', mid).upper()} ===\n{txt_tablas}")
                        instrucciones_modulos.append(mod_info["prompt"].obtener_system_instruction())

            # Si están involucrados NPS y TMO (o la consulta menciona participación), inyectar cálculo exacto cruzado
            if "nps" in tablas_por_modulo and "tmo" in tablas_por_modulo:
                txt_part = gestor_modulos.calcular_tabla_participacion(
                    tablas_por_modulo["nps"],
                    tablas_por_modulo["tmo"],
                    user_query=user_query,
                    contexto_previo=contexto_previo_txt
                )
                if txt_part:
                    contextos_tablas.append(txt_part)

            if not contextos_tablas:
                err_gemini = "No se pudo cargar la información de las bases seleccionadas."
                status_box.update(label="❌ Error al cargar bases de datos", state="error", expanded=True)
            else:
                status_box.write(f"📊 **Bases conectadas:** {', '.join(nombres_modulos)}")
                status_box.write("🧠 **Consultando Inteligencia Operativa:** Calculando métricas y análisis con Gemini...")

                # 3. Construir prompt orquestador
                system_prompt_maestro = f"""
PROMPT MAESTRO UNIFICADO: INTELIGENCIA OPERATIVA MULTI-MÓDULO
Sos el Agente Único Master de Inteligencia Operativa.
Tienes acceso simultáneo a múltiples bases de datos operativas de la compañía.
En esta consulta, has accedido internamente a los siguientes módulos de datos: {', '.join(nombres_modulos)}.

REGLAS GENERALES:
1. RIGOR MATEMÁTICO: Utiliza únicamente las tablas ya calculadas. Cero alucinación.
2. PRINCIPIO DE RELEVANCIA ABSOLUTA (CERO MÉTRICAS NO SOLICITADAS):
   - En el BLOQUE 1 (Tabla Markdown), incluye ÚNICAMENTE las métricas y columnas específicamente solicitadas por el usuario, más las dimensiones necesarias (Periodo, Proveedor o PCRC).
   - ESTÁ ESTRICTAMENTE PROHIBIDO incluir o calcular columnas o componentes accesorios que el usuario NO pidió.
     * Si piden "TMO por proveedor", la tabla debe contener ÚNICAMENTE: | Periodo | Proveedor | TMO Total |. JAMÁS agregues Tiempo Hablado (TT), Hold, ACW, Saliente, Horas Disponibles, Baño, Refrigerio, Coaching u otras métricas no pedidas.
     * Si piden "%NPS", muestra ÚNICAMENTE: | Periodo | %NPS |. NO agregues Promotores, Detractores, Neutros ni %Resolución a menos que se hayan pedido explícitamente.
     * Si piden "SPL 7D", muestra ÚNICAMENTE: | Periodo | %SPL 7 Días |. NO agregues 30m ni 48hs.
     * Si piden "Transferencias 1L", muestra ÚNICAMENTE: | Periodo | Tasa 1L |. NO agregues 2L ni Totales ni Retención.
     * Si piden "Porcentaje de Participación" (o "% Participación"), muestra ÚNICAMENTE: | Periodo | (Dimensión) | % Participación | (o agrega Q Meda y Q Llamadas solo si solicitan los totales).
3. CONTINUIDAD TEMÁTICA ESTRICTA EN PREGUNTAS DE SEGUIMIENTO:
   - Si la consulta del usuario es un refinamiento, seguimiento o filtro temporal/segmental (ej: "En los periodos Junio, Julio y Agosto, segmentado sus proveedores", "¿Y para Apex?", "¿Cómo fue en julio?", etc.) donde NO menciona explícitamente una nueva métrica, DEBES CONTINUAR ESTRICTAMENTE con la misma métrica y base tratada en los turnos previos de la conversación.
   - NUNCA cambies de métrica arbitrariamente (por ejemplo, si venías respondiendo Transferencias, NO respondas con NPS ni TMO). Mantén la coherencia temática absoluta.
4. FILTRADO TEMPORAL Y SEGMENTAL ESTRICTO:
   - Si el usuario solicita un rango de meses o periodo específico (ej: "de Mayo a Septiembre del 2026", "Junio, Julio y Agosto"), filtra y devuelve ÚNICAMENTE los datos correspondientes a esos meses. No incluyas meses fuera del rango.
   - Si pide un PCRC o Proveedor específico, filtra y devuelve ÚNICAMENTE ese PCRC o Proveedor.
   - Si pide segmentado por proveedores, muestra los proveedores para los periodos solicitados.
   - Si pide un Trimestre específico (ej: "Segundo Trimestre"), incluye ÚNICAMENTE los meses que componen ese trimestre (Abril, Mayo y Junio) agrupados en dicho período.
   - Si pide "anual", "promedio anual" o "todo el año", consolida todos los meses correspondientes al año en un único período.
5. FORMATO ESTRICTO DE TABLA MARKDOWN:
   - CADA FILA DEBE ESTAR OBLIGATORIAMENTE EN UNA LÍNEA NUEVA SEPARADA POR SALTO DE LÍNEA (\\n).
   - NUNCA comprimas múltiples filas en una sola línea ni uses '||'.
   - Incluye SIEMPRE la línea separadora de columnas después del encabezado (| :--- | :--- | :--- |).
   - Escribe todas las filas con sus datos correspondientes de manera estándar y completa (una fila por línea). El post-procesador de la app se encarga de suprimir limpiamente los duplicados consecutivos.
   - En la columna Periodo, utiliza siempre el nombre completo en español (ej: "Mayo 2026", "Junio 2026"), o la denominación temporal consolidada correspondiente (ej: "Año 2026", "Primer Trimestre 2026", "Segundo Trimestre 2026", etc.), nunca números tipo "2026-05".
6. SEMAFORIZACIÓN EJECUTIVA OBLIGATORIA (🟢 MEJOR Y 🔴 PEOR VALOR):
   - En la columna de la métrica consultada (para cada Periodo o grupo analizado en la tabla), agrega obligatoriamente:
     * Un círculo verde (🟢) al lado del MEJOR valor (ej: "412s 🟢" o "78.5% 🟢").
     * Un círculo rojo (🔴) al lado del PEOR valor (ej: "451s 🔴" o "45.8% 🔴").
   - Criterio de negocio según la métrica:
     * TMO y Tiempos: Menor tiempo es MEJOR (🟢 para el menor, 🔴 para el mayor).
     * Transferencias y Desvíos: Menor tasa es MEJOR (🟢 para la menor tasa, 🔴 para la mayor tasa).
     * %NPS y Satisfacción: Mayor porcentaje es MEJOR (🟢 para el mayor %, 🔴 para el menor %).
     * %SPL y Resolución: Mayor porcentaje es MEJOR (🟢 para el mayor %, 🔴 para el menor %).
     * %Participación (Q Meda / Q Llamadas): Mayor porcentaje es MEJOR (🟢 para el mayor %, 🔴 para el menor %).
7. CÁLCULO DE MÉTRICA CRUZADA - "PORCENTAJE DE PARTICIPACIÓN":
   - Cuando el usuario consulte el "Porcentaje de participación" (o "% Participación", "participación de encuestas"):
     * DEFINICIÓN: Es la cantidad de participación de encuestas por cantidad de llamadas atendidas.
     * COMPONENTES:
       - "Q MEDA" (Cantidad de encuestas): Proviene de la columna Encuestas_Total del módulo NPS.
       - "Q Llamadas" (Cantidad de llamadas atendidas): Proviene de la columna Llamadas_Validas del módulo TMO.
     * FÓRMULA MATEMÁTICA EXACTA: (Q MEDA / Q Llamadas) * 100.
     * Se expresa siempre en porcentaje con 1 decimal (ejemplo: "2.6%").
     * Utiliza directamente los datos matemáticos pre-calculados en la tabla cruzada provista.
8. AGREGACIÓN ANUAL (MÉTRICA ANUAL / PROMEDIO ANUAL / DE TODO EL AÑO):
   - Si la consulta solicita una "métrica Anual", "Promedio anual", "de todo el año", "anual 2026" o expresiones equivalentes, indica que se solicita calcular la métrica de todo el año como si fuera un único período consolidado.
   - REGLA DE ORO: ESTÁ TERMINANTEMENTE PROHIBIDO desglosar mes a mes (Enero, Febrero, Marzo, etc.) cuando se solicita una métrica anual. La tabla del BLOQUE 1 debe contener EXCLUSIVAMENTE la fila consolidada "Año 2026" (o 1 fila consolidada por proveedor/PCRC con Periodo "Año 2026"). Cero filas mensuales.
   - Utiliza directamente los datos matemáticos pre-consolidados de las tablas provistas en el contexto.
9. AGREGACIÓN TRIMESTRAL (MÉTRICAS POR TRIMESTRE / Q1, Q2, Q3, Q4):
   - Ante una solicitud de métrica trimestral ("trimestre", "trimestral", "primer trimestre", "segundo trimestre", "tercer trimestre", "cuarto trimestre", "Q1", "Q2", "Q3", "Q4"), se solicita la métrica agrupada como un único período.
   - REGLA DE ORO: ESTÁ TERMINANTEMENTE PROHIBIDO incluir meses individuales cuando se pide métrica trimestral. Muestra EXCLUSIVAMENTE la fila consolidada del trimestre solicitado (ej: "Primer Trimestre 2026"), o una fila por cada trimestre consolidado si solicitaron todos los trimestres.
   - DEFINICIÓN Y COMPOSICIÓN ESTRICTA DE TRIMESTRES:
     * Primer Trimestre (1T / Q1): Enero, Febrero y Marzo.
     * Segundo Trimestre (2T / Q2): Abril, Mayo y Junio.
     * Tercer Trimestre (3T / Q3): Julio, Agosto y Septiembre.
     * Cuarto Trimestre (4T / Q4): Octubre, Noviembre y Diciembre.
10. Si la consulta combina métricas de más de una base (ej: NPS y TMO), intégralas en tu tabla y análisis de forma armónica solo con las métricas pedidas.
11. Estructura rigurosamente la respuesta con los siguientes encabezados exactos en negrita:
   ### **BLOQUE 1: Datos Operativos**
   (Tabla Markdown con ÚNICAMENTE las métricas y periodos solicitados: % con 1 decimal, tiempos enteros con 's', periodo en español o denominación anual/trimestral, y semáforos 🟢 / 🔴 en los valores extremos. Cada fila en una línea nueva separada por \\n).

   ### **BLOQUE 2: Hallazgos Clave**
   (Máximo 3 viñetas ejecutivas ultra-cortas con desvíos y hallazgos clave sobre los datos solicitados: 🟢 mejor y 🔴 peor).

   ### **BLOQUE 3: Trazabilidad**
   (Filtros aplicados, Nivel de agregación, Bases consultadas: {', '.join(nombres_modulos)}).
12. Si el usuario solicita un gráfico, curva, comparativa visual o torta, incluye al final el bloque <chart_json> con su formato estándar, graficando ÚNICAMENTE la métrica o métricas solicitadas.

DIRECTIVAS ESPECÍFICAS DE LAS BASES ACTIVAS:
""" + "\n\n".join(instrucciones_modulos)

                contexto_datos_unificado = "\n\n".join(contextos_tablas)

                client = obtener_cliente_gemini()
                if client is not None:
                    respuesta_texto, chart_data, err_gemini = consultar_gemini(
                        client=client,
                        system_prompt=system_prompt_maestro,
                        contexto_datos=contexto_datos_unificado,
                        user_query=user_query,
                        historial_conversacion=historial_conversacion_txt
                    )

                if respuesta_texto:
                    status_box.update(label="✅ **Análisis completado**", state="complete", expanded=False)
                elif client is None:
                    status_box.update(label="⚠️ **Falta API Key**", state="error", expanded=True)
                else:
                    status_box.update(label="❌ **Error en la consulta**", state="error", expanded=True)

        # FUERA DEL SPINNER: Renderizar resultados limpiamente
        if client is None and not err_gemini:
            st.warning("🔑 **Falta tu clave de Gemini:** Por favor ingresa tu Gemini API Key en la barra lateral izquierda para que el agente pueda responder.")
        elif respuesta_texto:
            # Mostrar insignias de las bases consultadas
            badges = "".join([f"<span class='module-badge'>{m}</span>" for m in nombres_modulos])
            st.markdown(f"<div style='margin-bottom: 6px;'>{badges}</div>", unsafe_allow_html=True)
            render_contenido_asistente(
                respuesta_texto,
                chart=chart_data,
                key_chart=f"live_chart_{len(st.session_state.messages)}",
                modulos_usados=nombres_modulos,
                key_pdf=f"live_pdf_{len(st.session_state.messages)}"
            )

            # Persistir en historial
            st.session_state.messages.append({
                "role": "assistant",
                "content": respuesta_texto,
                "chart": chart_data,
                "modulos_usados": nombres_modulos
            })
            guardar_historial_usuario(user_id, "unificado", st.session_state.messages)
        else:
            st.error(f"Error al procesar la respuesta con Gemini: {err_gemini}")
