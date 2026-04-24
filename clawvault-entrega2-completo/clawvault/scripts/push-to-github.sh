#!/bin/bash
# ============================================================================
# ClawVault — Script de push para o GitHub
# ============================================================================
#
# Este script faz o seguinte na ordem:
#  1. Verifica se o Git está instalado
#  2. Inicializa o repositório (se não existe)
#  3. Adiciona todos os arquivos respeitando o .gitignore
#  4. Cria o primeiro commit
#  5. Configura o remote para seu repositório no GitHub
#  6. Faz o push inicial
#
# USO:
#   chmod +x scripts/push-to-github.sh
#   ./scripts/push-to-github.sh
#
# O Git vai pedir suas credenciais do GitHub na primeira vez.
# Use um "Personal Access Token" como senha (não sua senha normal).
# Crie o token em: https://github.com/settings/tokens/new
#   Escopo necessário: repo
# ============================================================================

set -e  # para se qualquer comando falhar

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "=============================================="
echo " ClawVault — Push para GitHub"
echo "=============================================="
echo -e "${NC}"

# URL do repositório (ajuste se seu repo tiver nome diferente)
REPO_URL="https://github.com/Elitj06/Elitj06-clawvault.git"

# ----------------------------------------------------------------------------
# 1. Verifica Git
# ----------------------------------------------------------------------------
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git não está instalado.${NC}"
    echo "Instale: https://git-scm.com/downloads"
    exit 1
fi
echo -e "${GREEN}✅ Git instalado: $(git --version)${NC}"

# ----------------------------------------------------------------------------
# 2. Verifica se está na pasta correta
# ----------------------------------------------------------------------------
if [ ! -f "README.md" ] || [ ! -d "backend" ]; then
    echo -e "${RED}❌ Este script deve ser rodado na raiz do ClawVault.${NC}"
    echo "Navegue até a pasta clawvault/ e rode de novo."
    exit 1
fi

# ----------------------------------------------------------------------------
# 3. Verifica se .env não está sendo commitado por engano
# ----------------------------------------------------------------------------
if [ -f ".env" ]; then
    if grep -q "^\.env$" .gitignore 2>/dev/null; then
        echo -e "${GREEN}✅ .env existe mas está no .gitignore (seguro)${NC}"
    else
        echo -e "${RED}⚠️  AVISO: .env existe e NÃO está no .gitignore!${NC}"
        echo "Suas chaves de API podem vazar. Cancelando."
        exit 1
    fi
fi

# ----------------------------------------------------------------------------
# 4. Inicializa repositório se necessário
# ----------------------------------------------------------------------------
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}📦 Inicializando repositório Git...${NC}"
    git init
    git branch -M main
fi

# ----------------------------------------------------------------------------
# 5. Configura identidade se não estiver configurada
# ----------------------------------------------------------------------------
if [ -z "$(git config user.email)" ]; then
    echo -e "${YELLOW}⚠️  Configurando identidade Git...${NC}"
    read -p "Seu email (do GitHub): " GIT_EMAIL
    read -p "Seu nome: " GIT_NAME
    git config user.email "$GIT_EMAIL"
    git config user.name "$GIT_NAME"
    echo -e "${GREEN}✅ Identidade configurada${NC}"
fi

# ----------------------------------------------------------------------------
# 6. Adiciona arquivos e cria commit
# ----------------------------------------------------------------------------
echo -e "${YELLOW}📝 Adicionando arquivos...${NC}"
git add .

# Só cria commit se tiver mudanças
if git diff --cached --quiet; then
    echo -e "${YELLOW}ℹ️  Sem mudanças para commitar.${NC}"
else
    COMMIT_COUNT=$(git rev-list --all --count 2>/dev/null || echo "0")
    if [ "$COMMIT_COUNT" = "0" ]; then
        COMMIT_MSG="Initial commit: ClawVault v0.2.0 — sistema multi-LLM com memória e WhatsApp"
    else
        COMMIT_MSG="Update: $(date +%Y-%m-%d)"
    fi
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✅ Commit criado: $COMMIT_MSG${NC}"
fi

# ----------------------------------------------------------------------------
# 7. Configura remote
# ----------------------------------------------------------------------------
if ! git remote get-url origin &> /dev/null; then
    echo -e "${YELLOW}🔗 Configurando remote origin...${NC}"
    git remote add origin "$REPO_URL"
    echo -e "${GREEN}✅ Remote configurado: $REPO_URL${NC}"
else
    CURRENT_REMOTE=$(git remote get-url origin)
    echo -e "${GREEN}✅ Remote já existe: $CURRENT_REMOTE${NC}"
fi

# ----------------------------------------------------------------------------
# 8. Push
# ----------------------------------------------------------------------------
echo -e "${YELLOW}🚀 Fazendo push para GitHub...${NC}"
echo -e "${YELLOW}   (Se pedir credenciais, use seu usuário GitHub e um Personal Access Token)${NC}"
echo ""

git push -u origin main

echo ""
echo -e "${GREEN}=============================================="
echo "🎉 SUCESSO! Código publicado no GitHub."
echo "=============================================="
echo -e "${NC}"
echo "Acesse: $REPO_URL"
echo ""
echo -e "${BLUE}Próximos passos:${NC}"
echo "  - Configure o README no GitHub (já está no projeto)"
echo "  - Adicione tópicos ao repo: ai, llm, whatsapp, agents"
echo "  - Considere tornar privado se ainda não está"
