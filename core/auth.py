import os
import re
import time
import hashlib
import hmac
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

# Contraseñas maestras cargadas exclusivamente de secretos o entorno
PASSWORD_ACCESO = obtener_secreto("APP_PASSWORD", "")
PASSWORD_ADMIN = obtener_secreto("ADMIN_PASSWORD", "")

SALT_PIN = "agy_salt_seguridad_2026_auth"

def hashear_pin(pin_texto: str) -> str:
    """Genera un hash SHA-256 seguro con sal criptográfica para el PIN numérico."""
    if not pin_texto:
        return ""
    return hashlib.sha256(f"{SALT_PIN}:{pin_texto}".encode("utf-8")).hexdigest()

def verificar_pin(pin_ingresado: str, pin_almacenado: str) -> bool:
    """
    Verifica el PIN ingresado contra el almacenado.
    Soporta comparación en tiempo constante y migración transparente de texto plano.
    """
    if not pin_ingresado or not pin_almacenado:
        return False
    hash_ingresado = hashear_pin(pin_ingresado)
    if hmac.compare_digest(hash_ingresado, pin_almacenado):
        return True
    if pin_almacenado == pin_ingresado:
        return True
    return False

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
                    if not PASSWORD_ACCESO:
                        st.error("⚠️ Configuración incompleta: Por favor define 'APP_PASSWORD' en .streamlit/secrets.toml")
                    elif pwd == PASSWORD_ACCESO:
                        st.session_state.general_authenticated = True
                        st.rerun()
                    else:
                        st.error("Contraseña general incorrecta.")
                return False

            # PASO 2: Usuario y PIN con solapas (Iniciar Sesión / Crear Nuevo Usuario)
            else:
                st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>👤 Tu Identificación</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: #64748b;'>Paso 2 de 2: Accede a tus consultas privadas</p>", unsafe_allow_html=True)
                st.write("")
                
                tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "✨ Crear Nuevo Usuario"])

                with tab_login:
                    with st.form("form_login_existente"):
                        usuario_input = st.text_input("Usuario o Legajo:", key="login_user_input", placeholder="Ej: mauro.r o tu legajo").strip()
                        pin_input = st.text_input("PIN personal (4 dígitos):", type="password", max_chars=4, key="login_pin_input", placeholder="****").strip()
                        st.write("")
                        boton_entrar = st.form_submit_button("Ingresar al Agente 🚀", type="primary", use_container_width=True)

                    if boton_entrar:
                        if not usuario_input:
                            st.warning("Ingresa tu usuario o legajo.")
                        elif not pin_input or len(pin_input) != 4 or not pin_input.isdigit():
                            st.warning("El PIN debe tener exactamente 4 números.")
                        else:
                            user_id = re.sub(r'[^a-zA-Z0-9_]', '', usuario_input.lower().replace(" ", "_"))
                            usuarios_db = cargar_usuarios()

                            if user_id not in usuarios_db:
                                st.error("Usuario no encontrado. Por favor regístrate en la solapa 'Crear Nuevo Usuario'.")
                            elif not verificar_pin(pin_input, usuarios_db[user_id].get("pin", "")):
                                st.error("PIN incorrecto.")
                            else:
                                # Migración automática y transparente de PIN antiguo a hash seguro
                                pin_guardado = str(usuarios_db[user_id].get("pin", ""))
                                if pin_guardado == pin_input:
                                    usuarios_db[user_id]["pin"] = hashear_pin(pin_input)
                                    guardar_usuarios(usuarios_db)

                                st.session_state.authenticated = True
                                st.session_state.current_user = user_id
                                st.session_state.user_display = usuarios_db[user_id].get("nombre", usuario_input)
                                registrar_latido_presencia(user_id, st.session_state.user_display)
                                st.rerun()

                with tab_reg:
                    with st.form("form_registro_nuevo"):
                        r_user = st.text_input("Usuario o Legajo nuevo:", key="reg_user_input", placeholder="Ej: mauro.r o tu legajo").strip()
                        r_nombre = st.text_input("Tu Nombre (como te llamará el agente):", key="reg_nombre_input", placeholder="Ej: Mauro").strip()
                        r_pin = st.text_input("Crea un PIN numérico (4 dígitos):", type="password", max_chars=4, key="reg_pin_input", placeholder="****").strip()
                        st.write("")
                        boton_crear = st.form_submit_button("Crear Usuario y Entrar ✨", type="primary", use_container_width=True)

                    if boton_crear:
                        if not r_user or not r_nombre or not r_pin:
                            st.warning("Completa todos los campos para registrarte.")
                        elif not r_pin.isdigit() or len(r_pin) != 4:
                            st.warning("El PIN debe tener exactamente 4 números.")
                        else:
                            r_id = re.sub(r'[^a-zA-Z0-9_]', '', r_user.lower().replace(" ", "_"))
                            usuarios_db = cargar_usuarios()

                            if r_id in usuarios_db:
                                st.error("Este usuario o legajo ya está registrado. Ingresa en la solapa 'Iniciar Sesión'.")
                            else:
                                usuarios_db[r_id] = {
                                    "nombre": r_nombre,
                                    "pin": hashear_pin(r_pin),
                                    "fecha_registro": datetime.now(TZ_ARG).strftime("%d/%m/%Y %H:%M")
                                }
                                guardar_usuarios(usuarios_db)
                                st.session_state.authenticated = True
                                st.session_state.current_user = r_id
                                st.session_state.user_display = r_nombre
                                registrar_latido_presencia(r_id, r_nombre)
                                st.success(f"¡Usuario {r_nombre} creado con éxito!")
                                st.rerun()

                st.write("")
                if st.button("⬅️ Volver", use_container_width=True):
                    st.session_state.general_authenticated = False
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
