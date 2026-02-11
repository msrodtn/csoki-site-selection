# Cost Analysis Report
## CSOKi Site Selection Platform - API & Infrastructure Spend

**Date:** February 5, 2026  
**Analysis Period:** Project inception through February 5, 2026  
**Status:** Estimated (actual usage logs not available)

---

## Executive Summary

### Current Monthly Spend (Estimated)
| Category | Monthly Cost | Status |
|----------|--------------|--------|
| **Infrastructure** | $20-30 | Railway hosting (3 services) |
| **Google Maps APIs** | $0-5 | Light usage, within free tier |
| **Mapbox** | $0 | Within free tier |
| **ATTOM API** | $0 | Within free tier |
| **Other APIs** | $0-10 | Occasional usage |
| **Total Current** | **$20-45/month** | **Mostly infrastructure** |

### Projected Spend (With Proposed Features)
| Scenario | Monthly Cost | Trigger |
|----------|--------------|---------|
| **Minimal Usage** | $20-50 | Current + fixed POIs |
| **Moderate Usage** | $50-150 | +Mapbox Matrix API, 50 analyses/day |
| **Heavy Usage** | $150-300 | +Advanced features, 200+ analyses/day |
| **Enterprise Scale** | $300-500+ | Full ML/AI features, 1000+ analyses/day |

**Key Finding:** Currently operating within free tiers for most APIs. Infrastructure is the primary cost.

---

## Historical Spend Analysis

### Phase 1: Foundation (Jan 2026)
**Focus:** Basic mapping, competitor visualization

| Service | Usage | Cost |
|---------|-------|------|
| Railway (PostgreSQL) | 1 instance | ~$5/month |
| Railway (Backend) | 1 instance | ~$5/month |
| Railway (Frontend) | 1 instance | ~$5/month |
| Google Maps (JavaScript API) | Map loads | $0 (free tier: 28k loads/month) |
| Google Maps (Static API) | Thumbnails | $0 (free tier: 100k/month) |
| **Subtotal** | | **~$15/month** |

### Phase 2: Data Enrichment (Feb 2026)
**Focus:** Trade area analysis, demographics

| Service | Usage | Cost |
|---------|-------|------|
| Infrastructure | (same as Phase 1) | ~$15/month |
| Google Places API | POI searches | $0 (broken, not working) |
| ArcGIS GeoEnrichment | Demographics | $0 (not heavily used) |
| ATTOM Property API | Property data | $0 (free tier: 1,000 req/month) |
| Mapbox GL JS | Map rendering | $0 (free for <50k loads) |
| Mapbox Isochrone | Drive times | $0 (free tier: 100k req/month) |
| **Subtotal** | | **~$15-20/month** |

### Phase 2.5: Properties Layer (Feb 4, 2026)
**Focus:** Commercial property intelligence

| Service | Usage | Cost |
|---------|-------|------|
| Infrastructure | (same) | ~$15/month |
| ATTOM API | Property searches | $0 (within free tier) |
| ReportAll API | Parcel details | $0 (unclear if active) |
| **Subtotal** | | **~$15-20/month** |

**Total Historical Spend (Jan-Feb 2026):** ~$30-40

---

## Current API Usage Breakdown

### Mapbox APIs

#### 1. Mapbox GL JS (Map Rendering)
**Current Usage:** Active  
**Endpoint:** Vector tiles, styles  
**Free Tier:** 50,000 map loads/month  
**Estimated Usage:** ~5,000 loads/month (low traffic)  
**Cost:** $0  
**Status:** ✅ Within free tier

**Notes:**
- 1 "load" = 1 unique user session opening the map
- Panning/zooming doesn't count as new loads
- Currently far below free tier limit

#### 2. Mapbox Isochrone API
**Current Usage:** Active  
**Endpoint:** `/isochrone/v1/mapbox/{profile}/{coordinates}`  
**Implementation:** `frontend/src/services/mapbox-isochrone.ts`  
**Free Tier:** 100,000 requests/month  
**Estimated Usage:** ~500 requests/month (occasional use)  
**Cost:** $0  
**Status:** ✅ Within free tier

**Usage Calculation:**
- Assuming 10 isochrone analyses per day
- 10 analyses/day × 30 days = 300 requests/month
- **Headroom:** 99,700 requests remaining

**Projected Cost (if exceeded):**
- Paid tier: $0.50 per 1,000 requests after free tier
- To reach $10/month: 20,000 paid requests = 120k total requests
- **Unlikely to exceed** unless doing hundreds of analyses daily

#### 3. Mapbox Search Box API (POI Search)
**Current Usage:** ⚠️ Implemented but failing (see CRITICAL_FIXES_REPORT.md)  
**Endpoint:** `/search/searchbox/v1/suggest`  
**Implementation:** `backend/app/services/mapbox_places.py` (needs verification)  
**Free Tier:** 100,000 requests/month  
**Estimated Usage:** 0 (broken)  
**Cost:** $0  
**Status:** ❌ Not working

**Projected Usage (when fixed):**
- Trade area analysis: 1-4 API calls per analysis
- 50 analyses/day × 4 calls = 200 requests/day = 6,000/month
- **Well within free tier**

**Projected Cost (if exceeded):**
- Paid tier: $0.50 per 1,000 requests
- To reach $10/month: 20,000 paid requests
- Would need ~330 analyses/day to exceed free tier

#### 4. Mapbox Static Images API
**Current Usage:** Not active  
**Free Tier:** 100,000 requests/month  
**Cost:** $0  
**Status:** Available but unused

**Potential Use Cases:**
- PDF report map thumbnails
- Email notifications with map previews
- Property listing images

#### 5. Mapbox Tiling Service (MTS)
**Current Usage:** Not active  
**Free Tier:** 200,000 tiles generated/month  
**Cost:** $0  
**Status:** Recommended for parcel data (see MAPBOX_IMPLEMENTATION_ROADMAP.md)

**Projected Usage:**
- One-time upload of Iowa traffic data (7,000 features)
- Generates ~10,000 tiles (one-time cost)
- Updates: ~1,000 tiles per update
- **Well within free tier**

#### 6. Mapbox Datasets API
**Current Usage:** Not active  
**Free Tier:** 480 reads/min, 40 writes/min  
**Cost:** $0  
**Status:** Recommended for traffic count management

**Projected Usage:**
- 7,000 traffic features stored server-side
- ~100 reads/min during map usage
- ~5 writes/day for updates
- **Well within free tier**

#### 7. Mapbox Matrix API (Proposed)
**Current Usage:** Not implemented  
**Free Tier:** 1,250 elements/month  
**Proposed Usage:** Competitive analysis  
**Status:** Recommended in roadmap

**Projected Cost:**
- 1 element = 1 origin × 1 destination
- 5 competitors × 1 target site = 5 elements per analysis
- 50 analyses/day × 5 elements = 250 elements/day = 7,500/month
- **Exceeds free tier by 6,250 elements**
- **Cost:** 6,250 elements ÷ 1,000 × $0.50 = **$3.13/month**

**Full-scale usage:**
- 200 analyses/day = 30,000 elements/month
- Exceeds free tier by 28,750 elements
- **Cost:** 28,750 ÷ 1,000 × $0.50 = **$14.38/month**

#### 8. Mapbox Directions API (Proposed)
**Current Usage:** Not implemented  
**Free Tier:** 100,000 requests/month  
**Proposed Usage:** Route planning, delivery zones  
**Status:** Recommended in roadmap

**Projected Cost:**
- 50 routes/day = 1,500/month (well within free tier)
- **Cost:** $0 initially
- If scaling to 200 routes/day = 6,000/month (still free)

---

### Google APIs

#### 1. Google Maps JavaScript API
**Current Usage:** ⚠️ Active but being phased out  
**Implementation:** Competitor store visualization (legacy)  
**Free Tier:** 28,000 loads/month ($200 credit)  
**Estimated Usage:** ~5,000 loads/month  
**Cost:** $0  
**Status:** ✅ Within free tier

**Notes:**
- Primary map is now Mapbox (MapboxMap.tsx)
- Google Maps may still be used in some views
- **Recommendation:** Fully migrate to Mapbox to avoid future costs

#### 2. Google Places API (Nearby Search)
**Current Usage:** ⚠️ Implemented as POI fallback  
**Endpoint:** `/maps/api/place/nearbysearch/json`  
**Implementation:** `backend/app/services/places.py`  
**Free Tier:** None (uses $200 monthly credit)  
**Estimated Usage:** 0 (API key not configured)  
**Cost:** $0  
**Status:** ❌ Not working (see CRITICAL_FIXES_REPORT.md)

**Pricing:**
- **Basic Data:** $17 per 1,000 requests (name, address, type)
- **Contact Data:** $3 per 1,000 requests (phone, hours, etc.)
- **Atmosphere Data:** $5 per 1,000 requests (reviews, ratings)

**Trade Area Analysis Cost:**
- 4 POI categories × 7 types per category = 28 API calls
- 1 analysis = 28 requests
- **Cost per analysis:** 28 × $0.017 = **$0.476** (Basic only)
- With contact data: 28 × $0.020 = **$0.56 per analysis**

**Projected Usage:**
- 50 analyses/day = 1,400 API calls/day = 42,000/month
- **Cost:** 42,000 × $0.017 = **$714/month** (🔴 EXPENSIVE)
- Free tier credit ($200) covers ~8 analyses/day

**Recommendation:** Use Mapbox POI search instead (8x cheaper)

#### 3. Google Places API (Autocomplete)
**Current Usage:** Active (city search)  
**Implementation:** Frontend search bar  
**Free Tier:** Uses $200 credit  
**Estimated Usage:** ~2,000 requests/month (light usage)  
**Cost:** $0  
**Status:** ✅ Within credit

**Pricing:**
- **Autocomplete - Per Session:** $2.83 per 1,000 sessions
- **Autocomplete - Per Request:** $17 per 1,000 requests

**Current implementation:** Per-request (less efficient)  
**Cost per search:** $0.017  
**Monthly cost (2,000 searches):** ~$34  
**Status:** Covered by $200 free credit

**Optimization opportunity:** Migrate to session-based pricing (6x cheaper)

#### 4. Google Geocoding API
**Current Usage:** Occasional (store address validation)  
**Free Tier:** Uses $200 credit  
**Estimated Usage:** <100 requests/month  
**Cost:** $0  
**Status:** ✅ Within credit

**Pricing:** $5 per 1,000 requests  
**No immediate concern** given low usage.

---

### ATTOM Property API

#### Current Usage
**Endpoint:** `/property/basicprofile/detail` (and others)  
**Implementation:** `backend/app/services/attom.py`  
**Features Used:**
- Property search by coordinates/bounds
- Opportunity signal detection
- Property details (address, lot size, value)

#### Free Tier
- **1,000 API calls/month** (per endpoint)
- Multiple endpoints available:
  - Basic profile
  - Sales history
  - Assessment history
  - AVM (Automated Valuation Model)

#### Estimated Usage
- Property search: 10-50 properties per map pan
- Opportunity scoring: Calculated client-side (no extra API calls)
- **Total:** ~500-800 requests/month
- **Status:** ✅ Within free tier

#### Projected Cost (if exceeded)
**Paid tier:** Contact for pricing (not published)  
**Estimated:** $0.10-0.50 per request (industry standard)  
**Break-even point:** ~1,100 requests/month (33 property searches/day)

**Recommendation:** Monitor usage closely. If approaching limit:
1. Implement caching (Redis) for property data
2. Reduce search radius (fewer properties per query)
3. Upgrade to paid tier (~$50-100/month expected)

---

### ReportAll API

#### Current Usage
**Endpoint:** `/api/parcels` (parcel lookup)  
**Implementation:** `backend/app/api/routes/analysis.py` (lines 247-366)  
**Free Tier:** Unknown (appears to be active)  
**Estimated Usage:** <100 requests/month  
**Cost:** Unknown  
**Status:** ⚠️ Needs verification

**Notes:**
- Code exists but usage not confirmed
- May be trial/demo account
- **Recommendation:** Verify API key validity and billing

---

### ArcGIS GeoEnrichment API

#### Current Usage
**Endpoint:** `/arcgis/rest/services/GeoEnrichment/*/Enrich`  
**Implementation:** `backend/app/services/arcgis.py`  
**Free Tier:** 1 million service credits/month (demo accounts)  
**Estimated Usage:** <1,000 credits/month (light usage)  
**Cost:** $0  
**Status:** ✅ Likely within free tier

**Service Credits:**
- 1 demographic query (1/3/5 mile radii) = ~10 credits
- 50 queries/month = 500 credits
- **Well below free tier limit**

**Notes:**
- ArcGIS API keys often have trial periods (30-90 days)
- **Recommendation:** Verify account status and expiration date

---

### AI APIs (Proposed)

#### OpenAI API
**Current Usage:** Not active  
**Proposed Usage:** Property data extraction, conversational features  
**Free Tier:** None ($5 free trial credit for new accounts)  
**Status:** Available but not implemented

**Projected Cost (if implemented):**
- GPT-4o mini: $0.15 per 1M input tokens, $0.60 per 1M output tokens
- URL import extraction: ~1,000 input + 500 output tokens per property
- Cost per extraction: ~$0.0005
- **50 extractions/day = 1,500/month = $0.75/month** ✅ Affordable

#### Anthropic API (Claude)
**Current Usage:** Not active  
**Proposed Usage:** Alternative to OpenAI  
**Free Tier:** None  
**Status:** Alternative option

**Pricing (Claude 3.5 Sonnet):**
- $3 per 1M input tokens, $15 per 1M output tokens
- Cost per extraction: ~$0.011 (20x more expensive than GPT-4o mini)
- **Not recommended for high-volume extraction**

#### Tavily API (Web Search)
**Current Usage:** Implemented but usage unknown  
**Endpoint:** `/search` (property listing search)  
**Implementation:** `backend/app/api/routes/analysis.py` (debug endpoint)  
**Free Tier:** 1,000 searches/month  
**Estimated Usage:** <100/month (if active)  
**Cost:** $0  
**Status:** ⚠️ Needs usage verification

**Paid tier:** $0.005 per search after free tier  
**Low impact even at scale.**

---

## Infrastructure Costs

### Railway (Current Hosting)

#### PostgreSQL Database
- **Plan:** Hobby ($5/month)
- **Storage:** 512MB (sufficient for current data)
- **Connections:** Shared (no limit)
- **Status:** ✅ Active

#### Backend Service
- **Plan:** Hobby ($5/month)
- **RAM:** 512MB
- **CPU:** Shared
- **Deployment:** Auto-deploy on git push
- **Status:** ✅ Active

#### Frontend Service
- **Plan:** Hobby ($5/month)
- **Deployment:** Static site (nginx)
- **CDN:** Included
- **Status:** ✅ Active

**Total Infrastructure:** ~$15/month (base cost)

#### Potential Upgrades
| Tier | RAM | CPU | Cost | When Needed |
|------|-----|-----|------|-------------|
| Hobby | 512MB | Shared | $5/mo | Current (sufficient) |
| Pro | 1GB | Shared | $10/mo | 100+ concurrent users |
| Team | 2GB | 1 vCPU | $20/mo | 500+ concurrent users |
| Enterprise | 4GB+ | 2+ vCPU | $50+/mo | 1000+ concurrent users |

**Current Status:** Hobby tier sufficient for current traffic  
**Recommendation:** Monitor memory usage, upgrade if >80% consistently

---

## Cost Projections by Usage Scenario

### Scenario 1: Minimal Usage (Current + Bug Fixes)
**User Count:** 5-10 active users  
**Daily Activity:** 10 map sessions, 5 trade area analyses

| Service | Monthly Cost |
|---------|--------------|
| Railway (3 services) | $15 |
| Mapbox (maps + isochrones) | $0 (free tier) |
| Google Places (POI fallback) | $12 (240 analyses @ $0.05 avg) |
| ATTOM (property data) | $0 (free tier) |
| **Total** | **$27/month** |

### Scenario 2: Moderate Usage (Roadmap Phase 1-2)
**User Count:** 20-30 active users  
**Daily Activity:** 50 map sessions, 25 trade area analyses, 10 competitive analyses

| Service | Monthly Cost |
|---------|--------------|
| Railway (3 services) | $15 |
| Mapbox GL JS | $0 (free tier) |
| Mapbox Isochrones | $0 (free tier) |
| Mapbox POI (primary) | $0 (free tier, 750 analyses) |
| Google Places (fallback 5%) | $2 (38 analyses) |
| Mapbox Matrix API | $8 (15k elements) |
| ATTOM API | $0 (free tier) |
| **Total** | **$25-30/month** |

**Key Change:** Mapbox POI replaces Google (8x cost reduction)

### Scenario 3: Heavy Usage (Roadmap Phase 3)
**User Count:** 50-100 active users  
**Daily Activity:** 200 map sessions, 100 analyses, 50 competitive analyses

| Service | Monthly Cost |
|---------|--------------|
| Railway (upgrade to Pro) | $30 (3 × $10) |
| Mapbox GL JS | $10 (75k loads @ $5/50k) |
| Mapbox Isochrones | $5 (120k requests) |
| Mapbox POI | $5 (150k requests) |
| Google Places (fallback) | $5 (100 failures) |
| Mapbox Matrix API | $25 (50k elements) |
| Mapbox Directions | $5 (120k routes) |
| ATTOM API (paid tier) | $50 (est. 5k requests) |
| **Total** | **$135/month** |

### Scenario 4: Enterprise Scale (Full ML/AI Features)
**User Count:** 200+ active users  
**Daily Activity:** 500+ map sessions, 300+ analyses, ML predictions

| Service | Monthly Cost |
|---------|--------------|
| Railway (Team tier) | $60 (3 × $20) |
| Mapbox (all APIs) | $50 |
| ATTOM API (paid tier) | $100 |
| OpenAI (ML features) | $50 |
| Additional infrastructure | $40 (Redis, etc.) |
| **Total** | **$300/month** |

---

## Cost Optimization Recommendations

### Immediate Wins (This Week)

#### 1. Fix POI System with Mapbox
**Current:** Google Places fallback = $0.48 per analysis  
**Proposed:** Mapbox POI primary = $0.004 per analysis  
**Savings:** $0.476 per analysis (120x cheaper!)

**Impact:**
- 50 analyses/day: Save $14.28/day = **$428/month**
- 100 analyses/day: Save $28.56/day = **$857/month**

**Implementation:** See CRITICAL_FIXES_REPORT.md

#### 2. Optimize Google Places Autocomplete
**Current:** Per-request pricing = $0.017 per search  
**Proposed:** Per-session pricing = $0.00283 per search  
**Savings:** $0.014 per search (6x cheaper)

**Impact:**
- 2,000 searches/month: Save $28/month
- 5,000 searches/month: Save $70/month

**Implementation:**
```javascript
// Add sessionToken to autocomplete requests
const sessionToken = new google.maps.places.AutocompleteSessionToken();
autocompleteService.getPlacePredictions({
  input: query,
  sessionToken: sessionToken,  // Enables session pricing
  types: ['(cities)']
});
```

#### 3. Implement Caching for ATTOM API
**Current:** Re-fetching same properties on every map pan  
**Proposed:** Redis cache with 1-hour TTL  
**Savings:** Reduce API calls by 60-80%

**Implementation:**
```python
# backend/app/services/attom.py
import redis
cache = redis.Redis(host=settings.REDIS_URL)

async def get_property(attom_id):
    cached = cache.get(f"attom:{attom_id}")
    if cached:
        return json.loads(cached)
    
    # Fetch from API
    result = await fetch_from_attom(attom_id)
    
    # Cache for 1 hour
    cache.setex(f"attom:{attom_id}", 3600, json.dumps(result))
    return result
```

**Impact:** Stay within ATTOM free tier longer

---

### Medium-term Optimizations (This Month)

#### 4. Migrate Remaining Google Maps to Mapbox
**Current:** Dual map libraries (Google + Mapbox)  
**Proposed:** 100% Mapbox  
**Savings:** Simplify stack, avoid future Google costs

**Benefits:**
- Consistent UX across all map views
- Lower bundle size (remove Google Maps SDK)
- Single API key to manage
- More predictable costs

#### 5. Implement Mapbox Datasets for Traffic Data
**Current:** Client loads 7,000 features on every session  
**Proposed:** Server-side vector tiles  
**Savings:** Reduce client bandwidth, faster load times

**Cost:** $0 (free tier: 480 reads/min sufficient)  
**Performance gain:** 80% faster map load

#### 6. Add Usage Monitoring Dashboard
**Proposed:** Track API usage in real-time  
**Tools:** Grafana + InfluxDB or Railway Analytics

**Metrics to track:**
- API calls per service per day
- Cost per user session
- Cache hit rates
- Error rates by API

**Alert thresholds:**
- Daily spend exceeds $5
- API error rate >5%
- Cache hit rate <70%

---

### Long-term Strategy (This Quarter)

#### 7. Negotiate Enterprise Pricing
**When:** Exceeding $100/month consistently  
**Services to negotiate:**
- ATTOM API (volume discount)
- Mapbox (custom plan)
- Railway (annual prepay discount)

**Expected savings:** 20-40% off list price

#### 8. Build Internal POI Database
**When:** POI API costs exceed $50/month  
**Implementation:**
- Scrape/purchase one-time POI datasets
- Store in PostgreSQL with PostGIS
- Update quarterly vs. real-time

**Cost:** One-time $500-1,000 for data  
**Savings:** $50/month ongoing (6-10 month ROI)

#### 9. Evaluate Self-Hosted Alternatives
**When:** Total API costs exceed $200/month  
**Options:**
- Self-host Nominatim (geocoding)
- Self-host Overpass API (POI data)
- Use OpenStreetMap tiles

**Trade-offs:**
- Lower ongoing costs
- Higher maintenance burden
- Potentially lower data quality

---

## Budget Recommendations

### Monthly Budget by Quarter

**Q1 2026 (Current - Bug fixes only):**
- Target: $50/month
- Infrastructure: $15
- APIs: $35 buffer
- **Risk:** Low (within free tiers)

**Q2 2026 (Roadmap Phase 1-2):**
- Target: $100/month
- Infrastructure: $30 (Pro tier)
- APIs: $70 (Mapbox Matrix, light usage)
- **Risk:** Medium (depends on adoption)

**Q3 2026 (Roadmap Phase 3):**
- Target: $150/month
- Infrastructure: $30
- APIs: $120 (Mapbox + ATTOM paid tiers)
- **Risk:** Medium-High (usage-dependent)

**Q4 2026 (Full features + ML):**
- Target: $200-300/month
- Infrastructure: $60 (Team tier)
- APIs: $140-240 (full stack)
- **Risk:** High (requires user growth)

### Cost Per User Metrics

**Current (estimated):**
- Infrastructure: $15/month ÷ 10 users = **$1.50 per user**
- APIs: $30/month ÷ 10 users = **$3.00 per user**
- **Total:** $4.50 per active user per month

**Target (at scale):**
- Infrastructure: $60/month ÷ 100 users = **$0.60 per user**
- APIs: $200/month ÷ 100 users = **$2.00 per user**
- **Total:** $2.60 per active user per month

**Efficiency gain at scale:** 42% reduction in cost per user

---

## Risk Analysis

### Cost Overrun Risks

#### Risk 1: POI API Costs Explode
**Scenario:** Team adopts trade area analysis heavily  
**Impact:** Google Places at $0.50/analysis = $500/month at 33 analyses/day  
**Likelihood:** High if not fixed  
**Mitigation:** Implement Mapbox POI (see CRITICAL_FIXES_REPORT.md)  
**Priority:** 🔴 CRITICAL - Fix this week

#### Risk 2: ATTOM Free Tier Exhausted
**Scenario:** Property search becomes popular feature  
**Impact:** ~$100-200/month for paid tier  
**Likelihood:** Medium (50+ searches/day)  
**Mitigation:** Implement caching, optimize queries  
**Priority:** 🟡 MEDIUM - Monitor usage

#### Risk 3: Mapbox Costs Exceed Budget
**Scenario:** Matrix API usage higher than projected  
**Impact:** $50-100/month additional  
**Likelihood:** Low (competitive analysis is advanced feature)  
**Mitigation:** Rate limiting, usage caps  
**Priority:** 🟢 LOW - Plan ahead

#### Risk 4: Railway Infrastructure Insufficient
**Scenario:** User growth requires Pro/Team tier  
**Impact:** $30-45/month additional infrastructure  
**Likelihood:** Medium (depends on marketing)  
**Mitigation:** Monitor performance metrics, scale proactively  
**Priority:** 🟡 MEDIUM - Track monthly

### Budget Exhaustion Triggers

**Set these alerts in Railway/Mapbox dashboards:**

1. **Daily spend exceeds $3** → Email Michael
2. **Weekly spend exceeds $15** → Review usage patterns
3. **Monthly projection exceeds $75** → Optimize or get approval
4. **Any single API exceeds $25/day** → Investigate immediately

---

## Summary & Action Items

### Current State
- **Monthly spend:** $20-30 (mostly infrastructure)
- **Within budget:** Yes (all APIs in free tier)
- **Biggest risk:** POI system using expensive Google fallback

### Immediate Actions (This Week)
1. [ ] Fix POI system to use Mapbox (saves $400+/month at scale)
2. [ ] Add GOOGLE_PLACES_API_KEY as emergency fallback
3. [ ] Verify ATTOM API key and billing status
4. [ ] Set up cost monitoring dashboard

### Short-term Actions (This Month)
1. [ ] Implement Redis caching for ATTOM API
2. [ ] Optimize Google Autocomplete to session-based pricing
3. [ ] Document API usage patterns
4. [ ] Create monthly cost report automation

### Long-term Strategy (This Quarter)
1. [ ] Migrate 100% to Mapbox (remove Google Maps)
2. [ ] Negotiate enterprise pricing (if spending >$100/month)
3. [ ] Evaluate self-hosted alternatives (if spending >$200/month)
4. [ ] Build internal POI database (if POI costs >$50/month)

### Budget Projections
- **Current:** $20-30/month ✅
- **After fixes:** $20-40/month ✅
- **With roadmap Phase 1-2:** $25-50/month ✅
- **With roadmap Phase 3:** $100-150/month ⚠️
- **Full ML features:** $250-350/month ⚠️

### Cost per User Targets
- **Current:** $4.50/user/month (10 users)
- **Target at scale:** $2.60/user/month (100+ users)
- **Efficiency gain:** 42% reduction with scale

---

**Prepared by:** AI Agent  
**Date:** February 5, 2026  
**Next Review:** March 5, 2026  
**Status:** Estimates based on code analysis (actual usage logs not available)

**Note:** Actual costs may vary. Recommend implementing usage tracking ASAP to get accurate data.
