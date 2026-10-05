import os
import re
import time
import streamlit as st
from datetime import datetime
from core.database_redis import (
    TZ_ARG,
    CARPETA_DATOS,
    cargar_usuarios,
    guardar_usuarios,
    redis_del,
    get_presencia_global,
    registrar_latido_presencia,
    remover_presencia,
    obtener_secreto
)

PASSWORD_ACCESO = obtener_secreto("APP_PASSWORD", "atencion2026")
PASSWORD_ADMIN = obtener_secreto("ADMIN_PASSWORD", "pirania9")

def init_auth_session():
    """Inicializa variables de sesión de autenticación."""
    if "general_authenticated" not in st.session_state:
        st.session_state.general_authenticated = False
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.user_display = ""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

def render_login(avatar_path="bot_avatar.png"):
    """Renderiza el flujo de autenticación en 2 pasos."""
    init_auth_session()

    if st.session_state.authenticated:
        registrar_latido_presencia(st.session_state.current_user, st.session_state.user_display)
        return True

    col_izq, col_centro, col_der = st.columns([1.2, 1.8, 1.2])

    with col_centro:
        with st.container(border=True):
            if os.path.exists(avatar_path):
                ci1, ci2, ci3 = st.columns([1, 1.2, 1])
                with ci2:
                    st.image(avatar_path, width=110)

            # PASO 1: Contraseña General
            if not st.session_state.general_authenticated:
                st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>🔒 Acceso a la Plataforma</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: #64748b;'>Paso 1 de 2: Ingresa la contraseña general</p>", unsafe_allow_html=True)
                st.write("")
                
                pwd = st.text_input("Contraseña General:", type="password", key="general_pwd", placeholder="Ingresa la contraseña aquí...")
                st.write("")
                if st.button("Continuar ➡️", type="primary", use_container_width=True):
                    if pwd == PASSWORD_ACCESO:
                        st.session_state.general_authenticated = True
                        st.rerun()
                    else:
                        st.error("Contraseña general incorrecta.")
                return False

            # PASO 2: Usuario y PIN
            else:
                st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>👤 Tu Identificación</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: #64748b;'>Paso 2 de 2: Accede a tus consultas privadas</p>", unsafe_allow_html=True)
                st.write("")
                
                with st.form("form_login_usuario"):
                    usuario_input = st.text_input("Nombre de Usuario o Legajo:", key="login_user_input", placeholder="Ej: mauro.r o tu legajo").strip()
                    pin_input = st.text_input("PIN personal (4 dígitos):", type="password", max_chars=4, key="login_pin_input", placeholder="****").strip()
                    st.write("")
                    boton_entrar = st.form_submit_button("Ingresar al Agente 🚀", type="primary", use_container_width=True)

                if st.button("⬅️ Volver", use_container_width=True):
                    st.session_state.general_authenticated = False
                    st.rerun()

                if boton_entrar:
                    if not usuario_input:
                        st.error("Ingresa tu nombre o legajo.")
                        return False
                    if not pin_input or len(pin_input) < 4 or not pin_input.isdigit():
                        st.error("El PIN debe tener exactamente 4 números.")
                        return False

                    user_id = re.sub(r'[^a-zA-Z0-9_]', '', usuario_input.lower().replace(" ", "_"))
                    usuarios_db = cargar_usuarios()

                    if user_id in usuarios_db:
                        if usuarios_db[user_id]["pin"] == pin_input:
                            st.session_state.authenticated = True
                            st.session_state.current_user = user_id
                            st.session_state.user_display = usuarios_db[user_id].get("nombre", usuario_input)
                            registrar_latido_presencia(user_id, st.session_state.user_display)
                            st.rerun()
                        else:
                            st.error("El usuario ya existe, pero el PIN es incorrecto.")
                            return False
                    else:
                        usuarios_db[user_id] = {
                            "nombre": usuario_input,
                            "pin": pin_input,
                            "fecha_registro": datetime.now(TZ_ARG).strftime("%d/%m/%Y %H:%M")
                        }
                        guardar_usuarios(usuarios_db)
                        st.session_state.authenticated = True
                        st.session_state.current_user = user_id
                        st.session_state.user_display = usuario_input
                        registrar_latido_presencia(user_id, st.session_state.user_display)
                        st.rerun()

                return False

def cerrar_sesion():
    """Cierra la sesión del usuario actual."""
    if st.session_state.get("current_user"):
        remover_presencia(st.session_state.current_user)
    st.session_state.authenticated = False
    st.session_state.general_authenticated = False
    st.session_state.admin_authenticated = False
    st.session_state.current_user = None
    st.session_state.user_display = ""
    st.rerun()

def render_admin_users_manager():
    """Renderiza la sección de administración de usuarios dentro del panel admin."""
    st.write("---")
    st.markdown("**👥 Usuarios registrados:**")
    db_users = cargar_usuarios()
    if db_users:
        for uid, info in db_users.items():
            st.caption(f"• **{info.get('nombre', uid)}** (Creado: {info.get('fecha_registro', 'N/D')})")
        
        st.markdown("##### 🗑️ Eliminar Usuario")
        uids_disponibles = list(db_users.keys())
        user_a_eliminar = st.selectbox(
            "Seleccionar usuario:",
            options=uids_disponibles,
            format_func=lambda u: f"{db_users[u].get('nombre', u)} ({u})"
        )
        
        if st.button("Eliminar usuario e historiales", type="secondary", use_container_width=True):
            nombre_del = db_users[user_a_eliminar].get("nombre", user_a_eliminar)
            del db_users[user_a_eliminar]
            guardar_usuarios(db_users)

            # Borrar archivos de historial asociados
            for f in os.listdir(CARPETA_DATOS):
                if f.startswith(f"historial_{user_a_eliminar}"):
                    try:
                        os.remove(os.path.join(CARPETA_DATOS, f))
                    except Exception:
                        pass

            redis_del(f"historial_{user_a_eliminar}")
            st.success(f"Usuario '{nombre_del}' y sus historiales fueron eliminados.")
            st.rerun()
    else:
        st.caption("No hay usuarios registrados aún.")

def render_presence_indicator():
    """Renderiza el widget verde de usuarios activos en la barra lateral."""
    presencia = get_presencia_global()
    ahora_timestamp = time.time()
    activos = {uid: info for uid, info in presencia.items() if ahora_timestamp - info.get("last_seen", 0) < 300}
    cant_activos = len(activos)

    texto_activos = f"🟢 {cant_activos} {'Usuario activo' if cant_activos == 1 else 'Usuarios activos'}"
    st.markdown(f"""
    <div style="background-color: #dcfce7; border: 2px solid #22c55e; color: #15803d; padding: 7px 10px; border-radius: 8px; font-weight: 700; text-align: center; font-size: 13px; margin: 4px 0 6px 0; box-shadow: 0 2px 4px rgba(34, 197, 94, 0.15);">
        {texto_activos}
    </div>
    """, unsafe_allow_html=True)
