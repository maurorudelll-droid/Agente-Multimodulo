import os
import pandas as pd
import numpy as np

def leer_archivo_robusto(origen):
    """Carga y normaliza encabezados del archivo Excel o CSV de SPL."""
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
        raise ValueError(f"Error al leer el archivo de SPL: {e}")

    mapa_cols = {}
    for c in df.columns:
        c_str = str(c).strip()
        c_u = c_str.upper()
        if c_u in ["MES", "PERIODO"]:
            mapa_cols[c] = "Periodo"
        elif c_u in ["NOMBREPCRC_SK", "NOMBREPCRC", "PCRC", "PRCR"]:
            mapa_cols[c] = "PCRC"
        elif c_u in ["PROVEEDOR", "NOMBREPROVEEDOR"]:
            mapa_cols[c] = "PROVEEDOR"
        elif "SPL" in c_u and "ATEND" in c_u:
            mapa_cols[c] = "Q_SPL_Atendidos"
        elif "SPL30" in c_u:
            mapa_cols[c] = "Q_SPL30_Reiterados"
        elif "SPL48" in c_u:
            mapa_cols[c] = "Q_SPL48_Reiterados"
        elif "SPL7" in c_u:
            mapa_cols[c] = "Q_SPL7_Reiterados"
        else:
            mapa_cols[c] = c_str

    df = df.rename(columns=mapa_cols)
    df = df.loc[:, ~df.columns.duplicated()]
    if 'Periodo' in df.columns:
        df = df[~df['Periodo'].astype(str).str.strip().str.upper().isin(['PERIODO', 'MES'])].reset_index(drop=True)
    return df

COLS_NUM_SPL = [
    'Q_SPL_Atendidos', 'Q_SPL30_Reiterados', 'Q_SPL48_Reiterados', 'Q_SPL7_Reiterados'
]

def computar_kpis_spl(df_grp):
    """Calcula las tasas de SPL (sin reiteración) ponderadas por llamadas atendidas."""
    q_spl = df_grp['Q_SPL_Atendidos'].replace(0, np.nan)

    spl30 = (1.0 - (df_grp['Q_SPL30_Reiterados'] / q_spl)) * 100
    spl48 = (1.0 - (df_grp['Q_SPL48_Reiterados'] / q_spl)) * 100
    spl7 = (1.0 - (df_grp['Q_SPL7_Reiterados'] / q_spl)) * 100

    res_df = pd.DataFrame({
        'Llamadas_Atendidas_SPL': df_grp['Q_SPL_Atendidos'].fillna(0).astype(int),
        'SPL_30min_%': spl30.round(1).astype(str) + '%',
        'SPL_48hs_%': spl48.round(1).astype(str) + '%',
        'SPL_7dias_%': spl7.round(1).astype(str) + '%',
        'Reiteradas_30min': df_grp['Q_SPL30_Reiterados'].fillna(0).astype(int),
        'Reiteradas_48hs': df_grp['Q_SPL48_Reiterados'].fillna(0).astype(int),
        'Reiteradas_7dias': df_grp['Q_SPL7_Reiterados'].fillna(0).astype(int)
    })
    return res_df

def procesar_dataset(filepath):
    """Procesa el dataset de SPL y retorna tablas agregadas."""
    df = leer_archivo_robusto(filepath)

    for col in COLS_NUM_SPL:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    if 'Periodo' in df.columns:
        df['Periodo_DT'] = pd.to_datetime(df['Periodo'], errors='coerce')
        df['Periodo_Str'] = df['Periodo_DT'].dt.strftime('%Y-%m').fillna(df['Periodo'].astype(str))
    else:
        df['Periodo_Str'] = 'Total'

    cols_sum = [c for c in COLS_NUM_SPL if c in df.columns]

    # 1. TABLA CANAL
    canal_vol = df.groupby('Periodo_Str')[cols_sum].sum().reset_index()
    tabla_canal = pd.concat([canal_vol[['Periodo_Str']], computar_kpis_spl(canal_vol)], axis=1)

    # 2. TABLA PCRC
    if 'PCRC' in df.columns:
        pcrc_vol = df.groupby(['Periodo_Str', 'PCRC'])[cols_sum].sum().reset_index()
        tabla_pcrc = pd.concat([pcrc_vol[['Periodo_Str', 'PCRC']], computar_kpis_spl(pcrc_vol)], axis=1)
    else:
        tabla_pcrc = pd.DataFrame()

    # 3. TABLA PROVEEDOR GLOBAL (SIN PCRC)
    if 'PROVEEDOR' in df.columns:
        prov_vol = df.groupby(['Periodo_Str', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_prov = pd.concat([prov_vol[['Periodo_Str', 'PROVEEDOR']], computar_kpis_spl(prov_vol)], axis=1)
    else:
        tabla_prov = pd.DataFrame()

    # 4. TABLA PCRC Y PROVEEDOR
    if 'PCRC' in df.columns and 'PROVEEDOR' in df.columns:
        pcrc_prov_vol = df.groupby(['Periodo_Str', 'PCRC', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_pcrc_prov = pd.concat([pcrc_prov_vol[['Periodo_Str', 'PCRC', 'PROVEEDOR']], computar_kpis_spl(pcrc_prov_vol)], axis=1)
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
    txt = "--- TABLA 1: NIVEL CANAL (Consolidado General de SPL, 1 fila por mes) ---\n"
    txt += tablas_dict["canal"].to_string(index=False)
    
    if not tablas_dict["pcrc"].empty:
        txt += "\n\n--- TABLA 2: NIVEL PCRC (SPL desglosado por PCRC) ---\n"
        txt += tablas_dict["pcrc"].to_string(index=False)

    if not tablas_dict["proveedor"].empty:
        txt += "\n\n--- TABLA 3: NIVEL PROVEEDOR GLOBAL (SPL consolidado por Proveedor, SIN PCRC) ---\n"
        txt += tablas_dict["proveedor"].to_string(index=False)

    if not tablas_dict["pcrc_proveedor"].empty:
        txt += "\n\n--- TABLA 4: NIVEL PCRC Y PROVEEDOR (SPL segmentado por PCRC y Proveedor) ---\n"
        txt += tablas_dict["pcrc_proveedor"].to_string(index=False)

    return txt
