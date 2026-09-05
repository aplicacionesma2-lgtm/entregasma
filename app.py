"""
Panel de Documentos Pendientes de Atención
--------------------------------------------
Lee los registros filtrados desde Google Sheets y permite explorar,
por fecha de vencimiento, almacenes, documento o artículos,
qué documentos tienen cantidad pendiente de atender.
Permite además exportar el resumen agrupado a un archivo PDF.
"""

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from streamlit_gsheets import GSheetsConnection

# --------------------------------------------------------------------------
# Configuración general de la página
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Pendientes de Atención",
    page_icon="📦",
    layout="wide",
)

# --------------------------------------------------------------------------
# Estilos: tarjetas de métricas y tipografía
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');

    html, body, [class*="css"]  {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    .app-header {
        display: flex;
        align-items: baseline;
        gap: 0.6rem;
        margin-bottom: 0.1rem;
    }
    .app-header h1 {
        font-size: 1.65rem;
        font-weight: 700;
        color: #1B2A38;
        margin: 0;
    }
    .app-subtitle {
        color: #5A6B7A;
        font-size: 0.95rem;
        margin-bottom: 1.4rem;
    }

    .metric-row {
        display: flex;
        gap: 14px;
        flex-wrap: wrap;
        margin-bottom: 1.6rem;
    }
    .metric-card {
        flex: 1 1 190px;
        border-radius: 10px;
        padding: 18px 20px;
        color: #FFFFFF;
        box-shadow: 0 2px 10px rgba(20, 30, 40, 0.12);
    }
    .metric-card .metric-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.9rem;
        font-weight: 600;
        line-height: 1.1;
    }
    .metric-card .metric-label {
        font-size: 0.83rem;
        opacity: 0.92;
        margin-top: 4px;
    }
    .metric-docs   { background: #2C5F7C; }
    .metric-items  { background: #B8790C; }
    .metric-qty    { background: #1F7A5C; }
    .metric-pend   { background: #B84A3E; }

    .section-title {
        font-weight: 600;
        font-size: 1.05rem;
        color: #1B2A38;
        margin: 1.6rem 0 0.5rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Función para generar el PDF del Resumen por Artículo
# --------------------------------------------------------------------------
def generar_pdf_resumen(df_resumen: pd.DataFrame, filtros_info: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    story = []
    styles = getSampleStyleSheet()

    # Estilos de texto
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1B2A38'),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#5A6B7A'),
        spaceAfter=12,
    )

    cell_header_style = ParagraphStyle(
        'HeaderCell',
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white,
        alignment=0,
    )

    cell_body_style = ParagraphStyle(
        'BodyCell',
        fontName='Helvetica',
        fontSize=8.5,
        textColor=colors.HexColor('#1B2A38'),
        alignment=0,
    )

    cell_body_right = ParagraphStyle(
        'BodyCellRight',
        fontName='Helvetica',
        fontSize=8.5,
        textColor=colors.HexColor('#1B2A38'),
        alignment=2,
    )

    cell_total_style = ParagraphStyle(
        'TotalCell',
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#1B2A38'),
        alignment=2,
    )

    # 1. Encabezado del reporte
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph("Reporte Resumen por Artículo", title_style))
    story.append(Paragraph(f"Filtros aplicados: {filtros_info} | Generado el: {fecha_emision}", subtitle_style))
    story.append(Spacer(1, 8))

    # 2. Construcción de la tabla
    headers = [
        Paragraph("Código Artículo", cell_header_style),
        Paragraph("Descripción del Artículo", cell_header_style),
        Paragraph("Cantidad Total", cell_header_style),
        Paragraph("Cant. Atendida", cell_header_style),
        Paragraph("Cant. Pendiente", cell_header_style),
    ]

    table_data = [headers]

    for _, row in df_resumen.iterrows():
        table_data.append([
            Paragraph(str(row["Número de artículo"]), cell_body_style),
            Paragraph(str(row["Descripción del artículo"]), cell_body_style),
            Paragraph(f"{row['Cantidad']:,.2f}", cell_body_right),
            Paragraph(f"{row['CantidadAtendida']:,.2f}", cell_body_right),
            Paragraph(f"{row['CantidadPendiente']:,.2f}", cell_body_right),
        ])

    # Fila de totales
    tot_cant = df_resumen["Cantidad"].sum()
    tot_atend = df_resumen["CantidadAtendida"].sum()
    tot_pend = df_resumen["CantidadPendiente"].sum()

    table_data.append([
        Paragraph("<b>TOTALES GENERALES</b>", cell_body_style),
        Paragraph("", cell_body_style),
        Paragraph(f"{tot_cant:,.2f}", cell_total_style),
        Paragraph(f"{tot_atend:,.2f}", cell_total_style),
        Paragraph(f"{tot_pend:,.2f}", cell_total_style),
    ])

    # Anchos de columnas
    col_widths = [3.5 * cm, 12 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Estilos visuales de la tabla
    ts = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B2A38')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#E2E8F0')),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#1B2A38')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EDF2F7')),
    ])
    table.setStyle(ts)
    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer


# --------------------------------------------------------------------------
# Carga de datos desde Google Sheets con manejo de excepciones
# --------------------------------------------------------------------------
REQUIRED_COLS = [
    "Número de documento",
    "Status de documento",
    "Fecha de vencimiento",
    "Número de artículo",
    "Descripción del artículo",
    "Cantidad",
    "De código de almacén",
    "Código de almacén",
    "CantidadAtendida",
    "CantidadPendiente",
]


@st.cache_data(ttl=300, show_spinner="Cargando datos desde Google Sheets…")
def load_data() -> pd.DataFrame:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=300)
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets. Revisa la configuración de `secrets.toml`: {e}")
        st.stop()

    df = df.dropna(how="all")
    faltantes = [c for c in REQUIRED_COLS if c not in df.columns]
    if faltantes:
        st.error(
            "Faltan columnas en la hoja de cálculo: "
            + ", ".join(faltantes)
            + ". Revisa que los encabezados coincidan exactamente."
        )
        st.stop()

    df["Fecha de vencimiento"] = pd.to_datetime(
        df["Fecha de vencimiento"], errors="coerce"
    ).dt.date
    for col in ["Cantidad", "CantidadAtendida", "CantidadPendiente"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["De código de almacén"] = df["De código de almacén"].astype(str).str.strip()
    df["Código de almacén"] = df["Código de almacén"].astype(str).str.strip()
    df["Status de documento"] = df["Status de documento"].astype(str).str.strip()
    df["Número de documento"] = df["Número de documento"].astype(str).str.strip()
    df["Número de artículo"] = df["Número de artículo"].astype(str).str.strip()
    df["Descripción del artículo"] = df["Descripción del artículo"].astype(str).str.strip()

    # Filtro de negocio: excluir registros Status C con pendiente > 0 y nada atendido
    excluir = (
        (df["Status de documento"] == "C")
        & (df["CantidadPendiente"] > 0)
        & (df["CantidadAtendida"] == 0)
    )
    df = df[~excluir]
    return df


df = load_data()

if df.empty:
    st.warning("No quedaron registros tras excluir Status C con pendiente > 0 y atendida = 0.")
    st.stop()

# --------------------------------------------------------------------------
# Encabezado
# --------------------------------------------------------------------------
st.markdown(
    '<div class="app-header">📦<h1>Documentos pendientes de atención</h1></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="app-subtitle">Filtra por fecha, almacén, documento o artículo para evaluar saldos pendientes.</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Filtros Fila 1: Fecha -> De código de almacén -> Código de almacén (con opción TODOS)
# --------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

fechas_disponibles = ["TODOS"] + sorted(df["Fecha de vencimiento"].dropna().unique())

with col1:
    fecha_sel = st.selectbox(
        "Fecha de vencimiento",
        options=fechas_disponibles,
        format_func=lambda d: "TODOS" if d == "TODOS" else d.strftime("%d/%m/%Y"),
    )

df_fecha = df if fecha_sel == "TODOS" else df[df["Fecha de vencimiento"] == fecha_sel]

with col2:
    de_almacenes = ["TODOS"] + sorted(df_fecha["De código de almacén"].dropna().unique())
    de_almacen_sel = st.selectbox("De código de almacén", options=de_almacenes)

df_de_almacen = df_fecha if de_almacen_sel == "TODOS" else df_fecha[df_fecha["De código de almacén"] == de_almacen_sel]

with col3:
    almacenes = ["TODOS"] + sorted(df_de_almacen["Código de almacén"].dropna().unique())
    almacen_sel = st.selectbox("Código de almacén", options=almacenes)

df_almacen = df_de_almacen if almacen_sel == "TODOS" else df_de_almacen[df_de_almacen["Código de almacén"] == almacen_sel]

# --------------------------------------------------------------------------
# Filtros Fila 2: Búsqueda avanzada por Documento, Código y Descripción
# --------------------------------------------------------------------------
col4, col5, col6 = st.columns(3)

with col4:
    doc_sel = st.text_input("Número de documento", value="", placeholder="Ej: 105423")

with col5:
    art_sel = st.text_input("Número de artículo", value="", placeholder="Ej: M6020039")

with col6:
    desc_sel = st.text_input("Descripción del artículo", value="", placeholder="Ej: ALFAJOR")

# Aplicar filtros de texto opcionales
df_sel = df_almacen.copy()

if doc_sel.strip():
    df_sel = df_sel[df_sel["Número de documento"].str.contains(doc_sel.strip(), case=False, na=False)]

if art_sel.strip():
    df_sel = df_sel[df_sel["Número de artículo"].str.contains(art_sel.strip(), case=False, na=False)]

if desc_sel.strip():
    df_sel = df_sel[df_sel["Descripción del artículo"].str.contains(desc_sel.strip(), case=False, na=False)]

# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------
n_documentos = df_sel["Número de documento"].nunique()
n_articulos = df_sel["Número de artículo"].nunique()
cantidad_total = df_sel["Cantidad"].sum()
cantidad_pendiente_total = df_sel["CantidadPendiente"].sum()

st.markdown(
    f"""
    <div class="metric-row">
        <div class="metric-card metric-docs">
            <div class="metric-value">{n_documentos:,}</div>
            <div class="metric-label">Documentos</div>
        </div>
        <div class="metric-card metric-items">
            <div class="metric-value">{n_articulos:,}</div>
            <div class="metric-label">Artículos distintos</div>
        </div>
        <div class="metric-card metric-qty">
            <div class="metric-value">{cantidad_total:,.2f}</div>
            <div class="metric-label">Cantidad total</div>
        </div>
        <div class="metric-card metric-pend">
            <div class="metric-value">{cantidad_pendiente_total:,.2f}</div>
            <div class="metric-label">Cantidad pendiente total</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Tabla de detalle
# --------------------------------------------------------------------------
st.markdown('<div class="section-title">Detalle</div>', unsafe_allow_html=True)

tabla_cols = [
    "Número de documento",
    "Fecha de vencimiento",
    "Número de artículo",
    "Descripción del artículo",
    "Cantidad",
    "CantidadAtendida",
    "CantidadPendiente",
]

st.dataframe(
    df_sel[tabla_cols].sort_values("Número de documento"),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Fecha de vencimiento": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Cantidad": st.column_config.NumberColumn(format="%.2f"),
        "CantidadAtendida": st.column_config.NumberColumn(format="%.2f"),
        "CantidadPendiente": st.column_config.NumberColumn(format="%.2f"),
    },
)

# --------------------------------------------------------------------------
# Resumen agrupado (sin Número de documento)
# --------------------------------------------------------------------------
st.markdown('<div class="section-title">Resumen por artículo</div>', unsafe_allow_html=True)

resumen = (
    df_sel.groupby(["Número de artículo", "Descripción del artículo"], as_index=False)
    .agg(
        Cantidad=("Cantidad", "sum"),
        CantidadAtendida=("CantidadAtendida", "sum"),
        CantidadPendiente=("CantidadPendiente", "sum"),
    )
    .sort_values("CantidadPendiente", ascending=False)
)

st.dataframe(
    resumen,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Cantidad": st.column_config.NumberColumn(format="%.2f"),
        "CantidadAtendida": st.column_config.NumberColumn(format="%.2f"),
        "CantidadPendiente": st.column_config.NumberColumn(format="%.2f"),
    },
)

# --------------------------------------------------------------------------
# Exportar Resumen a PDF
# --------------------------------------------------------------------------
if not resumen.empty:
    fecha_txt = fecha_sel.strftime("%d/%m/%Y") if fecha_sel != "TODOS" else "TODAS"
    filtros_str = f"Fecha: {fecha_txt} | De: {de_almacen_sel} | A: {almacen_sel}"

    pdf_bytes = generar_pdf_resumen(resumen, filtros_str)

    col_pdf, _ = st.columns([1, 3])
    with col_pdf:
        st.download_button(
            label="📄 Exportar Resumen a PDF",
            data=pdf_bytes,
            file_name=f"resumen_articulos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
