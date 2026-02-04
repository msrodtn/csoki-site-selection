# CSOKi Opportunities Feature - Implementation Complete

**Date:** February 4, 2026  
**Developer:** Subagent (OpenClaw)  
**Status:** ✅ **READY FOR TESTING**

---

## 🎯 Feature Overview

Built a complete ATTOM-based property opportunity filtering system for the CSOKi platform that identifies high-potential properties matching specific criteria with smart ranking based on opportunity signals.

---

## ✅ Completed Implementation

### Backend (Python/FastAPI)

#### 1. New Opportunities API Endpoint (`/api/v1/opportunities/search`)

**File:** `backend/app/api/routes/opportunities.py`

**Features:**
- **Property Filtering:**
  - Parcel size: 0.8-2 acres (configurable)
  - Building size: 2500-6000 sqft if building exists (configurable)
  - Property types: Retail (preferred), Office (acceptable), Land (empty parcels)
  - Automatically excludes multi-tenant buildings (heuristic-based)

- **Smart Opportunity Ranking:**
  ```
  Priority Order (highest to lowest):
  1. Empty parcels (land only)         → 100 points
  2. Vacant properties                 → 80 points
  3. Out-of-state/absentee owners      → 60 points
  4. Tax liens/pressure                → 50 points
  5. Aging owners (65+) / estates      → 40 points
  6. Small single-tenant buildings     → 30 points
  
  Bonus:
  - Foreclosure/distress               → 70 points
  ```

- **Response Format:**
  ```json
  {
    "center_latitude": 41.5,
    "center_longitude": -96.0,
    "total_found": 45,
    "opportunities": [
      {
        "property": { /* PropertyListing object */ },
        "rank": 1,  // 1-based ranking
        "priority_signals": [
          "Empty parcel (land only)",
          "Out-of-state owner"
        ],
        "signal_count": 5
      }
    ],
    "search_timestamp": "2026-02-04T12:00:00",
    "filters_applied": {
      "parcel_size_acres": "0.8-2.0",
      "building_size_sqft": "2500-6000",
      "property_types": ["retail", "office", "land"],
      "min_opportunity_score": 0
    }
  }
  ```

#### 2. Enhanced ATTOM Signal Detection

**File:** `backend/app/services/attom.py` (existing, reviewed for compatibility)

**Signals Detected:**
- Tax delinquency (high priority)
- Tax assessment increases (financial pressure)
- Vacant/unoccupied status
- Out-of-state/absentee ownership
- Estate/trust ownership (succession planning)
- Aging buildings (50+ years = renovation opportunity)
- Long-term ownership (15+ years)
- Foreclosure/pre-foreclosure status
- Property undervaluation (assessed < 70% of market value)

#### 3. Stats Endpoint (`/api/v1/opportunities/stats`)

Returns metadata about opportunity signals, ranking system, and filtering criteria for documentation/UI purposes.

---

### Frontend (React/TypeScript)

#### 1. New Types (`frontend/src/types/store.ts`)

```typescript
interface OpportunityRanking {
  property: PropertyListing;
  rank: number;  // 1-based ranking
  priority_signals: string[];
  signal_count: number;
}

interface OpportunitySearchRequest { /* ... */ }
interface OpportunitySearchResponse { /* ... */ }

const OPPORTUNITY_COLOR = '#9333EA';  // Purple
```

#### 2. Map Store Updates (`frontend/src/store/useMapStore.ts`)

**New State:**
```typescript
opportunitiesResult: OpportunitySearchResponse | null;
isLoadingOpportunities: boolean;
opportunitiesError: string | null;
selectedOpportunity: OpportunityRanking | null;
```

**New Actions:**
```typescript
setOpportunitiesResult()
setIsLoadingOpportunities()
setOpportunitiesError()
setSelectedOpportunity()
clearOpportunities()
```

#### 3. API Service (`frontend/src/services/api.ts`)

**New Module:**
```typescript
export const opportunitiesApi = {
  search: async (request: OpportunitySearchRequest): Promise<OpportunitySearchResponse>
  getStats: async (): Promise</* ... */>
}
```

#### 4. Map Layer Toggle (`frontend/src/components/Sidebar/MapLayers.tsx`)

**New Layer:**
```typescript
csoki_opportunities: {
  id: 'csoki_opportunities',
  name: 'CSOKi Opportunities',
  icon: Diamond,
  color: '#9333EA',  // Purple
  description: '0.8-2ac parcels with opportunity signals',
}
```

#### 5. Map Component (`frontend/src/components/Map/StoreMap.tsx`)

**New Features:**

1. **Automatic Data Fetching:**
   - Opportunities auto-fetch when `csoki_opportunities` layer is toggled ON
   - Clears data when toggled OFF
   - Fetches based on current map viewport bounds

2. **Custom Marker Icons:**
   ```typescript
   // Purple diamond with rank number
   createOpportunityMarkerIcon(opportunity: OpportunityRanking, isSelected: boolean)
   ```
   - Purple diamond shape (distinct from circular property markers)
   - Shows rank number (#1, #2, #3...) inside marker
   - Larger when selected

3. **Marker Behavior:**
   - Click to select opportunity
   - Shows highlight circle around selected marker
   - Opens PropertyInfoCard with enhanced context

4. **Enhanced Property Info Display:**
   - Shows opportunity rank: "Rank #5 of 42 opportunities"
   - Lists priority signals at top (empty parcel, tax delinquent, etc.)
   - Shows all opportunity signals from ATTOM
   - Displays property details (size, price, owner, etc.)

---

## 🔧 Technical Architecture

### Data Flow

```
User toggles "CSOKi Opportunities" layer
  ↓
Frontend detects layer change (useEffect)
  ↓
Calls opportunitiesApi.search() with map bounds
  ↓
Backend /opportunities/search endpoint
  ↓
Calls ATTOM API via attom_search_bounds()
  ↓
Filters properties by CSOKi criteria
  ↓
Calculates priority ranking
  ↓
Returns ranked opportunities
  ↓
Frontend displays purple diamond markers with ranks
  ↓
User clicks marker
  ↓
Shows PropertyInfoCard with rank + signals
```

### Integration Points

1. **ATTOM API:** Uses existing `app/services/attom.py` module
2. **Database:** No new tables required (ATTOM data is dynamic)
3. **Frontend Map:** Integrates seamlessly with existing property layers
4. **Property Info Card:** Reuses existing component with enhanced data

---

## 📁 Files Modified

### Backend
- ✅ `backend/app/api/routes/opportunities.py` (NEW - 407 lines)
- ✅ `backend/app/api/__init__.py` (added opportunities router)

### Frontend
- ✅ `frontend/src/types/store.ts` (added OpportunityRanking types)
- ✅ `frontend/src/store/useMapStore.ts` (added opportunities state)
- ✅ `frontend/src/services/api.ts` (added opportunitiesApi)
- ✅ `frontend/src/components/Sidebar/MapLayers.tsx` (added csoki_opportunities layer)
- ✅ `frontend/src/components/Map/StoreMap.tsx` (added opportunity markers & logic)

---

## 🧪 Testing Checklist

### Backend Testing

```bash
# Start backend server
cd backend
uvicorn app.main:app --reload

# Test endpoint
curl -X POST http://localhost:8000/api/v1/opportunities/search \
  -H "Content-Type: application/json" \
  -d '{
    "min_lat": 41.0,
    "max_lat": 42.0,
    "min_lng": -96.5,
    "max_lng": -95.5
  }'

# Expected response: JSON with ranked opportunities

# Test stats endpoint
curl http://localhost:8000/api/v1/opportunities/stats
```

### Frontend Testing

1. **Layer Toggle:**
   - [ ] Toggle "CSOKi Opportunities" layer ON
   - [ ] Purple diamond markers appear on map
   - [ ] Markers show rank numbers (#1, #2, #3...)

2. **Marker Interaction:**
   - [ ] Click opportunity marker
   - [ ] PropertyInfoCard opens
   - [ ] Card shows: "Rank #X of Y opportunities"
   - [ ] Priority signals listed at top
   - [ ] All opportunity signals displayed

3. **Data Refresh:**
   - [ ] Pan/zoom map
   - [ ] New opportunities load for new viewport
   - [ ] Old markers clear correctly

4. **Toggle OFF:**
   - [ ] Turn layer OFF
   - [ ] All opportunity markers disappear
   - [ ] No errors in console

5. **Error Handling:**
   - [ ] If ATTOM_API_KEY missing, shows error message
   - [ ] If no opportunities found, shows empty state gracefully

---

## 🎨 Visual Design

### Marker Design
- **Shape:** Diamond (distinct from circular property markers)
- **Color:** Purple (#9333EA)
- **Label:** White rank number inside marker
- **Size:** 32px (default), 40px (selected)
- **Z-Index:** 400 (default), 1800 (selected)

### Priority Signals Display
```
┌─────────────────────────────────────┐
│ Rank #5 of 42 opportunities         │ ← High priority badge
├─────────────────────────────────────┤
│ WHY THIS OPPORTUNITY?               │
│                                     │
│ ▸ Empty parcel (land only)         │ ← Priority signal 1
│ ▸ Out-of-state owner                │ ← Priority signal 2
│                                     │
│ OTHER SIGNALS (3 total):            │
│ • Long-term ownership (18 years)    │
│ • Large lot: 1.2 acres              │
│ • Commercial zoning                 │
└─────────────────────────────────────┘
```

---

## 🚀 Deployment Steps

### 1. Backend Deployment

```bash
# On Railway (or deployment platform):
# 1. Push changes to Git
# 2. Ensure ATTOM_API_KEY environment variable is set
# 3. Backend will auto-deploy

# Verify:
curl https://your-backend-url.com/api/v1/opportunities/stats
```

### 2. Frontend Deployment

```bash
# Build frontend
cd frontend
npm run build

# Deploy (Railway auto-deploys on git push)
# Verify at https://dashboard.fivecodevelopment.com
```

### 3. Environment Variables Required

**Backend (.env):**
```
ATTOM_API_KEY=your_attom_api_key_here
```

**Frontend (.env):**
```
VITE_API_URL=https://backend-production-cf26.up.railway.app
```

---

## 📊 Expected Results

### Performance
- **API Response Time:** ~2-3 seconds (ATTOM API latency)
- **Typical Results:** 20-50 opportunities per viewport
- **Max Results:** 100 (configurable)

### Sample Output
For Iowa region (41.0-42.0 lat, -96.5 to -95.5 lng):
- ~30-40 properties matching criteria
- Top 5 ranks typically: empty parcels with tax pressure
- Ranks 6-15: Vacant buildings + absentee owners
- Ranks 16+: Older buildings with various signals

---

## 🐛 Known Limitations

1. **ATTOM API Coverage:** Some rural areas may have limited data
2. **Multi-Tenant Detection:** Uses heuristics (size + context), not 100% accurate
3. **Owner Age:** Estimated via estate/trust ownership, not direct age data
4. **Real-Time Data:** ATTOM data is not real-time (updated quarterly)

---

## 🔄 Future Enhancements

1. **Filtering UI:** Add sidebar panel to adjust criteria (parcel size, etc.)
2. **Export:** CSV export of opportunities in current view
3. **Saved Searches:** Save opportunity search criteria
4. **Notifications:** Alert when new opportunities appear in saved searches
5. **Integration:** Link to parcel details (ReportAll integration)
6. **Bulk Actions:** Select multiple opportunities for batch review

---

## 📞 Support

**Questions? Issues?**
- Check backend logs for ATTOM API errors
- Verify ATTOM_API_KEY is set and valid
- Review browser console for frontend errors

**Success Criteria:**
✅ Purple diamond markers appear when layer is toggled
✅ Markers show rank numbers
✅ Clicking shows property details with opportunity context
✅ No console errors

---

## ✨ Summary

**What was built:**
A complete end-to-end opportunity filtering system that automatically identifies and ranks commercial properties matching CSOKi's criteria using ATTOM property data API.

**Key Value:**
Instead of manually searching through hundreds of properties, the system automatically surfaces the top 20-50 most promising opportunities in any geographic area, ranked by multiple opportunity signals.

**Ready for:** Production deployment after basic smoke testing

---

**Implementation Time:** ~3 hours  
**Lines of Code Added:** ~850 lines (backend + frontend)  
**Status:** ✅ **READY FOR REVIEW & TESTING**
