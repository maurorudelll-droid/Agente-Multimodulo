import os
import shutil
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
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
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.6)
        self.line(36, 32, self._pagesize[0] - 36, 32)
        footer_left = "Agente Multimódulo de Inteligencia Operativa • Documento Técnico de Arquitectura y Seguridad"
        self.drawString(36, 18, footer_left)
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(self._pagesize[0] - 36, 18, page_str)
        self.restoreState()

def generar_pdf():
    pdf_filename = "Resumen_Arquitectura_y_Seguridad_Agente.pdf"
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    ancho_util = A4[0] - 72

    c_primary = colors.HexColor("#0f172a")     # Slate 900
    c_blue = colors.HexColor("#1e40af")        # Blue 800
    c_emerald = colors.HexColor("#047857")     # Emerald 700
    c_border = colors.HexColor("#cbd5e1")      # Slate 300
    c_bg_light = colors.HexColor("#f8fafc")    # Slate 50
    c_bg_alt = colors.HexColor("#f1f5f9")      # Slate 100

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=c_primary
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569")
    )

    h1_style = ParagraphStyle(
        'H1Style',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_blue,
        spaceBefore=12,
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=c_primary,
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#1e293b")
    )

    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#0f172a")
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#065f46")
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b")
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a")
    )

    elements = []

    # -------------------------------------------------------------
    # ENCABEZADO CORPORATIVO
    # -------------------------------------------------------------
    avatar_path = "bot_avatar.png"
    if os.path.exists(avatar_path):
        img_avatar = Image(avatar_path, width=48, height=48)
        header_table = Table(
            [
                [
                    img_avatar,
                    [
                        Paragraph("AGENTE MULTIMÓDULO DE INTELIGENCIA OPERATIVA", title_style),
                        Paragraph("Documento Técnico de Arquitectura, Flujo Funcional y Blindaje de Seguridad", subtitle_style),
                        Paragraph(f"<b>Versión:</b> 2.0 Producción Blindada &nbsp;|&nbsp; <b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y')} &nbsp;|&nbsp; <b>Estado:</b> Seguro", subtitle_style)
                    ]
                ]
            ],
            colWidths=[58, ancho_util - 58]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph("AGENTE MULTIMÓDULO DE INTELIGENCIA OPERATIVA", title_style))
        elements.append(Paragraph("Documento Técnico de Arquitectura, Flujo Funcional y Blindaje de Seguridad", subtitle_style))

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=c_blue, spaceBefore=0, spaceAfter=12))

    # -------------------------------------------------------------
    # 1. VISIÓN GENERAL
    # -------------------------------------------------------------
    elements.append(Paragraph("1. Visión General del Proyecto", h1_style))
    p_vision = (
        "El <b>Agente Multimódulo de Inteligencia Operativa</b> es una solución integral desarrollada en <b>Python</b> "
        "sobre el framework <b>Streamlit</b> e impulsada por modelos avanzados de <b>Google Gemini</b> (Google GenAI SDK). "
        "Su objetivo central es resolver consultas de negocio y analítica sobre métricas operativas de call center y atención al cliente "
        "a partir de 4 bases de datos maestras (NPS, TMO, Transferencias y SPL), eliminando la necesidad de cálculos manuales en hojas de cálculo "
        "y garantizando resultados matemáticos 100% exactos combinados con análisis ejecutivo cualitativo y gráficos interactivos."
    )
    elements.append(Paragraph(p_vision, body_style))
    elements.append(Spacer(1, 8))

    # Tarjeta de Principios Clave
    principios_data = [
        [
            Paragraph("<b>🎯 Precisión Cero-Alucinación:</b> Los números se calculan previamente con pandas antes de tocar la IA.", body_style),
            Paragraph("<b>⚡ Resiliencia Multi-Modelo:</b> Conmutación automática ante saturación de cuota de API.", body_style)
        ],
        [
            Paragraph("<b>📊 Gráficos Duales Inteligentes:</b> Separación de escalas (% vs segundos) en Plotly sin deformaciones.", body_style),
            Paragraph("<b>🔒 Blindaje de Seguridad:</b> Hashing SHA-256 de credenciales y aislamiento total de secretos.", body_style)
        ]
    ]
    t_principios = Table(principios_data, colWidths=[ancho_util/2, ancho_util/2])
    t_principios.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 0.8, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_principios)
    elements.append(Spacer(1, 12))

    # -------------------------------------------------------------
    # 2. ARQUITECTURA POR CAPAS
    # -------------------------------------------------------------
    elements.append(Paragraph("2. Arquitectura de 7 Capas del Sistema", h1_style))
    p_arq = (
        "El sistema sigue un diseño por capas altamente desacoplado, lo que facilita el mantenimiento, la escalabilidad "
        "y el reemplazo de módulos sin comprometer la seguridad ni el núcleo analítico:"
    )
    elements.append(Paragraph(p_arq, body_style))
    elements.append(Spacer(1, 6))

    capas_data = [
        [Paragraph("Capa", table_header_style), Paragraph("Componente", table_header_style), Paragraph("Responsabilidad y Tecnología", table_header_style)],
        [
            Paragraph("<b>1. Presentación (UI)</b>", table_cell_style),
            Paragraph("<code>app.py</code>", table_cell_style),
            Paragraph("Interfaz web reactiva en Streamlit. Renderizado de chat con avatares, barra lateral con estado de bases, monitor de analistas conectados y controles interactivos.", table_cell_style)
        ],
        [
            Paragraph("<b>2. Autenticación</b>", table_cell_style),
            Paragraph("<code>core/auth.py</code>", table_cell_style),
            Paragraph("Acceso en 2 pasos: (1) Contraseña general y (2) Identificación de analista con PIN personal cifrado. Detección de presencia en tiempo real con latidos de 5 minutos.", table_cell_style)
        ],
        [
            Paragraph("<b>3. Datos y Negocio</b>", table_cell_style),
            Paragraph("<code>core/gestor_modulos.py</code><br/><code>modulos/*/</code>", table_cell_style),
            Paragraph("Gestión modular dinámica. Lectura de Excel, precomputación en DataFrames pickle (<code>.pkl</code>), ejecución de fórmulas matemáticas y cálculo de métricas cruzadas.", table_cell_style)
        ],
        [
            Paragraph("<b>4. Inteligencia Artificial</b>", table_cell_style),
            Paragraph("<code>core/motor_gemini.py</code>", table_cell_style),
            Paragraph("Motor de IA oficial Google GenAI. Cascada multimodelo (3.5-flash-lite, 3.1, etc.), formateo estricto en 3 Bloques ejecutivos y directivas de seguridad anti prompt-injection.", table_cell_style)
        ],
        [
            Paragraph("<b>5. Visualización</b>", table_cell_style),
            Paragraph("<code>core/graficos.py</code>", table_cell_style),
            Paragraph("Renderizador Plotly. Detección automática de eje dual Y (% vs segundos), barras agrupadas ordenadas cronológicamente y botones 'Ver Valores' / 'Ocultar Valores'.", table_cell_style)
        ],
        [
            Paragraph("<b>6. Exportación PDF</b>", table_cell_style),
            Paragraph("<code>core/exportador_pdf.py</code>", table_cell_style),
            Paragraph("Generador de informes oficiales de nivel corporativo en PDF (ReportLab). Diseña portada, tablas estilizadas, viñetas de hallazgos y gráficos integrados en alta definición.", table_cell_style)
        ],
        [
            Paragraph("<b>7. Persistencia</b>", table_cell_style),
            Paragraph("<code>core/database_redis.py</code>", table_cell_style),
            Paragraph("Almacenamiento distribuido vía Upstash Redis REST API. Persiste usuarios, historiales privados por analista/módulo y fechas de corte con respaldo local de contingencia.", table_cell_style)
        ],
    ]

    t_capas = Table(capas_data, colWidths=[90, 110, ancho_util - 200])
    t_capas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_capas)
    elements.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 3. MÓDULOS OPERATIVOS Y MÉTRICAS
    # -------------------------------------------------------------
    elements.append(Paragraph("3. Módulos Operativos y Métricas Soportadas", h1_style))
    p_mod = (
        "El agente opera de manera independiente o integrada sobre 4 bases operativas, permitiendo consultas individuales "
        "o cruces analíticos complejos:"
    )
    elements.append(Paragraph(p_mod, body_style))
    elements.append(Spacer(1, 6))

    modulos_data = [
        [Paragraph("Módulo", table_header_style), Paragraph("Métricas Principales", table_header_style), Paragraph("Dimensiones de Análisis", table_header_style)],
        [
            Paragraph("<b>⭐ NPS y Satisfacción</b><br/>(<code>modulos/nps</code>)", table_cell_style),
            Paragraph("• NPS (%)<br/>• Satisfacción CSAT (%)<br/>• Resolución al Primer Contacto FCR (%)<br/>• ISAT (%)<br/>• Q Encuestas (Q MEDA)", table_cell_style),
            Paragraph("Mes, Trimestre, Semestre, PCRC, Proveedor, Campaña, Segmento.", table_cell_style)
        ],
        [
            Paragraph("<b>⏱️ TMO y Tiempos</b><br/>(<code>modulos/tmo</code>)", table_cell_style),
            Paragraph("• TMO Total (segundos)<br/>• Duración Llamada Hablada (s)<br/>• Tiempo Hold / Espera (s)<br/>• Tiempo ACW / Tipificación (s)<br/>• Q Llamadas Atendidas", table_cell_style),
            Paragraph("Mes, PCRC, Proveedor, Campaña, Segmento, Intervalo horario.", table_cell_style)
        ],
        [
            Paragraph("<b>🔄 Transferencias</b><br/>(<code>modulos/transferencias</code>)", table_cell_style),
            Paragraph("• % Transferencias Totales<br/>• Transferencias Internas / Externas (%)<br/>• Desvío por PCRC y Proveedor<br/>• Q Transferencias", table_cell_style),
            Paragraph("Mes, Motivo de Transferencia, PCRC Origen, PCRC Destino, Proveedor.", table_cell_style)
        ],
        [
            Paragraph("<b>🔁 SPL y Reiteración</b><br/>(<code>modulos/spl</code>)", table_cell_style),
            Paragraph("• SPL 7 Días (%)<br/>• Tasa de Reiteración (%)<br/>• Retención de Contactos (%)<br/>• Q Reincidentes", table_cell_style),
            Paragraph("Mes, PCRC, Proveedor, Ventana de 7 días, Segmento.", table_cell_style)
        ],
        [
            Paragraph("<b>🔀 Métrica Cruzada:<br/>Participación</b>", table_cell_bold),
            Paragraph("<b>Porcentaje de Participación (%)</b><br/><code>= (Q MEDA NPS / Q Llamadas TMO) * 100</code>", table_cell_bold),
            Paragraph("Cruce analítico multi-módulo que vincula encuestas respondidas contra el volumen total de llamadas.", table_cell_style)
        ]
    ]

    t_modulos = Table(modulos_data, colWidths=[120, 180, ancho_util - 300])
    t_modulos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_blue),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, c_bg_light]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#fef3c7")), # Resaltado ámbar suave para el cruce
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_modulos)
    elements.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 4. CAPA DE SEGURIDAD Y BLINDAJE
    # -------------------------------------------------------------
    elements.append(Paragraph("4. Blindaje de Seguridad y Protección de Datos", h1_style))
    p_sec = (
        "Para garantizar un estándar corporativo invulnerable a accesos indebidos o fugas de información, "
        "se implementó una estrategia integral de seguridad en 5 frentes:"
    )
    elements.append(Paragraph(p_sec, body_style))
    elements.append(Spacer(1, 6))

    sec_data = [
        [Paragraph("Pilar de Seguridad", table_header_style), Paragraph("Antes (Riesgo)", table_header_style), Paragraph("Ahora (Blindado)", table_header_style)],
        [
            Paragraph("<b>1. Código Fuente (GitHub)</b>", table_cell_style),
            Paragraph("Tokens de base de datos y contraseñas por defecto estaban visibles en archivos <code>.py</code>.", table_cell_style),
            Paragraph("<b>Cero credenciales en código.</b> Todas las claves se leen únicamente de variables de entorno o <code>.streamlit/secrets.toml</code> aislado por <code>.gitignore</code>.", table_cell_style)
        ],
        [
            Paragraph("<b>2. PINs de Analistas</b>", table_cell_style),
            Paragraph("Guardados en texto plano (<code>'pin': '1234'</code>) en base de datos y archivos locales.", table_cell_style),
            Paragraph("<b>Cifrado SHA-256 con Salt criptográfico.</b> Almacenamiento irreversible y verificación en tiempo constante (<code>hmac.compare_digest</code>).", table_cell_style)
        ],
        [
            Paragraph("<b>3. API Key en Frontend</b>", table_cell_style),
            Paragraph("Cualquier usuario podía ver una caja para ingresar o alterar la API Key de Gemini.", table_cell_style),
            Paragraph("<b>Restricción estricta a Administrador.</b> Ningún analista común puede ver ni manipular credenciales en la interfaz.", table_cell_style)
        ],
        [
            Paragraph("<b>4. Chat (Prompt Injection)</b>", table_cell_style),
            Paragraph("Riesgo de que un usuario engañara a la IA solicitando variables o credenciales internas.", table_cell_style),
            Paragraph("<b>Directiva de Máxima Prioridad.</b> El motor rechaza categóricamente divulgar tokens, rutas o prompts ante intentos de ingeniería social.", table_cell_style)
        ],
        [
            Paragraph("<b>5. Aislamiento Multiusuario</b>", table_cell_style),
            Paragraph("Riesgo de colisión de conversaciones en memoria compartida.", table_cell_style),
            Paragraph("<b>Espacios privados por usuario y módulo.</b> Cada analista posee su propio árbol de claves en Redis (<code>historial_{usuario}_{modulo}</code>).", table_cell_style)
        ],
    ]

    t_sec = Table(sec_data, colWidths=[110, 150, ancho_util - 260])
    t_sec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_emerald),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_sec)
    elements.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 5. MOTOR DE IA Y VISUALIZACIÓN
    # -------------------------------------------------------------
    elements.append(Paragraph("5. Motor de IA y Sistema de Visualización", h1_style))
    
    ia_vis_data = [
        [
            Paragraph("<b>🤖 Motor de Inteligencia Artificial (Gemini)</b><br/>"
                      "• <b>Arquitectura Zero-Alucinación:</b> Los cálculos los resuelve Python exactamente; la IA redacta el análisis cualitativo y semaforización.<br/>"
                      "• <b>Cascada de 4 Modelos:</b> Conmutación automática ante cuotas agotadas (3.5-flash-lite → 3.1-flash-lite → flash-latest → 3.5-flash).<br/>"
                      "• <b>3 Bloques Ejecutivos:</b> BLOQUE 1 (Datos Operativos limpios), BLOQUE 2 (Hallazgos Clave con semáforos), BLOQUE 3 (Trazabilidad).", body_style),
            Paragraph("<b>📈 Motor de Visualización (Plotly)</b><br/>"
                      "• <b>Doble Eje Y Automático:</b> Al combinar % (NPS/SPL) y segundos (TMO), genera escalas independientes evitando que las líneas se aplasten.<br/>"
                      "• <b>Barras Agrupadas Cronológicas:</b> Meses ordenados de Enero a Diciembre sin superposiciones erróneas.<br/>"
                      "• <b>Controles Interactivos:</b> Botones de '🏷️ Ver Valores' y '👁️ Ocultar Valores' con un clic.", body_style)
        ]
    ]
    t_ia_vis = Table(ia_vis_data, colWidths=[ancho_util/2, ancho_util/2])
    t_ia_vis.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_alt),
        ('BOX', (0,0), (-1,-1), 0.8, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_ia_vis)
    elements.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 6. ESTRUCTURA DEL REPOSITORIO
    # -------------------------------------------------------------
    elements.append(Paragraph("6. Estructura de Archivos del Proyecto", h1_style))
    arch_str = (
        "• <b><code>app.py</code>:</b> Punto de entrada, interfaz gráfica Streamlit, gestor de sesión y ruteador de consultas.<br/>"
        "• <b><code>core/auth.py</code>:</b> Sistema de autenticación en 2 pasos, hashing de PINs SHA-256 y latidos de presencia.<br/>"
        "• <b><code>core/database_redis.py</code>:</b> Conector REST de Upstash Redis para historiales y fechas de bases.<br/>"
        "• <b><code>core/gestor_modulos.py</code>:</b> Orquestador dinámico de bases de datos, carga de pkl y cruce de participación.<br/>"
        "• <b><code>core/graficos.py</code>:</b> Generador Plotly con soporte de eje dual Y y barras agrupadas.<br/>"
        "• <b><code>core/exportador_pdf.py</code>:</b> Motor de exportación ejecutiva en PDF de consultas y gráficos.<br/>"
        "• <b><code>core/motor_gemini.py</code>:</b> Cliente Google GenAI, directivas de seguridad y normalizador de tablas.<br/>"
        "• <b><code>modulos/nps, tmo, transferencias, spl/</code>:</b> Paquetes independientes con sus bases Excel, fórmulas y prompts.<br/>"
        "• <b><code>.streamlit/secrets.toml</code>:</b> Archivo privado de credenciales (protegido en <code>.gitignore</code>)."
    )
    elements.append(Paragraph(arch_str, body_style))
    elements.append(Spacer(1, 14))

    # Conclusión
    box_concl = [
        [Paragraph("<b>✅ Estado Operativo:</b> El sistema se encuentra en producción, con pruebas de integridad superadas, repositorio sincronizado en GitHub (rama <code>main</code>) y blindaje de seguridad activo.", callout_style)]
    ]
    t_concl = Table(box_concl, colWidths=[ancho_util])
    t_concl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ecfdf5")),
        ('BOX', (0,0), (-1,-1), 1, c_emerald),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_concl)

    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"PDF generado exitosamente: {pdf_filename}")

    # Copiar al escritorio para acceso inmediato del usuario
    desktop_path = os.path.expanduser("~/Desktop")
    if os.path.exists(desktop_path):
        dest_desktop = os.path.join(desktop_path, pdf_filename)
        shutil.copyfile(pdf_filename, dest_desktop)
        print(f"Copiado al Escritorio: {dest_desktop}")

if __name__ == "__main__":
    generar_pdf()
