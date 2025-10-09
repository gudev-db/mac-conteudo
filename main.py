import streamlit as st
import io
import google.generativeai as genai
from PIL import Image
import requests
import datetime
import os
from pymongo import MongoClient
from bson import ObjectId
import json
import hashlib
from google.genai import types
import uuid
from datetime import datetime

# Configuração inicial
st.set_page_config(
    layout="wide",
    page_title="Conteúdo")

# --- Sistema de Autenticação ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# Dados de usuário (em produção, isso deve vir de um banco de dados seguro)
users = {
    "admin": make_hashes("senha1234"),  # admin/senha1234
    "user1": make_hashes("password1"),  # user1/password1
    "user2": make_hashes("password2")   # user2/password2
}

def login():
    """Formulário de login"""
    st.title("Macfor Conteúdo - Login")
    
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if username in users and check_hashes(password, users[username]):
                st.session_state.logged_in = True
                st.session_state.user = username
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos")

# Verificar se o usuário está logado
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

# --- CONEXÃO MONGODB (após login) ---
client = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
db = client['agentes_personalizados']
collection_agentes = db['agentes']
collection_conversas = db['conversas']

# Configuração da API do Gemini
gemini_api_key = os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("GEMINI_API_KEY não encontrada nas variáveis de ambiente")
    st.stop()

genai.configure(api_key=gemini_api_key)
modelo_vision = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.1})
modelo_texto = genai.GenerativeModel("gemini-2.5-flash")

# Configuração da API do Perplexity
perp_api_key = os.getenv("PERP_API_KEY")
if not perp_api_key:
    st.error("PERP_API_KEY não encontrada nas variáveis de ambiente")

# --- Funções CRUD para Agentes ---
def criar_agente(nome, system_prompt, base_conhecimento, comments, planejamento, categoria, agente_mae_id=None, herdar_elementos=None):
    """Cria um novo agente no MongoDB"""
    agente = {
        "nome": nome,
        "system_prompt": system_prompt,
        "base_conhecimento": base_conhecimento,
        "comments": comments,
        "planejamento": planejamento,
        "categoria": categoria,
        "agente_mae_id": agente_mae_id,
        "herdar_elementos": herdar_elementos or [],
        "data_criacao": datetime.datetime.now(),
        "ativo": True
    }
    result = collection_agentes.insert_one(agente)
    return result.inserted_id

def listar_agentes():
    """Retorna todos os agentes ativos"""
    return list(collection_agentes.find({"ativo": True}).sort("data_criacao", -1))

def listar_agentes_para_heranca(agente_atual_id=None):
    """Retorna todos os agentes ativos que podem ser usados como mãe"""
    query = {"ativo": True}
    if agente_atual_id:
        # Excluir o próprio agente da lista de opções para evitar auto-herança
        if isinstance(agente_atual_id, str):
            agente_atual_id = ObjectId(agente_atual_id)
        query["_id"] = {"$ne": agente_atual_id}
    return list(collection_agentes.find(query).sort("data_criacao", -1))

def obter_agente(agente_id):
    """Obtém um agente específico pelo ID"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return collection_agentes.find_one({"_id": agente_id})

def atualizar_agente(agente_id, nome, system_prompt, base_conhecimento, comments, planejamento, categoria, agente_mae_id=None, herdar_elementos=None):
    """Atualiza um agente existente"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return collection_agentes.update_one(
        {"_id": agente_id},
        {
            "$set": {
                "nome": nome,
                "system_prompt": system_prompt,
                "base_conhecimento": base_conhecimento,
                "comments": comments,
                "planejamento": planejamento,
                "categoria": categoria,
                "agente_mae_id": agente_mae_id,
                "herdar_elementos": herdar_elementos or [],
                "data_atualizacao": datetime.datetime.now()
            }
        }
    )

def desativar_agente(agente_id):
    """Desativa um agente (soft delete)"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return collection_agentes.update_one(
        {"_id": agente_id},
        {"$set": {"ativo": False, "data_desativacao": datetime.datetime.now()}}
    )

def obter_agente_com_heranca(agente_id):
    """Obtém um agente com os elementos herdados aplicados"""
    agente = obter_agente(agente_id)
    if not agente or not agente.get('agente_mae_id'):
        return agente
    
    agente_mae = obter_agente(agente['agente_mae_id'])
    if not agente_mae:
        return agente
    
    elementos_herdar = agente.get('herdar_elementos', [])
    agente_completo = agente.copy()
    
    for elemento in elementos_herdar:
        if elemento == 'system_prompt' and not agente_completo.get('system_prompt'):
            agente_completo['system_prompt'] = agente_mae.get('system_prompt', '')
        elif elemento == 'base_conhecimento' and not agente_completo.get('base_conhecimento'):
            agente_completo['base_conhecimento'] = agente_mae.get('base_conhecimento', '')
        elif elemento == 'comments' and not agente_completo.get('comments'):
            agente_completo['comments'] = agente_mae.get('comments', '')
        elif elemento == 'planejamento' and not agente_completo.get('planejamento'):
            agente_completo['planejamento'] = agente_mae.get('planejamento', '')
    
    return agente_completo

def salvar_conversa(agente_id, mensagens, segmentos_utilizados=None):
    """Salva uma conversa no histórico"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    conversa = {
        "agente_id": agente_id,
        "mensagens": mensagens,
        "segmentos_utilizados": segmentos_utilizados,
        "data_criacao": datetime.datetime.now()
    }
    return collection_conversas.insert_one(conversa)

def obter_conversas(agente_id, limite=10):
    """Obtém o histórico de conversas de um agente"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return list(collection_conversas.find(
        {"agente_id": agente_id}
    ).sort("data_criacao", -1).limit(limite))

# --- Função para construir contexto com segmentos selecionados ---
def construir_contexto(agente, segmentos_selecionados, historico_mensagens=None):
    """Constrói o contexto com base nos segmentos selecionados"""
    contexto = ""
    
    if "system_prompt" in segmentos_selecionados and agente.get('system_prompt'):
        contexto += f"### INSTRUÇÕES DO SISTEMA ###\n{agente['system_prompt']}\n\n"
    
    if "base_conhecimento" in segmentos_selecionados and agente.get('base_conhecimento'):
        contexto += f"### BASE DE CONHECIMENTO ###\n{agente['base_conhecimento']}\n\n"
    
    if "comments" in segmentos_selecionados and agente.get('comments'):
        contexto += f"### COMENTÁRIOS DO CLIENTE ###\n{agente['comments']}\n\n"
    
    if "planejamento" in segmentos_selecionados and agente.get('planejamento'):
        contexto += f"### PLANEJAMENTO ###\n{agente['planejamento']}\n\n"
    
    # Adicionar histórico se fornecido
    if historico_mensagens:
        contexto += "### HISTÓRICO DA CONVERSA ###\n"
        for msg in historico_mensagens:
            contexto += f"{msg['role']}: {msg['content']}\n"
        contexto += "\n"
    
    contexto += "### RESPOSTA ATUAL ###\nassistant:"
    
    return contexto

# --- Configuração de Autenticação de Administrador ---
def check_admin_password():
    """Retorna True se o usuário fornecer a senha de admin correta."""
    
    def admin_password_entered():
        """Verifica se a senha de admin está correta."""
        if st.session_state["admin_password"] == "senha123":
            st.session_state["admin_password_correct"] = True
            st.session_state["admin_user"] = "admin"
            del st.session_state["admin_password"]
        else:
            st.session_state["admin_password_correct"] = False

    if "admin_password_correct" not in st.session_state:
        # Mostra o input para senha de admin
        st.text_input(
            "Senha de Administrador", 
            type="password", 
            on_change=admin_password_entered, 
            key="admin_password"
        )
        return False
    elif not st.session_state["admin_password_correct"]:
        # Senha incorreta, mostra input + erro
        st.text_input(
            "Senha de Administrador", 
            type="password", 
            on_change=admin_password_entered, 
            key="admin_password"
        )
        st.error("😕 Senha de administrador incorreta")
        return False
    else:
        # Senha correta
        return True

# --- SELEÇÃO DE AGENTE NA PARTE SUPERIOR ---
st.sidebar.title(f"🤖 Bem-vindo, {st.session_state.user}!")

# Botão de logout na sidebar
if st.sidebar.button("🚪 Sair", key="logout_btn"):
    for key in ["logged_in", "user", "admin_password_correct", "admin_user"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# Seletor de Agente na parte superior (acima das abas)
st.header("🤖 Seletor de Agente")

# Inicializar estado da sessão para agente selecionado
if "agente_selecionado" not in st.session_state:
    st.session_state.agente_selecionado = None
if "segmentos_selecionados" not in st.session_state:
    st.session_state.segmentos_selecionados = ["system_prompt", "base_conhecimento", "comments", "planejamento"]

# Carregar agentes
agentes = listar_agentes()

if agentes:
    # Agrupar agentes por categoria
    agentes_por_categoria = {}
    for agente in agentes:
        categoria = agente.get('categoria', 'Social')
        if categoria not in agentes_por_categoria:
            agentes_por_categoria[categoria] = []
        agentes_por_categoria[categoria].append(agente)
    
    # Criar opções de seleção com agrupamento
    agente_options = {}
    for categoria, agentes_cat in agentes_por_categoria.items():
        for agente in agentes_cat:
            agente_completo = obter_agente_com_heranca(agente['_id'])
            display_name = f"{agente['nome']} ({categoria})"
            if agente.get('agente_mae_id'):
                display_name += " 🔗"
            agente_options[display_name] = agente_completo
    
    # Seletor de agente
    col1, col2 = st.columns([3, 1])
    with col1:
        agente_selecionado_display = st.selectbox(
            "Selecione um agente para trabalhar:", 
            list(agente_options.keys()),
            key="seletor_agente_global"
        )
    
    with col2:
        if st.button("🔄 Aplicar Agente", key="aplicar_agente"):
            st.session_state.agente_selecionado = agente_options[agente_selecionado_display]
            st.success(f"Agente '{agente_selecionado_display}' selecionado!")
            st.rerun()
    
    # Mostrar agente atual selecionado
    if st.session_state.agente_selecionado:
        agente_atual = st.session_state.agente_selecionado
        st.info(f"**Agente Ativo:** {agente_atual['nome']} ({agente_atual.get('categoria', 'Social')})")
        
        # Mostrar informações de herança se aplicável
        if 'agente_mae_id' in agente_atual and agente_atual['agente_mae_id']:
            agente_original = obter_agente(agente_atual['_id'])
            if agente_original and agente_original.get('herdar_elementos'):
                st.info(f"🔗 Este agente herda {len(agente_original['herdar_elementos'])} elementos do agente mãe")
else:
    st.info("Nenhum agente disponível. Crie um agente primeiro na aba de Gerenciamento.")

# Controles de segmentos na sidebar
if st.session_state.agente_selecionado:
    st.sidebar.subheader("🔧 Configurações do Agente")
    st.sidebar.write("Selecione quais bases de conhecimento usar:")
    
    segmentos_disponiveis = {
        "Prompt do Sistema": "system_prompt",
        "Brand Guidelines": "base_conhecimento", 
        "Comentários do Cliente": "comments",
        "Planejamento": "planejamento"
    }
    
    segmentos_selecionados = []
    for nome, chave in segmentos_disponiveis.items():
        if st.sidebar.checkbox(nome, value=chave in st.session_state.segmentos_selecionados, key=f"seg_{chave}"):
            segmentos_selecionados.append(chave)
    
    st.session_state.segmentos_selecionados = segmentos_selecionados
    
    # Exibir status dos segmentos
    if segmentos_selecionados:
        st.sidebar.success(f"✅ Usando {len(segmentos_selecionados)} segmento(s)")
    else:
        st.sidebar.warning("⚠️ Nenhum segmento selecionado")

st.title("Macfor - Conteúdo")

# Menu de abas - ADICIONANDO A NOVA ABA DE PIPELINE
tab_pipeline, tab_chat, tab_gerenciamento, tab_briefing, tab_conteudo, tab_blog, tab_revisao_ortografica, tab_revisao_tecnica, tab_briefing_tecnico, tab_otimizacao = st.tabs([
    "🚀 Pipeline Completo",
    "💬 Chat", 
    "⚙️ Gerenciar Agentes",
    "📋 Geração de Briefing",
    "✨ Geração de Conteúdo", 
    "🌱 Geração de Conteúdo Blog",
    "📝 Revisão Ortográfica",
    "🔧 Revisão Técnica",
    "⚙️ Geração de Briefing Técnico",
    "🚀 Otimização de Conteúdo"
])

# ========== ABA: PIPELINE COMPLETO ==========
with tab_pipeline:
    st.header("🚀 Pipeline Completo de Conteúdo")
    st.markdown("Fluxo completo: **Briefing → Conteúdo → Otimização → Revisão**")
    
    # Verificar se há um agente selecionado
    if not st.session_state.agente_selecionado:
        st.warning("⚠️ Selecione um agente na parte superior do app para usar o pipeline.")
        st.stop()
    
    # Inicializar estado do pipeline
    if "pipeline_etapa" not in st.session_state:
        st.session_state.pipeline_etapa = 1
    if "pipeline_briefing" not in st.session_state:
        st.session_state.pipeline_briefing = ""
    if "pipeline_conteudo" not in st.session_state:
        st.session_state.pipeline_conteudo = ""
    if "pipeline_otimizado" not in st.session_state:
        st.session_state.pipeline_otimizado = ""
    if "pipeline_revisado" not in st.session_state:
        st.session_state.pipeline_revisado = ""
    
    # Barra de progresso do pipeline
    etapas = ["📋 Briefing", "✨ Conteúdo", "🚀 Otimização", "✅ Revisão"]
    progresso = (st.session_state.pipeline_etapa - 1) / (len(etapas) - 1) if len(etapas) > 1 else 0
    
    col_progresso = st.columns(4)
    for i, etapa in enumerate(etapas):
        with col_progresso[i]:
            if i + 1 < st.session_state.pipeline_etapa:
                st.success(f"✓ {etapa}")
            elif i + 1 == st.session_state.pipeline_etapa:
                st.info(f"▶️ {etapa}")
            else:
                st.write(f"○ {etapa}")
    
    st.progress(progresso)
    
    # ETAPA 1: GERAÇÃO DE BRIEFING
    if st.session_state.pipeline_etapa == 1:
        st.subheader("📋 Etapa 1: Geração de Briefing")
        
        with st.form("pipeline_briefing_form"):
            st.write("**Informações do Projeto**")
            
            col1, col2 = st.columns(2)
            with col1:
                nome_projeto = st.text_input("Nome do Projeto:", key="pipeline_nome")
                tipo_conteudo = st.selectbox("Tipo de Conteúdo:", 
                                           ["Post Social", "Artigo Blog", "Email Marketing", "Landing Page", "Script Vídeo"],
                                           key="pipeline_tipo")
                publico_alvo = st.text_input("Público-Alvo:", key="pipeline_publico")
            
            with col2:
                objetivo_geral = st.text_area("Objetivo Geral:", height=100, key="pipeline_objetivo")
                palavras_chave = st.text_input("Palavras-chave:", key="pipeline_keywords")
                tom_voz = st.selectbox("Tom de Voz:", 
                                      ["Formal", "Informal", "Persuasivo", "Educativo", "Inspirador"],
                                      key="pipeline_tom")
            
            st.write("**Informações Específicas**")
            informacoes_especificas = st.text_area(
                "Detalhes específicos, contexto, informações técnicas, etc:",
                height=200,
                placeholder="Exemplo: Produto X para controle de nematoides na soja. Características: princípio ativo Y, dosagem Z. Benefícios: aumento de produtividade, proteção prolongada...",
                key="pipeline_especifico"
            )
            
            if st.form_submit_button("🎯 Gerar Briefing", use_container_width=True):
                with st.spinner("Gerando briefing profissional..."):
                    try:
                        # Construir prompt para briefing
                        prompt_briefing = f"""
                        Com base nas seguintes informações, crie um briefing completo e profissional:
                        
                        PROJETO: {nome_projeto}
                        TIPO DE CONTEÚDO: {tipo_conteudo}
                        PÚBLICO-ALVO: {publico_alvo}
                        OBJETIVO: {objetivo_geral}
                        PALAVRAS-CHAVE: {palavras_chave}
                        TOM DE VOZ: {tom_voz}
                        INFORMAÇÕES ESPECÍFICAS: {informacoes_especificas}
                        
                        Estruture o briefing com:
                        1. RESUMO EXECUTIVO
                        2. OBJETIVOS ESPECÍFICOS
                        3. PÚBLICO-ALVO DETALHADO
                        4. TOM E ESTILO
                        5. CONTEÚDO PRINCIPAL
                        6. CHAMADAS PARA AÇÃO
                        7. METAS E MÉTRICAS
                        8. OBSERVAÇÕES TÉCNICAS
                        
                        Seja detalhado e específico.
                        """
                        
                        # Usar o contexto do agente selecionado
                        agente = st.session_state.agente_selecionado
                        contexto = construir_contexto(agente, st.session_state.segmentos_selecionados)
                        prompt_completo = contexto + "\n\n" + prompt_briefing
                        
                        resposta = modelo_texto.generate_content(prompt_completo)
                        st.session_state.pipeline_briefing = resposta.text
                        st.session_state.pipeline_etapa = 2
                        st.success("Briefing gerado com sucesso! Avance para a próxima etapa.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Erro ao gerar briefing: {str(e)}")
        
        # Mostrar briefing gerado se existir
        if st.session_state.pipeline_briefing:
            st.subheader("📄 Briefing Gerado")
            st.text_area("Briefing:", value=st.session_state.pipeline_briefing, height=400, key="display_briefing")
            
            if st.button("➡️ Avançar para Geração de Conteúdo", key="avancar_etapa2"):
                st.session_state.pipeline_etapa = 2
                st.rerun()

    # ETAPA 2: GERAÇÃO DE CONTEÚDO
    elif st.session_state.pipeline_etapa == 2:
        st.subheader("✨ Etapa 2: Geração de Conteúdo")
        
        if not st.session_state.pipeline_briefing:
            st.warning("Nenhum briefing encontrado. Volte para a etapa 1.")
            if st.button("⬅️ Voltar para Briefing"):
                st.session_state.pipeline_etapa = 1
                st.rerun()
            st.stop()
        
        st.info("**Briefing da Etapa Anterior:**")
        st.text_area("Briefing:", value=st.session_state.pipeline_briefing, height=200, key="briefing_review", label_visibility="collapsed")
        
        with st.form("pipeline_conteudo_form"):
            st.write("**Configurações de Conteúdo**")
            
            col1, col2 = st.columns(2)
            with col1:
                estilo_conteudo = st.selectbox("Estilo de Conteúdo:", 
                                             ["Informativo", "Persuasivo", "Educativo", "Storytelling", "Técnico"],
                                             key="pipeline_estilo")
                numero_palavras = st.slider("Número de Palavras:", 300, 2000, 800, key="pipeline_palavras")
            
            with col2:
                incluir_cta = st.checkbox("Incluir Call-to-Action", value=True, key="pipeline_cta")
                incluir_exemplos = st.checkbox("Incluir Exemplos Práticos", value=True, key="pipeline_exemplos")
            
            if st.form_submit_button("🎨 Gerar Conteúdo", use_container_width=True):
                with st.spinner("Criando conteúdo personalizado..."):
                    try:
                        # Construir prompt para conteúdo
                        prompt_conteudo = f"""
                        Com base no briefing abaixo, crie um conteúdo completo e engajador:
                        
                        {st.session_state.pipeline_briefing}
                        
                        CONFIGURAÇÕES ADICIONAIS:
                        - Estilo: {estilo_conteudo}
                        - Número de palavras: aproximadamente {numero_palavras}
                        - Incluir CTA: {incluir_cta}
                        - Incluir exemplos práticos: {incluir_exemplos}
                        
                        Estruture o conteúdo de forma lógica e atrativa para o público-alvo.
                        """
                        
                        # Usar o contexto do agente selecionado
                        agente = st.session_state.agente_selecionado
                        contexto = construir_contexto(agente, st.session_state.segmentos_selecionados)
                        prompt_completo = contexto + "\n\n" + prompt_conteudo
                        
                        resposta = modelo_texto.generate_content(prompt_completo)
                        st.session_state.pipeline_conteudo = resposta.text
                        st.session_state.pipeline_etapa = 3
                        st.success("Conteúdo gerado com sucesso! Avance para a próxima etapa.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Erro ao gerar conteúdo: {str(e)}")
        
        # Mostrar conteúdo gerado se existir
        if st.session_state.pipeline_conteudo:
            st.subheader("📄 Conteúdo Gerado")
            st.text_area("Conteúdo:", value=st.session_state.pipeline_conteudo, height=400, key="display_conteudo")
            
            col_voltar, col_avancar = st.columns(2)
            with col_voltar:
                if st.button("⬅️ Voltar para Briefing", key="voltar_etapa1"):
                    st.session_state.pipeline_etapa = 1
                    st.rerun()
            with col_avancar:
                if st.button("➡️ Avançar para Otimização", key="avancar_etapa3"):
                    st.session_state.pipeline_etapa = 3
                    st.rerun()

    # ETAPA 3: OTIMIZAÇÃO DE CONTEÚDO
    elif st.session_state.pipeline_etapa == 3:
        st.subheader("🚀 Etapa 3: Otimização de Conteúdo")
        
        if not st.session_state.pipeline_conteudo:
            st.warning("Nenhum conteúdo encontrado. Volte para a etapa 2.")
            if st.button("⬅️ Voltar para Conteúdo"):
                st.session_state.pipeline_etapa = 2
                st.rerun()
            st.stop()
        
        st.info("**Conteúdo da Etapa Anterior:**")
        st.text_area("Conteúdo:", value=st.session_state.pipeline_conteudo, height=200, key="conteudo_review", label_visibility="collapsed")
        
        with st.form("pipeline_otimizacao_form"):
            st.write("**Configurações de Otimização**")
            
            col1, col2 = st.columns(2)
            with col1:
                tipo_otimizacao = st.selectbox("Foco da Otimização:", 
                                             ["SEO", "Engajamento", "Conversão", "Clareza", "Técnico"],
                                             key="pipeline_foco")
                nivel_agro = st.selectbox("Nível Técnico Agrícola:", 
                                        ["Básico", "Intermediário", "Avançado"],
                                        key="pipeline_nivel")
            
            with col2:
                incluir_metatags = st.checkbox("Gerar Meta Tags SEO", value=True, key="pipeline_metatags")
                otimizar_estrutura = st.checkbox("Otimizar Estrutura", value=True, key="pipeline_estrutura")
            
            palavras_chave_otimizacao = st.text_input("Palavras-chave para SEO (opcional):", key="pipeline_seo_keys")
            
            if st.form_submit_button("🔧 Otimizar Conteúdo", use_container_width=True):
                with st.spinner("Otimizando conteúdo com foco agro..."):
                    try:
                        # PROMPT DE OTIMIZAÇÃO AGRO (conforme solicitado)
                        prompt_otimizacao = f"""
                        SUA PERSONALIDADE: Você é um agrônomo sênior (15+ anos de campo) e estrategista de SEO/Conteúdo para o agro no Brasil (pt-BR). Você une profundidade técnica (cultivos, manejo, sustentabilidade, produtividade) com marketing de conteúdo e SEO avançado para posicionar marcas do agronegócio no topo do Google.  
                        
                        Objetivo macro: Otimizar o conteúdo enviado com base em "SEO Kit" profissional, maximizando tráfego orgânico qualificado, autoridade temática e conversões. 
                        
                        SEO KIT: 
                        - Português brasileiro, tecnicamente embasado, acessível e humano. 
                        - Subtítulo a cada ~200 palavras; cada subtítulo com 8–12 linhas. 
                        - Parágrafos curtos (máx. 3 frases, 1 ideia central). 
                        - Negrito apenas em conceitos-chave; itálico para citações/termos estrangeiros/disclaimers. 
                        - Evite jargão excessivo; defina termos técnicos quando surgirem. 
                        - Inclua exemplos práticos de campo, mini estudos de caso COM FONTES e orientações acionáveis. 
                        - Trate sazonalidade e regionalização (biomas/zonas climáticas do Brasil) quando pertinente. 
                        - E-E-A-T: deixar claras a experiência prática, fontes confiáveis e originalidade. Sem conteúdo genérico. 
                        
                        Redação especializada e escaneável (atualize o ARTIGO) 
                        - Introdução curta e impactante com promessa clara e CTA inicial. 
                        - Em cada seção: explique porquê/como/quando com FONTES (condições agronômicas, clima, solo, fenologia). 
                        - Traga dados e referências (ensaios, boletins técnicos, normas) com links confiáveis. 
                        - Sinalize pontos ideais para imagens/gráficos (ex.: curva de produtividade vs. adubação; diagnóstico de praga; tabela de híbridos). 
                        - Inclua tabelas quando houver comparativos (dose/época/manejo; custo/benefício). 
                        - Use mini-casos do campo (antes/depois, ganho em sc/ha, ROI estimado). 
                        - Conclusão forte com CTA (ex.: Baixe, Aplique, Fale com um especialista). 
                        
                        CONFIGURAÇÕES ATUAIS:
                        - Foco da otimização: {tipo_otimizacao}
                        - Nível técnico: {nivel_agro}
                        - Palavras-chave: {palavras_chave_otimizacao}
                        - Gerar meta tags: {incluir_metatags}
                        - Otimizar estrutura: {otimizar_estrutura}
                        
                        CONTEÚDO A SER OTIMIZADO:
                        {st.session_state.pipeline_conteudo}
                        
                        AO FINAL DO ARTIGO OTIMIZADO: 
                        1) On-page SEO completo (entregar junto com o artigo) 
                        - Title tag (≤60 caracteres) com KW1 no início. 
                        - Meta description (≤155 caracteres) com benefício + CTA. 
                        - H1 distinto do Title, natural e com KW1. 
                        - URL slug curto, descritivo, com KW1 (sem stopwords desnecessárias). 
                        
                        2) Conformidade e segurança (YMYL leve no agro) 
                        - Adicionar disclaimer quando envolver segurança de alimentos, aplicações químicas, legislações ou recomendações com receituário agronômico. 
                        - Reforçar boas práticas, EPIs e cumprimento de rótulo/legislação vigente. 
                        
                        Retorne o conteúdo otimizado seguindo EXATAMENTE estas instruções.
                        """
                        
                        resposta = modelo_texto.generate_content(prompt_otimizacao)
                        st.session_state.pipeline_otimizado = resposta.text
                        st.session_state.pipeline_etapa = 4
                        st.success("Conteúdo otimizado com sucesso! Avance para a próxima etapa.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Erro ao otimizar conteúdo: {str(e)}")
        
        # Mostrar conteúdo otimizado se existir
        if st.session_state.pipeline_otimizado:
            st.subheader("📊 Conteúdo Otimizado")
            st.text_area("Conteúdo Otimizado:", value=st.session_state.pipeline_otimizado, height=400, key="display_otimizado")
            
            col_voltar, col_avancar = st.columns(2)
            with col_voltar:
                if st.button("⬅️ Voltar para Conteúdo", key="voltar_etapa2"):
                    st.session_state.pipeline_etapa = 2
                    st.rerun()
            with col_avancar:
                if st.button("➡️ Avançar para Revisão Final", key="avancar_etapa4"):
                    st.session_state.pipeline_etapa = 4
                    st.rerun()

    # ETAPA 4: REVISÃO FINAL
    elif st.session_state.pipeline_etapa == 4:
        st.subheader("✅ Etapa 4: Revisão Final")
        
        if not st.session_state.pipeline_otimizado:
            st.warning("Nenhum conteúdo otimizado encontrado. Volte para a etapa 3.")
            if st.button("⬅️ Voltar para Otimização"):
                st.session_state.pipeline_etapa = 3
                st.rerun()
            st.stop()
        
        st.info("**Conteúdo Otimizado da Etapa Anterior:**")
        st.text_area("Conteúdo Otimizado:", value=st.session_state.pipeline_otimizado, height=200, key="otimizado_review", label_visibility="collapsed")
        
        with st.form("pipeline_revisao_form"):
            st.write("**Configurações de Revisão**")
            
            col1, col2 = st.columns(2)
            with col1:
                tipo_revisao = st.selectbox("Tipo de Revisão:", 
                                          ["Ortográfica e Gramatical", "Técnica", "Completa", "Estilo"],
                                          key="pipeline_revisao_tipo")
                rigor_revisao = st.select_slider("Rigor da Revisão:", 
                                               ["Leve", "Moderado", "Rigoroso"],
                                               key="pipeline_rigor")
            
            with col2:
                verificar_fatos = st.checkbox("Verificar Precisão de Fatos", value=True, key="pipeline_fatos")
                sugerir_melhorias = st.checkbox("Sugerir Melhorias", value=True, key="pipeline_sugestoes")
            
            if st.form_submit_button("🔍 Realizar Revisão Final", use_container_width=True):
                with st.spinner("Realizando revisão completa..."):
                    try:
                        prompt_revisao = f"""
                        Realize uma revisão {tipo_revisao.lower()} {rigor_revisao.lower()} do seguinte conteúdo:
                        
                        {st.session_state.pipeline_otimizado}
                        
                        CONFIGURAÇÕES:
                        - Tipo de revisão: {tipo_revisao}
                        - Rigor: {rigor_revisao}
                        - Verificar fatos: {verificar_fatos}
                        - Sugerir melhorias: {sugerir_melhorias}
                        
                        Forneça:
                        1. Conteúdo revisado e corrigido
                        2. Lista de alterações realizadas
                        3. Pontuação de qualidade (1-10)
                        4. { "Sugestões de melhoria" if sugerir_melhorias else "Apenas correções essenciais" }
                        
                        Seja minucioso e profissional na análise.
                        """
                        
                        resposta = modelo_texto.generate_content(prompt_revisao)
                        st.session_state.pipeline_revisado = resposta.text
                        st.success("Revisão finalizada com sucesso! Pipeline completo.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Erro na revisão: {str(e)}")
        
        # Mostrar resultado final
        if st.session_state.pipeline_revisado:
            st.subheader("🎉 Conteúdo Final Revisado")
            st.text_area("Conteúdo Final:", value=st.session_state.pipeline_revisado, height=400, key="display_final")
            
            # Botões de ação final
            col1, col2, col3 = st.columns(3)
            with col1:
                st.download_button(
                    "💾 Baixar Conteúdo Final",
                    data=st.session_state.pipeline_revisado,
                    file_name=f"conteudo_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col2:
                if st.button("🔄 Novo Pipeline", use_container_width=True):
                    # Resetar pipeline
                    for key in ["pipeline_etapa", "pipeline_briefing", "pipeline_conteudo", "pipeline_otimizado", "pipeline_revisado"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.session_state.pipeline_etapa = 1
                    st.rerun()
            with col3:
                if st.button("⬅️ Voltar para Otimização", key="voltar_etapa3"):
                    st.session_state.pipeline_etapa = 3
                    st.rerun()
            
            # Resumo do pipeline
            st.subheader("📊 Resumo do Pipeline")
            col_res1, col_res2, col_res3, col_res4 = st.columns(4)
            
            with col_res1:
                st.metric("Briefing", "✓ Completo")
            with col_res2:
                st.metric("Conteúdo", "✓ Gerado")
            with col_res3:
                st.metric("Otimização", "✓ Aplicada")
            with col_res4:
                st.metric("Revisão", "✓ Finalizada")

# ========== ABA: CHAT ==========
with tab_chat:
    st.header("💬 Chat com Agente")
    
    # Inicializar estado da sessão
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Verificar se há agente selecionado
    if not st.session_state.agente_selecionado:
        st.info("Selecione um agente na parte superior do app para iniciar o chat.")
    else:
        agente = st.session_state.agente_selecionado
        st.subheader(f"Conversando com: {agente['nome']}")
        
        # Exibir histórico de mensagens
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Input do usuário
        if prompt := st.chat_input("Digite sua mensagem..."):
            # Adicionar mensagem do usuário ao histórico
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Construir contexto com segmentos selecionados
            contexto = construir_contexto(
                agente, 
                st.session_state.segmentos_selecionados, 
                st.session_state.messages
            )
            
            # Gerar resposta
            with st.chat_message("assistant"):
                with st.spinner('Pensando...'):
                    try:
                        resposta = modelo_texto.generate_content(contexto)
                        st.markdown(resposta.text)
                        
                        # Adicionar ao histórico
                        st.session_state.messages.append({"role": "assistant", "content": resposta.text})
                        
                        # Salvar conversa com segmentos utilizados
                        salvar_conversa(
                            agente['_id'], 
                            st.session_state.messages,
                            st.session_state.segmentos_selecionados
                        )
                        
                    except Exception as e:
                        st.error(f"Erro ao gerar resposta: {str(e)}")

# ========== ABA: GERENCIAMENTO DE AGENTES ==========
with tab_gerenciamento:
    st.header("⚙️ Gerenciamento de Agentes")
    
    # Verificar autenticação apenas para gerenciamento
    if st.session_state.user != "admin":
        st.warning("Acesso restrito a administradores")
    else:
        # Verificar senha de admin
        if not check_admin_password():
            st.warning("Digite a senha de administrador")
        else:
            # Mostra o botão de logout admin
            if st.button("Logout Admin", key="admin_logout"):
                if "admin_password_correct" in st.session_state:
                    del st.session_state["admin_password_correct"]
                if "admin_user" in st.session_state:
                    del st.session_state["admin_user"]
                st.rerun()
            
            st.write(f'Bem-vindo administrador!')
            
            # Subabas para gerenciamento
            sub_tab1, sub_tab2, sub_tab3 = st.tabs(["Criar Agente", "Editar Agente", "Gerenciar Agentes"])
            
            with sub_tab1:
                st.subheader("Criar Novo Agente")
                
                with st.form("form_criar_agente"):
                    nome_agente = st.text_input("Nome do Agente:")
                    
                    # Seleção de categoria
                    categoria = st.selectbox(
                        "Categoria:",
                        ["Social", "SEO", "Conteúdo"],
                        help="Organize o agente por área de atuação"
                    )
                    
                    # Opção para criar como agente filho
                    criar_como_filho = st.checkbox("Criar como agente filho (herdar elementos)")
                    
                    agente_mae_id = None
                    herdar_elementos = []
                    
                    if criar_como_filho:
                        # Listar TODOS os agentes disponíveis para herança
                        agentes_mae = listar_agentes_para_heranca()
                        if agentes_mae:
                            agente_mae_options = {f"{agente['nome']} ({agente.get('categoria', 'Social')})": agente['_id'] for agente in agentes_mae}
                            agente_mae_selecionado = st.selectbox(
                                "Agente Mãe:",
                                list(agente_mae_options.keys()),
                                help="Selecione o agente do qual este agente irá herdar elementos"
                            )
                            agente_mae_id = agente_mae_options[agente_mae_selecionado]
                            
                            st.subheader("Elementos para Herdar"
                            herdar_elementos = st.multiselect(
                                "Selecione os elementos a herdar do agente mãe:",
                                ["system_prompt", "base_conhecimento", "comments", "planejamento"],
                                help="Estes elementos serão herdados do agente mãe se não preenchidos abaixo"
                            )
                        else:
                            st.info("Nenhum agente disponível para herança. Crie primeiro um agente mãe.")
                    
                    system_prompt = st.text_area("Prompt de Sistema:", height=150, 
                                                placeholder="Ex: Você é um assistente especializado em...",
                                                help="Deixe vazio se for herdar do agente mãe")
                    base_conhecimento = st.text_area("Brand Guidelines:", height=200,
                                                   placeholder="Cole aqui informações, diretrizes, dados...",
                                                   help="Deixe vazio se for herdar do agente mãe")
                    comments = st.text_area("Comentários do cliente:", height=200,
                                                   placeholder="Cole aqui os comentários de ajuste do cliente (Se houver)",
                                                   help="Deixe vazio se for herdar do agente mãe")
                    planejamento = st.text_area("Planejamento:", height=200,
                                               placeholder="Estratégias, planejamentos, cronogramas...",
                                               help="Deixe vazio se for herdar do agente mãe")
                    
                    submitted = st.form_submit_button("Criar Agente")
                    if submitted:
                        if nome_agente:
                            agente_id = criar_agente(
                                nome_agente, 
                                system_prompt, 
                                base_conhecimento, 
                                comments, 
                                planejamento,
                                categoria,
                                agente_mae_id if criar_como_filho else None,
                                herdar_elementos if criar_como_filho else []
                            )
                            st.success(f"Agente '{nome_agente}' criado com sucesso na categoria {categoria}!")
                        else:
                            st.error("Nome é obrigatório!")
            
            with sub_tab2:
                st.subheader("Editar Agente Existente")
                
                agentes = listar_agentes()
                if agentes:
                    agente_options = {agente['nome']: agente for agente in agentes}
                    agente_selecionado_nome = st.selectbox("Selecione o agente para editar:", 
                                                         list(agente_options.keys()))
                    
                    if agente_selecionado_nome:
                        agente = agente_options[agente_selecionado_nome]
                        
                        with st.form("form_editar_agente"):
                            novo_nome = st.text_input("Nome do Agente:", value=agente['nome'])
                            
                            # Categoria
                            nova_categoria = st.selectbox(
                                "Categoria:",
                                ["Social", "SEO", "Conteúdo"],
                                index=["Social", "SEO", "Conteúdo"].index(agente.get('categoria', 'Social')),
                                help="Organize o agente por área de atuação"
                            )
                            
                            # Informações de herança
                            if agente.get('agente_mae_id'):
                                agente_mae = obter_agente(agente['agente_mae_id'])
                                if agente_mae:
                                    st.info(f"🔗 Este agente é filho de: {agente_mae['nome']}")
                                    st.write(f"Elementos herdados: {', '.join(agente.get('herdar_elementos', []))}")
                            
                            # Opção para tornar independente
                            if agente.get('agente_mae_id'):
                                tornar_independente = st.checkbox("Tornar agente independente (remover herança)")
                                if tornar_independente:
                                    agente_mae_id = None
                                    herdar_elementos = []
                                else:
                                    agente_mae_id = agente.get('agente_mae_id')
                                    herdar_elementos = agente.get('herdar_elementos', [])
                            else:
                                agente_mae_id = None
                                herdar_elementos = []
                                # Opção para adicionar herança
                                adicionar_heranca = st.checkbox("Adicionar herança de agente mãe")
                                if adicionar_heranca:
                                    # Listar TODOS os agentes disponíveis para herança (excluindo o próprio)
                                    agentes_mae = listar_agentes_para_heranca(agente['_id'])
                                    if agentes_mae:
                                        agente_mae_options = {f"{agente_mae['nome']} ({agente_mae.get('categoria', 'Social')})": agente_mae['_id'] for agente_mae in agentes_mae}
                                        if agente_mae_options:
                                            agente_mae_selecionado = st.selectbox(
                                                "Agente Mãe:",
                                                list(agente_mae_options.keys()),
                                                help="Selecione o agente do qual este agente irá herdar elementos"
                                            )
                                            agente_mae_id = agente_mae_options[agente_mae_selecionado]
                                            herdar_elementos = st.multiselect(
                                                "Elementos para herdar:",
                                                ["system_prompt", "base_conhecimento", "comments", "planejamento"],
                                                default=herdar_elementos
                                            )
                                        else:
                                            st.info("Nenhum agente disponível para herança.")
                                    else:
                                        st.info("Nenhum agente disponível para herança.")
                            
                            novo_prompt = st.text_area("Prompt de Sistema:", value=agente['system_prompt'], height=150)
                            nova_base = st.text_area("Brand Guidelines:", value=agente.get('base_conhecimento', ''), height=200)
                            nova_comment = st.text_area("Comentários:", value=agente.get('comments', ''), height=200)
                            novo_planejamento = st.text_area("Planejamento:", value=agente.get('planejamento', ''), height=200)
                            
                            submitted = st.form_submit_button("Atualizar Agente")
                            if submitted:
                                if novo_nome:
                                    atualizar_agente(
                                        agente['_id'], 
                                        novo_nome, 
                                        novo_prompt, 
                                        nova_base, 
                                        nova_comment, 
                                        novo_planejamento,
                                        nova_categoria,
                                        agente_mae_id,
                                        herdar_elementos
                                    )
                                    st.success(f"Agente '{novo_nome}' atualizado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("Nome é obrigatório!")
                else:
                    st.info("Nenhum agente criado ainda.")
            
            with sub_tab3:
                st.subheader("Gerenciar Agentes")
                
                # Filtros por categoria
                categorias = ["Todos", "Social", "SEO", "Conteúdo"]
                categoria_filtro = st.selectbox("Filtrar por categoria:", categorias)
                
                agentes = listar_agentes()
                
                # Aplicar filtro
                if categoria_filtro != "Todos":
                    agentes = [agente for agente in agentes if agente.get('categoria') == categoria_filtro]
                
                if agentes:
                    for i, agente in enumerate(agentes):
                        with st.container():
                            st.write(f"**{agente['nome']} - {agente.get('categoria', 'Social')} - Criado em {agente['data_criacao'].strftime('%d/%m/%Y')}**")
                            
                            # Mostrar informações de herança
                            if agente.get('agente_mae_id'):
                                agente_mae = obter_agente(agente['agente_mae_id'])
                                if agente_mae:
                                    st.write(f"**🔗 Herda de:** {agente_mae['nome']}")
                                    st.write(f"**Elementos herdados:** {', '.join(agente.get('herdar_elementos', []))}")
                            
                            st.write(f"**Prompt de Sistema:** {agente['system_prompt'][:100]}..." if agente['system_prompt'] else "**Prompt de Sistema:** (herdado ou vazio)")
                            if agente.get('base_conhecimento'):
                                st.write(f"**Brand Guidelines:** {agente['base_conhecimento'][:200]}...")
                            if agente.get('comments'):
                                st.write(f"**Comentários do cliente:** {agente['comments'][:200]}...")
                            if agente.get('planejamento'):
                                st.write(f"**Planejamento:** {agente['planejamento'][:200]}...")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Selecionar para Chat", key=f"select_{i}"):
                                    st.session_state.agente_selecionado = obter_agente_com_heranca(agente['_id'])
                                    st.session_state.messages = []
                                    st.success(f"Agente '{agente['nome']}' selecionado!")
                            with col2:
                                if st.button("Desativar", key=f"delete_{i}"):
                                    desativar_agente(agente['_id'])
                                    st.success(f"Agente '{agente['nome']}' desativado!")
                                    st.rerun()
                            st.divider()
                else:
                    st.info("Nenhum agente encontrado para esta categoria.")

# ========== ABA: GERAÇÃO DE BRIEFING ==========
with tab_briefing:
    st.header("📋 Gerador de Briefing")
    st.caption("Crie briefings completos para diferentes áreas de atuação")
    
    # Conexão com MongoDB para briefings
    try:
        client2 = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
        db_briefings = client2['briefings_Broto_Tecnologia']
        collection_briefings = db_briefings['briefings']
        mongo_connected = True
    except Exception as e:
        st.error(f"Erro na conexão com MongoDB: {str(e)}")
        mongo_connected = False
    
    # Tipos de briefing disponíveis organizados por categoria
    tipos_briefing = {
        "Social": [
            "Post único",
            "Planejamento Mensal"
        ],
        "CRM": [
            "Planejamento de CRM",
            "Fluxo de Nutrição",
            "Email Marketing"
        ],
        "Mídias": [
            "Campanha de Mídia"
        ],
        "Tech": [
            "Manutenção de Site",
            "Construção de Site",
            "Landing Page"
        ],
        "Analytics": [
            "Dashboards"
        ],
        "Design": [
            "Social",
            "CRM",
            "Mídia",
            "KV/Identidade Visual"
        ],
        "Redação": [
            "Email Marketing",
            "Site",
            "Campanha de Mídias"
        ],
        "Planejamento": [
            "Relatórios",
            "Estratégico",
            "Concorrência"
        ]
    }

    # Aba de configuração
    tab_new, tab_saved = st.tabs(["Novo Briefing", "Briefings Salvos"])
        
    with tab_new:
        # Seleção hierárquica do tipo de briefing
        categoria = st.selectbox("Categoria:", list(tipos_briefing.keys()))
        tipo_briefing = st.selectbox("Tipo de Briefing:", tipos_briefing[categoria])
        
        # Campos comuns a todos os briefings
        st.subheader("Informações Básicas")
        nome_projeto = st.text_input("Nome do Projeto:")
        responsavel = st.text_input("Responsável pelo Briefing:")
        data_entrega = st.date_input("Data de Entrega Prevista:")
        objetivo_geral = st.text_area("Objetivo Geral:")
        obs = st.text_area("Observações")
        
        # Seção dinâmica baseada no tipo de briefing
        st.subheader("Informações Específicas")
        
        # Dicionário para armazenar todos os campos
        campos_briefing = {
            "basicos": {
                "nome_projeto": nome_projeto,
                "responsavel": responsavel,
                "data_entrega": str(data_entrega),
                "objetivo_geral": objetivo_geral,
                "obs": obs
            },
            "especificos": {}
        }
            
        # Função para criar campos dinâmicos com seleção
        def criar_campo_selecionavel(rotulo, tipo="text_area", opcoes=None, padrao=None, key_suffix=""):
            # Cria uma chave única baseada no rótulo e sufixo
            key = f"{rotulo}_{key_suffix}_{tipo}"
            
            # Inicializa o valor no session_state se não existir
            if key not in st.session_state:
                st.session_state[key] = padrao if padrao is not None else ""
            
            col1, col2 = st.columns([4, 1])
            valor = None
            
            with col1:
                if tipo == "text_area":
                    valor = st.text_area(rotulo, value=st.session_state[key], key=f"input_{key}")
                elif tipo == "text_input":
                    valor = st.text_input(rotulo, value=st.session_state[key], key=f"input_{key}")
                elif tipo == "selectbox":
                    valor = st.selectbox(rotulo, opcoes, index=opcoes.index(st.session_state[key]) if st.session_state[key] in opcoes else 0, key=f"input_{key}")
                elif tipo == "multiselect":
                    valor = st.multiselect(rotulo, opcoes, default=st.session_state[key], key=f"input_{key}")
                elif tipo == "date_input":
                    valor = st.date_input(rotulo, value=st.session_state[key], key=f"input_{key}")
                elif tipo == "number_input":
                    valor = st.number_input(rotulo, value=st.session_state[key], key=f"input_{key}")
                elif tipo == "file_uploader":
                    return st.file_uploader(rotulo, key=f"input_{key}")  # Retorna direto pois não pode ser salvo no MongoDB
            
            with col2:
                incluir = st.checkbox("", value=True, key=f"incluir_{key}")
                auto_preencher = st.button("🪄", key=f"auto_{key}", help="Preencher automaticamente com LLM")
            
            if auto_preencher:
                # Carrega contexto do data.txt
                try:
                    with open("data.txt", "r") as f:
                        contexto = f.read()
                except:
                    contexto = "Contexto não disponível"
                
                prompt = f"Com base no seguinte contexto:\n{contexto}\n\n E o objetivo do briefing {objetivo_geral} \n\nPreencha o campo '{rotulo}' para um briefing do tipo {tipo_briefing}. Retorne APENAS o valor para o campo, sem comentários ou formatação adicional."
                
                try:
                    resposta = modelo_texto.generate_content(prompt)
                    # Atualiza o session_state com a resposta da LLM
                    st.session_state[key] = resposta.text
                    # Força o rerun para atualizar a interface
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gerar sugestão: {str(e)}")
                    st.session_state[key] = ""
            
            # Atualiza o valor no session_state se foi modificado manualmente
            if valor is not None and valor != st.session_state[key]:
                st.session_state[key] = valor
            
            return st.session_state[key] if incluir else None

        # ========== SOCIAL ==========
        if tipo_briefing == "Post único":
            campos_briefing['especificos']['fotos'] = criar_campo_selecionavel("Sugestão de Fotos necessárias:")
            campos_briefing['especificos']['texto'] = criar_campo_selecionavel("Sugestão de Texto do post:")
            campos_briefing['especificos']['expectativa'] = criar_campo_selecionavel("Sugestão de Expectativa de resultado:")
            campos_briefing['especificos']['tom_voz'] = criar_campo_selecionavel("Sugestão de Tom de voz:")
            campos_briefing['especificos']['direcionamento_arte'] = criar_campo_selecionavel("Sugestão de Direcionamento para a arte (KV):")
            campos_briefing['especificos']['palavras_chave'] = criar_campo_selecionavel("Sugestão de Palavras/conceitos-chave:")
            campos_briefing['especificos']['do_donts'] = criar_campo_selecionavel("Sugestão de Do's and Don'ts:")
            campos_briefing['especificos']['referencias'] = criar_campo_selecionavel("Sugestão de Referências:")
            campos_briefing['especificos']['materiais_extras'] = criar_campo_selecionavel("Sugestão de Materiais extras:")
            campos_briefing['especificos']['info_sensiveis'] = criar_campo_selecionavel("Sugestão de Informações sensíveis:")
            
            if st.checkbox("É sobre produtos?"):
                campos_briefing['especificos']['produtos_destaque'] = criar_campo_selecionavel("Sugestão de Produtos para destacar:")
        
        elif tipo_briefing == "Planejamento Mensal":
            campos_briefing['especificos']['eventos_mes'] = criar_campo_selecionavel("Sugestão de Eventos do mês:")
            campos_briefing['especificos']['datas_comemorativas'] = criar_campo_selecionavel("Sugestão de Datas/comemorações:")
            campos_briefing['especificos']['expectativa_mensal'] = criar_campo_selecionavel("Sugestão de Expectativa de resultados:")
            campos_briefing['especificos']['planejamento_conteudos'] = criar_campo_selecionavel("Sugestão de Conteúdos planejados:")
            campos_briefing['especificos']['produtos_temas'] = criar_campo_selecionavel("Sugestão de Produtos/temas técnicos:")
            campos_briefing['especificos']['planejamento_anual'] = criar_campo_selecionavel("Sugestão de Planejamento anual aprovado:", "file_uploader")
            campos_briefing['especificos']['manuais'] = criar_campo_selecionavel("Sugestão de Manuais de conteúdo disponíveis:")
        
        # ========== CRM ==========
        elif tipo_briefing == "Planejamento de CRM":
            campos_briefing['especificos']['escopo'] = criar_campo_selecionavel("Escopo contratado:")
            campos_briefing['especificos']['ferramenta_crm'] = criar_campo_selecionavel("Ferramenta de CRM utilizada:")
            campos_briefing['especificos']['maturidade'] = criar_campo_selecionavel("Maturidade de CRM:", "selectbox", 
                                                                                 ["Iniciante", "Intermediário", "Avançado"])
            campos_briefing['especificos']['objetivo_crm'] = criar_campo_selecionavel("Objetivo com CRM:")
            campos_briefing['especificos']['canais'] = criar_campo_selecionavel("Canais disponíveis:", "multiselect", 
                                                                              ["Email", "SMS", "WhatsApp", "Mídia Paga"])
            campos_briefing['especificos']['perfil_empresa'] = criar_campo_selecionavel("Perfil da empresa:", "selectbox", ["B2B", "B2C"])
            campos_briefing['especificos']['metas'] = criar_campo_selecionavel("Metas a serem alcançadas:")
            campos_briefing['especificos']['tamanho_base'] = criar_campo_selecionavel("Tamanho da base:")
            campos_briefing['especificos']['segmentacao'] = criar_campo_selecionavel("Segmentação/público-alvo:")
            campos_briefing['especificos']['tom_voz'] = criar_campo_selecionavel("Tom de voz:")
            campos_briefing['especificos']['fluxos'] = criar_campo_selecionavel("Fluxos/e-mails para trabalhar:")
            
            if st.checkbox("Geração de leads?"):
                campos_briefing['especificos']['sla'] = criar_campo_selecionavel("SLA entre marketing e vendas:")
        
        elif tipo_briefing == "Fluxo de Nutrição":
            campos_briefing['especificos']['gatilho'] = criar_campo_selecionavel("Gatilho de entrada:")
            campos_briefing['especificos']['asset_relacionado'] = criar_campo_selecionavel("Asset/evento relacionado:")
            campos_briefing['especificos']['etapa_funil'] = criar_campo_selecionavel("Etapa do funil:", "selectbox", 
                                                                                  ["Topo", "Meio", "Fundo"])
            campos_briefing['especificos']['canais_fluxo'] = criar_campo_selecionavel("Canais para o fluxo:", "multiselect", 
                                                                                   ["Email", "SMS", "WhatsApp", "Mídia Paga"])
            campos_briefing['especificos']['data_ativacao'] = criar_campo_selecionavel("Data de ativação esperada:", "date_input")
            campos_briefing['especificos']['objetivo_fluxo'] = criar_campo_selecionavel("Objetivo do fluxo:")
            campos_briefing['especificos']['resultado_esperado'] = criar_campo_selecionavel("Resultado final esperado:")

        elif tipo_briefing == "Email Marketing":
            campos_briefing['especificos']['publico_email'] = criar_campo_selecionavel("Público e segmentação:")
            campos_briefing['especificos']['data_disparo'] = criar_campo_selecionavel("Data de disparo:", "date_input")
            campos_briefing['especificos']['horario_preferencial'] = criar_campo_selecionavel("Horário preferencial:", "text_input")
            campos_briefing['especificos']['objetivo_email'] = criar_campo_selecionavel("Objetivo:")
            campos_briefing['especificos']['resultado_esperado'] = criar_campo_selecionavel("Resultado final esperado:")
            campos_briefing['especificos']['psd_figma'] = criar_campo_selecionavel("Arquivo PSD/Figma do email:", "file_uploader")
            campos_briefing['especificos']['google_doc'] = criar_campo_selecionavel("Link do Google Doc com conteúdo:", "text_input")
            campos_briefing['especificos']['links_videos'] = criar_campo_selecionavel("Links de vídeos:")
            campos_briefing['especificos']['ctas'] = criar_campo_selecionavel("CTAs:")

        elif tipo_briefing == "Campanha de Mídia":
            campos_briefing['especificos']['periodo_acao'] = criar_campo_selecionavel("Período da ação:", "text_input")
            campos_briefing['especificos']['orcamento'] = criar_campo_selecionavel("Orçamento (R$):", "number_input")
            campos_briefing['especificos']['mecanismo_promocional'] = criar_campo_selecionavel("Mecanismo promocional:")
            campos_briefing['especificos']['praca_especifica'] = criar_campo_selecionavel("Praça específica:")
            campos_briefing['especificos']['responsavel_criativo'] = criar_campo_selecionavel("Quem fará os criativos:", "selectbox", 
                                                                                           ["Macfor", "Cliente"])
            campos_briefing['especificos']['materiais'] = criar_campo_selecionavel("Materiais (copies e peças criativas):")
            campos_briefing['especificos']['objetivo_acao'] = criar_campo_selecionavel("Objetivo da ação:")
            campos_briefing['especificos']['meta'] = criar_campo_selecionavel("Meta:")
            campos_briefing['especificos']['plataformas'] = criar_campo_selecionavel("Plataformas:", "multiselect", 
                                                                                  ["Facebook", "Instagram", "Google Ads", "LinkedIn"])
            campos_briefing['especificos']['segmentacao'] = criar_campo_selecionavel("Segmentação:")
            campos_briefing['especificos']['link_destino'] = criar_campo_selecionavel("Link de destino:", "text_input")

        elif tipo_briefing == "Manutenção de Site":
            st.markdown("**Descreva a demanda usando 5W2H:**")
            campos_briefing['especificos']['what'] = criar_campo_selecionavel("O que precisa ser feito?")
            campos_briefing['especificos']['why'] = criar_campo_selecionavel("Por que é necessário?")
            campos_briefing['especificos']['where'] = criar_campo_selecionavel("Onde deve ser implementado?")
            campos_briefing['especificos']['when'] = criar_campo_selecionavel("Quando precisa estar pronto?")
            campos_briefing['especificos']['who'] = criar_campo_selecionavel("Quem será impactado?")
            campos_briefing['especificos']['how'] = criar_campo_selecionavel("Como deve funcionar?")
            campos_briefing['especificos']['how_much'] = criar_campo_selecionavel("Qual o esforço estimado?")
            campos_briefing['especificos']['descricao_alteracao'] = criar_campo_selecionavel("Descrição detalhada da alteração:")
            campos_briefing['especificos']['prints'] = criar_campo_selecionavel("Anexar prints (se aplicável):", "file_uploader")
            campos_briefing['especificos']['link_referencia'] = criar_campo_selecionavel("Link de referência:", "text_input")
            
            if st.checkbox("É cliente novo?"):
                campos_briefing['especificos']['acessos'] = criar_campo_selecionavel("Acessos (servidor, CMS, etc.):")

        elif tipo_briefing == "Construção de Site":
            campos_briefing['especificos']['acessos'] = criar_campo_selecionavel("Acessos (servidor, nuvens, repositórios, CMS):")
            campos_briefing['especificos']['dominio'] = criar_campo_selecionavel("Domínio:", "text_input")
            campos_briefing['especificos']['prototipo'] = criar_campo_selecionavel("Protótipo em Figma:", "file_uploader")
            campos_briefing['especificos']['conteudos'] = criar_campo_selecionavel("Conteúdos (textos, banners, vídeos):")
            campos_briefing['especificos']['plataforma'] = criar_campo_selecionavel("Plataforma:", "selectbox", 
                                                                                 ["WordPress", "React", "Vue.js", "Outra"])
            campos_briefing['especificos']['hierarquia'] = criar_campo_selecionavel("Hierarquia de páginas:")
            
            if st.checkbox("Incluir otimização SEO?"):
                campos_briefing['especificos']['seo'] = True
                campos_briefing['especificos']['palavras_chave'] = criar_campo_selecionavel("Palavras-chave principais:")
            else:
                campos_briefing['especificos']['seo'] = False

        elif tipo_briefing == "Landing Page":
            campos_briefing['especificos']['objetivo_lp'] = criar_campo_selecionavel("Objetivo da LP:")
            campos_briefing['especificos']['plataforma'] = criar_campo_selecionavel("Plataforma de desenvolvimento:", "text_input")
            campos_briefing['especificos']['integracao_site'] = criar_campo_selecionavel("Precisa integrar com site existente?", "selectbox", 
                                                                                      ["Sim", "Não"])
            campos_briefing['especificos']['dados_coletar'] = criar_campo_selecionavel("Dados a serem coletados no formulário:")
            campos_briefing['especificos']['destino_dados'] = criar_campo_selecionavel("Onde os dados serão gravados:")
            campos_briefing['especificos']['kv_referencia'] = criar_campo_selecionavel("KV de referência:", "file_uploader")
            campos_briefing['especificos']['conteudos_pagina'] = criar_campo_selecionavel("Conteúdos da página:")
            campos_briefing['especificos']['menu'] = criar_campo_selecionavel("Menu/barra de navegação:")
            campos_briefing['especificos']['header_footer'] = criar_campo_selecionavel("Header e Footer:")
            campos_briefing['especificos']['comunicar'] = criar_campo_selecionavel("O que deve ser comunicado:")
            campos_briefing['especificos']['nao_comunicar'] = criar_campo_selecionavel("O que não deve ser comunicado:")
            campos_briefing['especificos']['observacoes'] = criar_campo_selecionavel("Observações:")

        elif tipo_briefing == "Dashboards":
            st.markdown("**Acessos:**")
            campos_briefing['especificos']['google_access'] = st.checkbox("Solicitar acesso Google Analytics")
            campos_briefing['especificos']['meta_access'] = st.checkbox("Solicitar acesso Meta Ads")
            campos_briefing['especificos']['outros_acessos'] = criar_campo_selecionavel("Outros acessos necessários:")
            
            st.markdown("**Requisitos do Dashboard:**")
            campos_briefing['especificos']['okrs'] = criar_campo_selecionavel("OKRs e metas:")
            campos_briefing['especificos']['dados_necessarios'] = criar_campo_selecionavel("Dados que precisam ser exibidos:")
            campos_briefing['especificos']['tipos_graficos'] = criar_campo_selecionavel("Tipos de gráficos preferidos:", "multiselect", 
                                                                                      ["Barras", "Linhas", "Pizza", "Mapas", "Tabelas"])
            campos_briefing['especificos']['atualizacao'] = criar_campo_selecionavel("Frequência de atualização:", "selectbox", 
                                                                                  ["Tempo real", "Diária", "Semanal", "Mensal"])

        elif tipo_briefing == "Social (Design)":
            campos_briefing['especificos']['formato'] = criar_campo_selecionavel("Formato:", "selectbox", ["Estático", "Motion"])
            campos_briefing['especificos']['kv'] = criar_campo_selecionavel("KV a ser seguido:", "file_uploader")
            campos_briefing['especificos']['linha_criativa'] = criar_campo_selecionavel("Linha criativa:")
            campos_briefing['especificos']['usar_fotos'] = criar_campo_selecionavel("Usar fotos?", "selectbox", ["Sim", "Não"])
            campos_briefing['especificos']['referencias'] = criar_campo_selecionavel("Referências:")
            campos_briefing['especificos']['identidade_visual'] = criar_campo_selecionavel("Elementos de identidade visual:")
            campos_briefing['especificos']['texto_arte'] = criar_campo_selecionavel("Texto da arte:")

        elif tipo_briefing == "CRM (Design)":
            st.info("Layouts simples são mais eficientes para CRM!")
            campos_briefing['especificos']['referencias'] = criar_campo_selecionavel("Referências visuais:")
            campos_briefing['especificos']['tipografia'] = criar_campo_selecionavel("Tipografia preferencial:", "text_input")
            campos_briefing['especificos']['ferramenta_envio'] = criar_campo_selecionavel("Ferramenta de CRM que enviará a arte:", "text_input")
            campos_briefing['especificos']['formato_arte'] = criar_campo_selecionavel("Formato da arte:", "selectbox", ["Imagem", "HTML"])

        elif tipo_briefing == "Mídia (Design)":
            campos_briefing['especificos']['formato'] = criar_campo_selecionavel("Formato:", "selectbox", ["Horizontal", "Vertical", "Quadrado"])
            campos_briefing['especificos']['tipo_peca'] = criar_campo_selecionavel("Tipo de peça:", "selectbox", 
                                                                                 ["Arte estática", "Carrossel", "Motion"])
            campos_briefing['especificos']['direcionamento'] = criar_campo_selecionavel("Direcionamento de conteúdo:")
            campos_briefing['especificos']['num_pecas'] = criar_campo_selecionavel("Número de peças:", "number_input", padrao=1)
            campos_briefing['especificos']['publico'] = criar_campo_selecionavel("Público-alvo:")
            campos_briefing['especificos']['objetivo'] = criar_campo_selecionavel("Objetivo:")
            campos_briefing['especificos']['referencias_concorrentes'] = criar_campo_selecionavel("Referências de concorrentes:")

        elif tipo_briefing == "KV/Identidade Visual":
            campos_briefing['especificos']['info_negocio'] = criar_campo_selecionavel("Informações do negócio:")
            campos_briefing['especificos']['referencias'] = criar_campo_selecionavel("Referências:")
            campos_briefing['especificos']['restricoes'] = criar_campo_selecionavel("O que não fazer (cores, elementos proibidos):")
            campos_briefing['especificos']['manual_anterior'] = criar_campo_selecionavel("Manual de marca anterior:", "file_uploader")
            campos_briefing['especificos']['imagem_transmitir'] = criar_campo_selecionavel("Qual imagem queremos transmitir?")
            campos_briefing['especificos']['tema_campanha'] = criar_campo_selecionavel("Tema da campanha:")
            campos_briefing['especificos']['publico'] = criar_campo_selecionavel("Público-alvo:")
            campos_briefing['especificos']['tom_voz'] = criar_campo_selecionavel("Tom de voz:")
            campos_briefing['especificos']['banco_imagens'] = criar_campo_selecionavel("Tipo de imagens:", "selectbox", 
                                                                                    ["Banco de imagens", "Pessoas reais"])
            campos_briefing['especificos']['limitacoes'] = criar_campo_selecionavel("Limitações de uso:")

        elif tipo_briefing == "Email Marketing (Redação)":
            campos_briefing['especificos']['objetivo_email'] = criar_campo_selecionavel("Objetivo:")
            campos_briefing['especificos']['produtos'] = criar_campo_selecionavel("Produtos a serem divulgados:")
            campos_briefing['especificos']['estrutura'] = criar_campo_selecionavel("Estrutura desejada:")
            campos_briefing['especificos']['cta'] = criar_campo_selecionavel("CTA desejado:")
            campos_briefing['especificos']['link_cta'] = criar_campo_selecionavel("Link para o CTA:", "text_input")
            campos_briefing['especificos']['parte_campanha'] = criar_campo_selecionavel("Faz parte de campanha maior?", "selectbox", 
                                                                                      ["Sim", "Não"])

        elif tipo_briefing == "Site (Redação)":
            campos_briefing['especificos']['objetivo_site'] = criar_campo_selecionavel("Objetivo:")
            campos_briefing['especificos']['informacoes'] = criar_campo_selecionavel("Quais informações precisa ter:")
            campos_briefing['especificos']['links'] = criar_campo_selecionavel("Links necessários:")
            campos_briefing['especificos']['wireframe'] = criar_campo_selecionavel("Wireframe do site:", "file_uploader")
            campos_briefing['especificos']['tamanho_texto'] = criar_campo_selecionavel("Tamanho do texto:", "selectbox", 
                                                                                    ["Curto", "Médio", "Longo"])
            
            if st.checkbox("É site novo?"):
                campos_briefing['especificos']['insumos'] = criar_campo_selecionavel("Insumos sobre a empresa/projeto:")

        elif tipo_briefing == "Campanha de Mídias (Redação)":
            campos_briefing['especificos']['objetivo_campanha'] = criar_campo_selecionavel("Objetivo:")
            campos_briefing['especificos']['plataformas'] = criar_campo_selecionavel("Plataformas:", "multiselect", 
                                                                                   ["Facebook", "Instagram", "LinkedIn", "Google"])
            campos_briefing['especificos']['palavras_chave'] = criar_campo_selecionavel("Palavras-chave:")
            campos_briefing['especificos']['tom_voz'] = criar_campo_selecionavel("Tom de voz:")
            campos_briefing['especificos']['publico'] = criar_campo_selecionavel("Público-alvo:")
            campos_briefing['especificos']['cronograma'] = criar_campo_selecionavel("Cronograma:")

        elif tipo_briefing == "Relatórios":
            campos_briefing['especificos']['objetivo_relatorio'] = criar_campo_selecionavel("Objetivo:")
            campos_briefing['especificos']['periodo_analise'] = criar_campo_selecionavel("Período de análise:")
            campos_briefing['especificos']['granularidade'] = criar_campo_selecionavel("Granularidade:", "selectbox", 
                                                                                    ["Diária", "Semanal", "Mensal", "Trimestral"])
            campos_briefing['especificos']['metricas'] = criar_campo_selecionavel("Métricas a serem incluídas:")
            campos_briefing['especificos']['comparativos'] = criar_campo_selecionavel("Comparativos desejados:")

        elif tipo_briefing == "Estratégico":
            campos_briefing['especificos']['introducao'] = criar_campo_selecionavel("Introdução sobre a empresa:")
            campos_briefing['especificos']['orcamento'] = criar_campo_selecionavel("Orçamento (R$):", "number_input")
            campos_briefing['especificos']['publico'] = criar_campo_selecionavel("Público-alvo:")
            campos_briefing['especificos']['objetivo_mkt'] = criar_campo_selecionavel("Objetivo de marketing:")
            campos_briefing['especificos']['etapas_funil'] = criar_campo_selecionavel("Etapas do funil:", "multiselect", 
                                                                                    ["Topo", "Meio", "Fundo"])
            campos_briefing['especificos']['canais'] = criar_campo_selecionavel("Canais disponíveis:", "multiselect", 
                                                                              ["Social", "Email", "Site", "Mídia Paga", "SEO"])
            campos_briefing['especificos']['produtos'] = criar_campo_selecionavel("Produtos/portfólio:")
            campos_briefing['especificos']['metas'] = criar_campo_selecionavel("Metas e métricas:")
            campos_briefing['especificos']['concorrentes'] = criar_campo_selecionavel("Concorrentes:")
            campos_briefing['especificos']['acessos'] = criar_campo_selecionavel("Acessos (GA, Meta Ads, etc.):")
            campos_briefing['especificos']['expectativas'] = criar_campo_selecionavel("Expectativas de resultados:")
            campos_briefing['especificos']['materiais'] = criar_campo_selecionavel("Materiais de apoio:")

        elif tipo_briefing == "Concorrência":
            campos_briefing['especificos']['orcamento'] = criar_campo_selecionavel("Orçamento (R$):", "number_input")
            campos_briefing['especificos']['publico'] = criar_campo_selecionavel("Público-alvo:")
            campos_briefing['especificos']['objetivo'] = criar_campo_selecionavel("Objetivo:")
            campos_briefing['especificos']['etapas_funil'] = criar_campo_selecionavel("Etapas do funil:", "multiselect", 
                                                                                    ["Topo", "Meio", "Fundo"])
            campos_briefing['especificos']['produtos'] = criar_campo_selecionavel("Produtos/portfólio:")
            campos_briefing['especificos']['metas'] = criar_campo_selecionavel("Metas e métricas:")
            campos_briefing['especificos']['concorrentes'] = criar_campo_selecionavel("Concorrentes:")
            campos_briefing['especificos']['acessos'] = criar_campo_selecionavel("Acessos (GA, Meta Ads, etc.):")
            campos_briefing['especificos']['expectativas'] = criar_campo_selecionavel("Expectativas de resultados:")
        
        # Botão para gerar o briefing
        if st.button("🔄 Gerar Briefing Completo", type="primary"):
            with st.spinner('Construindo briefing profissional...'):
                try:
                    # Remove campos None (não selecionados)
                    campos_briefing['especificos'] = {k: v for k, v in campos_briefing['especificos'].items() if v is not None}
                    
                    # Construir o prompt com todas as informações coletadas
                    prompt_parts = [
                        f"# BRIEFING {tipo_briefing.upper()} - Broto",
                        f"**Projeto:** {campos_briefing['basicos']['nome_projeto']}",
                        f"**Responsável:** {campos_briefing['basicos']['responsavel']}",
                        f"**Data de Entrega:** {campos_briefing['basicos']['data_entrega']}",
                        "",
                        "## 1. INFORMAÇÕES BÁSICAS",
                        f"**Objetivo Geral:** {campos_briefing['basicos']['objetivo_geral']}",
                        "",
                        "## 2. INFORMAÇões ESPECÍFICAS"
                    ]
                    
                    # Adicionar campos específicos
                    for campo, valor in campos_briefing['especificos'].items():
                        if isinstance(valor, list):
                            valor = ", ".join(valor)
                        prompt_parts.append(f"**{campo.replace('_', ' ').title()}:** {valor}")
                    
                    prompt = "\n".join(prompt_parts)
                    resposta = modelo_texto.generate_content('Gere o seguinte documento de Briefing EM PORTUGUÊS BRASILEIRO ' + prompt)

                    # Salvar no MongoDB
                    if mongo_connected:
                        briefing_data = {
                            "tipo": tipo_briefing,
                            "categoria": categoria,
                            "nome_projeto": campos_briefing['basicos']['nome_projeto'],
                            "responsavel": campos_briefing['basicos']['responsavel'],
                            "data_criacao": datetime.datetime.now(),
                            "data_entrega": campos_briefing['basicos']['data_entrega'],
                            "conteudo": resposta.text,
                            "campos_preenchidos": campos_briefing,
                            "observacoes": obs,
                        }
                        collection_briefings.insert_one(briefing_data)

                    st.subheader(f"Briefing {tipo_briefing} - {campos_briefing['basicos']['nome_projeto']}")
                    st.markdown(resposta.text)
                                
                    st.download_button(
                        label="📥 Download do Briefing",
                        data=resposta.text,
                        file_name=f"briefing_{tipo_briefing.lower().replace(' ', '_')}_{campos_briefing['basicos']['nome_projeto'].lower().replace(' ', '_')}.txt",
                        mime="text/plain"
                    )
                        
                except Exception as e:
                    st.error(f"Erro ao gerar briefing: {str(e)}")

    with tab_saved:
        st.subheader("Briefings Salvos")
        
        if mongo_connected:
            # Filtros
            col_filtro1, col_filtro2 = st.columns(2)
            with col_filtro1:
                filtro_categoria = st.selectbox("Filtrar por categoria:", ["Todos"] + list(tipos_briefing.keys()), key="filtro_cat")
            with col_filtro2:
                if filtro_categoria == "Todos":
                    tipos_disponiveis = [item for sublist in tipos_briefing.values() for item in sublist]
                    filtro_tipo = st.selectbox("Filtrar por tipo:", ["Todos"] + tipos_disponiveis, key="filtro_tipo")
                else:
                    filtro_tipo = st.selectbox("Filtrar por tipo:", ["Todos"] + tipos_briefing[filtro_categoria], key="filtro_tipo")
            
            # Construir query para MongoDB
            query = {}
            if filtro_categoria != "Todos":
                query["categoria"] = filtro_categoria
            if filtro_tipo != "Todos":
                query["tipo"] = filtro_tipo
            
            # Buscar briefings - adicionei ordenação por data decrescente
            briefings_salvos = list(collection_briefings.find(query).sort("data_criacao", -1).limit(50))
            
            # Debug: mostra quantos documentos foram encontrados
            st.caption(f"Documentos encontrados: {len(briefings_salvos)}")
            
            if not briefings_salvos:
                st.info("Nenhum briefing encontrado com os filtros selecionados")
            else:
                for briefing in briefings_salvos:
                    # Usando um container em vez de expander para evitar o problema de aninhamento
                    with st.container():
                        st.write(f"**{briefing['tipo']} - {briefing['nome_projeto']} ({briefing['data_criacao'].strftime('%d/%m/%Y')})**")
                        st.markdown(briefing['conteudo'])
                        
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.download_button(
                                label="📥 Download",
                                data=briefing['conteudo'],
                                file_name=f"briefing_{briefing['tipo'].lower().replace(' ', '_')}_{briefing['nome_projeto'].lower().replace(' ', '_')}.txt",
                                mime="text/plain",
                                key=f"dl_{briefing['_id']}"
                            )
                        with col2:
                            if st.button("🗑️", key=f"del_{briefing['_id']}"):
                                collection_briefings.delete_one({"_id": briefing['_id']})
                                st.rerun()
                        st.divider()

# ========== ABA: GERAÇÃO DE CONTEÚDO ==========
with tab_conteudo:
    st.header("✨ Geração de Conteúdo")
    
    # Conexão com MongoDB para briefings
    try:
        client2 = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
        db_briefings = client2['briefings_Broto_Tecnologia']
        collection_briefings = db_briefings['briefings']
        mongo_connected_conteudo = True
    except Exception as e:
        st.error(f"Erro na conexão com MongoDB: {str(e)}")
        mongo_connected_conteudo = False
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Entrada do Briefing")
        
        # Opção 1: Selecionar briefing do banco de dados
        st.write("**Selecione um briefing salvo:**")
        if mongo_connected_conteudo:
            briefings_disponiveis = list(collection_briefings.find().sort("data_criacao", -1).limit(20))
            if briefings_disponiveis:
                briefing_options = {f"{briefing['nome_projeto']} ({briefing['tipo']}) - {briefing['data_criacao'].strftime('%d/%m/%Y')}": briefing for briefing in briefings_disponiveis}
                briefing_selecionado = st.selectbox("Escolha um briefing:", list(briefing_options.keys()))
                
                if briefing_selecionado:
                    briefing_data = briefing_options[briefing_selecionado]
                    st.info(f"Briefing selecionado: {briefing_data['nome_projeto']}")
            else:
                st.info("Nenhum briefing encontrado no banco de dados.")
        else:
            st.warning("Conexão com MongoDB não disponível")
        
        # Opção 2: Inserir briefing manualmente
        st.write("**Ou cole o briefing manualmente:**")
        briefing_manual = st.text_area("Cole o briefing completo aqui:", height=200,
                                      placeholder="Exemplo:\nTítulo: Campanha de Lançamento\nObjetivo: Divulgar novo produto\nPúblico-alvo: Empresários...")
    
    with col2:
        st.subheader("⚙️ Configurações")
        
        tipo_conteudo = st.selectbox("Tipo de Conteúdo:", 
                                   ["Post Social", "Artigo Blog", "Email Marketing", "Landing Page", "Script Vídeo"])
        
        tom_voz = st.selectbox("Tom de Voz:", 
                              ["Formal", "Informal", "Persuasivo", "Educativo", "Inspirador"])
        
        palavras_chave = st.text_input("Palavras-chave (opcional):")
        
        numero_palavras = st.slider("Número de Palavras:", 100, 2000, 500)
    
    # Botão para gerar conteúdo
    if st.button("🚀 Gerar Conteúdo", type="primary", use_container_width=True):
        if briefing_manual or ('briefing_data' in locals() and briefing_data):
            with st.spinner("Gerando conteúdo personalizado..."):
                try:
                    # Usar briefing manual se fornecido, caso contrário usar briefing do banco
                    briefing_final = briefing_manual if briefing_manual else briefing_data['conteudo']
                    
                    prompt = f"""
                    Com base no seguinte briefing:
                    
                    {briefing_final}
                    
                    Gere um conteúdo do tipo {tipo_conteudo} com as seguintes características:
                    - Tom de voz: {tom_voz}
                    - Palavras-chave: {palavras_chave if palavras_chave else 'Não especificadas'}
                    - Número aproximado de palavras: {numero_palavras}
                    
                    Estruture o conteúdo de forma profissional e engajadora.
                    """
                    
                    resposta = modelo_texto.generate_content(prompt)
                    
                    st.subheader("📄 Conteúdo Gerado")
                    st.markdown(resposta.text)
                    
                    st.download_button(
                        "💾 Baixar Conteúdo",
                        data=resposta.text,
                        file_name=f"conteudo_gerado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao gerar conteúdo: {str(e)}")
        else:
            st.warning("Por favor, selecione um briefing do banco de dados ou cole um briefing manualmente.")

# ========== ABA: GERAÇÃO DE CONTEÚDO BLOG AGRÍCOLA ==========
with tab_blog:
    st.title("🌱 Gerador de Blog Posts Agrícolas")
    st.markdown("Crie conteúdos especializados para o agronegócio seguindo a estrutura profissional")

    # Conexão com MongoDB
    try:
        client_mongo = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
        db = client_mongo['blog_posts_agricolas']
        collection_posts = db['posts_gerados']
        collection_briefings = db['briefings']
        collection_kbf = db['kbf_produtos']
        mongo_connected_blog = True
    except Exception as e:
        st.error(f"Erro na conexão com MongoDB: {str(e)}")
        mongo_connected_blog = False

    # Funções para o banco de dados
    def salvar_post(titulo, cultura, editoria, mes_publicacao, objetivo_post, url, texto_gerado, palavras_chave, palavras_proibidas, tom_voz, estrutura, palavras_contagem, meta_title, meta_descricao, linha_fina):
        if mongo_connected_blog:
            documento = {
                "id": str(uuid.uuid4()),
                "titulo": titulo,
                "cultura": cultura,
                "editoria": editoria,
                "mes_publicacao": mes_publicacao,
                "objetivo_post": objetivo_post,
                "url": url,
                "texto_gerado": texto_gerado,
                "palavras_chave": palavras_chave,
                "palavras_proibidas": palavras_proibidas,
                "tom_voz": tom_voz,
                "estrutura": estrutura,
                "palavras_contagem": palavras_contagem,
                "meta_title": meta_title,
                "meta_descricao": meta_descricao,
                "linha_fina": linha_fina,
                "data_criacao": datetime.now(),
                "versao": "2.0"
            }
            collection_posts.insert_one(documento)
            return True
        return False

    def carregar_kbf_produtos():
        if mongo_connected_blog:
            try:
                kbf_docs = list(collection_kbf.find({}))
                return kbf_docs
            except:
                return []
        return []

    def salvar_briefing(briefing_data):
        if mongo_connected_blog:
            documento = {
                "id": str(uuid.uuid4()),
                "briefing": briefing_data,
                "data_criacao": datetime.now()
            }
            collection_briefings.insert_one(documento)
            return True
        return False

    def carregar_posts_anteriores():
        if mongo_connected_blog:
            try:
                posts = list(collection_posts.find({}).sort("data_criacao", -1).limit(10))
                return posts
            except:
                return []
        return []

    # Função para processar transcrições
    def processar_transcricoes(arquivos):
        transcricoes = []
        for arquivo in arquivos:
            if arquivo is not None:
                # Simulação de processamento de transcrição
                # Em produção, integrar com API de transcrição
                st.info(f"Processando transcrição de: {arquivo.name}")
                transcricoes.append(f"Conteúdo transcrito de {arquivo.name}")
        return "\n\n".join(transcricoes)

    # Regras base do sistema - ATUALIZADAS
    regras_base = '''
    **REGRAS DE REPLICAÇÃO - ESTRUTURA PROFISSIONAL:**

    **1. ESTRUTURA DO DOCUMENTO:**
    - Título principal impactante e com chamada para ação (máx 65 caracteres)
    - Linha fina resumindo o conteúdo (máx 200 caracteres)
    - Meta-title otimizado para SEO (máx 60 caracteres)
    - Meta-descrição atrativa (máx 155 caracteres)
    - Introdução contextualizando o problema e impacto
    - Seção de Problema: Detalhamento técnico dos desafios
    - Seção de Solução Genérica: Estratégia geral de manejo
    - Seção de Solução Específica: Produto como resposta aos desafios
    - Conclusão com reforço de compromisso e chamada para ação
    - Assinatura padrão da empresa

    **2. LINGUAGEM E TOM:**
    - {tom_voz}
    - Linguagem {nivel_tecnico} técnica e profissional
    - Uso de terminologia específica do agronegócio
    - Persuasão baseada em benefícios e solução de problemas
    - Evitar repetição de informações entre seções

    **3. ELEMENTOS TÉCNICOS OBRIGATÓRIOS:**
    - Nomes científicos entre parênteses quando aplicável
    - Citação EXPLÍCITA de fontes confiáveis (Embrapa, universidades, etc.) mencionando o órgão/instituição no corpo do texto
    - Destaque para termos técnicos-chave e nomes de produtos
    - Descrição detalhada de danos e benefícios
    - Dados concretos e informações mensuráveis com referências específicas

    **4. FORMATAÇÃO E ESTRUTURA:**
    - Parágrafos curtos (máximo 4-5 linhas cada)
    - Listas de tópicos com no máximo 5 itens cada
    - Evitar blocos extensos de texto
    - Usar subtítulos para quebrar o conteúdo

    **5. RESTRIÇÕES:**
    - Palavras proibidas: {palavras_proibidas}
    - Evitar viés comercial explícito
    - Manter abordagem {abordagem_problema}
    - Número de palavras: {numero_palavras} (±5%)
    - NÃO INVENTAR SOLUÇÕES ou informações não fornecidas
    - Seguir EXATAMENTE o formato e informações do briefing
    '''

    # CONFIGURAÇÕES DO BLOG (agora dentro da aba)
    st.header("📋 Configurações do Blog Agrícola")
    
    col_config1, col_config2 = st.columns(2)
    
    with col_config1:
        # Modo de entrada - Briefing ou Campos Individuais
        modo_entrada = st.radio("Modo de Entrada:", ["Campos Individuais", "Briefing Completo"])
        
        # Controle de palavras - MAIS RESTRITIVO
        numero_palavras = st.slider("Número de Palavras:", min_value=300, max_value=2500, value=1500, step=100)
        st.info(f"Meta: {numero_palavras} palavras (±5%)")
        
        # Palavras-chave
        st.subheader("🔑 Palavras-chave")
        palavra_chave_principal = st.text_input("Palavra-chave Principal:")
        palavras_chave_secundarias = st.text_area("Palavras-chave Secundárias (separadas por vírgula):")
        
        # Configurações de estilo
        st.subheader("🎨 Configurações de Estilo")
        tom_voz = st.selectbox("Tom de Voz:", ["Jornalístico", "Especialista Técnico", "Educativo", "Persuasivo"])
        nivel_tecnico = st.selectbox("Nível Técnico:", ["Básico", "Intermediário", "Avançado"])
        abordagem_problema = st.text_area("Aborde o problema de tal forma que:", "seja claro, técnico e focando na solução prática para o produtor")
    
    with col_config2:
        # Restrições
        st.subheader("🚫 Restrições")
        palavras_proibidas = st.text_area("Palavras Proibidas (separadas por vírgula):", "melhor, número 1, líder, insuperável, invenção, inventado, solução mágica")
        
        # Estrutura do texto
        st.subheader("📐 Estrutura do Texto")
        estrutura_opcoes = st.multiselect("Seções do Post:", 
                                         ["Introdução", "Problema", "Solução Genérica", "Solução Específica", 
                                          "Benefícios", "Implementação Prática", "Conclusão", "Fontes"],
                                         default=["Introdução", "Problema", "Solução Genérica", "Solução Específica", "Conclusão"])
        
        # KBF de Produtos
        st.subheader("📦 KBF de Produtos")
        kbf_produtos = carregar_kbf_produtos()
        if kbf_produtos:
            produtos_disponiveis = [prod['nome'] for prod in kbf_produtos]
            produto_selecionado = st.selectbox("Selecionar Produto do KBF:", ["Nenhum"] + produtos_disponiveis)
            if produto_selecionado != "Nenhum":
                produto_info = next((prod for prod in kbf_produtos if prod['nome'] == produto_selecionado), None)
                if produto_info:
                    st.info(f"**KBF Fixo:** {produto_info.get('caracteristicas', 'Informações do produto')}")
        else:
            st.info("Nenhum KBF cadastrado no banco de dados")

    # Área principal baseada no modo de entrada
    if modo_entrada == "Campos Individuais":
        col1, col2 = st.columns(2)
        
        with col1:
            st.header("📝 Informações Básicas")
            titulo_blog = st.text_input("Título do Blog:", "Proteja sua soja de nematoides e pragas de solo")
            cultura = st.text_input("Cultura:", "Soja")
            editoria = st.text_input("Editoria:", "Manejo e Proteção")
            mes_publicacao = st.text_input("Mês de Publicação:", "08/2025")
            objetivo_post = st.text_area("Objetivo do Post:", "Explicar a importância do manejo de nematoides e apresentar soluções via tratamento de sementes")
            url = st.text_input("URL:", "/manejo-e-protecao/proteja-sua-soja-de-nematoides")
            
            st.header("🔧 Conteúdo Técnico")
            problema_principal = st.text_area("Problema Principal/Contexto:", "Solos compactados e com palhada de milho têm favorecido a explosão populacional de nematoides")
            pragas_alvo = st.text_area("Pragas/Alvo Principal:", "Nematoide das galhas (Meloidogyne incognita), Nematoide de cisto (Heterodera glycines)")
            danos_causados = st.text_area("Danos Causados:", "Formação de galhas nas raízes que impedem a absorção de água e nutrientes")
            solucao_generica = st.text_area("Solução Genérica:", "Adoção de um manejo integrado com genética resistente, rotação de culturas e tratamento de sementes")
        
        with col2:
            st.header("🏭 Informações da Empresa")
            nome_empresa = st.text_input("Nome da Empresa/Marca:")
            nome_central = st.text_input("Nome da Central de Conteúdos:")
            
            st.header("💡 Soluções e Produtos")
            nome_produto = st.text_input("Nome do Produto:")
            principio_ativo = st.text_input("Princípio Ativo/Diferencial:")
            beneficios_produto = st.text_area("Benefícios do Produto:")
            espectro_acao = st.text_area("Espectro de Ação:")
            
            st.header("🎯 Diretrizes Específicas")
            diretrizes_usuario = st.text_area("Diretrizes Adicionais:", 
                                            "NÃO INVENTE SOLUÇÕES. Use apenas informações fornecidas. Incluir dicas práticas para implementação no campo. Manter linguagem acessível mas técnica.")
            fontes_pesquisa = st.text_area("Fontes para Pesquisa/Referência (cite órgãos específicos):", 
                                         "Embrapa Soja, Universidade de São Paulo - ESALQ, Instituto Biológico de São Paulo, Artigos técnicos sobre nematoides")
            
            # Upload de MÚLTIPLOS arquivos estratégicos
            arquivos_estrategicos = st.file_uploader("📎 Upload de Múltiplos Arquivos Estratégicos", 
                                                   type=['txt', 'pdf', 'docx', 'mp3', 'wav', 'mp4', 'mov'], 
                                                   accept_multiple_files=True)
            if arquivos_estrategicos:
                st.success(f"{len(arquivos_estrategicos)} arquivo(s) carregado(s) com sucesso!")
    
    else:  # Modo Briefing
        st.header("📄 Briefing Completo")
        
        st.warning("""
        **ATENÇÃO:** Para conteúdos técnicos complexos (especialmente Syngenta), 
        recomenda-se usar o modo "Campos Individuais" para melhor controle da qualidade.
        """)
        
        briefing_texto = st.text_area("Cole aqui o briefing completo:", height=300,
                                     placeholder="""EXEMPLO DE BRIEFING:
Título: Controle Eficiente de Nematoides na Soja
Cultura: Soja
Problema: Aumento da população de nematoides em solos com palhada de milho
Objetivo: Educar produtores sobre manejo integrado
Produto: NemaControl
Público-alvo: Produtores de soja técnica
Tom: Técnico-jornalístico
Palavras-chave: nematoide, soja, tratamento sementes, manejo integrado

IMPORTANTE: NÃO INVENTE SOLUÇÕES. Use apenas informações fornecidas aqui.""")
        
        if briefing_texto:
            if st.button("Processar Briefing"):
                salvar_briefing(briefing_texto)
                st.success("Briefing salvo no banco de dados!")

    # Configurações avançadas
    with st.expander("⚙️ Configurações Avançadas"):
        col_av1, col_av2 = st.columns(2)
        
        with col_av1:
            st.subheader("Opcionais")
            usar_pesquisa_web = st.checkbox("🔍 Habilitar Pesquisa Web", value=False)
            gerar_blocos_dinamicos = st.checkbox("🔄 Gerar Blocos Dinamicamente", value=True)
            incluir_fontes = st.checkbox("📚 Incluir Referências de Fontes", value=True)
            incluir_assinatura = st.checkbox("✍️ Incluir Assinatura Padrão", value=True)
            
        with col_av2:
            st.subheader("Controles de Qualidade")
            evitar_repeticao = st.slider("Nível de Evitar Repetição:", 1, 10, 8)
            profundidade_conteudo = st.selectbox("Profundidade do Conteúdo:", ["Superficial", "Moderado", "Detalhado", "Especializado"])
            
            # Configurações de formatação
            st.subheader("📐 Formatação")
            max_paragrafos = st.slider("Máximo de linhas por parágrafo:", 3, 8, 5)
            max_lista_itens = st.slider("Máximo de itens por lista:", 3, 8, 5)
            
            # MÚLTIPLOS arquivos para transcrição
            st.subheader("🎤 Transcrição de Mídia")
            arquivos_midia = st.file_uploader("Áudios/Vídeos para Transcrição (múltiplos)", 
                                            type=['mp3', 'wav', 'mp4', 'mov'], 
                                            accept_multiple_files=True)

    # Metadados para SEO
    st.header("🔍 Metadados para SEO")
    col_meta1, col_meta2 = st.columns(2)
    
    with col_meta1:
        meta_title = st.text_input("Meta Title (máx 60 caracteres):", 
                                 max_chars=60,
                                 help="Título para SEO - aparecerá nos resultados de busca")
        st.info(f"Caracteres: {len(meta_title)}/60")
        
        linha_fina = st.text_area("Linha Fina (máx 200 caracteres):",
                                max_chars=200,
                                help="Resumo executivo que aparece abaixo do título")
        st.info(f"Caracteres: {len(linha_fina)}/200")
    
    with col_meta2:
        meta_descricao = st.text_area("Meta Descrição (máx 155 caracteres):",
                                    max_chars=155,
                                    help="Descrição que aparece nos resultados de busca")
        st.info(f"Caracteres: {len(meta_descricao)}/155")

    # Área de geração
    st.header("🔄 Geração do Conteúdo")
    
    if st.button("🚀 Gerar Blog Post", type="primary", use_container_width=True):
        with st.spinner("Gerando conteúdo... Isso pode levar alguns minutos"):
            try:
                # Processar transcrições se houver arquivos
                transcricoes_texto = ""
                if 'arquivos_midia' in locals() and arquivos_midia:
                    transcricoes_texto = processar_transcricoes(arquivos_midia)
                    st.info(f"Processadas {len(arquivos_midia)} transcrição(ões)")
                
                # Construir prompt personalizado - MAIS RESTRITIVO
                regras_personalizadas = regras_base.format(
                    tom_voz=tom_voz,
                    nivel_tecnico=nivel_tecnico,
                    palavras_proibidas=palavras_proibidas,
                    abordagem_problema=abordagem_problema,
                    numero_palavras=numero_palavras
                )
                
                prompt_final = f"""
                **INSTRUÇÕES PARA CRIAÇÃO DE BLOG POST AGRÍCOLA:**
                
                {regras_personalizadas}
                
                **INFORMAÇÕES ESPECÍFICAS:**
                - Título: {titulo_blog if 'titulo_blog' in locals() else 'A definir'}
                - Cultura: {cultura if 'cultura' in locals() else 'A definir'}
                - Palavra-chave Principal: {palavra_chave_principal}
                - Palavras-chave Secundárias: {palavras_chave_secundarias}
                
                **METADADOS:**
                - Meta Title: {meta_title}
                - Meta Description: {meta_descricao}
                - Linha Fina: {linha_fina}
                
                **CONFIGURAÇÕES DE FORMATAÇÃO:**
                - Parágrafos máximos: {max_paragrafos} linhas
                - Listas máximas: {max_lista_itens} itens
                - Estrutura: {', '.join(estrutura_opcoes)}
                - Profundidade: {profundidade_conteudo}
                - Evitar repetição: Nível {evitar_repeticao}/10
                
                **DIRETRIZES CRÍTICAS:**
                - NÃO INVENTE SOLUÇÕES OU INFORMAÇÕES
                - Use APENAS dados fornecidos no briefing
                - Cite fontes específicas no corpo do texto
                - Mantenha parágrafos e listas CURTOS
                
                **CONTEÚDO DE TRANSCRIÇÕES:**
                {transcricoes_texto if transcricoes_texto else 'Nenhuma transcrição fornecida'}
                
                **DIRETRIZES ADICIONAIS:** {diretrizes_usuario if 'diretrizes_usuario' in locals() else 'Nenhuma'}
                
                Gere um conteúdo {profundidade_conteudo.lower()} com EXATAMENTE {numero_palavras} palavras (±5%).
                """
                
                response = modelo_texto.generate_content(prompt_final)
                
                texto_gerado = response.text
                
                # Verificar contagem de palavras
                palavras_count = len(texto_gerado.split())
                st.info(f"📊 Contagem de palavras geradas: {palavras_count} (meta: {numero_palavras})")
                
                if abs(palavras_count - numero_palavras) > numero_palavras * 0.1:
                    st.warning("⚠️ A contagem de palavras está significativamente diferente da meta")
                
                # Salvar no MongoDB
                if salvar_post(
                    titulo_blog if 'titulo_blog' in locals() else "Título gerado",
                    cultura if 'cultura' in locals() else "Cultura não especificada",
                    editoria if 'editoria' in locals() else "Editoria geral",
                    mes_publicacao if 'mes_publicacao' in locals() else datetime.now().strftime("%m/%Y"),
                    objetivo_post if 'objetivo_post' in locals() else "Objetivo não especificado",
                    url if 'url' in locals() else "/",
                    texto_gerado,
                    f"{palavra_chave_principal}, {palavras_chave_secundarias}",
                    palavras_proibidas,
                    tom_voz,
                    ', '.join(estrutura_opcoes),
                    palavras_count,
                    meta_title,
                    meta_descricao,
                    linha_fina
                ):
                    st.success("✅ Post gerado e salvo no banco de dados!")
                
                st.subheader("📝 Conteúdo Gerado")
                st.markdown(texto_gerado)
                
                st.download_button(
                    "💾 Baixar Post",
                    data=texto_gerado,
                    file_name=f"blog_post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
                
            except Exception as e:
                st.error(f"Erro na geração: {str(e)}")

    # Banco de textos gerados - CORRIGIDO: usando container em vez de expander
    st.header("📚 Banco de Textos Gerados")
    
    posts_anteriores = carregar_posts_anteriores()
    if posts_anteriores:
        for post in posts_anteriores:
            # Usando container em vez de expander para evitar o problema de aninhamento
            with st.container():
                st.write(f"**{post.get('titulo', 'Sem título')} - {post.get('data_criacao', '').strftime('%d/%m/%Y')}**")
                st.write(f"**Cultura:** {post.get('cultura', 'N/A')}")
                st.write(f"**Palavras:** {post.get('palavras_contagem', 'N/A')}")
                
                # Mostrar metadados salvos
                if post.get('meta_title'):
                    st.write(f"**Meta Title:** {post.get('meta_title')}")
                if post.get('meta_descricao'):
                    st.write(f"**Meta Descrição:** {post.get('meta_descricao')}")
                
                st.text_area("Conteúdo:", value=post.get('texto_gerado', ''), height=200, key=post['id'])
                
                col_uso1, col_uso2 = st.columns(2)
                with col_uso1:
                    if st.button("Reutilizar", key=f"reuse_{post['id']}"):
                        st.session_state.texto_gerado = post.get('texto_gerado', '')
                        st.success("Conteúdo carregado para reutilização!")
                with col_uso2:
                    st.download_button(
                        label="📥 Download",
                        data=post.get('texto_gerado', ''),
                        file_name=f"blog_post_{post.get('titulo', 'post').lower().replace(' ', '_')}.txt",
                        mime="text/plain",
                        key=f"dl_btn_{post['id']}"
                    )
                st.divider()
    else:
        st.info("Nenhum post encontrado no banco de dados.")

# ========== ABA: REVISÃO ORTOGRÁFICA ==========
with tab_revisao_ortografica:
    st.header("📝 Revisão Ortográfica")
    
    texto_para_revisao = st.text_area("Cole o texto que deseja revisar:", height=300)
    
    if st.button("🔍 Realizar Revisão Ortográfica", type="primary"):
        if texto_para_revisao:
            with st.spinner("Revisando texto..."):
                try:
                    prompt = f"""
                    Faça uma revisão ortográfica e gramatical completa do seguinte texto:
                    
                    {texto_para_revisao}
                    
                    Forneça:
                    1. Texto revisado com correções aplicadas
                    2. Lista de correções realizadas
                    3. Sugestões de melhorias de estilo
                    """
                    
                    resposta = modelo_texto.generate_content(prompt)
                    st.subheader("📋 Resultado da Revisão")
                    st.markdown(resposta.text)
                    
                except Exception as e:
                    st.error(f"Erro na revisão: {str(e)}")
        else:
            st.warning("Por favor, cole um texto para revisão.")

# ========== ABA: REVISÃO TÉCNICA ==========
with tab_revisao_tecnica:
    st.header("🔧 Revisão Técnica")
    
    texto_tecnico = st.text_area("Cole o conteúdo técnico para revisão:", height=300)
    area_tecnica = st.selectbox("Área Técnica:", 
                               ["Agricultura", "Tecnologia", "Engenharia", "Medicina", "Outra"])
    
    if st.button("🔍 Realizar Revisão Técnica", type="primary"):
        if texto_tecnico:
            with st.spinner("Realizando revisão técnica..."):
                try:
                    prompt = f"""
                    Faça uma revisão técnica especializada em {area_tecnica} do seguinte conteúdo:
                    
                    {texto_tecnico}
                    
                    Verifique:
                    1. Precisão técnica das informações
                    2. Consistência de terminologia
                    3. Clareza nas explicações
                    4. Atualização das referências
                    5. Sugestões de melhorias técnicas
                    """
                    
                    resposta = modelo_texto.generate_content(prompt)
                    st.subheader("📋 Resultado da Revisão Técnica")
                    st.markdown(resposta.text)
                    
                except Exception as e:
                    st.error(f"Erro na revisão técnica: {str(e)}")
        else:
            st.warning("Por favor, cole um conteúdo técnico para revisão.")

# ========== ABA: BRIEFING TÉCNICO ==========
with tab_briefing_tecnico:
    st.header("⚙️ Geração de Briefing Técnico")
    
    # Esta aba pode ser implementada de forma similar à aba de briefing geral
    # mas com foco em briefings técnicos específicos
    st.info("Em desenvolvimento - Briefings Técnicos Especializados")
    
    tipo_briefing_tecnico = st.selectbox("Tipo de Briefing Técnico:", 
                                       ["Documentação Técnica", "Manual de Produto", "Especificações", "Procedimentos"])
    
    st.text_area("Descreva os requisitos técnicos:", height=200,
                placeholder="Descreva os objetivos, requisitos técnicos, especificações, etc...")

# ========== ABA: OTIMIZAÇÃO DE CONTEÚDO ==========
with tab_otimizacao:
    st.header("🚀 Otimização de Conteúdo")
    
    texto_para_otimizar = st.text_area("Cole o conteúdo para otimização:", height=300)
    tipo_otimizacao = st.selectbox("Tipo de Otimização:", 
                                  ["SEO", "Engajamento", "Conversão", "Clareza"])
    
    if st.button("🚀 Otimizar Conteúdo", type="primary"):
        if texto_para_otimizar:
            with st.spinner("Otimizando conteúdo..."):
                try:
                    prompt = f"""
                    Otimize o seguinte conteúdo para {tipo_otimizacao}:
                    
                    {texto_para_otimizar}
                    
                    Forneça:
                    1. Versão otimizada do conteúdo
                    2. Explicação das otimizações realizadas
                    3. Métricas esperadas de melhoria
                    """
                    
                    resposta = modelo_texto.generate_content(prompt)
                    st.subheader("📊 Conteúdo Otimizado")
                    st.markdown(resposta.text)
                    
                except Exception as e:
                    st.error(f"Erro na otimização: {str(e)}")
        else:
            st.warning("Por favor, cole um conteúdo para otimização.")

# --- Estilização ---
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    [data-testid="stChatMessageContent"] {
        font-size: 1rem;
    }
    div[data-testid="stTabs"] {
        margin-top: -30px;
    }
    .segment-indicator {
        background-color: #f0f2f6;
        padding: 0.5rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #4CAF50;
    }
    /* Estilo para o pipeline */
    .pipeline-step {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        border-left: 5px solid #4CAF50;
    }
    .pipeline-complete {
        border-left-color: #4CAF50;
    }
    .pipeline-current {
        border-left-color: #2196F3;
    }
    .pipeline-pending {
        border-left-color: #ff9800;
    }
</style>
""", unsafe_allow_html=True)
