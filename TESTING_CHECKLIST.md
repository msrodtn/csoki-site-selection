# Testing Checklist - URL Import & Enhancements

## Pre-Deployment Testing

### 1. URL Import Service

#### Backend API Testing
- [ ] **Test endpoint health:** `GET /health`
- [ ] **Test single URL import (preview mode):**
  ```bash
  curl -X POST https://backend-production-cf26.up.railway.app/api/v1/listings/import-url/ \
    -H "Content-Type: application/json" \
    -d '{
      "url": "https://www.crexi.com/properties/SAMPLE-ID",
      "use_playwright": true,
      "save_to_database": false
    }'
  ```
  - Expected: JSON response with extracted data, confidence score
  - Check: `success: true`, fields populated, `confidence > 40`

- [ ] **Test single URL import (save mode):**
  ```bash
  curl -X POST https://backend-production-cf26.up.railway.app/api/v1/listings/import-url/ \
    -H "Content-Type: application/json" \
    -d '{
      "url": "https://www.crexi.com/properties/SAMPLE-ID",
      "use_playwright": true,
      "save_to_database": true
    }'
  ```
  - Expected: Same as above + `listing_id` populated
  - Check: Verify listing appears in database/UI

- [ ] **Test batch import:**
  ```bash
  curl -X POST https://backend-production-cf26.up.railway.app/api/v1/listings/import-urls-batch/ \
    -H "Content-Type: application/json" \
    -d '{
      "urls": [
        "https://www.crexi.com/properties/ID1",
        "https://www.loopnet.com/Listing/ID2"
      ],
      "use_playwright": true,
      "save_to_database": false
    }'
  ```
  - Expected: Array of results with `successful` and `failed` counts

- [ ] **Test error handling:**
  - Invalid URL: `http://invalid-url.com`
  - 404 page
  - Non-CRE website
  - Expected: Graceful error messages, no crashes

#### Frontend Testing
- [ ] **Open URL Import Panel:**
  - Navigate to map
  - Find "Import from URL" button/link
  - Panel opens with proper styling

- [ ] **Test URL input flow:**
  1. Paste valid Crexi URL
  2. Click "Extract Data"
  3. Wait for loading spinner
  4. Preview appears with confidence badge
  5. All extracted fields display correctly
  6. Click "Save to Database"
  7. Success message shows
  8. Property appears on map

- [ ] **Test confidence scoring:**
  - High confidence (80-100): Green badge
  - Medium confidence (60-79): Yellow badge
  - Low confidence (40-59): Red badge with warning

- [ ] **Test edge cases:**
  - Empty URL field (button disabled)
  - Cancel during preview
  - Network error handling
  - Long descriptions (text truncation)

#### Bookmarklet Testing
- [ ] **Install Version 1 (Simple):**
  1. Create bookmark from BOOKMARKLET.md code
  2. Visit live Crexi listing
  3. Click bookmarklet
  4. Verify alert with success/failure

- [ ] **Install Version 2 (Preview):**
  1. Create bookmark from BOOKMARKLET.md code
  2. Visit live Crexi listing
  3. Click bookmarklet
  4. Popup window opens with extracted data
  5. Review and click "Save to CSOKi"
  6. Success confirmation

- [ ] **Test CORS handling:**
  - Bookmarklet may show CORS errors (expected)
  - Verify data still imports server-side

---

### 2. ATTOM Signal Enhancements

#### Signal Generation Testing
Test with sample properties to verify new signals appear:

- [ ] **Aging building signal:**
  - Property built before 1975
  - Should show: "Built YYYY (XX years old) - renovation opportunity"

- [ ] **Absentee owner signal:**
  - Owner state != property state
  - Should show: "Out-of-state owner (XX)"

- [ ] **Tax pressure signal:**
  - Recent tax increase >20%
  - Should show: "Tax assessment increased XX% recently"

- [ ] **Vacant property signal:**
  - Occupancy status = vacant
  - Should show: "Property appears vacant"

- [ ] **Multiple parcels signal:**
  - Parcel count > 1
  - Should show: "X parcels - assemblage opportunity"

#### Signal Display Testing
- [ ] Open PropertyInfoCard for opportunity property
- [ ] Verify "Why This Opportunity?" section shows
- [ ] Signals display with correct color coding:
  - High = Red
  - Medium = Yellow/Amber
  - Low = Blue
- [ ] Opportunity score displays (0-100)
- [ ] Signal descriptions are clear and actionable

#### Fallback Signal Testing
- [ ] Test property with no strong signals
- [ ] Should show at least 1 fallback signal
- [ ] Fallback descriptions are informative (not generic)

---

### 3. Search Bar Fix

#### Navigation Testing
- [ ] **Basic search:**
  1. Type city name in search bar
  2. Suggestions appear
  3. Click suggestion
  4. Map smoothly pans to location
  5. No console errors

- [ ] **Edge cases:**
  - Search immediately after page load (map not ready?)
  - Search while map is animating
  - Rapid consecutive searches
  - All should work without errors

- [ ] **Error handling:**
  - Check browser console for warnings
  - "Map navigation attempted before map instance is ready" → should not appear during normal use
  - If it does appear, verify map still navigates once ready

---

### 4. External URL Links

#### PropertyInfoCard Testing
- [ ] Select property with `external_url` populated
- [ ] "View Listing" button appears at bottom
- [ ] Click button
- [ ] Opens in new tab with correct URL
- [ ] Security attributes correct (noopener noreferrer)

- [ ] Test property without `external_url`
- [ ] "View Listing" button should NOT appear

---

## Railway Deployment

### Pre-Deploy Checks
- [ ] `feature/url-import-service` branch tested locally
- [ ] All commits pushed to GitHub
- [ ] No merge conflicts with `main`

### Deployment Process
1. [ ] Merge feature branch to main:
   ```bash
   git checkout main
   git merge feature/url-import-service
   git push origin main
   ```

2. [ ] Monitor Railway build:
   - Check build logs for Playwright installation
   - Verify Chromium downloads successfully
   - Build should complete without errors

3. [ ] Post-deploy health check:
   - [ ] `GET /health` returns 200
   - [ ] Test URL import endpoint
   - [ ] Check logs for Playwright errors

### Rollback Plan
If deployment fails:
```bash
git revert HEAD
git push origin main
```

---

## Post-Deployment Testing

### Smoke Tests (Production)
- [ ] Homepage loads
- [ ] Map renders
- [ ] Search bar works
- [ ] Properties For Sale layer works
- [ ] URL import works
- [ ] ATTOM signals display

### Performance Testing
- [ ] URL import completes in <10 seconds
- [ ] Playwright doesn't cause memory issues
- [ ] Map remains responsive during imports

---

## Known Issues / Notes

### Playwright on Railway
- Large binary (~200MB with Chromium)
- First request may be slow (cold start)
- Consider warming up instance after deploy

### ATTOM API Limitations
- 20-mile max radius for searches
- Rate limits (check if hit during testing)
- Some fields may not be available for all properties

### Search Bar
- Depends on Google Maps API loading
- Autocomplete requires internet connection
- Suggestions limited to US locations

---

## Success Criteria

**URL Import:**
- ✅ Can import Crexi listing via UI
- ✅ Can import LoopNet listing via UI
- ✅ Bookmarklet works in production
- ✅ Batch import processes multiple URLs

**ATTOM Signals:**
- ✅ At least 3 new signal types working
- ✅ Signals display with correct colors
- ✅ Fallback signals always present
- ✅ Opportunity score calculated correctly

**Search Bar:**
- ✅ No console errors during normal use
- ✅ Map navigates reliably
- ✅ Error handling graceful

**External Links:**
- ✅ View Listing button works
- ✅ Opens correct URL in new tab

---

## Completion Status

**Testing Phase:** ⏳ IN PROGRESS  
**Deployment Phase:** ⏳ NOT STARTED  
**Production Verification:** ⏳ NOT STARTED  

---

Last Updated: Feb 4, 2026 - 11:45 AM EST
