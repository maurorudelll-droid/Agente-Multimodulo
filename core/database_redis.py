import os
import json
import time
import urllib.request
import streamlit as st
from datetime import datetime, timezone, timedelta

# Zona horaria fija de Argentina (UTC-3)
TZ_ARG = timezone(timedelta(hours=-3))

CARPETA_DATOS = "usuarios_data"
os.makedirs(CARPETA_DATOS, exist_ok=True)
PATH_USUARIOS = os.path.join(CARPETA_DATOS, "usuarios.json")

def obtener_secreto(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)

# Configuración Upstash Redis REST
UPSTASH_URL = obtener_secreto("UPSTASH_REDIS_REST_URL", "https://apparent-gopher-197179.upstash.io")
UPSTASH_TOKEN = obtener_secreto("UPSTASH_REDIS_REST_TOKEN", "gQAAAAAAAwI7AAIgcDFiZTVjN2FhMjU5OGE0NWM2YmYzOGE0MDg4ODNmMDZiMg")

def upstash_execute(*command):
    """Ejecuta un comando en Upstash Redis vía REST API con urllib nativo."""
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        payload = json.dumps(list(command), ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            UPSTASH_URL,
            data=payload,
            headers={
                'Authorization': f'Bearer {UPSTASH_TOKEN}',
                'Content-Type': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('result')
    except Exception:
        return None

def redis_get(key):
    res = upstash_execute("GET", key)
    if res is not None:
        try:
            return json.loads(res)
        except Exception:
            return res
    return None

def redis_set(key, value):
    val_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return upstash_execute("SET", key, val_str)

def redis_del(key):
    return upstash_execute("DEL", key)

@st.cache_resource
def get_presencia_global():
    """Memoria en tiempo real compartida entre todos los usuarios activos."""
    return {}

def registrar_latido_presencia(user_id, display_name):
    """Registra la presencia activa del usuario."""
    if user_id:
        presencia = get_presencia_global()
        presencia[user_id] = {
            "nombre": display_name,
            "last_seen": time.time()
        }

def remover_presencia(user_id):
    """Remueve al usuario de la presencia activa al cerrar sesión."""
    presencia = get_presencia_global()
    if user_id in presencia:
        del presencia[user_id]

def cargar_usuarios():
    """Carga los usuarios registrados desde la nube con fallback local."""
    usuarios_cloud = redis_get("app_usuarios")
    if usuarios_cloud and isinstance(usuarios_cloud, dict):
        try:
            with open(PATH_USUARIOS, "w", encoding="utf-8") as f:
                json.dump(usuarios_cloud, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return usuarios_cloud

    if os.path.exists(PATH_USUARIOS):
        try:
            with open(PATH_USUARIOS, "r", encoding="utf-8") as f:
                db_local = json.load(f)
                if db_local:
                    redis_set("app_usuarios", db_local)
                return db_local
        except Exception:
            return {}
    return {}

def guardar_usuarios(db):
    """Persiste los usuarios en Redis y respaldo local."""
    redis_set("app_usuarios", db)
    try:
        with open(PATH_USUARIOS, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def cargar_historial_usuario(user_id, modulo_id="general"):
    """Carga el historial privado del usuario específico por módulo."""
    key = f"historial_{user_id}_{modulo_id}"
    h_cloud = redis_get(key)
    path_hist = os.path.join(CARPETA_DATOS, f"{key}.json")
    
    if h_cloud and isinstance(h_cloud, list):
        try:
            with open(path_hist, "w", encoding="utf-8") as f:
                json.dump(h_cloud, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return h_cloud

    if os.path.exists(path_hist):
        try:
            with open(path_hist, "r", encoding="utf-8") as f:
                h_local = json.load(f)
                if h_local:
                    redis_set(key, h_local)
                return h_local
        except Exception:
            pass

    return None

def guardar_historial_usuario(user_id, modulo_id, messages):
    """Guarda el historial en la nube y localmente."""
    key = f"historial_{user_id}_{modulo_id}"
    redis_set(key, messages)
    path_hist = os.path.join(CARPETA_DATOS, f"{key}.json")
    try:
        with open(path_hist, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def obtener_fecha_base(modulo_id):
    """Obtiene la fecha de actualización independiente para cada módulo."""
    key = f"app_fecha_base_{modulo_id}"
    fecha_cloud = redis_get(key)
    if fecha_cloud and isinstance(fecha_cloud, str):
        return fecha_cloud

    path_fecha = os.path.join(CARPETA_DATOS, f"fecha_{modulo_id}.txt")
    if os.path.exists(path_fecha):
        try:
            with open(path_fecha, "r", encoding="utf-8") as f:
                f_txt = f.read().strip()
                if f_txt:
                    redis_set(key, f_txt)
                    return f_txt
        except Exception:
            pass
            
    ahora_arg = datetime.now(TZ_ARG).strftime('%d/%m/%Y %H:%M')
    guardar_fecha_base(modulo_id, ahora_arg)
    return ahora_arg

def guardar_fecha_base(modulo_id, fecha_str=None):
    """Persiste la fecha de actualización de la base de un módulo."""
    if not fecha_str:
        fecha_str = datetime.now(TZ_ARG).strftime('%d/%m/%Y %H:%M')
    key = f"app_fecha_base_{modulo_id}"
    redis_set(key, fecha_str)
    path_fecha = os.path.join(CARPETA_DATOS, f"fecha_{modulo_id}.txt")
    try:
        with open(path_fecha, "w", encoding="utf-8") as f:
            f.write(fecha_str)
    except Exception:
        pass
