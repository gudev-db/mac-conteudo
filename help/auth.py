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
                        # PROMPT DE OTIMIZAÇÃO AGRO COM SEO KIT
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
                        # Construir prompt de revisão considerando o agente selecionado
                        agente = st.session_state.agente_selecionado
                        contexto_agente = construir_contexto(agente, st.session_state.segmentos_selecionados)
                        
                        prompt_revisao = f"""
                        {contexto_agente}
                        
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
                    file_name=f"conteudo_final_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
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
