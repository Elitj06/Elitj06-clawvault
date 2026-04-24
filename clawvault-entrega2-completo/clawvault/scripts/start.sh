#!/bin/bash
# ============================================================================
# ClawVault — Iniciar backend e frontend
# ============================================================================
# Uso: ./scripts/start.sh
# ============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐾 Iniciando ClawVault...${NC}"

# Backend
echo -e "${GREEN}📡 Iniciando backend em http://localhost:8000${NC}"
python -m backend.api.server &
BACKEND_PID=$!

# Aguarda backend ficar pronto
sleep 2

# Frontend
if [ -d "frontend/node_modules" ]; then
    echo -e "${GREEN}🎨 Iniciando frontend em http://localhost:3000${NC}"
    cd frontend && npm run dev &
    FRONTEND_PID=$!
    cd ..
else
    echo -e "${BLUE}⚠️  Frontend não instalado. Rode: cd frontend && npm install${NC}"
fi

echo ""
echo -e "${GREEN}✅ ClawVault rodando!${NC}"
echo "   Backend: http://localhost:8000 (docs: /docs)"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Ctrl+C para parar."

# Espera pelos processos
wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
