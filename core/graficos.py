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

def detectar_unidad_serie(nombre_serie, valores, unidad_general=""):
    """
    Determina la unidad específica de una serie de datos ('%', 's', o '').
    Evita imprimir 'mixta', 'varias' o textos erróneos como sufijo numérico en los puntos del gráfico.
    """
    n = (nombre_serie or "").lower()
    ug_clean = (unidad_general or "").lower().strip()
    if ug_clean in ["mixta", "mixto", "mix", "varias", "diversas", "multiple", "múltiple", "distintas"]:
        ug_clean = ""

    if any(k in n for k in ["tmo", "tiempo", "tt", "hold", "acw", "saliente", "segundo", "duracion"]):
        return "s"
    if any(k in n for k in ["nps", "%", "spl", "resolucion", "resolución", "tasa", "participacion", "participación", "adherencia", "baño", "refrigerio", "coaching"]):
        return "%"

    vals_num = [v for v in valores if isinstance(v, (int, float))]
    if vals_num:
        prom = sum(vals_num) / len(vals_num)
        if prom > 150:
            return "s"
        if max(vals_num) <= 100:
            return "%"

    return ug_clean

def generar_figura_plotly(chart_data, incluir_updatemenus=True):
    """
    Construye y retorna un objeto go.Figure estandarizado a partir de chart_data.
    Reutilizable tanto para renderizado en pantalla como para exportación estática a PDF/PNG.
    Soporta eje dual Y inteligente cuando se combinan métricas de porcentaje (%) y tiempo (s).
    """
    if not chart_data or not isinstance(chart_data, dict) or not HAS_PLOTLY:
        return None

    try:
        tipo = str(chart_data.get("tipo", "linea")).lower()
        titulo = chart_data.get("titulo", "Visualización Operativa")
        eje_x = chart_data.get("eje_x", chart_data.get("x", []))
        series = chart_data.get("series", [])
        unidad_raw = chart_data.get("unidad", "")

        # Ordenar cronológicamente si es una serie temporal (meses en español)
        if tipo not in ["torta", "pie", "circular", "dona", "donut"] and eje_x and series:
            eje_x, series = ordenar_cronologico(eje_x, series)

        colores = ['#2563eb', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6']
        fig = go.Figure()

        # Detección de unidades por serie (elimina 'mixta')
        series_units = [detectar_unidad_serie(s.get("nombre", ""), s.get("valores", []), unidad_raw) for s in series]
        tiene_pct = any(u == "%" for u in series_units)
        tiene_sec = any(u == "s" for u in series_units)
        es_dual = tiene_pct and tiene_sec and tipo not in ["torta", "pie", "circular", "dona", "donut"]

        # Configuración del título del eje Y
        if es_dual:
            yaxis_title = "<b>Porcentaje (%)</b>"
        elif tiene_pct:
            yaxis_title = "<b>Porcentaje (%)</b>"
        elif tiene_sec:
            yaxis_title = "<b>Tiempo (segundos)</b>"
        else:
            ug_s = unidad_raw if str(unidad_raw).lower() not in ["mixta", "mix", "mixto", "varias"] else ""
            yaxis_title = f"<b>Valor ({ug_s})</b>" if ug_s else "<b>Valor</b>"

        layout_args = dict(
            title=dict(text=f"<b>📈 {titulo}</b>", x=0.02, xanchor="left", font=dict(size=17, color="#0f172a")),
            xaxis_title="<b>Periodo / Segmento</b>",
            yaxis=dict(title=yaxis_title),
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
            margin=dict(l=50, r=70 if es_dual else (60 if len(series) > 2 else 120), t=75, b=90)
        )

        if es_dual:
            # Eje Y2 secundario para métricas de tiempo (segundos) a la derecha
            layout_args["yaxis2"] = dict(
                title="<b>TMO / Tiempo (segundos)</b>",
                overlaying="y",
                side="right",
                showgrid=False
            )

        # Caso 1: Torta / Donut
        if tipo in ["torta", "pie", "circular", "dona", "donut"]:
            valores_torta = series[0].get("valores", []) if series else []
            u_torta = series_units[0] if series_units else "%"
            fig.add_trace(go.Pie(
                labels=eje_x,
                values=valores_torta,
                hole=0.35,
                textinfo="label+value+percent",
                hovertemplate="%{label}: <b>%{value}" + (f"{u_torta}" if u_torta else "") + "</b> (%{percent})<extra></extra>"
            ))
        # Caso 2: Barras Agrupadas (barmode="group", NUNCA apiladas)
        elif tipo in ["barra", "barras", "bar"]:
            todos_los_valores = []
            for s in series:
                for v in s.get("valores", []):
                    if isinstance(v, (int, float)):
                        todos_los_valores.append(float(v))
            max_val = max(todos_los_valores) if todos_los_valores else 100.0

            for i, s in enumerate(series):
                nombre = s.get("nombre", "Métrica")
                valores = s.get("valores", [])
                color = colores[i % len(colores)]
                u_serie = series_units[i]
                text_labels = [f"<b>{v}{u_serie}</b>" for v in valores]

                fig.add_trace(go.Bar(
                    x=eje_x,
                    y=valores,
                    name=nombre,
                    text=text_labels,
                    textposition="outside",
                    textfont=dict(size=10, family="Arial, sans-serif"),
                    marker=dict(color=color, line=dict(width=0.5, color="#334155")),
                    hovertemplate="<b>" + str(nombre) + "</b>: %{y}" + (str(u_serie) if u_serie else "") + "<extra></extra>"
                ))

            layout_args["barmode"] = "group"
            layout_args["bargap"] = 0.20
            layout_args["bargroupgap"] = 0.05
            layout_args["yaxis"]["range"] = [0, max_val * 1.18]
            layout_args["yaxis"]["autorange"] = False

        # Caso 3: Líneas (con separación inteligente y soporte de eje dual)
        else:
            es_multilinea = len(series) > 2

            # Recolectar valores por unidad para enfocar ejes
            vals_pct = []
            vals_sec = []
            for i, s in enumerate(series):
                for v in s.get("valores", []):
                    if isinstance(v, (int, float)):
                        if series_units[i] == "s":
                            vals_sec.append(float(v))
                        else:
                            vals_pct.append(float(v))

            for i, s in enumerate(series):
                nombre = s.get("nombre", "Métrica")
                valores = s.get("valores", [])
                color = colores[i % len(colores)]
                u_serie = series_units[i]
                text_labels = [f"<b>{v}{u_serie}</b>" for v in valores]

                modo = "lines+markers" if (es_multilinea or es_dual) else "lines+markers+text"
                eje_y_destino = "y2" if (es_dual and u_serie == "s") else "y"

                fig.add_trace(go.Scatter(
                    x=eje_x,
                    y=valores,
                    mode=modo,
                    name=f"{nombre} ({u_serie})" if (es_dual and u_serie) else nombre,
                    yaxis=eje_y_destino,
                    line=dict(width=3, color=color),
                    marker=dict(size=7, color=color),
                    text=text_labels,
                    textposition="top center",
                    textfont=dict(size=11, color=color, family="Arial, sans-serif"),
                    hovertemplate="<b>" + str(nombre) + "</b>: %{y}" + (str(u_serie) if u_serie else "") + "<extra></extra>"
                ))

                if not es_multilinea and not es_dual and eje_x and valores:
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

            if es_dual:
                if vals_pct:
                    min_p = min(vals_pct)
                    max_p = max(vals_pct)
                    pad_p = max((max_p - min_p) * 0.2, 5.0)
                    layout_args["yaxis"]["range"] = [max(0.0, min_p - pad_p), min(100.0, max_p + pad_p)]
                    layout_args["yaxis"]["autorange"] = False
                if vals_sec:
                    min_s = min(vals_sec)
                    max_s = max(vals_sec)
                    pad_s = max((max_s - min_s) * 0.2, 20.0)
                    layout_args["yaxis2"]["range"] = [max(0.0, min_s - pad_s), max_s + pad_s]
                    layout_args["yaxis2"]["autorange"] = False
            else:
                todos_los_valores = vals_pct + vals_sec
                vals_activos = [v for v in todos_los_valores if v > 0] or todos_los_valores
                if vals_activos:
                    min_activo = min(vals_activos)
                    max_val = max(todos_los_valores)
                    delta = max_val - min_activo
                    pad = max(delta * 0.15, 2.0)
                    rango_enfocado = [max(0.0, min_activo - pad), max_val + pad]
                    conviene_enfocar = (min_activo >= 20.0 and delta < 45.0) or (len(series) >= 3 and delta < 40.0)
                    if conviene_enfocar:
                        layout_args["yaxis"]["range"] = rango_enfocado
                        layout_args["yaxis"]["autorange"] = False

        # Botones interactivos en la barra superior
        updatemenus = []
        if incluir_updatemenus and tipo not in ["torta", "pie", "circular", "dona", "donut"]:
            botones = []
            if tipo in ["barra", "barras", "bar"]:
                botones.append(dict(label="🏷️ Ver Valores", method="restyle", args=[{"textposition": "outside"}]))
                botones.append(dict(label="👁️ Ocultar Valores", method="restyle", args=[{"textposition": "none"}]))
            else:
                botones.append(dict(label="🏷️ Ver Valores", method="restyle", args=[{"mode": "lines+markers+text"}]))
                botones.append(dict(label="👁️ Ocultar Valores", method="restyle", args=[{"mode": "lines+markers"}]))

                if not es_dual:
                    todos_los_valores = [float(v) for s in series for v in s.get("valores", []) if isinstance(v, (int, float))]
                    vals_activos = [v for v in todos_los_valores if v > 0] or todos_los_valores
                    if vals_activos:
                        min_act = min(vals_activos)
                        max_v = max(todos_los_valores)
                        delta = max_v - min_act
                        pad = max(delta * 0.15, 2.0)
                        r_enf = [max(0.0, min_act - pad), max_v + pad]
                        r_comp = [0.0, max_v + pad]
                        botones.append(dict(label="🔍 Separar Líneas", method="relayout", args=[{"yaxis.autorange": False, "yaxis.range": r_enf}]))
                        botones.append(dict(label="📏 Escala desde 0", method="relayout", args=[{"yaxis.autorange": False, "yaxis.range": r_comp}]))

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

        if updatemenus:
            layout_args["updatemenus"] = updatemenus

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

        # Ordenar cronológicamente si aplica
        if eje_x and series:
            eje_x, series = ordenar_cronologico(eje_x, series)

        df_chart = pd.DataFrame(index=eje_x)
        for s in series:
            df_chart[s.get("nombre", "Serie")] = s.get("valores", [])
        st.markdown(f"**📈 {titulo}**")
        if "barra" in tipo:
            st.bar_chart(df_chart, stack=False)
        else:
            st.line_chart(df_chart)
    except Exception as e:
        st.warning(f"No se pudo graficar: {e}")
