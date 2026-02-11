# Crexi Integration Plan

**Date:** 2026-02-04  
**Status:** Ready to Build  
**Timeline:** 2-3 days to production

---

## ✅ What We Learned from Export Sample

### Data Quality: Excellent
- **171 properties** from Davenport, IA export
- **All "On-Market"** (for sale) - Crexi export already filtered
- **Complete data:** lat/long, price, size, type, days on market
- **Direct links** to Crexi listings included

### Column Schema (24 fields total)
```
Property Link, Property Name, Property Status, Type, Address, City, State, Zip,
Tenant(s), Lease Term, Remaining Term, SqFt, Lot Size, Units, Price/Unit, NOI,
Cap Rate, Asking Price, Price/SqFt, Price/Acre, Days on Market, Opportunity Zone,
Longitude, Latitude
```

---

## 🎯 Filtering Strategy (Revised)

**Original criteria was too restrictive:** Only 3/171 properties matched

**Better approach - Two categories (OR logic):**

### Category A: Empty Land Parcels
- Lot size: 0.8-2 acres
- Type contains "Land"
- No building or minimal structure
- **Result:** 13 properties in sample

### Category B: Small Buildings  
- Building size: 2500-6000 sqft
- Type: Retail or Office
- Units ≤ 1 (single-tenant)
- **Result:** 14 properties in sample

### Combined Result
**27 properties match** (16% of export) - Much more reasonable!

---

## 🚀 Implementation Plan

### Phase 1: CSV Parser (Today - 2 hours)
**Build the backend service to parse Crexi exports**

**File:** `backend/app/services/crexi_parser.py`

**Functions:**
```python
def parse_crexi_csv(file_path: str) -> List[CrexiListing]:
    """Parse Crexi Excel export into structured data"""
    
def filter_opportunities(listings: List[CrexiListing]) -> List[CrexiListing]:
    """Apply Michael's criteria (empty land OR small buildings)"""
    
def import_to_database(listings: List[CrexiListing]) -> ImportResult:
    """Save listings to scraped_listings table"""
```

**Database table:** `scraped_listings`
- Store parsed Crexi data
- Track import timestamp
- Flag source as "Crexi Export"
- Include cache TTL (24-48 hours)

---

### Phase 2: Playwright Automation (Tomorrow - 4 hours)
**Automate the export process**

**File:** `backend/app/services/crexi_automation.py`

**Workflow:**
1. Launch headless Chromium
2. Navigate to crexi.com
3. Log in with credentials (from env vars)
4. Search for target location (city + state or ZIP)
5. Apply filters:
   - Property Status: For Sale
   - Property Type: Land, Retail, Office
6. Click "Export" button
7. Wait for download
8. Save to temp directory
9. Pass to parser
10. Clean up temp files

**Environment variables needed:**
```
CREXI_EMAIL=your_email@domain.com
CREXI_PASSWORD=your_password
```

**Estimated time:** 30-60 seconds per export

---

### Phase 3: API Endpoint (Tomorrow - 2 hours)
**Create backend endpoint for frontend to trigger**

**Endpoint:** `POST /listings/fetch-crexi-area`

**Request:**
```json
{
  "location": "Des Moines, IA",
  "forceRefresh": false
}
```

**Response:**
```json
{
  "success": true,
  "imported": 27,
  "cached": false,
  "timestamp": "2026-02-04T12:00:00Z",
  "expiresAt": "2026-02-05T12:00:00Z"
}
```

**Caching logic:**
- Check if location was fetched in last 24 hours
- If yes → return cached data
- If no → trigger Playwright automation
- Store cache timestamp in database

**Error handling:**
- Timeout after 90 seconds
- Return partial results if parse fails mid-way
- Log errors for debugging
- Graceful degradation (show ATTOM data even if Crexi fails)

---

### Phase 4: Frontend Integration (Day 3 - 3 hours)
**Add UI controls to trigger Crexi import**

**Component:** `CrexiDataLoader.tsx`

**UI Flow:**
1. User searches location or zooms to area
2. Button appears: "Load Crexi Listings"
3. Click → show loading state
4. Progress indicator: "Fetching from Crexi... (~60 sec)"
5. On success: "Loaded 27 properties from Crexi"
6. Properties appear as green pins on map
7. Cache indicator: "Last updated 2 hours ago"

**Features:**
- "Refresh" button (force new export)
- Auto-refresh if >24 hours old
- Error messages if automation fails
- Fallback to ATTOM opportunities

---

## 🔒 Security & Credentials

### Storage
- Crexi credentials in Railway environment variables
- Never exposed to frontend
- Never logged in plain text
- Backend-only access

### Rate Limiting
- Max 1 export per location per hour
- Prevents spam/abuse
- Protects Crexi account from flagging

### Session Management
- Playwright creates fresh session each time
- Cleans up cookies/cache after export
- No persistent login state

---

## 📊 Cache Strategy

### Location-based caching
**Key format:** `crexi:des_moines_ia:2026-02-04`

**TTL:** 24 hours (configurable)

**Storage:** PostgreSQL `cache` table
```sql
CREATE TABLE crexi_cache (
  id SERIAL PRIMARY KEY,
  location VARCHAR(255),
  fetched_at TIMESTAMP,
  expires_at TIMESTAMP,
  property_count INTEGER,
  status VARCHAR(50)
);
```

**Invalidation:**
- Auto-expires after 24 hours
- Manual refresh button forces new export
- Failed exports don't cache

---

## 🎯 User Experience

### Happy Path
1. User: "Show me Des Moines opportunities"
2. System: Checks cache → found (2 hours old)
3. System: Returns cached data instantly
4. User: Sees 27 properties on map
5. User: Clicks property → sees details + "View on Crexi" link

### First-time Path
1. User: "Show me Cedar Rapids opportunities"
2. System: Checks cache → not found
3. System: Triggers Playwright automation
4. System: Shows progress: "Fetching... 45 sec remaining"
5. System: Parses CSV, imports to database
6. User: Sees properties on map
7. System: Caches for 24 hours

### Error Path
1. User: "Show me Lincoln, NE opportunities"
2. System: Automation fails (Crexi timeout)
3. System: Shows friendly error: "Couldn't fetch Crexi data right now"
4. System: Fallback to ATTOM opportunities
5. User: Still sees useful data (ATTOM signals)

---

## 🧪 Testing Plan

### Unit Tests
- CSV parser handles various formats
- Filtering logic matches criteria
- Database import handles duplicates

### Integration Tests  
- Playwright automation logs in successfully
- Export button click works
- CSV download completes
- End-to-end: location → properties on map

### Manual Testing
1. Test with Des Moines (known working)
2. Test with Cedar Rapids (new location)
3. Test cache behavior (first fetch vs cached)
4. Test force refresh
5. Test error handling (wrong credentials, timeout)

---

## 📈 Success Metrics

### Technical
- Export completes in <90 seconds
- Parser handles 100% of Crexi CSV formats
- 0 crashes/errors in production
- Cache hit rate >70%

### User Experience
- Users can load any Iowa/Nebraska/Nevada location
- Properties appear on map immediately (if cached)
- Clear feedback during loading
- No confusion about data freshness

### Business Value
- 16% of Crexi properties match criteria (27/171)
- Users find opportunities faster
- Reduces manual Crexi browsing time
- Enables systematic market analysis

---

## 🚦 Risk Assessment

### Low Risk ✅
- CSV parsing (data structure is stable)
- Database import (standard SQL operations)
- Frontend integration (standard React patterns)

### Medium Risk ⚠️
- Playwright automation (Crexi could change their UI)
- Login flow (MFA could be enabled, captcha could appear)
- Export button location (Crexi redesign could move it)

### Mitigation
- Extensive error handling
- Fallback to manual CSV upload if automation fails
- Monitoring/alerting for automation failures
- Screenshot capture on errors for debugging

---

## 🔮 Future Enhancements

### Phase 2 Features (after initial launch)
1. **Multi-market batch export**
   - Load multiple cities at once
   - Background job queue
   - Email notification when complete

2. **Smart filtering**
   - User-adjustable criteria (size ranges, price, days on market)
   - Save filter presets
   - Compare opportunities across markets

3. **Data enrichment**
   - Cross-reference Crexi + ATTOM data
   - Combined scoring (listing + opportunity signals)
   - "Best of both" properties

4. **Automated monitoring**
   - Daily refresh of active markets
   - Alert when new properties match criteria
   - Price change notifications

---

## 💰 Cost Analysis

### Development Time
- Phase 1 (Parser): 2 hours
- Phase 2 (Automation): 4 hours
- Phase 3 (API): 2 hours
- Phase 4 (Frontend): 3 hours
- Testing: 2 hours
- **Total: ~13 hours over 2-3 days**

### Ongoing Costs
- Railway compute: Minimal (Playwright adds ~200MB memory)
- Storage: Minimal (listings cached, not permanent)
- Maintenance: Low (CSV structure rarely changes)

### ROI
**Before:** Team manually browses Crexi, copies data
**After:** One-click import, 27 opportunities in 60 seconds
**Time saved:** ~30 min per market search
**Value:** Massive productivity gain

---

## ✅ Next Steps

### Immediate (Today)
1. ✅ Confirm CSV structure analysis
2. ⏳ Get Michael's approval on filtering approach
3. ⏳ Secure Crexi credentials (email + password)
4. ⏳ Build CSV parser

### Tomorrow
1. Build Playwright automation
2. Test with Michael's credentials
3. Create API endpoint
4. Test end-to-end

### Day 3
1. Build frontend component
2. Integration testing
3. Deploy to Railway
4. User acceptance testing with Michael

---

## 🎯 Definition of Done

- ✅ User can click "Load Crexi Listings" for any location
- ✅ System exports from Crexi automatically
- ✅ 27/171 properties match criteria (16%)
- ✅ Properties appear on map with correct data
- ✅ "View on Crexi" link works
- ✅ Cache prevents duplicate exports
- ✅ Error handling shows friendly messages
- ✅ Performance: <90 sec for new location, <1 sec for cached

---

**Ready to proceed when Michael approves this approach.**
