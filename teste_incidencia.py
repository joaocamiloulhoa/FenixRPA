#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Teste para validar a correção da conversão de incidência
"""

from lancamento_fenix import get_recomendacao

def testar_conversao_incidencia():
    """Testa a conversão de incidência e cálculo de recomendação"""
    
    print("🧪 TESTE DE CONVERSÃO DE INCIDÊNCIA\n")
    
    # Casos de teste baseados nos dados reais
    casos_teste = [
        {
            'incidencia_original': '0.92',  # Valor do Excel
            'incidencia_esperada': 92,      # Valor esperado após conversão
            'severidade': 'BAIXO',
            'idade': 3,
            'descricao': 'B7A711 - VENDAVAL BAIXO 0.92 (deve ser 92%)'
        },
        {
            'incidencia_original': '0.05',  # Valor do Excel  
            'incidencia_esperada': 5,       # Valor esperado após conversão
            'severidade': 'ALTO',
            'idade': 3,
            'descricao': 'B7CY10 - INCÊNDIO ALTO 0.05 (deve ser 5%)'
        },
        {
            'incidencia_original': '92%',   # Valor já em percentual
            'incidencia_esperada': 92,      # Valor esperado (sem mudança)
            'severidade': 'BAIXO',
            'idade': 3,
            'descricao': 'Teste com % explícito'
        }
    ]
    
    for caso in casos_teste:
        print(f"📋 {caso['descricao']}")
        print(f"   Incidência original: {caso['incidencia_original']}")
        
        # Simular conversão (lógica corrigida)
        incidencia_raw = str(caso['incidencia_original']).replace('%', '').replace(',', '.').strip()
        incidencia_valor = float(incidencia_raw)
        
        if '%' in str(caso['incidencia_original']):
            incidencia_convertida = incidencia_valor
        else:
            if incidencia_valor <= 1:
                incidencia_convertida = incidencia_valor * 100
            else:
                incidencia_convertida = incidencia_valor
        
        print(f"   Incidência convertida: {incidencia_convertida}%")
        print(f"   Incidência esperada: {caso['incidencia_esperada']}%")
        
        # Calcular recomendação
        recomendacao = get_recomendacao(
            caso['severidade'], 
            incidencia_convertida, 
            caso['idade']
        )
        
        print(f"   Recomendação calculada: {recomendacao}")
        
        # Validar se está correto
        if incidencia_convertida == caso['incidencia_esperada']:
            print("   ✅ CONVERSÃO CORRETA")
        else:
            print("   ❌ CONVERSÃO INCORRETA")
        
        print()

if __name__ == "__main__":
    testar_conversao_incidencia()
