import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from supabase import create_client

# ============================================================
# CREDENCIALES SUPABASE desde variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

st.set_page_config(page_title="Dashboard Ventas - Marimon", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error("No se han configurado las variables de entorno SUPABASE_URL y SUPABASE_ANON_KEY.")
        st.stop()
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return client

supabase = init_supabase()

@st.cache_data(ttl=300)
def load_transacciones():
    tquery = supabase.table("transacciones").select(
        "id, fecha_emision, cantidad, precio, producto_id, empleado_id"
    ).eq("activo", True).execute()
    df = pd.DataFrame(tquery.data)
    df['fecha_emision'] = pd.to_datetime(df['fecha_emision'])
    df['total_venta'] = df['precio'] * df['cantidad']
    return df

@st.cache_data(ttl=300)
def load_productos_categorias():
    pquery = supabase.table("productos").select("id, nombre, categoria_id").execute()
    cquery = supabase.table("categorias").select("id, nombre").execute()
    dfp = pd.DataFrame(pquery.data)
    dfc = pd.DataFrame(cquery.data)
    dfp = dfp.merge(dfc, how='left', left_on='categoria_id', right_on='id', suffixes=('', '_categoria'))
    dfp['categoria_nombre'] = dfp['nombre_categoria'].fillna('Sin categoría')
    return dfp[['id', 'nombre', 'categoria_nombre']]

# Cargar datos
trans = load_transacciones()
prod_cat = load_productos_categorias()
df = trans.merge(prod_cat, left_on='producto_id', right_on='id', how='left')

st.markdown("<h1 style='color:#DC143C'>📊 Reporte de Ventas - Marimon</h1>", unsafe_allow_html=True)

# FILTROS
if not df.empty:
    # CSS personalizado para botones estilo móvil
    st.markdown("""
    <style>
    div.stButton > button {
        width: 100%;
        background-color: white;
        color: #DC143C;
        border: 2px solid #DC143C;
        border-radius: 25px;
        padding: 12px 20px;
        font-weight: bold;
        margin: 5px 0;
        font-size: 14px;
    }
    div.stButton > button:hover {
        background-color: #DC143C;
        color: white;
    }
    /* Ocultar el expand del sidebar en móvil */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    /* Estilo para selectbox */
    div[data-baseweb="select"] > div {
        border-radius: 10px;
        border-color: #DC143C;
    }
    </style>
    """, unsafe_allow_html=True)

    # Filtros en el sidebar con búsqueda
    st.sidebar.markdown("### 🔍 Filtros")
    
    # Filtro de rango de fechas
    fecha_min = df['fecha_emision'].min().date()
    fecha_max = df['fecha_emision'].max().date()
    
    col_fecha1, col_fecha2 = st.sidebar.columns(2)
    with col_fecha1:
        fecha_inicio = st.date_input("Desde", value=fecha_min, min_value=fecha_min, max_value=fecha_max)
    with col_fecha2:
        fecha_fin = st.date_input("Hasta", value=fecha_max, min_value=fecha_min, max_value=fecha_max)
    
    categoria_opts = ['Todas'] + sorted(df['categoria_nombre'].dropna().unique().tolist())
    categoria_sel = st.sidebar.selectbox(
        "Categoría",
        options=categoria_opts,
        index=0
    )
    
    # Filtro de producto con búsqueda (selectbox permite escribir)
    producto_opts = ['Todos'] + sorted(df['nombre'].dropna().unique().tolist())
    producto_sel = st.sidebar.selectbox(
        "Buscar Producto",
        options=producto_opts,
        index=0,
        help="Escribe para buscar un producto específico"
    )

    # Aplicar filtros
    df = df[(df['fecha_emision'].dt.date >= fecha_inicio) & (df['fecha_emision'].dt.date <= fecha_fin)]
    
    if categoria_sel != 'Todas':
        df = df[df['categoria_nombre'] == categoria_sel]
    
    if producto_sel != 'Todos':
        df = df[df['nombre'] == producto_sel]
    
    # Validar que existan datos con los filtros seleccionados
    if df.empty:
        st.warning("⚠️ No hay datos con las combinaciones de filtros seleccionadas. Por favor, ajusta los filtros.")
        st.stop()

    # Preparar datos
    df['quincena'] = df['fecha_emision'].apply(lambda x: f"{x.strftime('%b %Y')} Q1" if x.day <=15 else f"{x.strftime('%b %Y')} Q2")
    ventas_q = df.groupby('quincena').agg({'total_venta': 'sum'}).reset_index()
    ventas_cat = df.groupby('categoria_nombre')['total_venta'].sum().reset_index()
    ventas_cat['Porcentaje'] = (ventas_cat['total_venta']/ventas_cat['total_venta'].sum()*100).round(2)

    # Botones de navegación entre vistas
    st.markdown("### Selecciona Vista:")
    
    # Inicializar vista por defecto
    if 'vista_actual' not in st.session_state:
        st.session_state.vista_actual = "barras"
    
    # Crear 3 columnas para botones horizontales
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("📊 Gráfico De Líneas", key="btn_barras", use_container_width=True):
            st.session_state.vista_actual = "barras"
    
    with col_btn2:
        if st.button("🍩 Gráfico Circular", key="btn_circular", use_container_width=True):
            st.session_state.vista_actual = "circular"
    
    with col_btn3:
        if st.button("📋 Tabla Dinámica", key="btn_tabla", use_container_width=True):
            st.session_state.vista_actual = "tabla"

    st.markdown("---")

    # VISTA DE GRÁFICO DE LÍNEAS
    if st.session_state.vista_actual == "barras":
        st.markdown("## 📊 EVOLUCIÓN DE VENTAS - ACUMULADO MES A MES")
        
        # Crear gráfico de líneas acumuladas por mes
        df_sorted = df.sort_values('fecha_emision')
        df_sorted['mes'] = df_sorted['fecha_emision'].dt.to_period('M')
        ventas_mes = df_sorted.groupby('mes')['total_venta'].sum().reset_index()
        ventas_mes['ventas_acumuladas'] = ventas_mes['total_venta'].cumsum()
        ventas_mes['mes_str'] = ventas_mes['mes'].astype(str)
        
        fig_line = go.Figure()
        
        # Línea de ventas acumuladas
        fig_line.add_trace(go.Scatter(
            x=ventas_mes['mes_str'],
            y=ventas_mes['ventas_acumuladas'],
            mode='lines+markers+text',
            name='Ventas Acumuladas',
            text=[f"S/ {v:,.0f}" for v in ventas_mes['ventas_acumuladas']],
            textposition="top center",
            line=dict(color='#DC143C', width=3),
            marker=dict(size=10, color='#DC143C'),
            hovertemplate='<b>%{x}</b><br>Ventas Acumuladas: S/ %{y:,.0f}<extra></extra>'
        ))
        
        fig_line.update_layout(
            height=400,
            showlegend=True,
            xaxis_title="Mes",
            yaxis_title="Ventas Acumuladas (S/)",
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=20, b=40, l=40, r=20),
            font=dict(size=12),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_line, use_container_width=True)
        
        # Gráfico de dona de ingresos por trimestre
        st.markdown("### 📊 INGRESOS POR TRIMESTRE")
        df['trimestre'] = df['fecha_emision'].dt.quarter
        trimestre_map = {1: 'PRIMER TRIMESTRE', 2: 'SEGUNDO TRIMESTRE', 3: 'TERCER TRIMESTRE', 4: 'CUARTO TRIMESTRE'}
        df['trimestre_nombre'] = df['trimestre'].map(trimestre_map)
        ventas_trim = df.groupby('trimestre_nombre')['total_venta'].sum().reset_index()
        
        if not ventas_trim.empty:
            fig_dona_trim = go.Figure(go.Pie(
                labels=ventas_trim['trimestre_nombre'],
                values=ventas_trim['total_venta'],
                hole=0.5,
                textinfo='label+percent',
                textfont=dict(size=11),
                marker=dict(colors=['#DC143C', '#333333', '#8B0000', '#999999'])
            ))
            
            fig_dona_trim.update_layout(
                height=350,
                showlegend=True,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05),
                margin=dict(t=20, b=20, l=20, r=120)
            )
            
            st.plotly_chart(fig_dona_trim, use_container_width=True)

    # VISTA DE GRÁFICO CIRCULAR
    elif st.session_state.vista_actual == "circular":
        st.markdown("## 🍩 VENTAS POR PRODUCTO")
        
        # Ventas por producto individual
        ventas_prod = df.groupby('nombre')['total_venta'].sum().reset_index().nlargest(5, 'total_venta')
        
        fig_prod = go.Figure(go.Pie(
            labels=ventas_prod['nombre'],
            values=ventas_prod['total_venta'],
            hole=0.5,
            textinfo='label+percent',
            textfont=dict(size=12),
            marker=dict(colors=['#DC143C', '#333333', '#8B0000', '#999999', '#CCCCCC'])
        ))
        
        fig_prod.update_layout(
            height=400,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            margin=dict(t=20, b=80, l=20, r=20)
        )
        
        st.plotly_chart(fig_prod, use_container_width=True)
        
        # Gráfico de dona de ingresos por trimestre
        st.markdown("### INGRESOS POR TRIMESTRE")
        df['trimestre'] = df['fecha_emision'].dt.quarter
        trimestre_map = {1: 'PRIMER TRIMESTRE', 2: 'SEGUNDO TRIMESTRE', 3: 'TERCER TRIMESTRE', 4: 'CUARTO TRIMESTRE'}
        df['trimestre_nombre'] = df['trimestre'].map(trimestre_map)
        ventas_trim = df.groupby('trimestre_nombre')['total_venta'].sum().reset_index()
        
        fig_dona_trim = go.Figure(go.Pie(
            labels=ventas_trim['trimestre_nombre'],
            values=ventas_trim['total_venta'],
            hole=0.5,
            textinfo='label+percent',
            textfont=dict(size=11),
            marker=dict(colors=['#DC143C', '#333333', '#8B0000', '#999999'])
        ))
        
        fig_dona_trim.update_layout(
            height=350,
            showlegend=True,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05),
            margin=dict(t=20, b=20, l=20, r=120)
        )
        
        st.plotly_chart(fig_dona_trim, use_container_width=True)

    # VISTA DE TABLA DINÁMICA
    elif st.session_state.vista_actual == "tabla":
        st.markdown("## 📋 TABLA DINÁMICA")
        
        tabla = df.groupby(['nombre','categoria_nombre']).agg({
            'cantidad':'sum',
            'total_venta':'sum',
            'fecha_emision': 'max'
        }).reset_index()
        
        tabla = tabla.rename(columns={
            'nombre': 'Producto',
            'categoria_nombre': 'Categoría',
            'cantidad': 'Cantidad',
            'total_venta': 'Total',
            'fecha_emision': 'Última Venta'
        })
        
        tabla['Total'] = tabla['Total'].apply(lambda x: f"S/ {x:,.2f}")
        tabla['Última Venta'] = tabla['Última Venta'].dt.strftime('%d-%b-%Y')
        tabla = tabla.sort_values('Cantidad', ascending=False)
        
        st.dataframe(
            tabla,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Producto": st.column_config.TextColumn("Producto", width="medium"),
                "Categoría": st.column_config.TextColumn("Categoría", width="small"),
                "Cantidad": st.column_config.NumberColumn("Qty", width="small"),
                "Total": st.column_config.TextColumn("Precio", width="medium"),
                "Última Venta": st.column_config.TextColumn("Fecha", width="medium")
            }
        )
        
        st.markdown(f"**Total de registros:** {len(tabla)}")

    # Botón para ver dashboard completo en Power BI
    st.markdown("---")
    st.markdown("### 📊 ¿Necesitas más información?")
    
    powerbi_url = "https://app.powerbi.com/view?r=eyJrIjoiNDYxODJhZDYtMTBjZC00ZjhiLTgzMWQtMjhlMzIwODZjNDY1IiwidCI6Ijk4MjAxZmVmLWQ5ZjYtNGU2OC04NGY1LWMyNzA1MDc0ZTM0MiIsImMiOjR9"
    
    st.markdown(f"""
    <div style="text-align: center; margin: 20px 0;">
        <a href="{powerbi_url}" target="_blank" style="text-decoration: none;">
            <button style="
                background-color: #DC143C;
                color: white;
                padding: 15px 40px;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                transition: all 0.3s;
            ">
                🔍 Ver Dashboard Completo en Power BI
            </button>
        </a>
    </div>
    """, unsafe_allow_html=True)

else:
    st.warning("No hay datos para mostrar")
