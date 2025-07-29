# Sistema RPA Fênix - Configurações Centralizadas

"""
Configurações centralizadas do sistema RPA Fênix
"""

import os
from pathlib import Path

# =========================================================================
# CONFIGURAÇÕES GERAIS
# =========================================================================

# Caminhos
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# URLs
FENIX_URL = "https://fenixflorestal.suzanonet.com.br/"

# =========================================================================
# CONFIGURAÇÕES STREAMLIT
# =========================================================================

STREAMLIT_CONFIG = {
    'page_title': "Sistema RPA Fênix",
    'page_icon': "🌲",
    'layout': "wide",
    'initial_sidebar_state': "expanded"
}

# =========================================================================
# CONFIGURAÇÕES DE AUTOMAÇÃO
# =========================================================================

AUTOMATION_CONFIG = {
    'headless': False,      # Mostrar navegador
    'timeout': 30000,       # Timeout em ms
    'wait_between_actions': 1000,  # Pausa entre ações em ms
    'max_retries': 3,       # Máximo de tentativas por ação
}

# =========================================================================
# TEXTOS PADRÃO PARA LAUDOS
# =========================================================================

TEXTOS_PADRAO = {
    'objetivo': "O presente relatório foi elaborado por solicitação do GEOCAT com o objetivo de avaliar os efeitos dos sinistros nos plantios do Núcleo {nucleo} e determinar as recomendações para as áreas avaliadas em campo pela área de Mensuração.",
    
    'diagnostico': """Foi objeto deste Laudo as áreas afetadas por incêndios florestais e vendaval (Déficit Hídrico), conforme as características de danos a seguir:

Seca e mortalidade dos plantios devido ao fogo ou déficit hídrico em diferentes níveis de severidade;

Inclinação, tombamento e quebra de árvores devido a ocorrência de vendaval.

Para as ocorrências foram observados danos em reboleiras de diferentes tamanhos de área (ha) e intensidade dentro dos talhões.""",
    
    'licoes_aprendidas': """As visitas de campo juntamente com imagens de drones são fundamentais para a tomada de decisão. As ocorrências de sinistros são dinâmicas e, desta forma, é fundamental aguardar o tempo recomendado para a verificação da recuperação das plantas bem como manter as informações atualizadas, especialmente nas ocorrências de Déficit Hídrico e Incêndios Florestais. A efetivação da baixa e tratativas devem ocorrer imediatamente após a liberação do laudo, evitando-se retrabalho e dificuldades na rastreabilidade de todo o processo, assim como o comprometimento da produtividade no site.""",
    
    'consideracoes_finais': """Face ao exposto, com a avaliação de ha, recomenda-se:

O valor total imobilizado a ser apurado como prejuízo será de R$ X (XX reais e XXXX centavos), informado pela área Contábil. Vale ressaltar que o montante descrito pode sofrer alterações entre o período de emissão, assinaturas e devida baixa dos ativos; no momento da baixa, a Gestão Patrimonial fará a atualização e manterá comprovação anexa ao laudo. A destinação da madeira e eventuais dificuldades operacionais não foram objeto deste laudo.

As recomendações são por UP, considerando a ocorrência de maior abrangência; pode, contudo, existir mais de um tipo de sinistro na mesma UP, sendo necessária uma avaliação detalhada do microplanejamento quanto ao aproveitamento da madeira.

O laudo foi elaborado com base em croquis e fotos fornecidos pela equipe de mensuração florestal. A ausência de imagens aéreas de alta resolução e a falta de visitas de campo por parte dos extensionistas prejudicam a avaliação detalhada das UPs. Assim, se a equipe de Silvicultura, durante a execução das ações recomendadas, constatar divergências em campo, recomenda-se delimitar a área divergente a ser aproveitada e solicitar uma análise adicional à equipe de extensão tecnológica."""
}

# =========================================================================
# MAPEAMENTOS E REGRAS DE NEGÓCIO
# =========================================================================

# Mapeamento UNF por núcleo
UNF_MAPPING = {
    'BA2': 'BA', 'BA3': 'BA', 'BA4': 'BA', 'BA5': 'BA',
    'CS1': 'CS', 'CS2': 'CS', 'CS3': 'CS',
    'ES1': 'ES', 'ES2': 'ES', 'ES3': 'ES',
    'MA1': 'MA', 'MA2': 'MA', 'MA3': 'MA',
    'MS1': 'MS', 'MS2': 'MS', 'MS3': 'MS',
    'SP1': 'SP', 'SP2': 'SP', 'SP3': 'SP'
}

# Colunas obrigatórias do Excel
COLUNAS_OBRIGATORIAS = [
    'UP', 'Nucleo', 'Idade', 'Ocorrência Predominante',
    'Severidade Predominante', 'Incidencia', 'Laudo Existente',
    'Recomendacao'
]

# Validações
SEVERIDADES_VALIDAS = ['BAIXO', 'MEDIO', 'ALTO']
OCORRENCIAS_VALIDAS = [
    'VENDAVAL', 'INCENDIO', 'DEFICIT_HIDRICO', 'PRAGAS', 
    'DOENCA_BIOTICA', 'DOENCA_ABIOTICA', 'GEADA'
]

# =========================================================================
# FUNÇÕES UTILITÁRIAS
# =========================================================================

def criar_diretorios():
    """Cria diretórios necessários"""
    DATA_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

def validar_configuracao():
    """Valida configurações do sistema"""
    errors = []
    
    # Verificar diretórios
    if not BASE_DIR.exists():
        errors.append(f"Diretório base não encontrado: {BASE_DIR}")
    
    return errors

# =========================================================================
# INICIALIZAÇÃO
# =========================================================================

if __name__ == "__main__":
    criar_diretorios()
    errors = validar_configuracao()
    
    if errors:
        print("❌ Erros de configuração encontrados:")
        for error in errors:
            print(f"  • {error}")
    else:
        print("✅ Configuração validada com sucesso!")
        print(f"📁 Diretório base: {BASE_DIR}")
        print(f"🌐 URL Fênix: {FENIX_URL}")
        print(f"🏢 Núcleos configurados: {len(UNF_MAPPING)}")
        print(f"📊 Colunas obrigatórias: {len(COLUNAS_OBRIGATORIAS)}")
