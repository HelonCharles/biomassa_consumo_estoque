import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium
import pandas as pd
import folium
from folium import Element
import json
import plotly

# 1. Configuração da Interface
st.set_page_config(layout="wide", page_title="BioTrack Roraima", page_icon="🛰️")

st.title("🛰️ BioTrack - Gestão de Consumo e Estoque")
st.markdown("---")

# 2. Carregamento dos Dados
@st.cache_data
def carregar_dados():
    gdf = gpd.read_file("dados_auditoria.geojson")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf

# Inicializar estado do mapa na sessão
if 'map_state' not in st.session_state:
    st.session_state.map_state = {
        'center': [2.82, -60.67],
        'zoom': 12,
        'bounds': None
    }

# Inicializar estado do talhão selecionado para hover
if 'hover_talhao' not in st.session_state:
    st.session_state.hover_talhao = None

try:
    data = carregar_dados()

    # 3. Painel Lateral
    with st.sidebar:
        st.header("🔍 Painel de Controle")
        ano = st.selectbox("Selecione o Ano de Referência", ["2022", "2023", "2024", "2025"])
        col_exp = f"exploracao_{ano}" 
        col_saldo = f"saldo_{ano}"
        
        st.markdown("---")
        st.subheader("🎯 Focar em Talhão")
        lista_talhoes = sorted(data['fid'].unique().tolist())
        talhao_selecionado = st.selectbox("Escolha o ID para Inspeção", ["Visão Geral"] + lista_talhoes)
        
        # Botão para resetar o mapa
        if st.button("🔄 Resetar Visualização do Mapa"):
            st.session_state.map_state = {
                'center': [2.82, -60.67],
                'zoom': 12,
                'bounds': None
            }
            st.rerun()

        # Botão para focar no talhão selecionado
        if talhao_selecionado != "Visão Geral":
            if st.button("🎯 Centralizar no Talhão"):
                geom = data[data['fid'] == talhao_selecionado].geometry.centroid.iloc[0]
                st.session_state.map_state['center'] = [geom.y, geom.x]
                st.session_state.map_state['zoom'] = 16
                st.rerun()

    # 4. KPIs
    total_original = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    consumido = total_original - saldo_atual
    progresso = (consumido / total_original) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Estoque Inicial (2020)", f"{total_original:,.0f}".replace(",", "."))
    c2.metric("Saldo em Estoque", f"{saldo_atual:,.0f}".replace(",", "."), delta=f"-{consumido:,.0f}", delta_color="inverse")
    c3.metric("Percentual de Consumo", f"{progresso:.1f}%")

    st.markdown("---")

    # 5. Informações do Talhão Selecionado
    if talhao_selecionado != "Visão Geral":
        st.subheader(f"📊 Informações Detalhadas - Talhão {talhao_selecionado}")
        
        talhao_data = data[data['fid'] == talhao_selecionado].iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("ID do Talhão", talhao_selecionado)
        
        with col2:
            st.metric("Estoque Inicial (2020)", f"{talhao_data['mudas_2020']:,.0f}".replace(",", "."))
        
        with col3:
            st.metric(f"Saldo {ano}", f"{talhao_data[col_saldo]:,.0f}".replace(",", "."))
        
        with col4:
            consumo_talhao = talhao_data['mudas_2020'] - talhao_data[col_saldo]
            st.metric(
                f"% Consumo {ano}", 
                f"{talhao_data[col_exp]:.1f}%",
                delta=f"-{consumo_talhao:,.0f}".replace(",", ".") if consumo_talhao > 0 else None,
                delta_color="inverse"
            )
        
        st.progress(talhao_data[col_exp] / 100, text="Progresso de Consumo do Talhão")
        
        perc_consumo = talhao_data[col_exp]
        if perc_consumo < 30:
            status = "🟢 Baixo Consumo"
            status_color = "green"
        elif perc_consumo < 70:
            status = "🟡 Consumo Moderado"
            status_color = "orange"
        else:
            status = "🔴 Alto Consumo"
            status_color = "red"
        
        st.markdown(f"**Status:** <span style='color:{status_color}; font-weight:bold'>{status}</span>", unsafe_allow_html=True)
        st.markdown("---")

    # 6. Visualização Espacial
    st.subheader(f"🗺️ Mapa de Consumo e Estoque: {talhao_selecionado} ({ano})")
    
    center = st.session_state.map_state['center']
    zoom = st.session_state.map_state['zoom']
    
    m = leafmap.Map(center=center, zoom=zoom, google_map="SATELLITE")

    data_geojson = data.copy()
    data_geojson['properties'] = data_geojson.apply(lambda row: {
        'ID Talhão': row['fid'],
        'Estoque 2020': f"{row['mudas_2020']:,.0f}",
        f'Saldo {ano}': f"{row[col_saldo]:,.0f}",
        f'% Consumo {ano}': f"{row[col_exp]:.1f}%",
        'Status': 'Alto Consumo' if row[col_exp] >= 70 else ('Consumo Médio' if row[col_exp] >= 30 else 'Baixo Consumo')
    }, axis=1)
    
    m.add_data(
        data,
        column=col_exp,
        scheme="UserDefined", 
        classification_kwds=dict(bins=[1, 30, 70, 99, 100]),
        colors=["#228B22", "#ADFF2F", "#FFFF00", "#FF8C00", "#FF0000"],
        layer_name=f"Status Consumo {ano}",
        fields=["fid", "mudas_2020", col_saldo, col_exp],
        aliases=["ID Talhão", "Estoque 2020", "Saldo Atual", "% Consumido"],
        info_mode="on_hover"
    )

    if talhao_selecionado != "Visão Geral":
        geom_talhao = data[data['fid'] == talhao_selecionado].geometry.iloc[0]
        m.add_gdf(
            gpd.GeoDataFrame(geometry=[geom_talhao], crs="EPSG:4326"),
            style={
                "color": "yellow", 
                "weight": 5, 
                "fillOpacity": 0.1,
                "dashArray": "5, 5"
            },
            layer_name=f"✨ Talhão {talhao_selecionado} (Focado)",
            info_mode=None
        )
        
        centroid = geom_talhao.centroid
        row = data[data['fid'] == talhao_selecionado].iloc[0]
        
        popup_html = f"""
        <div style="font-family: monospace; min-width: 200px;">
            <h4 style="margin: 0 0 5px 0;">📍 Talhão {talhao_selecionado}</h4>
            <hr style="margin: 5px 0;">
            <b>🌱 Estoque 2020:</b> {row['mudas_2020']:,.0f}<br>
            <b>📊 Saldo {ano}:</b> {row[col_saldo]:,.0f}<br>
            <b>⚡ Consumo {ano}:</b> {row[col_exp]:.1f}%<br>
            <b>📈 Consumido:</b> {row['mudas_2020'] - row[col_saldo]:,.0f}<br>
            <hr style="margin: 5px 0;">
            <b>🎯 Status:</b> 
            <span style="color: {'red' if row[col_exp] >= 70 else 'orange' if row[col_exp] >= 30 else 'green'}">
                {'Alto Consumo' if row[col_exp] >= 70 else 'Atenção' if row[col_exp] >= 30 else 'Normal'}
            </span>
        </div>
        """
        
        folium.Marker(
            [centroid.y, centroid.x],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="red", icon="info-sign", prefix='glyphicon')
        ).add_to(m)

    output = st_folium(
        m, 
        key=f"map_instance_{ano}_{talhao_selecionado}", 
        width=1200, 
        height=600,
        returned_objects=["last_center", "last_bounds", "last_zoom", "last_object_clicked"]
    )
    
    if output and output.get('last_center') and output.get('last_zoom'):
        new_center = [output['last_center']['lat'], output['last_center']['lng']]
        new_zoom = output['last_zoom']
        
        if (new_center != st.session_state.map_state['center'] or 
            new_zoom != st.session_state.map_state['zoom']):
            st.session_state.map_state['center'] = new_center
            st.session_state.map_state['zoom'] = new_zoom
    
    # 7. Relatório Detalhado
    st.markdown("---")
    st.subheader("📋 Relatório de Consumo por Talhão")
    
    colunas_tabela = ['fid', 'mudas_2020', col_saldo, col_exp]
    df_tabela = data[colunas_tabela].copy()
    df_tabela.columns = ['ID Talhão', 'Estoque (2020)', 'Saldo Atual', '% Consumo']
    
    if talhao_selecionado != "Visão Geral":
        df_tabela['is_selected'] = df_tabela['ID Talhão'].apply(lambda x: 1 if str(x) == str(talhao_selecionado) else 0)
        df_tabela = df_tabela.sort_values(by=['is_selected', '% Consumo'], ascending=[False, False]).drop(columns=['is_selected'])
    else:
        df_tabela = df_tabela.sort_values(by='% Consumo', ascending=False)
    
    def highlight_selected(row):
        if talhao_selecionado != "Visão Geral" and str(row['ID Talhão']) == str(talhao_selecionado):
            return ['background-color: #FAFF00; color: black; font-weight: bold; border: 2px solid black'] * len(row)
        
        if row['% Consumo'] >= 70:
            return ['background-color: #FFCDD2; color: black'] * len(row)
        elif row['% Consumo'] >= 30:
            return ['background-color: #FFF9C4; color: black'] * len(row)
        else:
            return ['background-color: #C8E6C9; color: black'] * len(row)
    
    st.dataframe(
        df_tabela.style.apply(highlight_selected, axis=1).format({
            'Estoque (2020)': '{:,.0f}',
            'Saldo Atual': '{:,.0f}',
            '% Consumo': '{:.1f}%'
        }),
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    with st.expander("📖 Legenda do Relatório"):
        st.markdown("""
        **Cores na tabela:**
        - 🟡 **Amarelo** (destaque): Talhão atualmente selecionado
        - 🔴 **Vermelho**: Consumo ≥ 70% (Alto Consumo)
        - 🟡 **Amarelo Suave**: Consumo entre 30% e 70% (Moderado)
        - 🟢 **Verde**: Consumo < 30% (Baixo)
        """)
    
    # 8. Estatísticas Gerais
    st.markdown("---")
    with st.expander("📊 Estatísticas Gerais de Consumo", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            criticos = len(df_tabela[df_tabela['% Consumo'] >= 70])
            st.metric("Talhões com Alto Consumo", criticos, f"{(criticos/len(df_tabela)*100):.1f}%", delta_color="inverse")
        
        with col2:
            atencao = len(df_tabela[(df_tabela['% Consumo'] >= 30) & (df_tabela['% Consumo'] < 70)])
            st.metric("Talhões com Consumo Moderado", atencao, f"{(atencao/len(df_tabela)*100):.1f}%")
        
        with col3:
            normais = len(df_tabela[df_tabela['% Consumo'] < 30])
            st.metric("Talhões com Baixo Consumo", normais, f"{(normais/len(df_tabela)*100):.1f}%")

except Exception as e:
    st.error(f"⚠️ Erro ao carregar dashboard: {e}")