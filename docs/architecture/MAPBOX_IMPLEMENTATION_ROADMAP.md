# Mapbox Implementation Roadmap
## CSOKi Site Selection Platform

**Date:** February 5, 2026  
**Status:** Ready for Implementation  
**Based on:** 51KB Mapbox Capabilities Research

---

## Executive Summary

This roadmap prioritizes **immediate wins** (4 weeks, $0 cost) using existing Mapbox GL JS capabilities before exploring advanced features. Focus: maximize value from current stack.

### Quick Wins Summary (Month 1)
- **Data-driven expressions** for dynamic styling
- **3D extrusions** for population/revenue visualization
- **Time-based traffic** animations
- **Enhanced isochrones** with traffic awareness

**Total Investment:** 4 weeks, 1 developer, $0 additional cost

---

## Current Mapbox Integration Status

### ✅ Already Implemented
- Mapbox GL JS v3.18.1 (frontend/package.json)
- Basic map rendering (MapboxMap.tsx)
- Style switcher (8 styles: Standard, Streets, Satellite, etc.)
- Isochrone API (mapbox-isochrone.ts) - driving/walking/cycling modes
- 3D buildings layer (Mapbox Standard style)
- Marker clustering for stores
- Basic navigation controls

### ❌ Not Yet Implemented
- Data-driven styling expressions
- 3D data extrusions (population, revenue)
- Traffic-aware isochrones (depart_at parameter)
- Time-based animations
- Advanced layer interactions
- Matrix API for competitive analysis
- Datasets API for server-side data management

---

## Phase 1: Foundation Enhancements (Weeks 1-4) - $0 Cost

**Goal:** Maximize existing Mapbox GL JS features without new API calls.

### Week 1: Data-Driven Expressions

**Objective:** Replace static styling with dynamic, data-driven visualizations.

**Tasks:**
1. **Traffic Count Visualization** (2 days)
   - Replace fixed circle sizes with data-driven scaling
   - Implement color gradients based on traffic volume
   - Add zoom-responsive sizing
   - Code location: `frontend/src/components/Map/MapboxMap.tsx`

   ```typescript
   // Example implementation
   map.addLayer({
     id: 'traffic-counts',
     type: 'circle',
     source: 'traffic',
     paint: {
       'circle-radius': [
         'interpolate', ['linear'], ['zoom'],
         10, ['*', ['get', 'count'], 0.001],
         14, ['*', ['get', 'count'], 0.005],
         16, ['*', ['get', 'count'], 0.01]
       ],
       'circle-color': [
         'interpolate', ['linear'], ['get', 'count'],
         1000, '#fee5d9',
         5000, '#fc8d59',
         10000, '#e34a33',
         20000, '#b30000'
       ],
       'circle-opacity': 0.7
     }
   });
   ```

2. **Store Performance Indicators** (2 days)
   - Add performance-based styling to store markers
   - Implement conditional colors (green=growing, yellow=stable, red=declining)
   - Dynamic labels with formatted revenue

3. **Property Opportunity Scores** (1 day)
   - Color-code opportunity markers by score (0-100)
   - Size markers based on opportunity rank
   - Add pulsing animation for top opportunities

**Deliverables:**
- Enhanced traffic count visualization
- Performance-based store styling
- Improved opportunity marker system
- Documentation in `MAPBOX_EXPRESSIONS.md`

**Estimated Effort:** 5 days (1 week)  
**Cost:** $0 (uses existing GL JS expressions)  
**Dependencies:** None

---

### Week 2: 3D Data Extrusions

**Objective:** Create engaging 3D visualizations for metrics that matter.

**Tasks:**
1. **Population Density Extrusions** (2 days)
   - Add fill-extrusion layer for census blocks
   - Height = population density
   - Color gradient by density level
   - Code location: New file `frontend/src/components/Map/PopulationLayer.tsx`

   ```typescript
   map.addLayer({
     id: 'population-3d',
     type: 'fill-extrusion',
     source: 'census-blocks',
     paint: {
       'fill-extrusion-height': [
         '*',
         ['get', 'population_density'],
         5 // Scale factor
       ],
       'fill-extrusion-color': [
         'interpolate', ['linear'], ['get', 'population_density'],
         0, '#ffffcc',
         100, '#41b6c4',
         500, '#253494'
       ],
       'fill-extrusion-opacity': 0.7
     }
   });
   ```

2. **Store Revenue Visualization** (2 days)
   - 3D columns representing monthly revenue
   - Animated transitions on data updates
   - Interactive hover for details

3. **Controls & UI** (1 day)
   - Toggle for 3D visualizations
   - Pitch/bearing controls (already exist, enhance)
   - Performance optimization for large datasets

**Deliverables:**
- Population density 3D layer
- Store revenue 3D visualization
- Layer toggle controls
- Performance benchmarks

**Estimated Effort:** 5 days (1 week)  
**Cost:** $0 (GPU-accelerated, no API calls)  
**Dependencies:** Census block geometry data

---

### Week 3: Time-Based Traffic Animations

**Objective:** Show how traffic patterns change throughout the day.

**Tasks:**
1. **Hourly Traffic Data Model** (1 day)
   - Structure traffic data with hour_0 through hour_23 properties
   - Update traffic data import scripts
   - Code location: `scripts/download-iowa-traffic.js`

2. **Time Slider Component** (2 days)
   - Build React time slider component
   - Play/pause controls
   - Hour label display
   - Speed controls (1x, 2x, 4x)
   - Code location: New file `frontend/src/components/Map/TimeSlider.tsx`

3. **Heatmap Animation** (2 days)
   - Add heatmap layer with hourly weight property
   - Connect slider to layer filter
   - Smooth transitions between hours
   - Export/record functionality

**Deliverables:**
- Time slider UI component
- Animated traffic heatmap
- Hour-by-hour traffic visualization
- Usage documentation

**Estimated Effort:** 5 days (1 week)  
**Cost:** $0 (client-side animation)  
**Dependencies:** Hourly traffic data

---

### Week 4: Enhanced Isochrones

**Objective:** Make drive-time analysis more accurate and useful.

**Tasks:**
1. **Traffic-Aware Isochrones** (2 days)
   - Add `depart_at` parameter to isochrone API calls
   - Time-of-day selector UI
   - Compare AM vs PM drive times
   - Code location: `frontend/src/services/mapbox-isochrone.ts`

   ```typescript
   // Enhanced isochrone call
   const url = `https://api.mapbox.com/isochrone/v1/mapbox/driving-traffic/${lng},${lat}`;
   const params = new URLSearchParams({
     contours_minutes: minutes.toString(),
     polygons: 'true',
     depart_at: '2026-02-05T08:00:00', // Morning rush hour
     access_token: accessToken,
   });
   ```

2. **Distance-Based Contours** (1 day)
   - Add `contours_meters` option
   - Switch between time and distance modes
   - Useful for delivery zone planning

3. **Comparison Mode** (2 days)
   - Side-by-side comparison (different times or locations)
   - Overlap visualization
   - Difference highlighting

**Deliverables:**
- Traffic-aware isochrone mode
- Time-of-day selector
- AM/PM comparison view
- Updated IsochroneControl component

**Estimated Effort:** 5 days (1 week)  
**Cost:** $0 (within free tier: 100k requests/month)  
**Dependencies:** Mapbox Isochrone API (already configured)

---

## Phase 2: Data Infrastructure (Weeks 5-8) - $0-50/month

**Goal:** Migrate to server-side data management for scalability.

### Week 5-6: Datasets API Integration

**Objective:** Move traffic counts (7k+ features) to Mapbox server-side storage.

**Why This Matters:**
- Current: Client loads 7k+ GeoJSON features on every page load
- Future: Server-side tiles load instantly, enable real-time updates
- Free tier: 480 reads/min, 40 writes/min (sufficient)

**Tasks:**
1. **Dataset Creation & Migration** (3 days)
   - Create Mapbox dataset for Iowa traffic counts
   - Write migration script: GeoJSON → Datasets API
   - Implement batch upload (handle rate limits)
   - Code location: New file `backend/scripts/migrate-to-mapbox-datasets.py`

2. **Backend Integration** (2 days)
   - Add Datasets API endpoints to FastAPI
   - Update/create/delete traffic count features
   - Real-time sync triggers

3. **Frontend Update** (2 days)
   - Replace client-side GeoJSON with dataset source
   - Implement optimistic updates
   - Error handling & retry logic

4. **Testing & Optimization** (3 days)
   - Load testing (10k+ features)
   - Performance benchmarking
   - Cache strategy

**Deliverables:**
- Traffic counts migrated to Mapbox Datasets
- Real-time update capability
- Admin UI for traffic data management
- Migration documentation

**Estimated Effort:** 10 days (2 weeks)  
**Cost:** $0 (free tier sufficient)  
**Dependencies:** MAPBOX_ACCESS_TOKEN with Datasets scope

---

### Week 7-8: Tiling Service for Parcels

**Objective:** Optimize large parcel dataset (potential 100k+ features).

**Tasks:**
1. **Tileset Creation** (2 days)
   - Upload parcel GeoJSON to Mapbox Tiling Service
   - Create tileset recipe (zoom levels, simplification)
   - Publish tileset

2. **Source Integration** (1 day)
   - Replace client-side parcel rendering with vector tiles
   - Update layer styling

3. **Zoom-Level Optimization** (2 days)
   - Simplify geometries at low zoom
   - Show only relevant parcels at each zoom level
   - Performance testing

**Deliverables:**
- Parcel vector tileset
- Optimized zoom-level rendering
- Upload/update scripts

**Estimated Effort:** 5 days (1 week)  
**Cost:** Free tier: 200k tiles/month (sufficient for initial load)  
**Dependencies:** Parcel boundary data

---

## Phase 3: Advanced Analytics (Weeks 9-12) - $100-200/month

**Goal:** Add competitive analysis and route optimization.

### Week 9-10: Matrix API Integration

**Objective:** Multi-point travel time analysis for competitive catchment modeling.

**Use Cases:**
- Calculate drive times from all competitor stores to target site
- Identify market gaps (areas far from all competitors)
- Model catchment area overlap

**Tasks:**
1. **Matrix API Service** (3 days)
   - Build backend wrapper for Matrix API
   - Handle rate limiting (30 req/min for traffic profile)
   - Batch processing for large competitor sets
   - Code location: New file `backend/app/services/mapbox_matrix.py`

2. **Competitive Analysis UI** (3 days)
   - Competitor selection interface
   - Target site picker
   - Travel time matrix visualization
   - Heatmap of competitive pressure

3. **Catchment Overlap Visualization** (4 days)
   - Calculate overlapping catchment areas
   - Voronoi territories based on travel time
   - "Battle zones" where markets overlap

**Deliverables:**
- Matrix API integration
- Competitive travel time analysis
- Catchment overlap heatmap
- Territory visualization

**Estimated Effort:** 10 days (2 weeks)  
**Cost:** $50-100/month (est. 10k elements/day)  
**Free Tier:** 1,250 elements/month (5x5 matrix daily)  
**Dependencies:** Competitor store coordinates

---

### Week 11-12: Directions API & Route Planning

**Objective:** Model delivery routes and realistic travel times.

**Tasks:**
1. **Directions Integration** (3 days)
   - Add route planning from stores
   - Traffic-aware routing
   - Turn-by-turn directions display

2. **Delivery Zone Modeling** (4 days)
   - Calculate optimal delivery routes
   - Time-window constraints
   - Multiple stops optimization

3. **Integration with Isochrones** (3 days)
   - Combined view: isochrones + actual routes
   - Route validation (does route fit in isochrone?)
   - Documentation

**Deliverables:**
- Route planning from stores
- Delivery zone modeling
- Traffic-aware directions
- Combined isochrone/route view

**Estimated Effort:** 10 days (2 weeks)  
**Cost:** $25-50/month (5k routes/day)  
**Free Tier:** 100k requests/month  
**Dependencies:** Store coordinates, delivery addresses

---

## Phase 4: Advanced Visualizations (Weeks 13-18) - Optional

**Goal:** Create unique, differentiated visualizations.

### Custom WebGL Layers (6 weeks)

**High-Effort, High-Impact Features:**

1. **Particle System Traffic Flow** (2 weeks)
   - 10,000+ animated particles along roads
   - Speed = traffic speed, density = volume
   - Extremely engaging for demos

2. **Predictive ML Zones** (2 weeks)
   - AI-driven opportunity zone predictions
   - Confidence visualization
   - What-if scenario modeling

3. **Custom Interactions** (2 weeks)
   - Drag-to-compare tool
   - Drawing tools for custom areas
   - Snapshot/bookmark system

**Estimated Effort:** 30 days (6 weeks)  
**Cost:** $0 for rendering, variable for ML ($500-2000/month)  
**Dependencies:** ML model, training data

---

## Cost Analysis by Phase

### Phase 1: Foundation (Weeks 1-4)
- **API Costs:** $0
- **Reason:** Uses existing GL JS, no additional API calls
- **Within Free Tier:** Yes

### Phase 2: Data Infrastructure (Weeks 5-8)
- **API Costs:** $0
- **Datasets API:** 480 reads/min, 40 writes/min (free)
- **Tiling Service:** 200k tiles/month (free)
- **Within Free Tier:** Yes

### Phase 3: Advanced Analytics (Weeks 9-12)
- **Matrix API:** $50-100/month (10k elements/day)
- **Directions API:** $25-50/month (5k routes/day)
- **Total:** $75-150/month
- **When Exceeds Free Tier:** Matrix at ~40 analyses/day, Directions at ~3,333 routes/day

### Phase 4: Advanced Visualizations (Weeks 13-18)
- **Rendering:** $0 (client-side WebGL)
- **ML Services:** $500-2000/month (optional)
- **Total:** $0-2000/month depending on ML usage

### Annual Cost Projection (After Full Implementation)
- **Year 1:** $0-900 (Phases 1-2 only)
- **Year 2:** $900-1,800 (Adding Phase 3)
- **Year 3:** $1,800-3,600 (If adding ML/Phase 4)

**Comparison to Alternatives:**
- Google Maps: $7-200 per 1,000 requests (more expensive)
- ESRI ArcGIS: $1,500-10,000/year (enterprise)
- Mapbox: $0-3,600/year (scales with usage)

---

## Success Metrics

### Phase 1 (Foundation)
- [ ] Traffic visualization loads in <2 seconds
- [ ] 3D extrusions render at 60fps on modern hardware
- [ ] Time animation plays smoothly (no lag)
- [ ] Enhanced isochrones match existing functionality

### Phase 2 (Data Infrastructure)
- [ ] 10k+ features load instantly from Datasets
- [ ] Real-time updates propagate in <5 seconds
- [ ] Parcel vector tiles reduce client load by 80%
- [ ] No degradation in map performance

### Phase 3 (Advanced Analytics)
- [ ] Matrix analysis completes in <10 seconds
- [ ] Competitive heatmap updates on map pan
- [ ] Route planning works with traffic data
- [ ] API costs stay under budget

### Phase 4 (Advanced Visualizations)
- [ ] Particle system runs at 60fps
- [ ] ML predictions have >70% accuracy
- [ ] Custom tools enhance user workflow
- [ ] Positive user feedback

---

## Risk Assessment & Mitigation

### Risk 1: API Cost Overruns
**Likelihood:** Medium  
**Impact:** High  
**Mitigation:**
- Implement rate limiting
- Cache frequently accessed data
- Monitor usage daily
- Set cost alerts in Mapbox dashboard

### Risk 2: Performance Degradation
**Likelihood:** Low  
**Impact:** High  
**Mitigation:**
- Load testing before each phase
- Implement progressive disclosure (show less at low zoom)
- Use web workers for heavy computation
- Monitor client-side performance metrics

### Risk 3: Data Quality Issues
**Likelihood:** Medium  
**Impact:** Medium  
**Mitigation:**
- Validate data before Datasets upload
- Implement data quality checks
- Fallback to cached data on API failures
- Regular data audits

### Risk 4: Timeline Delays
**Likelihood:** High  
**Impact:** Low  
**Mitigation:**
- Prioritize high-value features first
- Ship incrementally (weekly releases)
- Buffer time for unexpected issues (20%)
- Parallel work where possible

---

## Dependencies & Prerequisites

### Phase 1 Requirements
- ✅ Mapbox GL JS v3.18.1 (already installed)
- ✅ MAPBOX_ACCESS_TOKEN (already configured)
- ⏳ Census block geometry data (need to source)
- ⏳ Hourly traffic data (need to collect)

### Phase 2 Requirements
- ✅ Mapbox access token with Datasets scope
- ⏳ Backend infrastructure for Datasets API
- ⏳ Parcel boundary GeoJSON files

### Phase 3 Requirements
- ⏳ Mapbox access token with Matrix/Directions scope
- ⏳ Budget approval for paid API usage
- ⏳ Competitor store coordinates (already have)

### Phase 4 Requirements
- ⏳ WebGL expertise (consider contractor)
- ⏳ ML model training data
- ⏳ Cloud infrastructure for ML inference

---

## Rollout Strategy

### Week-by-Week Rollout (Phase 1)

**Week 1:**
- Day 1-2: Data-driven traffic count styling
- Day 3-4: Store performance indicators
- Day 5: Property opportunity scores
- Deploy to staging Friday

**Week 2:**
- Day 1-2: Population density 3D layer
- Day 3-4: Store revenue 3D visualization
- Day 5: Layer controls & UI polish
- Deploy to production Friday

**Week 3:**
- Day 1: Hourly traffic data model
- Day 2-3: Time slider component
- Day 4-5: Heatmap animation
- Deploy to staging Friday

**Week 4:**
- Day 1-2: Traffic-aware isochrones
- Day 3: Distance-based contours
- Day 4-5: Comparison mode
- Deploy to production Friday, celebrate Month 1 completion

### Feature Flags
Implement feature flags for gradual rollout:
- `ENABLE_3D_EXTRUSIONS`
- `ENABLE_TIME_ANIMATION`
- `ENABLE_TRAFFIC_ISOCHRONES`
- `ENABLE_MATRIX_API` (Phase 3)

---

## Documentation Plan

### For Developers
- `MAPBOX_EXPRESSIONS.md` - Expression syntax guide with examples
- `MAPBOX_3D_LAYERS.md` - 3D extrusion patterns
- `MAPBOX_ANIMATIONS.md` - Animation techniques
- `MAPBOX_API_USAGE.md` - API integration guide

### For Users
- Video tutorial: "Using Time-Based Traffic Analysis"
- Guide: "Understanding 3D Population Visualizations"
- FAQ: "How to Interpret Opportunity Scores"

### For Stakeholders
- Monthly progress reports
- Cost vs. value analysis
- User adoption metrics

---

## Next Steps (Immediate)

### This Week (Week of Feb 5)
1. **Get approval** from Michael for Phase 1 roadmap
2. **Review data requirements** - confirm census block data availability
3. **Set up development environment** - ensure Mapbox token has required scopes
4. **Create feature branch** - `feature/mapbox-phase-1`
5. **Begin Week 1 tasks** - start with traffic count styling

### This Month (February 2026)
1. Complete Phase 1 (Weeks 1-4)
2. User testing and feedback collection
3. Performance benchmarking
4. Begin Phase 2 planning (Datasets API)

### This Quarter (Q1 2026)
1. Complete Phase 1 and Phase 2
2. Evaluate Phase 3 based on user feedback
3. Budget review for paid API features
4. Plan Phase 4 (if valuable)

---

## Conclusion

This roadmap delivers:
- ✅ **Immediate value** - 4 weeks, $0 cost, visible improvements
- ✅ **Scalable foundation** - Server-side data management in Weeks 5-8
- ✅ **Advanced features** - Optional Phases 3-4 when needed
- ✅ **Cost-conscious** - Stays in free tier for 2 months, scales gradually

**Recommendation:** Start Phase 1 immediately. Quick wins build momentum and validate approach before investing in paid APIs.

**Total Timeline:** 4-18 weeks depending on scope  
**Total Cost:** $0-$3,600/year depending on usage  
**ROI:** High - better insights, faster decisions, competitive advantage

---

**Prepared by:** AI Agent  
**Date:** February 5, 2026  
**Status:** Ready for Review & Approval  
**Based on:** MAPBOX_CAPABILITIES_RESEARCH.md (51KB)
