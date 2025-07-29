import streamlit as st
import os
import sys
from urllib.parse import quote
import pandas as pd
import tempfile
import getpass

# Importando bibliotecas necessárias
from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
from fpdf import FPDF
from PIL import Image

# =========================================================================
# CONFIGURAÇÕES
# =========================================================================

site_url = "https://suzano.sharepoint.com/sites/TOPS-VALIDAO"
default_username = "joaoco@suzano.com.br"

# =========================================================================
# FUNÇÃO PARA CONVERTER URL DO SHAREPOINT
# =========================================================================

def convert_sharepoint_url_to_path(url):
    """
    Converte uma URL do SharePoint copiada do navegador para o caminho relativo do servidor.
    """
    if not url:
        return ""
    
    # Remove parâmetros da URL (?csf=1&web=1&e=...)
    if '?' in url:
        url = url.split('?')[0]
    
    # Se for uma URL completa, extrair apenas o caminho
    if url.startswith('https://suzano.sharepoint.com/:f:/r/'):
        # Remove o prefixo da URL de compartilhamento
        path = url.replace('https://suzano.sharepoint.com/:f:/r/', '/')
        # Decodifica caracteres especiais
        path = path.replace('%20', ' ').replace('%2520', ' ')
        return path
    elif url.startswith('https://suzano.sharepoint.com/'):
        # Remove apenas o domínio
        path = url.replace('https://suzano.sharepoint.com', '')
        # Decodifica caracteres especiais
        path = path.replace('%20', ' ').replace('%2520', ' ')
        return path
    elif url.startswith('/sites/'):
        # Já é um caminho relativo, apenas decodifica
        return url.replace('%20', ' ').replace('%2520', ' ')
    else:
        # Assume que já está no formato correto
        return url

# =========================================================================
# 1) AUTENTICAÇÃO NO SHAREPOINT
# =========================================================================

def connect_to_sharepoint(site_url, username, password):
    ctx_auth = AuthenticationContext(site_url)
    if ctx_auth.acquire_token_for_user(username, password):
        return ClientContext(site_url, ctx_auth)
    else:
        raise Exception("Erro ao autenticar. Verifique suas credenciais.")

# =========================================================================
# 2) LISTAR ARQUIVOS (SEM SUBPASTAS)
# =========================================================================

def list_files(ctx, folder_url):
    folder = ctx.web.get_folder_by_server_relative_url(folder_url)
    files = folder.files
    ctx.load(files)
    ctx.execute_query()
    return [(f.properties["Name"], f.properties["ServerRelativeUrl"]) for f in files]

# =========================================================================
# 3) BAIXAR ARQUIVO DO SHAREPOINT
# =========================================================================

def download_file(ctx, server_relative_file_url, local_path):
    response = File.open_binary(ctx, server_relative_file_url)
    with open(local_path, "wb") as local_file:
        local_file.write(response.content)

# =========================================================================
# 4) FUNÇÃO PARA OTIMIZAR E REDIMENSIONAR IMAGEM
# =========================================================================

def optimize_and_resize_image(image_path, max_width_px=800, max_height_px=600, quality=70):
    """
    Otimiza uma imagem redimensionando e comprimindo para reduzir tamanho do arquivo.
    Cria uma versão otimizada temporária da imagem.
    
    Args:
        image_path: Caminho da imagem original
        max_width_px: Largura máxima em pixels
        max_height_px: Altura máxima em pixels  
        quality: Qualidade JPEG (1-100, menor = arquivo menor)
    
    Returns:
        tuple: (caminho_otimizado, largura_final_pt, altura_final_pt)
    """
    try:
        with Image.open(image_path) as img:
            # Converter para RGB se necessário (para salvar como JPEG)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            original_width, original_height = img.size
            
            # Calcular nova dimensão mantendo proporção
            scale_width = max_width_px / original_width
            scale_height = max_height_px / original_height
            scale = min(scale_width, scale_height)
            
            new_width_px = int(original_width * scale)
            new_height_px = int(original_height * scale)
            
            # Redimensionar a imagem
            img_resized = img.resize((new_width_px, new_height_px), Image.Resampling.LANCZOS)
            
            # Criar nome do arquivo temporário otimizado
            base_name = os.path.splitext(image_path)[0]
            optimized_path = f"{base_name}_optimized.jpg"
            
            # Salvar imagem otimizada
            img_resized.save(optimized_path, 'JPEG', quality=quality, optimize=True)
            
            # Converter pixels para pontos (aproximadamente 1 pixel = 0.75 pontos)
            width_pt = int(new_width_px * 0.75)
            height_pt = int(new_height_px * 0.75)
            
            return optimized_path, width_pt, height_pt
            
    except Exception as e:
        st.error(f"Erro ao otimizar imagem {image_path}: {e}")
        # Retornar valores padrão em caso de erro
        return image_path, 400, 300

def get_file_size_mb(file_path):
    """Retorna o tamanho do arquivo em MB"""
    try:
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        return round(size_mb, 2)
    except:
        return 0

# =========================================================================
# 5) CRIAR PLACEHOLDER PARA IMAGEM AUSENTE
# =========================================================================

def create_image_placeholder(width_pt, height_pt):
    """
    Cria um placeholder temporário para imagem ausente
    """
    try:
        # Criar uma imagem placeholder com PIL
        from PIL import Image, ImageDraw, ImageFont
        
        placeholder_img = Image.new('RGB', (int(width_pt * 1.33), int(height_pt * 1.33)), color='lightgray')
        draw = ImageDraw.Draw(placeholder_img)
        
        # Adicionar texto no placeholder
        try:
            # Tentar usar uma fonte padrão
            font = ImageFont.load_default()
        except:
            font = None
            
        text = "Imagem não encontrada"
        
        # Calcular posição do texto para centralizar
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            text_width = len(text) * 10  # Estimativa
            text_height = 20
            
        x = (placeholder_img.width - text_width) // 2
        y = (placeholder_img.height - text_height) // 2
        
        draw.text((x, y), text, fill='black', font=font)
        
        # Salvar placeholder temporário
        temp_path = os.path.join(tempfile.gettempdir(), f"placeholder_{os.getpid()}.jpg")
        placeholder_img.save(temp_path, 'JPEG', quality=85)
        
        return temp_path
        
    except Exception as e:
        st.error(f"Erro ao criar placeholder: {e}")
        return None

# =========================================================================
# 6) CRIAR O PDF COM SUPORTE A PLACEHOLDERS
# =========================================================================

def create_pdf_with_placeholders(up_data, image_path, croqui_path, pdf_path):
    """
    Cria um PDF otimizado com placeholders para imagens ausentes.
    """
    # Lista para armazenar arquivos temporários para limpeza posterior
    temp_files = []
    
    try:
        # PDF de 1920 pt de largura e 1080 pt de altura (como slide 16:9)
        pdf = FPDF(unit='pt', format=(1920, 1080))
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # Montar o texto em uma única string, separado por '||'
        text_line = (
            f"UP-C-R: {up_data['UP-C-R']} || "
            f"UP: {up_data['UP']} || "
            f"Nucleo: {up_data['Nucleo']} || "
            f"Data_Ocorrência: {up_data['Data_Ocorrência']} || "
            f"Idade: {up_data['Idade']} || "
            f"Quant.Ocorrências: {up_data['Quant.Ocorrências']} || "
            f"Ocorrência Predominante: {up_data['Ocorrência Predominante']} || "
            f"Severidade Predominante: {up_data['Severidade Predominante']} || "
            f"Area UP: {up_data['Area UP']} || "
            f"Area Liquida: {up_data['Area Liquida']} || "
            f"Incidencia: {up_data['Incidencia']} || "
            f"Quantidade de Imagens*: {up_data['Quantidade de Imagens*']} || "
            f"Recomendacao: {up_data['Recomendacao']}"
        )

        # Usar multi_cell para quebrar linha automaticamente
        pdf.multi_cell(0, 25, text_line)

        # Configurações para otimização das imagens
        max_width_px = 600   # Pixels
        max_height_px = 450  # Pixels
        image_quality = 60   # Qualidade JPEG
        
        # Posições iniciais
        x1 = 50  # Margem esquerda para primeira imagem
        y_images = 180  # Posição Y para ambas as imagens
        spacing = 40  # Espaçamento entre as imagens

        # Variáveis para controlar posicionamento
        x2 = x1

        # PRIMEIRA IMAGEM (otimizada ou placeholder)
        if os.path.exists(image_path):
            optimized_path1, img1_width, img1_height = optimize_and_resize_image(
                image_path, max_width_px, max_height_px, image_quality
            )
            temp_files.append(optimized_path1)
            
            pdf.image(optimized_path1, x=x1, y=y_images, w=img1_width, h=img1_height)
            
            # Calcular posição da segunda imagem
            x2 = x1 + img1_width + spacing
        else:
            # Criar placeholder para primeira imagem
            st.warning(f"Imagem não encontrada: {image_path}. Usando placeholder.")
            placeholder_width = int(max_width_px * 0.75)
            placeholder_height = int(max_height_px * 0.75)
            
            placeholder_path = create_image_placeholder(placeholder_width, placeholder_height)
            if placeholder_path:
                temp_files.append(placeholder_path)
                pdf.image(placeholder_path, x=x1, y=y_images, w=placeholder_width, h=placeholder_height)
                x2 = x1 + placeholder_width + spacing
            else:
                x2 = x1 + placeholder_width + spacing

        # SEGUNDA IMAGEM (otimizada ou placeholder)
        if os.path.exists(croqui_path):
            optimized_path2, img2_width, img2_height = optimize_and_resize_image(
                croqui_path, max_width_px, max_height_px, image_quality
            )
            temp_files.append(optimized_path2)
            
            pdf.image(optimized_path2, x=x2, y=y_images, w=img2_width, h=img2_height)
        else:
            # Criar placeholder para segunda imagem
            st.warning(f"Croqui não encontrado: {croqui_path}. Usando placeholder.")
            placeholder_width = int(max_width_px * 0.75)
            placeholder_height = int(max_height_px * 0.75)
            
            placeholder_path = create_image_placeholder(placeholder_width, placeholder_height)
            if placeholder_path:
                temp_files.append(placeholder_path)
                pdf.image(placeholder_path, x=x2, y=y_images, w=placeholder_width, h=placeholder_height)

        # Salvar o PDF
        pdf.output(pdf_path)
        
        # Verificar tamanho do arquivo gerado
        file_size = get_file_size_mb(pdf_path)
        
        # Alertar se ainda estiver muito grande
        if file_size > 9.0:
            st.warning(f"PDF ainda está grande ({file_size} MB). Considere usar compressão extra.")
            
        return file_size, True
            
    except Exception as e:
        st.error(f"Erro ao criar PDF com placeholders: {e}")
        return 0, False
        
    finally:
        # Limpar arquivos temporários
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                pass

# =========================================================================
# 7) CRIAR O PDF OTIMIZADO COM IMAGENS COMPRIMIDAS (FUNÇÃO ORIGINAL)
# =========================================================================

def create_pdf(up_data, image_path, croqui_path, pdf_path):
    """
    Cria um PDF otimizado com imagens comprimidas para manter tamanho abaixo de 9MB.
    """
    # Lista para armazenar arquivos temporários para limpeza posterior
    temp_files = []
    
    try:
        # PDF de 1920 pt de largura e 1080 pt de altura (como slide 16:9)
        pdf = FPDF(unit='pt', format=(1920, 1080))
        pdf.add_page()
        pdf.set_font("Arial", size=12)  # Fonte um pouco menor para economizar espaço

        # Montar o texto em uma única string, separado por '||'
        text_line = (
            f"UP-C-R: {up_data['UP-C-R']} || "
            f"UP: {up_data['UP']} || "
            f"Nucleo: {up_data['Nucleo']} || "
            f"Data_Ocorrência: {up_data['Data_Ocorrência']} || "
            f"Idade: {up_data['Idade']} || "
            f"Quant.Ocorrências: {up_data['Quant.Ocorrências']} || "
            f"Ocorrência Predominante: {up_data['Ocorrência Predominante']} || "
            f"Severidade Predominante: {up_data['Severidade Predominante']} || "
            f"Area UP: {up_data['Area UP']} || "
            f"Area Liquida: {up_data['Area Liquida']} || "
            f"Incidencia: {up_data['Incidencia']} || "
            f"Quantidade de Imagens*: {up_data['Quantidade de Imagens*']} || "
            f"Recomendacao: {up_data['Recomendacao']}"
        )

        # Usar multi_cell para quebrar linha automaticamente
        pdf.multi_cell(0, 25, text_line)  # Altura de linha menor

        # Configurações para otimização das imagens
        # Tamanhos em pixels (menores para reduzir tamanho do arquivo)
        max_width_px = 600   # Pixels
        max_height_px = 450  # Pixels
        image_quality = 60   # Qualidade JPEG (60 = boa qualidade, arquivo menor)
        
        # Posições iniciais
        x1 = 50  # Margem esquerda para primeira imagem
        y_images = 180  # Posição Y para ambas as imagens (um pouco mais alto)
        spacing = 40  # Espaçamento menor entre as imagens

        # Variáveis para controlar posicionamento
        x2 = x1

        # PRIMEIRA IMAGEM (otimizada)
        if os.path.exists(image_path):
            optimized_path1, img1_width, img1_height = optimize_and_resize_image(
                image_path, max_width_px, max_height_px, image_quality
            )
            temp_files.append(optimized_path1)
            
            pdf.image(optimized_path1, x=x1, y=y_images, w=img1_width, h=img1_height)
            
            # Calcular posição da segunda imagem
            x2 = x1 + img1_width + spacing
        else:
            st.warning(f"Arquivo de imagem não encontrado: {image_path}")
            x2 = x1 + 450 + spacing  # Valor padrão

        # SEGUNDA IMAGEM (otimizada)
        if os.path.exists(croqui_path):
            optimized_path2, img2_width, img2_height = optimize_and_resize_image(
                croqui_path, max_width_px, max_height_px, image_quality
            )
            temp_files.append(optimized_path2)
            
            pdf.image(optimized_path2, x=x2, y=y_images, w=img2_width, h=img2_height)
        else:
            st.warning(f"Arquivo de croqui não encontrado: {croqui_path}")

        # Salvar o PDF
        pdf.output(pdf_path)
        
        # Verificar tamanho do arquivo gerado
        file_size = get_file_size_mb(pdf_path)
        
        # Alertar se ainda estiver muito grande
        if file_size > 9.0:
            st.warning(f"PDF ainda está grande ({file_size} MB). Reduzindo mais a qualidade...")
            
        return file_size, True
            
    except Exception as e:
        st.error(f"Erro ao criar PDF: {e}")
        return 0, False
        
    finally:
        # Limpar arquivos temporários
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                pass

def create_pdf_extra_compressed(up_data, image_path, croqui_path, pdf_path):
    """
    Versão com compressão extra para casos onde o PDF ainda fica muito grande.
    """
    temp_files = []
    
    try:
        pdf = FPDF(unit='pt', format=(1920, 1080))
        pdf.add_page()
        pdf.set_font("Arial", size=10)  # Fonte ainda menor

        # Texto mais conciso
        text_line = (
            f"UP: {up_data['UP']} | Nucleo: {up_data['Nucleo']} | "
            f"Data: {up_data['Data_Ocorrência']} | Idade: {up_data['Idade']} | "
            f"Ocorrências: {up_data['Quant.Ocorrências']} | "
            f"Predominante: {up_data['Ocorrência Predominante']} | "
            f"Severidade: {up_data['Severidade Predominante']} | "
            f"Area UP: {up_data['Area UP']} | Area Liquida: {up_data['Area Liquida']} | "
            f"Incidencia: {up_data['Incidencia']} | "
            f"Recomendacao: {up_data['Recomendacao']}"
        )

        pdf.multi_cell(0, 20, text_line)

        # Configurações mais agressivas
        max_width_px = 400   # Ainda menores
        max_height_px = 300  
        image_quality = 45   # Qualidade menor
        
        x1, y_images, spacing = 50, 160, 30

        # Primeira imagem
        if os.path.exists(image_path):
            optimized_path1, img1_width, img1_height = optimize_and_resize_image(
                image_path, max_width_px, max_height_px, image_quality
            )
            temp_files.append(optimized_path1)
            pdf.image(optimized_path1, x=x1, y=y_images, w=img1_width, h=img1_height)
            x2 = x1 + img1_width + spacing
        else:
            x2 = x1 + 300 + spacing

        # Segunda imagem
        if os.path.exists(croqui_path):
            optimized_path2, img2_width, img2_height = optimize_and_resize_image(
                croqui_path, max_width_px, max_height_px, image_quality
            )
            temp_files.append(optimized_path2)
            pdf.image(optimized_path2, x=x2, y=y_images, w=img2_width, h=img2_height)

        pdf.output(pdf_path)
        
        file_size = get_file_size_mb(pdf_path)
        return file_size, True
        
    except Exception as e:
        st.error(f"Erro ao criar PDF com compressão extra: {e}")
        return 0, False
        
    finally:
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

# =========================================================================
# 6) PROCESSAMENTO DAS LINHAS (UPs) COM STREAMLIT
# =========================================================================

def process_properties_streamlit(df, ctx, images_folder_url, croquis_folder_url, output_dir, entrega_nome):
    # Preparar diretório de saída
    os.makedirs(output_dir, exist_ok=True)
    
    # Criar um container de progresso
    progress_container = st.empty()
    status_container = st.empty()
    
    with st.spinner("Obtendo lista de arquivos do SharePoint..."):
        # Obter lista de arquivos das pastas
        try:
            image_files = list_files(ctx, images_folder_url)
            croquis_files = list_files(ctx, croquis_folder_url)
        except Exception as e:
            st.error(f"Erro ao listar arquivos no SharePoint: {str(e)}")
            return
    
    # Exibir informações sobre arquivos encontrados
    st.write("### Arquivos encontrados")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Total de imagens: {len(image_files)}")
        if len(image_files) > 0:
            st.write("Exemplos de imagens:")
            for (n, _) in image_files[:3]:
                st.write(f"- {n}")
    
    with col2:
        st.write(f"Total de croquis: {len(croquis_files)}")
        if len(croquis_files) > 0:
            st.write("Exemplos de croquis:")
            for (n, _) in croquis_files[:3]:
                st.write(f"- {n}")
    
    # Contadores para relatório final
    total_ups = len(df)
    successful_pdfs = 0
    failed_ups = 0
    failed_up_list = []
    large_files = []  # Para rastrear arquivos que ficaram grandes
    
    # Criar barra de progresso
    progress_bar = st.progress(0)
    
    # Para cada linha no DataFrame
    for index, row in df.iterrows():
        # Atualizar barra de progresso
        progress = int((index / total_ups) * 100)
        progress_bar.progress(progress)
        
        up_code = str(row['UP']).strip()
        status_container.write(f"Processando UP {up_code} ({index+1} de {total_ups})...")
        
        nucleo = str(row['Nucleo']).strip()
        ocorrencia_predominante = str(row['Ocorrência Predominante']).strip()

        # Filtrar imagem e croqui
        possible_image_files = [
            (n, u)
            for (n, u) in image_files
            if n[:6].upper() == up_code.upper()
        ]
        possible_croquis_files = [
            (n, u)
            for (n, u) in croquis_files
            if up_code.upper() in n.upper()
        ]

        if not possible_image_files and not possible_croquis_files:
            st.warning(f"Nenhum arquivo encontrado para UP {up_code}. Criando PDF com placeholders.")
            
            # Criar pasta mesmo sem arquivos
            folder_name = f"{entrega_nome} - {nucleo} - {ocorrencia_predominante}"
            folder_path = os.path.join(output_dir, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            # Definir caminhos mesmo que os arquivos não existam
            image_path = os.path.join(folder_path, f"{up_code}_image.jpg")
            croqui_path = os.path.join(folder_path, f"{up_code}_croqui.jpg")
            
            try:
                # Criar PDF com placeholders para ambas as imagens
                pdf_path = os.path.join(folder_path, f"{up_code}.pdf")
                file_size, success = create_pdf_with_placeholders(row, image_path, croqui_path, pdf_path)
                
                if success:
                    processed_ups += 1
                    if file_size > 9.0:
                        large_files += 1
                    st.success(f"PDF criado com placeholders para UP {up_code} ({file_size} MB)")
                else:
                    failed_ups += 1
                    failed_up_list.append(f"{up_code} (erro ao criar PDF com placeholders)")
                continue
                
            except Exception as e:
                st.error(f"Erro ao processar UP {up_code} com placeholders: {e}")
                failed_ups += 1
                failed_up_list.append(f"{up_code} (erro geral com placeholders)")
                continue

        # Criar pasta quando pelo menos um arquivo for encontrado
        folder_name = f"{entrega_nome} - {nucleo} - {ocorrencia_predominante}"
        folder_path = os.path.join(output_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # Definir caminhos e URLs dos arquivos
        image_name, image_url = possible_image_files[0] if possible_image_files else (None, None)
        croqui_name, croqui_url = possible_croquis_files[0] if possible_croquis_files else (None, None)

        image_path = os.path.join(folder_path, f"{up_code}_image.jpg")
        croqui_path = os.path.join(folder_path, f"{up_code}_croqui.jpg")

        try:
            # Baixar arquivos que existem
            if possible_image_files:
                download_file(ctx, image_url, image_path)
            else:
                st.warning(f"Imagem não encontrada para UP {up_code}. Será usado placeholder.")
                
            if possible_croquis_files:
                download_file(ctx, croqui_url, croqui_path)
            else:
                st.warning(f"Croqui não encontrado para UP {up_code}. Será usado placeholder.")

            # Criar PDF otimizado com suporte a placeholders
            pdf_path = os.path.join(folder_path, f"{up_code}.pdf")
            file_size, success = create_pdf_with_placeholders(row, image_path, croqui_path, pdf_path)
            
            if not success:
                failed_ups += 1
                failed_up_list.append(f"{up_code} (erro ao criar PDF)")
                continue
            
            # Verificar tamanho e aplicar compressão extra se necessário
            if file_size > 9.0:
                status_container.write(f"PDF muito grande ({file_size} MB), aplicando compressão extra...")
                file_size, success = create_pdf_extra_compressed(row, image_path, croqui_path, pdf_path)
                
                if not success:
                    failed_ups += 1
                    failed_up_list.append(f"{up_code} (erro na compressão extra)")
                    continue
                
                if file_size > 9.0:
                    large_files.append(f"{up_code} ({file_size} MB)")
                    st.warning(f"PDF ainda grande após compressão extra: {file_size} MB")
            
            successful_pdfs += 1

        except Exception as e:
            st.error(f"Erro ao processar UP {up_code}: {str(e)}")
            failed_ups += 1
            failed_up_list.append(f"{up_code} (erro: {str(e)[:50]}...)")
    
    # Limpar contêineres de progresso
    progress_container.empty()
    status_container.empty()
    
    # Relatório final
    st.success("Processamento concluído!")
    st.write("## Relatório Final")
    st.write(f"Total de UPs no arquivo Excel: {total_ups}")
    st.write(f"PDFs gerados com sucesso: {successful_pdfs}")
    st.write(f"UPs que falharam: {failed_ups}")
    
    if successful_pdfs > 0:
        st.write(f"Taxa de sucesso: {(successful_pdfs/total_ups)*100:.1f}%")
    
    if large_files:
        st.warning("### Arquivos que ainda ficaram grandes (>9MB):")
        for large_file in large_files:
            st.write(f"- {large_file}")
        st.info("Dica: Estes arquivos podem ter imagens muito grandes ou complexas.")
    
    if failed_up_list:
        st.error("### UPs que falharam:")
        for failed_up in failed_up_list:
            st.write(f"- {failed_up}")
    
    # Link para o diretório com os PDFs gerados
    st.success(f"Os PDFs foram salvos em: {output_dir}")
    
    # Botão para abrir o diretório dos PDFs
    if st.button("Abrir diretório com os PDFs"):
        import subprocess
        try:
            os.startfile(output_dir)  # Windows
        except:
            try:
                subprocess.Popen(['xdg-open', output_dir])  # Linux
            except:
                try:
                    subprocess.Popen(['open', output_dir])  # macOS
                except:
                    st.error("Não foi possível abrir o diretório automaticamente.")

# =========================================================================
# INTERFACE STREAMLIT
# =========================================================================

def criar_pdf_streamlit():
    st.title("Criação de PDFs com Imagens e Croquis")
    
    st.markdown("""
    ### 📊 Ferramenta de Geração de PDFs para UPs
    
    Esta ferramenta permite criar PDFs combinando dados do Excel com imagens e croquis do SharePoint.
    
    **Instruções:**
    1. Faça upload do arquivo Excel contendo os dados das UPs
    2. Forneça as informações de acesso ao SharePoint
    3. Configure as pastas e o nome da entrega
    4. Clique em "Iniciar Processamento"
    """)
    
    # Upload do arquivo Excel
    st.header("1. Upload do Arquivo Excel")
    uploaded_file = st.file_uploader("Selecione o arquivo Excel", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        # Ler o arquivo Excel
        try:
            df = pd.read_excel(uploaded_file, sheet_name="Export")
            st.success(f"Arquivo carregado com sucesso! {len(df)} linhas encontradas.")
            
            # Mostrar preview
            st.write("Preview dos dados:")
            st.dataframe(df.head())
            
            # Configuração do SharePoint
            st.header("2. Configuração do SharePoint")
            
            username = st.text_input("E-mail do SharePoint:", value=default_username)
            password = st.text_input("Senha do SharePoint:", type="password")
            
            # Configuração dos caminhos
            st.header("3. Configuração de Pastas e Entrega")
            
            entrega_nome = st.text_input("Nome da Entrega (ex: Entrega 4):", value="Entrega")
            
            st.markdown("""
            **Dica para URL do SharePoint:**
            Você pode copiar a URL diretamente do navegador, por exemplo:
            `https://suzano.sharepoint.com/:f:/r/sites/TOPS-VALIDAO/Documentos%20Compartilhados/TOPS/ENTREGA_5/FOTOS`
            
            Ou usar o caminho relativo:
            `/sites/TOPS-VALIDAO/Documentos Compartilhados/TOPS/ENTREGA_5/FOTOS`
            """)
            
            images_folder_input = st.text_input("URL/Caminho da pasta de IMAGENS no SharePoint:")
            croquis_folder_input = st.text_input("URL/Caminho da pasta de CROQUIS no SharePoint:")
            
            # Converter caminhos do SharePoint
            if images_folder_input and croquis_folder_input:
                images_folder_url = convert_sharepoint_url_to_path(images_folder_input)
                croquis_folder_url = convert_sharepoint_url_to_path(croquis_folder_input)
                
                st.write("Caminhos convertidos:")
                st.code(f"Imagens: {images_folder_url}")
                st.code(f"Croquis: {croquis_folder_url}")
            
            # Seleção da pasta de saída
            st.header("4. Pasta de Saída")
            output_dir = st.text_input("Caminho para salvar os PDFs gerados:", 
                                      value=os.path.join(os.path.expanduser("~"), "Documents", "PDFs_Gerados"))
            
            # Botão para iniciar processamento
            if st.button("Iniciar Processamento"):
                if not username or not password:
                    st.error("Por favor, forneça as credenciais do SharePoint.")
                elif not images_folder_input or not croquis_folder_input:
                    st.error("Por favor, forneça os caminhos das pastas de imagens e croquis.")
                elif not output_dir:
                    st.error("Por favor, forneça um diretório de saída.")
                else:
                    try:
                        # Conectar ao SharePoint
                        with st.spinner("Conectando ao SharePoint..."):
                            ctx = connect_to_sharepoint(site_url, username, password)
                            st.success("Conexão com SharePoint estabelecida com sucesso!")
                        
                        # Iniciar processamento
                        process_properties_streamlit(
                            df, ctx, images_folder_url, croquis_folder_url, output_dir, entrega_nome
                        )
                    except Exception as e:
                        st.error(f"Erro: {str(e)}")
        
        except Exception as e:
            st.error(f"Erro ao ler o arquivo Excel: {str(e)}")

# Função principal - chamada pelo arquivo app.py principal
def main():
    criar_pdf_streamlit()

if __name__ == "__main__":
    main()
