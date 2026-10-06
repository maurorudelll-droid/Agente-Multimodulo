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
        # Eliminar archivos Excel/CSV previos para evitar duplicados o versiones viejas
        for f in os.listdir(mod_info["path"]):
            if f.endswith(('.xlsx', '.xls', '.csv')) and not f.startswith("~$"):
                try:
                    os.remove(os.path.join(mod_info["path"], f))
                except Exception:
                    pass

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

def seleccionar_tablas_relevantes(tablas_dict, user_query=""):
    """
    Filtra inteligentemente las tablas del módulo según la dimensión solicitada en la consulta.
    Evita enviar tablas masivas innecesarias (ej. pcrc_proveedor que puede pesar +70.000 caracteres)
    si el usuario solo pidió nivel proveedor, nivel pcrc o nivel canal consolidado.
    Reduce drásticamente el tamaño del contexto hasta en un 90%, evitando límites de cuota (429) y demoras.
    """
    if not isinstance(tablas_dict, dict):
        return {}

    q = (user_query or "").lower()
    pide_cruzado = ("pcrc" in q and "proveedor" in q) or "cruzad" in q
    pide_prov = "proveedor" in q
    pide_pcrc = "pcrc" in q or "campa" in q or "servicio" in q
    pide_canal = "canal" in q or "general" in q or "total" in q or "consolidado" in q

    seleccionadas = {}
    if pide_cruzado:
        if "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
        if "pcrc_proveedor" in tablas_dict and not getattr(tablas_dict["pcrc_proveedor"], "empty", True):
            seleccionadas["pcrc_proveedor"] = tablas_dict["pcrc_proveedor"]
    elif pide_prov:
        if "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
        if "proveedor" in tablas_dict and not getattr(tablas_dict["proveedor"], "empty", True):
            seleccionadas["proveedor"] = tablas_dict["proveedor"]
    elif pide_pcrc:
        if "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
        if "pcrc" in tablas_dict and not getattr(tablas_dict["pcrc"], "empty", True):
            seleccionadas["pcrc"] = tablas_dict["pcrc"]
    elif pide_canal:
        if "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
    else:
        # Por defecto si no especifica: canal, proveedor y pcrc (se excluye pcrc_proveedor para no saturar memoria)
        for k in ["canal", "proveedor", "pcrc"]:
            if k in tablas_dict and not getattr(tablas_dict[k], "empty", True):
                seleccionadas[k] = tablas_dict[k]

    if not seleccionadas and "canal" in tablas_dict:
        seleccionadas["canal"] = tablas_dict["canal"]

    return seleccionadas

def generar_contexto_modulo(mod_info, tablas_dict, user_query=""):
    """
    Genera el texto formateado en Markdown de las tablas relevantes para la consulta del usuario.
    """
    tablas_sel = seleccionar_tablas_relevantes(tablas_dict, user_query)
    nombres_desc = {
        "canal": "TABLA 1: NIVEL CANAL (Consolidado General, 1 fila por mes)",
        "pcrc": "TABLA 2: NIVEL PCRC (Desglosado por PCRC/Campaña)",
        "proveedor": "TABLA 3: NIVEL PROVEEDOR GLOBAL (Consolidado por Proveedor, SIN PCRC)",
        "pcrc_proveedor": "TABLA 4: NIVEL PCRC Y PROVEEDOR (Segmentado por PCRC y Proveedor)"
    }
    partes = []
    for k, df in tablas_sel.items():
        desc = nombres_desc.get(k, f"TABLA: {k.upper()}")
        partes.append(f"--- {desc} ---\n" + df.to_string(index=False))
    return "\n\n".join(partes)

def calcular_tabla_participacion(tablas_nps, tablas_tmo, user_query=""):
    """
    Calcula de forma matemática exacta el 'Porcentaje de Participación' entre módulos:
    Fórmula: (Q MEDA / Q Llamadas) * 100
    - Q MEDA: Encuestas_Total (módulo NPS)
    - Q Llamadas: Llamadas_Validas (módulo TMO)
    Genera tabla estructurada pre-calculada para alimentar a Gemini con rigor matemático exacto.
    """
    if not isinstance(tablas_nps, dict) or not isinstance(tablas_tmo, dict):
        return ""

    tablas_sel_nps = seleccionar_tablas_relevantes(tablas_nps, user_query)
    tablas_sel_tmo = seleccionar_tablas_relevantes(tablas_tmo, user_query)

    bloques = []
    for dim in ["canal", "proveedor", "pcrc", "pcrc_proveedor"]:
        if dim in tablas_sel_nps and dim in tablas_sel_tmo:
            df_nps = tablas_sel_nps[dim]
            df_tmo = tablas_sel_tmo[dim]
            if "Encuestas_Total" in df_nps.columns and "Llamadas_Validas" in df_tmo.columns:
                cols_merge = ["Periodo_Str"]
                if dim == "proveedor" and "PROVEEDOR" in df_nps.columns and "PROVEEDOR" in df_tmo.columns:
                    cols_merge.append("PROVEEDOR")
                elif dim == "pcrc" and "PCRC" in df_nps.columns and "PCRC" in df_tmo.columns:
                    cols_merge.append("PCRC")
                elif dim == "pcrc_proveedor":
                    if "PCRC" in df_nps.columns and "PCRC" in df_tmo.columns:
                        cols_merge.append("PCRC")
                    if "PROVEEDOR" in df_nps.columns and "PROVEEDOR" in df_tmo.columns:
                        cols_merge.append("PROVEEDOR")

                cols_nps = cols_merge + ["Encuestas_Total"]
                cols_tmo = cols_merge + ["Llamadas_Validas"]

                try:
                    df_m = pd.merge(df_nps[cols_nps], df_tmo[cols_tmo], on=cols_merge, how="inner")
                    mask_val = df_m["Llamadas_Validas"] > 0
                    df_m["Participacion_%"] = "0.0%"
                    df_m.loc[mask_val, "Participacion_%"] = (
                        (df_m.loc[mask_val, "Encuestas_Total"] / df_m.loc[mask_val, "Llamadas_Validas"]) * 100
                    ).round(1).astype(str) + "%"
                    df_m.rename(columns={"Encuestas_Total": "Q_Meda", "Llamadas_Validas": "Q_Llamadas"}, inplace=True)
                    bloques.append(f"--- TABLA CRUZADA EXACTA % PARTICIPACIÓN ({dim.upper()}): Q_Meda / Q_Llamadas ---\n" + df_m.to_string(index=False))
                except Exception:
                    pass

    if bloques:
        return "=== TABLA CRUZADA PRE-CALCULADA MATEMÁTICA EXACTA: PORCENTAJE DE PARTICIPACIÓN (Q MEDA / Q LLAMADAS) ===\n" + "\n\n".join(bloques)
    return ""

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

    # Si la consulta pide 'participación' o cruce de encuestas/llamadas, activar NPS y TMO
    if "participaci" in query_lower or ("encuesta" in query_lower and "llamada" in query_lower):
        if "nps" not in modulos_seleccionados and any(m["id"] == "nps" for m in modulos_disponibles):
            modulos_seleccionados.append("nps")
        if "tmo" not in modulos_seleccionados and any(m["id"] == "tmo" for m in modulos_disponibles):
            modulos_seleccionados.append("tmo")

    # Si no hubo coincidencia específica (ej. saludo, pregunta general del canal), se inyectan todos
    if not modulos_seleccionados:
        modulos_seleccionados = [m["id"] for m in modulos_disponibles]

    return modulos_seleccionados
