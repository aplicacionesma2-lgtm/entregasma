"""
Panel de Registro de Entrega de Productos Terminados
------------------------------------------------------
Lee los registros desde Google Sheets y permite exportar un PDF
con la cantidad total por artículo agrupada por cada día del rango.
"""

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from streamlit_gsheets import GSheetsConnection

# --------------------------------------------------------------------------
# Configuración general de la página
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Entrega de Productos Terminados",
    page_icon="📦",
    layout="wide",
)

# --------------------------------------------------------------------------
# Estilos CSS
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
        color: #1B2B85;
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
# Función PDF con pivote por Fecha (Horizontal / Landscape)
# --------------------------------------------------------------------------
def generar_pdf_resumen_por_fecha(df_pivote: pd.DataFrame, filtros_info: str) -> BytesIO:
    buffer = BytesIO()
    # Usamos Landscape (Horizontal) para acomodar múltiples fechas
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.8 * cm,
        leftMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
    )

    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#1B2B85'),
        spaceAfter=2,
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#5A6B7A'),
        spaceAfter=6,
    )

    cell_header_style = ParagraphStyle(
        'HeaderCell',
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=colors.white,
        alignment=1, # Centrado
    )

    cell_header_left = ParagraphStyle(
        'HeaderCellLeft',
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=colors.white,
        alignment=0, # Izquierda
    )

    cell_body_left = ParagraphStyle(
        'BodyCellLeft',
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#1B2A38'),
        alignment=0,
    )

    cell_body_center = ParagraphStyle(
        'BodyCellCenter',
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#1B2A38'),
        alignment=1,
    )

    # Encabezado
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph("Resumen de Entregas por Artículo y Día", title_style))
    story.append(Paragraph(f"Filtros: {filtros_info} | Generado el: {fecha_emision}", subtitle_style))
    story.append(Spacer(1, 4))

    # Construcción de encabezados dinámicos
    columnas = list(df_pivote.columns)
    headers = []
    
    for col in columnas:
        if col in ["Número de artículo", "Descripción del artículo"]:
            headers.append(Paragraph(col, cell_header_left))
        else:
            headers.append(Paragraph(str(col), cell_header_style))

    table_data = [headers]

    for _, row in df_pivote.iterrows():
        fila = []
        for col in columnas:
            val = row[col]
            if col == "Número de artículo":
                fila.append(Paragraph(str(val), cell_body_left))
            elif col == "Descripción del artículo":
                fila.append(Paragraph(str(val), cell_body_left))
            else:
                txt_val = f"{val:,.0f}" if val > 0 else "-"
                fila.append(Paragraph(txt_val, cell_body_center))
        table_data.append(fila)

    # Anchos de columna dinámicos
    num_fechas = len(columnas) - 2
    ancho_disponible = 26.3 * cm # Ancho imprimible landscape
    ancho_codigo = 2.8 * cm
    ancho_desc = 7.5 * cm
    
    if num_fechas > 0:
        ancho_fecha = min(2.5 * cm, (ancho_disponible - ancho_codigo - ancho_desc) / num_fechas)
    else:
        ancho_fecha = 2.0 * cm

    col_widths = [ancho_codigo, ancho_desc] + [ancho_fecha] * num_fechas

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    ts = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B2B85')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ])
    table.setStyle(ts)
    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer


# --------------------------------------------------------------------------
# Carga de datos desde Google Sheets
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
        st.error(f"Error al conectar con Google Sheets: {e}")
        st.stop()

    df = df.dropna(how="all")
    faltantes = [c for c in REQUIRED_COLS if c not in df.columns]
    if faltantes:
        st.error("Faltan columnas en la hoja de cálculo: " + ", ".join(faltantes))
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

    excluir = (
        (df["Status de documento"] == "C")
        & (df["CantidadPendiente"] > 0)
        & (df["CantidadAtendida"] == 0)
    )
    df = df[~excluir]
    return df


df = load_data()

if df.empty:
    st.warning("No quedaron registros disponibles.")
    st.stop()

# --------------------------------------------------------------------------
# Encabezado
# --------------------------------------------------------------------------
st.markdown(
    '<div class="app-header">📦<h1>Registro de Entrega de Productos Terminados</h1></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="app-subtitle">Filtra por fecha, almacén, orden de fabricación o artículo para visualizar registros.</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Filtros Fila 1
# --------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

fechas_validas = df["Fecha de vencimiento"].dropna()
min_fecha = fechas_validas.min()
max_fecha = fechas_validas.max()

with col1:
    rango_fechas = st.date_input(
        "Fecha de vencimiento",
        value=(min_fecha, max_fecha),
        min_value=min_fecha,
        max_value=max_fecha,
        format="DD/MM/YYYY",
    )

if isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 2:
    f_inicio, f_fin = rango_fechas
    df_fecha = df[(df["Fecha de vencimiento"] >= f_inicio) & (df["Fecha de vencimiento"] <= f_fin)]
elif isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 1:
    df_fecha = df[df["Fecha de vencimiento"] == rango_fechas[0]]
else:
    df_fecha = df.copy()

with col2:
    de_almacenes = ["TODOS"] + sorted(df_fecha["De código de almacén"].dropna().unique())
    de_almacen_sel = st.selectbox("De código de almacén", options=de_almacenes)

df_de_almacen = df_fecha if de_almacen_sel == "TODOS" else df_fecha[df_fecha["De código de almacén"] == de_almacen_sel]

with col3:
    almacenes = ["TODOS"] + sorted(df_de_almacen["Código de almacén"].dropna().unique())
    almacen_sel = st.selectbox("Código de almacén", options=almacenes)

df_almacen = df_de_almacen if almacen_sel == "TODOS" else df_de_almacen[df_de_almacen["Código de almacén"] == almacen_sel]

# --------------------------------------------------------------------------
# Filtros Fila 2
# --------------------------------------------------------------------------
col4, col5, col6 = st.columns(3)

with col4:
    doc_sel = st.text_input("Número de documento", value="", placeholder="Ej: 105423")

with col5:
    art_sel = st.text_input("Número de artículo", value="", placeholder="Ej: M6020039")

with col6:
    desc_sel = st.text_input("Descripción del artículo", value="", placeholder="Ej: ALFAJOR")

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
# Tabla de Detalle
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
# Resumen agrupado por Día (Pivote)
# --------------------------------------------------------------------------
st.markdown('<div class="section-title">Resumen de Cantidad por Día y Artículo</div>', unsafe_allow_html=True)

if not df_sel.empty:
    # Formatear la fecha a String DD/MM/YYYY para las columnas del pivote
    df_piv = df_sel.copy()
    df_piv["Fecha_Str"] = pd.to_datetime(df_piv["Fecha de vencimiento"]).dt.strftime("%d/%m/%Y")

    pivote = pd.pivot_table(
        df_piv,
        values="Cantidad",
        index=["Número de artículo", "Descripción del artículo"],
        columns="Fecha_Str",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    st.dataframe(
        pivote,
        use_container_width=True,
        hide_index=True,
    )

    # Exportar Resumen Diario a PDF
    if isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 2:
        fecha_txt = f"{rango_fechas[0].strftime('%d/%m/%Y')} a {rango_fechas[1].strftime('%d/%m/%Y')}"
    elif isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 1:
        fecha_txt = rango_fechas[0].strftime("%d/%m/%Y")
    else:
        fecha_txt = "TODAS"

    filtros_str = f"Fecha: {fecha_txt} | De: {de_almacen_sel} | A: {almacen_sel}"

    pdf_bytes = generar_pdf_resumen_por_fecha(pivote, filtros_str)

    col_pdf, _ = st.columns([1, 3])
    with col_pdf:
        st.download_button(
            label="📄 Exportar Resumen por Día a PDF",
            data=pdf_bytes,
            file_name=f"resumen_diario_articulos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
