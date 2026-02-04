#!/bin/bash
# Quick test script for Opportunities API

echo "🧪 Testing CSOKi Opportunities API"
echo "===================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backend URL (change if needed)
API_URL="${API_URL:-http://localhost:8000}"

echo "📍 Using API URL: $API_URL"
echo ""

# Test 1: Health check
echo "${YELLOW}Test 1: API Health Check${NC}"
if curl -s "${API_URL}/health" > /dev/null 2>&1; then
    echo "${GREEN}✅ API is responding${NC}"
else
    echo "${RED}❌ API is not responding${NC}"
    echo "   Make sure backend is running: cd backend && uvicorn app.main:app --reload"
    exit 1
fi
echo ""

# Test 2: Check ATTOM key configuration
echo "${YELLOW}Test 2: ATTOM API Key Check${NC}"
ATTOM_STATUS=$(curl -s "${API_URL}/api/v1/analysis/check-attom-key/" | python3 -m json.tool 2>/dev/null)
if echo "$ATTOM_STATUS" | grep -q '"configured": true'; then
    echo "${GREEN}✅ ATTOM API key is configured${NC}"
else
    echo "${RED}❌ ATTOM API key is NOT configured${NC}"
    echo "   Set ATTOM_API_KEY in backend/.env"
    exit 1
fi
echo ""

# Test 3: Opportunities stats endpoint
echo "${YELLOW}Test 3: Opportunities Stats Endpoint${NC}"
STATS=$(curl -s "${API_URL}/api/v1/opportunities/stats" 2>/dev/null)
if echo "$STATS" | grep -q "priority_order"; then
    echo "${GREEN}✅ Stats endpoint working${NC}"
    echo "   Priority signals configured:"
    echo "$STATS" | python3 -m json.tool | grep -A2 '"signal":' | grep '"signal"' | head -6
else
    echo "${RED}❌ Stats endpoint failed${NC}"
    echo "   Response: $STATS"
fi
echo ""

# Test 4: Opportunities search endpoint (Iowa test area)
echo "${YELLOW}Test 4: Opportunities Search (Iowa test area)${NC}"
echo "   Searching 41.0-42.0 lat, -96.5 to -95.5 lng..."

SEARCH_RESULT=$(curl -s -X POST "${API_URL}/api/v1/opportunities/search" \
  -H "Content-Type: application/json" \
  -d '{
    "min_lat": 41.0,
    "max_lat": 42.0,
    "min_lng": -96.5,
    "max_lng": -95.5,
    "min_parcel_acres": 0.8,
    "max_parcel_acres": 2.0,
    "limit": 10
  }' 2>/dev/null)

if echo "$SEARCH_RESULT" | grep -q "opportunities"; then
    TOTAL=$(echo "$SEARCH_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_found', 0))" 2>/dev/null)
    echo "${GREEN}✅ Search endpoint working${NC}"
    echo "   Found: $TOTAL opportunities"
    
    # Show top 3 ranked properties
    echo ""
    echo "   Top 3 Opportunities:"
    echo "$SEARCH_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for opp in data.get('opportunities', [])[:3]:
    prop = opp['property']
    print(f\"   #{opp['rank']}: {prop['address']}, {prop['city']}, {prop['state']}\")
    print(f\"        Signals: {opp['signal_count']} | Priority: {', '.join(opp['priority_signals'][:2])}\")
" 2>/dev/null
else
    echo "${RED}❌ Search endpoint failed${NC}"
    echo "   Response: ${SEARCH_RESULT:0:200}..."
fi
echo ""

echo "===================================="
echo "${GREEN}✅ All tests completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Start frontend: cd frontend && npm run dev"
echo "2. Open http://localhost:5173"
echo "3. Toggle 'CSOKi Opportunities' layer in sidebar"
echo "4. Look for purple diamond markers with rank numbers"
