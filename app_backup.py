import streamlit as st
import pandas as pd
import time
from datetime import datetime
from cria_pdf import criar_pdf_streamlit
from lancamento_fenix import executar_lancamento_fenix, get_recomendacao, atualizar_status_planilha

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
            
            # Agrupa por núcleo
            nucleos_sem_laudo = df_sem_laudo.groupby('Nucleo').size().reset_index(name='quantidade_ups')
            
            # Overview dos dados
            st.subheader("📊 Overview dos Dados")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total de UPs sem laudo", len(df_sem_laudo))
            with col2:
                st.metric("Núcleos sem laudo", len(nucleos_sem_laudo))
            with col3:
                st.metric("Total de registros", len(df))
            
            # Tabela de núcleos
            st.subheader("🏢 Núcleos sem Laudo")
            st.dataframe(nucleos_sem_laudo, use_container_width=True)
            
            # Opções de lançamento
            st.subheader("🚀 Opções de Lançamento")
            
            # Botões para cada núcleo
            cols = st.columns(min(len(nucleos_sem_laudo) + 1, 4))
            
            # Botão para todos os núcleos
            with cols[0]:
                if st.button("🎯 Todos os Núcleos", key="todos_nucleos", use_container_width=True):
                    st.session_state.nucleos_selecionados = nucleos_sem_laudo['Nucleo'].tolist()
                    st.session_state.opcao_selecionada = "todos"
            
            # Botões individuais para cada núcleo
            for idx, nucleo in enumerate(nucleos_sem_laudo['Nucleo'].tolist()):
                col_idx = (idx + 1) % 4
                with cols[col_idx]:
                    if st.button(f"📍 {nucleo}", key=f"nucleo_{nucleo}", use_container_width=True):
                        st.session_state.nucleos_selecionados = [nucleo]
                        st.session_state.opcao_selecionada = nucleo
            
            # Se uma opção foi selecionada, mostra o botão Play
            if hasattr(st.session_state, 'opcao_selecionada'):
                st.success(f"Selecionado: {st.session_state.opcao_selecionada}")
                
                # Dados que serão processados
                ups_para_processar = df_sem_laudo[df_sem_laudo['Nucleo'].isin(st.session_state.nucleos_selecionados)]
                
                st.subheader("📋 Dados que serão processados:")
                st.dataframe(ups_para_processar[['UP', 'Nucleo', 'Ocorrência Predominante', 'Severidade Predominante', 'Incidencia']], use_container_width=True)
                
                # Botão Play para iniciar
                if st.button("▶️ INICIAR LANÇAMENTO", key="play_button", type="primary", use_container_width=True):
                    processar_lancamento(ups_para_processar, st.session_state.nucleos_selecionados, df)
                    
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {str(e)}")

def processar_lancamento(df_ups, nucleos_selecionados, df_original):
    """Função principal que processa o lançamento usando o módulo lancamento_fenix"""
    try:
        st.info("🚀 Iniciando processamento...")
        
        # Salvar DataFrame original no session_state para posterior atualização
        st.session_state.df_original = df_original.copy()
        
        # Usar o módulo de automação
        resultado = executar_lancamento_fenix(df_ups, nucleos_selecionados)
        
        if resultado:
            st.balloons()  # Animação de comemoração
            st.success("🎉 Processamento de todos os núcleos concluído!")
            
            # NOVA FUNCIONALIDADE: Perguntar sobre atualização da planilha
            st.subheader("📝 Atualização da Planilha")
            st.info("Deseja atualizar o status das UPs processadas com sucesso na planilha?")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ SIM - Atualizar Status", key="atualizar_sim", type="primary"):
                    # Obter UPs processadas com sucesso (será passado pelo resultado da automação)
                    ups_processadas = getattr(st.session_state, 'ups_processadas_com_sucesso', [])
                    if ups_processadas:
                        if atualizar_status_planilha(st.session_state.df_original, ups_processadas):
                            st.success("📊 Planilha atualizada com sucesso!")
                        else:
                            st.error("❌ Erro ao atualizar a planilha.")
                    else:
                        st.warning("⚠️ Nenhuma UP foi processada com sucesso.")
                        
            with col2:
                if st.button("❌ NÃO - Manter Original", key="atualizar_nao"):
                    st.info("✋ Planilha mantida sem alterações.")
        else:
            st.error("❌ Houve erros durante o processamento. Verifique os logs acima.")
        
    except Exception as e:
        st.error(f"Erro durante o processamento: {str(e)}")

def criar_pdf():
    # Chama a função do módulo cria_pdf.py
    criar_pdf_streamlit()

def main():
    st.title("Sistema de Automação RPA")
    
    # Criando o menu lateral
    st.sidebar.title("Menu de Opções")
    opcao = st.sidebar.radio(
        "Selecione a operação desejada:",
        ["Lançamento no Fênix", "Criar PDF com Imagens e Croquis"],
        key="menu_principal"
    )
    
    # Navegação baseada na escolha do usuário
    if opcao == "Lançamento no Fênix":
        lancamento_fenix()
    else:
        criar_pdf()

if __name__ == "__main__":
    main()
