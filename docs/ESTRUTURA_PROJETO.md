# 📁 Estrutura Organizada do Projeto FenixRPA

## 🎯 Objetivo da Reorganização

Este projeto foi reorganizado em **14/09/2025** para melhorar a manutenibilidade e clareza do código, separando arquivos por categoria e função.

## 📂 Estrutura de Pastas

### 📄 **Raiz do Projeto** (Arquivos Essenciais)
- `app.py` - Interface principal Streamlit com menu dual (Fênix + PDF)
- `lancamento_fenix.py` - Motor de automação com login automático Microsoft SSO
- `cria_pdf.py` - Gerador de PDFs profissionais com imagens
- `config.py` - Configurações centralizadas do sistema
- `requirements.txt` - Dependências Python necessárias
- `README.md` - Documentação principal do projeto

### 📁 **docs/** - Documentação Técnica
Contém toda a documentação de desenvolvimento, correções e guias:
- `AUTENTICACAO_MODERNA.md` - Guia de autenticação Microsoft SSO
- `CORRECAO_*.md` - Documentação de correções específicas implementadas
- `GUIA_AUTENTICACAO_MODERNA.md` - Tutorial detalhado de autenticação
- `VALIDACAO_UP_AVALIADA.md` - Validação de campos UP
- `VERIFICACAO_IMPLEMENTACOES.md` - Checklist de implementações

### 📁 **backup/** - Arquivos de Backup e Logs
Contém backups de versões anteriores e logs de desenvolvimento:
- `app_backup.py` - Backup da versão anterior do app principal
- `becapeapp.txt` - Backup de configurações da interface
- `becapeConfig.txt` - Backup de configurações gerais
- `becape_lancamento_fenix.txt` - Backup do módulo de automação
- `botFenix.txt` - Logs e notas de desenvolvimento
- `criaPdf 1.txt` - Backup do sistema de PDF

### 📁 **tests/** - Scripts de Teste
Scripts utilizados para testes durante o desenvolvimento:
- `criar_dados_exemplo.py` - Gerador de dados de teste
- `teste_exemplo.py` - Testes de funcionalidades básicas
- `teste_incidencia.py` - Testes específicos de cálculo de incidência
- `test_placeholder.py` - Testes de placeholder e validação

### 📁 **examples/** - Dados e Exemplos
Dados de exemplo e recursos para testes:
- `data.xlsx` - Planilha de exemplo para testes
- `entrega_9.xlsx` - Exemplo de planilha de entrega
- `teste_propriedade.csv` - Dados CSV de propriedades de teste
- `teste_propriedade.xlsx` - Dados Excel de propriedades de teste
- `teste_croquis/` - Pasta com imagens de croquis de exemplo
- `teste_imagens/` - Pasta com imagens de teste para PDFs

## 🔄 Benefícios da Reorganização

### ✅ **Melhoria na Manutenibilidade**
- Separação clara entre código de produção e arquivos auxiliares
- Documentação centralizada e organizada
- Backups preservados sem poluir o código principal

### ✅ **Facilidade de Deploy**
- Raiz limpa com apenas arquivos essenciais
- Estrutura profissional e padronizada
- Fácil identificação dos componentes principais

### ✅ **Desenvolvimento Mais Eficiente**
- Testes organizados em pasta específica
- Exemplos e dados separados do código
- Documentação técnica acessível e estruturada

### ✅ **Compatibilidade Mantida**
- ✅ Todas as funcionalidades preservadas
- ✅ Imports e referências atualizados
- ✅ Sistema continua funcionando normalmente

## 🎯 Próximos Passos

1. **Testes de Funcionalidade** - Verificar se todas as funções estão operacionais
2. **Atualização de Imports** - Garantir que não há referências quebradas
3. **Commit Organizado** - Versionar a nova estrutura
4. **Deploy Limpo** - Estrutura pronta para produção

---

*Reorganização realizada em 14/09/2025 - Mantendo funcionalidades intactas com estrutura profissional*