import re
import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

MESES_ORDEN = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

def ordenar_cronologico(eje_x, series):
    """Ordena cronológicamente los periodos si contienen nombres de meses en español."""
    def clave_fecha(label):
        lbl = str(label).lower()
        # Buscar año (4 dígitos)
        match_anio = re.search(r'\b(20\d\d)\b', lbl)
        anio = int(match_anio.group(1)) if match_anio else 2026

        # Buscar mes en español
        mes_num = 0
        for mes_nombre, num in MESES_ORDEN.items():
            if mes_nombre in lbl:
                mes_num = num
                break
        return (anio, mes_num, lbl)

    # Verificar si al menos la mitad de los elementos parecen meses
    es_temporal = sum(1 for x in eje_x if any(m in str(x).lower() for m in MESES_ORDEN)) >= len(eje_x) / 2
    if not es_temporal:
        return eje_x, series

    # Ordenar eje_x y reordenar correspondientemente cada serie
    indices_ordenados = sorted(range(len(eje_x)), key=lambda i: clave_fecha(eje_x[i]))
    nuevo_eje_x = [eje_x[i] for i in indices_ordenados]

    nuevas_series = []
    for s in series:
        vals = s.get("valores", [])
        if len(vals) == len(eje_x):
            nuevos_vals = [vals[i] for i in indices_ordenados]
        else:
            nuevos_vals = vals
        nueva_s = dict(s)
        nueva_s["valores"] = nuevos_vals
        nuevas_series.append(nueva_s)

    return nuevo_eje_x, nuevas_series

def dibujar_grafico(chart_data):
    """Renderiza gráficos Plotly estandarizados con valores impresos fijos y leyendas claras."""
    if not chart_data or not isinstance(chart_data, dict):
        return

    try:
        tipo = str(chart_data.get("tipo", "linea")).lower()
        titulo = chart_data.get("titulo", "Visualización Operativa")
        eje_x = chart_data.get("eje_x", chart_data.get("x", []))
        series = chart_data.get("series", [])
        unidad = chart_data.get("unidad", "")

        # Ordenar cronológicamente si es una serie temporal
        if tipo not in ["torta", "pie", "circular", "dona", "donut"] and eje_x and series:
            eje_x, series = ordenar_cronologico(eje_x, series)

        colores = ['#2563eb', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6']

        if HAS_PLOTLY:
            fig = go.Figure()

            # Caso 1: Torta / Donut
            if tipo in ["torta", "pie", "circular", "dona", "donut"]:
                valores_torta = series[0].get("valores", []) if series else []
                fig.add_trace(go.Pie(
                    labels=eje_x,
                    values=valores_torta,
                    hole=0.35,
                    textinfo="label+value+percent",
                    hovertemplate="%{label}: <b>%{value}" + (f"{unidad}" if unidad else "") + "</b> (%{percent})<extra></extra>"
                ))
            # Caso 2: Barras
            elif tipo in ["barra", "barras", "bar"]:
                for i, s in enumerate(series):
                    nombre = s.get("nombre", "Métrica")
                    valores = s.get("valores", [])
                    color = colores[i % len(colores)]
                    fig.add_trace(go.Bar(
                        x=eje_x,
                        y=valores,
                        name=nombre,
                        text=[f"<b>{v}{unidad}</b>" for v in valores],
                        textposition="outside",
                        marker_color=color,
                        hovertemplate="<b>" + str(nombre) + "</b>: %{y}" + (str(unidad) if unidad else "") + "<extra></extra>"
                    ))
                fig.update_layout(barmode="group")
            # Caso 3: Líneas (con valores impresos fijos e indicador de nombre de métrica)
            else:
                for i, s in enumerate(series):
                    nombre = s.get("nombre", "Métrica")
                    valores = s.get("valores", [])
                    color = colores[i % len(colores)]

                    # Trazado de línea con valores impresos fijos sobre cada punto
                    fig.add_trace(go.Scatter(
                        x=eje_x,
                        y=valores,
                        mode="lines+markers+text",
                        name=nombre,
                        line=dict(width=3.5, color=color),
                        marker=dict(size=9, color=color),
                        text=[f"<b>{v}{unidad}</b>" for v in valores],
                        textposition="top center",
                        textfont=dict(size=12, color=color, family="Arial, sans-serif"),
                        hovertemplate="<b>" + str(nombre) + "</b><br>Periodo: %{x}<br>Valor: <b>%{y}" + (str(unidad) if unidad else "") + "</b><extra></extra>"
                    ))

                    # Rótulo al final de la línea para identificar qué métrica es cada curva
                    if eje_x and valores:
                        ultimo_val = valores[-1]
                        fig.add_annotation(
                            x=eje_x[-1],
                            y=ultimo_val,
                            text=f" <b>◀ {nombre}</b>",
                            showarrow=False,
                            xanchor="left",
                            font=dict(size=12, color=color, family="Arial, sans-serif"),
                            bgcolor="rgba(255, 255, 255, 0.85)",
                            bordercolor=color,
                            borderwidth=1,
                            borderpad=3
                        )

            fig.update_layout(
                title=dict(text=f"<b>📈 {titulo}</b>", x=0.02, xanchor="left", font=dict(size=17, color="#0f172a")),
                xaxis_title="<b>Periodo / Segmento</b>",
                yaxis_title=f"<b>Valor ({unidad})</b>" if unidad else "<b>Valor</b>",
                template="plotly_white",
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.22,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=13, color="#1e293b"),
                    bgcolor="rgba(248, 250, 252, 0.9)",
                    bordercolor="#cbd5e1",
                    borderwidth=1
                ),
                margin=dict(l=45, r=130, t=70, b=90)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            df_chart = pd.DataFrame(index=eje_x)
            for s in series:
                df_chart[s.get("nombre", "Serie")] = s.get("valores", [])
            st.markdown(f"**📈 {titulo}**")
            if "barra" in tipo:
                st.bar_chart(df_chart)
            else:
                st.line_chart(df_chart)
    except Exception as e:
        st.warning(f"No se pudo graficar automáticamente: {e}")
