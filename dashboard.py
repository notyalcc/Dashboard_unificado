import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
import tempfile
from github import Github, GithubException
from sqlalchemy import create_engine, inspect
from pandas.api.types import is_datetime64_any_dtype
import utils # Importa o novo módulo

# --- Configuração da Página ---
# st.set_page_config removido para funcionar no projeto unificado

# --- 1. CARREGAMENTO E TRATAMENTO DE DADOS ---

# CONFIGURAÇÃO DO BANCO DE DADOS
if os.environ.get("FROZEN_APP") == "true":
    # Se for executável, salva o banco na mesma pasta do .exe
    base_path = os.environ.get("EXE_DIR", ".")
    db_path = os.path.join(base_path, "dados.db")
    DATABASE_URL = f"sqlite:///{db_path}"
else:
    DATABASE_URL = "sqlite:///dados.db"
TABLE_NAME = 'performance_logistica'

# @st.cache_resource: Otimização de performance.
# Mantém a conexão com o banco aberta na memória para não reconectar a cada clique do usuário.
@st.cache_resource
def get_database_engine(url):
    return create_engine(url)

engine = get_database_engine(DATABASE_URL)

# --- FUNÇÕES PARA GITHUB (PERSISTÊNCIA NA NUVEM) ---
# Funções movidas para utils.py para evitar duplicação

# Função para salvar dados carregados via Upload no banco de dados persistente
def save_uploaded_data(df, replace=False):
    try:
        # Colunas esperadas
        expected_cols = ['DATA', 'TRANSPORTADORA', 'OPERAÇÃO', 'LIBERADOS', 'MALHA', 'TOTAL TRANSPORTADORAS']
        # Filtra colunas existentes no DF carregado
        cols_to_save = [c for c in expected_cols if c in df.columns]
        
        if cols_to_save:
            if replace:
                st.session_state['df_dados'] = df[cols_to_save].copy()
            else:
                if st.session_state['df_dados'].empty:
                    st.session_state['df_dados'] = df[cols_to_save].copy()
                else:
                    # Concatena os dados existentes com os novos
                    df_combined = pd.concat([st.session_state['df_dados'], df[cols_to_save]], ignore_index=True)
                    
                    # Remove duplicatas para garantir que apenas dados novos sejam mantidos
                    rows_before = len(df_combined)
                    st.session_state['df_dados'] = df_combined.drop_duplicates()
                    rows_after = len(st.session_state['df_dados'])
                    
                    if rows_before > rows_after:
                        st.sidebar.info(f"ℹ️ {rows_before - rows_after} registros duplicados foram ignorados (já existiam no banco).")
            
            # Tenta salvar no GitHub
            creds = utils.get_github_connection()
            path = creds["file_path"] if creds else "dados.csv"
            salvo_github = utils.save_data_to_github(st.session_state['df_dados'], path, "Atualizando dados via Dashboard")
            
            # Salva no banco local também (backup/cache)
            if not salvo_github:
                st.session_state['df_dados'].to_sql(TABLE_NAME, engine, if_exists='replace', index=False)
                
            st.sidebar.success(f"✅ Dados atualizados e salvos!")
        else:
            st.sidebar.error("❌ O arquivo não contém as colunas necessárias.")
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao salvar: {e}")

# Função CRÍTICA: Limpeza de dados. É aqui que corrigimos erros comuns de digitação e formatação.
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Realiza a limpeza e padronização dos dados."""
    # Padronizar nomes das colunas
    df.columns = df.columns.str.strip().str.upper()

    # 1. Garantir numéricos (Mover para o início para permitir cálculos de perda)
    for col in ['LIBERADOS', 'MALHA', 'TOTAL TRANSPORTADORAS']:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'DATA' in df.columns:
        # Só executa a limpeza pesada se NÃO for data ainda
        if not is_datetime64_any_dtype(df['DATA']):
            # 1. Converter para string e limpar espaços
            df['DATA'] = df['DATA'].astype(str).str.strip()
            
            # 2. Corrigir erro comum 31/09
            df['DATA'] = df['DATA'].str.replace('31/09', '30/09', regex=False)
            
            # 3. Tentar converter formato padrão (Dia/Mês/Ano)
            # errors='coerce' transforma o que falhar em NaT (Not a Time)
            dates_iso = pd.to_datetime(df['DATA'], dayfirst=True, errors='coerce')
            
            # 4. Recuperar datas que falharam (NaT) tentando ler como Serial Excel (números)
            # Isso recupera as linhas que o Excel salvou como número (ex: 45321)
            mask_nat = dates_iso.isna()
            if mask_nat.any():
                try:
                    # Tenta converter strings numéricas para float e depois para data (Excel base 1899-12-30)
                    numeric_dates = pd.to_numeric(df.loc[mask_nat, 'DATA'], errors='coerce')
                    recovered = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30')
                    dates_iso = dates_iso.fillna(recovered)
                except:
                    pass
            
            df['DATA'] = dates_iso
            
            # Verifica e remove linhas que continuam inválidas
            mask_invalid = df['DATA'].isna()
            linhas_invalidas = mask_invalid.sum()
            if linhas_invalidas > 0:
                vol_perdido = df.loc[mask_invalid, ['LIBERADOS', 'MALHA']].sum().sum()
                st.warning(f"⚠️ Atenção: {linhas_invalidas} linhas foram removidas pois a coluna 'DATA' contém valores inválidos/vazios. Volume total ignorado nestas linhas: {vol_perdido:,.0f}")
                df = df.dropna(subset=['DATA'])
    
    return df

# Função robusta para ler diferentes tipos de arquivo (CSV, Excel, SQLite)
def load_data(uploaded_file=None):
    df = None
    # 1. Tenta carregar do upload
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                # Lógica robusta para CSV (ponto e vírgula ou vírgula)
                # Tenta ler com ';', se falhar (poucas colunas), tenta com ','
                try:
                    df = pd.read_csv(uploaded_file, sep=';')
                    if df.shape[1] < 2:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=',')
                except:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=None, engine='python')
            elif uploaded_file.name.endswith('.db'):
                with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                try:
                    temp_engine = create_engine(f"sqlite:///{tmp_path}")
                    inspector = inspect(temp_engine)
                    tables = inspector.get_table_names()
                    # Remove tabelas internas do SQLite se existirem
                    tables = [t for t in tables if t != 'sqlite_sequence']
                    
                    if tables:
                        # Tenta achar a tabela pelo nome (ignorando maiúsculas/minúsculas) ou pega a primeira
                        target_table = next((t for t in tables if t.lower() == TABLE_NAME.lower()), tables[0])
                        
                        # Identifica colunas de data para leitura correta (igual ao carregamento local)
                        columns_info = inspector.get_columns(target_table)
                        date_cols = [c['name'] for c in columns_info if c['name'].upper() == 'DATA']
                        
                        df = pd.read_sql(f"SELECT * FROM '{target_table}'", con=temp_engine, parse_dates=date_cols)
                    else:
                        st.error("O arquivo .db não contém tabelas de dados válidas.")
                    temp_engine.dispose()
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo .db: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            return None
    # 2. Carrega da Memória (Session State)
    else:
        if 'df_dados' in st.session_state:
            df = st.session_state['df_dados'].copy()

    if df is not None:
        df = clean_dataframe(df)

    return df

# --- FUNÇÕES AUXILIARES DE CÁLCULO ---
def calculate_retention_rate(row):
    """Calcula a taxa de retenção: (Malha / Total Geral) * 100."""
    total = row['LIBERADOS'] + row['MALHA']
    if total == 0: return 0.0
    return round((row['MALHA'] / total) * 100, 2)

# --- NOVA FUNÇÃO: EXPORTAR PARA EXCEL ---
@st.cache_data
def convert_df_to_excel(df):
    """Converte o DataFrame filtrado para um arquivo Excel em memória."""
    output = io.BytesIO()
    # Engine 'openpyxl' é necessária para escrever .xlsx
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio')
    return output.getvalue()

# --- FUNÇÃO PRINCIPAL DO APP ---
def app():
    # --- INICIALIZAÇÃO DOS DADOS NA MEMÓRIA (SESSION STATE) ---
    # O Session State é a "memória de curto prazo" do usuário.
    # Usamos isso para que os dados não sumam quando o usuário clica em um filtro.
    if 'df_dados' not in st.session_state:
        try:
            # Tenta ler do GitHub primeiro (se configurado)
            df_start = utils.load_data_from_github("file_path")
            
            if df_start is None:
                # Se não tem GitHub ou falhou, tenta ler do banco local (SQLite)
                try:
                    df_start = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", con=engine, parse_dates=['DATA'])
                except:
                    df_start = pd.DataFrame()
                
                # Se o banco estiver vazio ou falhar, tenta ler o Excel local (igual ao teste_validacao.py)
                if df_start.empty and os.path.exists('dados.xlsx'):
                    try:
                        df_start = pd.read_excel('dados.xlsx')
                    except Exception:
                        pass
                
            # Garante tipos corretos
            df_start.columns = df_start.columns.str.strip().str.upper()
            if 'DATA' in df_start.columns:
                df_start['DATA'] = pd.to_datetime(df_start['DATA'])
            st.session_state['df_dados'] = df_start
        except Exception:
            # Se der erro (ex: banco não existe), inicia vazio
            st.session_state['df_dados'] = pd.DataFrame(columns=['DATA', 'TRANSPORTADORA', 'OPERAÇÃO', 'LIBERADOS', 'MALHA'])

    # --- 2. BARRA LATERAL (UPLOAD E FILTROS) ---

    # Tenta carregar logo localmente
    possible_logos = ["logo.png", "logo.jpg", "logo.jpeg"]
    local_logo = None

    # Define onde procurar o logo (prioridade: pasta do executável > pasta do script)
    search_dirs = []
    if os.environ.get("FROZEN_APP") == "true":
        search_dirs.append(os.environ.get("EXE_DIR", "."))
    search_dirs.append(os.path.dirname(os.path.abspath(__file__)))

    for d in search_dirs:
        if os.path.exists(d):
            found = next((f for f in os.listdir(d) if f.lower() in possible_logos), None)
            if found:
                local_logo = os.path.join(d, found)
                break

    logo_image = None
    if local_logo:
        logo_image = local_logo
        st.sidebar.image(local_logo)
    else:
        # Fallback para o GIF se não tiver logo local
        st.sidebar.image("https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExNzVseGVsdWtocmNidGU3MDZtYzdmcm1kMzMxM3VhZGJjYzJuNGZiMSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/hR12JVvN9GftOzxqGd/giphy.gif", width=150)

    # --- SISTEMA DE LOGIN (BARRA LATERAL) ---
    # Controla se o usuário pode editar dados ou apenas visualizar
    # O login agora é gerenciado pelo main.py
    acesso_liberado = st.session_state.get('logged_in', False)

    uploaded_file = None

    if acesso_liberado:
        st.sidebar.header("Importar Dados")
        uploaded_file = st.sidebar.file_uploader("Carregar arquivo (CSV, Excel ou DB)", type=['csv', 'xlsx', 'db'])

        # --- FORMULÁRIO DE INSERÇÃO ---
        st.sidebar.markdown("---")
        st.sidebar.header("Inserir Dados Manualmente")
        with st.sidebar.form("form_insercao", clear_on_submit=True):
            f_data = st.date_input("Data", format="DD/MM/YYYY")
            f_transp = st.text_input("Transportadora")
            f_op = st.selectbox("Operação", ["LML", "Direta", "Reversa", "Outros"])
            f_lib = st.number_input("Liberados (Vol)", min_value=0, step=1)
            f_malha = st.number_input("Malha (Qtd)", min_value=0, step=1)
            
            btn_salvar = st.form_submit_button("Salvar Registro")
            
            if btn_salvar:
                if not f_transp:
                    st.sidebar.warning("⚠️ O campo 'Transportadora' é obrigatório.")
                else:
                    new_row = {
                        'DATA': [pd.to_datetime(f_data)], 
                        'TRANSPORTADORA': [f_transp], 
                        'LIBERADOS': [f_lib], 
                        'MALHA': [f_malha], 
                        'OPERAÇÃO': [f_op],
                        'TOTAL TRANSPORTADORAS': [f_lib + f_malha]
                    }
                    df_new = pd.DataFrame(new_row)
                    
                    try:
                        # Atualiza session state
                        if st.session_state['df_dados'].empty:
                            st.session_state['df_dados'] = df_new.copy()
                        else:
                            st.session_state['df_dados'] = pd.concat([st.session_state['df_dados'], df_new], ignore_index=True)
                        
                        # Persistência
                        creds = utils.get_github_connection()
                        path = creds["file_path"] if creds else "dados.csv"
                        salvo = utils.save_data_to_github(st.session_state['df_dados'], path)
                        if not salvo:
                            # Salva o dataframe COMPLETO para garantir consistência (Excel + Novos)
                            st.session_state['df_dados'].to_sql(TABLE_NAME, engine, if_exists='replace', index=False)
                            
                        st.success("Salvo no Banco de Dados com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco: {e}")

    df = load_data(uploaded_file)

    if df is None or df.empty:
        st.info("O banco de dados está vazio. Utilize o menu lateral para carregar um arquivo ou inserir dados manualmente.")
        return # Encerra a função se não houver dados

    if acesso_liberado:
        # Botão para salvar dados importados no banco (aparece apenas se houver upload)
        if uploaded_file is not None:
            replace_data = st.sidebar.checkbox("Substituir todo o banco de dados", help="Marque para apagar o banco atual e criar um novo com este arquivo.")
            if st.sidebar.button("💾 Converter/Salvar em dados.db"):
                save_uploaded_data(df, replace=replace_data)

        # Botão para baixar o banco de dados atualizado
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            temp_engine = create_engine(f"sqlite:///{tmp.name}")
            st.session_state['df_dados'].to_sql(TABLE_NAME, temp_engine, if_exists='replace', index=False)
            
            with open(tmp.name, "rb") as fp:
                st.sidebar.download_button(
                    label="📥 Baixar dados.db (Backup)",
                    data=fp,
                    file_name="dados.db",
                    mime="application/x-sqlite3"
                )

        st.sidebar.header("Filtros")

        # Filtro de Ano
        anos_disponiveis = sorted(df['DATA'].dt.year.unique(), reverse=True)
        anos_selecionados = st.sidebar.multiselect(
            "Ano",
            options=anos_disponiveis,
            default=anos_disponiveis
        )

        # Filtro de Data
        min_date = df['DATA'].min()
        max_date = df['DATA'].max()
        start_date, end_date = st.sidebar.date_input(
            "Selecione o Período",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY"
        )

        # Filtro de Operação
        operacoes = st.sidebar.multiselect(
            "Tipo de Operação",
            options=df['OPERAÇÃO'].unique(),
            default=df['OPERAÇÃO'].unique()
        )

        # Filtro de Transportadora
        transportadoras = st.sidebar.multiselect(
            "Transportadora",
            options=df['TRANSPORTADORA'].unique(),
            default=df['TRANSPORTADORA'].unique()
        )

        # Botão para recarregar dados (Limpar Cache)
        st.sidebar.subheader("Gerenciamento de Dados")
        col_btn1, col_btn2 = st.sidebar.columns(2)
        
        if col_btn1.button("🔄 Recarregar DB"):
            del st.session_state['df_dados']
            st.rerun()
            
        if os.path.exists('dados.xlsx'):
            if col_btn2.button("📂 Ler Excel Local"):
                try:
                    st.session_state['df_dados'] = load_data(open('dados.xlsx', 'rb'))
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Erro: {e}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("Desenvolvido por **Clayton S. Silva**")

    if not acesso_liberado:
        # --- MODO LEITURA (SEM LOGIN) ---
        # Define filtros padrão para que o dashboard funcione
        min_date = df['DATA'].min()
        max_date = df['DATA'].max()
        start_date, end_date = min_date, max_date
        operacoes = df['OPERAÇÃO'].unique()
        transportadoras = df['TRANSPORTADORA'].unique()
        anos_selecionados = df['DATA'].dt.year.unique()
        
        st.sidebar.info("ℹ️ Faça login para acessar filtros e ferramentas de edição.")

    # --- APLICAÇÃO DOS FILTROS ---
    # Aplicar Filtros
    df_filtered = df[
        (df['DATA'].dt.year.isin(anos_selecionados)) &
        (df['DATA'] >= pd.to_datetime(start_date)) &
        (df['DATA'] <= pd.to_datetime(end_date)) &
        (df['OPERAÇÃO'].isin(operacoes)) &
        (df['TRANSPORTADORA'].isin(transportadoras))
    ].copy()

    # Criar colunas de período
    df_filtered['Mês_Ano'] = df_filtered['DATA'].dt.strftime('%Y-%m')
    df_filtered['Ano'] = df_filtered['DATA'].dt.strftime('%Y')

    # --- CONSTRUÇÃO DE TEXTOS DINÂMICOS (PARA TÍTULOS) ---
    if not df_filtered.empty:
        periodo_label = f"{pd.to_datetime(start_date).strftime('%d/%m/%Y')} a {pd.to_datetime(end_date).strftime('%d/%m/%Y')}"
        anos_label = ", ".join(map(str, sorted(df_filtered['DATA'].dt.year.unique())))
    else:
        periodo_label = "Sem dados"
        anos_label = "-"

    # --- NOVA FUNCIONALIDADE: BOTÃO DE DOWNLOAD DO RELATÓRIO FILTRADO ---
    if acesso_liberado and not df_filtered.empty:
        st.sidebar.markdown("---")
        st.sidebar.header("📥 Exportar Relatório")
        excel_data = convert_df_to_excel(df_filtered)
        st.sidebar.download_button(
            label="Baixar Dados Filtrados (.xlsx)",
            data=excel_data,
            file_name="relatorio_logistica_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- 3. DASHBOARD PRINCIPAL ---
    if logo_image:
        st.image(logo_image, width=200)

    # --- ANIMAÇÃO CAMINHÃO ---
    st.markdown("""
    <style>
    @keyframes drive {
        0% { margin-left: 100%; }
        100% { margin-left: -100px; }
    }
    .truck-anim {
        font-size: 40px;
        animation: drive 15s linear infinite;
    }
    </style>
    <div style="width: 100%; overflow: hidden;">
        <div class="truck-anim">🚚</div>
    </div>
    """, unsafe_allow_html=True)    

    st.title(f"📊 Dashboard Controle de Malha Fina e Liberados ({anos_label})")
    st.markdown(f"##### 🗓️ Período de Análise: {periodo_label}")



    # --- CONTEXTO DO PROCESSO (NOVO) ---
    with st.expander("ℹ️ Entenda o Processo de Malha Fina (Auditoria)"):
        st.markdown("""
        **Fluxo Operacional Padrão:**
        
        1.   **Carregamento:** A transportadora realiza o carregamento dos produtos e o veículo se dirige à **Portaria de Saída**.
        2.  🎲 **Sorteio Aleatório:** Na portaria, é realizado um sorteio individual para cada veículo.
        3.  🚦 **Resultado:**
            *   🟢 **Liberado:** O veículo segue viagem normalmente.
            *   🔴 **Malha (Retenção):** O veículo deve retornar ao **Setor de Retorno** para uma **Nova Conferência**.
        4.  📋 **Conclusão:** Após a reconferência, se não houver divergências, o veículo é liberado. Caso contrário, a divergência é relatada.
        """)

    # --- CÁLCULO DE KPIS E DELTAS (COMPARATIVO) ---
    # Período Atual
    total_liberados = df_filtered['LIBERADOS'].sum()
    total_malha = df_filtered['MALHA'].sum()

    # Tenta usar a coluna de Total do Excel se existir (para bater com os 68.128), senão calcula a soma
    if 'TOTAL TRANSPORTADORAS' in df_filtered.columns and df_filtered['TOTAL TRANSPORTADORAS'].sum() > 0:
        total_veiculos = df_filtered['TOTAL TRANSPORTADORAS'].sum()
    else:
        total_veiculos = total_liberados + total_malha

    taxa_malha_global = (total_malha / total_veiculos * 100) if total_veiculos > 0 else 0

    # Período Anterior (para cálculo do Delta)
    periodo_dias = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    data_inicio_prev = pd.to_datetime(start_date) - pd.Timedelta(days=periodo_dias)
    data_fim_prev = pd.to_datetime(start_date) - pd.Timedelta(days=1)

    df_prev = df[
        (df['DATA'] >= data_inicio_prev) &
        (df['DATA'] <= data_fim_prev) &
        (df['OPERAÇÃO'].isin(operacoes)) &
        (df['TRANSPORTADORA'].isin(transportadoras))
    ]

    if 'TOTAL TRANSPORTADORAS' in df_prev.columns and df_prev['TOTAL TRANSPORTADORAS'].sum() > 0:
        total_veiculos_prev = df_prev['TOTAL TRANSPORTADORAS'].sum()
    else:
        total_veiculos_prev = df_prev['LIBERADOS'].sum() + df_prev['MALHA'].sum()

    total_liberados_prev = df_prev['LIBERADOS'].sum()
    total_malha_prev = df_prev['MALHA'].sum()
    taxa_malha_prev = (total_malha_prev / total_veiculos_prev * 100) if total_veiculos_prev > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fluxo Total (Veículos)", f"{total_veiculos:,.0f}", f"{total_veiculos - total_veiculos_prev:,.0f} vs período anterior")
    col2.metric("Veículos Liberados", f"{total_liberados:,.0f}", f"{total_liberados - total_liberados_prev:,.0f} vs período anterior")
    col3.metric("Retidos em Malha", f"{total_malha:,.0f}", f"{total_malha - total_malha_prev:,.0f} vs período anterior", delta_color="inverse")
    col4.metric("Taxa de Retenção Global", f"{taxa_malha_global:.2f}%", f"{taxa_malha_global - taxa_malha_prev:.2f} p.p.", delta_color="inverse")

    st.markdown("---")

    st.subheader("🏆 Rankings")
    col_r1, col_r2 = st.columns(2)

    with col_r1:
        top_vol = df_filtered.groupby('TRANSPORTADORA')['LIBERADOS'].sum().reset_index().sort_values(by='LIBERADOS', ascending=True)
        fig_top_vol = px.bar(top_vol, x='LIBERADOS', y='TRANSPORTADORA', orientation='h', text_auto=True, title=f"Ranking de Fluxo ({periodo_label})", color='LIBERADOS', color_continuous_scale='Teal')
        fig_top_vol.update_traces(textfont_size=14)
        fig_top_vol.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Volume Liberado", yaxis_title=None, showlegend=False)
        st.plotly_chart(fig_top_vol, key="rank_vol", width="stretch")
        st.caption("📝 **Fluxo:** Volume total de veículos que saíram liberados (sem auditoria).")

    with col_r2:
        top_malha = df_filtered.groupby('TRANSPORTADORA')['MALHA'].sum().reset_index().sort_values(by='MALHA', ascending=True)
        fig_top_malha = px.bar(top_malha, x='MALHA', y='TRANSPORTADORA', orientation='h', text_auto=True, title=f"Ranking de Retenção ({periodo_label})", color='MALHA', color_continuous_scale='Reds')
        fig_top_malha.update_traces(textfont_size=14)
        fig_top_malha.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Qtd. Veículos Retidos", yaxis_title=None, showlegend=False)
        st.plotly_chart(fig_top_malha, key="rank_malha", width="stretch")
        st.caption("📝 **Retenção:** Quantidade absoluta de veículos parados para auditoria (Malha Fina).")

    with st.expander("💡 Guia Rápido: Como ler os Rankings?"):
        st.markdown("""
        *   **Ranking de Fluxo:** Mostra quem opera mais. Útil para dimensionar recursos de pátio e conferentes.
        *   **Ranking de Retenção:** Mostra quem mais cai na malha em **números absolutos**. 
            *   ⚠️ *Atenção:* Uma transportadora pode estar no topo aqui apenas porque tem muito volume. Para ver quem tem a *pior performance relativa* (quem "falha" mais proporcionalmente), consulte os gráficos de **Taxa de Retenção (%)** nas abas abaixo.
        """)

    # Abas para análises
    tab_geral, tab_dia, tab_mes, tab_ano = st.tabs(["🔍 Visão Geral & Risco", "📅 Visão Diária", "📆 Visão Mensal", "📅 Visão Anual"])

    with tab_geral:
        st.subheader("Visão Geral Integrada")
        
        # --- NOVO GRÁFICO: FUNIL DO PROCESSO ---
        # Mostra visualmente o "Sorteio"
        col_funnel, col_heatmap = st.columns(2)
        
        with col_funnel:
            st.markdown("##### 🎲 Fluxo do Sorteio (Funil)")
            data_funnel = dict(
                number=[total_veiculos, total_liberados, total_malha],
                stage=["Veículos na Portaria", "🟢 Liberados (Viagem)", "🔴 Retidos (Malha Fina)"]
            )
            fig_funnel = px.funnel(data_funnel, x='number', y='stage', color='stage', 
                                   color_discrete_map={"Veículos na Portaria": "#2E86C1", "🟢 Liberados (Viagem)": "#27AE60", "🔴 Retidos (Malha Fina)": "#C0392B"})
            fig_funnel.update_layout(showlegend=False, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_funnel, width="stretch")

        with col_heatmap:
            st.markdown("##### 🔥 Mapa de Calor: Risco por Dia da Semana")
            # Prepara dados para heatmap: Dia da Semana x Transportadora
            df_heat = df_filtered.copy()
            df_heat['Dia_Semana'] = df_heat['DATA'].dt.day_name()
            # Traduzir dias se necessário, ou usar ordem
            order_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            df_heat_group = df_heat.groupby(['Dia_Semana', 'TRANSPORTADORA'])[['LIBERADOS', 'MALHA']].sum().reset_index()
            
            # Calcula % usando a função auxiliar
            df_heat_group['MALHA_PCT'] = df_heat_group.apply(calculate_retention_rate, axis=1)
            
            fig_heat = px.density_heatmap(df_heat_group, x='Dia_Semana', y='TRANSPORTADORA', z='MALHA_PCT', 
                                          category_orders={"Dia_Semana": order_days},
                                          color_continuous_scale='Reds', title="Intensidade de Retenção (%)")
            fig_heat.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_heat, width="stretch")

        with st.expander("💡 Análise de Risco e Fluxo (Como interpretar?)"):
            st.markdown("""
            *   **Fluxo do Sorteio (Funil):** Mostra a proporção de veículos que seguem viagem direta vs. aqueles desviados para o **Setor de Retorno**. Uma base vermelha larga indica gargalo na reconferência.
            *   **Mapa de Calor (Heatmap):** Identifica dias críticos na operação.
                *   🔥 **Cor Intensa:** Indica que, naquele dia da semana, a transportadora tem alta incidência de ida para Malha.
                *   🕵️ **Ação:** Investigar se há padrões viciados (ex: toda sexta-feira a taxa sobe) ou problemas específicos na expedição.
            """)

        st.markdown("---")
        
        # Filtro de Data Específico para a Visão Geral (Padrão: Últimos 5 dias)
        df_geral_view = df_filtered.copy()
        periodo_g_label = periodo_label # Default
        if not df_filtered.empty:
            max_date_g = df_filtered['DATA'].max()
            min_date_g = df_filtered['DATA'].min()
            # Define padrão: últimos 5 dias
            default_start = max_date_g - pd.Timedelta(days=4)
            if default_start < min_date_g: default_start = min_date_g
            
            dates_g = st.date_input(
                "📅 Filtrar Período (Gráficos Diários)",
                value=[default_start, max_date_g],
                min_value=min_date_g,
                max_value=max_date_g,
                format="DD/MM/YYYY",
                key="filter_geral_dates"
            )
            
            if len(dates_g) == 2:
                df_geral_view = df_filtered[(df_filtered['DATA'] >= pd.to_datetime(dates_g[0])) & (df_filtered['DATA'] <= pd.to_datetime(dates_g[1]))]
                periodo_g_label = f"{pd.to_datetime(dates_g[0]).strftime('%d/%m')} a {pd.to_datetime(dates_g[1]).strftime('%d/%m')}"

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_vol_dia_g = px.bar(df_geral_view, x='DATA', y='LIBERADOS', color='TRANSPORTADORA', barmode='group', title=f"Fluxo de Saída por Dia ({periodo_g_label})", text_auto=True)
            fig_vol_dia_g.update_xaxes(tickformat="%d/%m/%Y")
            fig_vol_dia_g.update_traces(textfont_size=14)
            fig_vol_dia_g.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Data", yaxis_title="Volume")
            st.plotly_chart(fig_vol_dia_g, key="geral_vol_dia", width="stretch")
            st.caption("📊 **Volume Operacional:** Quantidade de veículos liberados dia a dia.")
        with col_g2:
            df_dia_malha_g = df_geral_view.groupby(['DATA', 'TRANSPORTADORA'])[['LIBERADOS', 'MALHA']].sum().reset_index()
            # Cálculo da Taxa de Retenção (%) usando função auxiliar
            df_dia_malha_g['MALHA_PCT'] = df_dia_malha_g.apply(calculate_retention_rate, axis=1)
            
            fig_malha_dia_g = px.bar(df_dia_malha_g, x='DATA', y='MALHA_PCT', color='TRANSPORTADORA', title=f"Taxa de Retenção % por Dia ({periodo_g_label})")
            fig_malha_dia_g.update_xaxes(tickformat="%d/%m/%Y")
            fig_malha_dia_g.update_traces(texttemplate='%{y:.2f}%', textposition='auto', textfont_size=14)
            fig_malha_dia_g.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Data", yaxis_title="Retenção (%)")
            st.plotly_chart(fig_malha_dia_g, key="geral_malha_dia", width="stretch")
            st.caption("🛡️ **Intensidade da Fiscalização:** Porcentagem de veículos auditados em relação ao total de saídas.")
        
        with st.expander("💡 Análise de Tendência Diária (O que observar?)"):
            st.markdown("""
            *   📊 **Fluxo de Saída (Volume):** Acompanhe a quantidade de veículos processados na portaria. Quedas podem indicar falta de carga ou problemas sistêmicos.
            *   🛡️ **Taxa de Retenção (%):** Monitora a severidade do sorteio.
                *   📈 **Picos:** Indicam que muitos veículos foram enviados para reconferência naquele dia, o que pode gerar atrasos e filas no retorno.
                *   📉 **Zeros:** Dias com 0% de malha sugerem falha no sistema de sorteio (todos passaram direto).
            """)

        st.markdown("---")
        st.subheader("Distribuição Operacional")
        col_g3, col_g4 = st.columns(2)
        with col_g3:
            fig_pie_op = px.pie(df_filtered, names='OPERAÇÃO', values='LIBERADOS', title=f"Volume por Operação ({periodo_label})", hole=0.4)
            fig_pie_op.update_traces(textinfo='percent+label')
            fig_pie_op.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie_op, key="pie_op", width="stretch")
        with col_g4:
            fig_pie_transp = px.pie(df_filtered, names='TRANSPORTADORA', values='LIBERADOS', title=f"Share de Volume ({periodo_label})", hole=0.4)
            fig_pie_transp.update_traces(textinfo='percent+label', textposition='inside')
            fig_pie_transp.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie_transp, key="pie_transp", width="stretch")
        
        with st.expander("💡 Análise de Distribuição"):
            st.markdown("""
            *   **Por Operação:** Verifica se o esforço de fiscalização está proporcional ao volume de cada tipo de operação (LML, Direta, etc.).
            *   **Share de Transportadora:** Mostra a representatividade de cada empresa. Transportadoras com maior fatia do gráfico devem ter atenção redobrada, pois qualquer desvio impacta muito o resultado global da unidade.
            """)
            
        st.markdown("---")
        st.subheader("🎯 Matriz de Desempenho: Volume vs. Qualidade")
        
        # Scatter Plot: Cruza Volume (X) com Taxa de Retenção (Y)
        # Isso ajuda a identificar quem opera muito e erra pouco (Ideal) vs quem opera pouco e erra muito.
        df_scatter = df_filtered.groupby('TRANSPORTADORA')[['LIBERADOS', 'MALHA']].sum().reset_index()
        df_scatter['TOTAL'] = df_scatter['LIBERADOS'] + df_scatter['MALHA']
        df_scatter['RETENCAO_PCT'] = df_scatter.apply(calculate_retention_rate, axis=1)
        
        # Filtra volumes muito baixos para limpar o gráfico (opcional, aqui mantive todos)
        fig_scatter = px.scatter(df_scatter, x='LIBERADOS', y='RETENCAO_PCT', 
                                 size='TOTAL', color='TRANSPORTADORA',
                                 hover_name='TRANSPORTADORA',
                                 title=f"Dispersão: Volume vs. Taxa de Retenção ({periodo_label})",
                                 labels={'LIBERADOS': 'Volume Liberado (Eixo X)', 'RETENCAO_PCT': 'Taxa de Retenção % (Eixo Y)'})
        
        # Linha de referência (Média Global)
        if not df_scatter.empty:
            avg_retention = taxa_malha_global
            fig_scatter.add_hline(y=avg_retention, line_dash="dash", line_color="red", annotation_text="Média Global")
        
        fig_scatter.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.caption("💡 **Como ler:** O cenário ideal são transportadoras no canto **inferior direito** (Alto Volume, Baixa Retenção). O canto **superior esquerdo** é crítico (Baixo Volume, Alta Retenção).")
        
        with st.expander("📘 Guia Detalhado: Interpretando a Matriz de Desempenho"):
            st.markdown("""
            Este gráfico cruza duas dimensões críticas para avaliar a eficiência das transportadoras:
            1.  **Eixo Horizontal (X):** Volume de Operação (Quantidade de veículos liberados). Quanto mais à direita, maior a operação.
            2.  **Eixo Vertical (Y):** Taxa de Retenção (%). Quanto mais alto, maior a incidência de malha fina (problemas/auditoria).

            **Análise por Quadrantes:**
            *   🟢 **Alta Performance (Canto Inferior Direito):** Transportadoras com **Alto Volume** e **Baixa Retenção**. São as parceiras ideais, que operam muito e geram pouco retrabalho.
            *   🟡 **Em Observação (Canto Superior Direito):** Transportadoras com **Alto Volume** mas **Alta Retenção**. Elas movimentam a operação, mas sobrecarregam a auditoria. Ações corretivas aqui têm alto impacto no resultado global.
            *   🔴 **Crítico (Canto Superior Esquerdo):** Transportadoras com **Baixo Volume** e **Alta Retenção**. Operam pouco e quase sempre dão problema. Avaliar viabilidade da parceria.
            *   ⚪ **Nicho (Canto Inferior Esquerdo):** Transportadoras com **Baixo Volume** e **Baixa Retenção**. Operam pouco, mas não geram problemas.
            """)

    with tab_dia:
        st.subheader("Análise Diária")
        st.markdown("ℹ️ *Esta visão permite isolar dias específicos para entender o que aconteceu em datas com anomalias identificadas na Visão Geral.*")
        
        # Filtro Independente
        modo_filtro = st.radio("Modo de Visualização:", ["Semana Atual (Automático)", "Selecionar Dia Específico (Independente)"], horizontal=True)
        dia_label = ""
        
        if "Independente" in modo_filtro:
            # Cria um dataframe base ignorando o filtro de data global, mas mantendo filtros de categoria
            df_base_indep = df[
                (df['OPERAÇÃO'].isin(operacoes)) &
                (df['TRANSPORTADORA'].isin(transportadoras))
            ].copy()
            
            if not df_base_indep.empty:
                datas_disponiveis = sorted(df_base_indep['DATA'].dt.date.unique())
                data_selecionada = st.date_input(
                    "Selecione a Data:", 
                    value=datas_disponiveis[-1], 
                    min_value=min(datas_disponiveis), 
                    max_value=max(datas_disponiveis),
                    format="DD/MM/YYYY"
                )
                df_dia_view = df_base_indep[df_base_indep['DATA'].dt.date == data_selecionada]
                dia_label = data_selecionada.strftime('%d/%m/%Y')
            else:
                df_dia_view = pd.DataFrame()
                st.warning("Não há dados disponíveis para os filtros de Operação/Transportadora selecionados.")
        else:
            # Lógica original (Semana Atual baseada no filtro global)
            df_dia_view = df_filtered.copy()
            if not df_dia_view.empty:
                max_date = df_dia_view['DATA'].max()
                start_of_week = max_date - pd.Timedelta(days=max_date.weekday())
                df_dia_view = df_dia_view[df_dia_view['DATA'] >= start_of_week]
                dia_label = f"Semana de {start_of_week.strftime('%d/%m')} a {max_date.strftime('%d/%m')}"

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            fig_vol_dia = px.bar(df_dia_view, x='DATA', y='LIBERADOS', color='TRANSPORTADORA', barmode='group', title=f"Fluxo de Saída ({dia_label})", text_auto=True)
            fig_vol_dia.update_xaxes(tickformat="%d/%m/%Y")
            fig_vol_dia.update_traces(textfont_size=14)
            fig_vol_dia.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Data", yaxis_title="Volume")
            st.plotly_chart(fig_vol_dia, key="dia_vol", width="stretch")
            st.caption("📊 **Volume:** Quantidade de veículos liberados por dia.")
        with col_d2:
            df_dia_malha = df_dia_view.groupby(['DATA', 'TRANSPORTADORA'])[['LIBERADOS', 'MALHA']].sum().reset_index()
            # Cálculo da Taxa de Retenção (%) usando função auxiliar
            df_dia_malha['MALHA_PCT'] = df_dia_malha.apply(calculate_retention_rate, axis=1)
            
            fig_malha_dia = px.bar(df_dia_malha, x='DATA', y='MALHA_PCT', color='TRANSPORTADORA', title=f"Taxa de Retenção % ({dia_label})")
            fig_malha_dia.update_xaxes(tickformat="%d/%m/%Y")
            fig_malha_dia.update_traces(texttemplate='%{y:.2f}%', textposition='auto', textfont_size=14)
            fig_malha_dia.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Data", yaxis_title="Retenção (%)")
            st.plotly_chart(fig_malha_dia, key="dia_malha", width="stretch")
            st.caption("🛡️ **Auditoria:** % de veículos retidos sobre o total.")

    with tab_mes:
        st.subheader("Análise Mensal")
        st.markdown("ℹ️ *Utilize esta visão para identificar sazonalidade (meses de pico) e se a performance das transportadoras está sendo Liberada ou seguindo a malha ao longo do ano.*")
        
        # Filtro de Meses
        meses_disponiveis = sorted(df_filtered['Mês_Ano'].unique())
        # Define padrão como os últimos 3 meses
        padrao_meses = meses_disponiveis[-3:] if len(meses_disponiveis) >= 3 else meses_disponiveis
        meses_selecionados = st.multiselect("Selecione os Meses para Visualizar:", options=meses_disponiveis, default=padrao_meses)
        
        if meses_selecionados:
            df_mes_filtered = df_filtered[df_filtered['Mês_Ano'].isin(meses_selecionados)]
        else:
            df_mes_filtered = df_filtered
            
        df_mes = df_mes_filtered.groupby(['Mês_Ano', 'TRANSPORTADORA'])[['LIBERADOS', 'MALHA']].sum().reset_index()
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            fig_vol_mes = px.bar(df_mes, x='Mês_Ano', y='LIBERADOS', color='TRANSPORTADORA', barmode='group', title=f"Fluxo de Saída por Mês ({anos_label})", text_auto=True)
            fig_vol_mes.update_traces(textfont_size=14)
            fig_vol_mes.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Mês", yaxis_title="Volume")
            st.plotly_chart(fig_vol_mes, key="mes_vol", width="stretch")
            st.caption("📊 **Sazonalidade:** Volume acumulado de liberados por mês.")
        with col_m2:
            # Cálculo da Taxa de Retenção (%) usando função auxiliar
            df_mes['MALHA_PCT'] = df_mes.apply(calculate_retention_rate, axis=1)
            
            fig_malha_mes = px.bar(df_mes, x='Mês_Ano', y='MALHA_PCT', color='TRANSPORTADORA', title=f"Taxa de Retenção % por Mês ({anos_label})")
            fig_malha_mes.update_traces(texttemplate='%{y:.2f}%', textposition='auto', textfont_size=14)
            fig_malha_mes.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Mês", yaxis_title="Retenção (%)")
            st.plotly_chart(fig_malha_mes, key="mes_malha", width="stretch")
            st.caption("🛡️ **Tendência:** Variação mensal da taxa de retenção na malha fina.")

    with tab_ano:
        st.subheader("Análise Anual")
        st.markdown("ℹ️ *Visão consolidada para relatórios gerenciais de longo prazo.*")
        df_ano = df_filtered.groupby(['Ano', 'TRANSPORTADORA'])[['LIBERADOS', 'MALHA']].sum().reset_index()
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            fig_vol_ano = px.bar(df_ano, x='Ano', y='LIBERADOS', color='TRANSPORTADORA', barmode='group', title=f"Fluxo de Saída por Ano ({anos_label})", text_auto=True)
            fig_vol_ano.update_traces(textfont_size=14)
            fig_vol_ano.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Ano", yaxis_title="Volume")
            st.plotly_chart(fig_vol_ano, key="ano_vol", width="stretch")
            st.caption("📊 **Histórico:** Volume total de liberados por ano.")
        with col_a2:
            # Cálculo da Taxa de Retenção (%) usando função auxiliar
            df_ano['MALHA_PCT'] = df_ano.apply(calculate_retention_rate, axis=1)
            
            fig_malha_ano = px.bar(df_ano, x='Ano', y='MALHA_PCT', color='TRANSPORTADORA', title=f"Taxa de Retenção % por Ano ({anos_label})")
            fig_malha_ano.update_traces(texttemplate='%{y:.2f}%', textposition='auto', textfont_size=14)
            fig_malha_ano.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Ano", yaxis_title="Retenção (%)")
            st.plotly_chart(fig_malha_ano, key="ano_malha", width="stretch")
            st.caption("🛡️ **Consolidado:** Taxa média anual de retenção para auditoria.")

    # --- 4. TABELA DE DADOS E EDIÇÃO ---
    with st.expander("Ver Dados Detalhados / Editar"):
        if acesso_liberado:
            st.markdown("### ✏️ Modo de Edição")
            st.info("Faça alterações nas células abaixo e clique em 'Salvar' para persistir no Banco de Dados. Você pode adicionar linhas (clique na última linha vazia) ou excluir (selecione a linha e aperte Delete).")
            
            # Seleciona apenas colunas base para edição
            cols_base = ['DATA', 'TRANSPORTADORA', 'OPERAÇÃO', 'LIBERADOS', 'MALHA']
            
            # Editor de Dados
            df_edited = st.data_editor(
                df_filtered[cols_base].sort_values(by=['DATA', 'TRANSPORTADORA']),
                num_rows="dynamic",
                width="stretch",
                key="editor_dados",
                column_config={
                    "DATA": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "LIBERADOS": st.column_config.NumberColumn("Liberados", min_value=0, step=1, format="%d"),
                    "MALHA": st.column_config.NumberColumn("Malha", min_value=0, step=1, format="%d"),
                    "OPERAÇÃO": st.column_config.SelectboxColumn("Operação", options=["LML", "Direta", "Reversa", "Outros"]),
                }
            )

            if st.button("💾 Salvar Alterações"):
                try:
                    # Lógica de Atualização:
                    df_full = st.session_state['df_dados']
                    indices_originais = df_filtered.index
                    
                    # Remove as linhas antigas correspondentes ao filtro atual
                    df_full = df_full.drop(indices_originais, errors='ignore')
                    
                    # Adiciona as linhas que vieram do editor
                    if df_full.empty:
                        df_full = df_edited.copy()
                    else:
                        df_full = pd.concat([df_full, df_edited], ignore_index=True)
                    
                    # Limpeza e Persistência
                    df_full = clean_dataframe(df_full)
                    df_full = df_full.sort_values(by='DATA')
                    
                    st.session_state['df_dados'] = df_full
                    
                    creds = utils.get_github_connection()
                    path = creds["file_path"] if creds else "dados.csv"
                    salvo = utils.save_data_to_github(df_full, path)
                    if not salvo:
                        df_full.to_sql(TABLE_NAME, engine, if_exists='replace', index=False)
                    
                    st.success("✅ Banco de dados atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

        else:
            # --- MODO LEITURA ---
            df_display = df_filtered.copy()
            df_display['TOTAL GERAL'] = df_display['LIBERADOS'] + df_display['MALHA']
            df_display['% MALHA'] = df_display.apply(calculate_retention_rate, axis=1)

            st.data_editor(
                df_display.sort_values(by=['DATA', 'TRANSPORTADORA']),
                width="stretch",
                disabled=True,
                column_config={
                    "DATA": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "% MALHA": st.column_config.NumberColumn("% Malha", format="%.2f%%"),
                    "TOTAL GERAL": st.column_config.NumberColumn("Total Geral", format="%d")
                }
            )

    # Assinatura
    st.markdown("---")
    st.markdown("<div style='text-align: center'>Desenvolvido por <b>Clayton S. Silva</b></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    st.set_page_config(page_title="Dashboard de Logística", page_icon="🚚", layout="wide")
    app()
