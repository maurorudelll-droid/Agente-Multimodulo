import os
import re
import io
from datetime import datetime
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from core.graficos import generar_figura_plotly

class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular y numerar páginas dinámicamente."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Pie de página: Línea separadora
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.6)
        self.line(36, 32, self._pagesize[0] - 36, 32)

        # Textos de pie de página
        footer_left = "Agente Master de Inteligencia Operativa • Reporte Oficial Ejecutivo"
        self.drawString(36, 18, footer_left)
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(self._pagesize[0] - 36, 18, page_str)
        self.restoreState()

def limpiar_texto_para_pdf(texto):
    """
    Normaliza el texto para ReportLab:
    1. Reemplaza semáforos Unicode con etiquetas de color compatibles.
    2. Convierte formato markdown básico (**negrita**) a HTML (<b>).
    3. Escapa caracteres reservados si es necesario.
    """
    if not texto:
        return ""
    
    t = str(texto)
    # Reemplazo de semáforos por distintivos con color
    t = t.replace("🟢", '<font color="#16a34a"><b> [Óptimo]</b></font>')
    t = t.replace("🔴", '<font color="#dc2626"><b> [Desvío]</b></font>')
    
    # Markdown negrita (**texto** -> <b>texto</b>)
    t = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', t)
    # Markdown cursiva (*texto* -> <i>texto</i>)
    t = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', t)
    
    # Reemplazar viñetas markdown
    t = re.sub(r'^\s*[\*\-]\s*', '• ', t)
    
    return t.strip()

def extraer_componentes_respuesta(content):
    """
    Extrae la tabla Markdown del Bloque 1, el contenido del Bloque 2 y el Bloque 3.
    """
    b1_match = re.search(r'(?i)BLOQUE\s*1[^\n]*', content)
    b2_match = re.search(r'(?i)BLOQUE\s*2[^\n]*', content)
    b3_match = re.search(r'(?i)BLOQUE\s*3[^\n]*', content)

    idx_b1 = b1_match.start() if b1_match else 0
    idx_b2 = b2_match.start() if b2_match else len(content)
    idx_b3 = b3_match.start() if b3_match else len(content)

    parte_b1 = content[idx_b1:idx_b2].strip()
    parte_b2 = content[idx_b2:idx_b3].strip()
    parte_b3 = content[idx_b3:].strip()

    # Procesar tabla del bloque 1
    filas_tabla = []
    resto_b1 = []
    for linea in parte_b1.split("\n"):
        strip = linea.strip()
        if strip.startswith("|") and strip.endswith("|"):
            celdas = [c.strip() for c in strip.split("|")[1:-1]]
            if all(set(c) <= set(":- ") for c in celdas):
                continue  # Línea separadora Markdown
            filas_tabla.append(celdas)
        else:
            if not any(k in strip.upper() for k in ["BLOQUE 1", "DATOS OPERATIVOS"]) and strip:
                resto_b1.append(strip)

    # Limpiar líneas de Bloque 2
    b2_lineas = [
        l.strip() for l in parte_b2.split("\n")
        if l.strip() and not any(k in l.upper() for k in ["BLOQUE 2", "HALLAZGOS CLAVE"])
    ]

    # Limpiar líneas de Bloque 3
    b3_lineas = [
        l.strip() for l in parte_b3.split("\n")
        if l.strip() and not any(k in l.upper() for k in ["BLOQUE 3", "TRAZABILIDAD"])
    ]

    return {
        "tabla_b1": filas_tabla,
        "texto_b1": "\n".join(resto_b1),
        "lineas_b2": b2_lineas,
        "lineas_b3": b3_lineas
    }

def generar_pdf_reporte(content, chart_data=None, usuario="Usuario", modulos_usados=None):
    """
    Genera un archivo PDF ejecutivo en memoria con diseño formal de alta calidad.
    Retorna bytes del archivo PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=42
    )

    ancho_util = doc.width  # ~523 pt en A4 con márgenes 36pt

    # Paleta de colores ejecutivos
    c_primario = colors.HexColor("#1e3a8a")     # Azul marino institucional
    c_secundario = colors.HexColor("#0284c7")   # Azul celeste ejecutivo
    c_oscuro = colors.HexColor("#0f172a")       # Texto principal
    c_gris_claro = colors.HexColor("#f8fafc")   # Fondo filas alternas
    c_borde = colors.HexColor("#cbd5e1")        # Bordes suaves
    c_card_bg = colors.HexColor("#f1f5f9")      # Fondo tarjetas

    styles = getSampleStyleSheet()

    # Estilos tipográficos refinados
    style_titulo = ParagraphStyle(
        "ReportTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=c_primario
    )
    style_subtitulo = ParagraphStyle(
        "ReportSubTitle",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569")
    )
    style_bloque_header = ParagraphStyle(
        "BlockHeader",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.white
    )
    style_celda_header = ParagraphStyle(
        "CellHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=1,  # Centrado
        textColor=colors.white
    )
    style_celda = ParagraphStyle(
        "CellBody",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        alignment=1,  # Centrado
        textColor=c_oscuro
    )
    style_celda_izq = ParagraphStyle(
        "CellBodyLeft",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        alignment=0,  # Izquierda
        textColor=c_oscuro
    )
    style_item_b2 = ParagraphStyle(
        "ItemB2",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=c_oscuro
    )
    style_item_b3 = ParagraphStyle(
        "ItemB3",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155")
    )

    story = []

    # 1. ENCABEZADO EJECUTIVO CON LOGO / AVATAR
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    bases_txt = ", ".join(modulos_usados) if modulos_usados else "Inteligencia Operativa Unificada"

    header_data = []
    avatar_path = "bot_avatar.png"
    if os.path.exists(avatar_path):
        try:
            img_avatar = Image(avatar_path, width=42, height=42)
            col_avatar = img_avatar
        except Exception:
            col_avatar = Paragraph("🤖", style_titulo)
    else:
        col_avatar = Paragraph("🤖", style_titulo)

    info_header = Paragraph(
        f"<b>REPORTE EJECUTIVO DE INTELIGENCIA OPERATIVA</b><br/>"
        f"<font size=8 color='#64748b'>Generado para: <b>{usuario}</b> &nbsp;|&nbsp; Emisión: <b>{fecha_emision}</b> &nbsp;|&nbsp; Bases: <b>{bases_txt}</b></font>",
        style_subtitulo
    )

    t_header = Table([[col_avatar, info_header]], colWidths=[50, ancho_util - 50])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t_header)

    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=2, color=c_primario, spaceBefore=2, spaceAfter=10))

    # Parsear componentes de la respuesta del modelo
    componentes = extraer_componentes_respuesta(content)

    # 2. BLOQUE 1: DATOS OPERATIVOS
    tabla_b1 = componentes["tabla_b1"]

    # Banner del Bloque 1
    t_b1_title = Table([[Paragraph("  BLOQUE 1: DATOS OPERATIVOS", style_bloque_header)]], colWidths=[ancho_util])
    t_b1_title.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), c_primario),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_b1_title)
    story.append(Spacer(1, 4))

    if tabla_b1:
        num_cols = len(tabla_b1[0])
        col_widths = [ancho_util / num_cols] * num_cols

        # Ajuste inteligente de anchos: columna 0 (Periodo) y 1 (Proveedor/PCRC) un poco más anchas
        if num_cols >= 3:
            col_widths[0] = ancho_util * 0.18
            col_widths[1] = ancho_util * 0.28
            ancho_restante = ancho_util - (col_widths[0] + col_widths[1])
            for i in range(2, num_cols):
                col_widths[i] = ancho_restante / (num_cols - 2)

        datos_tabla_pdf = []
        for r_idx, fila in enumerate(tabla_b1):
            fila_pdf = []
            for c_idx, val in enumerate(fila):
                val_limpio = limpiar_texto_para_pdf(val)
                if r_idx == 0:
                    fila_pdf.append(Paragraph(val_limpio, style_celda_header))
                else:
                    st_c = style_celda_izq if c_idx in [0, 1] else style_celda
                    fila_pdf.append(Paragraph(val_limpio, st_c))
            datos_tabla_pdf.append(fila_pdf)

        t_datos = Table(datos_tabla_pdf, colWidths=col_widths, repeatRows=1)
        estilos_datos = [
            ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
            ('GRID', (0, 0), (-1, -1), 0.5, c_borde),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        # Fondo alternado en filas
        for r in range(1, len(datos_tabla_pdf)):
            bg = c_gris_claro if r % 2 == 0 else colors.white
            estilos_datos.append(('BACKGROUND', (0, r), (-1, r), bg))

        t_datos.setStyle(TableStyle(estilos_datos))
        story.append(t_datos)
    elif componentes["texto_b1"]:
        story.append(Paragraph(limpiar_texto_para_pdf(componentes["texto_b1"]), style_item_b2))

    story.append(Spacer(1, 10))

    # 3. BLOQUE 2: HALLAZGOS CLAVE
    if componentes["lineas_b2"]:
        t_b2_title = Table([[Paragraph("  BLOQUE 2: HALLAZGOS CLAVE", style_bloque_header)]], colWidths=[ancho_util])
        t_b2_title.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0f766e")), # Verde esmeralda ejecutivo
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elementos_b2 = [t_b2_title, Spacer(1, 4)]
        celdas_b2 = []
        for l in componentes["lineas_b2"]:
            l_limpia = limpiar_texto_para_pdf(l)
            celdas_b2.append([Paragraph(f"• {l_limpia}" if not l_limpia.startswith("•") else l_limpia, style_item_b2)])

        if celdas_b2:
            t_box_b2 = Table(celdas_b2, colWidths=[ancho_util])
            t_box_b2.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#86efac")),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            elementos_b2.append(t_box_b2)
        
        story.append(KeepTogether(elementos_b2))
        story.append(Spacer(1, 10))

    # 4. BLOQUE 3: TRAZABILIDAD
    if componentes["lineas_b3"]:
        t_b3_title = Table([[Paragraph("  BLOQUE 3: TRAZABILIDAD Y FUENTES", style_bloque_header)]], colWidths=[ancho_util])
        t_b3_title.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#475569")), # Gris pizarra ejecutivo
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elementos_b3 = [t_b3_title, Spacer(1, 4)]
        celdas_b3 = []
        for l in componentes["lineas_b3"]:
            l_limpia = limpiar_texto_para_pdf(l)
            celdas_b3.append([Paragraph(f"• {l_limpia}" if not l_limpia.startswith("•") else l_limpia, style_item_b3)])

        if celdas_b3:
            t_box_b3 = Table(celdas_b3, colWidths=[ancho_util])
            t_box_b3.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), c_card_bg),
                ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            elementos_b3.append(t_box_b3)

        story.append(KeepTogether(elementos_b3))
        story.append(Spacer(1, 10))

    # 5. GRÁFICO OPERATIVO (SI EXISTE)
    if chart_data and isinstance(chart_data, dict):
        try:
            fig = generar_figura_plotly(chart_data, incluir_updatemenus=False)
            if fig is not None:
                # Exportar gráfico Plotly a imagen PNG de alta densidad
                img_bytes = fig.to_image(format="png", width=950, height=430, scale=2)
                if img_bytes:
                    img_stream = io.BytesIO(img_bytes)
                    img_pdf = Image(img_stream, width=ancho_util, height=ancho_util * 0.45)
                    
                    titulo_g = chart_data.get("titulo", "Visualización Operativa")
                    t_g_title = Table([[Paragraph(f"  GRÁFICO: {titulo_g.upper()}", style_bloque_header)]], colWidths=[ancho_util])
                    t_g_title.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), c_secundario),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ]))
                    story.append(KeepTogether([t_g_title, Spacer(1, 4), img_pdf]))
        except Exception as e:
            print(f"Advertencia al incrustar gráfico en PDF: {e}")

    # Compilar el documento
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()

import json
import streamlit as st

@st.cache_data(show_spinner=False)
def obtener_pdf_reporte_cached(content, chart_json_str, usuario, modulos_list_str):
    """Caché en memoria para evitar regenerar el PDF en cada rerun de Streamlit."""
    chart_data = json.loads(chart_json_str) if chart_json_str else None
    modulos_usados = json.loads(modulos_list_str) if modulos_list_str else None
    return generar_pdf_reporte(content, chart_data=chart_data, usuario=usuario, modulos_usados=modulos_usados)

def render_boton_descarga_pdf(content, chart=None, usuario="Usuario", modulos_usados=None, key="btn_pdf"):
    """
    Renderiza el botón de descarga del reporte en PDF con estilo corporativo.
    """
    if not content or ("BLOQUE" not in content and not chart):
        return

    chart_str = json.dumps(chart, sort_keys=True) if chart else ""
    modulos_str = json.dumps(modulos_usados, sort_keys=True) if modulos_usados else ""

    try:
        pdf_bytes = obtener_pdf_reporte_cached(content, chart_str, usuario, modulos_str)
        if pdf_bytes:
            st.download_button(
                label="📄 Descargar Reporte en PDF",
                data=pdf_bytes,
                file_name=f"Reporte_Operativo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                key=key,
                use_container_width=True
            )
    except Exception as e:
        st.caption(f"ℹ️ Exportación PDF no disponible: {e}")
