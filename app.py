"""
Panel de Registro de Entrega de Productos Terminados & KPIs
------------------------------------------------------------
Lee los registros desde Google Sheets mediante gspread nativo, gestiona
la exploración de entregas, exportación a PDF por fecha y un Dashboard
de Indicadores Ejecutivo con gráficos de Plotly y Curva Pareto (ABC).
"""

from datetime import datetime
from io import BytesIO

import gspread
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from google.oauth2.service_account import Credentials
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# --------------------------------------------------------------------------
# Configuración general de la página
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Entrega de Productos Terminados",
    page_icon="📦",
    layout="wide",
)

# Inicializar página actual en el estado de la sesión
if "pagina_actual" not in st.session_state:
    st.session_state.pagina_actual = "registro"

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
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
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

    /* Tarjetas KPI Especiales */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
    }
    .kpi-title {
        font-size: 0.82rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value-big {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin: 8px 0;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #3B82F6;
        font-weight: 600;
    }

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
# Función para Generar Gráfico Pareto (Curva ABC) con make_subplots
# --------------------------------------------------------------------------
def crear_grafico_pareto(df_input: pd.DataFrame):
    """
    Genera un gráfico combinado (Barras + Línea Acumulada) para la Curva Pareto ABC.
    Utiliza make_subplots para evitar incompatibilidad de tipos en update_layout.
    """
    if df_input.empty:
        return None

    df_pareto = (
        df_input.groupby("Descripción del artículo")["Cantidad"]
        .sum()
        .reset_index()
        .sort_values("Cantidad", ascending=False)
    )

    total_vol = df_pareto["Cantidad"].sum()
    if total_vol == 0:
        return None

    df_pareto["% Acumulado"] = (df_pareto["Cantidad"].cumsum() / total_vol) * 100

    # Limitar a los Top 20 SKUs para legibilidad en el eje X
    df_plot = df_pareto.head(20).copy()

    # Crear la figura con eje Y secundario explícito
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Barras de Volumen en Eje Primario
    fig.add_trace(
        go.Bar(
            x=df_plot["Descripción del artículo"],
            y=df_plot["Cantidad"],
            name="Volumen (Unidades)",
            marker_color="#1B2B85",
            hovertemplate="<b>%{x}</b><br>Volumen: %{y:,.2f}<extra></extra>",
        ),
        secondary_y=False,
    )

    # Línea de Porcentaje Acumulado en Eje Secundario
    fig.add_trace(
        go.Scatter(
            x=df_plot["Descripción del artículo"],
            y=df_plot["% Acumulado"],
            name="% Acumulado",
            mode="lines+markers",
            line=dict(color="#D97706", width=3),
            marker=dict(size=6),
            hovertemplate="<b>%{x}</b><br>Acumulado: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    # Línea de umbral del 80% (Pareto)
    fig.add_hline(
        y=80,
        line_dash="dash",
        line_color="#EF4444",
        annotation_text="Límite 80% (Pareto)",
        annotation_position="bottom right",
        secondary_y=True,
    )

    # Títulos y formato general
    fig.update_layout(
        title_text="Curva Pareto ABC (Top 20 SKUs por Volumen)",
        legend=dict(orient="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=50, b=100),
        height=420,
    )

    # Ajustes estéticos para cada eje
    fig.update_xaxes(title_text="Producto", tickangle=-45)
    fig.update_yaxes(title_text="Volumen Entregado", secondary_y=False)
    fig.update_yaxes(
        title_text="% Acumulado",
        range=[0, 105],
        showgrid=False,
        secondary_y=True,
    )

    return fig

# --------------------------------------------------------------------------
# Función PDF con pivote por Fecha (Landscape)
# --------------------------------------------------------------------------
def generar_pdf_resumen_por_fecha(df_pivote: pd.DataFrame, filtros_info: str) -> BytesIO:
    buffer = BytesIO()
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
        alignment=1,
    )

    cell_header_left = ParagraphStyle(
        'HeaderCellLeft',
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=colors.white,
        alignment=0,
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

    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph("Resumen de Entregas por Artículo y Día", title_style))
    story.append(Paragraph(f"Filtros: {filtros_info} | Generado el: {fecha_emision}", subtitle_style))
    story.append(Spacer(1, 4))

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

    num_fechas = len(columnas) - 2
    ancho_disponible = 26.3 * cm
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
# Carga NATIVA de datos con gspread
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
        sec_gsheets = st.secrets["connections"]["gsheets"]
        credentials_dict = dict(sec_gsheets)

        if "private_key" in credentials_dict:
            pk = str(credentials_dict["private_key"])
            credentials_dict["private_key"] = pk.replace("\\n", "\n")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(creds)

        spreadsheet_url = credentials_dict.get("spreadsheet")
        sh = client.open_by_url(spreadsheet_url)
        worksheet = sh.worksheet("Sheet1")

        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
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
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["De código de almacén"] = df["De código de almacén"].astype(str).str.strip()
    df["Código de almacén"] = df["Código de almacén"].astype(str).str.strip()
    df["Status de documento"] = df["Status de documento"].astype(str).str.strip()
    df["Número de documento"] = df["Número de documento"].astype(str).str.strip()
    df["Número de artículo"] = df["Número de artículo"].astype(str).str.strip()
    df["Descripción del artículo"] = df["Descripción del artículo"].astype(str).str.strip()

    if "Negocio" in df.columns:
        df["Negocio"] = df["Negocio"].astype(str).str.strip()

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

# ==========================================================================
# BARRA SUPERIOR DE NAVEGACIÓN Y TÍTULO
# ==========================================================================
col_header, col_nav = st.columns([3, 1])

with col_header:
    if st.session_state.pagina_actual == "registro":
        st.markdown(
            '<h1 style="font-size: 38px; color: #1B2B85; font-weight: 700; margin: 0;">📦 Registro de Entrega de Productos Terminados</h1>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<h1 style="font-size: 32px; color: #1B2B85; font-weight: 700; margin: 0;">📊 Dashboard de Indicadores Operativos (KPIs)</h1>',
            unsafe_allow_html=True
        )

with col_nav:
    if st.session_state.pagina_actual == "registro":
        if st.button("📊 Ver Indicadores (KPIs)", use_container_width=True, type="primary"):
            st.session_state.pagina_actual = "kpis"
            st.rerun()
    else:
        if st.button("⬅️ Volver al Registro", use_container_width=True, type="secondary"):
            st.session_state.pagina_actual = "registro"
            st.rerun()

st.divider()

# ==========================================================================
# VISTA 1: REGISTRO DE ENTREGAS Y TABLAS
# ==========================================================================
if st.session_state.pagina_actual == "registro":
    
    st.markdown(
        '<div class="app-subtitle">Filtra por fecha, almacén, negocio, orden de fabricación o artículo para visualizar registros.</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3, col_neg_reg = st.columns([2, 1.5, 1.5, 1.5])

    fechas_validas = pd.to_datetime(df["Fecha de vencimiento"].dropna())
    min_fecha = fechas_validas.min().date() if not fechas_validas.empty else datetime.now().date()
    max_fecha = fechas_validas.max().date() if not fechas_validas.empty else datetime.now().date()

    with col1:
        rango_fechas = st.date_input(
            "Fecha de vencimiento",
            value=(min_fecha, max_fecha),
            min_value=min_fecha,
            max_value=max_fecha,
            format="DD/MM/YYYY",
            key="reg_fechas"
        )

    if isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 2:
        f_inicio, f_fin = rango_fechas
        df_fecha = df[
            (pd.to_datetime(df["Fecha de vencimiento"]) >= pd.to_datetime(f_inicio)) &
            (pd.to_datetime(df["Fecha de vencimiento"]) <= pd.to_datetime(f_fin))
        ]
    elif isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 1:
        df_fecha = df[pd.to_datetime(df["Fecha de vencimiento"]) == pd.to_datetime(rango_fechas[0])]
    else:
        df_fecha = df.copy()

    with col2:
        de_almacenes = ["TODOS"] + sorted(df_fecha["De código de almacén"].dropna().unique())
        de_almacen_sel = st.selectbox("De código de almacén", options=de_almacenes, key="reg_de_alm")

    df_de_almacen = df_fecha if de_almacen_sel == "TODOS" else df_fecha[df_fecha["De código de almacén"] == de_almacen_sel]

    with col3:
        almacenes = sorted(df_de_almacen["Código de almacén"].dropna().unique())
        almacenes_sel = st.multiselect("Código de almacén (Destino)", options=almacenes, default=[], key="reg_a_alm")

    df_almacen = df_de_almacen if not almacenes_sel else df_de_almacen[df_de_almacen["Código de almacén"].isin(almacenes_sel)]

    with col_neg_reg:
        opciones_negocio_reg = ["TODOS"] + sorted([x for x in df_almacen["Negocio"].dropna().unique() if str(x) != "nan"]) if "Negocio" in df_almacen.columns else ["TODOS", "B2B", "B2C"]
        negocio_sel_reg = st.selectbox("Negocio", options=opciones_negocio_reg, key="reg_negocio")

    df_negocio_reg = df_almacen if negocio_sel_reg == "TODOS" else df_almacen[df_almacen["Negocio"] == negocio_sel_reg]

    col4, col5, col6 = st.columns(3)

    with col4:
        doc_sel = st.text_input("Número de documento", value="", placeholder="Ej: 105423")

    with col5:
        art_sel = st.text_input("Número de artículo", value="", placeholder="Ej: M6020039")

    with col6:
        desc_sel = st.text_input("Descripción del artículo", value="", placeholder="Ej: ALFAJOR")

    df_sel = df_negocio_reg.copy()

    if doc_sel.strip():
        df_sel = df_sel[df_sel["Número de documento"].str.contains(doc_sel.strip(), case=False, na=False)]

    if art_sel.strip():
        df_sel = df_sel[df_sel["Número de artículo"].str.contains(art_sel.strip(), case=False, na=False)]

    if desc_sel.strip():
        df_sel = df_sel[df_sel["Descripción del artículo"].str.contains(desc_sel.strip(), case=False, na=False)]

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

    st.markdown('<div class="section-title">Detalle</div>', unsafe_allow_html=True)
    tabla_cols = [
        "Número de documento", "Fecha de vencimiento", "Número de artículo",
        "Descripción del artículo", "Cantidad", "CantidadAtendida", "CantidadPendiente",
    ]
    if "Negocio" in df_sel.columns:
        tabla_cols.append("Negocio")

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

    st.markdown('<div class="section-title">Resumen de Cantidad por Día y Artículo</div>', unsafe_allow_html=True)

    if not df_sel.empty:
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

        st.dataframe(pivote, use_container_width=True, hide_index=True)

        if isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 2:
            fecha_txt = f"{rango_fechas[0].strftime('%d/%m/%Y')} a {rango_fechas[1].strftime('%d/%m/%Y')}"
        elif isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 1:
            fecha_txt = rango_fechas[0].strftime("%d/%m/%Y")
        else:
            fecha_txt = "TODAS"

        txt_destinos = ", ".join(almacenes_sel) if almacenes_sel else "TODOS"
        filtros_str = f"Fecha: {fecha_txt} | De: {de_almacen_sel} | A: {txt_destinos} | Negocio: {negocio_sel_reg}"
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

# ==========================================================================
# VISTA 2: DASHBOARD DE INDICADORES CON FILTROS EXTENDIDOS Y PARETO
# ==========================================================================
elif st.session_state.pagina_actual == "kpis":

    st.markdown('<div class="app-subtitle">Selecciona el rango de fechas, almacenes, negocio y artículo para consultar los indicadores.</div>', unsafe_allow_html=True)

    # FILTROS DE KPIS - FILA 1 (Fechas, Almacenes y Negocio)
    ck1, ck2, ck3, ck_neg = st.columns([2, 1.5, 1.5, 1.5])

    fechas_validas_kpi = pd.to_datetime(df["Fecha de vencimiento"].dropna())
    min_fecha_k = fechas_validas_kpi.min().date() if not fechas_validas_kpi.empty else datetime.now().date()
    max_fecha_k = fechas_validas_kpi.max().date() if not fechas_validas_kpi.empty else datetime.now().date()

    with ck1:
        rango_kpi = st.date_input(
            "Rango de Fechas (KPIs)",
            value=(min_fecha_k, max_fecha_k),
            min_value=min_fecha_k,
            max_value=max_fecha_k,
            format="DD/MM/YYYY",
            key="kpi_fechas"
        )

    if isinstance(rango_kpi, (tuple, list)) and len(rango_kpi) == 2:
        df_kpi = df[
            (pd.to_datetime(df["Fecha de vencimiento"]) >= pd.to_datetime(rango_kpi[0])) &
            (pd.to_datetime(df["Fecha de vencimiento"]) <= pd.to_datetime(rango_kpi[1]))
        ]
    elif isinstance(rango_kpi, (tuple, list)) and len(rango_kpi) == 1:
        df_kpi = df[pd.to_datetime(df["Fecha de vencimiento"]) == pd.to_datetime(rango_kpi[0])]
    else:
        df_kpi = df.copy()

    with ck2:
        de_almacenes_k = ["TODOS"] + sorted(df_kpi["De código de almacén"].dropna().unique())
        de_alm_kpi = st.selectbox("De código de almacén (Origen)", options=de_almacenes_k, key="kpi_de_alm")

    if de_alm_kpi != "TODOS":
        df_kpi = df_kpi[df_kpi["De código de almacén"] == de_alm_kpi]

    with ck3:
        almacenes_k = sorted(df_kpi["Código de almacén"].dropna().unique())
        a_alm_kpi = st.multiselect("Código de almacén (Destino)", options=almacenes_k, default=[], key="kpi_a_alm")

    if a_alm_kpi:
        df_kpi = df_kpi[df_kpi["Código de almacén"].isin(a_alm_kpi)]

    with ck_neg:
        opciones_negocio_kpi = ["TODOS"] + sorted([x for x in df_kpi["Negocio"].dropna().unique() if str(x) != "nan"]) if "Negocio" in df_kpi.columns else ["TODOS", "B2B", "B2C"]
        negocio_kpi = st.selectbox("Negocio", options=opciones_negocio_kpi, key="kpi_negocio")

    if negocio_kpi != "TODOS" and "Negocio" in df_kpi.columns:
        df_kpi = df_kpi[df_kpi["Negocio"] == negocio_kpi]

    # FILTROS DE KPIS - FILA 2 (Artículo y Descripción)
    ck4, ck5 = st.columns(2)

    with ck4:
        art_kpi = st.text_input("Código de artículo (KPIs)", value="", placeholder="Ej: M6020039", key="kpi_art")

    with ck5:
        desc_kpi = st.text_input("Descripción del artículo (KPIs)", value="", placeholder="Ej: ALFAJOR", key="kpi_desc")

    if art_kpi.strip():
        df_kpi = df_kpi[df_kpi["Número de artículo"].str.contains(art_kpi.strip(), case=False, na=False)]

    if desc_kpi.strip():
        df_kpi = df_kpi[df_kpi["Descripción del artículo"].str.contains(desc_kpi.strip(), case=False, na=False)]

    st.markdown("---")

    if df_kpi.empty:
        st.warning("No hay registros para los filtros seleccionados.")
    else:
        # -------------------------------------------------------------------------
        # CÁLCULOS PRINCIPALES Y KPIS
        # -------------------------------------------------------------------------
        total_unidades = df_kpi["Cantidad"].sum()
        total_docs = df_kpi["Número de documento"].nunique()
        total_dias_actividad = df_kpi["Fecha de vencimiento"].nunique()
        total_sku = df_kpi["Número de artículo"].nunique()

        prom_prod_por_doc = df_kpi.groupby("Número de documento")["Número de artículo"].nunique().mean() if total_docs > 0 else 0
        prom_prod_por_dia = df_kpi.groupby("Fecha de vencimiento")["Número de artículo"].nunique().mean() if total_dias_actividad > 0 else 0

        # Fill Rate
        docs_pendientes = df_kpi.groupby("Número de documento")["CantidadPendiente"].sum()
        docs_completos = (docs_pendientes == 0).sum()
        pct_fill_rate = (docs_completos / total_docs * 100) if total_docs > 0 else 0

        # Mix B2B / B2C
        if "Negocio" in df_kpi.columns and total_unidades > 0:
            vol_b2b = df_kpi[df_kpi["Negocio"] == "B2B"]["Cantidad"].sum()
            vol_b2c = df_kpi[df_kpi["Negocio"] == "B2C"]["Cantidad"].sum()
            pct_b2b = (vol_b2b / total_unidades) * 100
            pct_b2c = (vol_b2c / total_unidades) * 100
        else:
            pct_b2b, pct_b2c = 0, 0

        # Concentración Top 20% SKUs
        if total_sku > 0 and total_unidades > 0:
            top_20_count = max(1, int(total_sku * 0.20))
            vol_top_20 = (
                df_kpi.groupby("Número de artículo")["Cantidad"]
                .sum()
                .sort_values(ascending=False)
                .head(top_20_count)
                .sum()
            )
            pct_pareto = (vol_top_20 / total_unidades) * 100
        else:
            pct_pareto = 0

        # -------------------------------------------------------------------------
        # TARJETAS DE KPIS PRINCIPALES (FILA 1 Y 2)
        # -------------------------------------------------------------------------
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)

        with kpi1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Promedio Productos / Doc</div>
                    <div class="kpi-value-big">{prom_prod_por_doc:.1f}</div>
                    <div class="kpi-sub" style="color: #6366F1;">📦 Ítems distintos / Documento</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Promedio Productos / Día</div>
                    <div class="kpi-value-big">{prom_prod_por_dia:.1f}</div>
                    <div class="kpi-sub" style="color: #2563EB;">📅 Ítems distintos / Día</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Variedad de SKUs</div>
                    <div class="kpi-value-big">{total_sku:,}</div>
                    <div class="kpi-sub" style="color: #D97706;">🏷️ Catálogo Movido</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi4:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Días Operativos</div>
                    <div class="kpi-value-big">{total_dias_actividad}</div>
                    <div class="kpi-sub" style="color: #059669;">🗓️ Cobertura de Calendario</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        kpi5, kpi6, kpi7, kpi8 = st.columns(4)

        with kpi5:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Nivel de Servicio (Fill Rate)</div>
                    <div class="kpi-value-big">{pct_fill_rate:.1f}%</div>
                    <div class="kpi-sub" style="color: #059669;">✅ Docs Entregados al 100%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi6:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Participación B2B</div>
                    <div class="kpi-value-big">{pct_b2b:.1f}%</div>
                    <div class="kpi-sub" style="color: #2563EB;">🏢 Del Volumen Total</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi7:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Participación B2C</div>
                    <div class="kpi-value-big">{pct_b2c:.1f}%</div>
                    <div class="kpi-sub" style="color: #8B5CF6;">🏪 Del Volumen Total</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi8:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Concentración Top 20% SKUs</div>
                    <div class="kpi-value-big">{pct_pareto:.1f}%</div>
                    <div class="kpi-sub" style="color: #D97706;">🔥 Del Volumen en Productos Clave</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # -------------------------------------------------------------------------
        # SECCIÓN DE GRÁFICOS (VOLUMEN, TENDENCIA, MIX B2B/B2C Y PARETO)
        # -------------------------------------------------------------------------
        col_chart1, col_chart2, col_chart3 = st.columns([1.5, 1.5, 1])

        with col_chart1:
            st.markdown("### 🏆 Top 10 Productos por Volumen")
            top_productos = (
                df_kpi.groupby("Descripción del artículo")["Cantidad"]
                .sum()
                .reset_index()
                .sort_values("Cantidad", ascending=False)
                .head(10)
            )
            st.bar_chart(
                top_productos,
                x="Descripción del artículo",
                y="Cantidad",
                color="#1B2B85",
            )

        with col_chart2:
            st.markdown("### 📅 Comportamiento Diario")
            evolucion_volumen = (
                df_kpi.groupby("Fecha de vencimiento")["Cantidad"]
                .sum()
                .reset_index()
            )
            st.line_chart(
                evolucion_volumen,
                x="Fecha de vencimiento",
                y="Cantidad",
                color="#2C5F7C",
            )

        with col_chart3:
            st.markdown("### 🍩 Mix B2B vs B2C")
            if "Negocio" in df_kpi.columns and total_unidades > 0:
                df_pie = df_kpi.groupby("Negocio")["Cantidad"].sum().reset_index()
                fig_pie = px.pie(
                    df_pie,
                    values="Cantidad",
                    names="Negocio",
                    hole=0.45,
                    color="Negocio",
                    color_discrete_map={"B2B": "#2563EB", "B2C": "#8B5CF6"}
                )
                fig_pie.update_traces(textinfo="percent+label", textposition="inside")
                fig_pie.update_layout(
                    showlegend=False,
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=280
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Sin datos de Negocio")

        st.markdown("---")

        # SECCIÓN PARETO INTERACTIVO
        st.markdown("### 📈 Análisis de Concentración Pareto (Curva ABC)")
        fig_pareto = crear_grafico_pareto(df_kpi)
        if fig_pareto:
            st.plotly_chart(fig_pareto, use_container_width=True)
        else:
            st.info("Sin información para generar la curva Pareto.")

        st.markdown("---")

        # DETALLE DE PRODUCTOS ENTREGADOS
        st.markdown("### 📋 Detalle Completo de Productos Entregados (Mayor a Menor)")
        
        detalle_productos = (
            df_kpi.groupby(["Número de artículo", "Descripción del artículo"])
            .agg(
                Cantidad_Entregada=("Cantidad", "sum"),
                Documentos_Asociados=("Número de documento", "nunique")
            )
            .reset_index()
            .sort_values("Cantidad_Entregada", ascending=False)
        )

        detalle_productos["% Participación"] = (
            detalle_productos["Cantidad_Entregada"] / total_unidades * 100
        ).round(2) if total_unidades > 0 else 0

        st.dataframe(
            detalle_productos,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Número de artículo": st.column_config.TextColumn("Código Artículo"),
                "Descripción del artículo": st.column_config.TextColumn("Descripción"),
                "Cantidad_Entregada": st.column_config.NumberColumn("Cantidad Total", format="%.2f"),
                "Documentos_Asociados": st.column_config.NumberColumn("Total Docs", format="%d"),
                "% Participación": st.column_config.NumberColumn("% del Total", format="%.2f %%"),
            },
        )
