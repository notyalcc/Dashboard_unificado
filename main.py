
import streamlit as st
import dashboard
import app as drone_app

# --- Configuração Global da Página ---
st.set_page_config(
    page_title="Portal Integrado - Logística & Drones",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Estilo CSS Personalizado (Para ficar "Lindo") ---
st.markdown("""
<style>
    /* Ajuste do fundo e fontes */
    
    /* Estilo da Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(to bottom, #1e293b, #0f172a) !important;
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    
    /* Títulos */
    h1, h2, h3 {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Cards de Seleção na Home */
    .nav-card {
        background-color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        text-align: center;
        transition: transform 0.2s;
        border: 1px solid #e2e8f0;
        height: 100%;
    }
    .nav-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #3b82f6;
    }
    .nav-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    .nav-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1e293b;
        margin-bottom: 0.5rem;
    }
    .nav-desc {
        color: #64748b;
    }
</style>
""", unsafe_allow_html=True)

# --- Inicialização de Sessão ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- Navegação Lateral ---
with st.sidebar:
    st.title("🏢 Portal Corporativo")
    st.markdown("---")
    
    # --- Widget de Login Unificado ---
    if not st.session_state['logged_in']:
        with st.expander("🔒 Acesso Administrativo", expanded=True):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                # Credenciais simples para exemplo (pode expandir depois)
                if usuario == "admin" and senha == "admin123":
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Credenciais inválidas")
    else:
        st.success("✅ Logado como Admin")
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()
    
    st.markdown("---")
    
    # Menu de Navegação
    selection = st.radio(
        "Navegar para:",
        ["🏠 Início", "🚚 Logística (Malha Fina)", "🚁 Controle de Drones"],
        index=0
    )
    
    st.markdown("---")
    st.caption("Sistema Unificado v1.0")

# --- Lógica de Exibição ---
if selection == "🏠 Início":
    st.title("Bem-vindo ao Portal Integrado")
    st.markdown("Selecione um sistema abaixo para começar:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="nav-card">
            <div class="nav-icon">🚚</div>
            <div class="nav-title">Logística & Malha</div>
            <div class="nav-desc">Controle de expedição, auditoria de malha fina e KPIs de transportadoras.</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="nav-card">
            <div class="nav-icon">🚁</div>
            <div class="nav-title">Gestão de Drones</div>
            <div class="nav-desc">Registro de voos, controle de operadores e relatórios operacionais.</div>
        </div>
        """, unsafe_allow_html=True)

elif selection == "🚚 Logística (Malha Fina)":
    dashboard.app()

elif selection == "🚁 Controle de Drones":
    drone_app.app()
