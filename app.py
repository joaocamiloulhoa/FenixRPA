import streamlit as st
import pandas as pd
from cria_pdf import criar_pdf_streamlit

def lancamento_fenix():
    st.header("Lançamento de Informações no Fênix")
    
    # Upload do arquivo Excel
    uploaded_file = st.file_uploader("Escolha um arquivo Excel", type=['xlsx', 'xls'], key="lancamento_excel_uploader")
    
    if uploaded_file is not None:
        try:
            # Lê o arquivo Excel
            df = pd.read_excel(uploaded_file)
            
            # Mostra informações básicas sobre o DataFrame
            st.write("Informações do arquivo:")
            st.write(f"Total de linhas: {len(df)}")
            st.write(f"Colunas disponíveis: {', '.join(df.columns)}")
            
            # Mostra os primeiros registros do DataFrame
            st.write("Visualização dos dados:")
            st.dataframe(df.head())
            
            # Aqui você pode adicionar os filtros baseados nas colunas do DataFrame
            st.subheader("Filtros")
            # Exemplo: se quiser selecionar uma coluna específica
            if len(df.columns) > 0:
                coluna_selecionada = st.selectbox("Selecione uma coluna para filtrar:", df.columns, key="lancamento_coluna_selectbox")
                valores_unicos = df[coluna_selecionada].unique()
                valores_selecionados = st.multiselect(
                    f"Selecione os valores de {coluna_selecionada}:",
                    valores_unicos,
                    key="lancamento_valores_multiselect"
                )
                
                # Aplica o filtro se algum valor foi selecionado
                if valores_selecionados:
                    df_filtrado = df[df[coluna_selecionada].isin(valores_selecionados)]
                    st.write("Dados filtrados:")
                    st.dataframe(df_filtrado)
                    
                    # Adiciona botão para iniciar o processo de lançamento
                    if st.button("Iniciar Lançamento no Fênix", key="lancamento_iniciar_button"):
                        st.info("Funcionalidade de lançamento será implementada em breve...")
                    
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {str(e)}")

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
