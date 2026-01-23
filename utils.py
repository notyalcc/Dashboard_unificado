import streamlit as st
import pandas as pd
import io
import plotly.express as px
from github import Github, GithubException

def get_github_connection():
    """Verifica se existem credenciais do GitHub configuradas."""
    try:
        if "github" in st.secrets:
            return st.secrets["github"]
    except Exception:
        return None
    return None

def load_data_from_github(file_path_key="file_path"):
    """
    Lê o arquivo CSV do repositório.
    file_path_key: A chave dentro de st.secrets['github'] que contém o caminho do arquivo.
                   Pode ser 'file_path' (logística) ou 'file_path_drones' (drones).
    """
    creds = get_github_connection()
    if not creds: return None
    
    try:
        g = Github(creds["token"])
        repo = g.get_repo(creds["repo"])
        
        # Resolve o caminho do arquivo
        target_path = creds.get(file_path_key)
        if not target_path and file_path_key == "file_path_drones":
             # Fallback para lógica antiga de drones se a chave específica não existir
             base_path = creds.get("file_path", "")
             if "/" in base_path:
                 directory = base_path.rsplit("/", 1)[0]
                 target_path = f"{directory}/voos.csv"
             else:
                 target_path = "voos.csv"
        elif not target_path:
            target_path = creds.get("file_path")

        contents = repo.get_contents(target_path, ref=creds.get("branch", "main"))
        df = pd.read_csv(io.StringIO(contents.decoded_content.decode("utf-8")))
        return df
    except Exception:
        return None

def save_data_to_github(df, target_path, commit_message="Atualizando dados"):
    """Salva o DataFrame no GitHub."""
    creds = get_github_connection()
    if not creds: return False
    
    try:
        g = Github(creds["token"])
        repo = g.get_repo(creds["repo"])
        branch = creds.get("branch", "main")
        csv_content = df.to_csv(index=False)
        
        try:
            contents = repo.get_contents(target_path, ref=branch)
            repo.update_file(contents.path, commit_message, csv_content, contents.sha, branch=branch)
        except GithubException:
            repo.create_file(target_path, f"Criando: {commit_message}", csv_content, branch=branch)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no GitHub: {e}")
        return False

# --- GERENCIADOR DE TEMAS E CORES (COMPARTILHADO) ---
def get_theme_colors(theme="Padrão"):
    """Retorna a lista de cores baseada no tema escolhido."""
    themes = {
        "Padrão": px.colors.qualitative.Alphabet + px.colors.qualitative.Dark24,
        "Vibrante": px.colors.qualitative.Bold + px.colors.qualitative.Prism,
        "Pastel": px.colors.qualitative.Pastel + px.colors.qualitative.Set3,
        "Alto Contraste": px.colors.qualitative.G10 + px.colors.qualitative.T10
    }
    return themes.get(theme, themes["Padrão"])

def get_color_map(items, theme="Padrão"):
    """Gera um dicionário {Item: Cor} consistente para uma lista de itens."""
    palette = get_theme_colors(theme)
    unique_items = sorted(list(set(items)))
    return {item: palette[i % len(palette)] for i, item in enumerate(unique_items)}