"""
Script de teste para a funcionalidade de placeholders em PDFs
"""
import os
import sys
import tempfile
from cria_pdf import create_pdf_with_placeholders, create_image_placeholder

def test_placeholder_functionality():
    """
    Testa a criação de PDFs com placeholders para imagens ausentes
    """
    print("🧪 Testando funcionalidade de placeholders...")
    
    # Dados de exemplo para o PDF
    up_data = {
        'UP-C-R': 'TEST-001-R',
        'UP': 'TEST-001',
        'Nucleo': 'Núcleo Teste',
        'Data_Ocorrência': '2024-01-15',
        'Idade': '5.2',
        'Quant.Ocorrências': '3',
        'Ocorrência Predominante': 'Teste de Placeholder',
        'Severidade Predominante': 'Baixa',
        'Area UP': '10.5',
        'Area Liquida': '9.8',
        'Incidencia': '28.6',
        'Quantidade de Imagens*': '2',
        'Recomendacao': 'Esta é uma recomendação de teste para verificar a funcionalidade de placeholders.'
    }
    
    # Criar pasta temporária para teste
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Pasta temporária: {temp_dir}")
    
    # Caminhos de arquivos que não existem (para testar placeholders)
    image_path = os.path.join(temp_dir, "imagem_inexistente.jpg")
    croqui_path = os.path.join(temp_dir, "croqui_inexistente.jpg")
    pdf_path = os.path.join(temp_dir, "teste_placeholder.pdf")
    
    print("🔍 Testando com ambas as imagens ausentes...")
    
    try:
        # Testar criação de PDF com placeholders
        file_size, success = create_pdf_with_placeholders(
            up_data, image_path, croqui_path, pdf_path
        )
        
        if success:
            print(f"✅ PDF criado com sucesso! Tamanho: {file_size} MB")
            print(f"📄 PDF salvo em: {pdf_path}")
            
            # Verificar se o arquivo foi realmente criado
            if os.path.exists(pdf_path):
                actual_size = os.path.getsize(pdf_path) / (1024 * 1024)
                print(f"🔍 Tamanho real do arquivo: {actual_size:.2f} MB")
            else:
                print("❌ Arquivo PDF não foi encontrado!")
                
        else:
            print("❌ Falha ao criar PDF")
            
    except Exception as e:
        print(f"🚨 Erro durante o teste: {e}")
        
    # Teste do placeholder individual
    print("\n🖼️ Testando criação de placeholder individual...")
    try:
        placeholder_path = create_image_placeholder(400, 300)
        if placeholder_path and os.path.exists(placeholder_path):
            print(f"✅ Placeholder criado: {placeholder_path}")
            # Limpar placeholder
            os.remove(placeholder_path)
        else:
            print("❌ Falha ao criar placeholder")
    except Exception as e:
        print(f"🚨 Erro ao criar placeholder: {e}")
    
    print(f"\n🧹 Limpando arquivos temporários...")
    # Limpar arquivos de teste
    try:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        os.rmdir(temp_dir)
        print("✅ Limpeza concluída")
    except Exception as e:
        print(f"⚠️ Aviso na limpeza: {e}")
    
    print("\n🎉 Teste concluído!")

if __name__ == "__main__":
    test_placeholder_functionality()
