"""
Módulo de Lançamento no Fênix - Sistema RPA
Este módulo contém toda a lógica de automação para o portal Fênix Florestal
"""

import streamlit as st
import pandas as pd
import time
import io
from datetime import datetime
from playwright.async_api import async_playwright
import asyncio
import sys

# =========================================================================
# CONFIGURAÇÕES E CONSTANTES
# =========================================================================

FENIX_URL = "https://fenixflorestal.suzanonet.com.br/"

# Textos padronizados para os laudos
TEXTOS_PADRAO = {
    'objetivo_nucleo': "O presente relatório foi elaborado por solicitação do GEOCAT com o objetivo de avaliar os efeitos dos sinistros nos plantios do Núcleo {nome} e determinar as recomendações para as áreas avaliadas em campo pela área de Mensuração.",
    'objetivo_propriedade': "O presente relatório foi elaborado por solicitação do GEOCAT com o objetivo de avaliar os efeitos dos sinistros nos plantios da Fazenda {nome} e determinar as recomendações para as áreas avaliadas em campo pela área de Mensuração.",
    
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

# Mapeamento UNF por núcleo
UNF_MAPPING = {
    # Bahia
    'BA2': 'BA', 'BA3': 'BA', 'BA4': 'BA', 'BA5': 'BA',
    'ba2': 'BA', 'ba3': 'BA', 'ba4': 'BA', 'ba5': 'BA',
    
    # Capão da Serra
    'CS1': 'CS', 'CS2': 'CS', 'CS3': 'CS',
    'cs1': 'CS', 'cs2': 'CS', 'cs3': 'CS',
    
    # Espírito Santo
    'ES1': 'ES', 'ES2': 'ES', 'ES3': 'ES',
    'es1': 'ES', 'es2': 'ES', 'es3': 'ES',
    
    # Maranhão
    'MA1': 'MA', 'MA2': 'MA', 'MA3': 'MA',
    'ma1': 'MA', 'ma2': 'MA', 'ma3': 'MA',
    
    # Mato Grosso do Sul
    'MS1': 'MS', 'MS2': 'MS', 'MS3': 'MS',
    'ms1': 'MS', 'ms2': 'MS', 'ms3': 'MS',
    
    # São Paulo
    'SP1': 'SP', 'SP2': 'SP', 'SP3': 'SP',
    'sp1': 'SP', 'sp2': 'SP', 'sp3': 'SP',
    
    # Possíveis variações adicionais
    'BA': 'BA', 'CS': 'CS', 'ES': 'ES', 'MA': 'MA', 'MS': 'MS', 'SP': 'SP'
}

# =========================================================================
# FUNÇÕES DE REGRAS DE NEGÓCIO
# =========================================================================

def get_recomendacao(severidade, incidencia, idade):
    """
    Determina a recomendação baseada na severidade, incidência e idade
    
    Opções disponíveis no sistema:
    - Antecipar Colheita
    - Antecipar Colheita Parcial  
    - Manter Ciclo
    - Limpeza de Área
    - Limpeza de Área Parcial
    - Reavaliar
    
    Regras:
    - Baixa: sempre "Manter Ciclo"
    - Média + Incidencia < 25%: "Manter Ciclo" 
    - Média + Incidencia >= 25%: "Reavaliar"
    - Alta + 0-5%: "Manter Ciclo"
    - Alta + 5-25%: "Reavaliar"  
    - Alta + 25-100%:
      - Idade > 6 anos: sempre "Antecipar Colheita"
      - Idade > 3 anos: "Antecipar Colheita" se inc > 75%, senão "Antecipar Colheita Parcial"
      - Idade <= 3 anos: "Limpeza de Área" se inc > 75%, senão "Limpeza de Área Parcial"
    """
    try:
        # Normalizar valores
        severidade_str = str(severidade).strip().upper()
        incidencia = float(incidencia) if isinstance(incidencia, (int, float)) else 0
        idade = float(idade) if isinstance(idade, (int, float)) else 0
        
        print(f"[REGRA] Severidade: {severidade_str}, Incidência: {incidencia}%, Idade: {idade} anos")
        
        # Mapear severidades - aceitar variações
        if severidade_str in ['BAIXA', 'BAIXO', 'LOW', 'B']:
            print(f"[REGRA] Severidade BAIXA → Manter Ciclo")
            return "Manter Ciclo"
        
        elif severidade_str in ['MÉDIA', 'MEDIA', 'MEDIO', 'MEDIUM', 'M']:
            if incidencia < 25:
                print(f"[REGRA] Severidade MÉDIA + Incidência {incidencia}% < 25% → Manter Ciclo")
                return "Manter Ciclo"
            else:
                print(f"[REGRA] Severidade MÉDIA + Incidência {incidencia}% >= 25% → Reavaliar")
                return "Reavaliar"
        
        elif severidade_str in ['ALTA', 'ALTO', 'HIGH', 'A']:
            if incidencia <= 5:
                print(f"[REGRA] Severidade ALTA + Incidência {incidencia}% <= 5% → Manter Ciclo")
                return "Manter Ciclo"
            elif incidencia <= 25:
                print(f"[REGRA] Severidade ALTA + Incidência {incidencia}% <= 25% → Reavaliar")
                return "Reavaliar"
            else:  # incidencia > 25
                if idade > 6:
                    print(f"[REGRA] Severidade ALTA + Incidência {incidencia}% > 25% + Idade {idade} > 6 anos → Antecipar Colheita")
                    return "Antecipar Colheita"
                elif idade > 3:
                    if incidencia > 75:
                        print(f"[REGRA] Severidade ALTA + Incidência {incidencia}% > 75% + Idade {idade} > 3 anos → Antecipar Colheita")
                        return "Antecipar Colheita"
                    else:
                        print(f"[REGRA] Severidade ALTA + Incidência {incidencia}% <= 75% + Idade {idade} > 3 anos → Antecipar Colheita Parcial")
                        return "Antecipar Colheita Parcial"
                else:  # idade <= 3
                    if incidencia > 75:
                        print(f"[REGRA] Severidade ALTA + Incidência {incidencia}% > 75% + Idade {idade} <= 3 anos → Limpeza de Área")
                        return "Limpeza de Área"
                    else:
                        print(f"[REGRA] Severidade ALTA + Incidência {incidencia}% <= 75% + Idade {idade} <= 3 anos → Limpeza de Área Parcial")
                        return "Limpeza de Área Parcial"
        
        print(f"[REGRA] Severidade não reconhecida: '{severidade_str}' → Default: Manter Ciclo")
        return "Manter Ciclo"  # Default
        
    except Exception:
        return "Manter Ciclo"  # Default em caso de erro

def detectar_unf_por_nucleo(nucleo):
    """Detecta UNF baseado no núcleo"""
    if not nucleo:
        return 'CS'  # Default
    
    # Converter para string e limpar
    nucleo_str = str(nucleo).strip()
    
    # Tentar mapeamento direto (case-sensitive)
    if nucleo_str in UNF_MAPPING:
        return UNF_MAPPING[nucleo_str]
    
    # Tentar mapeamento case-insensitive
    nucleo_upper = nucleo_str.upper()
    nucleo_lower = nucleo_str.lower()
    
    for key, value in UNF_MAPPING.items():
        if key.upper() == nucleo_upper or key.lower() == nucleo_lower:
            return value
    
    # Tentar extrair padrão (ex: "CS1abc" -> "CS1")
    import re
    match = re.match(r'^([A-Za-z]{2}\d*)', nucleo_str)
    if match:
        extracted = match.group(1)
        if extracted in UNF_MAPPING:
            return UNF_MAPPING[extracted]
        # Tentar case-insensitive do padrão extraído
        for key, value in UNF_MAPPING.items():
            if key.upper() == extracted.upper():
                return value
    
    # Se começar com duas letras, usar as duas letras como UNF
    if len(nucleo_str) >= 2 and nucleo_str[:2].isalpha():
        return nucleo_str[:2].upper()
    
    # Default fallback
    return 'CS'

# =========================================================================
# CLASSE PRINCIPAL DE AUTOMAÇÃO
# =========================================================================

class FenixAutomation:
    def __init__(self, tipo_organizacao='nucleo'):
        self.browser = None
        self.page = None
        self.playwright = None
        self.tipo_organizacao = tipo_organizacao  # 'nucleo' ou 'propriedade'
        
        self.stats = {
            'inicio': None,
            'nucleos_processados': 0,
            'ups_processadas': 0,
            'ups_com_erro': 0,
            'ups_com_sucesso': [],  # Lista das UPs processadas com sucesso
            'erros': []
        }
    
    def log_status(self, message: str, level: str = "info"):
        """Log de status integrado com Streamlit"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Log no Streamlit baseado no nível
        if level == "info":
            st.info(formatted_message)
        elif level == "success":
            st.success(formatted_message)
        elif level == "warning":
            st.warning(formatted_message)
        elif level == "error":
            st.error(formatted_message)
        
        # Log no console também
        print(formatted_message)
    
    def forcar_reinicializacao_navegador(self):
        """Força a reinicialização do navegador limpando o estado"""
        try:
            self.log_status("🔄 Forçando reinicialização do navegador...")
            
            # Limpar session_state
            st.session_state.browser_ativo = False
            if hasattr(st.session_state, 'automation_instance'):
                del st.session_state.automation_instance
            
            # Limpar instâncias locais
            self.browser = None
            self.page = None
            self.context = None
            self.playwright = None
            
            self.log_status("✅ Estado do navegador limpo. Próxima execução criará nova instância.")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao forçar reinicialização: {str(e)}", "error")
            return False
    
    async def inicializar_browser(self):
        """Inicializa o browser Playwright"""
        try:
            self.log_status("🔧 Inicializando navegador...")
            
            # Correção específica para Windows com asyncio
            import sys
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=[
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--no-sandbox'
                ]
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
            self.log_status("✅ Navegador inicializado com sucesso!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao inicializar navegador: {str(e)}", "error")
            return False
    
    async def navegar_para_fenix(self):
        """Navega para o site do Fênix"""
        try:
            self.log_status(f"🌐 Navegando para {FENIX_URL}")
            await self.page.goto(FENIX_URL)
            await self.page.wait_for_load_state('networkidle')
            
            self.log_status("✅ Página do Fênix carregada!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao navegar: {str(e)}", "error")
            return False
    
    async def aguardar_login(self):
        """Aguarda o usuário fazer login manualmente"""
        self.log_status("🔐 Aguardando login manual...", "warning")
        self.log_status("⚠️ Se aparecer tela de login, faça o login no navegador aberto.")
        
        try:
            # Aguardar até 2 minutos pelo login
            max_tentativas = 60  # 60 tentativas de 2 segundos
            tentativa = 0
            
            while tentativa < max_tentativas:
                try:
                    # Verificar se existe o botão "Submissão de Laudos" (indica login feito)
                    submissao_btn = await self.page.query_selector('button:has-text("Submissão de Laudos")')
                    if submissao_btn:
                        self.log_status("✅ Login detectado! Continuando...", "success")
                        return True
                    
                    await asyncio.sleep(2)
                    tentativa += 1
                    
                    # Feedback a cada 30 segundos
                    if tentativa % 15 == 0:
                        self.log_status(f"⏳ Ainda aguardando login... ({tentativa * 2}s)")
                        
                except Exception:
                    await asyncio.sleep(2)
                    tentativa += 1
            
            # Se chegou aqui, assumir que o login foi feito
            self.log_status("⚠️ Timeout no login. Assumindo que foi realizado e continuando...", "warning")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro durante aguardo de login: {str(e)}", "error")
            return False
    
    async def verificar_estado_navegador(self):
        """Verifica se o navegador está responsivo e em que página estamos"""
        try:
            # Verificar se o navegador está responsivo
            await self.page.evaluate('document.title')
            
            current_url = self.page.url
            page_title = await self.page.title()
            
            self.log_status(f"🔍 Estado do navegador - URL: {current_url}")
            self.log_status(f"🔍 Estado do navegador - Título: {page_title}")
            
            return True
            
        except Exception as e:
            self.log_status(f"❌ Navegador não está responsivo: {str(e)}")
            return False

    async def voltar_para_inicio(self):
        """Navega de volta para a página inicial se necessário"""
        try:
            # Primeiro verificar se o navegador está responsivo
            if not await self.verificar_estado_navegador():
                self.log_status("⚠️ Navegador não responsivo, tentando continuar mesmo assim...")
                return False
            
            current_url = self.page.url
            self.log_status(f"🔍 Verificando página atual: {current_url}")
            
            # Verificar se já estamos na página correta
            try:
                await self.page.wait_for_selector('button:has-text("Submissão de Laudos")', timeout=3000)
                self.log_status("✅ Já estamos na página inicial correta!")
                return True
            except:
                # Não estamos na página inicial
                pass
            
            # Se não estamos na página inicial, voltar
            if "fenixflorestal.suzanonet.com.br" not in current_url or "upload" in current_url.lower() or "assinatura" in current_url.lower():
                self.log_status("🔄 Navegando de volta para a página inicial...")
                await self.page.goto("https://fenixflorestal.suzanonet.com.br/")
                await asyncio.sleep(2)
                
                # Verificar se chegamos na página inicial
                try:
                    await self.page.wait_for_selector('button:has-text("Submissão de Laudos")', timeout=15000)
                    self.log_status("✅ Página inicial carregada com sucesso!")
                    return True
                except:
                    self.log_status("⚠️ Botão 'Submissão de Laudos' ainda não encontrado após navegar...")
                    
                    # Tentar recarregar a página
                    self.log_status("🔄 Tentando recarregar a página...")
                    await self.page.reload()
                    await asyncio.sleep(2)
                    
                    try:
                        await self.page.wait_for_selector('button:has-text("Submissão de Laudos")', timeout=15000)
                        self.log_status("✅ Página inicial carregada após recarregar!")
                        return True
                    except:
                        self.log_status("❌ Não foi possível carregar a página inicial corretamente")
                        return False
            
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao voltar para início: {str(e)}")
            return False

    async def navegar_para_upload(self):
        """Navega para a seção de upload de laudos"""
        try:
            self.log_status("📁 Navegando para 'Submissão de Laudos'...")
            
            # CORREÇÃO: Primeiro verificar se o navegador está responsivo
            if not await self.verificar_estado_navegador():
                raise Exception("Navegador não está responsivo")
            
            # CORREÇÃO: Primeiro tentar voltar para página inicial se necessário
            if not await self.voltar_para_inicio():
                raise Exception("Não foi possível navegar para a página inicial")
            
            # CORREÇÃO: Aguardar página carregar antes de procurar elementos
            await asyncio.sleep(2)
            
            # Verificar se já estamos na página de upload
            try:
                # Se já estivermos na página de upload, não precisamos navegar
                await self.page.wait_for_selector('text="Upload de Laudos"', timeout=3000)
                self.log_status("✅ Já na página de upload!", "success")
                return True
            except:
                # Não estamos na página de upload, precisamos navegar
                pass
            
            # Múltiplas estratégias para encontrar "Submissão de Laudos"
            submissao_selectors = [
                'button:has-text("Submissão de Laudos")',
                'xpath=//button[contains(text(), "Submissão de Laudos")]',
                'xpath=//*[contains(text(), "Submissão de Laudos")]',
                '[role="button"]:has-text("Submissão de Laudos")',
                'xpath=//button[contains(@class, "btn") and contains(text(), "Submissão")]',
                'xpath=//div[contains(text(), "Submissão de Laudos")]',
                'text="Submissão de Laudos"'
            ]
            
            submissao_btn = None
            for i, selector in enumerate(submissao_selectors):
                try:
                    self.log_status(f"🔍 Tentativa {i+1} - Procurando 'Submissão de Laudos': {selector[:50]}...")
                    submissao_btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if submissao_btn:
                        self.log_status(f"✅ Botão 'Submissão de Laudos' encontrado na tentativa {i+1}")
                        break
                except Exception as e:
                    self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                    continue
            
            if not submissao_btn:
                # CORREÇÃO: Tentar uma última vez com recarregamento da página
                self.log_status("🔄 Última tentativa - recarregando página...")
                await self.page.reload()
                await asyncio.sleep(2)
                
                try:
                    submissao_btn = await self.page.wait_for_selector('button:has-text("Submissão de Laudos")', timeout=10000)
                    self.log_status("✅ Botão encontrado após recarregar página!")
                except:
                    # Debug: Mostrar todos os botões disponíveis
                    try:
                        buttons = await self.page.query_selector_all('button')
                        self.log_status(f"🔍 Debug: Encontrados {len(buttons)} botões na página")
                        for idx, btn in enumerate(buttons[:5]):  # Mostrar apenas os primeiros 5
                            text = await btn.text_content()
                            self.log_status(f"   Botão {idx+1}: '{text[:30]}'")
                    except:
                        pass
                    raise Exception("Botão 'Submissão de Laudos' não encontrado mesmo após recarregar")
            
            # Clicar em "Submissão de Laudos"
            await submissao_btn.click()
            await asyncio.sleep(2)  # Aguardar menu expandir
            
            # Múltiplas estratégias para encontrar "Upload de Laudos"
            self.log_status("📤 Clicando em 'Upload de Laudos'...")
            upload_selectors = [
                'text="Upload de Laudos"',
                'xpath=//a[contains(text(), "Upload de Laudos")]',
                'xpath=//*[contains(text(), "Upload de Laudos")]',
                'a:has-text("Upload de Laudos")',
                '[role="menuitem"]:has-text("Upload de Laudos")'
            ]
            
            upload_link = None
            for i, selector in enumerate(upload_selectors):
                try:
                    self.log_status(f"🔍 Tentativa {i+1} - Procurando 'Upload de Laudos': {selector[:50]}...")
                    upload_link = await self.page.wait_for_selector(selector, timeout=5000)
                    if upload_link:
                        self.log_status(f"✅ Link 'Upload de Laudos' encontrado na tentativa {i+1}")
                        break
                except Exception as e:
                    self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                    continue
            
            if not upload_link:
                raise Exception("Link 'Upload de Laudos' não encontrado com nenhum seletor")
            
            await upload_link.click()
            await asyncio.sleep(2)
            
            # Validar se chegamos na página correta
            try:
                await self.page.wait_for_selector('text="Upload de Laudos"', timeout=5000)
                self.log_status("✅ Página de upload carregada!", "success")
                return True
            except:
                self.log_status("⚠️ Não foi possível confirmar se a página de upload carregou", "warning")
                return True  # Assumir que funcionou para continuar
            
        except Exception as e:
            self.log_status(f"❌ Erro ao navegar para upload: {str(e)}", "error")
            
            # CORREÇÃO: Tentar diagnóstico da página atual e recuperação
            try:
                current_url = self.page.url
                page_title = await self.page.title()
                self.log_status(f"🔍 Diagnóstico - URL atual: {current_url}")
                self.log_status(f"🔍 Diagnóstico - Título da página: {page_title}")
                
                # Tentar recuperação se estivermos em uma página inesperada
                if "assinatura" in current_url.lower() or "finalizado" in current_url.lower():
                    self.log_status("🔄 Detectada página de finalização, tentando voltar ao início...")
                    await self.page.goto("https://fenixflorestal.suzanonet.com.br/")
                    await asyncio.sleep(2)
                    return await self.navegar_para_upload()  # Tentar novamente recursivamente
                    
            except Exception as diag_error:
                self.log_status(f"⚠️ Erro no diagnóstico: {str(diag_error)}", "warning")
                
            return False
    
    async def preencher_informacoes_basicas(self, nucleo, ups_nucleo):
        """Preenche as informações básicas do formulário"""
        try:
            self.log_status("📝 Preenchendo informações básicas...")
            
            data_atual = datetime.now().strftime("%d/%m/%Y")
            
            # CORREÇÃO: Pegar UNF diretamente da planilha (coluna 19)
            # Usar a primeira linha do ups_nucleo para pegar a UNF (todas as UPs do mesmo núcleo têm a mesma UNF)
            unf = None
            
            if not ups_nucleo.empty:
                # Tentar primeiro por nome de coluna 'UNF'
                if 'UNF' in ups_nucleo.columns:
                    unf = str(ups_nucleo.iloc[0]['UNF']).strip()
                    self.log_status(f"✅ UNF obtida da planilha pela coluna 'UNF': '{unf}'", "success")
                # Se não tiver coluna 'UNF', tentar pela posição (coluna 19 = índice 18)
                elif len(ups_nucleo.columns) > 18:
                    nome_coluna_19 = ups_nucleo.columns[18]  # Coluna 19 (índice 18)
                    unf = str(ups_nucleo.iloc[0, 18]).strip()  # Usar índice direto
                    self.log_status(f"✅ UNF obtida da planilha pela posição (coluna 19 - '{nome_coluna_19}'): '{unf}'", "success")
            
            # Se não conseguiu obter da planilha, usar fallback
            if not unf or unf in ['nan', 'NaN', '']:
                unf = detectar_unf_por_nucleo(nucleo) 
                self.log_status(f"⚠️ UNF não encontrada na planilha, usando fallback: '{unf}'", "warning")
            
            # Debug: Mostrar informações de debug
            self.log_status(f"🔍 Debug UNF - Núcleo: '{nucleo}' → UNF: '{unf}'")
            if hasattr(ups_nucleo, 'columns'):
                if len(ups_nucleo.columns) > 18:
                    nome_coluna_19 = ups_nucleo.columns[18]
                    valor_coluna_19 = ups_nucleo.iloc[0, 18] if not ups_nucleo.empty else "N/A"
                    self.log_status(f"📋 Coluna 19 ('{nome_coluna_19}'): {valor_coluna_19}")
                else:
                    self.log_status(f"⚠️ Planilha não tem coluna 19 (só tem {len(ups_nucleo.columns)} colunas)", "warning")
                
                self.log_status(f"📋 Todas as colunas disponíveis: {list(ups_nucleo.columns)}")
            else:
                self.log_status(f"⚠️ ups_nucleo não é um DataFrame válido", "warning")
            
            # Campo Solicitante (preencher com "Geocat")
            self.log_status("✏️ Preenchendo Solicitante: Geocat")
            try:
                solicitante_input = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[1]/div[1]/div/div/div[1]/div/div/input', timeout=5000)
                await solicitante_input.fill("Geocat")
            except:
                self.log_status("⚠️ Campo Solicitante não encontrado ou já preenchido", "warning")
            
            # Campo Data de Visita Campo - usando xpath mais específico
            self.log_status(f"✏️ Preenchendo Data de Visita: {data_atual}")
            try:
                # Tentar primeiro por placeholder
                visita_campo = await self.page.wait_for_selector('input[placeholder="Data da visita de campo"]', timeout=5000)
                await visita_campo.fill(data_atual)
            except:
                # Se falhar, usar xpath
                visita_campo = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[1]/div[1]/div/div/div[2]/div[2]/div/div/div/input', timeout=5000)
                await visita_campo.fill(data_atual)
            
            # Dropdown UNF - logo após Visita Campo
            self.log_status(f"✏️ Selecionando UNF: {unf}")
            await self.selecionar_unf(unf)
            
            # Dropdown Urgência (sempre "Média") - xpath correto
            self.log_status("✏️ Selecionando Urgência: Média")
            try:
                urgencia_dropdown = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[1]/div[1]/div/div/div[6]/div[1]/div/div/div', timeout=5000)
                await urgencia_dropdown.click()
                await asyncio.sleep(1)
                media_option = await self.page.wait_for_selector('text="Média"', timeout=3000)
                await media_option.click()
            except:
                self.log_status("⚠️ Campo Urgência não encontrado, continuando...", "warning")
            
            # Dropdown Tipo Ocorrência (sempre "Sinistro") - usando xpath específico
            self.log_status("✏️ Selecionando Tipo Ocorrência: Sinistro")
            try:
                # Tentar clicar no dropdown usando xpath
                tipo_dropdown = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[1]/div[1]/div/div/div[6]/div[2]/div/div/div', timeout=5000)
                await tipo_dropdown.click()
                await asyncio.sleep(1)
                
                # Selecionar "Sinistro" do dropdown
                sinistro_option = await self.page.wait_for_selector('text="Sinistro"', timeout=3000)
                await sinistro_option.click()
                await asyncio.sleep(1)
            except Exception as e:
                self.log_status(f"⚠️ Erro ao selecionar Tipo Ocorrência: {str(e)}", "warning")
            
            self.log_status("✅ Informações básicas preenchidas!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao preencher informações básicas: {str(e)}", "error")
            return False

    async def selecionar_unf(self, unf):
        """Seleciona UNF no dropdown usando múltiplas estratégias"""
        try:
            self.log_status(f"🔍 Iniciando seleção UNF: {unf}")
            
            # Aguardar um pouco para garantir que a página carregou
            await asyncio.sleep(1)
            
            # Múltiplos seletores baseados no DOM fornecido
            seletores_dropdown = [
                # Baseado na estrutura específica do react-select para UNF
                'xpath=//span[contains(text(), "UNF")]/following::div[contains(@class, "css-1ek14t9-control")][1]',
                'xpath=//label[contains(text(), "UNF")]/following::div[contains(@class, "css-1ek14t9-control")][1]',
                # Baseado na posição no formulário (após campo de Data de Visita)
                'xpath=//input[@placeholder="Data da visita de campo"]/ancestor::div[contains(@class, "flex")]//following::div[contains(@class, "css-1ek14t9-control")][1]',
                # Seletor específico para campo UNF no formulário de informações básicas
                'xpath=//form//div[contains(@class, "flex")]//span[text()="UNF"]/following::div[contains(@class, "control")][1]',
                # Procurar por react-select com placeholder "- Selecione -" próximo ao texto UNF
                'xpath=//span[contains(text(), "UNF")]/following::div[.//div[contains(text(), "- Selecione -")]][1]',
                # Baseado na estrutura completa do react-select
                'div[class*="css-1ek14t9-control"]:has(input[id*="react-select"]):has(div[class*="placeholder"])',
                # Fallback mais genérico
                'xpath=//div[contains(@class, "control") and .//div[contains(text(), "- Selecione -")]]'
            ]
            
            dropdown_element = None
            seletor_usado = None
            
            for i, seletor in enumerate(seletores_dropdown):
                try:
                    self.log_status(f"🔍 Tentativa {i+1}: {seletor[:80]}...")
                    dropdown_element = await self.page.wait_for_selector(seletor, timeout=3000)
                    if dropdown_element:
                        # Verificar se é visível
                        is_visible = await dropdown_element.is_visible()
                        if is_visible:
                            seletor_usado = seletor
                            self.log_status(f"✅ UNF dropdown encontrado com seletor {i+1}")
                            break
                        else:
                            self.log_status(f"⚠️ Dropdown encontrado mas não visível (tentativa {i+1})")
                except Exception as e:
                    self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                    continue
            
            if not dropdown_element:
                self.log_status("❌ Dropdown UNF não encontrado com nenhum seletor", "error")
                return False
            
            # Scroll para garantir que o elemento está visível
            await dropdown_element.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            # Debug: Mostrar informações do elemento encontrado
            try:
                element_info = await dropdown_element.evaluate("""
                    element => {
                        return {
                            tagName: element.tagName,
                            className: element.className,
                            id: element.id,
                            innerHTML: element.innerHTML.substring(0, 200)
                        }
                    }
                """)
                self.log_status(f"🔍 Debug elemento: {element_info['tagName']}, classes: {element_info['className'][:50]}")
            except:
                pass
            
            # Clicar no dropdown para abrir
            self.log_status("🖱️ Clicando no dropdown UNF...")
            await dropdown_element.click()
            await asyncio.sleep(1.5)  # Aguardo maior para dropdown abrir
            
            # Verificar se o dropdown abriu
            try:
                menu_aberto = await self.page.wait_for_selector('div[class*="menu"]', timeout=3000)
                if menu_aberto:
                    self.log_status("✅ Menu UNF aberto com sucesso")
                else:
                    self.log_status("⚠️ Menu pode não ter aberto")
            except:
                self.log_status("⚠️ Timeout aguardando menu abrir, continuando...")
            
            # Procurar pela opção do UNF com múltiplas estratégias
            opcoes_seletores = [
                # Opção mais específica - dentro do menu ativo
                f'xpath=//div[contains(@class, "menu")]//div[contains(@class, "option") and text()="{unf}"]',
                # Alternativas para react-select
                f'xpath=//div[@role="option" and text()="{unf}"]',
                f'xpath=//div[contains(@class, "option") and normalize-space(text())="{unf}"]',
                # Busca mais genérica
                f'text="{unf}"',
                # Fallback - primeira opção que contém o texto
                f'xpath=//div[contains(@class, "option") and contains(text(), "{unf}")]'
            ]
            
            opcao_encontrada = False
            for i, opcao_seletor in enumerate(opcoes_seletores):
                try:
                    self.log_status(f"🔍 Procurando opção '{unf}' (tentativa {i+1}): {opcao_seletor[:60]}...")
                    opcao = await self.page.wait_for_selector(opcao_seletor, timeout=3000)
                    if opcao:
                        is_visible = await opcao.is_visible()
                        if is_visible:
                            self.log_status(f"🎯 Clicando na opção '{unf}'...")
                            await opcao.click()
                            opcao_encontrada = True
                            self.log_status(f"✅ UNF '{unf}' selecionado com sucesso!")
                            break
                        else:
                            self.log_status(f"⚠️ Opção encontrada mas não visível (tentativa {i+1})")
                except Exception as e:
                    self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                    continue
            
            if not opcao_encontrada:
                # Debug: Listar todas as opções disponíveis
                try:
                    self.log_status("🔍 Debug: Listando opções disponíveis no dropdown...")
                    opcoes_disponiveis = await self.page.query_selector_all('xpath=//div[contains(@class, "option")]')
                    if opcoes_disponiveis:
                        for idx, opcao in enumerate(opcoes_disponiveis[:5]):  # Máximo 5 para não poluir
                            texto = await opcao.inner_text()
                            self.log_status(f"   Opção {idx+1}: '{texto}'")
                    else:
                        self.log_status("⚠️ Nenhuma opção encontrada no dropdown")
                except:
                    pass
                
                self.log_status(f"❌ Opção '{unf}' não encontrada no dropdown UNF", "error")
                return False
            
            # Aguardar seleção ser aplicada
            await asyncio.sleep(1)
            
            # Validar se a seleção foi aplicada
            try:
                # Procurar pelo valor selecionado
                valor_selecionado = await self.page.query_selector('xpath=//div[contains(@class, "singleValue")]')
                if valor_selecionado:
                    texto_selecionado = await valor_selecionado.inner_text()
                    if texto_selecionado.strip() == unf:
                        self.log_status(f"✅ Validação OK: UNF '{unf}' confirmado no campo", "success")
                        return True
                    else:
                        self.log_status(f"⚠️ Validação: Campo mostra '{texto_selecionado}', esperado '{unf}'", "warning")
                        return False
                else:
                    self.log_status("⚠️ Não foi possível validar a seleção", "warning")
                    return True  # Assumir sucesso se não conseguir validar
            except Exception as e:
                self.log_status(f"⚠️ Erro na validação: {str(e)}", "warning")
                return True  # Assumir sucesso se não conseguir validar
                
        except Exception as e:
            self.log_status(f"❌ Erro ao selecionar UNF: {str(e)}", "error")
            return False
    
    async def preencher_campos_texto(self, nome, tipo_organizacao="nucleo"):
        """Preenche os campos de texto do formulário"""
        try:
            self.log_status("📄 Preenchendo campos de texto...")
            
            # Escolher o texto correto baseado no tipo de organização
            if tipo_organizacao == "propriedade":
                texto_objetivo = TEXTOS_PADRAO['objetivo_propriedade'].format(nome=nome)
                self.log_status(f"🏗️ Usando texto para Fazenda: {nome}")
            else:
                texto_objetivo = TEXTOS_PADRAO['objetivo_nucleo'].format(nome=nome)
                self.log_status(f"🏢 Usando texto para Núcleo: {nome}")
            
            # Lista de campos e seus textos
            campos = [
                ("Objetivo", texto_objetivo, 'textarea[name="objetivo"]'),
                ("Diagnóstico", TEXTOS_PADRAO['diagnostico'], 'textarea[name="diagnostico"]'),
                ("Lições Aprendidas", TEXTOS_PADRAO['licoes_aprendidas'], 'textarea[name="licoesAprendidas"]'),
                ("Considerações Finais", TEXTOS_PADRAO['consideracoes_finais'], 'textarea[name="consideracoesFinais"]')
            ]
            
            for campo_nome, texto, selector in campos:
                self.log_status(f"📝 Preenchendo {campo_nome}...")
                try:
                    campo = await self.page.wait_for_selector(selector, timeout=5000)
                    await campo.fill(texto)
                    await asyncio.sleep(1)
                except Exception as e:
                    self.log_status(f"⚠️ Erro ao preencher {campo_nome}: {str(e)}", "warning")
            
            self.log_status("✅ Campos de texto preenchidos!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro geral ao preencher campos de texto: {str(e)}", "error")
            return False
    
    async def limpar_campo_up_avaliada(self, up_index):
        """Limpa o campo UP avaliada após falha para preparar próxima tentativa"""
        try:
            self.log_status(f"🧹 Limpando campo UP avaliada da linha {up_index + 1}")
            
            # Primeiro tentar fechar qualquer dropdown aberto
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
            
            # NOVA ABORDAGEM: Múltiplos seletores baseados na estrutura HTML real
            selectors_up_limpar = [
                f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "control")]',
                f'xpath=(//*[contains(text(), "UP avaliada:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
            ]
            
            # Tentar encontrar e clicar no botão de limpar (X)
            for selector_base in selectors_up_limpar:
                try:
                    # Primeiro verificar se o campo tem conteúdo
                    value_selector = selector_base.replace('control', 'singleValue')
                    existing_value = await self.page.query_selector(value_selector)
                    
                    if existing_value:
                        # Campo tem conteúdo, procurar botão clear
                        clear_selectors = [
                            selector_base.replace('control', 'clearIndicator'),
                            selector_base + '//div[contains(@aria-label, "clear")]',
                            selector_base + '//*[contains(@class, "clear")]'
                        ]
                        
                        for clear_selector in clear_selectors:
                            try:
                                clear_button = await self.page.wait_for_selector(clear_selector, timeout=1000)
                                await clear_button.click()
                                await asyncio.sleep(0.5)
                                self.log_status(f"✅ Campo UP avaliada limpo")
                                return
                            except:
                                continue
                except:
                    continue
            
            # Se não conseguiu limpar com o botão X, tentar método alternativo
            for selector in selectors_up_limpar:
                try:
                    up_dropdown = await self.page.wait_for_selector(selector, timeout=2000)
                    await up_dropdown.click()
                    await asyncio.sleep(0.5)
                    
                    # Selecionar tudo e deletar
                    await self.page.keyboard.press('Control+a')
                    await asyncio.sleep(0.2)
                    await self.page.keyboard.press('Delete')
                    await asyncio.sleep(0.5)
                    
                    # Fechar dropdown
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                    
                    self.log_status(f"✅ Campo UP avaliada limpo (método alternativo)")
                    return
                    
                except Exception as alt_error:
                    continue
            
            # Se chegou aqui, nenhum método funcionou
            self.log_status(f"⚠️ Não foi possível limpar campo UP avaliada com nenhum método", "warning")
            # Pelo menos tentar fechar dropdown
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
                
        except Exception as e:
            self.log_status(f"⚠️ Erro ao limpar campo UP avaliada: {str(e)}", "warning")
            # Garantir que dropdown seja fechado
            try:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
            except:
                pass

    async def processar_up(self, up_data, up_index=0):
        """Processa uma UP individual na Matriz de Decisão"""
        try:
            self.log_status(f"📍 Processando UP: {up_data['UP']} na LINHA {up_index + 1} da matriz")
            self.log_status(f"🔢 Índice técnico: {up_index} (linha {up_index + 1} visualmente)")
            
            # 1. Selecionar UP avaliada (dropdown com digitação)
            try:
                # Primeiro, garantir que qualquer dropdown aberto seja fechado
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
                
                # VALIDAÇÃO PRÉVIA: Verificar se a linha já tem dados preenchidos
                try:
                    existing_up_selectors = [
                        f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]',
                        f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]'
                    ]
                    
                    for check_selector in existing_up_selectors:
                        try:
                            existing_up_element = await self.page.query_selector(check_selector)
                            if existing_up_element:
                                existing_up_text = await existing_up_element.inner_text()
                                if existing_up_text and existing_up_text.strip():
                                    self.log_status(f"⚠️ ATENÇÃO: Linha {up_index + 1} já contém UP '{existing_up_text}'!", "warning")
                                    self.log_status(f"🚨 Possível sobreposição detectada - essa linha deveria estar vazia", "warning")
                                    break
                        except:
                            continue
                except:
                    pass
                
                # NOVA ABORDAGEM: Usar estrutura HTML real baseada na posição das linhas
                # Cada linha da matriz está dentro de um div com classe "flex flex-col lg:flex-row"
                # A primeira linha não tem input name com índice, as subsequentes têm sinistros[1], sinistros[2], etc.
                selectors_up = [
                    # Seletor baseado na estrutura real: usar a N-ésima linha da matriz
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    # Alternativo usando a posição da linha no fieldset
                    f'xpath=(//fieldset/div/div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "control")]',
                    # Usando o padrão do name do input "idade" como referência (sinistros[0], sinistros[1], etc.)
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "control")]',
                    # Seletor baseado na ordem absoluta dos campos UP avaliada
                    f'xpath=(//*[contains(text(), "UP avaliada:")]/following::div[contains(@class, "control")])[{up_index + 1}]',
                    # Fallback: se for a primeira linha (índice 0), usar o primeiro campo disponível vazio
                    'xpath=//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "control") and not(.//div[contains(@class, "singleValue")])]' if up_index == 0 else f'xpath=(//*[contains(text(), "UP avaliada:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
                ]
                
                up_dropdown = None
                working_selector = None
                
                for i, selector in enumerate(selectors_up):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1}: {selector[:80]}...")
                        up_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if up_dropdown:
                            working_selector = selector
                            self.log_status(f"✅ Seletor funcionou na tentativa {i+1}")
                            break
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:60]}...")
                        continue
                
                if not up_dropdown:
                    raise Exception("Nenhum seletor para 'UP avaliada' funcionou. Verifique se a página carregou corretamente.")
                
                # Limpar campo antes de começar (caso tenha conteúdo anterior)
                try:
                    # NOVA ABORDAGEM: Verificar se o campo já tem conteúdo usando estrutura HTML real
                    existing_value_selectors = [
                        f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]',
                        f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]',
                        f'xpath=(//*[contains(text(), "UP avaliada:")]/following::div[contains(@class, "singleValue")])[{up_index + 1}]'
                    ]
                    
                    existing_value = None
                    for val_selector in existing_value_selectors:
                        try:
                            existing_value = await self.page.query_selector(val_selector)
                            if existing_value:
                                break
                        except:
                            continue
                    
                    if existing_value:
                        # Campo tem conteúdo, precisa limpar
                        clear_selectors = [
                            f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "indicatorSeparator")]/../div[contains(@class, "IndicatorsContainer")]//div[contains(@aria-label, "clear")]',
                            f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@aria-label, "clear")]'
                        ]
                        
                        cleared = False
                        for clear_selector in clear_selectors:
                            try:
                                clear_button = await self.page.wait_for_selector(clear_selector, timeout=2000)
                                await clear_button.click()
                                await asyncio.sleep(1)
                                self.log_status(f"🧹 Campo UP avaliada linha {up_index + 1} limpo")
                                cleared = True
                                break
                            except:
                                continue
                        
                        if not cleared:
                            # Se não conseguir limpar, pelo menos registrar
                            self.log_status(f"⚠️ Campo UP avaliada linha {up_index + 1} tem conteúdo mas não foi possível limpar", "warning")
                except:
                    pass
                
                # Clicar no dropdown para abrir
                await up_dropdown.click()
                await asyncio.sleep(1)
                
                # NOVA ABORDAGEM: Digitar o valor da UP para filtrar as opções
                up_value = str(up_data["UP"])
                self.log_status(f"📝 Digitando UP: {up_value}")
                
                # Digitar o valor da UP no campo de busca do dropdown
                await self.page.keyboard.type(up_value)
                await asyncio.sleep(2)  # Aguardar o filtro funcionar
                
                # Tentar selecionar o primeiro item que aparecer
                try:
                    # Aguardar opções aparecerem após digitação
                    await asyncio.sleep(1)
                    
                    # PRIMEIRO: Verificar se existe "Nenhum Resultado"
                    nenhum_resultado_selectors = [
                        '//div[contains(text(), "Nenhum resultado")]',
                        '//div[contains(text(), "Nenhum Resultado")]',
                        '//div[contains(text(), "No results")]',
                        '//div[contains(@class, "option") and contains(text(), "Nenhum")]'
                    ]
                    
                    # Verificar se apareceu "Nenhum Resultado"
                    nenhum_resultado_encontrado = False
                    for no_result_selector in nenhum_resultado_selectors:
                        try:
                            no_result_element = await self.page.wait_for_selector(no_result_selector, timeout=1000)
                            if no_result_element:
                                result_text = await no_result_element.inner_text()
                                self.log_status(f"❌ UP não encontrada: '{result_text}'", "warning")
                                nenhum_resultado_encontrado = True
                                break
                        except:
                            continue
                    
                    if nenhum_resultado_encontrado:
                        self.log_status(f"🚫 UP '{up_value}' não existe no sistema - pulando para próxima", "warning")
                        # Pressionar Escape para fechar dropdown
                        await self.page.keyboard.press('Escape')
                        await asyncio.sleep(1)
                        
                        # Limpar o campo para reutilizar na próxima UP
                        await self.limpar_campo_up_avaliada(up_index)
                        return False
                    
                    # Múltiplas tentativas de seleção com diferentes seletores
                    option_selectors = [
                        '//div[contains(@class, "css-") and contains(@class, "option")][1]',
                        '//div[@role="option"][1]',
                        '//div[contains(@class, "css-1n7v3ny-option")][1]',
                        '//div[contains(@class, "option")][1]'
                    ]
                    
                    option_selected = False
                    for selector in option_selectors:
                        try:
                            first_option = await self.page.wait_for_selector(selector, timeout=2000)
                            if first_option:
                                option_text = await first_option.inner_text()
                                
                                # Verificar se não é mensagem de "Nenhum resultado"
                                if "nenhum" in option_text.lower() or "no result" in option_text.lower():
                                    self.log_status(f"🚫 UP '{up_value}' não encontrada - mensagem: '{option_text}'", "warning")
                                    await self.page.keyboard.press('Escape')
                                    await asyncio.sleep(1)
                                    await self.limpar_campo_up_avaliada(up_index)
                                    return False
                                
                                self.log_status(f"🎯 Tentando selecionar opção: '{option_text}'")
                                await first_option.click()
                                self.log_status(f"✅ Opção selecionada: '{option_text}'")
                                option_selected = True
                                break
                        except:
                            continue
                    
                    if not option_selected:
                        self.log_status(f"⚠️ Nenhuma opção encontrada após digitar '{up_value}'", "warning")
                        # Tentar pressionar Enter como fallback
                        await self.page.keyboard.press('Enter')
                        await asyncio.sleep(1)
                    
                    await asyncio.sleep(2)  # Aguardar o campo ser preenchido
                    
                except Exception as selection_error:
                    self.log_status(f"⚠️ Erro ao selecionar opções: {str(selection_error)}", "warning")
                    # Tentar pressionar Escape para fechar o dropdown
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(1)
                
                # VALIDAÇÃO CRÍTICA: Verificar se o campo foi realmente preenchido
                try:
                    # NOVA ABORDAGEM: Múltiplos seletores baseados na estrutura HTML real
                    validation_selectors = [
                        f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]',
                        f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]',
                        f'xpath=(//*[contains(text(), "UP avaliada:")]/following::div[contains(@class, "singleValue")])[{up_index + 1}]'
                    ]
                    
                    # Tentar localizar o campo de valor com timeout menor
                    field_found = False
                    field_text = ""
                    
                    for validation_selector in validation_selectors:
                        try:
                            self.log_status(f"🔍 Validando com seletor: {validation_selector}")
                            up_field_value = await self.page.wait_for_selector(validation_selector, timeout=2000)
                            field_text = await up_field_value.inner_text()
                            field_found = True
                            self.log_status(f"✅ Seletor de validação funcionou")
                            break
                        except Exception as val_error:
                            self.log_status(f"⚠️ Seletor de validação falhou: {str(val_error)}")
                            continue
                    
                    if not field_found:
                        # Se nenhum seletor encontrou o campo, significa que não foi preenchido
                        self.log_status(f"❌ Campo UP avaliada não preenchido após digitação", "error")
                        self.log_status(f"⚠️ UP '{up_data['UP']}' não encontrada no sistema", "warning")
                        self.log_status(f"💡 Verifique se a UP está cadastrada no Fênix", "info")
                        self.log_status(f"🚫 CANCELANDO processamento da UP {up_data['UP']}", "error")
                        
                        # IMPORTANTE: Limpar o campo para próxima UP
                        await self.limpar_campo_up_avaliada(up_index)
                        
                        return False
                    
                    if not field_text or field_text.strip() == "":
                        self.log_status(f"❌ Campo 'UP avaliada' vazio - UP não cadastrada", "error")
                        self.log_status(f"⚠️ UP '{up_data['UP']}' não existe no sistema Fênix", "warning")
                        self.log_status(f"🚫 CANCELANDO processamento da UP {up_data['UP']}", "error")
                        
                        # IMPORTANTE: Limpar o campo para próxima UP
                        await self.limpar_campo_up_avaliada(up_index)
                        
                        return False
                    else:
                        self.log_status(f"✅ Validação OK: Campo preenchido com '{field_text}'", "success")
                        
                except Exception as validation_error:
                    self.log_status(f"❌ ERRO na validação do campo UP: {str(validation_error)}", "error")
                    self.log_status(f"⚠️ Campo UP avaliada pode não ter sido preenchido", "warning")
                    self.log_status(f"🚫 CANCELANDO processamento da UP {up_data['UP']} por segurança", "error")
                    
                    # IMPORTANTE: Limpar o campo para próxima UP
                    await self.limpar_campo_up_avaliada(up_index)
                    
                    return False
                    
            except Exception as e:
                self.log_status(f"❌ Erro ao processar UP avaliada: {str(e)}", "error")
                self.log_status(f"🚫 CANCELANDO processamento da UP {up_data['UP']}", "error")
                
                # IMPORTANTE: Limpar o campo para próxima UP
                await self.limpar_campo_up_avaliada(up_index)
                
                return False
            
            # 2. Selecionar Tipo Dano
            try:
                # NOVA ABORDAGEM: Múltiplos seletores baseados na estrutura HTML real
                tipo_dano_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "control")]',
                    f'xpath=(//*[contains(text(), "Tipo Dano:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
                ]
                
                tipo_dano_dropdown = None
                for i, selector in enumerate(tipo_dano_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} Tipo Dano: {selector[:60]}...")
                        tipo_dano_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if tipo_dano_dropdown:
                            self.log_status(f"✅ Seletor Tipo Dano funcionou na tentativa {i+1}")
                            break
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                        continue
                
                if not tipo_dano_dropdown:
                    raise Exception("Nenhum seletor para 'Tipo Dano' funcionou")
                
                # CORREÇÃO CRÍTICA: Fechar menus anteriores antes de abrir novo
                try:
                    # Clicar em área neutra para fechar dropdowns abertos
                    await self.page.click('body', position={'x': 10, 'y': 10})
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                await tipo_dano_dropdown.click()
                await asyncio.sleep(0.3)  # Reduzido de 1s para 0.3s
                
                # DIAGNÓSTICO: Verificar quantos menus estão abertos
                try:
                    all_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu")]')
                    active_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu") and @aria-hidden="false"]')
                    self.log_status(f"🔍 DIAGNÓSTICO: {len(all_menus)} menus total, {len(active_menus)} menus ativos")
                except:
                    pass
                
                # Verificar se o dropdown abriu corretamente
                try:
                    await self.page.wait_for_selector('xpath=//div[contains(@class, "menu")]', timeout=2000)
                    self.log_status(f"✅ Dropdown Tipo Dano aberto com sucesso")
                except:
                    self.log_status(f"⚠️ Dropdown Tipo Dano pode não ter aberto, tentando novamente...")
                    await tipo_dano_dropdown.click()
                    await asyncio.sleep(1)
                
                # Mapear Ocorrência Predominante para Tipo Dano do sistema
                dano_mapping = {
                    'DEFICIT HIDRICO': 'D. Hídrico',
                    'INCENDIO': 'Incêndio', 
                    'VENDAVAL': 'Vendaval'
                }
                
                # Usar a chave correta que foi criada no up_data
                ocorrencia_excel = str(up_data['Tipo_Dano']).upper().strip()
                tipo_dano = dano_mapping.get(ocorrencia_excel, 'Incêndio')  # Fallback para Incêndio
                
                self.log_status(f"📋 Ocorrência Excel: '{up_data['Tipo_Dano']}' → Tipo Dano: '{tipo_dano}'")
                
                # Tentar múltiplos seletores para encontrar a opção do Tipo Dano
                # CORREÇÃO CRÍTICA: Garantir que estamos selecionando a opção do dropdown correto
                
                # Aguardar um pouco para garantir que o dropdown está aberto
                await asyncio.sleep(0.2)  # Reduzido de 1s para 0.2s
                
                # Seletores mais específicos que garantem o contexto da UP atual
                tipo_dano_option_selectors = [
                    # Opção 1: Buscar dentro do menu ativo (mais recente)
                    f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{tipo_dano}"]',
                    # Opção 2: Buscar dentro do último menu aberto
                    f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{tipo_dano}"]',
                    # Opção 3: Buscar opção visível e não desabilitada
                    f'xpath=//div[contains(@class, "option") and text()="{tipo_dano}" and not(contains(@class, "disabled"))]',
                    # Opção 4: Seletor direto por texto (última opção)
                    f'text="{tipo_dano}"'
                ]
                
                option_found = False
                for i, option_selector in enumerate(tipo_dano_option_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} para opção '{tipo_dano}': {option_selector[:60]}...")
                        dano_option = await self.page.wait_for_selector(option_selector, timeout=3000)
                        
                        if dano_option:
                            # CORREÇÃO CRÍTICA: Verificar se o elemento está visível e clicável
                            is_visible = await dano_option.is_visible()
                            if is_visible:
                                # Scroll para o elemento se necessário
                                await dano_option.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                
                                # Obter texto da opção para validação
                                option_text = await dano_option.inner_text()
                                self.log_status(f"🎯 Clicando em opção Tipo Dano: '{option_text}'")
                                
                                # Clicar na opção
                                await dano_option.click()
                                await asyncio.sleep(1)
                                
                                self.log_status(f"✅ Tipo Dano selecionado: '{option_text}' (tentativa {i+1})")
                                option_found = True
                                break
                            else:
                                self.log_status(f"⚠️ Elemento encontrado mas não visível (tentativa {i+1})")
                        
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:60]}...")
                        continue
                
                if not option_found:
                    raise Exception(f"Não foi possível encontrar opção '{tipo_dano}' no dropdown")
                
                # CORREÇÃO: Aguardar seleção ser aplicada e validar
                await asyncio.sleep(0.5)  # Reduzido de 2s para 0.5s
                
                # VALIDAR se o Tipo Dano foi realmente selecionado
                validation_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "singleValue")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "singleValue")]',
                    f'xpath=(//*[contains(text(), "Tipo Dano:")]/following::div[contains(@class, "singleValue")])[{up_index + 1}]'
                ]
                
                validation_ok = False
                for val_selector in validation_selectors:
                    try:
                        selected_value_element = await self.page.wait_for_selector(val_selector, timeout=3000)
                        selected_text = await selected_value_element.inner_text()
                        if selected_text.strip() == tipo_dano:
                            self.log_status(f"✅ VALIDAÇÃO OK: Tipo Dano '{tipo_dano}' confirmado no campo")
                            validation_ok = True
                            break
                        else:
                            self.log_status(f"⚠️ VALIDAÇÃO: Campo mostra '{selected_text}', esperado '{tipo_dano}'", "warning")
                    except:
                        continue
                
                if not validation_ok:
                    self.log_status(f"❌ ERRO: Tipo Dano '{tipo_dano}' NÃO foi selecionado corretamente!", "error")
                    self.log_status(f"🔄 Tentativa de correção...", "warning")
                    
                    # Tentar novamente com aguardo maior
                    try:
                        await tipo_dano_dropdown.click()
                        await asyncio.sleep(1.5)  # Aguardo maior para dropdown abrir
                        
                        # Usar os mesmos seletores específicos
                        retry_selectors = [
                            f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{tipo_dano}"]',
                            f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{tipo_dano}"]',
                            f'xpath=//div[contains(@class, "option") and text()="{tipo_dano}" and not(contains(@class, "disabled"))]'
                        ]
                        
                        for selector in retry_selectors:
                            try:
                                dano_option = await self.page.wait_for_selector(selector, timeout=3000)
                                if await dano_option.is_visible():
                                    await dano_option.scroll_into_view_if_needed()
                                    await asyncio.sleep(0.5)
                                    await dano_option.click()
                                    await asyncio.sleep(3)  # Aguardo maior para confirmar seleção
                                    self.log_status(f"🔄 Segunda tentativa de seleção do Tipo Dano realizada")
                                    break
                            except:
                                continue
                    except Exception as retry_error:
                        self.log_status(f"❌ Falha na segunda tentativa: {str(retry_error)}", "error")
                        
                await asyncio.sleep(1)
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Tipo Dano: {str(e)}", "error")
            
            # 3. Selecionar Ocorrência na UP (primeiro item do dropdown)
            try:
                # NOVA ABORDAGEM: Seletor baseado na estrutura HTML real
                ocorrencia_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Ocorrência na UP:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Ocorrência na UP:")]/following::div[1]//div[contains(@class, "control")]',
                    f'xpath=(//*[contains(text(), "Ocorrência na UP:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
                ]
                
                ocorrencia_dropdown = None
                for i, selector in enumerate(ocorrencia_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} Ocorrência: {selector[:60]}...")
                        ocorrencia_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if ocorrencia_dropdown:
                            self.log_status(f"✅ Seletor Ocorrência funcionou na tentativa {i+1}")
                            break
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                        continue
                
                if not ocorrencia_dropdown:
                    raise Exception("Nenhum seletor para 'Ocorrência na UP' funcionou")
                
                # CORREÇÃO CRÍTICA: Fechar menus anteriores antes de abrir novo
                try:
                    # Clicar em área neutra para fechar dropdowns abertos
                    await self.page.click('body', position={'x': 10, 'y': 10})
                    await asyncio.sleep(0.5)
                except:
                    pass
                    
                await ocorrencia_dropdown.click()
                await asyncio.sleep(0.3)  # Reduzido de 1s para 0.3s
                
                # DIAGNÓSTICO: Verificar quantos menus estão abertos
                try:
                    all_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu")]')
                    active_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu") and @aria-hidden="false"]')
                    self.log_status(f"🔍 DIAGNÓSTICO Ocorrência: {len(all_menus)} menus total, {len(active_menus)} menus ativos")
                except:
                    pass
                
                # Múltiplos seletores para encontrar a primeira opção do dropdown
                # CORREÇÃO CRÍTICA: Garantir que estamos no dropdown correto
                await asyncio.sleep(0.2)  # Reduzido de 1s para 0.2s (Aguardar dropdown abrir completamente)
                
                option_selectors = [
                    # Opção 1: Buscar dentro do menu ativo (mais recente)
                    'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option")][1]',
                    # Opção 2: Buscar dentro do último menu aberto
                    'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option")][1]',
                    # Opção 3: Primeira opção visível e não desabilitada
                    'xpath=//div[contains(@class, "option") and not(contains(@class, "disabled"))][1]',
                    # Opção 4: Fallback - primeira opção do menuList
                    'xpath=//div[contains(@class, "menuList")]/div[contains(@class, "option")][1]'
                ]
                
                primeiro_item_encontrado = False
                for i, selector in enumerate(option_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} para Ocorrência: {selector[:50]}...")
                        primeiro_item = await self.page.wait_for_selector(selector, timeout=3000)
                        
                        if primeiro_item and await primeiro_item.is_visible():
                            option_text = await primeiro_item.inner_text()
                            
                            # Verificar se não é uma mensagem de erro
                            if "nenhum" not in option_text.lower() and "no result" not in option_text.lower():
                                self.log_status(f"🎯 Tentando selecionar primeira opção: '{option_text}'")
                                
                                # Scroll até o elemento se necessário
                                await primeiro_item.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                
                                await primeiro_item.click()
                                self.log_status(f"✅ Primeira ocorrência selecionada: '{option_text}'")
                                primeiro_item_encontrado = True
                                break
                            else:
                                self.log_status(f"⚠️ Opção inválida ignorada: '{option_text}'")
                        
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:60]}...")
                        continue
                
                if not primeiro_item_encontrado:
                    # Fallback: tentar pressionar Enter
                    self.log_status(f"⚠️ Usando fallback: pressionar Enter", "warning")
                    await self.page.keyboard.press('Enter')
                    
                await asyncio.sleep(0.3)  # Reduzido de 1s para 0.3s
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Ocorrência: {str(e)}", "error")
            
            # 4. Preencher Recomendação (%) com incidência
            try:
                # NOVA ABORDAGEM: Múltiplos seletores baseados na estrutura HTML real
                recomendacao_pct_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Recomendação(%)")]/following::div[1]//input',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Recomendação(%)")]/following::div[1]//input',
                    f'xpath=(//*[contains(text(), "Recomendação(%)")]/following::input)[{up_index + 1}]'
                ]
                
                recomendacao_input = None
                for i, selector in enumerate(recomendacao_pct_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} Recomendação %: {selector[:60]}...")
                        recomendacao_input = await self.page.wait_for_selector(selector, timeout=3000)
                        if recomendacao_input:
                            self.log_status(f"✅ Seletor Recomendação % funcionou na tentativa {i+1}")
                            break
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                        continue
                
                if not recomendacao_input:
                    raise Exception("Nenhum seletor para 'Recomendação %' funcionou")
                
                # CORREÇÃO: Formatar valor para campo input[type="number"]
                # Campos input[type="number"] precisam usar ponto (.) como separador decimal
                incidencia_valor = f"{up_data['Incidencia']:.2f}"
                self.log_status(f"📝 Preenchendo Recomendação % com: {incidencia_valor}%")
                
                # Limpar campo primeiro e usar múltiplas estratégias de preenchimento
                await recomendacao_input.click()
                await asyncio.sleep(0.2)  # Reduzido de 0.5s para 0.2s
                
                # Estratégia 1: Limpar com Ctrl+A e preencher
                await self.page.keyboard.press('Control+a')
                await asyncio.sleep(0.1)  # Reduzido de 0.2s para 0.1s
                await recomendacao_input.fill("")
                await asyncio.sleep(0.1)  # Reduzido de 0.2s para 0.1s
                await recomendacao_input.fill(incidencia_valor)
                await asyncio.sleep(0.2)  # Reduzido de 0.5s para 0.2s
                
                # Estratégia 2: Se não funcionou, tentar com type()
                field_check = await recomendacao_input.input_value()
                if not field_check or field_check.strip() == "":
                    self.log_status("⚠️ Fill() não funcionou, tentando type()...")
                    await recomendacao_input.click()
                    await self.page.keyboard.press('Control+a')
                    await asyncio.sleep(0.1)  # Reduzido de 0.2s para 0.1s
                    await recomendacao_input.type(incidencia_valor)
                    await asyncio.sleep(0.2)  # Reduzido de 0.5s para 0.2s
                # VALIDAÇÃO: Verificar se o valor foi preenchido
                try:
                    field_value = await recomendacao_input.input_value()
                    if field_value and field_value.strip():
                        # Converter valores para comparação (aceitar tanto . quanto , como separador)
                        field_normalized = field_value.replace(',', '.')
                        expected_normalized = incidencia_valor.replace(',', '.')
                        if abs(float(field_normalized) - float(expected_normalized)) < 0.01:
                            self.log_status(f"✅ Recomendação % CONFIRMADA: {field_value}%", "success")
                        else:
                            self.log_status(f"⚠️ Recomendação % valor divergente: esperado {incidencia_valor}%, obtido {field_value}%", "warning")
                    else:
                        # Estratégia 3: Última tentativa usando JavaScript direto no selector
                        self.log_status("⚠️ Campo vazio, tentando JavaScript...")
                        try:
                            # Usar o primeiro selector que funcionou para localizar o elemento via JavaScript
                            await self.page.evaluate(f'''
                                () => {{
                                    // Tentar encontrar o input pelo XPath ou CSS
                                    let input = null;
                                    
                                    // Tentar diferentes abordagens para encontrar o campo
                                    const inputs = document.querySelectorAll('input[type="number"]');
                                    for (let inp of inputs) {{
                                        const span = inp.closest('div').previousElementSibling;
                                        if (span && span.textContent.includes('Recomendação(%)')) {{
                                            input = inp;
                                            break;
                                        }}
                                    }}
                                    
                                    if (input) {{
                                        input.value = "{incidencia_valor}";
                                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        return true;
                                    }}
                                    return false;
                                }}
                            ''')
                            await asyncio.sleep(0.5)
                            
                            # Verificar novamente
                            final_check = await recomendacao_input.input_value()
                            if final_check:
                                self.log_status(f"✅ Recomendação % via JavaScript: {final_check}%", "success")
                            else:
                                self.log_status(f"❌ Falha total ao preencher Recomendação %", "error")
                                
                        except Exception as js_error:
                            self.log_status(f"⚠️ Erro no JavaScript: {str(js_error)}", "warning")
                            
                except Exception as val_error:
                    self.log_status(f"⚠️ Erro na validação de Recomendação %: {str(val_error)}", "warning")
            except Exception as e:
                self.log_status(f"❌ Erro ao preencher Recomendação %: {str(e)}", "error")
            
            # 5. Selecionar Severidade
            try:
                # NOVA ABORDAGEM: Múltiplos seletores baseados na estrutura HTML real
                severidade_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Severidade:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Severidade:")]/following::div[1]//div[contains(@class, "control")]',
                    f'xpath=(//*[contains(text(), "Severidade:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
                ]
                
                severidade_dropdown = None
                for i, selector in enumerate(severidade_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} Severidade: {selector[:60]}...")
                        severidade_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if severidade_dropdown:
                            self.log_status(f"✅ Seletor Severidade funcionou na tentativa {i+1}")
                            break
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                        continue
                
                if not severidade_dropdown:
                    raise Exception("Nenhum seletor para 'Severidade' funcionou")
                
                # CORREÇÃO CRÍTICA: Fechar menus anteriores antes de abrir novo
                try:
                    # Clicar em área neutra para fechar dropdowns abertos
                    await self.page.click('body', position={'x': 10, 'y': 10})
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                await severidade_dropdown.click()
                await asyncio.sleep(0.3)  # Reduzido de 1s para 0.3s
                
                # DIAGNÓSTICO: Verificar quantos menus estão abertos
                try:
                    all_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu")]')
                    active_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu") and @aria-hidden="false"]')
                    self.log_status(f"🔍 DIAGNÓSTICO Severidade: {len(all_menus)} menus total, {len(active_menus)} menus ativos")
                except:
                    pass
                
                # Verificar se o dropdown abriu corretamente
                try:
                    await self.page.wait_for_selector('xpath=//div[contains(@class, "menu")]', timeout=2000)
                    self.log_status(f"✅ Dropdown Severidade aberto com sucesso")
                except:
                    self.log_status(f"⚠️ Dropdown Severidade pode não ter aberto, tentando novamente...")
                    await severidade_dropdown.click()
                    await asyncio.sleep(0.3)  # Reduzido de 1s para 0.3s
                
                # Normalizar severidade - mapeamento para as opções EXATAS do sistema
                severidade_original = str(up_data.get('Severidade', '')).strip()
                severidade_mapping = {
                    'BAIXA': 'Baixa',
                    'BAIXO': 'Baixa', 
                    'LOW': 'Baixa',
                    'B': 'Baixa',
                    'MÉDIA': 'Média',
                    'MEDIA': 'Média',
                    'MEDIO': 'Média',
                    'MEDIUM': 'Média',
                    'M': 'Média',
                    'ALTA': 'Alta',
                    'ALTO': 'Alta',
                    'HIGH': 'Alta',
                    'A': 'Alta'
                }
                
                severidade_normalizada = severidade_original.upper()
                severidade_valor = severidade_mapping.get(severidade_normalizada, 'Baixa')
                
                self.log_status(f"Severidade original: '{severidade_original}' -> Mapeada: '{severidade_valor}'")
                
                # CORREÇÃO CRÍTICA: Seletores específicos para encontrar a opção no menu ativo
                # Aguardar um pouco para garantir que o dropdown está aberto
                await asyncio.sleep(0.2)  # Reduzido de 1s para 0.2s
                
                # Seletores mais específicos que garantem o contexto correto
                severidade_option_selectors = [
                    # Opção 1: Buscar dentro do menu ativo (mais recente)
                    f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{severidade_valor}"]',
                    # Opção 2: Buscar dentro do último menu aberto
                    f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{severidade_valor}"]',
                    # Opção 3: Buscar opção visível e não desabilitada
                    f'xpath=//div[contains(@class, "option") and text()="{severidade_valor}" and not(contains(@class, "disabled"))]',
                    # Opção 4: Seletor direto por texto (última opção)
                    f'text="{severidade_valor}"'
                ]
                
                option_found = False  
                for i, selector in enumerate(severidade_option_selectors):
                    try:
                        self.log_status(f"🔍 Procurando opção Severidade: '{severidade_valor}' (tentativa {i+1})")
                        
                        # Aguardar o elemento aparecer
                        severidade_option = await self.page.wait_for_selector(selector, timeout=3000)
                        
                        # CORREÇÃO: Verificar se o elemento está visível e clicável
                        if await severidade_option.is_visible():
                            # Scroll até o elemento se necessário
                            await severidade_option.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            
                            # Clicar na opção
                            await severidade_option.click()
                            self.log_status(f"✅ Severidade selecionada: {severidade_valor}")
                            option_found = True
                            break
                        else:
                            self.log_status(f"⚠️ Opção encontrada mas não visível (tentativa {i+1})")
                            
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                        continue
                
                if not option_found:
                    raise Exception(f"Não foi possível encontrar opção '{severidade_valor}' no dropdown")
                
                # CORREÇÃO: Aguardar seleção ser aplicada e validar
                await asyncio.sleep(0.5)  # Reduzido de 2s para 0.5s
                
                # VALIDAR se a Severidade foi realmente selecionada
                validation_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Severidade:")]/following::div[1]//div[contains(@class, "singleValue")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Severidade:")]/following::div[1]//div[contains(@class, "singleValue")]',
                    f'xpath=(//*[contains(text(), "Severidade:")]/following::div[contains(@class, "singleValue")])[{up_index + 1}]'
                ]
                
                validation_ok = False
                for val_selector in validation_selectors:
                    try:
                        selected_value_element = await self.page.wait_for_selector(val_selector, timeout=3000)
                        selected_text = await selected_value_element.inner_text()
                        if selected_text.strip() == severidade_valor:
                            self.log_status(f"✅ VALIDAÇÃO OK: Severidade '{severidade_valor}' confirmada no campo")
                            validation_ok = True
                            break
                        else:
                            self.log_status(f"⚠️ VALIDAÇÃO: Campo mostra '{selected_text}', esperado '{severidade_valor}'", "warning")
                    except:
                        continue
                
                if not validation_ok:
                    self.log_status(f"❌ ERRO: Severidade '{severidade_valor}' NÃO foi selecionada corretamente!", "error")
                    self.log_status(f"🔄 Tentativa de correção...", "warning")
                    
                    # Tentar novamente com aguardo maior
                    try:
                        await severidade_dropdown.click()
                        await asyncio.sleep(0.5)  # Reduzido de 1.5s para 0.5s (Aguardo maior para dropdown abrir)
                        
                        # Usar os mesmos seletores específicos
                        retry_selectors = [
                            f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{severidade_valor}"]',
                            f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{severidade_valor}"]',
                            f'xpath=//div[contains(@class, "option") and text()="{severidade_valor}" and not(contains(@class, "disabled"))]'
                        ]
                        
                        for selector in retry_selectors:
                            try:
                                severidade_option = await self.page.wait_for_selector(selector, timeout=3000)
                                if await severidade_option.is_visible():
                                    await severidade_option.scroll_into_view_if_needed()
                                    await asyncio.sleep(0.5)
                                    await severidade_option.click()
                                    await asyncio.sleep(3)  # Aguardo maior para confirmar seleção
                                    self.log_status(f"🔄 Segunda tentativa de seleção da Severidade realizada")
                                    break
                            except:
                                continue
                    except Exception as retry_error:
                        self.log_status(f"❌ Falha na segunda tentativa: {str(retry_error)}", "error")
                        
                await asyncio.sleep(0.2)  # Reduzido de 1s para 0.2s
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Severidade: {str(e)}", "error")
            
            # 6. Selecionar Recomendação (aplicar regra de negócio)
            try:
                # NOVA ABORDAGEM: Múltiplos seletores baseados na estrutura HTML real
                recomendacao_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Recomendaçao:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Recomendaçao:")]/following::div[1]//div[contains(@class, "control")]',
                    f'xpath=(//*[contains(text(), "Recomendaçao:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
                ]
                
                recomendacao_dropdown = None
                for i, selector in enumerate(recomendacao_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} Recomendação: {selector[:60]}...")
                        recomendacao_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if recomendacao_dropdown:
                            self.log_status(f"✅ Seletor Recomendação funcionou na tentativa {i+1}")
                            break
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:50]}...")
                        continue
                
                if not recomendacao_dropdown:
                    raise Exception("Nenhum seletor para 'Recomendação' funcionou")
                
                # CORREÇÃO CRÍTICA: Fechar menus anteriores antes de abrir novo
                try:
                    # Clicar em área neutra para fechar dropdowns abertos
                    await self.page.click('body', position={'x': 10, 'y': 10})
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                await recomendacao_dropdown.click()
                await asyncio.sleep(0.3)  # Reduzido de 1s para 0.3s
                
                # DIAGNÓSTICO: Verificar quantos menus estão abertos
                try:
                    all_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu")]')
                    active_menus = await self.page.query_selector_all('xpath=//div[contains(@class, "menu") and @aria-hidden="false"]')
                    self.log_status(f"🔍 DIAGNÓSTICO Recomendação: {len(all_menus)} menus total, {len(active_menus)} menus ativos")
                except:
                    pass
                
                # CORREÇÃO: Melhorar seleção da recomendação com validação
                recomendacao_final = up_data['Recomendacao']
                self.log_status(f"🎯 Procurando opção de recomendação: '{recomendacao_final}'")
                
                # CORREÇÃO CRÍTICA: Seletores específicos para encontrar a opção no menu ativo
                # Aguardar um pouco para garantir que o dropdown está aberto
                await asyncio.sleep(0.2)  # Reduzido de 1s para 0.2s
                
                # Seletores mais específicos que garantem o contexto correto
                recomendacao_option_selectors = [
                    # Opção 1: Buscar dentro do menu ativo (mais recente)
                    f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{recomendacao_final}"]',
                    # Opção 2: Buscar dentro do último menu aberto
                    f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{recomendacao_final}"]',
                    # Opção 3: Buscar opção visível e não desabilitada
                    f'xpath=//div[contains(@class, "option") and text()="{recomendacao_final}" and not(contains(@class, "disabled"))]',
                    # Opção 4: Seletor direto por texto (última opção)
                    f'text="{recomendacao_final}"'
                ]
                
                option_found = False
                for i, option_selector in enumerate(recomendacao_option_selectors):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1} para opção '{recomendacao_final}': {option_selector[:60]}...")
                        recomendacao_option = await self.page.wait_for_selector(option_selector, timeout=3000)
                        
                        if recomendacao_option:
                            # CORREÇÃO CRÍTICA: Verificar se o elemento está visível e clicável
                            is_visible = await recomendacao_option.is_visible()
                            if is_visible:
                                # Scroll para o elemento se necessário
                                await recomendacao_option.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                
                                # Obter texto da opção para validação
                                try:
                                    option_text = await recomendacao_option.inner_text()
                                    self.log_status(f"🎯 Clicando em opção Recomendação: '{option_text}'")
                                except:
                                    option_text = recomendacao_final
                                
                                # Clicar na opção
                                await recomendacao_option.click()
                                await asyncio.sleep(2)
                                
                                # VALIDAÇÃO: Verificar se a opção foi realmente selecionada
                                validation_selectors = [
                                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Recomendaçao:")]/following::div[1]//div[contains(@class, "singleValue")]',
                                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Recomendaçao:")]/following::div[1]//div[contains(@class, "singleValue")]'
                                ]
                                
                                selection_confirmed = False
                                for val_selector in validation_selectors:
                                    try:
                                        selected_value_element = await self.page.wait_for_selector(val_selector, timeout=2000)
                                        selected_value = await selected_value_element.inner_text()
                                        if selected_value and recomendacao_final in selected_value:
                                            self.log_status(f"✅ Recomendação CONFIRMADA: '{selected_value}' (tentativa {i+1})", "success")
                                            selection_confirmed = True
                                            option_found = True
                                            break
                                    except:
                                        continue
                                
                                if selection_confirmed:
                                    break
                                else:
                                    self.log_status(f"⚠️ Recomendação pode não ter sido selecionada corretamente (tentativa {i+1})", "warning")
                            else:
                                self.log_status(f"⚠️ Elemento encontrado mas não visível (tentativa {i+1})")
                        
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:60]}...")
                        continue
                
                if not option_found:
                    self.log_status(f"❌ FALHA: Não foi possível selecionar '{recomendacao_final}'", "error")
                    self.log_status(f"⚠️ Dropdown pode não ter sido aberto ou opção não existe", "warning")
                else:
                    self.log_status(f"✅ Recomendação '{recomendacao_final}' selecionada e VALIDADA!", "success")
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Recomendação: {str(e)}", "error")
            
            self.stats['ups_processadas'] += 1
            self.log_status(f"✅ UP {up_data['UP']} processada!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro na UP {up_data['UP']}: {str(e)}", "error")
            self.stats['ups_com_erro'] += 1
            return False
    
    async def processar_ups_nucleo(self, ups_nucleo):
        """Processa todas as UPs de um núcleo"""
        try:
            self.log_status(f"🔄 Processando {len(ups_nucleo)} UPs...")
            
            # Criar barra de progresso no Streamlit
            progress_bar = st.progress(0)
            
            ups_processadas = 0
            linha_atual = 0  # Controla qual linha da matriz usar (não incrementa quando UP falha)
            
            for idx, (_, up_row) in enumerate(ups_nucleo.iterrows()):
                # CORREÇÃO: Converter incidência corretamente 
                incidencia_raw = str(up_row['Incidencia']).replace('%', '').replace(',', '.').strip()
                try:
                    incidencia_valor = float(incidencia_raw)
                    
                    # Lógica de conversão:
                    # Se o valor original contém '%' -> já está na forma correta (ex: "92%" → 92)
                    # Se o valor é decimal sem '%' (ex: 0.92) -> converter para percentual (0.92 → 92)
                    if '%' in str(up_row['Incidencia']):
                        # Valor já em percentual (ex: "92%" → 92)
                        incidencia = incidencia_valor
                        self.log_status(f"📊 Incidência (formato %): '{up_row['Incidencia']}' → {incidencia:.2f}%".replace('.', ','))
                    else:
                        # Valor decimal que precisa ser convertido para percentual
                        if incidencia_valor <= 1:
                            incidencia = incidencia_valor * 100  # 0.92 → 92%
                            self.log_status(f"📊 Incidência (decimal): '{up_row['Incidencia']}' → {incidencia:.2f}%".replace('.', ','))
                        else:
                            incidencia = incidencia_valor  # Já está em percentual
                            self.log_status(f"📊 Incidência (já %): '{up_row['Incidencia']}' → {incidencia:.2f}%".replace('.', ','))
                    
                except Exception as e:
                    incidencia = 0
                    self.log_status(f"⚠️ Erro ao converter incidência: '{up_row['Incidencia']}' → assumindo 0% | Erro: {str(e)}", "warning")
                
                # Calcular recomendação
                self.log_status(f"🧮 Calculando recomendação:")
                self.log_status(f"   • Severidade: {up_row['Severidade Predominante']}")
                self.log_status(f"   • Incidência: {incidencia:.2f}%".replace('.', ','))
                self.log_status(f"   • Idade: {up_row['Idade']} anos")
                
                recomendacao = get_recomendacao(
                    up_row['Severidade Predominante'],
                    incidencia,
                    float(up_row['Idade'])
                )
                
                self.log_status(f"🎯 Recomendação calculada: '{recomendacao}'", "success")
                
                # Dados da UP
                up_data = {
                    'UP': up_row['UP'],
                    'Tipo_Dano': up_row['Ocorrência Predominante'],
                    'Incidencia': incidencia,
                    'Severidade': up_row['Severidade Predominante'],
                    'Recomendacao': recomendacao,
                    'UP_CR': up_row.get('UP-C-R', up_row['UP'])
                }
                
                # Processar UP com a linha atual da matriz
                self.log_status(f"🔄 Processando UP {up_row['UP']} ({idx + 1}/{len(ups_nucleo)}) na linha {linha_atual + 1}...")
                self.log_status(f"📊 Status: ups_processadas={ups_processadas}, linha_atual={linha_atual}, idx={idx}")
                
                if await self.processar_up(up_data, linha_atual):
                    ups_processadas += 1
                    # CORREÇÃO: Registrar UP processada com sucesso
                    self.stats['ups_com_sucesso'].append(up_row['UP'])
                    self.log_status(f"✅ UP {up_row['UP']} processada com sucesso na linha {linha_atual + 1}!", "success")
                    
                    # IMPORTANTE: Incrementar linha_atual ANTES de decidir se adiciona nova linha
                    linha_atual += 1
                    self.log_status(f"📈 Próxima UP usará linha {linha_atual + 1} (índice {linha_atual})")
                    
                    # Adicionar nova linha para próxima UP (se ainda há UPs para processar)
                    if idx + 1 < len(ups_nucleo):  # Se não é a última UP
                        self.log_status(f"➕ Adicionando nova linha para próxima UP ({idx + 2}/{len(ups_nucleo)})")
                        try:
                            # Múltiplos seletores para o botão de adicionar linha (do mais confiável ao menos)
                            add_button_selectors = [
                                # MAIS CONFIÁVEL: aria-label é mais estável que classes CSS
                                'xpath=//button[@aria-label="Adicionar linha da Matriz de decisão"]',
                                # Alternativo com aria-label
                                'button[aria-label="Adicionar linha da Matriz de decisão"]',
                                # XPath absoluto fornecido pelo usuário  
                                'xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[2]/div/div[3]/button',
                                # CSS Selector fornecido pelo usuário
                                '#__next > div.max-w-screen-xl.mx-auto.px-2.sm\\:px-4.lg\\:px-0.py-0.bg-white.rounded-md.shadow-md.h-min-screen > div > div > div > div.z-0 > div > div > div > div > div.sm\\:mx-0.lg\\:mt-4 > div > div > form > div:nth-child(2) > div > div.absolute.-right-4.bottom-12.z-50 > button',
                                # Seletores baseados no SVG interno (fallback)
                                'xpath=//button[.//svg[@stroke="currentColor" and @fill="currentColor" and contains(@viewBox, "0 0 1024 1024")]]',
                                'xpath=//button[.//svg[contains(@class, "h-8") and contains(@class, "w-8")]]'
                            ]
                            
                            add_button_clicked = False
                            for i, add_selector in enumerate(add_button_selectors):
                                try:
                                    # Mapear nome amigável para cada seletor
                                    selector_names = [
                                        "ARIA-LABEL (mais confiável)",
                                        "ARIA-LABEL CSS",
                                        "XPATH Absoluto",
                                        "CSS Selector",
                                        "SVG ViewBox",
                                        "SVG Classes"
                                    ]
                                    
                                    selector_name = selector_names[i] if i < len(selector_names) else f"Seletor {i+1}"
                                    self.log_status(f"🔍 Tentativa {i+1} - {selector_name}: {add_selector[:70]}...")
                                    
                                    add_button = await self.page.wait_for_selector(add_selector, timeout=3000)
                                    if add_button:
                                        await add_button.click()
                                        await asyncio.sleep(2)
                                        self.log_status(f"➕ Nova linha adicionada com sucesso usando {selector_name}")
                                        add_button_clicked = True
                                        break
                                except Exception as btn_error:
                                    self.log_status(f"⚠️ {selector_name} falhou: {str(btn_error)[:60]}...")
                                    continue
                            
                            if not add_button_clicked:
                                self.log_status(f"⚠️ Não foi possível adicionar nova linha automaticamente", "warning")
                                self.log_status(f"💡 Continuando com as linhas existentes...", "info")
                                
                        except Exception as add_error:
                            self.log_status(f"⚠️ Erro ao adicionar nova linha: {str(add_error)}", "warning")
                    else:
                        self.log_status(f"🏁 Última UP processada - não precisa adicionar nova linha")
                else:
                    self.log_status(f"⚠️ UP {up_row['UP']} foi PULADA - linha {linha_atual + 1} permanece disponível", "warning")
                    self.log_status(f"� Próxima UP tentará usar a mesma linha {linha_atual + 1}", "info")
                    # IMPORTANTE: NÃO incrementar linha_atual quando UP falha
                
                # Atualizar progresso
                progress_bar.progress((idx + 1) / len(ups_nucleo))
            
            self.log_status(f"✅ {ups_processadas}/{len(ups_nucleo)} UPs processadas!", "success")
            return ups_processadas > 0
            
        except Exception as e:
            self.log_status(f"❌ Erro ao processar UPs: {str(e)}", "error")
            return False
    
    async def finalizar_laudo(self):
        """Finaliza o laudo enviando e confirmando"""
        try:
            self.log_status("🎯 Finalizando laudo...")
            
            # Clicar em Enviar usando xpath específico
            self.log_status("📤 Clicando em 'Enviar'...")
            try:
                enviar_btn = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[3]/button', timeout=10000)
                await enviar_btn.click()
            except:
                # Método alternativo
                enviar_btn = await self.page.wait_for_selector('button:has-text("Enviar")', timeout=10000)
                await enviar_btn.click()
            
            await asyncio.sleep(1)  # Reduzido de 3s para 1s
            
            # Aguardar página de assinatura
            self.log_status("✍️ Aguardando página de assinatura...")
            await asyncio.sleep(1)  # Reduzido de 2s para 1s
            
            # Clicar em Assinatura Funcional usando xpath específico
            try:
                assinatura_btn = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/button/div/div/div[1]', timeout=7000)
                await assinatura_btn.click()
                await asyncio.sleep(1)  # Reduzido de 2s para 1s
                self.log_status("✅ Assinatura Funcional clicada!")
            except:
                self.log_status("⚠️ Botão 'Assinatura Funcional' não encontrado, continuando...", "warning")
            
            # Clicar em Confirmar usando xpath específico
            try:
                confirmar_btn = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div[2]/button', timeout=5000)
                await confirmar_btn.click()
                await asyncio.sleep(1)  # Reduzido de 2s para 1s
                self.log_status("✅ Confirmação clicada!")
            except:
                self.log_status("⚠️ Botão 'Confirmar' não encontrado, continuando...", "warning")
            
            self.log_status("🎉 Laudo finalizado com sucesso!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao finalizar laudo: {str(e)}", "error")
            return False
    
    async def processar_nucleo_completo(self, nucleo, ups_nucleo):
        """Processa um núcleo completo"""
        try:
            self.log_status(f"🏢 PROCESSANDO NÚCLEO: {nucleo}")
            
            # Navegar para upload
            if not await self.navegar_para_upload():
                return False
            
            # Preencher informações básicas - passar o ups_nucleo para acessar a coluna UNF
            if not await self.preencher_informacoes_basicas(nucleo, ups_nucleo):
                self.log_status("⚠️ Erro nas informações básicas, mas continuando...", "warning")
            
            # Preencher campos de texto
            # Determinar tipo de organização baseado no context
            tipo_organizacao = getattr(self, 'tipo_organizacao', 'nucleo')
            if not await self.preencher_campos_texto(nucleo, tipo_organizacao):
                self.log_status("⚠️ Erro nos campos de texto, mas continuando...", "warning")
            
            # Processar UPs
            if await self.processar_ups_nucleo(ups_nucleo):
                # Finalizar laudo
                if await self.finalizar_laudo():
                    self.stats['nucleos_processados'] += 1
                    return True
            
            return False
            
        except Exception as e:
            self.log_status(f"❌ Erro crítico no núcleo {nucleo}: {str(e)}", "error")
            self.stats['erros'].append(f"Núcleo {nucleo}: {str(e)}")
            return False
    
    async def tentar_recuperar_navegador(self):
        """
        Tenta recuperar um navegador não responsivo usando várias estratégias
        sem forçar reinicialização completa.
        """
        try:
            self.log_status("🔧 Iniciando estratégias de recuperação do navegador...")
            
            # Estratégia 1: Tentar refresh da página atual
            try:
                self.log_status("📄 Estratégia 1: Tentando refresh da página...")
                await self.page.reload(wait_until='networkidle')
                await asyncio.sleep(2)
                
                # Testar se voltou a responder
                titulo = await self.page.title()
                self.log_status(f"✅ Página recarregada com sucesso! Título: {titulo}")
                return True
                
            except Exception as e1:
                self.log_status(f"⚠️ Estratégia 1 falhou: {str(e1)}")
            
            # Estratégia 2: Tentar navegar para URL principal
            try:
                self.log_status("🌐 Estratégia 2: Tentando navegar para página inicial...")
                await self.page.goto('https://fenixflorestal.suzanonet.com.br/', wait_until='networkidle')
                await asyncio.sleep(2)
                
                # Testar se voltou a responder
                titulo = await self.page.title()
                self.log_status(f"✅ Navegação bem-sucedida! Título: {titulo}")
                return True
                
            except Exception as e2:
                self.log_status(f"⚠️ Estratégia 2 falhou: {str(e2)}")
            
            # Estratégia 3: Tentar criar nova página no mesmo contexto
            try:
                self.log_status("📑 Estratégia 3: Tentando criar nova aba no mesmo navegador...")
                if self.context:
                    nova_pagina = await self.context.new_page()
                    await nova_pagina.goto('https://fenixflorestal.suzanonet.com.br/', wait_until='networkidle')
                    await asyncio.sleep(2)
                    
                    # Fechar página antiga e usar nova
                    try:
                        await self.page.close()
                    except:
                        pass
                    
                    self.page = nova_pagina
                    titulo = await self.page.title()
                    self.log_status(f"✅ Nova aba criada com sucesso! Título: {titulo}")
                    return True
                
            except Exception as e3:
                self.log_status(f"⚠️ Estratégia 3 falhou: {str(e3)}")
            
            self.log_status("❌ Todas as estratégias de recuperação falharam")
            return False
            
        except Exception as e:
            self.log_status(f"❌ Erro geral na recuperação: {str(e)}")
            return False

    async def preparar_para_novo_lancamento(self):
        """Prepara o navegador para um novo lançamento, verificando e limpando o estado"""
        try:
            self.log_status("🧹 Preparando navegador para novo lançamento...")
            
            # Verificar se o navegador está responsivo
            if not await self.verificar_estado_navegador():
                self.log_status("❌ Navegador não está responsivo")
                return False
            
            # Voltar para a página inicial
            if not await self.voltar_para_inicio():
                self.log_status("❌ Não foi possível voltar para a página inicial")
                return False
            
            # Resetar estatísticas para o novo lançamento
            self.stats['ups_processadas'] = 0
            self.stats['ups_com_sucesso'] = []
            self.stats['erros'] = []
            
            self.log_status("✅ Navegador preparado para novo lançamento!")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao preparar navegador: {str(e)}")
            return False

    async def executar_automacao_completa(self, df_ups, nucleos_selecionados):
        """Executa a automação completa"""
        try:
            self.log_status("🤖 INICIANDO AUTOMAÇÃO COMPLETA DO FÊNIX")
            self.stats['inicio'] = datetime.now()
            
            # Verificar se é continuação de uma sessão existente
            browser_ja_aberto = hasattr(st.session_state, 'browser_ativo') and st.session_state.browser_ativo
            
            # Se o navegador já está aberto, preparar para novo lançamento
            if browser_ja_aberto and self.browser and self.page:
                if not await self.preparar_para_novo_lancamento():
                    self.log_status("⚠️ Erro na preparação, mas continuando...")
            else:
                browser_ja_aberto = False
            
            if not browser_ja_aberto:
                # Inicializar browser apenas se não estiver já aberto
                if not await self.inicializar_browser():
                    return False
                
                # Navegar para Fênix
                if not await self.navegar_para_fenix():
                    return False
                
                # Aguardar login
                if not await self.aguardar_login():
                    return False
                
                # Marcar navegador como ativo
                st.session_state.browser_ativo = True
                st.session_state.automation_instance = self
            else:
                # Reutilizar instância do navegador existente
                if hasattr(st.session_state, 'automation_instance'):
                    old_instance = st.session_state.automation_instance
                    
                    # CORREÇÃO: Validar se o navegador ainda está válido
                    try:
                        # Verificar se page, browser e context ainda estão válidos
                        if (old_instance.page and old_instance.browser and 
                            old_instance.context and old_instance.playwright):
                            
                            # Verificação robusta do navegador existente
                            try:
                                # Tentar uma operação simples para verificar se está responsivo
                                await old_instance.page.evaluate('document.title')
                                current_url = old_instance.page.url
                                
                                if current_url and 'suzanonet' in current_url:
                                    # Se chegou aqui, navegador está válido - reutilizar
                                    self.browser = old_instance.browser
                                    self.page = old_instance.page
                                    self.context = old_instance.context
                                    self.playwright = old_instance.playwright
                                    self.log_status("🔄 Reutilizando navegador já aberto")
                                    
                                    # Verificar se precisa navegar de volta ao início
                                    if not await self.preparar_para_novo_lancamento():
                                        self.log_status("⚠️ Erro na preparação, reinicializando navegador...")
                                        raise Exception("Falha na preparação do navegador")
                                    
                                    # Navegar para upload
                                    if not await self.navegar_para_upload():
                                        self.log_status("⚠️ Erro na navegação, reinicializando navegador...")
                                        raise Exception("Falha na navegação para upload")
                                else:
                                    raise Exception("URL inválida ou não está no Fenix")
                            except Exception as responsiveness_error:
                                self.log_status(f"⚠️ Navegador não responsivo: {str(responsiveness_error)}")
                                self.log_status("🔧 Tentando estratégias de recuperação...")
                                
                                # Estratégias de recuperação sem reiniciar o navegador
                                if await self.tentar_recuperar_navegador():
                                    self.log_status("✅ Navegador recuperado com sucesso!")
                                    # Continuar com o navegador recuperado
                                    if not await self.navegar_para_upload():
                                        self.log_status("⚠️ Erro na navegação após recuperação")
                                        raise Exception("Falha na navegação para upload após recuperação")
                                else:
                                    raise Exception("Não foi possível recuperar o navegador")
                        else:
                            raise Exception("Instâncias do navegador são None")
                            
                    except Exception as validation_error:
                        self.log_status(f"⚠️ Navegador existente inválido: {str(validation_error)}", "warning")
                        
                        # Tentar recuperação antes de reinicializar
                        self.log_status("� Tentando recuperar navegador existente antes de reinicializar...")
                        if await self.tentar_recuperar_navegador():
                            self.log_status("✅ Navegador recuperado! Continuando com sessão existente...")
                            # Tentar navegar para upload com navegador recuperado
                            if await self.navegar_para_upload():
                                return True
                            else:
                                self.log_status("⚠️ Falhou ao navegar após recuperação, forçando reinicialização...")
                        
                        self.log_status("�🔄 Recuperação falhou, inicializando novo navegador...", "info")
                        
                        # Usar função de reinicialização forçada apenas como último recurso
                        self.forcar_reinicializacao_navegador()
                        
                        # Inicializar novo navegador
                        if not await self.inicializar_browser():
                            return False
                        
                        # Navegar para Fênix
                        if not await self.navegar_para_fenix():
                            return False
                        
                        # Aguardar login
                        if not await self.aguardar_login():
                            return False
                        
                        # Marcar navegador como ativo
                        st.session_state.browser_ativo = True
                        st.session_state.automation_instance = self
                else:
                    # Se não há instância salva, tratar como novo navegador
                    self.log_status("⚠️ Instância não encontrada, inicializando novo navegador...", "warning")
                    st.session_state.browser_ativo = False
                    
                    # Inicializar novo navegador
                    if not await self.inicializar_browser():
                        return False
                    
                    # Navegar para Fênix
                    if not await self.navegar_para_fenix():
                        return False
                    
                    # Aguardar login
                    if not await self.aguardar_login():
                        return False
                    
                    # Marcar navegador como ativo
                    st.session_state.browser_ativo = True
                    st.session_state.automation_instance = self
            
            # Processar cada núcleo
            for nucleo in nucleos_selecionados:
                ups_nucleo = df_ups[df_ups['Nucleo'] == nucleo]
                
                if await self.processar_nucleo_completo(nucleo, ups_nucleo):
                    self.log_status(f"✅ Núcleo {nucleo} concluído!", "success")
                else:
                    self.log_status(f"❌ Falha no núcleo {nucleo}", "error")
                
                # Pausa entre núcleos se houver mais de um
                if len(nucleos_selecionados) > 1:
                    self.log_status("⏳ Aguardando 10 segundos antes do próximo núcleo...")
                    await asyncio.sleep(5)
            
            # NOVA LÓGICA: Se processou apenas 1 núcleo, perguntar se quer continuar
            if len(nucleos_selecionados) == 1:
                self.log_status("🎊 Núcleo processado com sucesso!", "success")
                st.session_state.mostrar_continuar_lancamento = True
                return True
            else:
                self.log_status("🎊 AUTOMAÇÃO COMPLETA FINALIZADA!", "success")
                return True
            
        except Exception as e:
            self.log_status(f"❌ Erro crítico na automação: {str(e)}", "error")
            return False
        
        finally:
            # Só fechar o navegador se processou todos os núcleos ou se houve erro
            if len(nucleos_selecionados) > 1 or not hasattr(st.session_state, 'mostrar_continuar_lancamento'):
                await self.fechar_browser()
                if hasattr(st.session_state, 'browser_ativo'):
                    st.session_state.browser_ativo = False
                    del st.session_state.automation_instance
            
            self.exibir_relatorio_final()
    
    async def fechar_browser(self):
        """Fecha o browser"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.log_status("🔧 Navegador fechado")
            
            # Limpar session_state
            if hasattr(st.session_state, 'browser_ativo'):
                st.session_state.browser_ativo = False
            if hasattr(st.session_state, 'automation_instance'):
                del st.session_state.automation_instance
                
        except Exception as e:
            self.log_status(f"⚠️ Erro ao fechar navegador: {str(e)}", "warning")

    async def fechar_browser_manual(self):
        """Fecha o browser manualmente via interface"""
        try:
            await self.fechar_browser()
            st.session_state.mostrar_continuar_lancamento = False
            st.success("🔧 Navegador fechado com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ Erro ao fechar navegador: {str(e)}")
    
    def exibir_relatorio_final(self):
        """Exibe relatório final da automação"""
        tempo_total = datetime.now() - self.stats['inicio'] if self.stats['inicio'] else "N/A"
        
        st.markdown("---")
        st.markdown("## 📊 RELATÓRIO FINAL DA AUTOMAÇÃO")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Núcleos Processados", self.stats['nucleos_processados'])
        with col2:
            st.metric("UPs Processadas", self.stats['ups_processadas'])
        with col3:
            st.metric("UPs com Erro", self.stats['ups_com_erro'])
        with col4:
            tempo_str = str(tempo_total).split('.')[0] if tempo_total != "N/A" else "N/A"
            st.metric("Tempo Total", tempo_str)
        
        if self.stats['erros']:
            st.markdown("### ⚠️ ERROS ENCONTRADOS:")
            for erro in self.stats['erros']:
                st.error(f"• {erro}")
        
        # Taxa de sucesso
        total_ups = self.stats['ups_processadas'] + self.stats['ups_com_erro']
        taxa_sucesso = (self.stats['ups_processadas'] / total_ups * 100) if total_ups > 0 else 0
        st.metric("Taxa de Sucesso", f"{taxa_sucesso:.1f}%")

# =========================================================================
# FUNÇÃO PRINCIPAL PARA USO NO APP.PY
# =========================================================================

def executar_lancamento_fenix(df_ups, nucleos_selecionados, tipo_organizacao=None):
    """Função principal que executa o lançamento no Fênix"""
    # Determinar tipo de organização
    organizacao_tipo = 'propriedade' if tipo_organizacao and tipo_organizacao.startswith("🏗️ Por Propriedade") else 'nucleo'
    automation = FenixAutomation(organizacao_tipo)
    
    # Verificar se é continuação de sessão existente
    if hasattr(st.session_state, 'browser_ativo') and st.session_state.browser_ativo:
        # Reutilizar instância existente
        if hasattr(st.session_state, 'automation_instance'):
            automation = st.session_state.automation_instance
    
    # Executar automação em loop assíncrono
    try:
        import sys
        
        # Configuração específica para Windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Executar automação diretamente com asyncio.run
        try:
            resultado = asyncio.run(
                automation.executar_automacao_completa(df_ups, nucleos_selecionados)
            )
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                # Se há um loop rodando no Streamlit, usar uma abordagem diferente
                import threading
                import queue
                
                result_queue = queue.Queue()
                
                def run_automation():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result = new_loop.run_until_complete(
                            automation.executar_automacao_completa(df_ups, nucleos_selecionados)
                        )
                        result_queue.put(result)
                    except Exception as e:
                        result_queue.put(e)
                    finally:
                        new_loop.close()
                
                thread = threading.Thread(target=run_automation)
                thread.start()
                thread.join()
                
                resultado = result_queue.get()
                if isinstance(resultado, Exception):
                    raise resultado
        
        # CORREÇÃO: Salvar UPs processadas com sucesso no session_state
        if resultado and hasattr(automation, 'stats') and 'ups_com_sucesso' in automation.stats:
            st.session_state.ups_processadas_com_sucesso = automation.stats['ups_com_sucesso']
            ups_count = len(automation.stats['ups_com_sucesso'])
            if ups_count > 0:
                st.success(f"✅ {ups_count} UP(s) processada(s) com sucesso: {', '.join(automation.stats['ups_com_sucesso'])}")
                
                # NOVA FUNCIONALIDADE: Perguntar sobre atualização da planilha
                st.session_state.mostrar_opcao_excel = True
        
        return resultado
        
    except Exception as e:
        st.error(f"❌ Erro crítico na execução: {str(e)}")
        return False

def fechar_navegador_manual():
    """Função para fechar navegador via app.py"""
    try:
        if hasattr(st.session_state, 'automation_instance') and st.session_state.automation_instance:
            import asyncio
            import sys
            
            # Configuração específica para Windows
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            # Executar fechamento
            try:
                asyncio.run(st.session_state.automation_instance.fechar_browser())
            except RuntimeError as e:
                if "cannot be called from a running event loop" in str(e):
                    import threading
                    import queue
                    
                    result_queue = queue.Queue()
                    
                    def close_browser():
                        try:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            new_loop.run_until_complete(st.session_state.automation_instance.fechar_browser())
                            result_queue.put("success")
                        except Exception as e:
                            result_queue.put(e)
                        finally:
                            new_loop.close()
                    
                    thread = threading.Thread(target=close_browser)
                    thread.start()
                    thread.join()
                    
                    resultado = result_queue.get()
                    if isinstance(resultado, Exception):
                        raise resultado
            
            # Limpar session_state
            st.session_state.browser_ativo = False
            st.session_state.mostrar_continuar_lancamento = False
            if hasattr(st.session_state, 'automation_instance'):
                del st.session_state.automation_instance
            
            return True
        else:
            st.warning("Nenhum navegador ativo encontrado.")
            return False
    except Exception as e:
        st.error(f"❌ Erro ao fechar navegador: {str(e)}")
        return False
    """Função principal que executa o lançamento no Fênix"""
    automation = FenixAutomation()
    
    # Executar automação em loop assíncrono
    try:
        import sys
        
        # Configuração específica para Windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Executar automação diretamente com asyncio.run
        try:
            resultado = asyncio.run(
                automation.executar_automacao_completa(df_ups, nucleos_selecionados)
            )
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                # Se há um loop rodando no Streamlit, usar uma abordagem diferente
                import threading
                import queue
                
                result_queue = queue.Queue()
                
                def run_automation():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result = new_loop.run_until_complete(
                            automation.executar_automacao_completa(df_ups, nucleos_selecionados)
                        )
                        result_queue.put(result)
                    except Exception as e:
                        result_queue.put(e)
                    finally:
                        new_loop.close()
                
                thread = threading.Thread(target=run_automation)
                thread.start()
                thread.join()
                
                resultado = result_queue.get()
                if isinstance(resultado, Exception):
                    raise resultado
        
        # CORREÇÃO: Salvar UPs processadas com sucesso no session_state
        if resultado and hasattr(automation, 'stats') and 'ups_com_sucesso' in automation.stats:
            st.session_state.ups_processadas_com_sucesso = automation.stats['ups_com_sucesso']
            ups_count = len(automation.stats['ups_com_sucesso'])
            if ups_count > 0:
                st.success(f"✅ {ups_count} UP(s) processada(s) com sucesso: {', '.join(automation.stats['ups_com_sucesso'])}")
                
                # NOVA FUNCIONALIDADE: Perguntar sobre atualização da planilha
                st.session_state.mostrar_opcao_excel = True
        
        return resultado
        
    except Exception as e:
        st.error(f"❌ Erro crítico na execução: {str(e)}")
        return False

def atualizar_status_planilha(df_original, ups_processadas_com_sucesso, nome_arquivo=None):
    """
    Atualiza o status das UPs processadas com sucesso na planilha Excel
    """
    try:
        if not ups_processadas_com_sucesso:
            st.warning("Nenhuma UP foi processada com sucesso para atualizar.")
            return False
        
        # Fazer uma cópia do DataFrame original
        df_atualizado = df_original.copy()
        
        # Debug: Mostrar informações antes da atualização
        st.info(f"🔍 DataFrame original tem {len(df_atualizado)} linhas")
        st.info(f"🔍 Colunas disponíveis: {list(df_atualizado.columns)}")
        st.info(f"🔍 UPs para atualizar: {ups_processadas_com_sucesso}")
        
        # Verificar se a coluna 'UP' existe
        if 'UP' not in df_atualizado.columns:
            st.error("❌ Coluna 'UP' não encontrada no DataFrame!")
            return False
            
        # Verificar se a coluna 'Laudo Existente' existe  
        if 'Laudo Existente' not in df_atualizado.columns:
            st.error("❌ Coluna 'Laudo Existente' não encontrada no DataFrame!")
            return False
        
        # Debug: Mostrar algumas UPs existentes no DataFrame para comparação
        ups_existentes = df_atualizado['UP'].unique()
        st.info(f"🔍 Total de UPs únicas no DataFrame: {len(ups_existentes)}")
        st.info(f"🔍 Primeiras 10 UPs no DataFrame: {list(ups_existentes[:10])}")
        
        # Estado antes da atualização
        antes_nao = len(df_atualizado[df_atualizado['Laudo Existente'].str.upper() == 'NÃO'])
        antes_sim = len(df_atualizado[df_atualizado['Laudo Existente'].str.upper() == 'SIM'])
        st.info(f"📊 ANTES: {antes_nao} com 'NÃO', {antes_sim} com 'SIM'")
        
        ups_atualizadas = []
        ups_nao_encontradas = []
        
        # Atualizar status das UPs processadas com sucesso
        for up in ups_processadas_com_sucesso:
            # Converter UP para string para garantir comparação correta
            up_str = str(up).strip()
            st.info(f"🔍 Procurando UP: '{up_str}'")
            
            # CORREÇÃO: Buscar a UP no DataFrame (comparação ainda mais robusta)
            # Tentar várias abordagens de comparação
            mask1 = df_atualizado['UP'].astype(str).str.strip() == up_str
            mask2 = df_atualizado['UP'].astype(str).str.strip().str.upper() == up_str.upper()
            mask3 = df_atualizado['UP'] == up  # Comparação direta
            
            # NOVO: Busca mais flexível removendo espaços e caracteres especiais
            up_clean = ''.join(c for c in up_str if c.isalnum()).upper()
            mask4 = df_atualizado['UP'].astype(str).apply(lambda x: ''.join(c for c in str(x) if c.isalnum()).upper()) == up_clean
            
            # NOVO: Busca por substring (útil se há prefixos/sufixos diferentes)
            mask5 = df_atualizado['UP'].astype(str).str.contains(up_str.replace(' ', ''), case=False, na=False)
            
            # Combinar todas as máscaras
            mask_final = mask1 | mask2 | mask3 | mask4 | mask5
            
            linhas_encontradas = mask_final.sum()
            st.info(f"🔍 Linhas encontradas para UP '{up_str}': {linhas_encontradas}")
            
            if linhas_encontradas > 0:
                # Mostrar valores atuais antes da atualização
                valores_atuais = df_atualizado.loc[mask_final, 'Laudo Existente'].tolist()
                st.info(f"🔍 Valores atuais de 'Laudo Existente' para UP '{up_str}': {valores_atuais}")
                
                # Atualizar para 'SIM'
                df_atualizado.loc[mask_final, 'Laudo Existente'] = 'SIM'
                ups_atualizadas.append(up_str)
                
                # Verificar se a atualização funcionou
                valores_apos = df_atualizado.loc[mask_final, 'Laudo Existente'].tolist()
                st.success(f"✅ UP '{up_str}' atualizada! Valores após: {valores_apos}")
            else:
                ups_nao_encontradas.append(up_str)
                st.warning(f"⚠️ UP '{up_str}' não encontrada no DataFrame")
                
                # CORREÇÃO: Debug mais detalhado quando UP não é encontrada
                st.info(f"🔍 UP procurada (original): '{up}' (tipo: {type(up)})")
                st.info(f"🔍 UP procurada (string): '{up_str}'")
                st.info(f"🔍 UP procurada (limpa): '{''.join(c for c in up_str if c.isalnum()).upper()}'")
                
                # Debug adicional: mostrar UPs similares
                ups_similares = [u for u in ups_existentes if up_str.lower() in str(u).lower() or str(u).lower() in up_str.lower()]
                if ups_similares:
                    st.info(f"🔍 UPs similares encontradas: {ups_similares[:5]}")
                else:
                    # Mostrar algumas UPs do DataFrame para comparação
                    st.info(f"🔍 Algumas UPs existentes no DataFrame: {list(ups_existentes[:20])}")
        
        # Estado após a atualização
        depois_nao = len(df_atualizado[df_atualizado['Laudo Existente'].str.upper() == 'NÃO'])
        depois_sim = len(df_atualizado[df_atualizado['Laudo Existente'].str.upper() == 'SIM'])
        st.info(f"📊 DEPOIS: {depois_nao} com 'NÃO', {depois_sim} com 'SIM'")
        
        # Verificar se houve mudança
        mudancas = depois_sim - antes_sim
        st.info(f"📊 MUDANÇA: {mudancas} linhas alteradas de 'NÃO' para 'SIM'")
        
        # Resumo das atualizações
        if ups_atualizadas:
            st.success(f"✅ {len(ups_atualizadas)} UP(s) atualizadas com sucesso: {ups_atualizadas}")
        
        if ups_nao_encontradas:
            st.warning(f"⚠️ {len(ups_nao_encontradas)} UP(s) não encontradas: {ups_nao_encontradas}")
        
        # Mostrar uma amostra do DataFrame atualizado
        st.subheader("📋 Amostra do DataFrame Atualizado:")
        ups_atualizadas_sample = df_atualizado[df_atualizado['UP'].astype(str).str.strip().isin([str(up).strip() for up in ups_processadas_com_sucesso])]
        if not ups_atualizadas_sample.empty:
            st.dataframe(ups_atualizadas_sample[['UP', 'Laudo Existente']], use_container_width=True)
        else:
            st.warning("Nenhuma amostra das UPs atualizadas encontrada para exibir")
        
        # Salvar arquivo atualizado
        if nome_arquivo:
            arquivo_saida = f"Planilha_Atualizada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            df_atualizado.to_excel(arquivo_saida, index=False)
            st.success(f"📄 Planilha atualizada salva como: {arquivo_saida}")
        
        # Oferecer download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_atualizado.to_excel(writer, index=False, sheet_name='Dados_Atualizados')
        
        st.download_button(
            label="📥 Baixar Planilha Atualizada",
            data=buffer.getvalue(),
            file_name=f"Planilha_Atualizada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Retornar True se pelo menos uma UP foi atualizada ou houve mudanças
        return len(ups_atualizadas) > 0 or mudancas > 0
        
    except Exception as e:
        st.error(f"❌ Erro ao atualizar planilha: {str(e)}")
        st.error(f"❌ Detalhes do erro: {type(e).__name__}")
        import traceback
        st.error(f"❌ Stack trace: {traceback.format_exc()}")
        return False
