import pandas as pd
import os

# Criar dados de exemplo para demonstração
dados_exemplo = {
    'UP-C-R': ['UP001-C-R', 'UP002-C-R', 'UP003-C-R'],
    'UP': ['UP001', 'UP002', 'UP003'],
    'Nucleo': ['Núcleo Norte', 'Núcleo Sul', 'Núcleo Leste'],
    'Data_Ocorrência': ['2025-01-15', '2025-01-20', '2025-01-25'],
    'Idade': ['5.2', '3.8', '7.1'],
    'Quant.Ocorrências': ['3', '2', '5'],
    'Ocorrência Predominante': ['Pragas', 'Doenças', 'Deficiência Nutricional'],
    'Severidade Predominante': ['Baixa', 'Média', 'Alta'],
    'Area UP': ['10.5', '15.2', '8.9'],
    'Area Liquida': ['9.8', '14.1', '8.2'],
    'Incidencia': ['28.6', '35.2', '42.1'],
    'Quantidade de Imagens*': ['2', '2', '2'],
    'Recomendacao': [
        'Aplicar inseticida conforme protocolo técnico estabelecido',
        'Implementar manejo integrado com fungicida sistêmico',
        'Realizar adubação foliar com micronutrientes específicos'
    ]
}

# Criar DataFrame
df = pd.DataFrame(dados_exemplo)

# Salvar como Excel para demonstração
arquivo_demo = 'dados_exemplo_fenix.xlsx'
with pd.ExcelWriter(arquivo_demo, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Export', index=False)

print(f"✅ Arquivo de demonstração criado: {arquivo_demo}")
print("📊 Dados incluídos:")
for i, row in df.iterrows():
    print(f"   - UP {row['UP']}: {row['Ocorrência Predominante']}")
    
print("\n💡 Como usar:")
print("1. Execute o sistema: python executar_sistema.py") 
print("2. Selecione 'Modo Offline'")
print("3. Faça upload deste arquivo Excel")
print("4. PDFs serão criados com placeholders")
