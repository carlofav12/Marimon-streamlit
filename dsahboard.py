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

    st.markdown("## 📈 Gráfico De Líneas: Evolución de Ventas Quincenal")
    df['quincena'] = df['fecha_emision'].apply(lambda x: f"{x.strftime('%b %Y')} Q1" if x.day <=15 else f"{x.strftime('%b %Y')} Q2")
    ventas_q = df.groupby('quincena').agg({'total_venta': 'sum'}).reset_index()
    fig_l = go.Figure()
    fig_l.add_trace(go.Scatter(
        x=ventas_q['quincena'],
        y=ventas_q['total_venta'],
        mode='lines+markers+text',
        text=[f"S/ {v:,.0f}" for v in ventas_q['total_venta']],
        textposition="top center",
        line=dict(color='#DC143C', width=3),
        marker=dict(size=10)
    ))
    fig_l.update_layout(title="Ventas Totales por Quincena", xaxis_title="Mes y Quincena", yaxis_title="Total Ventas (S/)")
    st.plotly_chart(fig_l, use_container_width=True)

    st.markdown("## 🍩 Gráfico Circular: Participación por Categoría")
    ventas_cat = df.groupby('categoria_nombre')['total_venta'].sum().reset_index()
    ventas_cat['Porcentaje'] = (ventas_cat['total_venta']/ventas_cat['total_venta'].sum()*100).round(2)
    pie = go.Figure(go.Pie(
        labels=ventas_cat['categoria_nombre'],
        values=ventas_cat['total_venta'],
        hole=0.4,
        textinfo='label+percent',
        textfont=dict(size=14, family='Arial'),
        marker=dict(colors=['#DC143C', '#8B0000', '#555', '#999','#bdbdbd'])
    ))
    pie.update_layout(title="Distribución de Ventas por Categoría")
    st.plotly_chart(pie, use_container_width=True)

    st.markdown("## 🗃️ Tabla Dinámica: Ventas por Producto")
    tabla = df.groupby(['nombre','categoria_nombre']).agg({'cantidad':'sum','total_venta':'sum'}).reset_index()
    tabla['total_venta'] = tabla['total_venta'].apply(lambda x: f"S/ {x:,.2f}")
    st.dataframe(tabla, use_container_width=True)
else:
    st.warning("No hay datos para mostrar")
