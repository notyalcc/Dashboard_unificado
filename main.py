
import streamlit as st
import dashboard
import app as drone_app
from datetime import datetime
import os
import base64

# --- Configuração Global da Página ---
st.set_page_config(
    page_title="Portal Integrado - Logística & Drones",
    page_icon="image.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Estilo CSS Personalizado (Para ficar "Lindo") ---
st.markdown("""
<style>
    
    /* Estilo da Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(to bottom, #1e293b, #0f172a) !important;
    }
    
    /* Animações Keyframes */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translate3d(0, 40px, 0); }
        to { opacity: 1; transform: translate3d(0, 0, 0); }
    }
    
    /* Elementos de Texto da Sidebar (Exclui Inputs para evitar texto branco em fundo branco) */
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stRadio label {
        color: #e2e8f0 !important;
    }
    
    /* Títulos */
    h1, h2, h3 {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Hero Section (Topo da Home) */
    .hero-container {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        padding: 3rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(59, 130, 246, 0.5);
        animation: fadeInUp 0.8s ease-out;
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    .hero-subtitle {
        font-size: 1.2rem;
        opacity: 0.9;
    }

    /* Cards de Seleção na Home */
    .nav-card {
        background-color: white;
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        text-align: center;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(255,255,255,0.5);
        height: 100%;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 1s ease-out;
    }
    .nav-card:hover {
        transform: translateY(-10px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        border-color: #60a5fa;
    }
    .nav-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; width: 100%; height: 5px;
        background: linear-gradient(90deg, #3b82f6, #06b6d4);
    }
    .nav-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        transition: transform 0.3s;
    }
    .nav-card:hover .nav-icon {
        transform: scale(1.1) rotate(5deg);
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
    if os.path.exists("image.png"):
        st.image("image.png", width=100)
    st.title("Portal Corporativo")
    st.markdown("---")
    
    # --- Widget de Login Unificado ---
    if not st.session_state['logged_in']:
        with st.expander("🔒 Acesso Administrativo", expanded=True):
            # Verifica se os segredos foram carregados corretamente
            if "auth" not in st.secrets:
                st.error("⚠️ Erro: O arquivo `.streamlit/secrets.toml` não foi encontrado ou está sem a seção [auth]. Verifique o nome do arquivo (deve ser plural).")

            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                # Busca credenciais no st.secrets (seção [auth])
                valid_user = st.secrets.get("auth", {}).get("username")
                valid_pass = st.secrets.get("auth", {}).get("password")

                if valid_user and valid_pass and usuario == valid_user and senha == valid_pass:
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
    # Saudação baseada no horário
    hora_atual = datetime.now().hour
    if 5 <= hora_atual < 12:
        saudacao = "Bom dia"
    elif 12 <= hora_atual < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    # Hero Section
    st.markdown(f"""
    <div class="hero-container">
        <div class="hero-title">{saudacao}, Equipe! 🚀</div>
        <div class="hero-subtitle">Bem-vindo ao Portal Integrado de Operações. Selecione um módulo abaixo para iniciar suas atividades.</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    # Prepara o ícone: Se existir car.gif, usa ele (Base64), senão mantém o caminhão
    icon_logistica = "🚚"
    if os.path.exists("car.gif"):
        with open("car.gif", "rb") as f:
            data = base64.b64encode(f.read()).decode()
        icon_logistica = f'<img src="data:image/gif;base64,{data}" style="width: 250px; vertical-align: middle;">'

    with col1:
        st.markdown(f"""
        <div class="nav-card">
            <div class="nav-icon">{icon_logistica}</div>
            <div class="nav-title">Logística & Malha</div>
            <div class="nav-desc">
                Gestão completa de expedição e auditoria.<br><br>
                ✅ Controle de Malha Fina<br>
                ✅ KPIs de Transportadoras<br>
                ✅ Análise de Risco Diária
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # Prepara o ícone: Se existir logo.gif, usa ele (Base64), senão mantém o helicóptero
    icon_drone = "🚁"
    if os.path.exists("logo.gif"):
        with open("logo.gif", "rb") as f:
            data = base64.b64encode(f.read()).decode()
        icon_drone = f'<img src="data:image/gif;base64,{data}" style="width: 250px; vertical-align: middle;">'

    with col2:
        st.markdown(f"""
        <div class="nav-card">
            <div class="nav-icon">{icon_drone}</div>
            <div class="nav-title">Gestão de Drones</div>
            <div class="nav-desc">
                Monitoramento aéreo e segurança patrimonial.<br><br>
                ✅ Registro de Voos e Rotas<br>
                ✅ Ranking de Operadores<br>
                ✅ Relatórios Automáticos
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Seção de Status / Atualizações
    st.markdown("### 📢 Status do Sistema")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="status-box">🟢 <b>Logística:</b> Operando Normalmente</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="status-box">🟢 <b>Drones:</b> Banco de Dados Sincronizado</div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="status-box">🔵 <b>Versão:</b> 1.2.0 (Atualizado Hoje)</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption("© 2025 Casas Bahia - Departamento de Prevenção e Perdas | Desenvolvido por Clayton S. Silva")

elif selection == "🚚 Logística (Malha Fina)":
    dashboard.app()

elif selection == "🚁 Controle de Drones":
    drone_app.app()
