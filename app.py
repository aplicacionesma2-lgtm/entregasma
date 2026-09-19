"""
Panel de Registro de Entrega de Productos Terminados & KPIs
------------------------------------------------------------
Lee los registros desde Google Sheets, gestiona la exploración de entregas,
exportación a PDF por fecha y un Dashboard de Indicadores Ejecutivo.
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

# ==========================================================================
# BARRA SUPERIOR DE NAVEGACIÓN Y TÍTULO
# ==========================================================================
col_header, col_nav = st.columns([3, 1])

with col_header:
    if st.session_state.pagina_actual == "registro":
        st.markdown('📦 **Registro de Entrega de Productos Terminados**')
    else:
        st.markdown('📊 **Dashboard de Indicadores Operativos (KPIs)**')

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
        '<div class="app-subtitle">Filtra por fecha, almacén, orden de fabricación o artículo para visualizar registros.</div>',
        unsafe_allow_html=True,
    )

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
            key="reg_fechas"
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
        de_almacen_sel = st.selectbox("De código de almacén", options=de_almacenes, key="reg_de_alm")

    df_de_almacen = df_fecha if de_almacen_sel == "TODOS" else df_fecha[df_fecha["De código de almacén"] == de_almacen_sel]

    with col3:
        almacenes = sorted(df_de_almacen["Código de almacén"].dropna().unique())
        almacenes_sel = st.multiselect("Código de almacén (Destino)", options=almacenes, default=[], key="reg_a_alm")

    df_almacen = df_de_almacen if not almacenes_sel else df_de_almacen[df_de_almacen["Código de almacén"].isin(almacenes_sel)]

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
        filtros_str = f"Fecha: {fecha_txt} | De: {de_almacen_sel} | A: {txt_destinos}"
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
# VISTA 2: DASHBOARD DE INDICADORES CON FILTROS Y DETALLE DE PRODUCTOS
# ==========================================================================
elif st.session_state.pagina_actual == "kpis":

    st.markdown('<div class="app-subtitle">Selecciona el rango de fechas y almacenes para consultar los indicadores de flujo.</div>', unsafe_allow_html=True)

    # FILTROS EXCLUSIVOS PARA KPIS
    ck1, ck2, ck3 = st.columns(3)

    fechas_validas_kpi = df["Fecha de vencimiento"].dropna()
    min_fecha_k = fechas_validas_kpi.min()
    max_fecha_k = fechas_validas_kpi.max()

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
        df_kpi = df[(df["Fecha de vencimiento"] >= rango_kpi[0]) & (df["Fecha de vencimiento"] <= rango_kpi[1])]
    elif isinstance(rango_kpi, (tuple, list)) and len(rango_kpi) == 1:
        df_kpi = df[df["Fecha de vencimiento"] == rango_kpi[0]]
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

    st.markdown("---")

    if df_kpi.empty:
        st.warning("No hay registros para los almacenes y fechas seleccionadas.")
    else:
        # CÁLCULOS
        total_unidades = df_kpi["Cantidad"].sum()
        total_docs = df_kpi["Número de documento"].nunique()
        total_sku = df_kpi["Número de artículo"].nunique()
        total_dias_actividad = df_kpi["Fecha de vencimiento"].nunique()

        promedio_unidades_doc = total_unidades / total_docs if total_docs > 0 else 0
        promedio_diario = total_unidades / total_dias_actividad if total_dias_actividad > 0 else 0

        # TARJETAS DE KPIS PRINCIPALES
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)

        with kpi1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Promedio Unidades / Documento</div>
                    <div class="kpi-value-big">{promedio_unidades_doc:,.1f}</div>
                    <div class="kpi-sub">📦 Tamaño Promedio de Orden</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Promedio Unidades / Día</div>
                    <div class="kpi-value-big">{promedio_diario:,.0f}</div>
                    <div class="kpi-sub" style="color: #2563EB;">📅 Ritmo de Entrega Diario</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Variedad de Productos (SKUs)</div>
                    <div class="kpi-value-big">{total_sku:,}</div>
                    <div class="kpi-sub" style="color: #D97706;">🏷️ Catálogo Solicitado</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi4:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Días Operativos con Entrega</div>
                    <div class="kpi-value-big">{total_dias_actividad}</div>
                    <div class="kpi-sub" style="color: #059669;">🗓️ Cobertura de Calendario</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # GRÁFICOS
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("### 🏆 Top 10 Productos por Volumen Total")
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
            st.markdown("### 📅 Comportamiento Diario de Volumen")
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

        st.markdown("---")

        # DETALLE DE PRODUCTOS ENTREGADOS (DE MAYOR A MENOR)
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
        ).round(2)

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
