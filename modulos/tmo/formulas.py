import os
import pandas as pd
import numpy as np

def leer_archivo_robusto(origen):
    """Carga y normaliza encabezados del archivo Excel o CSV de TMO."""
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
        raise ValueError(f"Error al leer el archivo de TMO: {e}")

    mapa_cols = {}
    for c in df.columns:
        c_str = str(c).strip()
        c_u = c_str.upper()
        if c_u == "PERIODO":
            mapa_cols[c] = "Periodo"
        elif c_u in ["NOMBREPCRC", "PCRC", "PRCR"]:
            mapa_cols[c] = "PCRC"
        elif c_u in ["NOMBREPROVEEDOR", "PROVEEDOR"]:
            mapa_cols[c] = "PROVEEDOR"
        elif "BA" in c_u and "O" in c_u:  # Baño o Bao
            mapa_cols[c] = "Baño"
        else:
            mapa_cols[c] = c_str

    df = df.rename(columns=mapa_cols)
    df = df.loc[:, ~df.columns.duplicated()]
    if 'Periodo' in df.columns:
        df = df[df['Periodo'].astype(str).str.strip().str.upper() != 'PERIODO'].reset_index(drop=True)
    return df

COLS_NUM_TMO = [
    'Q llamadas', 'Tiempo TT', 'Tiempo Staff', 'Tiempo Avail', 'Tiempo ACW in',
    'Tiempo Hold', 'Tiempo Saliente', 'Tiempo Auxiliares', 'Baño', 'Problema Sistema',
    'Refrigerio', 'Agenda', 'Capacitacion', 'Coaching individual', 'Coaching Express',
    'Re entrenamiento', 'Gestiones Out', 'tareas gremiales', 'Otros', 'descanso visual',
    'Reimagina'
]

def computar_kpis_tmo(df_grp):
    """Calcula las métricas ponderadas de TMO, tiempos y auxiliares."""
    q_ll = df_grp['Q llamadas'].replace(0, np.nan)

    # Tiempos en segundos por llamada
    tt_seg = df_grp['Tiempo TT'] / q_ll
    hold_seg = df_grp['Tiempo Hold'] / q_ll
    acw_seg = df_grp['Tiempo ACW in'] / q_ll
    sal_seg = df_grp['Tiempo Saliente'] / q_ll
    tmo_seg = (df_grp['Tiempo TT'] + df_grp['Tiempo Hold'] + df_grp['Tiempo ACW in'] + df_grp['Tiempo Saliente']) / q_ll

    # Horas Disponibles = ((TMO_Total_Segundos) + Tiempo Avail) / 3600
    tmo_total_segundos = df_grp['Tiempo TT'] + df_grp['Tiempo Hold'] + df_grp['Tiempo ACW in'] + df_grp['Tiempo Saliente']
    horas_dispo = (tmo_total_segundos + df_grp['Tiempo Avail']) / 3600.0
    horas_dispo_safe = horas_dispo.replace(0, np.nan)

    # Auxiliares en horas
    bano_hs = df_grp['Baño'] / 3600.0
    refri_hs = df_grp['Refrigerio'] / 3600.0
    coaching_hs = (df_grp['Coaching Express'] + df_grp['Coaching individual'] + df_grp['Agenda'] + df_grp['Reimagina']) / 3600.0

    pct_bano = (bano_hs / horas_dispo_safe) * 100
    pct_refri = (refri_hs / horas_dispo_safe) * 100
    pct_coaching = (coaching_hs / horas_dispo_safe) * 100

    res_df = pd.DataFrame({
        'Llamadas_Validas': df_grp['Q llamadas'].fillna(0).astype(int),
        'TMO_Total': tmo_seg.round(0).fillna(0).astype(int).astype(str) + 's',
        'Tiempo_Hablado_TT': tt_seg.round(0).fillna(0).astype(int).astype(str) + 's',
        'Tiempo_Hold': hold_seg.round(0).fillna(0).astype(int).astype(str) + 's',
        'Tiempo_ACW': acw_seg.round(0).fillna(0).astype(int).astype(str) + 's',
        'Tiempo_Saliente': sal_seg.round(0).fillna(0).astype(int).astype(str) + 's',
        'Horas_Disponibles': horas_dispo.round(1).astype(str) + 'h',
        'Bano_%': pct_bano.round(1).astype(str) + '%',
        'Refrigerio_%': pct_refri.round(1).astype(str) + '%',
        'Coaching_%': pct_coaching.round(1).astype(str) + '%'
    })
    return res_df

def procesar_dataset(filepath):
    """Procesa el dataset de TMO y retorna tablas agregadas."""
    df = leer_archivo_robusto(filepath)

    for col in COLS_NUM_TMO:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    if 'Periodo' in df.columns:
        df['Periodo_DT'] = pd.to_datetime(df['Periodo'], errors='coerce')
        df['Periodo_Str'] = df['Periodo_DT'].dt.strftime('%Y-%m').fillna(df['Periodo'].astype(str))
    elif 'dia' in df.columns:
        df['Periodo_Str'] = df['dia'].astype(str)
    else:
        df['Periodo_Str'] = 'Total'

    cols_sum = [c for c in COLS_NUM_TMO if c in df.columns]

    # 1. TABLA CANAL
    canal_vol = df.groupby('Periodo_Str')[cols_sum].sum().reset_index()
    tabla_canal = pd.concat([canal_vol[['Periodo_Str']], computar_kpis_tmo(canal_vol)], axis=1)

    # 2. TABLA PCRC
    if 'PCRC' in df.columns:
        pcrc_vol = df.groupby(['Periodo_Str', 'PCRC'])[cols_sum].sum().reset_index()
        tabla_pcrc = pd.concat([pcrc_vol[['Periodo_Str', 'PCRC']], computar_kpis_tmo(pcrc_vol)], axis=1)
    else:
        tabla_pcrc = pd.DataFrame()

    # 3. TABLA PROVEEDOR GLOBAL (SIN PCRC)
    if 'PROVEEDOR' in df.columns:
        prov_vol = df.groupby(['Periodo_Str', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_prov = pd.concat([prov_vol[['Periodo_Str', 'PROVEEDOR']], computar_kpis_tmo(prov_vol)], axis=1)
    else:
        tabla_prov = pd.DataFrame()

    # 4. TABLA PCRC Y PROVEEDOR
    if 'PCRC' in df.columns and 'PROVEEDOR' in df.columns:
        pcrc_prov_vol = df.groupby(['Periodo_Str', 'PCRC', 'PROVEEDOR'])[cols_sum].sum().reset_index()
        tabla_pcrc_prov = pd.concat([pcrc_prov_vol[['Periodo_Str', 'PCRC', 'PROVEEDOR']], computar_kpis_tmo(pcrc_prov_vol)], axis=1)
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
    txt = "--- TABLA 1: NIVEL CANAL (Consolidado General de TMO, 1 fila por mes) ---\n"
    txt += tablas_dict["canal"].to_string(index=False)
    
    if not tablas_dict["pcrc"].empty:
        txt += "\n\n--- TABLA 2: NIVEL PCRC (TMO desglosado por PCRC) ---\n"
        txt += tablas_dict["pcrc"].to_string(index=False)

    if not tablas_dict["proveedor"].empty:
        txt += "\n\n--- TABLA 3: NIVEL PROVEEDOR GLOBAL (TMO consolidado por Proveedor, SIN PCRC) ---\n"
        txt += tablas_dict["proveedor"].to_string(index=False)

    if not tablas_dict["pcrc_proveedor"].empty:
        txt += "\n\n--- TABLA 4: NIVEL PCRC Y PROVEEDOR (TMO segmentado por PCRC y Proveedor) ---\n"
        txt += tablas_dict["pcrc_proveedor"].to_string(index=False)

    return txt
