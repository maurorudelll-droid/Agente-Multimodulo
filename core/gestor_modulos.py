import os
import json
import pickle
import importlib
import pandas as pd
import streamlit as st
from core.database_redis import guardar_fecha_base, obtener_fecha_base

CARPETA_MODULOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modulos")

def listar_modulos():
    """Descubre y retorna la lista de módulos configurados ordenados."""
    if not os.path.exists(CARPETA_MODULOS):
        os.makedirs(CARPETA_MODULOS, exist_ok=True)
        return []

    modulos = []
    for item in os.listdir(CARPETA_MODULOS):
        path_item = os.path.join(CARPETA_MODULOS, item)
        if os.path.isdir(path_item):
            cfg_path = os.path.join(path_item, "config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    cfg.setdefault("id", item)
                    cfg.setdefault("nombre", item.capitalize())
                    cfg.setdefault("icono", "📊")
                    cfg.setdefault("descripcion", "")
                    cfg.setdefault("orden", 99)
                    cfg["path"] = path_item
                    modulos.append(cfg)
                except Exception:
                    pass

    modulos.sort(key=lambda m: (m.get("orden", 99), m.get("nombre", "")))
    return modulos

def obtener_modulo(modulo_id):
    """Carga la configuración y módulos de Python (fórmulas y prompts) de un módulo."""
    path_mod = os.path.join(CARPETA_MODULOS, modulo_id)
    if not os.path.isdir(path_mod):
        return None

    cfg_path = os.path.join(path_mod, "config.json")
    if not os.path.exists(cfg_path):
        return None

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Import dinámico de fórmulas y prompt
    modulo_formulas = importlib.import_module(f"modulos.{modulo_id}.formulas")
    modulo_prompt = importlib.import_module(f"modulos.{modulo_id}.prompt_negocio")

    return {
        "config": cfg,
        "path": path_mod,
        "formulas": modulo_formulas,
        "prompt": modulo_prompt
    }

def buscar_archivo_dataset(path_mod):
    """Detecta el archivo Excel o CSV principal del módulo."""
    # 1. Nombre estándar
    for nom in ["base_datos.xlsx", "base_datos.xls", "base_datos.csv"]:
        p = os.path.join(path_mod, nom)
        if os.path.exists(p):
            return p

    # 2. Cualquier archivo .xlsx o .csv dentro de la carpeta del módulo
    for f in os.listdir(path_mod):
        if f.endswith(('.xlsx', '.xls', '.csv')) and not f.startswith("~$"):
            return os.path.join(path_mod, f)

    return None

@st.cache_data
def cargar_tablas_modulo(modulo_id):
    """Carga las tablas exactas del módulo. Usa caché serializada ultrarrápida si existe."""
    mod_info = obtener_modulo(modulo_id)
    if not mod_info:
        return None, "Módulo no encontrado."

    pkl_path = os.path.join(mod_info["path"], "tablas_calculadas.pkl")
    if os.path.exists(pkl_path):
        try:
            with open(pkl_path, "rb") as f:
                data = pickle.load(f)
            return data["tablas"], data["meta"]
        except Exception:
            pass

    dataset_path = buscar_archivo_dataset(mod_info["path"])
    if not dataset_path:
        return None, "No se encontró archivo de base de datos (.xlsx o .csv) para este módulo."

    try:
        tablas_dict, meta = mod_info["formulas"].procesar_dataset(dataset_path)
        # Guardar en pickle para cargas subsiguientes ultrarrápidas
        try:
            with open(pkl_path, "wb") as f:
                pickle.dump({"tablas": tablas_dict, "meta": meta}, f)
        except Exception:
            pass
        return tablas_dict, meta
    except Exception as e:
        return None, f"Error al procesar fórmulas: {e}"

def guardar_dataset_modulo(modulo_id, archivo_subido):
    """Guarda un nuevo dataset para el módulo, recalcula la caché y actualiza su fecha en Redis."""
    mod_info = obtener_modulo(modulo_id)
    if not mod_info:
        return False, "Módulo no encontrado."

    ext = ".xlsx" if archivo_subido.name.endswith(('.xlsx', '.xls')) else ".csv"
    destino = os.path.join(mod_info["path"], f"base_datos{ext}")

    try:
        with open(destino, "wb") as f:
            f.write(archivo_subido.getbuffer())

        # Recalcular tablas y regenerar caché pickle
        try:
            tablas_dict, meta = mod_info["formulas"].procesar_dataset(destino)
            pkl_path = os.path.join(mod_info["path"], "tablas_calculadas.pkl")
            with open(pkl_path, "wb") as f:
                pickle.dump({"tablas": tablas_dict, "meta": meta}, f)
        except Exception as e_proc:
            print(f"Advertencia al regenerar pickle: {e_proc}")

        guardar_fecha_base(modulo_id)
        st.cache_data.clear()
        return True, "Archivo guardado y tablas recalculadas exitosamente."
    except Exception as e:
        return False, str(e)

def enrutar_consulta(user_query, modulos_disponibles):
    """
    Detecta de forma inteligente qué módulos son relevantes para la consulta del usuario.
    Permite responder consultas mono-módulo y también consultas multi-módulo cruzadas.
    """
    query_lower = user_query.lower()
    modulos_seleccionados = []

    for mod in modulos_disponibles:
        kws = mod.get("keywords", [])
        if any(kw in query_lower for kw in kws):
            modulos_seleccionados.append(mod["id"])

    # Si no hubo coincidencia específica (ej. saludo, pregunta general del canal), se inyectan todos
    if not modulos_seleccionados:
        modulos_seleccionados = [m["id"] for m in modulos_disponibles]

    return modulos_seleccionados
