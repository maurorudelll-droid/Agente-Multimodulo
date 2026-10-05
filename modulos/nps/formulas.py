import os
import pandas as pd
import numpy as np

def leer_archivo_robusto(origen):
    """Carga y normaliza encabezados del archivo Excel o CSV de NPS."""
    try:
        if isinstance(origen, str):
            if origen.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(origen)
            else:
                df = pd.read_csv(origen)
        else:
            if origen.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(origen)
            else:
                df = pd.read_csv(origen)
    except Exception as e:
        raise ValueError(f"Error al leer el archivo de NPS: {e}")

    # Limpieza de encabezados
    mapa_cols = {}
    for c in df.columns:
        c_str = str(c).strip()
        c_u = c_str.upper()
        if c_u == "PERIODO":
            mapa_cols[c] = "Periodo"
        elif c_u in ["PCRC", "PRCR"]:
            mapa_cols[c] = "PCRC"
        elif c_u in ["PROVEEDOR", "NOMBREPROVEEDOR"]:
            mapa_cols[c] = "PROVEEDOR"
        else:
            mapa_cols[c] = c_str

    df = df.rename(columns=mapa_cols)
    df = df.loc[:, ~df.columns.duplicated()]
    if 'Periodo' in df.columns:
        df = df[df['Periodo'].astype(str).str.strip().str.upper() != 'PERIODO'].reset_index(drop=True)
    return df

COLS_NUM_NPS = [
    'Q meda', 'Promotores', 'detractor', 'Neutro', 'Res si', 'Q Res',
    'Q sat', 'sat top2', 'sat botton', 'Q 0y1'
]

def computar_kpis_nps(df_grp):
    """Calcula las métricas ponderadas de NPS y Resolución."""
    q_meda = df_grp['Q meda'].replace(0, np.nan)
    nps = ((df_grp['Promotores'] - df_grp['detractor']) / q_meda) * 100
    promotor = (df_grp['Promotores'] / q_meda) * 100
    detractor = (df_grp['detractor'] / q_meda) * 100
    neutro = (df_grp['Neutro'] / q_meda) * 100

    q_res = df_grp['Q Res'].replace(0, np.nan)
    resolucion = (df_grp['Res si'] / q_res) * 100

    res_df = pd.DataFrame({
        'Encuestas_Total': df_grp['Q meda'].fillna(0).astype(int),
        'NPS': nps.round(1).astype(str) + '%',
        'Promotor_%': promotor.round(1).astype(str) + '%',
        'Detractor_%': detractor.round(1).astype(str) + '%',
        'Neutro_%': neutro.round(1).astype(str) + '%',
        'Resolucion_%': resolucion.round(1).astype(str) + '%',
        'Q_Promotores': df_grp['Promotores'].fillna(0).astype(int),
        'Q_Detractores': df_grp['detractor'].fillna(0).astype(int),
        'Q_Neutros': df_grp['Neutro'].fillna(0).astype(int),
        'Q_Resueltas': df_grp['Res si'].fillna(0).astype(int),
    })
    return res_df

def procesar_dataset(filepath):
    """Procesa el dataset de NPS y retorna las 4 tablas agregadas con metadatos."""
    df = leer_archivo_robusto(filepath)

    for col in COLS_NUM_NPS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    if 'Periodo' in df.columns:
        df['Periodo_DT'] = pd.to_datetime(df['Periodo'], errors='coerce')
        df['Periodo_Str'] = df['Periodo_DT'].dt.strftime('%Y-%m').fillna(df['Periodo'].astype(str))
    elif 'mes' in df.columns:
        df['Periodo_Str'] = df['mes'].astype(str)
    else:
        df['Periodo_Str'] = 'Total'

    cols_sum = [c for c in COLS_NUM_NPS if c in df.columns]

    # 1. TABLA CANAL: Consolidado general (1 fila por periodo)
    canal_vol = df.groupby('Periodo_Str')[cols_sum].sum().reset_index()
    tabla_canal = pd.concat([canal_vol[['Periodo_Str']], computar_kpis_nps(canal_vol)], axis=1)

    # 2. TABLA PCRC: Agrupado por Periodo y PCRC
    if 'PCRC' in df.columns:
        pcrc_vol = df.groupby(['Periodo_Str', 'PCRC'])[cols_sum].sum().reset_index()
        tabla_pcrc = pd.concat([pcrc_vol[['Periodo_Str', 'PCRC']], computar_kpis_nps(pcrc_vol)], axis=1)
    else:
        tabla_pcrc = pd.DataFrame()

    # 3. TABLA PROVEEDOR GLOBAL (Puro): Agrupado por Periodo y Proveedor (SIN PCRC)
    if 'PROVEEDOR' in df.columns:
        prov_vol = df.groupby(['Periodo_Str', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_prov = pd.concat([prov_vol[['Periodo_Str', 'PROVEEDOR']], computar_kpis_nps(prov_vol)], axis=1)
    else:
        tabla_prov = pd.DataFrame()

    # 4. TABLA PCRC Y PROVEEDOR: Agrupado por Periodo, PCRC y Proveedor
    if 'PCRC' in df.columns and 'PROVEEDOR' in df.columns:
        pcrc_prov_vol = df.groupby(['Periodo_Str', 'PCRC', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_pcrc_prov = pd.concat([pcrc_prov_vol[['Periodo_Str', 'PCRC', 'PROVEEDOR']], computar_kpis_nps(pcrc_prov_vol)], axis=1)
    else:
        tabla_pcrc_prov = pd.DataFrame()

    meta = {
        "total_registros": len(df),
        "pcrcs": sorted([str(x) for x in df['PCRC'].dropna().unique().tolist()]) if 'PCRC' in df.columns else [],
        "proveedores": sorted([str(x) for x in df['PROVEEDOR'].dropna().unique().tolist()]) if 'PROVEEDOR' in df.columns else []
    }

    tablas_dict = {
        "canal": tabla_canal,
        "pcrc": tabla_pcrc,
        "proveedor": tabla_prov,
        "pcrc_proveedor": tabla_pcrc_prov
    }

    return tablas_dict, meta

def generar_contexto_tablas(tablas_dict):
    """Convierte las tablas a formato Markdown estructurado para Gemini."""
    txt = "--- TABLA 1: NIVEL CANAL (Consolidado General de NPS, 1 fila por mes) ---\n"
    txt += tablas_dict["canal"].to_string(index=False)
    
    if not tablas_dict["pcrc"].empty:
        txt += "\n\n--- TABLA 2: NIVEL PCRC (NPS desglosado por PCRC/Campaña) ---\n"
        txt += tablas_dict["pcrc"].to_string(index=False)

    if not tablas_dict["proveedor"].empty:
        txt += "\n\n--- TABLA 3: NIVEL PROVEEDOR GLOBAL (NPS consolidado por Proveedor, SIN PCRC) ---\n"
        txt += tablas_dict["proveedor"].to_string(index=False)

    if not tablas_dict["pcrc_proveedor"].empty:
        txt += "\n\n--- TABLA 4: NIVEL PCRC Y PROVEEDOR (NPS segmentado por PCRC y Proveedor) ---\n"
        txt += tablas_dict["pcrc_proveedor"].to_string(index=False)

    return txt
