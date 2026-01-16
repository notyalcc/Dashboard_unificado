# 🏢 Portal Corporativo Integrado - Logística & Drones

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Status](https://img.shields.io/badge/Status-Em_Desenvolvimento-yellow?style=for-the-badge)

> **Sistema Unificado de Gestão Operacional** desenvolvido para centralizar o controle de auditoria logística (Malha Fina) e o registro de operações com drones.

---

## 📋 Sobre o Projeto

Este projeto unifica dois dashboards essenciais em uma única aplicação web interativa:

1.  **🚚 Dashboard de Logística:** Focado no controle de expedição, monitorando veículos liberados vs. retidos em malha fina, com análise de KPIs por transportadora e operação.
2.  **🚁 Controle de Drones:** Sistema para registro de voos, gestão de operadores, visualização de mapas e geração de relatórios operacionais.

O sistema possui **Login Unificado**, persistência de dados híbrida (**SQLite** local + **GitHub** Cloud) e exportação de relatórios (Excel e PDF).

---

## 🚀 Funcionalidades

### 🔐 Geral
*   **Login Administrativo:** Proteção de acesso para edição e visualização de dados sensíveis.
*   **Navegação Integrada:** Menu lateral intuitivo para alternar entre os sistemas.
*   **Design Responsivo:** Interface moderna adaptada para temas Claro e Escuro.

### 🚚 Módulo Logística
*   **KPIs em Tempo Real:** Fluxo total, veículos liberados, retidos e taxa de retenção global.
*   **Rankings:** Top transportadoras por volume e por retenção.
*   **Análise Temporal:** Visões diária, mensal e anual.
*   **Matriz de Desempenho:** Gráfico de dispersão (Scatter Plot) cruzando volume vs. qualidade.
*   **Mapa de Calor:** Identificação visual de dias críticos e padrões de risco.
*   **Funil de Auditoria:** Visualização do processo de sorteio e fiscalização.
*   **Gestão de Dados:** Importação de Excel/CSV, edição manual e backup na nuvem.

### 🚁 Módulo Drones
*   **Registro de Voos:** Formulário para cadastro de operações (Rotas, Voos, Tipo).
*   **Metas e Projeções:** Acompanhamento visual de metas mensais por operador.
*   **Análise de Ocorrências:** Categorização automática de problemas (Clima, Técnico, etc.) via processamento de texto.
*   **Eficiência Operacional:** Indicador de produtividade (Rotas por Voo).
*   **Mapa Interativo:** Visualização via satélite do local de operação (Folium).
*   **Relatórios:** Geração automática de PDF e exportação para Excel.

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Função |
|Data | Descrição |
|---|---|
| **Python** | Linguagem principal |
| **Streamlit** | Framework Web Interativo |
| **Pandas** | Manipulação e análise de dados |
| **Plotly** | Gráficos interativos e dashboards |
| **SQLite** | Banco de dados local |
| **PyGithub** | Integração para backup na nuvem |
| **Folium** | Mapas interativos |
| **FPDF** | Geração de relatórios PDF |

---

## ⚙️ Instalação e Configuração

### 1. Pré-requisitos
Certifique-se de ter o Python instalado. Recomenda-se o uso de um ambiente virtual (`venv`).

### 2. Instalação das Dependências
Execute o comando abaixo para instalar todas as bibliotecas necessárias:

```bash
pip install -r requirements.txt
```

### 3. Configuração de Segredos (Opcional - Para Nuvem)
Para que o salvamento automático no GitHub funcione, crie um arquivo `.streamlit/secrets.toml` na raiz do projeto com o seguinte conteúdo:

```toml
[github]
token = "SEU_TOKEN_DO_GITHUB"
repo = "seu_usuario/nome_do_repositorio"
branch = "main"
file_path = "dados_logistica.csv"       # Arquivo para dados de logística
file_path_drones = "voos.csv"           # Arquivo para dados de drones
```

> **Nota:** Se não configurar os segredos, o sistema funcionará apenas com o banco de dados local (`dados.db` e `voos.db`).

---

## ▶️ Como Executar

Para iniciar a aplicação, utilize o comando do Streamlit apontando para o arquivo principal:

```bash
streamlit run main.py
```

O sistema abrirá automaticamente no seu navegador padrão (geralmente em `http://localhost:8501`).

---

## 📂 Estrutura do Projeto

```text
Dashboar_unifinificado/
├── main.py              # Arquivo Principal (Menu e Login)
├── dashboard.py         # Módulo de Logística
├── app.py               # Módulo de Drones
├── utils.py             # Funções auxiliares e conexão GitHub
├── requirements.txt     # Lista de dependências
├── logo.png             # Logotipo da empresa
├── usuarios.json        # (Opcional) Controle de usuários local
├── dados.db             # Banco de dados local (Logística)
├── voos.db              # Banco de dados local (Drones)
└── README.md            # Documentação do projeto
```

---

## 👤 Autor

**Clayton S. Silva**

---

## 📄 Licença

Este projeto é de uso corporativo interno. Todos os direitos reservados.
```
