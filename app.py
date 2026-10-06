import os
import re
import streamlit as st
from datetime import datetime

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

    # Configuración de Gemini API Key si no está cargada
    from core.database_redis import obtener_secreto
    api_key_actual = obtener_secreto("GEMINI_API_KEY", "") or st.session_state.get("gemini_api_key_manual", "")
    if not api_key_actual:
        st.divider()
        st.warning("⚠️ Falta Gemini API Key")
        key_input = st.text_input("Ingresa tu Gemini API Key:", type="password", key="input_api_key_sidebar", placeholder="AIzaSy...")
        if key_input:
            st.session_state.gemini_api_key_manual = key_input
            # Guardar automáticamente en .streamlit/secrets.toml
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

    # Estado de las 4 bases de datos conectadas
    st.markdown("### 🗂️ Bases de Datos Conectadas")
    for m in modulos:
        mid = m["id"]
        fecha_m = obtener_fecha_base(mid)
        icono = m.get("icono", "📊")
        nombre = m.get("nombre", mid)
        st.markdown(f"**{icono} {nombre}**")
        st.caption(f"🕒 Act: `{fecha_m}`")

    st.caption("⚡ **Powered by Mauro. R**")
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
                if clave_admin == PASSWORD_ADMIN:
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
    st.caption("Arquitectura V2 Multi-Módulo &nbsp;|&nbsp; Enrutamiento inteligente entre NPS, TMO, Transferencias y SPL")

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

def render_contenido_asistente(content, chart=None, key_chart=None):
    """
    Renderiza la respuesta del asistente de forma adaptable:
    - Si la tabla de datos tiene espacio en blanco lateral (<= 4 columnas):
      Ubica el BLOQUE 1 a la izquierda (55%) y BLOQUES 2 y 3 a la derecha (45%).
    - Si la tabla es ancha por cantidad de datos/columnas (> 4 columnas):
      Ubica el BLOQUE 2 y 3 debajo a ancho completo.
    - Gráfico Plotly interactivo por debajo a ancho completo.
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

# Renderizar historial de chat
for idx, msg in enumerate(st.session_state.messages):
    avatar_ico = AVATAR_PATH if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar_ico):
        if msg.get("modulos_usados"):
            badges = "".join([f"<span class='module-badge'>{m}</span>" for m in msg["modulos_usados"]])
            st.markdown(f"<div style='margin-bottom: 6px;'>{badges}</div>", unsafe_allow_html=True)
        if msg["role"] == "assistant":
            render_contenido_asistente(msg["content"], chart=msg.get("chart"), key_chart=f"hist_chart_{idx}")
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

        with st.spinner(frase_spinner):
            # 1. Enrutamiento automático
            modulos_detectados_ids = gestor_modulos.enrutar_consulta(user_query, modulos)
            
            # 2. Cargar datos y prompts de los módulos involucrados
            contextos_tablas = []
            instrucciones_modulos = []

            for mid in modulos_detectados_ids:
                mod_info = gestor_modulos.obtener_modulo(mid)
                if mod_info:
                    tablas_dict, meta = gestor_modulos.cargar_tablas_modulo(mid)
                    if tablas_dict is not None:
                        txt_tablas = mod_info["formulas"].generar_contexto_tablas(tablas_dict)
                        cfg = mod_info["config"]
                        nombres_modulos.append(f"{cfg.get('icono', '')} {cfg.get('nombre', mid)}")
                        contextos_tablas.append(f"=== BASE DE DATOS / MÓDULO: {cfg.get('nombre', mid).upper()} ===\n{txt_tablas}")
                        instrucciones_modulos.append(mod_info["prompt"].obtener_system_instruction())

            if not contextos_tablas:
                err_gemini = "No se pudo cargar la información de las bases seleccionadas."
            else:
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
3. FILTRADO TEMPORAL Y SEGMENTAL ESTRICTO:
   - Si el usuario solicita un rango de meses o periodo específico (ej: "de Mayo a Septiembre del 2026"), filtra y devuelve ÚNICAMENTE los datos correspondientes a esos meses. No incluyas meses fuera del rango.
   - Si pide un PCRC o Proveedor específico, filtra y devuelve ÚNICAMENTE ese PCRC o Proveedor.
4. FORMATO ESTRICTO DE TABLA MARKDOWN:
   - CADA FILA DEBE ESTAR OBLIGATORIAMENTE EN UNA LÍNEA NUEVA SEPARADA POR SALTO DE LÍNEA (\n).
   - NUNCA comprimas múltiples filas en una sola línea ni uses '||'.
   - Incluye SIEMPRE la línea separadora de columnas después del encabezado (| :--- | :--- | :--- |).
   - Escribe todas las filas con sus datos correspondientes de manera estándar y completa (una fila por línea). El post-procesador de la app se encarga de suprimir limpiamente los duplicados consecutivos.
   - En la columna Periodo, utiliza siempre el nombre completo en español (ej: "Mayo 2026", "Junio 2026"), nunca números tipo "2026-05".
5. SEMAFORIZACIÓN EJECUTIVA OBLIGATORIA (🟢 MEJOR Y 🔴 PEOR VALOR):
   - En la columna de la métrica consultada (para cada Periodo o grupo analizado en la tabla), agrega obligatoriamente:
     * Un círculo verde (🟢) al lado del MEJOR valor (ej: "412s 🟢" o "78.5% 🟢").
     * Un círculo rojo (🔴) al lado del PEOR valor (ej: "451s 🔴" o "45.8% 🔴").
   - Criterio de negocio según la métrica:
     * TMO y Tiempos: Menor tiempo es MEJOR (🟢 para el menor, 🔴 para el mayor).
     * Transferencias y Desvíos: Menor tasa es MEJOR (🟢 para la menor tasa, 🔴 para la mayor tasa).
     * %NPS y Satisfacción: Mayor porcentaje es MEJOR (🟢 para el mayor %, 🔴 para el menor %).
     * %SPL y Resolución: Mayor porcentaje es MEJOR (🟢 para el mayor %, 🔴 para el menor %).
6. Si la consulta combina métricas de más de una base (ej: NPS y TMO), intégralas en tu tabla y análisis de forma armónica solo con las métricas pedidas.
7. Estructura rigurosamente la respuesta con los siguientes encabezados exactos en negrita:
   ### **BLOQUE 1: Datos Operativos**
   (Tabla Markdown con ÚNICAMENTE las métricas y periodos solicitados: % con 1 decimal, tiempos enteros con 's', periodo en español, y semáforos 🟢 / 🔴 en los valores extremos. Cada fila en una línea nueva separada por \n).

   ### **BLOQUE 2: Hallazgos Clave**
   (Máximo 3 viñetas ejecutivas ultra-cortas con desvíos y hallazgos clave sobre los datos solicitados: 🟢 mejor y 🔴 peor).

   ### **BLOQUE 3: Trazabilidad**
   (Filtros aplicados, Nivel de agregación, Bases consultadas: {', '.join(nombres_modulos)}).
8. Si el usuario solicita un gráfico, curva, comparativa visual o torta, incluye al final el bloque <chart_json> con su formato estándar, graficando ÚNICAMENTE la métrica o métricas solicitadas.

DIRECTIVAS ESPECÍFICAS DE LAS BASES ACTIVAS:
""" + "\n\n".join(instrucciones_modulos)

                contexto_datos_unificado = "\n\n".join(contextos_tablas)

                client = obtener_cliente_gemini()
                if client is not None:
                    respuesta_texto, chart_data, err_gemini = consultar_gemini(
                        client=client,
                        system_prompt=system_prompt_maestro,
                        contexto_datos=contexto_datos_unificado,
                        user_query=user_query
                    )

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
                key_chart=f"live_chart_{len(st.session_state.messages)}"
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
