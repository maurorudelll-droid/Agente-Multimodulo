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

def seleccionar_tablas_relevantes(tablas_dict, user_query="", contexto_previo=""):
    """
    Selecciona de forma inteligente únicamente las tablas necesarias según la dimensión solicitada:
    si el usuario solo pidió nivel proveedor, nivel pcrc o nivel canal consolidado.
    Reduce drásticamente el tamaño del contexto hasta en un 90%, evitando límites de cuota (429) y demoras.
    """
    if not isinstance(tablas_dict, dict):
        return {}

    q = (user_query or "").lower()
    q_ctx = ((contexto_previo or "") + " " + q).lower()

    pide_cruzado = ("pcrc" in q and "proveedor" in q) or "cruzad" in q or ("pcrc" in q_ctx and "proveedor" in q)
    pide_prov = "proveedor" in q
    pide_pcrc = "pcrc" in q or "campa" in q or "servicio" in q
    pide_canal = "canal" in q or "general" in q or "total" in q or "consolidado" in q

    seleccionadas = {}
    if pide_cruzado:
        # Si piden específicamente PCRC y proveedor cruzados, enviar pcrc_proveedor y proveedor
        if "pcrc_proveedor" in tablas_dict and not getattr(tablas_dict["pcrc_proveedor"], "empty", True):
            seleccionadas["pcrc_proveedor"] = tablas_dict["pcrc_proveedor"]
        if "proveedor" in tablas_dict and not getattr(tablas_dict["proveedor"], "empty", True):
            seleccionadas["proveedor"] = tablas_dict["proveedor"]
        if not seleccionadas and "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
    elif pide_prov:
        if "proveedor" in tablas_dict and not getattr(tablas_dict["proveedor"], "empty", True):
            seleccionadas["proveedor"] = tablas_dict["proveedor"]
        if "pcrc" in q_ctx and "pcrc_proveedor" in tablas_dict and not getattr(tablas_dict["pcrc_proveedor"], "empty", True):
            seleccionadas["pcrc_proveedor"] = tablas_dict["pcrc_proveedor"]
        elif not seleccionadas and "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
    elif pide_pcrc:
        if "pcrc" in tablas_dict and not getattr(tablas_dict["pcrc"], "empty", True):
            seleccionadas["pcrc"] = tablas_dict["pcrc"]
        elif "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
    elif pide_canal:
        if "canal" in tablas_dict and not getattr(tablas_dict["canal"], "empty", True):
            seleccionadas["canal"] = tablas_dict["canal"]
    else:
        # Por defecto si no especifica: canal, proveedor y pcrc
        for k in ["canal", "proveedor", "pcrc"]:
            if k in tablas_dict and not getattr(tablas_dict[k], "empty", True):
                seleccionadas[k] = tablas_dict[k]

    if not seleccionadas and "canal" in tablas_dict:
        seleccionadas["canal"] = tablas_dict["canal"]

    return seleccionadas

def filtrar_filas_por_entidades(df, user_query="", contexto_previo=""):
    """Filtra filas por PCRC o PROVEEDOR si se especifica uno concreto."""
    if df is None or getattr(df, 'empty', True):
        return df

    import re
    df_res = df.copy()
    q = (user_query or "").lower()
    q_ctx = ((contexto_previo or "") + " " + q).lower()

    # 1. Filtrar filas por PCRC si se menciona uno específico
    if "PCRC" in df_res.columns:
        pide_todos_pcrc = any(frase in q for frase in ["todos los pcrc", "cada pcrc", "nivel pcrc", "por pcrc", "general", "canal"])
        if not pide_todos_pcrc:
            pcrcs = [str(p) for p in df_res["PCRC"].dropna().unique() if str(p).strip()]
            pcrc_encontrado = None
            for p in pcrcs:
                palabras = [w for w in re.split(r'\W+', p.lower()) if len(w) > 2]
                if palabras and all(w in q for w in palabras):
                    pcrc_encontrado = p
                    break
            if not pcrc_encontrado and contexto_previo:
                for p in pcrcs:
                    palabras = [w for w in re.split(r'\W+', p.lower()) if len(w) > 2]
                    if palabras and all(w in q_ctx for w in palabras):
                        pcrc_encontrado = p
                        break
            if pcrc_encontrado:
                df_res = df_res[df_res["PCRC"].astype(str).str.lower() == pcrc_encontrado.lower()]

    # 2. Filtrar filas por PROVEEDOR si se menciona uno específico (pero no si pide todos)
    if "PROVEEDOR" in df_res.columns:
        pide_todos_prov = any(frase in q for frase in ["sus proveedores", "por proveedor", "los proveedores", "cada proveedor", "segmentado proveedor", "segmentado sus proveedores"])
        if not pide_todos_prov:
            provs = [str(pr) for pr in df_res["PROVEEDOR"].dropna().unique() if str(pr).strip()]
            prov_encontrado = None
            for pr in provs:
                palabras = [w for w in re.split(r'\W+', pr.lower()) if len(w) > 2]
                if palabras and all(w in q for w in palabras):
                    prov_encontrado = pr
                    break
            if not prov_encontrado and contexto_previo:
                for pr in provs:
                    palabras = [w for w in re.split(r'\W+', pr.lower()) if len(w) > 2]
                    if palabras and all(w in q_ctx for w in palabras):
                        prov_encontrado = pr
                        break
            if prov_encontrado:
                df_res = df_res[df_res["PROVEEDOR"].astype(str).str.lower() == prov_encontrado.lower()]

    return df_res

def filtrar_columnas_por_metricas(df, user_query="", contexto_previo=""):
    """Estrecha las columnas según las métricas solicitadas en la consulta."""
    if df is None or getattr(df, 'empty', True):
        return df

    df_res = df.copy()
    q = (user_query or "").lower()
    q_ctx = ((contexto_previo or "") + " " + q).lower()

    cols_base = [c for c in df_res.columns if c in ["Periodo_Str", "Periodo", "PCRC", "PROVEEDOR"]]
    cols_seleccionadas = list(cols_base)

    q_metricas = q if any(m in q for m in ["nps", "spl", "tmo", "transf", "1l", "2l", "resol", "sat", "llamadas", "encuestas"]) else q_ctx

    for c in df_res.columns:
        if c in cols_base:
            continue
        c_low = c.lower()
        if ("nps" in c_low and "nps" in q_metricas) or \
           ("spl" in c_low and "spl" in q_metricas) or \
           ("tmo" in c_low and "tmo" in q_metricas) or \
           ("resol" in c_low and ("resol" in q_metricas or "fcr" in q_metricas)) or \
           ("sat" in c_low and ("sat" in q_metricas or "csat" in q_metricas)) or \
           ("transf" in c_low and ("transf" in q_metricas or "1l" in q_metricas or "2l" in q_metricas)) or \
           ("llamadas" in c_low and ("llamadas" in q_metricas or "volumen" in q_metricas)) or \
           ("encuestas" in c_low and ("encuestas" in q_metricas or "q meda" in q_metricas or "participac" in q_metricas)):
            cols_seleccionadas.append(c)

    if len(cols_seleccionadas) > len(cols_base):
        df_res = df_res[cols_seleccionadas]

    return df_res

def filtrar_df_por_entidades_y_metricas(df, user_query="", contexto_previo=""):
    """Filtra filas y columnas de un DataFrame según las entidades y métricas específicas."""
    df_filas = filtrar_filas_por_entidades(df, user_query, contexto_previo)
    return filtrar_columnas_por_metricas(df_filas, user_query, contexto_previo)

def consolidar_bloque_df(sub_df, etiqueta, dim_cols):
    """Consolida un grupo de filas calculando matemáticamente las métricas ponderadas."""
    if sub_df is None or sub_df.empty:
        return pd.DataFrame()

    filas = []
    if dim_cols:
        grupos = sub_df.groupby(dim_cols, as_index=False)
        for _, sub in grupos:
            r = {'Periodo_Str': etiqueta}
            for d in dim_cols:
                r[d] = sub[d].iloc[0]

            vol_col = None
            for vc in ['Encuestas_Total', 'Llamadas_Validas', 'Llamadas_Atendidas_SPL']:
                if vc in sub.columns:
                    vol_col = vc
                    break

            for c in sub.columns:
                if c in ['Periodo_Str', 'Periodo', 'Periodo_DT'] + dim_cols:
                    continue
                if c in ['Encuestas_Total', 'Llamadas_Validas', 'Llamadas_Atendidas_SPL', 'Q_Promotores', 'Q_Detractores', 'Q_Neutros', 'Q_Resueltas', 'Q_Transferidas', 'Reiteradas_30min', 'Reiteradas_48hs', 'Reiteradas_7dias']:
                    r[c] = int(sub[c].sum())
                elif c == 'NPS' and 'Q_Promotores' in sub.columns and 'Encuestas_Total' in sub.columns:
                    tot_e = sub['Encuestas_Total'].sum()
                    val = round(((sub['Q_Promotores'].sum() - sub['Q_Detractores'].sum()) / tot_e) * 100, 1) if tot_e > 0 else 0.0
                    r[c] = f'{val}%'
                elif c in ['TMO_Total'] or c.startswith('Tiempo_'):
                    nums = sub[c].astype(str).str.replace('s', '', regex=False).str.replace('%', '', regex=False).astype(float)
                    if vol_col and sub[vol_col].sum() > 0:
                        val = int(round((nums * sub[vol_col]).sum() / sub[vol_col].sum()))
                    else:
                        val = int(round(nums.mean()))
                    r[c] = f'{val}s'
                elif c.endswith('%'):
                    nums = sub[c].astype(str).str.replace('%', '', regex=False).str.replace('s', '', regex=False).astype(float)
                    if vol_col and sub[vol_col].sum() > 0:
                        val = round((nums * sub[vol_col]).sum() / sub[vol_col].sum(), 1)
                    else:
                        val = round(nums.mean(), 1)
                    r[c] = f'{val}%'
                elif c == 'Horas_Disponibles':
                    nums = sub[c].astype(str).str.replace('h', '', regex=False).astype(float)
                    r[c] = f'{round(nums.sum(), 1)}h'
                else:
                    r[c] = sub[c].iloc[0]
            filas.append(r)
    else:
        sub = sub_df
        r = {'Periodo_Str': etiqueta}
        vol_col = None
        for vc in ['Encuestas_Total', 'Llamadas_Validas', 'Llamadas_Atendidas_SPL']:
            if vc in sub.columns:
                vol_col = vc
                break
        for c in sub.columns:
            if c in ['Periodo_Str', 'Periodo', 'Periodo_DT']:
                continue
            if c in ['Encuestas_Total', 'Llamadas_Validas', 'Llamadas_Atendidas_SPL', 'Q_Promotores', 'Q_Detractores', 'Q_Neutros', 'Q_Resueltas', 'Q_Transferidas', 'Reiteradas_30min', 'Reiteradas_48hs', 'Reiteradas_7dias']:
                r[c] = int(sub[c].sum())
            elif c == 'NPS' and 'Q_Promotores' in sub.columns and 'Encuestas_Total' in sub.columns:
                tot_e = sub['Encuestas_Total'].sum()
                val = round(((sub['Q_Promotores'].sum() - sub['Q_Detractores'].sum()) / tot_e) * 100, 1) if tot_e > 0 else 0.0
                r[c] = f'{val}%'
            elif c in ['TMO_Total'] or c.startswith('Tiempo_'):
                nums = sub[c].astype(str).str.replace('s', '', regex=False).str.replace('%', '', regex=False).astype(float)
                if vol_col and sub[vol_col].sum() > 0:
                    val = int(round((nums * sub[vol_col]).sum() / sub[vol_col].sum()))
                else:
                    val = int(round(nums.mean()))
                r[c] = f'{val}s'
            elif c.endswith('%'):
                nums = sub[c].astype(str).str.replace('%', '', regex=False).str.replace('s', '', regex=False).astype(float)
                if vol_col and sub[vol_col].sum() > 0:
                    val = round((nums * sub[vol_col]).sum() / sub[vol_col].sum(), 1)
                else:
                    val = round(nums.mean(), 1)
                r[c] = f'{val}%'
            elif c == 'Horas_Disponibles':
                nums = sub[c].astype(str).str.replace('h', '', regex=False).astype(float)
                r[c] = f'{round(nums.sum(), 1)}h'
            else:
                r[c] = sub[c].iloc[0]
        filas.append(r)
    return pd.DataFrame(filas)

def agregar_df_temporalmente(df, user_query="", contexto_previo=""):
    """
    Consolida filas temporalmente cuando el usuario solicita una agregación Anual o Trimestral.
    Si se solicita 'anual' / 'todo el año', agrupa todos los meses en una fila 'Año 2026'.
    Si se solicita un trimestre específico (Q1, Q2, Q3, Q4), agrupa los 3 meses correspondientes.
    Si se solicita 'trimestral', genera una fila consolidada por cada trimestre.
    """
    if df is None or getattr(df, 'empty', True) or "Periodo_Str" not in df.columns:
        return df

    import re
    q_u = (user_query or "").lower()
    q_ctx = (contexto_previo or "").lower()
    q_check = q_u if any(w in q_u for w in ["anual", "año", "ano", "trimestr", "q1", "q2", "q3", "q4", "promedio anual"]) else f"{q_ctx} {q_u}"

    # Si se piden meses específicos sin mencionar anual ni trimestral, no agregar
    meses_nombres = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    if any(m in q_u for m in meses_nombres) and not any(w in q_u for w in ["anual", "año", "ano", "trimestr", "q1", "q2", "q3", "q4", "promedio anual"]):
        return df

    pide_q1 = any(w in q_check for w in ["primer trimestre", "1er trimestre", "1° trimestre", "trimestre 1", "q1", "1t"])
    pide_q2 = any(w in q_check for w in ["segundo trimestre", "2do trimestre", "2° trimestre", "trimestre 2", "q2", "2t"])
    pide_q3 = any(w in q_check for w in ["tercer trimestre", "3er trimestre", "3° trimestre", "trimestre 3", "q3", "3t"])
    pide_q4 = any(w in q_check for w in ["cuarto trimestre", "4to trimestre", "4° trimestre", "trimestre 4", "q4", "4t"])
    pide_trimestral_all = any(w in q_check for w in ["trimestral", "trimestres", "por trimestre", "cada trimestre", "todos los trimestres", "evolutivo trimestral"]) and not (pide_q1 or pide_q2 or pide_q3 or pide_q4)
    pide_anual = any(w in q_check for w in ["anual", "todo el año", "de todo el ano", "todo el ano", "de todo el año", "del año", "del ano", "promedio anual", "acumulado anual"])

    if not (pide_anual or pide_q1 or pide_q2 or pide_q3 or pide_q4 or pide_trimestral_all):
        return df

    if 'PCRC' in df.columns and 'PROVEEDOR' in df.columns:
        dim_cols = ['PCRC', 'PROVEEDOR']
    elif 'PROVEEDOR' in df.columns:
        dim_cols = ['PROVEEDOR']
    elif 'PCRC' in df.columns:
        dim_cols = ['PCRC']
    else:
        dim_cols = []

    match_ano = re.search(r'(20\d\d)', " ".join(df['Periodo_Str'].astype(str).unique()))
    ano_str = match_ano.group(1) if match_ano else "2026"

    trimestres_map = [
        ("Primer Trimestre " + ano_str, ["-01", "-02", "-03", "enero", "febrero", "marzo"]),
        ("Segundo Trimestre " + ano_str, ["-04", "-05", "-06", "abril", "mayo", "junio"]),
        ("Tercer Trimestre " + ano_str, ["-07", "-08", "-09", "julio", "agosto", "septiembre"]),
        ("Cuarto Trimestre " + ano_str, ["-10", "-11", "-12", "octubre", "noviembre", "diciembre"]),
    ]

    dfs_res = []

    if pide_anual:
        df_ano = consolidar_bloque_df(df, f"Año {ano_str}", dim_cols)
        if not df_ano.empty:
            dfs_res.append(df_ano)
    elif pide_q1:
        mask = df['Periodo_Str'].astype(str).str.lower().apply(lambda s: any(pat in s for pat in trimestres_map[0][1]))
        sub = df[mask]
        df_q = consolidar_bloque_df(sub if not sub.empty else df, trimestres_map[0][0], dim_cols)
        if not df_q.empty:
            dfs_res.append(df_q)
    elif pide_q2:
        mask = df['Periodo_Str'].astype(str).str.lower().apply(lambda s: any(pat in s for pat in trimestres_map[1][1]))
        sub = df[mask]
        df_q = consolidar_bloque_df(sub if not sub.empty else df, trimestres_map[1][0], dim_cols)
        if not df_q.empty:
            dfs_res.append(df_q)
    elif pide_q3:
        mask = df['Periodo_Str'].astype(str).str.lower().apply(lambda s: any(pat in s for pat in trimestres_map[2][1]))
        sub = df[mask]
        df_q = consolidar_bloque_df(sub if not sub.empty else df, trimestres_map[2][0], dim_cols)
        if not df_q.empty:
            dfs_res.append(df_q)
    elif pide_q4:
        mask = df['Periodo_Str'].astype(str).str.lower().apply(lambda s: any(pat in s for pat in trimestres_map[3][1]))
        sub = df[mask]
        df_q = consolidar_bloque_df(sub if not sub.empty else df, trimestres_map[3][0], dim_cols)
        if not df_q.empty:
            dfs_res.append(df_q)
    elif pide_trimestral_all:
        for etiq, pats in trimestres_map:
            mask = df['Periodo_Str'].astype(str).str.lower().apply(lambda s: any(pat in s for pat in pats))
            sub = df[mask]
            if not sub.empty:
                df_q = consolidar_bloque_df(sub, etiq, dim_cols)
                if not df_q.empty:
                    dfs_res.append(df_q)

    if dfs_res:
        df_final = pd.concat(dfs_res, ignore_index=True)
        cols_orden = [c for c in df.columns if c in df_final.columns]
        for c in df_final.columns:
            if c not in cols_orden:
                cols_orden.append(c)
        return df_final[cols_orden]

    return df

def generar_contexto_modulo(mod_info, tablas_dict, user_query="", contexto_previo=""):
    """
    Genera el texto formateado en Markdown de las tablas relevantes y filtradas para la consulta.
    """
    tablas_sel = seleccionar_tablas_relevantes(tablas_dict, user_query, contexto_previo)
    nombres_desc = {
        "canal": "TABLA 1: NIVEL CANAL (Consolidado General, 1 fila por mes)",
        "pcrc": "TABLA 2: NIVEL PCRC (Desglosado por PCRC/Campaña)",
        "proveedor": "TABLA 3: NIVEL PROVEEDOR GLOBAL (Consolidado por Proveedor, SIN PCRC)",
        "pcrc_proveedor": "TABLA 4: NIVEL PCRC Y PROVEEDOR (Segmentado por PCRC y Proveedor)"
    }
    partes = []
    for k, df in tablas_sel.items():
        desc = nombres_desc.get(k, f"TABLA: {k.upper()}")
        df_filtrado = filtrar_filas_por_entidades(df, user_query, contexto_previo)
        df_filtrado = agregar_df_temporalmente(df_filtrado, user_query, contexto_previo)
        df_filtrado = filtrar_columnas_por_metricas(df_filtrado, user_query, contexto_previo)
        partes.append(f"--- {desc} ---\n" + df_filtrado.to_string(index=False))
    return "\n\n".join(partes)

def calcular_tabla_participacion(tablas_nps, tablas_tmo, user_query="", contexto_previo=""):
    """
    Calcula de forma matemática exacta el 'Porcentaje de Participación' entre módulos:
    Fórmula: (Q MEDA / Q Llamadas) * 100
    - Q MEDA: Encuestas_Total (módulo NPS)
    - Q Llamadas: Llamadas_Validas (módulo TMO)
    Genera tabla estructurada pre-calculada para alimentar a Gemini con rigor matemático exacto.
    """
    if not isinstance(tablas_nps, dict) or not isinstance(tablas_tmo, dict):
        return ""

    tablas_sel_nps = seleccionar_tablas_relevantes(tablas_nps, user_query, contexto_previo)
    tablas_sel_tmo = seleccionar_tablas_relevantes(tablas_tmo, user_query, contexto_previo)

    # Aplicar agregación temporal a las tablas antes del cruce
    tablas_sel_nps = {k: agregar_df_temporalmente(filtrar_df_por_entidades_y_metricas(v, user_query, contexto_previo), user_query, contexto_previo) for k, v in tablas_sel_nps.items()}
    tablas_sel_tmo = {k: agregar_df_temporalmente(filtrar_df_por_entidades_y_metricas(v, user_query, contexto_previo), user_query, contexto_previo) for k, v in tablas_sel_tmo.items()}

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

def normalizar_texto_sin_acentos(texto):
    # Elimina diacriticos y acentos para comparaciones robustas
    import unicodedata
    if not texto:
        return ""
    texto = str(texto).lower()
    return "".join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def detectar_modulos_en_texto(texto, modulos_disponibles):
    # Detecta modulos con coincidencia de palabras clave sin distincion de acentos
    if not texto:
        return []
    texto_norm = normalizar_texto_sin_acentos(texto)
    mods_detectados = []

    for mod in modulos_disponibles:
        kws = mod.get("keywords", [])
        for kw in kws:
            kw_norm = normalizar_texto_sin_acentos(kw)
            if kw_norm in texto_norm:
                if mod["id"] not in mods_detectados:
                    mods_detectados.append(mod["id"])
                break

    # Caso especial cruzado: si se menciona participación o encuestas + llamadas
    if "participaci" in texto_norm or ("encuesta" in texto_norm and "llamada" in texto_norm):
        if "nps" not in mods_detectados and any(m["id"] == "nps" for m in modulos_disponibles):
            mods_detectados.append("nps")
        if "tmo" not in mods_detectados and any(m["id"] == "tmo" for m in modulos_disponibles):
            mods_detectados.append("tmo")

    return mods_detectados

def enrutar_consulta(user_query, modulos_disponibles, historial_mensajes=None, ultimo_modulo=None):
    # Detecta de forma inteligente que modulos son relevantes para la consulta del usuario.
    # Incorpora MEMORIA CONVERSACIONAL: si la consulta es de seguimiento y no contiene keywords,
    # hereda estrictamente el contexto del ultimo modulo activo o de turnos previos.
    todos_ids = [m["id"] for m in modulos_disponibles]

    # 1. Coincidencia en la consulta directa del usuario
    modulos_seleccionados = detectar_modulos_en_texto(user_query, modulos_disponibles)
    if modulos_seleccionados:
        return modulos_seleccionados

    # 2. Si no hay coincidencia directa en la consulta actual:
    # Caso pregunta de seguimiento / refinamiento ("¿Y en junio?", "segmentado sus proveedores", etc.)
    # Primero: verificar último módulo activo explícito en sesión
    if ultimo_modulo:
        if isinstance(ultimo_modulo, str):
            ultimo_modulo = [ultimo_modulo]
        val_ult = [mid for mid in ultimo_modulo if mid in todos_ids]
        if val_ult and len(val_ult) < len(todos_ids):
            return val_ult

    # Segundo: buscar en el historial de mensajes de la conversación (del más reciente al más antiguo)
    if historial_mensajes:
        for msg in reversed(historial_mensajes):
            # A) Si el mensaje es del usuario, buscar si mencionó algún módulo
            if msg.get("role") == "user":
                c_user = msg.get("content", "")
                mods_prev = detectar_modulos_en_texto(c_user, modulos_disponibles)
                if mods_prev and len(mods_prev) < len(todos_ids):
                    return mods_prev
            # B) Si el mensaje es del asistente, ver qué módulos usó
            elif msg.get("role") == "assistant" and msg.get("modulos_usados"):
                mods_asistente = []
                for nom_u in msg["modulos_usados"]:
                    nom_u_norm = normalizar_texto_sin_acentos(nom_u)
                    for mod in modulos_disponibles:
                        mid = mod["id"]
                        mnom = normalizar_texto_sin_acentos(mod.get("nombre", ""))
                        if mid in nom_u_norm or mnom in nom_u_norm:
                            if mid not in mods_asistente:
                                mods_asistente.append(mid)
                if mods_asistente and len(mods_asistente) < len(todos_ids):
                    return mods_asistente

    # 3. Si no hubo coincidencia en query ni en historial (ej: saludo, pregunta general del canal):
    return todos_ids
