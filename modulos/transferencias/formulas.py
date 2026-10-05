import os
import pandas as pd
import numpy as np

def leer_archivo_robusto(origen):
    """Carga y normaliza encabezados del archivo Excel o CSV de Transferencias."""
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
        raise ValueError(f"Error al leer el archivo de Transferencias: {e}")

    mapa_cols = {}
    for c in df.columns:
        c_str = str(c).strip()
        c_u = c_str.upper()
        if c_u == "PERIODO":
            mapa_cols[c] = "Periodo"
        elif c_u in ["PCRC ORIGEN", "PCRC", "PRCR"]:
            mapa_cols[c] = "PCRC"
        elif c_u in ["PROVEEDOR ORIGEN", "PROVEEDOR REAL", "PROVEEDOR"]:
            mapa_cols[c] = "PROVEEDOR"
        elif c_u in ["REP_1L", "REP 1L"]:
            mapa_cols[c] = "REP_1L"
        elif c_u in ["REP_2L", "REP 2L"]:
            mapa_cols[c] = "REP_2L"
        else:
            mapa_cols[c] = c_str

    df = df.rename(columns=mapa_cols)
    df = df.loc[:, ~df.columns.duplicated()]
    if 'Periodo' in df.columns:
        df = df[df['Periodo'].astype(str).str.strip().str.upper() != 'PERIODO'].reset_index(drop=True)
    return df

COLS_NUM_TRANSF = [
    'Q llamadas', 'Q transferidas', 'REP_1L', 'REP_2L', 'RetencionTransf',
    'ComplejasTransf', 'TecnicaTransfResto', 'TecnicaTransfPrio'
]

def computar_kpis_transf(df_grp):
    """Calcula las tasas de transferencias ponderadas por llamadas."""
    q_ll = df_grp['Q llamadas'].replace(0, np.nan)

    transf_1l = (df_grp['REP_1L'] / q_ll) * 100
    transf_2l = (df_grp['REP_2L'] / q_ll) * 100
    transf_1l_2l = ((df_grp['REP_1L'] + df_grp['REP_2L']) / q_ll) * 100
    transf_tot = (df_grp['Q transferidas'] / q_ll) * 100
    transf_ret = (df_grp['RetencionTransf'] / q_ll) * 100
    transf_comp = (df_grp['ComplejasTransf'] / q_ll) * 100
    transf_tec_resto = (df_grp['TecnicaTransfResto'] / q_ll) * 100
    transf_tec_prio = (df_grp['TecnicaTransfPrio'] / q_ll) * 100

    res_df = pd.DataFrame({
        'Llamadas_Validas': df_grp['Q llamadas'].fillna(0).astype(int),
        'Transf_Totales_%': transf_tot.round(1).astype(str) + '%',
        'Rep_1L_%': transf_1l.round(1).astype(str) + '%',
        'Rep_2L_%': transf_2l.round(1).astype(str) + '%',
        '1L_mas_2L_%': transf_1l_2l.round(1).astype(str) + '%',
        'Retencion_%': transf_ret.round(1).astype(str) + '%',
        'Complejas_%': transf_comp.round(1).astype(str) + '%',
        'Tecnica_Normal_%': transf_tec_resto.round(1).astype(str) + '%',
        'Tecnica_Priority_%': transf_tec_prio.round(1).astype(str) + '%',
        'Q_Transferidas': df_grp['Q transferidas'].fillna(0).astype(int)
    })
    return res_df

def procesar_dataset(filepath):
    """Procesa el dataset de Transferencias y retorna tablas agregadas."""
    df = leer_archivo_robusto(filepath)

    for col in COLS_NUM_TRANSF:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    if 'Periodo' in df.columns:
        df['Periodo_DT'] = pd.to_datetime(df['Periodo'], errors='coerce')
        df['Periodo_Str'] = df['Periodo_DT'].dt.strftime('%Y-%m').fillna(df['Periodo'].astype(str))
    else:
        df['Periodo_Str'] = 'Total'

    cols_sum = [c for c in COLS_NUM_TRANSF if c in df.columns]

    # 1. TABLA CANAL
    canal_vol = df.groupby('Periodo_Str')[cols_sum].sum().reset_index()
    tabla_canal = pd.concat([canal_vol[['Periodo_Str']], computar_kpis_transf(canal_vol)], axis=1)

    # 2. TABLA PCRC
    if 'PCRC' in df.columns:
        pcrc_vol = df.groupby(['Periodo_Str', 'PCRC'])[cols_sum].sum().reset_index()
        tabla_pcrc = pd.concat([pcrc_vol[['Periodo_Str', 'PCRC']], computar_kpis_transf(pcrc_vol)], axis=1)
    else:
        tabla_pcrc = pd.DataFrame()

    # 3. TABLA PROVEEDOR GLOBAL (SIN PCRC)
    if 'PROVEEDOR' in df.columns:
        prov_vol = df.groupby(['Periodo_Str', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_prov = pd.concat([prov_vol[['Periodo_Str', 'PROVEEDOR']], computar_kpis_transf(prov_vol)], axis=1)
    else:
        tabla_prov = pd.DataFrame()

    # 4. TABLA PCRC Y PROVEEDOR
    if 'PCRC' in df.columns and 'PROVEEDOR' in df.columns:
        pcrc_prov_vol = df.groupby(['Periodo_Str', 'PCRC', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_pcrc_prov = pd.concat([pcrc_prov_vol[['Periodo_Str', 'PCRC', 'PROVEEDOR']], computar_kpis_transf(pcrc_prov_vol)], axis=1)
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
    txt = "--- TABLA 1: NIVEL CANAL (Consolidado General de Transferencias, 1 fila por mes) ---\n"
    txt += tablas_dict["canal"].to_string(index=False)
    
    if not tablas_dict["pcrc"].empty:
        txt += "\n\n--- TABLA 2: NIVEL PCRC (Transferencias desglosadas por PCRC) ---\n"
        txt += tablas_dict["pcrc"].to_string(index=False)

    if not tablas_dict["proveedor"].empty:
        txt += "\n\n--- TABLA 3: NIVEL PROVEEDOR GLOBAL (Transferencias consolidadas por Proveedor, SIN PCRC) ---\n"
        txt += tablas_dict["proveedor"].to_string(index=False)

    if not tablas_dict["pcrc_proveedor"].empty:
        txt += "\n\n--- TABLA 4: NIVEL PCRC Y PROVEEDOR (Transferencias segmentadas por PCRC y Proveedor) ---\n"
        txt += tablas_dict["pcrc_proveedor"].to_string(index=False)

    return txt
