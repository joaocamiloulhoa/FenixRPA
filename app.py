import streamlit as st
import pandas as pd
import time
import traceback
from datetime import datetime
from cria_pdf import criar_pdf_streamlit
from lancamento_fenix import executar_lancamento_fenix, get_recomendacao, atualizar_status_planilha, fechar_navegador_manual
from lancamento_fenix_hard import executar_lancamento_fenix_hard, obter_propriedades_por_unf

# Mantendo apenas as funções auxiliares de texto que são usadas pela interface

def get_objetivo_text(nucleo):
    """Retorna o texto do objetivo"""
    return f"O presente relatório foi elaborado por solicitação do GEOCAT com o objetivo de avaliar os efeitos dos sinistros nos plantios do Núcleo {nucleo} e determinar as recomendações para as áreas avaliadas em campo pela área de Mensuração."

def get_diagnostico_text():
    """Retorna o texto de diagnóstico fixo"""
    return (
        "Foi objeto deste Laudo as áreas afetadas por incêndios florestais e vendaval (Déficit Hídrico), conforme as características de danos a seguir:\n\n"
        "Seca e mortalidade dos plantios devido ao fogo ou déficit hídrico em diferentes níveis de severidade;\n\n"
        "Inclinação, tombamento e quebra de árvores devido a ocorrência de vendaval.\n\n"
        "Para as ocorrências foram observados danos em reboleiras de diferentes tamanhos de área (ha) e intensidade dentro dos talhões."
    )

def get_licoes_text():
    """Retorna o texto fixo de lições aprendidas"""
    return (
        "As visitas de campo juntamente com imagens de drones são fundamentais para a tomada de decisão. "
        "As ocorrências de sinistros são dinâmicas e, desta forma, é fundamental aguardar o tempo recomendado para a verificação da recuperação das plantas bem como manter as informações atualizadas, especialmente nas ocorrências de Déficit Hídrico e Incêndios Florestais. "
        "A efetivação da baixa e tratativas devem ocorrer imediatamente após a liberação do laudo, evitando-se retrabalho e dificuldades na rastreabilidade de todo o processo, assim como o comprometimento da produtividade no site."
    )

def get_consideracoes_text():
    """Retorna o texto das considerações finais"""
    return (
        "Face ao exposto, com a avaliação de ha, recomenda-se:\n\n"
        "O valor total imobilizado a ser apurado como prejuízo será de R$ X (XX reais e XXXX centavos), "
        "informado pela área Contábil. Vale ressaltar que o montante descrito pode sofrer alterações "
        "entre o período de emissão, assinaturas e devida baixa dos ativos; no momento da baixa, a "
        "Gestão Patrimonial fará a atualização e manterá comprovação anexa ao laudo. A destinação da "
        "madeira e eventuais dificuldades operacionais não foram objeto deste laudo.\n\n"
        "As recomendações são por UP, considerando a ocorrência de maior abrangência; pode, contudo, "
        "existir mais de um tipo de sinistro na mesma UP, sendo necessária uma avaliação detalhada do "
        "microplanejamento quanto ao aproveitamento da madeira.\n\n"
        "O laudo foi elaborado com base em croquis e fotos fornecidos pela equipe de mensuração florestal. "
        "A ausência de imagens aéreas de alta resolução e a falta de visitas de campo por parte dos "
        "extensionistas prejudicam a avaliação detalhada das UPs. Assim, se a equipe de Silvicultura, "
        "durante a execução das ações recomendadas, constatar divergências em campo, recomenda-se delimitar "
        "a área divergente a ser aproveitada e solicitar uma análise adicional à equipe de extensão tecnológica."
    )

def lancamento_fenix():
    st.header("Lançamento de Informações no Fênix")
    
    # Verificar se há opção de continuar lançamento
    if hasattr(st.session_state, 'mostrar_continuar_lancamento') and st.session_state.mostrar_continuar_lancamento:
        st.success("🎉 Núcleo anterior processado com sucesso!")
        st.info("🔄 Navegador mantido aberto para continuar com outros núcleos")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Continuar com Outro Núcleo", key="continuar_lancamento", type="primary", use_container_width=True):
                st.session_state.mostrar_continuar_lancamento = False
                st.rerun()
        
        with col2:
            if st.button("🔚 Finalizar e Fechar Navegador", key="finalizar_lancamento", use_container_width=True):
                if fechar_navegador_manual():
                    st.success("✅ Navegador fechado com sucesso!")
                    time.sleep(2)
                    st.rerun()
        
        st.markdown("---")
    
    # Upload do arquivo Excel
    uploaded_file = st.file_uploader("Escolha um arquivo Excel", type=['xlsx', 'xls'], key="lancamento_excel_uploader")
    
    if uploaded_file is not None:
        try:
            # Lê o arquivo Excel
            df = pd.read_excel(uploaded_file)
            
            # Verifica se as colunas necessárias existem
            required_columns = [
                'UP', 'Nucleo', 'Idade', 'Ocorrência Predominante',
                'Severidade Predominante', 'Incidencia', 'Laudo Existente',
                'Recomendacao'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                st.error(f"Colunas obrigatórias não encontradas: {', '.join(missing_columns)}")
                st.write("Colunas disponíveis no arquivo:", list(df.columns))
                return
            
            # Filtra apenas registros sem laudo
            df_sem_laudo = df[df['Laudo Existente'].str.upper() == 'NÃO'].copy()
            
            if len(df_sem_laudo) == 0:
                st.warning("Não há registros sem laudo para processar.")
                return
            
            # Seleção do tipo de organização
            st.subheader("📋 Tipo de Organização dos Laudos")
            tipo_organizacao = st.radio(
                "Como deseja organizar os laudos?",
                [
                    "🏢 Por Núcleo (Método Original)",
                    "🏗️ Por Propriedade (Coluna 4 da tabela)"
                ],
                help="Núcleo: Agrupa UPs por núcleo. Propriedade: Agrupa UPs por propriedade (recomendado para laudos específicos por propriedade)."
            )
            
            # Definir coluna de agrupamento baseada na seleção
            if tipo_organizacao.startswith("🏗️ Por Propriedade"):
                # Usar coluna 4 (índice 3) como coluna de propriedade
                coluna_agrupamento = df.columns[3]  # Coluna 4 (índice base 0)
                st.info(f"✅ Usando coluna de propriedade: **{coluna_agrupamento}**")
                
                # Agrupar por propriedade
                grupos_sem_laudo = df_sem_laudo.groupby(coluna_agrupamento).size().reset_index(name='quantidade_ups')
                grupos_sem_laudo = grupos_sem_laudo.rename(columns={coluna_agrupamento: 'Agrupamento'})
                tipo_label = "Propriedades"
                icone_agrupamento = "🏗️"
            else:
                # Usar núcleo (método original)
                coluna_agrupamento = 'Nucleo'
                grupos_sem_laudo = df_sem_laudo.groupby('Nucleo').size().reset_index(name='quantidade_ups')
                grupos_sem_laudo = grupos_sem_laudo.rename(columns={'Nucleo': 'Agrupamento'})
                tipo_label = "Núcleos"
                icone_agrupamento = "🏢"
            
            # Manter compatibilidade com código existente
            nucleos_sem_laudo = grupos_sem_laudo
            
            # Overview dos dados
            st.subheader("📊 Overview dos Dados")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total de UPs sem laudo", len(df_sem_laudo))
            with col2:
                st.metric("Núcleos sem laudo", len(nucleos_sem_laudo))
            with col3:
                st.metric("Total de registros", len(df))
            
            # Tabela de grupos (núcleos ou propriedades)
            st.subheader(f"{icone_agrupamento} {tipo_label} sem Laudo")
            st.dataframe(grupos_sem_laudo, use_container_width=True)
            
            # Opções de lançamento
            st.subheader("🚀 Opções de Lançamento")
            
            # Botões para cada grupo
            cols = st.columns(min(len(grupos_sem_laudo) + 1, 4))
            
            # Botão para todos os grupos
            with cols[0]:
                if st.button(f"🎯 Todos os {tipo_label}", key="todos_grupos", use_container_width=True):
                    st.session_state.grupos_selecionados = grupos_sem_laudo['Agrupamento'].tolist()
                    st.session_state.opcao_selecionada = "todos"
                    st.session_state.tipo_organizacao = tipo_organizacao
                    st.session_state.coluna_agrupamento = coluna_agrupamento
            
            # Botões individuais para cada grupo
            for idx, grupo in enumerate(grupos_sem_laudo['Agrupamento'].tolist()):
                col_idx = (idx + 1) % 4
                with cols[col_idx]:
                    if st.button(f"{icone_agrupamento} {grupo}", key=f"grupo_{idx}_{grupo}", use_container_width=True):
                        st.session_state.grupos_selecionados = [grupo]
                        st.session_state.opcao_selecionada = grupo
                        st.session_state.tipo_organizacao = tipo_organizacao
                        st.session_state.coluna_agrupamento = coluna_agrupamento
            
            # Se uma opção foi selecionada, mostra o botão Play
            if hasattr(st.session_state, 'opcao_selecionada'):
                st.success(f"Selecionado: {st.session_state.opcao_selecionada}")
                
                # Dados que serão processados baseado no tipo de organização
                if hasattr(st.session_state, 'tipo_organizacao') and st.session_state.tipo_organizacao.startswith("🏗️ Por Propriedade"):
                    # Filtrar por propriedade
                    ups_para_processar = df_sem_laudo[df_sem_laudo[st.session_state.coluna_agrupamento].isin(st.session_state.grupos_selecionados)]
                    colunas_exibir = ['UP', st.session_state.coluna_agrupamento, 'Ocorrência Predominante', 'Severidade Predominante', 'Incidencia']
                else:
                    # Filtrar por núcleo (método original)
                    ups_para_processar = df_sem_laudo[df_sem_laudo['Nucleo'].isin(st.session_state.grupos_selecionados)]
                    colunas_exibir = ['UP', 'Nucleo', 'Ocorrência Predominante', 'Severidade Predominante', 'Incidencia']
                
                st.subheader("📋 Dados que serão processados:")
                st.dataframe(ups_para_processar[colunas_exibir], use_container_width=True)
                
                # Seção de Credenciais
                st.subheader("🔐 Credenciais de Acesso")
                col1, col2 = st.columns(2)
                
                with col1:
                    email_partial_orig = st.text_input("📧 Email:", placeholder="seu.email", key="original_email", help="Digite apenas a parte antes do @. O @suzano.com.br será adicionado automaticamente.")
                
                with col2:
                    senha_orig = st.text_input("🔒 Senha:", type="password", placeholder="Sua senha", key="original_senha")
                
                if not email_partial_orig or not senha_orig:
                    st.warning("⚠️ Por favor, preencha email e senha para continuar.")
                    return
                
                # Concatenar automaticamente com @suzano.com.br
                email_completo_orig = f"{email_partial_orig}@suzano.com.br"
                
                # Botão Play para iniciar
                if st.button("▶️ INICIAR LANÇAMENTO", key="play_button", type="primary", use_container_width=True):
                    # Verificar se é continuação de sessão
                    is_continuation = hasattr(st.session_state, 'browser_ativo') and st.session_state.browser_ativo
                    if is_continuation:
                        st.info("🔄 Continuando com navegador aberto...")
                    
                    processar_lancamento_novo(ups_para_processar, st.session_state.grupos_selecionados, df, st.session_state.tipo_organizacao, st.session_state.coluna_agrupamento, email_completo_orig, senha_orig)
                    
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {str(e)}")

def processar_lancamento(df_ups, nucleos_selecionados, df_original):
    """Função principal que processa o lançamento usando o módulo lancamento_fenix"""
    try:
        st.info("🚀 Iniciando processamento...")
        
        # Salvar DataFrame original no session_state para posterior atualização
        st.session_state.df_original = df_original.copy()
        
        # Usar o módulo de automação (função original sempre usa núcleo)
        resultado = executar_lancamento_fenix(df_ups, nucleos_selecionados, "🏢 Por Núcleo", None, None)
        
        if resultado:
            st.balloons()  # Animação de comemoração
            
            # Verificar se deve mostrar opção de continuar
            if hasattr(st.session_state, 'mostrar_continuar_lancamento') and st.session_state.mostrar_continuar_lancamento:
                st.success("🎉 Núcleo processado com sucesso!")
                st.info("🚀 Pronto para processar outro núcleo - use os botões acima!")
            else:
                st.success("🎉 Processamento de todos os núcleos concluído!")
            
        # NOVA FUNCIONALIDADE: Mostrar opção de atualização se houver UPs processadas com sucesso
        if hasattr(st.session_state, 'mostrar_opcao_excel') and st.session_state.mostrar_opcao_excel:
            ups_processadas = getattr(st.session_state, 'ups_processadas_com_sucesso', [])
            if ups_processadas:
                st.markdown("---")
                st.subheader("📝 Atualização da Planilha")
                st.info(f"✅ {len(ups_processadas)} UP(s) processada(s) com sucesso: {', '.join(ups_processadas)}")
                st.info("Deseja atualizar o status dessas UPs de 'NÃO' para 'SIM' na coluna 'Laudo Existente'?")
                
                # Debug: Mostrar informações sobre o DataFrame original
                if hasattr(st.session_state, 'df_original'):
                    df_info = st.session_state.df_original
                    total_nao = len(df_info[df_info['Laudo Existente'].str.upper() == 'NÃO'])
                    total_sim = len(df_info[df_info['Laudo Existente'].str.upper() == 'SIM'])
                    st.info(f"📊 Status atual da planilha: {total_nao} com 'NÃO', {total_sim} com 'SIM'")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ SIM - Atualizar Status", key="atualizar_sim", type="primary"):
                        st.info("🔄 Iniciando atualização da planilha...")
                        
                        # Debug adicional: verificar dados no session_state
                        st.info(f"🔍 DataFrame original shape: {st.session_state.df_original.shape}")
                        st.info(f"🔍 UPs a serem atualizadas: {ups_processadas}")
                        st.info(f"🔍 Tipo das UPs: {[type(up) for up in ups_processadas]}")
                        
                        try:
                            resultado_atualizacao = atualizar_status_planilha(st.session_state.df_original, ups_processadas)
                            
                            if resultado_atualizacao:
                                st.success("📊 Planilha atualizada com sucesso!")
                                st.success("🎉 Todas as UPs processadas com sucesso tiveram seu status atualizado para 'SIM'!")
                                st.info("📥 Use o botão de download acima para baixar a planilha atualizada.")
                                
                                # Reset da opção após uso
                                st.session_state.mostrar_opcao_excel = False
                                st.rerun()  # Forçar atualização da interface
                            else:
                                st.error("❌ Erro ao atualizar a planilha ou nenhuma UP foi encontrada.")
                                st.error("🔍 Verifique os logs de debug acima para entender o problema.")
                        except Exception as update_error:
                            st.error(f"❌ Erro durante atualização: {str(update_error)}")
                            import traceback
                            st.error(f"❌ Stack trace completo: {traceback.format_exc()}")
                            
                with col2:
                    if st.button("❌ NÃO - Manter Original", key="atualizar_nao"):
                        st.info("✋ Planilha mantida sem alterações.")
                        # Reset da opção após uso
                        st.session_state.mostrar_opcao_excel = False
                        st.rerun()  # Forçar atualização da interface
                        
        if not resultado:
            st.error("❌ Houve erros durante o processamento. Verifique os logs acima.")
        
    except Exception as e:
        st.error(f"Erro durante o processamento: {str(e)}")

def processar_lancamento_novo(df_ups, grupos_selecionados, df_original, tipo_organizacao, coluna_agrupamento, email=None, senha=None):
    """
    Função aprimorada que processa o lançamento tanto por núcleo quanto por propriedade
    """
    try:
        st.info("🚀 Iniciando processamento...")
        
        # Salvar DataFrame original no session_state para posterior atualização
        st.session_state.df_original = df_original.copy()
        
        # CORREÇÃO: Debug do DataFrame original antes do processamento
        st.info(f"🔍 DEBUG: DataFrame original salvo com {len(df_original)} linhas")
        st.info(f"🔍 DEBUG: Colunas disponíveis: {list(df_original.columns)}")
        if 'UP' in df_original.columns:
            ups_originais = df_original['UP'].unique()
            st.info(f"🔍 DEBUG: Total de UPs únicas no DataFrame original: {len(ups_originais)}")
            st.info(f"🔍 DEBUG: Primeiras 10 UPs do DataFrame original: {list(ups_originais[:10])}")
        if 'Laudo Existente' in df_original.columns:
            status_counts = df_original['Laudo Existente'].value_counts()
            st.info(f"🔍 DEBUG: Status na coluna 'Laudo Existente': {dict(status_counts)}")
        
        # Determinar se é por propriedade ou por núcleo e processar adequadamente
        if tipo_organizacao.startswith("🏗️ Por Propriedade"):
            st.info(f"🏗️ Processando por Propriedade usando coluna: {coluna_agrupamento}")
            
            # Para propriedades, precisamos filtrar o DataFrame pela propriedade selecionada
            # e depois simular como se fosse um núcleo
            df_filtrado_por_propriedade = pd.DataFrame()
            
            for propriedade in grupos_selecionados:
                st.info(f"📋 Filtrando UPs da propriedade: {propriedade}")
                ups_desta_propriedade = df_ups[df_ups[coluna_agrupamento] == propriedade]
                st.info(f"📊 Encontradas {len(ups_desta_propriedade)} UPs para propriedade {propriedade}")
                df_filtrado_por_propriedade = pd.concat([df_filtrado_por_propriedade, ups_desta_propriedade], ignore_index=True)
            
            # Agora vamos criar um "núcleo simulado" para cada propriedade
            # Modificar temporariamente a coluna "Nucleo" para conter o nome da propriedade
            df_para_processamento = df_filtrado_por_propriedade.copy()
            
            # Para cada propriedade selecionada, substituir o valor da coluna "Nucleo" 
            # pelo nome da propriedade para que o sistema de automação funcione
            for propriedade in grupos_selecionados:
                mask = df_para_processamento[coluna_agrupamento] == propriedade
                df_para_processamento.loc[mask, 'Nucleo'] = propriedade
            
            resultado = executar_lancamento_fenix(df_para_processamento, grupos_selecionados, tipo_organizacao, email, senha)
        
        else:
            st.info("🏢 Processando por Núcleo (método original)")
            resultado = executar_lancamento_fenix(df_ups, grupos_selecionados, tipo_organizacao, email, senha)
        
        if resultado:
            st.balloons()  # Animação de comemoração
            
            # Verificar se deve mostrar opção de continuar
            if hasattr(st.session_state, 'mostrar_continuar_lancamento') and st.session_state.mostrar_continuar_lancamento:
                if tipo_organizacao.startswith("🏗️ Por Propriedade"):
                    st.success("🎉 Propriedade processada com sucesso!")
                    st.info("🚀 Pronto para processar outra propriedade - use os botões acima!")
                else:
                    st.success("🎉 Núcleo processado com sucesso!")
                    st.info("🚀 Pronto para processar outro núcleo - use os botões acima!")
            else:
                if tipo_organizacao.startswith("🏗️ Por Propriedade"):
                    st.success("🎉 Processamento de todas as propriedades concluído!")
                else:
                    st.success("🎉 Processamento de todos os núcleos concluído!")
            
        # Funcionalidade de atualização da planilha (mantida igual)
        if hasattr(st.session_state, 'mostrar_opcao_excel') and st.session_state.mostrar_opcao_excel:
            ups_processadas = getattr(st.session_state, 'ups_processadas_com_sucesso', [])
            
            # CORREÇÃO: Debug das UPs processadas
            st.info(f"🔍 DEBUG: UPs registradas como processadas: {ups_processadas}")
            st.info(f"🔍 DEBUG: Tipo de organização usado: {tipo_organizacao}")
            st.info(f"🔍 DEBUG: Grupos selecionados: {grupos_selecionados}")
            if ups_processadas:
                st.markdown("---")
                st.subheader("📝 Atualização da Planilha")
                st.info(f"✅ {len(ups_processadas)} UP(s) processada(s) com sucesso: {', '.join(ups_processadas)}")
                st.info("Deseja atualizar o status dessas UPs de 'NÃO' para 'SIM' na coluna 'Laudo Existente'?")
                
                # Debug: Mostrar informações sobre o DataFrame original
                if hasattr(st.session_state, 'df_original'):
                    df_info = st.session_state.df_original
                    total_nao = len(df_info[df_info['Laudo Existente'].str.upper() == 'NÃO'])
                    total_sim = len(df_info[df_info['Laudo Existente'].str.upper() == 'SIM'])
                    st.info(f"📊 Status atual da planilha: {total_nao} com 'NÃO', {total_sim} com 'SIM'")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ SIM - Atualizar Status", key="atualizar_sim_novo", type="primary"):
                        st.info("🔄 Iniciando atualização da planilha...")
                        
                        try:
                            resultado_atualizacao = atualizar_status_planilha(st.session_state.df_original, ups_processadas)
                            
                            if resultado_atualizacao:
                                st.success("📊 Planilha atualizada com sucesso!")
                                st.success("🎉 Todas as UPs processadas com sucesso tiveram seu status atualizado para 'SIM'!")
                                st.info("📥 Use o botão de download acima para baixar a planilha atualizada.")
                                
                                # Reset da opção após uso
                                st.session_state.mostrar_opcao_excel = False
                                st.rerun()
                            else:
                                st.error("❌ Erro ao atualizar a planilha ou nenhuma UP foi encontrada.")
                        except Exception as update_error:
                            st.error(f"❌ Erro durante atualização: {str(update_error)}")
                            import traceback
                            st.error(f"❌ Stack trace completo: {traceback.format_exc()}")
                            
                with col2:
                    if st.button("❌ NÃO - Manter Original", key="atualizar_nao_novo"):
                        st.info("✋ Planilha mantida sem alterações.")
                        # Reset da opção após uso
                        st.session_state.mostrar_opcao_excel = False
                        st.rerun()
                        
        if not resultado:
            st.error("❌ Houve erros durante o processamento. Verifique os logs acima.")
        
    except Exception as e:
        st.error(f"Erro durante o processamento: {str(e)}")
        import traceback
        st.error(f"Stack trace: {traceback.format_exc()}")

def lancamento_fenix_hard():
    """Interface para Lançamento Automático no Fênix (Hard Mode)"""
    st.header("🚀 Lançamento Fênix Hard - Modo Automático")
    st.info("💪 Este modo processa automaticamente todas as propriedades selecionadas sem intervenção do usuário.")
    
    # Upload do arquivo Excel
    uploaded_file = st.file_uploader("Escolha um arquivo Excel", type=['xlsx', 'xls'], key="hard_excel_uploader")
    
    if uploaded_file is not None:
        try:
            # Lê o arquivo Excel
            df = pd.read_excel(uploaded_file)
            st.success(f"✅ Arquivo carregado com sucesso! {len(df)} linhas encontradas.")
            
            # Verifica colunas necessárias e normaliza nomes
            required_columns = ['UP', 'UNF', 'Idade', 'Ocorrência Predominante', 'Severidade Predominante', 'Incidencia', 'Laudo Existente']
            
            # Verificar se existe coluna de propriedade (aceitar variações)
            propriedade_col = None
            for col in df.columns:
                if col.lower() in ['propriedade', 'property']:
                    propriedade_col = col
                    break
            
            if propriedade_col is None:
                st.error("❌ Coluna de propriedade não encontrada. Procurando por: 'propriedade', 'Propriedade', 'property'")
                st.info("📋 Colunas disponíveis no arquivo:")
                st.write(list(df.columns))
                return
            
            # Normalizar nome da coluna de propriedade
            if propriedade_col != 'Propriedade':
                df = df.rename(columns={propriedade_col: 'Propriedade'})
                st.success(f"✅ Coluna '{propriedade_col}' renomeada para 'Propriedade'")
            
            # Verificar outras colunas obrigatórias
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"❌ Colunas obrigatórias não encontradas: {', '.join(missing_columns)}")
                st.info("📋 Colunas disponíveis no arquivo:")
                st.write(list(df.columns))
                return
            
            # Filtrar apenas registros sem laudo
            df_sem_laudo = df[df['Laudo Existente'].str.upper() == 'NÃO'].copy()
            
            if len(df_sem_laudo) == 0:
                st.warning("⚠️ Não há registros sem laudo para processar.")
                return
            
            st.success(f"📊 {len(df_sem_laudo)} UPs sem laudo encontradas para processamento.")
            
            # Seção de Credenciais
            st.subheader("🔐 Credenciais de Acesso")
            col1, col2 = st.columns(2)
            
            with col1:
                email_partial = st.text_input("📧 Email:", placeholder="seu.email", key="hard_email", help="Digite apenas a parte antes do @. O @suzano.com.br será adicionado automaticamente.")
            
            with col2:
                senha = st.text_input("🔒 Senha:", type="password", placeholder="Sua senha", key="hard_senha")
            
            if not email_partial or not senha:
                st.warning("⚠️ Por favor, preencha email e senha para continuar.")
                return
            
            # Concatenar automaticamente com @suzano.com.br
            email_completo = f"{email_partial}@suzano.com.br"
            
            # Seleção de UNF
            st.subheader("🏢 Seleção de UNF")
            unfs_disponveis = sorted(df_sem_laudo['UNF'].unique())
            
            if len(unfs_disponveis) == 0:
                st.error("❌ Nenhuma UNF encontrada nos dados.")
                return
            
            unf_selecionada = st.selectbox("Selecione a UNF:", unfs_disponveis, key="hard_unf_select")
            
            if unf_selecionada:
                # Mostrar propriedades disponíveis para a UNF selecionada
                st.subheader(f"🏗️ Propriedades da UNF {unf_selecionada}")
                
                propriedades_info = obter_propriedades_por_unf(df_sem_laudo, unf_selecionada)
                
                if not propriedades_info:
                    st.warning(f"⚠️ Nenhuma propriedade encontrada para UNF {unf_selecionada}")
                    return
                
                # Mostrar propriedades em formato de tabela
                propriedades_df = pd.DataFrame([
                    {"Propriedade": prop, "Quantidade de UPs": qtd}
                    for prop, qtd in propriedades_info.items()
                ])
                
                st.dataframe(propriedades_df, use_container_width=True)
                
                # Seleção múltipla de propriedades
                st.subheader("✅ Seleção de Propriedades")
                todas_propriedades = list(propriedades_info.keys())
                
                # Opção de selecionar todas
                if st.checkbox("🎯 Selecionar todas as propriedades", key="hard_select_all"):
                    propriedades_selecionadas = todas_propriedades
                else:
                    propriedades_selecionadas = st.multiselect(
                        "Escolha as propriedades para processar:",
                        todas_propriedades,
                        key="hard_propriedades_select"
                    )
                
                if propriedades_selecionadas:
                    # Mostrar resumo
                    total_ups = sum(propriedades_info[prop] for prop in propriedades_selecionadas)
                    
                    st.success(f"📋 Resumo da Seleção:")
                    st.info(f"🏗️ {len(propriedades_selecionadas)} propriedades selecionadas")
                    st.info(f"📊 {total_ups} UPs serão processadas")
                    st.info(f"🏢 UNF: {unf_selecionada}")
                    
                    # Lista das propriedades selecionadas
                    st.write("**Propriedades selecionadas:**")
                    for prop in propriedades_selecionadas:
                        st.write(f"• {prop} ({propriedades_info[prop]} UPs)")
                    
                    # Botão para iniciar processamento
                    st.markdown("---")
                    
                    # Aviso importante
                    st.warning("⚠️ **ATENÇÃO**: O modo Hard é totalmente automático. Uma vez iniciado, o sistema processará todas as propriedades selecionadas sem parar para confirmações.")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.button("🚀 INICIAR PROCESSAMENTO AUTOMÁTICO", type="primary", key="hard_start_processing", use_container_width=True):
                            st.info("🎯 Iniciando processamento automático...")
                            
                            # Validar novamente as credenciais
                            if not email_completo or not senha:
                                st.error("❌ Email e senha são obrigatórios!")
                                return
                            
                            # Executar processamento
                            with st.status("🔄 Processando todas as propriedades...", expanded=True) as status:
                                resultado = executar_lancamento_fenix_hard(
                                    df_sem_laudo, 
                                    email_completo, 
                                    senha, 
                                    unf_selecionada, 
                                    propriedades_selecionadas
                                )
                                
                                if resultado:
                                    status.update(label="✅ Processamento concluído com sucesso!", state="complete", expanded=False)
                                    st.balloons()
                                    st.success("🎉 Todas as propriedades foram processadas automaticamente!")
                                else:
                                    status.update(label="❌ Processamento concluído com erros", state="error", expanded=True)
                                    st.error("💥 Houve erros durante o processamento. Verifique os logs acima.")
                    
                    with col_btn2:
                        if st.button("📋 Visualizar Dados", key="hard_preview_data", use_container_width=True):
                            st.subheader("👀 Prévia dos Dados que Serão Processados")
                            
                            # Filtrar dados pelas propriedades selecionadas
                            dados_preview = df_sem_laudo[
                                (df_sem_laudo['UNF'] == unf_selecionada) & 
                                (df_sem_laudo['Propriedade'].isin(propriedades_selecionadas))
                            ]
                            
                            colunas_preview = ['UP', 'Propriedade', 'Ocorrência Predominante', 'Severidade Predominante', 'Incidencia', 'Idade']
                            st.dataframe(dados_preview[colunas_preview], use_container_width=True)
                            
                else:
                    st.info("👆 Selecione pelo menos uma propriedade para continuar.")
                    
        except Exception as e:
            st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
            st.error(f"🔍 Detalhes: {traceback.format_exc()}")

def criar_pdf():
    # Chama a função do módulo cria_pdf.py
    criar_pdf_streamlit()

def main():
    st.title("Sistema de Automação RPA")
    
    # Inicializar flags do session_state
    if 'mostrar_opcao_excel' not in st.session_state:
        st.session_state.mostrar_opcao_excel = False
    
    if 'mostrar_continuar_lancamento' not in st.session_state:
        st.session_state.mostrar_continuar_lancamento = False
    
    if 'browser_ativo' not in st.session_state:
        st.session_state.browser_ativo = False
    
    # Criando o menu lateral
    st.sidebar.title("Menu de Opções")
    opcao = st.sidebar.radio(
        "Selecione a operação desejada:",
        ["Lançamento no Fênix", "Lançamento Fênix Hard", "Criar PDF com Imagens e Croquis"],
        key="menu_principal"
    )
    
    # Mostrar status do navegador na sidebar se estiver ativo
    if st.session_state.browser_ativo:
        st.sidebar.success("🌐 Navegador Ativo")
        if st.sidebar.button("🔚 Fechar Navegador", key="sidebar_fechar"):
            if fechar_navegador_manual():
                st.success("✅ Navegador fechado!")
                time.sleep(1)
                st.rerun()
    
    # Navegação baseada na escolha do usuário
    if opcao == "Lançamento no Fênix":
        lancamento_fenix()
    elif opcao == "Lançamento Fênix Hard":
        lancamento_fenix_hard()
    else:
        criar_pdf()

if __name__ == "__main__":
    main()
