import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import io
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium
from fpdf import FPDF
import sqlite3
from github import Github, GithubException

# ================= CONFIG ==================
# st.set_page_config removido para funcionar no projeto unificado

# ================= ARQUIVOS ==================
USUARIOS = "usuarios.json"
DB_FILE = "voos.db"
COLUNAS_VOOS = ["Data","Operador","Tipo","Rotas","Voos","Obs"]

LAT = -22.6238754
LON = -43.2217511

# ================= BASE ==================
# Funções para GitHub (Adaptadas do dashboard.py)
def get_github_connection():
    try:
        if "github" in st.secrets:
            return st.secrets["github"]
    except Exception:
        return None
    return None

def load_data_from_github():
    creds = get_github_connection()
    if not creds: return None
    try:
        g = Github(creds["token"])
        repo = g.get_repo(creds["repo"])
        
        # Lógica de caminho simplificada (mesma pasta do dashboard ou raiz)
        file_path = creds.get("file_path_drones")
        if not file_path:
            base_path = creds.get("file_path", "")
            if "/" in base_path:
                directory = base_path.rsplit("/", 1)[0]
                file_path = f"{directory}/voos.csv"
            else:
                file_path = "voos.csv"
        
        branch = creds.get("branch", "main")
        contents = repo.get_contents(file_path, ref=branch)
        df = pd.read_csv(io.StringIO(contents.decoded_content.decode("utf-8")))
        return df
    except:
        return None

def save_data_to_github(df):
    creds = get_github_connection()
    if not creds: return False
    
    try:
        g = Github(creds["token"])
        repo = g.get_repo(creds["repo"])
        
        # Lógica de caminho simplificada (mesma pasta do dashboard ou raiz)
        file_path = creds.get("file_path_drones")
        if not file_path:
            base_path = creds.get("file_path", "")
            if "/" in base_path:
                directory = base_path.rsplit("/", 1)[0]
                file_path = f"{directory}/voos.csv"
            else:
                file_path = "voos.csv"
        
        branch = creds.get("branch", "main")
        csv_content = df.to_csv(index=False)
        
        try:
            contents = repo.get_contents(file_path, ref=branch)
            repo.update_file(contents.path, "Atualizando voos via App", csv_content, contents.sha, branch=branch)
        except GithubException:
            # Se o arquivo não existe, cria um novo
            repo.create_file(file_path, "Criando arquivo de voos", csv_content, branch=branch)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no GitHub: {e}")
        return False

# --- FUNÇÃO PRINCIPAL DO APP ---
def app():
    # Inicialização de Dados (Session State)
    if 'df_voos' not in st.session_state:
        # 1. Tenta GitHub
        df_start = load_data_from_github()
        
        # 2. Se falhar, tenta SQLite Local
        if df_start is None:
            conn = sqlite3.connect(DB_FILE)
            try:
                df_start = pd.read_sql("SELECT * FROM voos", conn)
            except Exception:
                df_start = pd.DataFrame(columns=COLUNAS_VOOS)
            conn.close()
        
        # Tratamento de tipos
        if not df_start.empty:
            df_start["Data"] = pd.to_datetime(df_start["Data"], dayfirst=True, errors="coerce")
            df_start["Voos"] = pd.to_numeric(df_start["Voos"], errors="coerce").fillna(0)
            df_start["Rotas"] = pd.to_numeric(df_start["Rotas"], errors="coerce").fillna(0)
        else:
            df_start = pd.DataFrame(columns=COLUNAS_VOOS)
            
        st.session_state['df_voos'] = df_start

    # Usa o dataframe da sessão
    df = st.session_state['df_voos'].copy()
    
    # Garante coluna Mes para gráficos
    if not df.empty and "Data" in df.columns:
        df["Mes"] = df["Data"].dt.strftime("%b").str.upper()
    else:
        df["Mes"] = []

    # ================= ESTILO (Carregado apenas ao abrir este módulo) ==================
    st.markdown("""
    <style>
    /* Importando fonte para um visual mais moderno */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Roboto', sans-serif;
    }

    /* Animação de entrada suave */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .block-container { 
        padding-top: 3.5rem; 
        animation: fadeIn 0.8s ease-in-out;
    }

    .card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.05);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0px 8px 20px rgba(0,0,0,0.15);
    }

    .metric-card {
        background: linear-gradient(135deg, #0052cc, #2f80ed);
        color: white;
        padding: 22px;
        border-radius: 15px;
        text-align: center;
        font-size: 26px;
        font-weight: bold;
        box-shadow: 0px 4px 10px rgba(0, 82, 204, 0.3);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        width: 100%;
        box-sizing: border-box;
    }
    .metric-card:hover {
        transform: scale(1.05);
        box-shadow: 0px 8px 25px rgba(0, 82, 204, 0.6);
        cursor: pointer;
    }
    .metric-card .small {
        font-size: 14px;
        font-weight: normal;
        opacity: 0.9;
        margin-top: 5px;
    }

    .rank {
        background: white;
        color: #003366 !important;
        font-weight: bold;
        border-left: 6px solid #0052cc;
        padding: 12px;
        margin-bottom: 10px;
        border-radius: 0 8px 8px 0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    .rank:hover {
        background-color: #f0f7ff;
        border-left-width: 10px;
        padding-left: 20px;
        transform: translateX(5px);
    }
    </style>
    """, unsafe_allow_html=True)

    # ================= MENU ==================
    if os.path.exists("logo.png"):
        st.sidebar.image("logo.png")

    menu = st.sidebar.radio("📂 Menu", [
        "Dashboard",
        "Registrar Voo",
        "Editar Registros",
        "Banco de Dados",
        "Mapa",
        "Relatório PDF",
        "Sair"
    ])

    # Botão útil para desenvolvimento: Limpa o cache se algo travar
    if st.sidebar.button("🧹 Limpar Cache"):
        # Limpa os dados da sessão
        if 'df_voos' in st.session_state:
            del st.session_state['df_voos']
        # Limpa também o estado dos filtros para evitar gráficos quebrados/vazios ao recarregar
        keys_to_clear = ["filtro_todos", "filtro_manual", "filtro_dia_ini", "filtro_dia_fim", "filtro_mes_ini", "filtro_mes_fim", "filtro_ano_geral"]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style='text-align: center; font-size: 12px;'>
            Desenvolvido por <br> <b>Clayton S. Silva</b>
        </div>
        """, unsafe_allow_html=True)

    # ================= DASHBOARD ==================
    if menu == "Dashboard":
        col_img, col_title = st.columns([1, 10])
        with col_img:
            if os.path.exists("logo.gif"):
                st.image("logo.gif", width=70)
            elif os.path.exists("logo.png"):
                st.image("logo.png", width=70)
        with col_title:
            st.markdown("## Dashboard Controle de Voos - Casas Bahia 1401")

        with st.expander("📖 Guia Interativo: Como ler este Dashboard"):
            st.markdown("""
            ### 🧭 Como navegar pelos dados
            
            **1. 🔍 Filtros Inteligentes**
            *   **Operadores:** Use o menu suspenso no topo para isolar um operador específico ou comparar um grupo.
            *   **Selecionar Todos:** Use o checkbox para alternar rapidamente entre a visão individual e a visão da equipe completa.
            
            **2. 📈 Indicadores (Cards Azuis)**
            *   Estes números reagem instantaneamente aos seus filtros. Eles mostram o **Total Absoluto** do que está selecionado no momento.
            
            **3. 📅 Análise Temporal**
            *   **Filtro Diário:** Ajuste as datas de *Início* e *Fim* para analisar períodos curtos (ex: semana passada).
            *   **Gráfico Diário:** Mostra a produtividade dia a dia. *Dica: Passe o mouse sobre as barras para ver detalhes.*
            
            **4. 🎯 Gestão de Metas**
            *   Defina a meta no campo numérico. As barras de progresso mostram visualmente o quão perto cada operador está do objetivo.
            *   **Projeção:** Um cálculo matemático que estima o fechamento do mês baseado no ritmo atual.
            
            **5. 📊 Histórico e Tendências**
            *   Use a seção final para ver a evolução mês a mês ou filtrar por anos anteriores.
            """)

        # ===== FILTRO GERAL =====
        # Tratamento de dados (Igual ao teste que funcionou)
        df["Operador"] = df["Operador"].fillna("Não Informado").astype(str).str.strip()
        
        op_lista = sorted(df["Operador"].unique().tolist())
        
        # Checkbox para controle total (Igual ao teste)
        todos = st.checkbox("Selecionar Todos", value=True, key="chk_todos")
        
        # Define uma chave dinâmica para forçar o reset do componente quando o checkbox muda
        key_filtro = "filtro_todos" if todos else "filtro_manual"
        
        if todos:
            op_selecionados = st.multiselect("Filtrar por Operador", op_lista, default=op_lista, key=key_filtro)
        else:
            op_selecionados = st.multiselect("Filtrar por Operador", op_lista, default=[], key=key_filtro)
        
        # Aplicação do filtro
        if not op_selecionados:
            st.warning("⚠️ Nenhum operador selecionado. A tabela ficará vazia.")
            df_filtrado = df.iloc[0:0] # Cria um DF vazio com as mesmas colunas
        else:
            df_filtrado = df[df["Operador"].isin(op_selecionados)]

        # ===== KPIs (Cards) =====
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='metric-card'>{int(df_filtrado['Voos'].sum())}<div class='small'>Total de Voos</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='metric-card'>{int(df_filtrado['Rotas'].sum())}<div class='small'>Total de Rotas</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='metric-card'>{df_filtrado['Operador'].nunique()}<div class='small'>Operadores</div></div>", unsafe_allow_html=True)

        hoje = datetime.now().date()
        semana_passada = hoje - timedelta(days=7)
        tres_meses = hoje - timedelta(days=90)

        # ===== FILTRO DIÁRIO =====
        st.markdown("### 📅 Filtro Diário")
        f1, f2 = st.columns(2)
        
        inicio_dia = f1.date_input("Data Início", semana_passada, format="DD/MM/YYYY", key="filtro_dia_ini")
        fim_dia = f2.date_input("Data Fim", hoje, format="DD/MM/YYYY", key="filtro_dia_fim")

        base_dia = df_filtrado[(df_filtrado["Data"].dt.date >= inicio_dia) & (df_filtrado["Data"].dt.date <= fim_dia)]

        # ===== GRAFICO DIÁRIO =====
        st.markdown("### 📊 Produção por Operador (Dia)")
        dia = base_dia.groupby("Operador")[["Rotas","Voos"]].sum().reset_index()
        fig_dia = px.bar(dia, x="Operador", y=["Rotas","Voos"], barmode="group", text_auto=True,
                        template="plotly_white", color_discrete_sequence=["#0052cc", "#2f80ed"])
        fig_dia.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_dia, width="stretch", key="chart_dia")

        # ===== RANKING =====
        st.markdown("### 🥇 Ranking dos Operadores")
        ranking = dia.sort_values("Voos", ascending=False)
        for i, row in ranking.head(5).iterrows():
            medalha = "🥇" if i == ranking.index[0] else "🥈" if i == ranking.index[1] else "🥉"
            st.markdown(f"<div class='rank'>{medalha} {row['Operador']} — {int(row['Voos'])} voos</div>", unsafe_allow_html=True)

        # ===== META =====
        st.markdown("### 🎯 Meta Mensal")
        meta = st.number_input("Meta de voos por operador", 50, 2000, 225)
        mes_atual = df_filtrado[df_filtrado["Data"].dt.month == hoje.month]
        meta_base = mes_atual.groupby("Operador")["Voos"].sum().reset_index()

        for _, row in meta_base.iterrows():
            perc = min(row["Voos"] / meta, 1.0)
            st.write(f"{row['Operador']} - {int(row['Voos'])}/{meta}")
            st.progress(perc)

        # ===== PROJEÇÃO =====
        st.markdown("### 📈 Projeção do Mês")
        voos_ate_hoje = mes_atual["Voos"].sum()
        dias_passados = hoje.day
        projecao = int((voos_ate_hoje / max(dias_passados,1)) * 30)

        st.metric("Projeção de voos no mês", projecao)



        # ===== GRÁFICO MENSAL =====
        st.markdown("### 📊 Produção por Mês")
        f3, f4 = st.columns(2)
        inicio_mes = f3.date_input("Data Início (Mensal)", tres_meses, format="DD/MM/YYYY", key="filtro_mes_ini")
        fim_mes = f4.date_input("Data Fim (Mensal)", hoje, format="DD/MM/YYYY", key="filtro_mes_fim")

        base_mes = df_filtrado[(df_filtrado["Data"].dt.date >= inicio_mes) & (df_filtrado["Data"].dt.date <= fim_mes)]
        mes = base_mes.groupby(["Mes","Operador"])[["Rotas","Voos"]].sum().reset_index()

        fig_mes = px.bar(mes, x="Operador", y=["Rotas","Voos"], barmode="group",
                        facet_col="Mes", text_auto=True,
                        template="plotly_white", color_discrete_sequence=["#0052cc", "#2f80ed"])
        fig_mes.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_mes, width="stretch", key="chart_mes")

        # ===== TOTAL GERAL =====
        st.markdown("### 📊 Total Geral (Histórico)")
        
        anos = sorted(df_filtrado["Data"].dt.year.dropna().unique().astype(int), reverse=True)
        ano_filtro = st.selectbox("Selecione o Ano", ["Todos"] + list(anos), key="filtro_ano_geral")

        if ano_filtro != "Todos":
            df_geral = df_filtrado[df_filtrado["Data"].dt.year == ano_filtro]
        else:
            df_geral = df_filtrado

        geral = df_geral.groupby("Operador")[["Rotas","Voos"]].sum().reset_index()
        fig_geral = px.bar(geral, x="Operador", y=["Rotas","Voos"], barmode="group", text_auto=True,
                        template="plotly_white", color_discrete_sequence=["#0052cc", "#2f80ed"])
        fig_geral.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_geral, width="stretch", key="chart_geral")

        # ===== EXPORTAÇÃO =====
        st.markdown("### 📤 Exportar Dados do Período (Filtro Diário)")
        if st.button("Baixar Excel"):
            base_dia.to_excel("exportacao_periodo.xlsx", index=False)
            st.success("Arquivo exportado: exportacao_periodo.xlsx")

    # ================= REGISTRAR ==================
    if menu == "Registrar Voo":
        if not st.session_state.get('logged_in', False):
            st.warning("🔒 Você precisa fazer login no menu lateral para registrar voos.")
            st.stop()

        st.markdown("## 📋 Registrar Voo")

        with st.form("form_registro", clear_on_submit=True):
            data = st.date_input("Data", datetime.now(), format="DD/MM/YYYY")
            operador = st.text_input("Operador")
            tipo = st.selectbox("Tipo", ["FIXO","RESERVA"])
            rotas = st.number_input("Rotas", min_value=0, value=1)
            voos = st.number_input("Voos", min_value=0, value=1)
            obs = st.text_area("Observações")

            submitted = st.form_submit_button("Salvar")

            if submitted:
                if operador:
                    data_formatada = data.strftime("%d/%m/%Y")
                    novo = pd.DataFrame([[data_formatada,operador,tipo,rotas,voos,obs]], columns=COLUNAS_VOOS)
                    
                    # Atualiza Session State
                    # Converte a data do novo registro para datetime para manter consistência no DF em memória
                    novo_memoria = novo.copy()
                    novo_memoria["Data"] = pd.to_datetime(novo_memoria["Data"], dayfirst=True)
                    st.session_state['df_voos'] = pd.concat([st.session_state['df_voos'], novo_memoria], ignore_index=True)
                    
                    # Salva GitHub
                    salvo_cloud = save_data_to_github(st.session_state['df_voos'])
                    
                    # Salva SQLite (Backup Local)
                    conn = sqlite3.connect(DB_FILE)
                    novo.to_sql("voos", conn, if_exists="append", index=False)
                    conn.close()
                    
                    if salvo_cloud:
                        st.success("✅ Voo registrado e salvo na Nuvem (GitHub)!")
                    else:
                        st.success("✅ Voo registrado Localmente.")
                        st.warning("⚠️ Não foi possível salvar no GitHub. Verifique se as 'Secrets' estão configuradas no painel do Streamlit Cloud.")
                else:
                    st.warning("Por favor, preencha o nome do Operador para cadastrar.")

    # ================= EDITAR ==================
    if menu == "Editar Registros":
        if not st.session_state.get('logged_in', False):
            st.warning("🔒 Acesso restrito a administradores.")
            st.stop()

        st.markdown("## ✏️ Editar Registros")
        st.info("Faça as alterações na tabela abaixo e clique em Salvar. Você pode corrigir erros de digitação ou excluir linhas.")

        # Edição apenas das colunas originais
        df_edit = st.data_editor(
            df[COLUNAS_VOOS], 
            num_rows="dynamic", 
            width="stretch",
            key="editor_voos",
            column_config={
                "Data": st.column_config.DateColumn(
                    "Data",
                    format="DD/MM/YYYY"
                )
            }
        )

        if st.button("💾 Salvar Alterações"):
            try:
                df_salvar = df_edit.copy()
                st.session_state['df_voos'] = df_salvar
                
                # Salva GitHub
                salvo_cloud = save_data_to_github(df_salvar)
                
                # Salva SQLite
                # Garante formato de data string (DD/MM/YYYY) para manter o padrão do banco
                df_sqlite = df_salvar.copy()
                df_sqlite["Data"] = pd.to_datetime(df_sqlite["Data"]).dt.strftime("%d/%m/%Y")
                conn = sqlite3.connect(DB_FILE)
                df_sqlite.to_sql("voos", conn, if_exists="replace", index=False)
                conn.close()
                
                if salvo_cloud:
                    st.success("✅ Banco de dados atualizado e sincronizado com GitHub!")
                    st.rerun()
                else:
                    st.warning("⚠️ Banco de dados atualizado APENAS Localmente. Falha ao salvar no GitHub (verifique credenciais).")
                    # Não executamos st.rerun() imediatamente para dar tempo de ler o aviso
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    # ================= BANCO DE DADOS ==================
    if menu == "Banco de Dados":
        if not st.session_state.get('logged_in', False):
            st.warning("🔒 Acesso restrito a administradores.")
            st.stop()

        st.markdown("## 💾 Gerenciar Banco de Dados")
        
        tab1, tab2 = st.tabs(["📥 Importar", "📤 Exportar"])

        # --- ÁREA DE DIAGNÓSTICO ---
        with st.expander("🔧 Diagnóstico de Conexão GitHub"):
            if st.button("Testar Conexão GitHub"):
                creds = get_github_connection()
                if not creds:
                    st.error("❌ Credenciais não encontradas.")
                else:
                    try:
                        g = Github(creds["token"])
                        repo = g.get_repo(creds["repo"])
                        branch = creds.get("branch", "main")
                        st.success(f"✅ Conectado ao repositório: {creds['repo']} (Branch: {branch})")
                        
                        # Tenta listar arquivos na raiz para provar acesso
                        contents = repo.get_contents("", ref=branch)
                        arquivos = [c.name for c in contents]
                        st.info(f"📂 Arquivos na raiz do repo: {', '.join(arquivos)}")
                    except Exception as e:
                        st.error(f"❌ Erro de conexão: {e}")

        with tab1:
            st.markdown("### Importar Excel")
            arq = st.file_uploader("Selecione o arquivo .xlsx", type=["xlsx"])
            if arq:
                base = pd.read_excel(arq)
                st.markdown("#### 🔍 Pré-visualização")
                # Garante que a data seja salva como texto DD/MM/YYYY
                if "Data" in base.columns:
                    base["Data"] = pd.to_datetime(base["Data"]).dt.strftime("%d/%m/%Y")
                st.dataframe(base.head())
                
                modo = st.radio("Modo de Importação", ["Unificar (Adicionar aos dados existentes)", "Substituir (Apagar dados antigos)"])
                
                if st.button("✅ Confirmar Importação"):
                    conn = sqlite3.connect(DB_FILE)
                    # Prepara dados
                    df_novo = base[COLUNAS_VOOS].copy()
                    # Converte data para datetime para memória
                    df_novo["Data"] = pd.to_datetime(df_novo["Data"], dayfirst=True, errors='coerce')
                    # Garante tipos numéricos e limpa strings para evitar duplicatas falsas
                    df_novo["Voos"] = pd.to_numeric(df_novo["Voos"], errors="coerce").fillna(0)
                    df_novo["Rotas"] = pd.to_numeric(df_novo["Rotas"], errors="coerce").fillna(0)
                    df_novo["Operador"] = df_novo["Operador"].astype(str).str.strip()
                    
                    if "Unificar" in modo:
                        combined = pd.concat([st.session_state['df_voos'], df_novo], ignore_index=True)
                        # Garante que os dados originais também estejam limpos para comparação
                        combined["Operador"] = combined["Operador"].astype(str).str.strip()
                        # Remove duplicatas exatas para evitar repetição de dados ao importar o mesmo arquivo
                        st.session_state['df_voos'] = combined.drop_duplicates()
                    else:
                        st.session_state['df_voos'] = df_novo
                    
                    # Salva GitHub e SQLite
                    salvo_github = save_data_to_github(st.session_state['df_voos'])
                    
                    # Para SQLite, converte data para string
                    df_sqlite = st.session_state['df_voos'].copy()
                    df_sqlite["Data"] = df_sqlite["Data"].dt.strftime("%d/%m/%Y")
                    df_sqlite.to_sql("voos", conn, if_exists="replace", index=False)
                    conn.close()

                    if salvo_github:
                        st.success("✅ Dados importados e salvos na Nuvem (GitHub) com sucesso!")
                    else:
                        st.warning("⚠️ Dados importados apenas Localmente. Não foi possível salvar no GitHub (verifique credenciais).")

        with tab2:
            st.markdown("### Exportar Dados")
            
            # Botão CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Baixar CSV (Planilha)", csv, "voos_backup.csv", "text/csv")
            
            # Botão DB
            # Verifica se o arquivo existe antes de abrir. Se não existir (ambiente cloud), recria a partir da memória.
            if not os.path.exists(DB_FILE):
                conn = sqlite3.connect(DB_FILE)
                df_temp = st.session_state['df_voos'].copy()
                if "Data" in df_temp.columns:
                    df_temp["Data"] = pd.to_datetime(df_temp["Data"]).dt.strftime("%d/%m/%Y")
                df_temp.to_sql("voos", conn, if_exists="replace", index=False)
                conn.close()

            if os.path.exists(DB_FILE):
                with open(DB_FILE, "rb") as f:
                    st.download_button("⬇️ Baixar Banco de Dados (.db)", f, "voos.db", "application/octet-stream")

    # ================= MAPA ==================
    if menu == "Mapa":
        if not st.session_state.get('logged_in', False):
            st.warning("🔒 Faça login para visualizar o mapa.")
            st.stop()

        st.markdown("## 🗺️ Galpão Casas Bahia")
        mapa = folium.Map(
            location=[LAT, LON], 
            zoom_start=17, 
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 
            attr="Esri World Imagery"
        )
        folium.Marker([LAT,LON], popup="CD - 1401 ", tooltip="Casas Bahia").add_to(mapa)
        st_folium(mapa, width="stretch")

    # ================= PDF ==================
    if menu == "Relatório PDF":
        if not st.session_state.get('logged_in', False):
            st.warning("🔒 Faça login para gerar relatórios.")
            st.stop()

        st.dataframe(df)
        if st.button("Gerar PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial","B",14)
            pdf.cell(0,10,"Relatório de Voos - Casas Bahia", ln=True)
            pdf.set_font("Arial","",10)

            for _, r in df.iterrows():
                pdf.cell(0,8,f"{r['Operador']} - {r['Voos']} voos - {r['Rotas']} rotas", ln=True)

            pdf.cell(0,10,"Desenvolvido por Clayton S. Silva", ln=True)
            pdf.output("relatorio.pdf")
            st.success("PDF gerado!")

            with open("relatorio.pdf", "rb") as f:
                st.download_button("⬇️ Baixar PDF", f, file_name="relatorio_voos.pdf", mime="application/pdf")

    # ================= SAIR ==================
    if menu == "Sair":
        st.session_state['logged_in'] = False
        st.rerun()

if __name__ == "__main__":
    st.set_page_config(
        page_title="Controle de Drones - Casas Bahia",
        page_icon="logo.png",
        layout="wide"
    )
    app()


##  streamlit run app.py
