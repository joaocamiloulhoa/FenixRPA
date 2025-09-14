import pandas as pd

# Criar dados de exemplo para testar
dados_exemplo = {
    'UP': ['123456', '123457', '123458', '789001', '789002'],
    'Nucleo': ['UNF_A', 'UNF_A', 'UNF_A', 'UNF_B', 'UNF_B'],
    'Idade': [5, 6, 4, 7, 5],
    'Ocorrência Predominante': ['Incêndio', 'Seca', 'Vendaval', 'Incêndio', 'Seca'],
    'Severidade Predominante': ['Alta', 'Média', 'Baixa', 'Alta', 'Média'],
    'Area UP': [10.5, 8.2, 12.3, 15.1, 9.8],
    'Area Liquida': [9.8, 7.5, 11.2, 14.2, 8.9],
    'Incidencia': [100, 80, 60, 90, 75],
    'Recomendacao': ['Replantio', 'Monitoramento', 'Poda', 'Replantio', 'Irrigação']
}

# Criar DataFrame
df = pd.DataFrame(dados_exemplo)

# Salvar como Excel com a aba "Export"
with pd.ExcelWriter('exemplo_teste.xlsx') as writer:
    df.to_excel(writer, sheet_name='Export', index=False)

print("Arquivo exemplo_teste.xlsx criado com sucesso!")
print(f"UNFs disponíveis: {df['Nucleo'].unique()}")
print(f"Total de UPs: {len(df)}")
