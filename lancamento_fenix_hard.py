"""
Módulo de Lançamento Automático no Fênix (Hard Mode) - Sistema RPA
Este módulo contém toda a lógica de automação completa para o portal Fênix Florestal
com processamento automático por propriedades sem intervenção do usuário
"""

import streamlit as st
import pandas as pd
import asyncio
import sys
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright

# Importar configurações e constantes do módulo original
try:
    from lancamento_fenix import (
        FENIX_URL, 
        TEXTOS_PADRAO, 
        UNF_MAPPING, 
        get_recomendacao, 
        detectar_unf_por_nucleo
    )
except ImportError as e:
    st.error(f"Erro ao importar módulo lancamento_fenix: {e}")
    # Fallback values em caso de erro
    FENIX_URL = "https://fenixflorestal.suzanonet.com.br/"
    TEXTOS_PADRAO = {
        'objetivo_propriedade': "O presente relatório foi elaborado por solicitação do GEOCAT com o objetivo de avaliar os efeitos dos sinistros nos plantios da Fazenda {nome} e determinar as recomendações para as áreas avaliadas em campo pela área de Mensuração.",
        'diagnostico': "Foi objeto deste Laudo as áreas afetadas por incêndios florestais e vendaval (Déficit Hídrico)...",
        'licoes_aprendidas': "As visitas de campo juntamente com imagens de drones são fundamentais...",
        'consideracoes_finais': "Face ao exposto, com a avaliação de ha, recomenda-se..."
    }

# =========================================================================
# CLASSE PRINCIPAL DE AUTOMAÇÃO HARD MODE
# =========================================================================

class FenixAutomationHard:
    def __init__(self, email=None, senha=None):
        self.browser = None
        self.page = None
        self.playwright = None
        self.email = email
        self.senha = senha
        
        self.stats = {
            'inicio': None,
            'propriedades_processadas': 0,
            'propriedades_total': 0,
            'ups_processadas_total': 0,
            'ups_com_erro_total': 0,
            'propriedades_com_sucesso': [],
            'propriedades_com_erro': [],
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
    
    async def inicializar_browser(self):
        """Inicializa o browser Playwright"""
        try:
            self.log_status("🔧 Inicializando navegador para modo automático...")
            
            # Verificar se o Playwright está instalado
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                self.log_status("❌ Playwright não está instalado. Execute: pip install playwright", "error")
                return False
            
            # Inicializar Playwright com configuração simples
            self.log_status("🔄 Conectando ao Playwright...")
            self.playwright = await async_playwright().start()
            
            # Configurações básicas do browser (mais simples para evitar problemas)
            browser_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
            
            self.log_status("🌐 Lançando navegador Chrome...")
            
            # Lançar browser com configuração mínima
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=browser_args
            )
            
            self.log_status("📄 Criando contexto do navegador...")
            
            # Criar contexto com configurações básicas
            self.context = await self.browser.new_context()
            
            self.log_status("🆕 Criando nova página...")
            
            # Criar página
            self.page = await self.context.new_page()
            
            self.log_status("✅ Navegador inicializado com sucesso!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao inicializar navegador: {str(e)}", "error")
            
            # Log mais detalhado do erro
            import traceback
            error_details = traceback.format_exc()
            self.log_status(f"� Detalhes técnicos: {error_details}", "error")
            
            self.log_status("💡 Possíveis soluções:", "warning")
            self.log_status("   1. Execute: playwright install", "warning")
            self.log_status("   2. Reinicie o VS Code", "warning")
            self.log_status("   3. Verifique se não há outro Chrome aberto", "warning")
            
            return False
    
    async def navegar_para_fenix(self):
        """Navega para o site do Fênix"""
        try:
            self.log_status(f"🌐 Navegando para {FENIX_URL}")
            await self.page.goto(FENIX_URL)
            await self.page.wait_for_load_state('networkidle')
            
            self.log_status("✅ Página do Fênix carregada!")
            
            # Aguardar um pouco para garantir que a página carregou completamente
            await asyncio.sleep(3)
            
            # Clicar no botão inicial necessário
            try:
                self.log_status("🔘 Clicando no botão inicial do Fênix...")
                botao_inicial = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[1]/div[2]/button', timeout=10000)
                await botao_inicial.click()
                await asyncio.sleep(2)
                self.log_status("✅ Botão inicial clicado com sucesso!")
            except Exception as btn_error:
                self.log_status(f"⚠️ Aviso: Não foi possível clicar no botão inicial: {str(btn_error)}", "warning")
                # Continuar mesmo se não conseguir clicar no botão
            
            self.log_status("✅ Navegação para o Fênix concluída!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao navegar: {str(e)}", "error")
            return False
    
    async def fazer_login_automatico(self):
        """Faz login automático usando as credenciais fornecidas"""
        try:
            self.log_status("🔐 Iniciando login automático...")
            
            if not self.email or not self.senha:
                self.log_status("❌ Email ou senha não fornecidos", "error")
                return False
            
            # Aguardar página carregar
            self.log_status("⏳ Aguardando página carregar...")
            await asyncio.sleep(3)
            
            # Verificar se já estamos logados
            try:
                submissao_btn = await self.page.query_selector('button:has-text("Submissão de Laudos")')
                if submissao_btn:
                    self.log_status("✅ Usuário já está logado!", "success")
                    return True
            except:
                pass
            
            # PASSO 1: Clicar no botão específico //*[@id="__next"]/div[1]/div[2]/button
            self.log_status("�️ Clicando no botão de login inicial...")
            try:
                login_btn_xpath = '//*[@id="__next"]/div[1]/div[2]/button'
                login_btn = await self.page.wait_for_selector(f'xpath={login_btn_xpath}', timeout=10000)
                await login_btn.click()
                self.log_status("✅ Botão de login inicial clicado")
                await asyncio.sleep(2)
            except Exception as e:
                self.log_status(f"❌ Erro ao clicar no botão de login inicial: {str(e)}", "error")
                return False
            
            # PASSO 2: Aguardar tela de email aparecer e preencher
            self.log_status("📧 Aguardando tela de email aparecer...")
            try:
                # Múltiplas estratégias para encontrar campo de email
                email_selectors = [
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[name="loginfmt"]',  # Campo comum do Microsoft
                    'input[placeholder*="email"]',
                    'input[placeholder*="Email"]',
                    'input[id*="email"]',
                    '#i0116',  # ID comum do campo email Microsoft
                    'input[type="text"]:first-of-type'
                ]
                
                email_field = None
                for selector in email_selectors:
                    try:
                        email_field = await self.page.wait_for_selector(selector, timeout=5000)
                        if email_field:
                            self.log_status(f"✅ Campo de email encontrado: {selector}")
                            break
                    except:
                        continue
                
                if not email_field:
                    self.log_status("❌ Campo de email não encontrado", "error")
                    return False
                
                await email_field.fill(self.email)
                self.log_status(f"✅ Email preenchido: {self.email}")
                
                # Pressionar Enter após email
                self.log_status("⌨️ Pressionando Enter após email...")
                await self.page.keyboard.press('Enter')
                await asyncio.sleep(3)
                
            except Exception as e:
                self.log_status(f"❌ Erro ao preencher email: {str(e)}", "error")
                return False
            
            # PASSO 3: Aguardar tela de senha aparecer e preencher
            self.log_status("🔒 Aguardando tela de senha aparecer...")
            try:
                # Múltiplas estratégias para encontrar campo de senha
                senha_selectors = [
                    'input[type="password"]',
                    'input[name="passwd"]',  # Campo comum do Microsoft
                    'input[name="password"]',
                    'input[id*="password"]',
                    '#i0118',  # ID comum do campo senha Microsoft
                    'input[placeholder*="senha"]',
                    'input[placeholder*="password"]'
                ]
                
                senha_field = None
                for selector in senha_selectors:
                    try:
                        senha_field = await self.page.wait_for_selector(selector, timeout=5000)
                        if senha_field:
                            self.log_status(f"✅ Campo de senha encontrado: {selector}")
                            break
                    except:
                        continue
                
                if not senha_field:
                    self.log_status("❌ Campo de senha não encontrado", "error")
                    return False
                
                await senha_field.fill(self.senha)
                self.log_status("✅ Senha preenchida")
                
                # Pressionar Enter após senha
                self.log_status("⌨️ Pressionando Enter após senha...")
                await self.page.keyboard.press('Enter')
                
            except Exception as e:
                self.log_status(f"❌ Erro ao preencher senha: {str(e)}", "error")
                return False
            
            # PASSO 4: Aguardar 10 segundos para autenticação 2 fatores
            self.log_status("🔐 Aguardando 10 segundos para autenticação 2 fatores...")
            await asyncio.sleep(10)
            
            # PASSO 5: Verificar se aparece tela para guardar informações e pressionar Enter
            self.log_status("💾 Verificando tela para guardar informações...")
            try:
                # Aguardar um pouco para a tela aparecer
                await asyncio.sleep(3)
                
                # Pressionar Enter para aceitar guardar informações
                self.log_status("⌨️ Pressionando Enter para guardar informações...")
                await self.page.keyboard.press('Enter')
                
                # Aguardar redirecionamento final
                await asyncio.sleep(5)
                
            except Exception as e:
                self.log_status(f"⚠️ Possível erro ao guardar informações: {str(e)}", "warning")
            
            # Aguardar login ser processado
            self.log_status("⏳ Aguardando processamento do login...")
            await asyncio.sleep(5)
            
            # Verificar se login foi bem-sucedido
            self.log_status("🔍 Verificando se login foi bem-sucedido...")
            
            success_selectors = [
                'button:has-text("Submissão de Laudos")',
                'text="Submissão de Laudos"',
                'button:has-text("Laudos")',
                'text="Dashboard"',
                'text="Bem-vindo"'
            ]
            
            login_successful = False
            
            for i, selector in enumerate(success_selectors):
                try:
                    self.log_status(f"🔍 Verificando sucesso {i+1}/{len(success_selectors)}: {selector}")
                    success_element = await self.page.wait_for_selector(selector, timeout=15000)
                    if success_element:
                        self.log_status("✅ Login realizado com sucesso!", "success")
                        login_successful = True
                        break
                except:
                    continue
            
            if not login_successful:
                current_url = self.page.url
                self.log_status(f"❌ Login falhou - não foi possível verificar página principal", "error")
                self.log_status(f"🔍 URL atual: {current_url}")
                return False
            
            return True
                
        except Exception as e:
            self.log_status(f"❌ Erro durante login automático: {str(e)}", "error")
            return False
    
    async def navegar_para_upload(self):
        """Navega para a seção de upload de laudos (mesmo método do original)"""
        try:
            self.log_status("📁 Navegando para 'Submissão de Laudos'...")
            
            # Aguardar página carregar
            await asyncio.sleep(2)
            
            # Verificar se já estamos na página de upload
            try:
                await self.page.wait_for_selector('text="Upload de Laudos"', timeout=3000)
                self.log_status("✅ Já na página de upload!", "success")
                return True
            except:
                pass
            
            # Procurar e clicar em "Submissão de Laudos"
            submissao_btn = await self.page.wait_for_selector('button:has-text("Submissão de Laudos")', timeout=10000)
            await submissao_btn.click()
            await asyncio.sleep(2)
            
            # Procurar e clicar em "Upload de Laudos"
            upload_link = await self.page.wait_for_selector('text="Upload de Laudos"', timeout=5000)
            await upload_link.click()
            await asyncio.sleep(2)
            
            # Validar se chegamos na página correta
            await self.page.wait_for_selector('text="Upload de Laudos"', timeout=5000)
            self.log_status("✅ Página de upload carregada!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao navegar para upload: {str(e)}", "error")
            return False
    
    async def processar_propriedade_completa(self, propriedade_nome, ups_propriedade, unf):
        """Processa uma propriedade completa com todas as suas UPs"""
        try:
            self.log_status(f"🏗️ PROCESSANDO PROPRIEDADE: {propriedade_nome}")
            self.log_status(f"📊 UPs para processar: {len(ups_propriedade)}")
            
            # Navegar para página de upload (limpa formulários anteriores)
            if not await self.navegar_para_upload():
                raise Exception("Não foi possível navegar para página de upload")
            
            # Preencher informações básicas
            if not await self.preencher_informacoes_basicas(propriedade_nome, ups_propriedade, unf):
                raise Exception("Erro ao preencher informações básicas")
            
            # Preencher campos de texto (usando tipo propriedade)
            if not await self.preencher_campos_texto(propriedade_nome, "propriedade"):
                raise Exception("Erro ao preencher campos de texto")
            
            # Processar todas as UPs da propriedade
            ups_processadas = 0
            linha_atual = 0
            
            for idx, (_, up_data) in enumerate(ups_propriedade.iterrows()):
                try:
                    self.log_status(f"🔄 Processando UP {up_data['UP']} ({idx + 1}/{len(ups_propriedade)})")
                    
                    if await self.processar_up(up_data, linha_atual):
                        ups_processadas += 1
                        linha_atual += 1
                        
                        # Adicionar nova linha se não for a última UP
                        if idx < len(ups_propriedade) - 1:
                            await self.adicionar_nova_linha()
                    else:
                        self.log_status(f"⚠️ UP {up_data['UP']} foi pulada", "warning")
                        
                except Exception as up_error:
                    self.log_status(f"❌ Erro ao processar UP {up_data['UP']}: {str(up_error)}", "error")
                    continue
            
            self.log_status(f"✅ {ups_processadas}/{len(ups_propriedade)} UPs processadas!")
            
            # Finalizar e enviar laudo
            if ups_processadas > 0:
                if await self.finalizar_laudo():
                    self.log_status(f"🎉 Propriedade {propriedade_nome} finalizada com sucesso!", "success")
                    self.stats['propriedades_com_sucesso'].append(propriedade_nome)
                    self.stats['ups_processadas_total'] += ups_processadas
                    return True
                else:
                    raise Exception("Erro ao finalizar laudo")
            else:
                raise Exception("Nenhuma UP foi processada com sucesso")
                
        except Exception as e:
            self.log_status(f"❌ Erro ao processar propriedade {propriedade_nome}: {str(e)}", "error")
            self.stats['propriedades_com_erro'].append(propriedade_nome)
            return False
    
    async def preencher_informacoes_basicas(self, propriedade_nome, ups_propriedade, unf):
        """Preenche as informações básicas do formulário"""
        try:
            self.log_status("📝 Preenchendo informações básicas...")
            
            data_atual = datetime.now().strftime("%d/%m/%Y")
            
            # Campo Solicitante
            try:
                solicitante_input = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[1]/div[1]/div/div/div[1]/div/div/input', timeout=5000)
                await solicitante_input.fill("Geocat")
            except:
                pass
            
            # Campo Data de Visita Campo
            try:
                visita_campo = await self.page.wait_for_selector('input[placeholder="Data da visita de campo"]', timeout=5000)
                await visita_campo.fill(data_atual)
            except:
                pass
            
            # Dropdown UNF
            self.log_status(f"✏️ Selecionando UNF: {unf}")
            await self.selecionar_unf(unf)
            
            # Dropdown Urgência (sempre "Média")
            try:
                urgencia_dropdown = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[1]/div[1]/div/div/div[6]/div[1]/div/div/div', timeout=5000)
                await urgencia_dropdown.click()
                await asyncio.sleep(1)
                media_option = await self.page.wait_for_selector('text="Média"', timeout=3000)
                await media_option.click()
            except:
                pass
            
            # Dropdown Tipo Ocorrência (sempre "Sinistro")
            try:
                tipo_dropdown = await self.page.wait_for_selector('xpath=//*[@id="__next"]/div[3]/div/div/div/div[2]/div/div/div/div/div[2]/div/div/form/div[1]/div[1]/div/div/div[6]/div[2]/div/div/div', timeout=5000)
                await tipo_dropdown.click()
                await asyncio.sleep(1)
                sinistro_option = await self.page.wait_for_selector('text="Sinistro"', timeout=3000)
                await sinistro_option.click()
            except:
                pass
            
            self.log_status("✅ Informações básicas preenchidas!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao preencher informações básicas: {str(e)}", "error")
            return False
    
    async def selecionar_unf(self, unf):
        """Seleciona UNF no dropdown (método simplificado)"""
        try:
            # Procurar dropdown UNF
            dropdown_selector = 'xpath=//span[contains(text(), "UNF")]/following::div[contains(@class, "css-1ek14t9-control")][1]'
            dropdown_element = await self.page.wait_for_selector(dropdown_selector, timeout=5000)
            
            # Clicar no dropdown
            await dropdown_element.click()
            await asyncio.sleep(1.5)
            
            # Selecionar opção
            opcao_selector = f'xpath=//div[contains(@class, "option") and text()="{unf}"]'
            opcao = await self.page.wait_for_selector(opcao_selector, timeout=3000)
            await opcao.click()
            
            await asyncio.sleep(1)
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao selecionar UNF: {str(e)}", "error")
            return False
    
    async def preencher_campos_texto(self, nome, tipo_organizacao="propriedade"):
        """Preenche os campos de texto do formulário"""
        try:
            self.log_status("📄 Preenchendo campos de texto...")
            
            # Usar sempre texto para propriedade no modo hard
            texto_objetivo = TEXTOS_PADRAO['objetivo_propriedade'].format(nome=nome)
            
            campos = [
                ("Objetivo", texto_objetivo, 'textarea[name="objetivo"]'),
                ("Diagnóstico", TEXTOS_PADRAO['diagnostico'], 'textarea[name="diagnostico"]'),
                ("Lições Aprendidas", TEXTOS_PADRAO['licoes_aprendidas'], 'textarea[name="licoesAprendidas"]'),
                ("Considerações Finais", TEXTOS_PADRAO['consideracoes_finais'], 'textarea[name="consideracoesFinais"]')
            ]
            
            for campo_nome, texto, selector in campos:
                try:
                    campo = await self.page.wait_for_selector(selector, timeout=5000)
                    await campo.fill(texto)
                    await asyncio.sleep(1)
                except:
                    continue
            
            self.log_status("✅ Campos de texto preenchidos!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao preencher campos de texto: {str(e)}", "error")
            return False
    
    async def processar_up(self, up_data, up_index=0):
        """Processa uma UP individual na Matriz de Decisão (copiado do original)"""
        try:
            self.log_status(f"📍 Processando UP: {up_data['UP']} na LINHA {up_index + 1} da matriz")
            
            # 1. Selecionar UP avaliada (dropdown com digitação)
            try:
                # Fechar qualquer dropdown aberto
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
                
                # Seletores para encontrar o campo UP avaliada
                selectors_up = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "control")]',
                    f'xpath=(//*[contains(text(), "UP avaliada:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
                ]
                
                up_dropdown = None
                for i, selector in enumerate(selectors_up):
                    try:
                        up_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if up_dropdown:
                            break
                    except:
                        continue
                
                if not up_dropdown:
                    raise Exception("Campo 'UP avaliada' não encontrado")
                
                # Clicar no dropdown
                await up_dropdown.click()
                await asyncio.sleep(1)
                
                # Digitar o nome da UP
                up_value = str(up_data["UP"])
                await self.page.keyboard.type(up_value)
                await asyncio.sleep(2)
                
                # Selecionar primeira opção
                option_selectors = [
                    '//div[contains(@class, "css-") and contains(@class, "option")][1]',
                    '//div[@role="option"][1]',
                    '//div[contains(@class, "option")][1]'
                ]
                
                option_selected = False
                for selector in option_selectors:
                    try:
                        first_option = await self.page.wait_for_selector(selector, timeout=2000)
                        if first_option:
                            option_text = await first_option.inner_text()
                            if "nenhum" not in option_text.lower():
                                await first_option.click()
                                self.log_status(f"✅ UP selecionada: '{option_text}'")
                                option_selected = True
                                break
                    except:
                        continue
                
                if not option_selected:
                    self.log_status(f"❌ UP '{up_value}' não encontrada no sistema", "error")
                    return False
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar UP: {str(e)}", "error")
                return False
            
            # 2. Selecionar Tipo Dano
            try:
                tipo_dano_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "control")]'
                ]
                
                tipo_dano_dropdown = None
                for selector in tipo_dano_selectors:
                    try:
                        tipo_dano_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if tipo_dano_dropdown:
                            break
                    except:
                        continue
                
                if not tipo_dano_dropdown:
                    raise Exception("Campo 'Tipo Dano' não encontrado")
                
                # Fechar outros dropdowns
                await self.page.click('body', position={'x': 10, 'y': 10})
                await asyncio.sleep(0.5)
                
                await tipo_dano_dropdown.click()
                await asyncio.sleep(1)
                
                # Mapear ocorrência
                dano_mapping = {
                    'DEFICIT HIDRICO': 'D. Hídrico',
                    'INCENDIO': 'Incêndio', 
                    'VENDAVAL': 'Vendaval'
                }
                
                ocorrencia_excel = str(up_data.get('Ocorrência', '')).upper().strip()
                tipo_dano = dano_mapping.get(ocorrencia_excel, 'D. Hídrico')
                
                # Selecionar opção
                dano_option = await self.page.wait_for_selector(f'text="{tipo_dano}"', timeout=3000)
                await dano_option.click()
                await asyncio.sleep(1)
                
                self.log_status(f"✅ Tipo Dano selecionado: {tipo_dano}")
                
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Tipo Dano: {str(e)}", "error")
            
            # 3. Preencher outros campos
            await self.preencher_campos_up_completos(up_data, up_index)
            
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao processar UP {up_data['UP']}: {str(e)}", "error")
            return False
    
    async def preencher_campos_up_completos(self, up_data, up_index):
        """Preenche todos os campos da UP seguindo EXATAMENTE a lógica do lancamento_fenix.py original"""
        try:
            self.log_status(f"📍 Processando UP: {up_data['UP']} na LINHA {up_index + 1} da matriz")
            
            # 1. Selecionar UP avaliada (dropdown com digitação) - MESMA LÓGICA DO ORIGINAL
            try:
                # Primeiro, garantir que qualquer dropdown aberto seja fechado
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
                
                # Seletores baseados no arquivo original
                selectors_up = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "control")]',
                    f'xpath=(//*[contains(text(), "UP avaliada:")]/following::div[contains(@class, "control")])[{up_index + 1}]'
                ]
                
                up_dropdown = None
                for i, selector in enumerate(selectors_up):
                    try:
                        self.log_status(f"🔍 Tentativa {i+1}: {selector[:80]}...")
                        up_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if up_dropdown:
                            self.log_status(f"✅ Seletor funcionou na tentativa {i+1}")
                            break
                    except Exception as e:
                        self.log_status(f"⚠️ Tentativa {i+1} falhou: {str(e)[:60]}...")
                        continue
                
                if not up_dropdown:
                    raise Exception("Nenhum seletor para 'UP avaliada' funcionou")
                
                # Clicar no dropdown para abrir
                await up_dropdown.click()
                await asyncio.sleep(1)
                
                # Digitar o valor da UP para filtrar as opções
                up_value = str(up_data["UP"])
                self.log_status(f"📝 Digitando UP: {up_value}")
                
                await self.page.keyboard.type(up_value)
                await asyncio.sleep(2)  # Aguardar o filtro funcionar
                
                # Tentar selecionar o primeiro item que aparecer
                try:
                    await asyncio.sleep(1)
                    
                    # Verificar se existe "Nenhum Resultado"
                    nenhum_resultado_selectors = [
                        '//div[contains(text(), "Nenhum resultado")]',
                        '//div[contains(text(), "Nenhum Resultado")]',
                        '//div[contains(text(), "No results")]'
                    ]
                    
                    nenhum_resultado_encontrado = False
                    for no_result_selector in nenhum_resultado_selectors:
                        try:
                            nenhum_resultado = await self.page.query_selector(no_result_selector)
                            if nenhum_resultado and await nenhum_resultado.is_visible():
                                nenhum_resultado_encontrado = True
                                break
                        except:
                            continue
                    
                    if nenhum_resultado_encontrado:
                        self.log_status(f"⚠️ UP '{up_data['UP']}' não encontrada no sistema", "warning")
                        self.log_status(f"🚫 CANCELANDO processamento da UP {up_data['UP']}", "error")
                        return False
                    
                    # Tentar clicar na primeira opção
                    option_selectors = [
                        'xpath=//div[contains(@class, "option")][1]',
                        'xpath=//div[contains(@class, "menu")]//div[contains(@class, "option")][1]'
                    ]
                    
                    option_selected = False
                    for option_selector in option_selectors:
                        try:
                            primeira_opcao = await self.page.wait_for_selector(option_selector, timeout=2000)
                            if primeira_opcao and await primeira_opcao.is_visible():
                                await primeira_opcao.click()
                                option_selected = True
                                self.log_status(f"✅ UP selecionada: {up_value}")
                                break
                        except:
                            continue
                    
                    if not option_selected:
                        await self.page.keyboard.press('Enter')
                        await asyncio.sleep(1)
                    
                    await asyncio.sleep(2)  # Aguardar o campo ser preenchido
                    
                except Exception as selection_error:
                    self.log_status(f"⚠️ Erro ao selecionar opções: {str(selection_error)}", "warning")
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(1)
                
                # VALIDAÇÃO CRÍTICA: Verificar se o campo foi realmente preenchido
                validation_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "UP avaliada:")]/following::div[1]//div[contains(@class, "singleValue")]'
                ]
                
                field_found = False
                field_text = ""
                
                for validation_selector in validation_selectors:
                    try:
                        up_field_value = await self.page.wait_for_selector(validation_selector, timeout=2000)
                        field_text = await up_field_value.inner_text()
                        field_found = True
                        break
                    except:
                        continue
                
                if not field_found or not field_text or field_text.strip() == "":
                    self.log_status(f"❌ Campo UP avaliada não preenchido - UP não cadastrada", "error")
                    self.log_status(f"🚫 CANCELANDO processamento da UP {up_data['UP']}", "error")
                    return False
                else:
                    self.log_status(f"✅ Validação OK: Campo preenchido com '{field_text}'", "success")
                    
            except Exception as e:
                self.log_status(f"❌ Erro ao processar UP avaliada: {str(e)}", "error")
                return False
            
            # 2. Selecionar Tipo Dano - MESMA LÓGICA DO ORIGINAL
            try:
                tipo_dano_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Tipo Dano:")]/following::div[1]//div[contains(@class, "control")]'
                ]
                
                tipo_dano_dropdown = None
                for i, selector in enumerate(tipo_dano_selectors):
                    try:
                        tipo_dano_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if tipo_dano_dropdown:
                            break
                    except:
                        continue
                
                if not tipo_dano_dropdown:
                    raise Exception("Nenhum seletor para 'Tipo Dano' funcionou")
                
                # Clicar em área neutra primeiro
                await self.page.click('body', position={'x': 10, 'y': 10})
                await asyncio.sleep(0.5)
                
                await tipo_dano_dropdown.click()
                await asyncio.sleep(0.3)
                
                # Mapeamento baseado no arquivo original
                dano_mapping = {
                    'INCÊNDIO': 'Incêndio',
                    'INCENDIO': 'Incêndio',
                    'VENDAVAL': 'Vendaval'
                }
                
                # Usar a chave correta que foi criada no up_data
                ocorrencia_excel = str(up_data['Ocorrência Predominante']).upper().strip()
                tipo_dano = dano_mapping.get(ocorrencia_excel, 'Incêndio')  # Fallback para Incêndio
                
                self.log_status(f"📋 Ocorrência Excel: '{up_data['Ocorrência Predominante']}' → Tipo Dano: '{tipo_dano}'")
                
                # Seletores mais específicos baseados no original
                tipo_dano_option_selectors = [
                    f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{tipo_dano}"]',
                    f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{tipo_dano}"]',
                    f'xpath=//div[contains(@class, "option") and text()="{tipo_dano}" and not(contains(@class, "disabled"))]',
                    f'text="{tipo_dano}"'
                ]
                
                option_found = False
                for i, option_selector in enumerate(tipo_dano_option_selectors):
                    try:
                        dano_option = await self.page.wait_for_selector(option_selector, timeout=3000)
                        
                        if dano_option:
                            is_visible = await dano_option.is_visible()
                            if is_visible:
                                await dano_option.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                
                                option_text = await dano_option.inner_text()
                                self.log_status(f"🎯 Clicando em opção Tipo Dano: '{option_text}'")
                                
                                await dano_option.click()
                                await asyncio.sleep(1)
                                
                                self.log_status(f"✅ Tipo Dano selecionado: '{option_text}' (tentativa {i+1})")
                                option_found = True
                                break
                        
                    except Exception as e:
                        continue
                
                if not option_found:
                    raise Exception(f"Não foi possível encontrar opção '{tipo_dano}' no dropdown")
                
                await asyncio.sleep(1)
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Tipo Dano: {str(e)}", "error")
            
            # 3. Selecionar Ocorrência na UP (primeiro item do dropdown) - MESMA LÓGICA DO ORIGINAL
            try:
                ocorrencia_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Ocorrência na UP:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Ocorrência na UP:")]/following::div[1]//div[contains(@class, "control")]'
                ]
                
                ocorrencia_dropdown = None
                for selector in ocorrencia_selectors:
                    try:
                        ocorrencia_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if ocorrencia_dropdown:
                            break
                    except:
                        continue
                
                if not ocorrencia_dropdown:
                    raise Exception("Nenhum seletor para 'Ocorrência na UP' funcionou")
                
                # Clicar em área neutra para fechar dropdowns abertos
                await self.page.click('body', position={'x': 10, 'y': 10})
                await asyncio.sleep(0.5)
                    
                await ocorrencia_dropdown.click()
                await asyncio.sleep(0.3)
                
                # Múltiplos seletores para encontrar a primeira opção do dropdown
                option_selectors = [
                    'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option")][1]',
                    'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option")][1]',
                    'xpath=//div[contains(@class, "option") and not(contains(@class, "disabled"))][1]'
                ]
                
                primeiro_item_encontrado = False
                for selector in option_selectors:
                    try:
                        primeiro_item = await self.page.wait_for_selector(selector, timeout=3000)
                        
                        if primeiro_item and await primeiro_item.is_visible():
                            option_text = await primeiro_item.inner_text()
                            
                            if "nenhum" not in option_text.lower() and "no result" not in option_text.lower():
                                await primeiro_item.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                
                                await primeiro_item.click()
                                self.log_status(f"✅ Primeira ocorrência selecionada: '{option_text}'")
                                primeiro_item_encontrado = True
                                break
                        
                    except Exception as e:
                        continue
                
                if not primeiro_item_encontrado:
                    await self.page.keyboard.press('Enter')
                    
                await asyncio.sleep(0.3)
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Ocorrência: {str(e)}", "error")
            
            # 4. Preencher Recomendação (%) com incidência - MESMA LÓGICA DO ORIGINAL
            try:
                recomendacao_pct_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Recomendação(%)")]/following::div[1]//input',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Recomendação(%)")]/following::div[1]//input'
                ]
                
                recomendacao_input = None
                for selector in recomendacao_pct_selectors:
                    try:
                        recomendacao_input = await self.page.wait_for_selector(selector, timeout=3000)
                        if recomendacao_input:
                            break
                    except:
                        continue
                
                if not recomendacao_input:
                    raise Exception("Nenhum seletor para 'Recomendação %' funcionou")
                
                # CORREÇÃO: Formatar valor igual ao original
                incidencia_valor = f"{up_data['Incidencia']:.2f}"
                self.log_status(f"📝 Preenchendo Recomendação % com: {incidencia_valor}%")
                
                await recomendacao_input.click()
                await asyncio.sleep(0.2)
                
                await self.page.keyboard.press('Control+a')
                await asyncio.sleep(0.1)
                await recomendacao_input.fill("")
                await asyncio.sleep(0.1)
                await recomendacao_input.fill(incidencia_valor)
                await asyncio.sleep(0.2)
                
                # Validação do campo
                field_check = await recomendacao_input.input_value()
                if field_check and field_check.strip():
                    self.log_status(f"✅ Recomendação % preenchida: {field_check}%", "success")
                else:
                    self.log_status(f"⚠️ Recomendação % pode não ter sido preenchida corretamente", "warning")
                    
            except Exception as e:
                self.log_status(f"❌ Erro ao preencher Recomendação %: {str(e)}", "error")
            
            # 5. Selecionar Severidade - MESMA LÓGICA DO ORIGINAL
            try:
                severidade_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Severidade:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Severidade:")]/following::div[1]//div[contains(@class, "control")]'
                ]
                
                severidade_dropdown = None
                for selector in severidade_selectors:
                    try:
                        severidade_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if severidade_dropdown:
                            break
                    except:
                        continue
                
                if not severidade_dropdown:
                    raise Exception("Nenhum seletor para 'Severidade' funcionou")
                
                # Clicar em área neutra para fechar dropdowns abertos
                await self.page.click('body', position={'x': 10, 'y': 10})
                await asyncio.sleep(0.5)
                
                await severidade_dropdown.click()
                await asyncio.sleep(0.3)
                
                # Normalizar severidade - mapeamento EXATO do original
                severidade_original = str(up_data.get('Severidade Predominante', '')).strip()
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
                
                # Seletores específicos baseados no original
                severidade_option_selectors = [
                    f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{severidade_valor}"]',
                    f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{severidade_valor}"]',
                    f'xpath=//div[contains(@class, "option") and text()="{severidade_valor}" and not(contains(@class, "disabled"))]',
                    f'text="{severidade_valor}"'
                ]
                
                option_found = False  
                for i, selector in enumerate(severidade_option_selectors):
                    try:
                        severidade_option = await self.page.wait_for_selector(selector, timeout=3000)
                        
                        if await severidade_option.is_visible():
                            await severidade_option.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            
                            await severidade_option.click()
                            self.log_status(f"✅ Severidade selecionada: {severidade_valor}")
                            option_found = True
                            break
                            
                    except Exception as e:
                        continue
                
                if not option_found:
                    raise Exception(f"Não foi possível encontrar opção '{severidade_valor}' no dropdown")
                
                await asyncio.sleep(0.2)
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Severidade: {str(e)}", "error")
            
            # 6. Selecionar Recomendação (aplicar regra de negócio) - MESMA LÓGICA DO ORIGINAL
            try:
                recomendacao_selectors = [
                    f'xpath=(//fieldset//div[contains(@class, "flex") and contains(@class, "flex-col") and contains(@class, "lg:flex-row")])[{up_index + 1}]//span[contains(text(), "Recomendaçao:")]/following::div[1]//div[contains(@class, "css-1ek14t9-control")]',
                    f'xpath=//input[@name="sinistros[{up_index}].idade"]/ancestor::div[contains(@class, "flex-col") and contains(@class, "lg:flex-row")]//span[contains(text(), "Recomendaçao:")]/following::div[1]//div[contains(@class, "control")]'
                ]
                
                recomendacao_dropdown = None
                for selector in recomendacao_selectors:
                    try:
                        recomendacao_dropdown = await self.page.wait_for_selector(selector, timeout=3000)
                        if recomendacao_dropdown:
                            break
                    except:
                        continue
                
                if not recomendacao_dropdown:
                    raise Exception("Nenhum seletor para 'Recomendação' funcionou")
                
                # Clicar em área neutra para fechar dropdowns abertos
                await self.page.click('body', position={'x': 10, 'y': 10})
                await asyncio.sleep(0.5)
                
                await recomendacao_dropdown.click()
                await asyncio.sleep(0.3)
                
                # CORREÇÃO: Usar valor da coluna 'Recomendacao' (se disponível)
                recomendacao_final = up_data.get('Recomendacao', 'Limpeza de Área')
                self.log_status(f"🎯 Procurando opção de recomendação: '{recomendacao_final}'")
                
                # Seletores específicos baseados no original
                recomendacao_option_selectors = [
                    f'xpath=//div[contains(@class, "menu") and @aria-hidden="false"]//div[contains(@class, "option") and text()="{recomendacao_final}"]',
                    f'xpath=(//div[contains(@class, "menu")])[last()]//div[contains(@class, "option") and text()="{recomendacao_final}"]',
                    f'xpath=//div[contains(@class, "option") and text()="{recomendacao_final}" and not(contains(@class, "disabled"))]',
                    f'text="{recomendacao_final}"'
                ]
                
                option_found = False
                for i, option_selector in enumerate(recomendacao_option_selectors):
                    try:
                        recomendacao_option = await self.page.wait_for_selector(option_selector, timeout=3000)
                        
                        if recomendacao_option:
                            is_visible = await recomendacao_option.is_visible()
                            if is_visible:
                                await recomendacao_option.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                
                                try:
                                    option_text = await recomendacao_option.inner_text()
                                    self.log_status(f"🎯 Clicando em opção Recomendação: '{option_text}'")
                                except:
                                    option_text = recomendacao_final
                                
                                await recomendacao_option.click()
                                await asyncio.sleep(2)
                                
                                # VALIDAÇÃO baseada no original
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
                        
                    except Exception as e:
                        continue
                
                if not option_found:
                    self.log_status(f"❌ FALHA: Não foi possível selecionar '{recomendacao_final}'", "error")
                else:
                    self.log_status(f"✅ Recomendação '{recomendacao_final}' selecionada e VALIDADA!", "success")
            except Exception as e:
                self.log_status(f"❌ Erro ao selecionar Recomendação: {str(e)}", "error")
            
            self.log_status(f"✅ UP {up_data['UP']} processada!", "success")
            return True
                
        except Exception as e:
            self.log_status(f"❌ Erro na UP {up_data['UP']}: {str(e)}", "error")
            return False
            


    
    async def adicionar_nova_linha(self):
        """Adiciona uma nova linha na matriz de decisão"""
        try:
            add_button = await self.page.wait_for_selector('button[aria-label="Adicionar linha na matriz de decisão"]', timeout=5000)
            await add_button.click()
            await asyncio.sleep(2)
            return True
        except Exception as e:
            self.log_status(f"❌ Erro ao adicionar nova linha: {str(e)}", "error")
            return False
    
    async def finalizar_laudo(self):
        """Finaliza e envia o laudo"""
        try:
            self.log_status("🎯 Finalizando laudo...")
            
            # Clicar em Enviar
            enviar_btn = await self.page.wait_for_selector('button:has-text("Enviar")', timeout=10000)
            await enviar_btn.click()
            await asyncio.sleep(3)
            
            # Página de assinatura - clicar em "Assinatura Funcional"
            assinatura_btn = await self.page.wait_for_selector('button:has-text("Assinatura Funcional")', timeout=10000)
            await assinatura_btn.click()
            await asyncio.sleep(2)
            
            # Confirmar
            confirmar_btn = await self.page.wait_for_selector('button:has-text("Confirmar")', timeout=5000)
            await confirmar_btn.click()
            await asyncio.sleep(3)
            
            self.log_status("✅ Laudo enviado com sucesso!", "success")
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro ao finalizar laudo: {str(e)}", "error")
            return False
    
    async def processar_todas_propriedades(self, propriedades_selecionadas, df_data, unf_selecionada):
        """Processa todas as propriedades selecionadas automaticamente"""
        try:
            self.stats['inicio'] = datetime.now()
            self.stats['propriedades_total'] = len(propriedades_selecionadas)
            
            self.log_status(f"🚀 INICIANDO PROCESSAMENTO AUTOMÁTICO DE {len(propriedades_selecionadas)} PROPRIEDADES", "success")
            
            # Inicializar navegador e fazer login
            if not await self.inicializar_browser():
                return False
            
            if not await self.navegar_para_fenix():
                return False
            
            if not await self.fazer_login_automatico():
                return False
            
            # Processar cada propriedade
            for idx, propriedade in enumerate(propriedades_selecionadas):
                try:
                    self.log_status(f"\n{'='*50}")
                    self.log_status(f"🏗️ PROPRIEDADE {idx + 1}/{len(propriedades_selecionadas)}: {propriedade}")
                    self.log_status(f"{'='*50}")
                    
                    # Filtrar UPs desta propriedade
                    ups_propriedade = df_data[df_data['Propriedade'] == propriedade]
                    
                    if ups_propriedade.empty:
                        self.log_status(f"⚠️ Nenhuma UP encontrada para propriedade {propriedade}", "warning")
                        continue
                    
                    # Processar propriedade
                    if await self.processar_propriedade_completa(propriedade, ups_propriedade, unf_selecionada):
                        self.stats['propriedades_processadas'] += 1
                        self.log_status(f"✅ Propriedade {propriedade} concluída!", "success")
                    else:
                        self.log_status(f"❌ Erro ao processar propriedade {propriedade}", "error")
                    
                    # Aguardar antes da próxima propriedade
                    if idx < len(propriedades_selecionadas) - 1:
                        self.log_status("⏳ Aguardando antes da próxima propriedade...")
                        await asyncio.sleep(3)
                        
                except Exception as prop_error:
                    self.log_status(f"❌ Erro crítico na propriedade {propriedade}: {str(prop_error)}", "error")
                    continue
            
            # Estatísticas finais
            tempo_total = datetime.now() - self.stats['inicio']
            self.log_status(f"\n🎊 PROCESSAMENTO CONCLUÍDO!")
            self.log_status(f"⏱️ Tempo total: {tempo_total}")
            self.log_status(f"✅ Propriedades processadas: {self.stats['propriedades_processadas']}/{self.stats['propriedades_total']}")
            self.log_status(f"📊 UPs processadas: {self.stats['ups_processadas_total']}")
            self.log_status(f"🎯 Propriedades com sucesso: {len(self.stats['propriedades_com_sucesso'])}")
            
            if self.stats['propriedades_com_sucesso']:
                self.log_status(f"✅ Propriedades bem-sucedidas: {', '.join(self.stats['propriedades_com_sucesso'])}")
            
            if self.stats['propriedades_com_erro']:
                self.log_status(f"❌ Propriedades com erro: {', '.join(self.stats['propriedades_com_erro'])}")
            
            return True
            
        except Exception as e:
            self.log_status(f"❌ Erro crítico no processamento automático: {str(e)}", "error")
            return False
        
        finally:
            # Fechar navegador
            try:
                if self.browser:
                    await self.browser.close()
                if self.playwright:
                    await self.playwright.stop()
            except:
                pass

# =========================================================================
# FUNÇÕES UTILITÁRIAS
# =========================================================================

def obter_propriedades_por_unf(df, unf):
    """Obtém lista de propriedades e contagem de UPs por UNF"""
    try:
        # Verificar se a coluna de propriedade existe (aceitar variações)
        propriedade_col = 'Propriedade'
        if 'Propriedade' not in df.columns:
            for col in df.columns:
                if col.lower() in ['propriedade', 'property']:
                    propriedade_col = col
                    break
        
        if propriedade_col not in df.columns:
            st.error("Coluna de propriedade não encontrada")
            return {}
        
        # Filtrar dados pela UNF
        df_unf = df[df['UNF'] == unf]
        
        if df_unf.empty:
            return {}
        
        # Agrupar por propriedade e contar UPs
        propriedades_info = df_unf.groupby(propriedade_col).size().to_dict()
        
        return propriedades_info
        
    except Exception as e:
        st.error(f"Erro ao obter propriedades por UNF: {str(e)}")
        return {}

def executar_lancamento_fenix_hard(df_data, email, senha, unf_selecionada, propriedades_selecionadas):
    """Função principal para executar o lançamento automático"""
    try:
        # Validações
        if df_data.empty:
            st.error("❌ Dados não carregados")
            return False
        
        if not email or not senha:
            st.error("❌ Email e senha são obrigatórios")
            return False
        
        if not propriedades_selecionadas:
            st.error("❌ Nenhuma propriedade selecionada")
            return False
        
        # Verificar se o Playwright está disponível
        try:
            import playwright
            st.info("✅ Playwright disponível")
        except ImportError:
            st.error("❌ Playwright não está instalado. Execute: pip install playwright")
            return False
        
        # Criar instância da automação
        st.info("🔧 Criando instância de automação...")
        automation = FenixAutomationHard(email=email, senha=senha)
        
        # Executar processamento com correção específica para Windows
        st.info("🚀 Iniciando processamento automático...")
        
        # Solução para problema do asyncio no Windows
        if sys.platform == 'win32':
            # Usar asyncio.run com a política correta
            try:
                # Definir política do Windows antes de executar
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                resultado = asyncio.run(
                    automation.processar_todas_propriedades(
                        propriedades_selecionadas, 
                        df_data, 
                        unf_selecionada
                    )
                )
            except Exception as asyncio_error:
                st.warning(f"⚠️ Erro com ProactorEventLoop, tentando alternativa: {str(asyncio_error)}")
                # Fallback: usar SelectorEventLoop
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                resultado = asyncio.run(
                    automation.processar_todas_propriedades(
                        propriedades_selecionadas, 
                        df_data, 
                        unf_selecionada
                    )
                )
        else:
            # Para outros sistemas operacionais
            resultado = asyncio.run(
                automation.processar_todas_propriedades(
                    propriedades_selecionadas, 
                    df_data, 
                    unf_selecionada
                )
            )
        
        return resultado
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"❌ Erro na execução: {str(e)}")
        st.error(f"🔍 Detalhes do erro:\n```\n{error_details}\n```")
        return False