#!/bin/bash
# ClawVault — Diagnóstico de conexão

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKEND_LOCAL="http://localhost:8000"
TUNNEL_URL="https://deeply-investigations-suggesting-wheat.trycloudflare.com"
FRONTEND_URL="https://clawvault-ashen.vercel.app"
SERVER_IP="5.78.198.180"

echo -e "${BLUE}=================================================="
echo " ClawVault — Diagnóstico de Conexão"
echo " $(date)"
echo "==================================================${NC}"
echo ""

echo -e "${YELLOW}[TESTE 1/7] Backend está rodando localmente?${NC}"
if curl -s -f -o /dev/null --max-time 5 "$BACKEND_LOCAL/api/status"; then
 echo -e "${GREEN}✓ OK — Backend respondendo em $BACKEND_LOCAL${NC}"
 STATUS=$(curl -s "$BACKEND_LOCAL/api/status")
 PROVIDERS_ON=$(echo "$STATUS" | grep -o '"true"' | wc -l)
 echo " → Providers ativos: $PROVIDERS_ON"
else
 echo -e "${RED}✗ FALHA — Backend NÃO responde em $BACKEND_LOCAL${NC}"
 exit 1
fi
echo ""

echo -e "${YELLOW}[TESTE 2/7] Cloudflare tunnel está ativo?${NC}"
TUNNEL_RESP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$TUNNEL_URL/api/status")
if [ "$TUNNEL_RESP" = "200" ]; then
 echo -e "${GREEN}✓ OK — Tunnel respondendo (HTTP 200)${NC}"
elif [ "$TUNNEL_RESP" = "000" ]; then
 echo -e "${RED}✗ FALHA — Tunnel inativo ou URL mudou${NC}"
else
 echo -e "${RED}✗ FALHA — Tunnel respondeu HTTP $TUNNEL_RESP${NC}"
fi
echo ""

echo -e "${YELLOW}[TESTE 3/7] CORS está liberando o domínio do Vercel?${NC}"
CORS_HEADERS=$(curl -s -I -X OPTIONS \
 -H "Origin: $FRONTEND_URL" \
 -H "Access-Control-Request-Method: POST" \
 --max-time 5 \
 "$BACKEND_LOCAL/api/chat" 2>/dev/null)

if echo "$CORS_HEADERS" | grep -qi "access-control-allow-origin"; then
 ALLOWED=$(echo "$CORS_HEADERS" | grep -i "access-control-allow-origin" | head -1)
 echo -e "${GREEN}✓ OK — Backend retorna header CORS:${NC}"
 echo " $ALLOWED"
else
 echo -e "${RED}✗ FALHA — Backend NÃO está retornando header CORS!${NC}"
 echo " Isso é a causa MUITO PROVÁVEL do 'Failed to fetch'."
fi
echo ""

echo -e "${YELLOW}[TESTE 4/7] OpenRouter está acessível e respondendo?${NC}"
if [ -f ".env" ]; then
 OR_KEY=$(grep "^OPENROUTER_API_KEY=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
 if [ -z "$OR_KEY" ]; then
 echo -e "${RED}✗ FALHA — OPENROUTER_API_KEY não está no .env${NC}"
 else
 OR_TEST=$(curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
 -H "Authorization: Bearer $OR_KEY" \
 -H "Content-Type: application/json" \
 -d '{"model":"meta-llama/llama-3.3-70b-instruct:free","messages":[{"role":"user","content":"oi"}]}' \
 --max-time 15)
 if echo "$OR_TEST" | grep -q '"content"'; then
 echo -e "${GREEN}✓ OK — OpenRouter respondendo com modelo grátis${NC}"
 else
 echo -e "${RED}✗ FALHA — OpenRouter não respondeu corretamente:${NC}"
 echo "$OR_TEST" | head -3
 fi
 fi
fi
echo ""

echo -e "${YELLOW}[TESTE 5/7] Chat completo (backend local → LLM)?${NC}"
CHAT_RESP=$(curl -s -X POST "$BACKEND_LOCAL/api/chat" \
 -H "Content-Type: application/json" \
 -d '{"message":"diga apenas: ok","compress":false}' \
 --max-time 30)

if echo "$CHAT_RESP" | grep -q '"content"'; then
 MODEL=$(echo "$CHAT_RESP" | grep -o '"model_id":"[^"]*"' | cut -d'"' -f4)
 echo -e "${GREEN}✓ OK — Chat funcionou usando modelo: $MODEL${NC}"
elif echo "$CHAT_RESP" | grep -q '"detail"'; then
 ERROR=$(echo "$CHAT_RESP" | grep -o '"detail":"[^"]*"' | head -1)
 echo -e "${RED}✗ FALHA — Chat retornou erro:${NC}"
 echo " $ERROR"
else
 echo -e "${RED}✗ FALHA — Resposta inesperada:${NC}"
 echo "$CHAT_RESP" | head -5
fi
echo ""

echo -e "${YELLOW}[TESTE 6/7] Porta 8000 acessível de fora?${NC}"
EXT_RESP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://$SERVER_IP:8000/api/status")
if [ "$EXT_RESP" = "200" ]; then
 echo -e "${GREEN}✓ OK — Porta 8000 acessível externamente${NC}"
else
 echo -e "${RED}✗ FALHA — Porta 8000 NÃO acessível de fora (HTTP $EXT_RESP)${NC}"
fi
echo ""

echo -e "${YELLOW}[TESTE 7/7] Porta 3000 acessível?${NC}"
PORT3K=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:3000" 2>/dev/null)
if [ "$PORT3K" = "200" ] || [ "$PORT3K" = "302" ]; then
 echo -e "${GREEN}✓ OK — Porta 3000 respondendo${NC}"
else
 echo -e "${YELLOW}⚠ Porta 3000 não está em uso (frontend não rodando localmente)${NC}"
fi
echo ""

echo -e "${BLUE}=================================================="
echo " RESUMO DO DIAGNÓSTICO"
echo "==================================================${NC}"
