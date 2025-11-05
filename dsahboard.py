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
    categoria_opts = sorted(df['categoria_nombre'].dropna().unique())
    producto_opts = sorted(df['nombre'].dropna().unique())
    categorias_sel = st.sidebar.multiselect("Categoría", categoria_opts, default=categoria_opts)
    productos_sel = st.sidebar.multiselect("Producto", producto_opts, default=None)

    # FILTRADO
    df = df[df['categoria_nombre'].isin(categorias_sel)]
    if productos_sel:
        df = df[df['nombre'].isin(productos_sel)]

    # CSS personalizado para botones estilo móvil
    st.markdown("""
    <style>
    div.stButton > button {
        width: 100%;
        background-color: white;
        color: #DC143C;
        border: 2px solid #DC143C;
        border-radius: 20px;
        padding: 10px 20px;
        font-weight: bold;
        margin: 5px 0;
    }
    div.stButton > button:hover {
        background-color: #DC143C;
        color: white;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #DC143C;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # Preparar datos
    df['quincena'] = df['fecha_emision'].apply(lambda x: f"{x.strftime('%b %Y')} Q1" if x.day <=15 else f"{x.strftime('%b %Y')} Q2")
    ventas_q = df.groupby('quincena').agg({'total_venta': 'sum'}).reset_index()
    ventas_cat = df.groupby('categoria_nombre')['total_venta'].sum().reset_index()
    ventas_cat['Porcentaje'] = (ventas_cat['total_venta']/ventas_cat['total_venta'].sum()*100).round(2)

    # Métricas superiores
    col1, col2 = st.columns(2)
    with col1:
        total_ventas = df['total_venta'].sum()
        st.markdown(f"""
        <div class="metric-card">
            <h4 style='margin:0; color:#666'>VENTAS TOTAL</h4>
            <h2 style='margin:5px 0; color:#DC143C'>S/ {total_ventas:,.0f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_productos = df['cantidad'].sum()
        st.markdown(f"""
        <div class="metric-card">
            <h4 style='margin:0; color:#666'>PRODUCTOS VENDIDOS</h4>
            <h2 style='margin:5px 0; color:#DC143C'>{total_productos:,.0f}</h2>
        </div>
        """, unsafe_allow_html=True)

    # Botones de navegación entre vistas
    st.markdown("### Selecciona Vista:")
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("📊 Gráfico De Barras", key="btn_barras"):
            st.session_state.vista_actual = "barras"
    
    with col_btn2:
        if st.button("🍩 Gráfico Circular", key="btn_circular"):
            st.session_state.vista_actual = "circular"
    
    with col_btn3:
        if st.button("📋 Tabla Dinámica", key="btn_tabla"):
            st.session_state.vista_actual = "tabla"

    # Inicializar vista por defecto
    if 'vista_actual' not in st.session_state:
        st.session_state.vista_actual = "barras"

    st.markdown("---")

    # VISTA DE GRÁFICO DE BARRAS
    if st.session_state.vista_actual == "barras":
        st.markdown("## 📊 VENTAS POR MES")
        
        # Crear gráfico de barras
        df['mes'] = df['fecha_emision'].dt.strftime('%b')
        ventas_mes = df.groupby('mes')['total_venta'].sum().reset_index()
        
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=ventas_mes['mes'],
            y=ventas_mes['total_venta'],
            text=[f"S/ {v:,.0f}" for v in ventas_mes['total_venta']],
            textposition='outside',
            marker=dict(color='#DC143C'),
            hovertemplate='<b>%{x}</b><br>Ventas: S/ %{y:,.0f}<extra></extra>'
        ))
        
        fig_bar.update_layout(
            height=400,
            showlegend=False,
            xaxis_title="",
            yaxis_title="Ventas (S/)",
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=20, b=40, l=40, r=20),
            font=dict(size=12)
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)
        
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

else:
    st.warning("No hay datos para mostrar")
