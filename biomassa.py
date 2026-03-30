import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium
import pandas as pd
import folium
import plotly.express as px

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

# Inicializar estados da sessão
if 'map_state' not in st.session_state:
    st.session_state.map_state = {'center': [2.82, -60.67], 'zoom': 12}

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
        
        if st.button("🔄 Resetar Mapa"):
            st.session_state.map_state = {'center': [2.82, -60.67], 'zoom': 12}
            st.rerun()

        if talhao_selecionado != "Visão Geral":
            if st.button("🎯 Centralizar no Talhão"):
                geom = data[data['fid'] == talhao_selecionado].geometry.centroid.iloc[0]
                st.session_state.map_state = {'center': [geom.y, geom.x], 'zoom': 16}
                st.rerun()

    # 4. KPIs Principais
    total_original = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    consumido = total_original - saldo_atual
    progresso = (consumido / total_original) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Estoque Inicial (2020)", f"{total_original:,.0f}".replace(",", "."))
    c2.metric("Saldo em Estoque", f"{saldo_atual:,.0f}".replace(",", "."), delta=f"-{consumido:,.0f}", delta_color="inverse")
    c3.metric("Percentual de Consumo", f"{progresso:.1f}%")

    # 5. Informações do Talhão Selecionado
    if talhao_selecionado != "Visão Geral":
        st.markdown("---")
        st.subheader(f"📊 Detalhes - Talhão {talhao_selecionado}")
        t_data = data[data['fid'] == talhao_selecionado].iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ID", talhao_selecionado)
        col2.metric("Original", f"{t_data['mudas_2020']:,.0f}".replace(",", "."))
        col3.metric(f"Saldo {ano}", f"{t_data[col_saldo]:,.0f}".replace(",", "."))
        col4.metric(f"% Consumo", f"{t_data[col_exp]:.1f}%")
        st.progress(t_data[col_exp] / 100)

    # 6. Visualização Espacial
    st.markdown("---")
    m = leafmap.Map(center=st.session_state.map_state['center'], zoom=st.session_state.map_state['zoom'], google_map="SATELLITE")
    
    m.add_data(
        data, column=col_exp, scheme="UserDefined", 
        classification_kwds=dict(bins=[1, 30, 70, 99, 100]),
        colors=["#228B22", "#ADFF2F", "#FFFF00", "#FF8C00", "#FF0000"],
        layer_name="Status Consumo", fields=["fid", col_exp], info_mode="on_hover"
    )

    if talhao_selecionado != "Visão Geral":
        sel_data = data[data['fid'] == talhao_selecionado].iloc[0]
        geom_talhao = sel_data.geometry
        centroid = geom_talhao.centroid
        
        # Destaque da borda do talhão
        m.add_gdf(gpd.GeoDataFrame(geometry=[geom_talhao], crs="EPSG:4326"), 
                  style={"color": "yellow", "weight": 5, "fillOpacity": 0.1}, layer_name="Foco")
        
        # O MARCADOR QUE TINHA SUMIDO:
        folium.Marker(
            [centroid.y, centroid.x],
            popup=f"Talhão {talhao_selecionado}: {sel_data[col_exp]:.1f}% consumido",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)

    st_folium(m, key=f"map_{ano}_{talhao_selecionado}", width=1200, height=500)

    # 7. Relatório Detalhado
    st.markdown("---")
    st.subheader("📋 Relatório por Talhão")
    
    df_tabela = data[['fid', 'mudas_2020', col_saldo, col_exp]].copy()
    
    # Ordenação mantendo o selecionado no topo
    if talhao_selecionado != "Visão Geral":
        df_tabela['sel_hidden'] = (df_tabela['fid'].astype(str) == str(talhao_selecionado)).astype(int)
        df_tabela = df_tabela.sort_values(['sel_hidden', col_exp], ascending=[False, False])
    else:
        df_tabela = df_tabela.sort_values(col_exp, ascending=False)

    # Função de estilização corrigida
    def style_row(row):
        styles = [''] * len(row)
        # Se for o selecionado (usando a coluna oculta de controle)
        if talhao_selecionado != "Visão Geral" and str(row['fid']) == str(talhao_selecionado):
            return ['background-color: #FAFF00; color: black; font-weight: bold; border: 2px solid black'] * len(row)
        
        # Cores de criticidade
        if row[col_exp] >= 70:
            return ['background-color: #FFCDD2; color: black'] * len(row)
        elif row[col_exp] >= 30:
            return ['background-color: #FFF9C4; color: black'] * len(row)
        else:
            return ['background-color: #C8E6C9; color: black'] * len(row)

    # Exibição com as colunas certas (removendo a 'sel_hidden' da visão do usuário)
    st.dataframe(
        df_tabela.drop(columns=['sel_hidden'] if 'sel_hidden' in df_tabela.columns else []).style.apply(style_row, axis=1).format({
            'mudas_2020': '{:,.0f}', 
            col_saldo: '{:,.0f}', 
            col_exp: '{:.1f}%'
        }),
        column_config={
            "fid": "ID Talhão", 
            "mudas_2020": "Inicial", 
            col_saldo: "Saldo Atual", 
            col_exp: "% Consumo"
        },
        use_container_width=True, 
        hide_index=True, 
        height=350
    )

    # 8. Estatísticas Gerais e Gráficos
    st.markdown("---")
    with st.expander("📊 Estatísticas e Ranking de Consumo", expanded=True):
        # 8.1 Métricas (Mantendo como você já tem)
        m1, m2, m3 = st.columns(3)
        with m1:
            c_alt = len(df_tabela[df_tabela[col_exp] >= 70])
            st.metric("Alto Consumo", c_alt, f"{(c_alt/len(df_tabela)*100):.1f}%")
        with m2:
            c_med = len(df_tabela[(df_tabela[col_exp] >= 30) & (df_tabela[col_exp] < 70)])
            st.metric("Consumo Médio", c_med, f"{(c_med/len(df_tabela)*100):.1f}%")
        with m3:
            c_baix = len(df_tabela[df_tabela[col_exp] < 30])
            st.metric("Baixo Consumo", c_baix, f"{(c_baix/len(df_tabela)*100):.1f}%")

        st.markdown("---")
        
        # 8.2 Preparação do Gráfico Dinâmico (Ranking)
        # Criamos um DF focado apenas no ranking para não confundir o Plotly
        df_ranking = data[['fid', col_exp]].copy()
        df_ranking = df_ranking.sort_values(by=col_exp, ascending=False).reset_index(drop=True)
        df_ranking['fid_str'] = df_ranking['fid'].astype(str)
        
        if talhao_selecionado != "Visão Geral":
            # Encontra a POSIÇÃO (0, 1, 2...) do talhão no ranking ordenado
            idx_list = df_ranking.index[df_ranking['fid_str'] == str(talhao_selecionado)].tolist()
            
            if idx_list:
                posicao_real = idx_list[0]
                
                # Define as cores: Amarelo para o selecionado, Cinza para o resto
                df_ranking['Destaque'] = df_ranking['fid_str'].apply(
                    lambda x: 'Selecionado' if x == str(talhao_selecionado) else 'Outros'
                )
                
                # JANELA DE DESLOCAMENTO: Pega 5 talhões antes e 5 depois no ranking
                start = max(0, posicao_real - 5)
                end = min(len(df_ranking), posicao_real + 6)
                df_zoom = df_ranking.iloc[start:end].copy()
                
                st.subheader(f"📈 Posição no Ranking: {posicao_real + 1}º lugar")
            else:
                df_zoom = df_ranking.head(15)
                st.subheader("📈 Ranking Geral de Consumo")
        else:
            df_ranking['Destaque'] = 'Geral'
            df_zoom = df_ranking.head(15)
            st.subheader("📈 Top 15 Maiores Consumos")

        # 8.3 Criação do Gráfico de Barras
        fig_barra = px.bar(
            df_zoom, 
            x='fid_str', 
            y=col_exp,
            color='Destaque',
            color_discrete_map={'Selecionado': '#FAFF00', 'Outros': '#A0A0A0', 'Geral': '#0083B8'},
            text_auto='.1f',
            # Isso impede que o Plotly reordene os IDs (mantém o ranking do maior para o menor)
            category_orders={"fid_str": df_zoom['fid_str'].tolist()} 
        )

        fig_barra.update_layout(
            showlegend=False, 
            height=400,
            xaxis_title="ID do Talhão (Ranking Decrescente)",
            yaxis_title="% Consumo",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )

        # 8.4 Seta Indicadora (Apenas se houver seleção)
        if talhao_selecionado != "Visão Geral":
            val_y = df_zoom[df_zoom['fid_str'] == str(talhao_selecionado)][col_exp].values[0]
            fig_barra.add_annotation(
                x=str(talhao_selecionado), 
                y=val_y,
                text="📍 SELECIONADO", 
                showarrow=True, 
                arrowhead=2, 
                ay=-50,
                bgcolor="#FAFF00", 
                font=dict(color="black", size=12, weight="bold")
            )

        st.plotly_chart(fig_barra, use_container_width=True)

        # 8.5 Gráfico de Linha (Histórico)
        if talhao_selecionado != "Visão Geral":
            st.markdown("---")
            st.subheader(f"📅 Histórico de Consumo - Talhão {talhao_selecionado}")
            t_row = data[data['fid'] == talhao_selecionado].iloc[0]
            df_hist = pd.DataFrame([
                {"Ano": a, "Consumo": t_row[f"exploracao_{a}"]} for a in ["2022", "2023", "2024", "2025"]
            ])
            fig_line = px.line(df_hist, x="Ano", y="Consumo", markers=True)
            fig_line.update_traces(line_color='#FAFF00', line_width=4, marker=dict(size=10, color="black"))
            st.plotly_chart(fig_line, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro crítico: {e}")
    st.exception(e)