import re
import uuid
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

def generar_figura_plotly(chart_data, incluir_updatemenus=True):
    """
    Construye y retorna un objeto go.Figure estandarizado a partir de chart_data.
    Reutilizable tanto para renderizado en pantalla como para exportación estática a PDF/PNG.
    """
    if not chart_data or not isinstance(chart_data, dict) or not HAS_PLOTLY:
        return None

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
        # Caso 3: Líneas (con separación inteligente y enfoque dinámico)
        else:
            es_multilinea = len(series) > 2

            # Recolectar valores para análisis de rango
            todos_los_valores = []
            for s in series:
                for v in s.get("valores", []):
                    if isinstance(v, (int, float)):
                        todos_los_valores.append(float(v))

            valores_activos = [v for v in todos_los_valores if v > 0]
            if not valores_activos:
                valores_activos = todos_los_valores

            min_activo = min(valores_activos) if valores_activos else 0.0
            max_val = max(todos_los_valores) if todos_los_valores else 100.0

            delta = max_val - min_activo
            pad = max(delta * 0.15, 2.0)
            rango_enfocado = [max(0.0, min_activo - pad), max_val + pad]
            rango_completo = [0.0, max_val + pad]

            conviene_enfocar = (min_activo >= 20.0 and delta < 45.0) or (len(series) >= 3 and delta < 40.0)

            for i, s in enumerate(series):
                nombre = s.get("nombre", "Métrica")
                valores = s.get("valores", [])
                color = colores[i % len(colores)]

                modo = "lines+markers" if es_multilinea else "lines+markers+text"
                text_labels = [f"<b>{v}{unidad}</b>" for v in valores]

                fig.add_trace(go.Scatter(
                    x=eje_x,
                    y=valores,
                    mode=modo,
                    name=nombre,
                    line=dict(width=3, color=color),
                    marker=dict(size=7, color=color),
                    text=text_labels,
                    textposition="top center",
                    textfont=dict(size=11, color=color, family="Arial, sans-serif"),
                    hovertemplate="<b>" + str(nombre) + "</b>: %{y}" + (str(unidad) if unidad else "") + "<extra></extra>"
                ))

                if not es_multilinea and eje_x and valores:
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

        updatemenus = []
        if incluir_updatemenus and tipo not in ["torta", "pie", "circular", "dona", "donut"]:
            botones = []
            if tipo in ["barra", "barras", "bar"]:
                botones.append(dict(label="🏷️ Ver Valores", method="restyle", args=[{"textposition": "outside"}]))
                botones.append(dict(label="👁️ Ocultar Valores", method="restyle", args=[{"textposition": "none"}]))
            else:
                botones.append(dict(label="🏷️ Ver Valores", method="restyle", args=[{"mode": "lines+markers+text"}]))
                botones.append(dict(label="👁️ Ocultar Valores", method="restyle", args=[{"mode": "lines+markers"}]))

            if es_multilinea or conviene_enfocar:
                botones.append(dict(label="🔍 Separar Líneas", method="relayout", args=[{"yaxis.autorange": False, "yaxis.range": rango_enfocado}]))
                botones.append(dict(label="📏 Escala desde 0", method="relayout", args=[{"yaxis.autorange": False, "yaxis.range": rango_completo}]))

            updatemenus = [
                dict(
                    type="buttons",
                    direction="left",
                    x=1.0,
                    y=1.16,
                    xanchor="right",
                    yanchor="top",
                    pad=dict(r=0, t=0, b=0),
                    showactive=True,
                    buttons=botones
                )
            ]

        layout_args = dict(
            title=dict(text=f"<b>📈 {titulo}</b>", x=0.02, xanchor="left", font=dict(size=17, color="#0f172a")),
            xaxis_title="<b>Periodo / Segmento</b>",
            yaxis_title=f"<b>Valor ({unidad})</b>" if unidad else "<b>Valor</b>",
            template="plotly_white",
            height=480,
            hovermode="x unified" if len(series) > 1 else "closest",
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="center",
                x=0.5,
                font=dict(size=12, color="#1e293b"),
                bgcolor="rgba(248, 250, 252, 0.9)",
                bordercolor="#cbd5e1",
                borderwidth=1,
                itemclick="toggle",
                itemdoubleclick="toggleothers"
            ),
            margin=dict(l=45, r=60 if (tipo not in ["torta", "pie", "circular", "dona", "donut"] and len(series) > 2) else 130, t=75, b=90)
        )

        if updatemenus:
            layout_args["updatemenus"] = updatemenus

        if tipo not in ["torta", "pie", "circular", "dona", "donut"] and conviene_enfocar:
            layout_args["yaxis"] = dict(range=rango_enfocado, autorange=False)

        fig.update_layout(**layout_args)
        return fig
    except Exception as e:
        print(f"Error generando figura Plotly: {e}")
        return None

def dibujar_grafico(chart_data, key=None):
    """Renderiza gráficos Plotly interactivos en Streamlit."""
    if not chart_data or not isinstance(chart_data, dict):
        return

    if not key:
        key = f"plotly_chart_{uuid.uuid4().hex[:10]}"

    if HAS_PLOTLY:
        fig = generar_figura_plotly(chart_data, incluir_updatemenus=True)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, key=key)
            return

    # Fallback básico si falla Plotly
    try:
        eje_x = chart_data.get("eje_x", chart_data.get("x", []))
        series = chart_data.get("series", [])
        titulo = chart_data.get("titulo", "Visualización Operativa")
        tipo = str(chart_data.get("tipo", "linea")).lower()
        df_chart = pd.DataFrame(index=eje_x)
        for s in series:
            df_chart[s.get("nombre", "Serie")] = s.get("valores", [])
        st.markdown(f"**📈 {titulo}**")
        if "barra" in tipo:
            st.bar_chart(df_chart)
        else:
            st.line_chart(df_chart)
    except Exception as e:
        st.warning(f"No se pudo graficar: {e}")
