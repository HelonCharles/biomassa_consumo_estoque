import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium
import pandas as pd
import folium
import plotly.express as px

# 1. Configuração da Interface
st.set_page_config(layout="wide", page_title="Gestor de Estoque de Acácia mangium", page_icon="🛰️")

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
    c1.metric("Estoque Inicial de Mangium - Referência 2020", f"{total_original:,.0f}".replace(",", ".") + " unid.")
    c2.metric("Saldo em Estoque de Mangium", f"{saldo_atual:,.0f}".replace(",", ".") + " unid.", delta=f"-{consumido:,.0f} unid.", delta_color="inverse")
    c3.metric("Percentual de Consumo de Mangium", f"{progresso:.1f}%")

    # 5. Informações do Talhão Selecionado
    if talhao_selecionado != "Visão Geral":
        st.markdown("---")
        st.subheader(f"📊 Detalhes - Talhão {talhao_selecionado}")
        t_data = data[data['fid'] == talhao_selecionado].iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ID", talhao_selecionado)
        col2.metric("Original", f"{t_data['mudas_2020']:,.0f}".replace(",", ".") + " unid.")
        col3.metric(f"Saldo {ano}", f"{t_data[col_saldo]:,.0f}".replace(",", ".") + " unid.")
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

    # DESTAQUE DINÂMICO NAS COORDENADAS POR ANO SELECIONADO
    if talhao_selecionado != "Visão Geral":
        sel_data = data[data['fid'] == talhao_selecionado].iloc[0]
        geom_talhao = sel_data.geometry
        centroid = geom_talhao.centroid
        
        m.add_gdf(gpd.GeoDataFrame(geometry=[geom_talhao], crs="EPSG:4326"), 
                  style={"color": "yellow", "weight": 5, "fillOpacity": 0.1}, layer_name="Foco")
        
        # Marcador ajustado com as coordenadas exatas e dados sintonizados ao ano escolhido
        folium.Marker(
            [centroid.y, centroid.x],
            popup=f"<b>Talhão {talhao_selecionado}</b><br>Consumo em {ano}: {sel_data[col_exp]:.1f}%<br>Saldo Atual: {sel_data[col_saldo]:,.0f} unid.",
            tooltip=f"Inspeção Talhão {talhao_selecionado} ({ano})",
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
            col_saldo: f"Saldo {ano} (unid.)", 
            col_exp: "% Consumo"
        },
        use_container_width=True, 
        hide_index=True, 
        height=350
    )

    # 8. Estatísticas Gerais e Gráficos
    st.markdown("---")
    with st.expander("📊 Estatísticas e Histórico de Monitoramento", expanded=True):
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
        
        # 8.2 Linha Comparativa do Consumo Ajustada (Eixo numérico para forçar renderização)
        st.subheader("⏳ Evolução Temporal e Linha Comparativa do Consumo")
        
        anos_disponiveis = ["2022", "2023", "2024", "2025"]
        
        if talhao_selecionado != "Visão Geral":
            df_historico = data[data['fid'] == talhao_selecionado].copy()
        else:
            df_historico = data.copy()
            
        lista_linhas = []
        mapa_cores_talhoes = {}
        
        for index, row in df_historico.iterrows():
            fid_str = f"Talhão {row['fid']}"
            
            # ATUALIZAÇÃO: Descobre a cor dinamicamente com base no ano selecionado no Painel Lateral!
            consumo_referencia = row[col_exp]
            if consumo_referencia >= 99: cor = "#FF0000"    # Vermelho
            elif consumo_referencia >= 70: cor = "#FF8C00"  # Laranja
            elif consumo_referencia >= 30: cor = "#FFFF00"  # Amarelo
            elif consumo_referencia >= 1: cor = "#ADFF2F"   # Verde Claro
            else: cor = "#228B22"                     # Verde Escuro (Corte Zero / 100% Preservado)
            
            mapa_cores_talhoes[fid_str] = cor
            
            for a in anos_disponiveis:
                lista_linhas.append({
                    'ID Talhão': fid_str,
                    'Ano': int(a),  # Convertido para int para forçar a linha contínua no gráfico
                    '% Consumo': row[f"exploracao_{a}"]
                })
                
        df_linha_plot = pd.DataFrame(lista_linhas)
        
        # Gerando o gráfico de linhas
        fig_linha = px.line(
            df_linha_plot,
            x='Ano',
            y='% Consumo',
            color='ID Talhão',
            markers=True,
            color_discrete_map=mapa_cores_talhoes
        )
        
        # Configurações de destaque e anotação
        if talhao_selecionado != "Visão Geral":
            # Puxa dinamicamente a cor que foi definida para o talhão atual
            cor_atual = mapa_cores_talhoes[f"Talhão {talhao_selecionado}"]
            fig_linha.update_traces(line_width=4, marker=dict(size=10, color="black"), line_color=cor_atual)
            
            # DESTAQUE NA COORDENADA DO ANO ESCOLHIDO
            valores_ano = df_linha_plot[df_linha_plot['Ano'] == int(ano)]['% Consumo'].values
            if len(valores_ano) > 0:
                val_ano_y = valores_ano[0]
                fig_linha.add_annotation(
                    x=int(ano),
                    y=val_ano_y,
                    text=f"Foco: {ano}",
                    showarrow=True,
                    arrowhead=2,
                    ay=-40,
                    ax=0,
                    bgcolor=cor_atual,  # A caixinha de texto acompanha a cor do nível de criticidade
                    font=dict(color="black" if cor_atual != "#228B22" else "white", size=11, weight="bold")
                )
        else:
            fig_linha.update_traces(line_width=2.5)
        
        # Ajuste estrito do layout
        fig_linha.update_layout(
            height=450,
            xaxis_title="Ano de Monitoramento",
            yaxis_title="% Consumo Acumulado",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickmode='array',
                tickvals=[2022, 2023, 2024, 2025],
                ticktext=["2022", "2023", "2024", "2025"]
            ),
            yaxis=dict(range=[-5, 105])
        )
        st.plotly_chart(fig_linha, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro crítico: {e}")
    st.exception(e)
