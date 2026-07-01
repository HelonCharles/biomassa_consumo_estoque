import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium
import pandas as pd
import folium
import plotly.express as px

# 1. Configuração da Interface
st.set_page_config(layout="wide", page_title="Gestão de Mangium Roraima", page_icon="🛰️")

st.title("🛰️ Gestão de Consumo e Estoque")
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
        anos_disponiveis = ["2022", "2023", "2024", "2025"]
        ano = st.selectbox("Selecione o Ano de Referência", anos_disponiveis)
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
    c1.metric(
        "Estoque Inicial de Mangium - Referência 2020", 
        f"{total_original:,.0f} unid.".replace(",", ".")
    )
    c2.metric(
        "Saldo em Estoque de Mangium", 
        f"{saldo_atual:,.0f} unid.".replace(",", "."), 
        delta=f"-{consumido:,.0f} unid.", 
        delta_color="inverse"
    )
    c3.metric(
        "Percentual de Consumo de Mangium", 
        f"{progresso:.1f}% consumido"
    )

    # 5. Informações do Talhão Selecionado
    if talhao_selecionado != "Visão Geral":
        st.markdown("---")
        st.subheader(f"📊 Detalhes - Talhão {talhao_selecionado}")
        t_data = data[data['fid'] == talhao_selecionado].iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ID", talhao_selecionado)
        col2.metric("Original", f"{t_data['mudas_2020']:,.0f} unid.".replace(",", "."))
        col3.metric(f"Saldo {ano}", f"{t_data[col_saldo]:,.0f} unid.".replace(",", "."))
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
        
        m.add_gdf(gpd.GeoDataFrame(geometry=[geom_talhao], crs="EPSG:4326"), 
                  style={"color": "yellow", "weight": 5, "fillOpacity": 0.1}, layer_name="Foco")
        
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
    
    if talhao_selecionado != "Visão Geral":
        df_tabela['sel_hidden'] = (df_tabela['fid'].astype(str) == str(talhao_selecionado)).astype(int)
        df_tabela = df_tabela.sort_values(['sel_hidden', col_exp], ascending=[False, False])
    else:
        df_tabela = df_tabela.sort_values(col_exp, ascending=False)

    def style_row(row):
        if talhao_selecionado != "Visão Geral" and str(row['fid']) == str(talhao_selecionado):
            return ['background-color: #FAFF00; color: black; font-weight: bold; border: 2px solid black'] * len(row)
        
        if row[col_exp] >= 70:
            return ['background-color: #FFCDD2; color: black'] * len(row)
        elif row[col_exp] >= 30:
            return ['background-color: #FFF9C4; color: black'] * len(row)
        else:
            return ['background-color: #C8E6C9; color: black'] * len(row)

    st.dataframe(
        df_tabela.drop(columns=['sel_hidden'] if 'sel_hidden' in df_tabela.columns else []).style.apply(style_row, axis=1).format({
            'mudas_2020': '{:,.0f}', 
            col_saldo: '{:,.0f}', 
            col_exp: '{:.1f}%'
        }),
        column_config={
            "fid": "ID Talhão", 
            "mudas_2020": "Inicial (unid.)", 
            col_saldo: "Saldo Atual (unid.)", 
            col_exp: "% Consumo"
        },
        use_container_width=True, 
        hide_index=True, 
        height=350
    )

    # 8. Estatísticas Gerais e Gráficos de Linha Temporal
    st.markdown("---")
    with st.expander("📊 Estatísticas e Evolução Temporal do Consumo", expanded=True):
        
        # 8.1 Métricas de Severidade
        m1, m2, m3 = st.columns(3)
        with m1:
            c_alt = len(df_tabela[df_tabela[col_exp] >= 70])
            st.metric("Alto Consumo (>=70%)", c_alt, f"{(c_alt/len(df_tabela)*100):.1f}%")
        with m2:
            c_med = len(df_tabela[(df_tabela[col_exp] >= 30) & (df_tabela[col_exp] < 70)])
            st.metric("Consumo Médio (30%-69%)", c_med, f"{(c_med/len(df_tabela)*100):.1f}%")
        with m3:
            c_baix = len(df_tabela[df_tabela[col_exp] < 30])
            st.metric("Baixo Consumo (<30%)", c_baix, f"{(c_baix/len(df_tabela)*100):.1f}%")

        st.markdown("---")
        
        # 8.2 Montagem do Gráfico de Linhas Comparativo Temporal
        historico_anos = []
        
        if talhao_selecionado != "Visão Geral":
            st.subheader(f"📈 Comparação de Consumo ao Longo dos Anos - Talhão {talhao_selecionado}")
            t_row = data[data['fid'] == talhao_selecionado].iloc[0]
            
            for a in anos_disponiveis:
                historico_anos.append({
                    "Ano": str(a),
                    "% Consumo": t_row[f"exploracao_{a}"],
                    "Saldo (unid.)": t_row[f"saldo_{a}"]
                })
            df_linha = pd.DataFrame(historico_anos)
            
            fig_linha = px.line(
                df_linha, x="Ano", y="% Consumo", markers=True,
                text=[f"{val:.1f}%" for val in df_linha["% Consumo"]],
                title=f"Histórico de Consumo Acumulado - Talhão {talhao_selecionado}"
            )
            cor_base = '#FF0000'
            
        else:
            st.subheader("📈 Comparação de Consumo ao Longo dos Anos - Todos os Talhões")
            
            for a in anos_disponiveis:
                media_consumo = data[f"exploracao_{a}"].mean()
                historico_anos.append({
                    "Ano": str(a),
                    "Média % Consumo": media_consumo
                })
            df_linha = pd.DataFrame(historico_anos)
            
            fig_linha = px.line(
                df_linha, x="Ano", y="Média % Consumo", markers=True,
                text=[f"{val:.1f}%" for val in df_linha["Média % Consumo"]],
                title="Média Geral de Consumo Acumulado do Projeto"
            )
            cor_base = '#0083B8'

        # Criação dinâmica das propriedades dos marcadores (Destaque baseado no ano ativo)
        lista_cores = []
        lista_tamanhos = []
        for a in anos_disponiveis:
            if str(a) == str(ano):
                lista_cores.append('#FAFF00')  # Cor de destaque (Amarelo) para o ano selecionado
                lista_tamanhos.append(14)      # Tamanho maior para dar ênfase
            else:
                lista_cores.append(cor_base)   # Cor padrão (Vermelho ou Azul)
                lista_tamanhos.append(8)       # Tamanho padrão menor

        # Atualizando os marcadores de forma limpa e compatível com px.line
        fig_linha.update_traces(
            line=dict(color=cor_base, width=4),
            marker=dict(
                color=lista_cores, 
                size=lista_tamanhos,
                line=dict(color='black', width=1) # Cria uma borda preta sutil em volta dos marcadores
            ),
            textposition="top center"
        )

        fig_linha.update_layout(
            height=400,
            xaxis_title="Ano de Referência",
            yaxis_title="% Consumo",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(range=[0, 105]),
            xaxis=dict(type='category')
        )
        
        st.plotly_chart(fig_linha, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro crítico: {e}")
    st.exception(e)
