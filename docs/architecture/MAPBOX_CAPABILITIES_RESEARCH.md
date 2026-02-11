# Mapbox Capabilities Research
## Commercial Real Estate Site Selection Platform

**Research Date:** February 4, 2026  
**Platform:** CSOKI Convenience Store Site Selection  
**Current Stack:** React, TypeScript, Mapbox GL JS (basic: vector tiles, markers, popups, isochrones, 3D buildings)

---

## Executive Summary

### Top 5 Most Valuable Integrations for Site Selection

1. **Matrix API + Advanced Isochrones** - Multi-point travel time analysis for competitive catchment modeling
   - **Value:** Compare drive times from 25 locations simultaneously; identify overlap zones between competitors
   - **Quick Win:** High impact for site evaluation, moderate implementation complexity

2. **Datasets API + Real-Time Updates** - Dynamic data management for traffic counts and property data
   - **Value:** Efficiently manage 7k+ traffic features with server-side storage; enable real-time updates
   - **Cost Efficiency:** Stays within free tier (480 reads/min, 40 writes/min)

3. **Data-Driven Expressions + 3D Extrusions** - Dynamic visualizations based on performance metrics
   - **Value:** Visualize store performance, traffic density, population density as animated 3D bars
   - **Quick Win:** Uses existing GL JS, zero API cost, high visual impact

4. **Custom Layers (WebGL)** - Particle systems for traffic flow, animated heatmaps
   - **Value:** Create unique "living map" visualizations that differentiate your platform
   - **Strategic Investment:** High effort but creates competitive moat

5. **Directions API with Traffic** - Real-time route optimization and delivery zone planning
   - **Value:** Model delivery routes, calculate realistic travel times with traffic conditions
   - **Integration:** Works seamlessly with existing isochrone visualizations

---

## API Reference Guide

### 1. Datasets API

**What It Does:**  
Server-side storage and management of GeoJSON features. Create, read, update, delete features via REST API.

**How We Could Use It:**
- Store and manage 7k+ traffic count features server-side
- Enable collaborative editing of store locations and properties
- Version control for parcel and property data
- Real-time updates pushed to all connected clients

**Pricing:**
- **Free Tier:** 480 reads/min, 40 writes/min
- **Paid:** Contact for higher limits
- **No storage fees** - unlimited datasets and features

**Implementation Complexity:** ⭐⭐⭐ (3/5)
- Requires backend integration
- Simple REST API
- Need to convert current client-side data to Datasets

**Example Use Case:**
```javascript
// Update traffic count in real-time
const updateTrafficCount = async (featureId, newCount) => {
  await fetch(`https://api.mapbox.com/datasets/v1/${username}/${datasetId}/features/${featureId}`, {
    method: 'PUT',
    body: JSON.stringify({
      type: 'Feature',
      properties: { traffic_count: newCount, updated: Date.now() },
      geometry: { type: 'Point', coordinates: [lon, lat] }
    })
  });
  
  // Refresh map data
  map.getSource('traffic-data').setData(`/datasets/v1/${username}/${datasetId}/features`);
};
```

---

### 2. Tiling Service (MTS)

**What It Does:**  
Convert large GeoJSON datasets into optimized vector tiles. Upload data, get back a tileset URL.

**How We Could Use It:**
- Create custom vector tiles for parcels (100k+ features)
- Optimize property boundaries for fast rendering
- Custom tiles for census data, zoning, school districts
- Combine multiple data sources into single tileset

**Pricing:**
- **Free Tier:** 200k tiles generated/month
- **Paid:** $5 per additional 100k tiles
- Processing is one-time cost per dataset update

**Implementation Complexity:** ⭐⭐ (2/5)
- Upload GeoJSON via API
- Get tileset URL back
- Add as map source (same as current implementation)

**When to Use vs. Datasets API:**
- Use MTS for **large, static datasets** (parcels, boundaries)
- Use Datasets for **smaller, frequently updated data** (stores, traffic counts)

---

### 3. Matrix API

**What It Does:**  
Calculate travel times/distances between multiple points. Returns NxN matrix of all point-to-point combinations.

**How We Could Use It:**
- **Competitive Analysis:** Calculate drive times from all competitor stores to target site
- **Multi-Store Planning:** Find optimal location to serve existing stores (warehouse, distribution)
- **Catchment Overlap:** Identify areas served by multiple stores
- **Customer Access:** Measure accessibility from residential clusters

**Pricing:**
- **Free Tier:** 1,250 elements/month (25x25 matrix or 12x12 with multiple requests)
- **Paid:** Volume discounts available
- **Billed by Elements:** sources × destinations = elements

**Rate Limits:**
- 60 requests/min (standard profiles)
- 30 requests/min (traffic profile)
- Max 25 coords per request (standard), 10 coords (traffic)

**Implementation Complexity:** ⭐⭐⭐ (3/5)
- Simple API request
- Need to process and visualize matrix results
- Can integrate with existing isochrone visualizations

**Example Use Case:**
```javascript
// Calculate travel times from 5 competitor stores to target site
const competitors = [
  [-97.7431, 30.2672], // Store A
  [-97.7389, 30.2611], // Store B
  [-97.7521, 30.2701], // Store C
  [-97.7299, 30.2588], // Store D
  [-97.7612, 30.2755]  // Store E
];

const targetSite = [-97.7450, 30.2650];

const response = await fetch(
  `https://api.mapbox.com/directions-matrix/v1/mapbox/driving-traffic/` +
  `${[...competitors, targetSite].map(c => c.join(',')).join(';')}` +
  `?sources=0,1,2,3,4&destinations=5&annotations=duration,distance`
);

// Result: Array of [time, distance] from each competitor to target
// Use to identify if target is in "dead zone" between competitors
```

---

### 4. Geocoding API (Search API)

**What It Does:**  
Forward geocoding (address → coordinates) and reverse geocoding (coordinates → address). Structured input for precise results.

**How We Could Use It:**
- Address validation for property data entry
- Autocomplete for site search
- Reverse geocode to get full address context
- Structured input for precise data imports

**Pricing:**
- **Free Tier:** 100,000 requests/month (permanent storage)
- **Temporary storage:** More generous limits but can't cache results
- **Paid:** $0.50 per 1,000 requests after free tier

**Implementation Complexity:** ⭐ (1/5)
- Drop-in replacement for current geocoding
- Well-documented with React examples

**Pro Tip:**
- Use **structured input** for bulk imports: `address_number`, `street`, `place`, `region`, `postcode`
- Set `permanent=true` only when storing results
- Use `autocomplete=false` to reduce API calls

---

### 5. Directions API

**What It Does:**  
Turn-by-turn routing with traffic-aware options. Supports driving, walking, cycling profiles with live traffic data.

**How We Could Use It:**
- Delivery route planning from stores
- Calculate realistic drive times (vs. straight-line distance)
- Traffic-aware routing for time-of-day analysis
- EV routing for electric delivery fleet planning

**Pricing:**
- **Free Tier:** 100,000 requests/month
- **Paid:** $0.50 per 1,000 requests
- Traffic profile same price as standard

**Rate Limits:**
- 300 requests/min
- Max 25 waypoints per route

**Implementation Complexity:** ⭐⭐ (2/5)
- Simple API, rich response data
- Can visualize routes on map

**Advanced Features:**
- `exclude=toll,ferry,motorway` - route preferences
- `depart_at` - time-dependent routing
- `alternatives=true` - compare route options
- `annotations=duration,distance,speed,congestion` - detailed metrics

---

### 6. Isochrone API (Already Using!)

**What You Might Be Missing:**
- **Traffic-aware isochrones:** `mapbox/driving-traffic` profile with `depart_at` parameter
- **Distance-based contours:** `contours_meters` instead of `contours_minutes`
- **Polygon vs. Line output:** `polygons=true` for filled areas
- **Styling with simplestyle-spec:** Color code by time/distance
- **Auto-fit with padding:** `auto` parameter for dynamic bounds

**Advanced Use Cases:**
```javascript
// Traffic-aware isochrone for morning rush hour
const morningCommute = await fetch(
  `https://api.mapbox.com/isochrone/v1/mapbox/driving-traffic/` +
  `${lon},${lat}` +
  `?contours_minutes=5,10,15,20` +
  `&polygons=true` +
  `&depart_at=2026-02-05T08:00:00` + // 8 AM departure
  `&access_token=${token}`
);

// Compare to evening rush hour
const eveningCommute = await fetch(
  `...&depart_at=2026-02-05T17:00:00` // 5 PM departure
);

// Visualize difference to show traffic impact
```

---

### 7. Static Images API

**What It Does:**  
Generate static map images (PNG/JPEG) from Mapbox styles. No interactive map needed.

**How We Could Use It:**
- PDF reports with embedded maps
- Email notifications with site previews
- Thumbnail previews in site lists
- Print-ready materials for presentations

**Pricing:**
- **Free Tier:** 100,000 requests/month
- **Paid:** $0.50 per 1,000 requests

**Implementation Complexity:** ⭐ (1/5)
- URL-based API (no JavaScript needed)
- Can overlay GeoJSON, markers, paths

**Example:**
```html
<!-- Embed static map in report -->
<img src="https://api.mapbox.com/styles/v1/mapbox/streets-v12/static/
  geojson(%7B%22type%22%3A%22Point%22...)/
  -97.7431,30.2672,14,0/600x400@2x?access_token=..." 
  alt="Site Location">
```

---

## Dynamic Visualization Catalog

### 1. Animated Traffic Flow (Moving Lines & Pulses)

**Visual Description:**  
Animated lines that flow along road segments, with speed/color representing traffic volume. Pulsing circles at intersections.

**Use Case for Site Selection:**  
- Visualize customer flow patterns
- Show peak traffic hours with time-lapse
- Identify high-traffic corridors for signage visibility

**Implementation Approach:**
```javascript
// Pulse animation using circle-radius transition
map.addLayer({
  id: 'traffic-pulse',
  type: 'circle',
  source: 'traffic-counts',
  paint: {
    'circle-radius': [
      'interpolate', ['linear'], ['zoom'],
      12, ['*', ['get', 'traffic_count'], 0.01],
      16, ['*', ['get', 'traffic_count'], 0.05]
    ],
    'circle-color': [
      'interpolate', ['linear'], ['get', 'traffic_count'],
      1000, '#fee5d9',
      5000, '#fc8d59',
      10000, '#e34a33',
      20000, '#b30000'
    ],
    'circle-opacity': [
      'interpolate', ['linear'], ['zoom'],
      12, 0.6,
      16, 0.8
    ],
    // Pulse effect with transition
    'circle-stroke-width': 4,
    'circle-stroke-color': '#fff',
    'circle-stroke-opacity': [
      'interpolate', ['linear'], 
      ['%', ['/', ['-', ['number', ['get', 'timestamp']], Date.now()], 1000], 2],
      0, 0.8,
      1, 0
    ]
  }
});

// Animate along route
function animateTrafficFlow(route, speed) {
  let step = 0;
  const steps = 100;
  
  const animate = () => {
    const point = turf.along(route, (step / steps) * turf.length(route));
    
    map.getSource('flow-point').setData({
      type: 'Feature',
      geometry: point.geometry
    });
    
    step = (step + 1) % steps;
    requestAnimationFrame(animate);
  };
  
  animate();
}
```

**Performance Considerations:**
- Limit to visible viewport
- Use `requestAnimationFrame` for smooth 60fps
- Throttle updates for large datasets (max 1000 animated points)

**Implementation Complexity:** ⭐⭐⭐⭐ (4/5)

---

### 2. Dynamic Population Density (Expanding Spheres)

**Visual Description:**  
3D columns that grow/shrink based on data. Population density as height, with gradient colors. Can pulse or breathe.

**Use Case for Site Selection:**  
- Compare population density across neighborhoods
- Identify underserved high-density areas
- Visualize demographic changes over time

**Implementation Approach:**
```javascript
map.addLayer({
  id: 'population-extrusion',
  type: 'fill-extrusion',
  source: 'census-blocks',
  paint: {
    // Height based on population density
    'fill-extrusion-height': [
      '*',
      ['get', 'population_density'],
      5 // Scale factor
    ],
    
    // Color gradient
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'population_density'],
      0, '#ffffcc',
      100, '#41b6c4',
      500, '#253494'
    ],
    
    // Opacity for see-through effect
    'fill-extrusion-opacity': 0.7,
    
    // Vertical gradient for depth
    'fill-extrusion-vertical-gradient': true
  }
});

// Breathing effect
let breathePhase = 0;
setInterval(() => {
  breathePhase += 0.1;
  const scale = 1 + Math.sin(breathePhase) * 0.2; // ±20% height variation
  
  map.setPaintProperty('population-extrusion', 'fill-extrusion-height', [
    '*',
    ['*', ['get', 'population_density'], 5],
    scale
  ]);
}, 50);
```

**Performance Considerations:**
- Fill-extrusion is GPU-accelerated (very performant)
- Limit breathing animation to <500 polygons
- Use vector tiles for large datasets

**Implementation Complexity:** ⭐⭐⭐ (3/5)

---

### 3. Radiating Store Influence (Pulsing Catchment Areas)

**Visual Description:**  
Concentric circles radiating outward from stores. Opacity fades with distance. Can overlap to show competitive zones.

**Use Case for Site Selection:**  
- Visualize store trade areas
- Identify gaps in coverage
- Show competitive overlap ("catchment area battles")
- Animate customer acquisition zones

**Implementation Approach:**
```javascript
// Create multiple expanding circles
const createInfluenceRings = (store, maxRadius) => {
  const rings = [];
  const ringCount = 5;
  
  for (let i = 0; i < ringCount; i++) {
    const radius = (maxRadius / ringCount) * (i + 1);
    const circle = turf.circle(store.coordinates, radius, {
      steps: 64,
      units: 'miles',
      properties: {
        store_id: store.id,
        ring_index: i,
        opacity: 1 - (i / ringCount)
      }
    });
    rings.push(circle);
  }
  
  return turf.featureCollection(rings);
};

map.addLayer({
  id: 'influence-rings',
  type: 'fill',
  source: {
    type: 'geojson',
    data: createInfluenceRings(selectedStore, 3)
  },
  paint: {
    'fill-color': [
      'match', ['get', 'store_id'],
      'store-1', '#ff0000',
      'store-2', '#00ff00',
      'store-3', '#0000ff',
      '#cccccc'
    ],
    'fill-opacity': ['get', 'opacity']
  }
});

// Pulse animation
let pulseRadius = 0;
const pulse = () => {
  pulseRadius = (pulseRadius + 0.1) % 3;
  
  map.getSource('influence-rings').setData(
    createInfluenceRings(selectedStore, pulseRadius)
  );
  
  requestAnimationFrame(pulse);
};
pulse();
```

**Alternative: Shader-Based Ripples (Advanced)**
```javascript
// Custom layer with WebGL shader for smooth ripples
const RippleLayer = {
  id: 'ripples',
  type: 'custom',
  
  onAdd(map, gl) {
    // Create shader program
    this.program = createShaderProgram(gl, vertexShader, fragmentShader);
    // ... WebGL setup
  },
  
  render(gl, matrix) {
    // Draw animated ripples with fragment shader
    // Much smoother than GeoJSON approach
  }
};
```

**Performance Considerations:**
- GeoJSON approach: <50 animated stores simultaneously
- WebGL shader: Can handle 1000+ stores smoothly

**Implementation Complexity:**  
- GeoJSON: ⭐⭐⭐ (3/5)  
- WebGL: ⭐⭐⭐⭐⭐ (5/5)

---

### 4. Time-Based Traffic Patterns (Hourly Heat Animation)

**Visual Description:**  
Heatmap that animates through 24-hour cycle. Color intensity shows traffic volume by hour. Scrubber to pause/seek.

**Use Case for Site Selection:**  
- Identify peak hours for different locations
- Compare morning vs. evening commute patterns
- Optimize store hours based on traffic
- Plan grand opening for maximum visibility

**Implementation Approach:**
```javascript
// Traffic data with hourly breakdown
const trafficByHour = {
  type: 'FeatureCollection',
  features: locations.map(loc => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: loc.coords },
    properties: {
      hour_0: 120,  hour_1: 80,  hour_2: 50,  // ... to hour_23
      hour_6: 2500, hour_7: 4500, hour_8: 6000, // Morning rush
      hour_17: 5800, hour_18: 5200 // Evening rush
    }
  }))
};

let currentHour = 0;

map.addLayer({
  id: 'traffic-heatmap',
  type: 'heatmap',
  source: {
    type: 'geojson',
    data: trafficByHour
  },
  paint: {
    // Dynamic weight based on current hour
    'heatmap-weight': [
      'interpolate', ['linear'],
      ['get', `hour_${currentHour}`],
      0, 0,
      10000, 1
    ],
    
    'heatmap-intensity': [
      'interpolate', ['linear'], ['zoom'],
      0, 1,
      15, 3
    ],
    
    'heatmap-color': [
      'interpolate', ['linear'], ['heatmap-density'],
      0, 'rgba(33,102,172,0)',
      0.2, 'rgb(103,169,207)',
      0.4, 'rgb(209,229,240)',
      0.6, 'rgb(253,219,199)',
      0.8, 'rgb(239,138,98)',
      1, 'rgb(178,24,43)'
    ],
    
    'heatmap-radius': [
      'interpolate', ['linear'], ['zoom'],
      10, 20,
      15, 40
    ]
  }
});

// Time slider control
const animateHours = () => {
  currentHour = (currentHour + 1) % 24;
  
  map.setPaintProperty('traffic-heatmap', 'heatmap-weight', [
    'interpolate', ['linear'],
    ['get', `hour_${currentHour}`],
    0, 0,
    10000, 1
  ]);
  
  document.getElementById('hour-label').textContent = 
    `${currentHour}:00 ${currentHour < 12 ? 'AM' : 'PM'}`;
};

// Auto-play or scrubber control
let intervalId = setInterval(animateHours, 500); // 2 hours per second
```

**Performance Considerations:**
- Heatmap layer is GPU-accelerated (excellent performance)
- Can handle 10k+ points easily
- Smooth transitions built-in

**Implementation Complexity:** ⭐⭐⭐ (3/5)

---

### 5. Data-Driven 3D Bars (Store Performance)

**Visual Description:**  
3D columns representing metrics (sales, revenue, customer count). Height = value, color = trend. Grows/shrinks on update.

**Use Case for Site Selection:**  
- Compare store performance across locations
- Visualize revenue potential predictions
- Show demographic metrics (income, population)
- Before/after site selection impact

**Implementation Approach:**
```javascript
map.addLayer({
  id: 'store-performance',
  type: 'fill-extrusion',
  source: {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: stores.map(store => turf.circle(
        store.coordinates,
        0.1, // radius in km
        { 
          properties: {
            revenue: store.monthlyRevenue,
            trend: store.revenueGrowth, // positive or negative
            name: store.name
          }
        }
      ))
    }
  },
  paint: {
    // Height represents revenue
    'fill-extrusion-height': [
      '*',
      ['get', 'revenue'],
      0.001 // Scale: $1000 = 1 meter
    ],
    
    // Color represents trend
    'fill-extrusion-color': [
      'case',
      ['>', ['get', 'trend'], 0.05], '#10b981', // Green: growing
      ['<', ['get', 'trend'], -0.05], '#ef4444', // Red: declining
      '#fbbf24' // Yellow: stable
    ],
    
    'fill-extrusion-opacity': 0.8,
    
    // Animated transition on data update
    'fill-extrusion-transition': {
      duration: 1000,
      delay: 0
    }
  }
});

// Smooth update animation
const updateStoreData = (newData) => {
  const currentData = map.getSource('store-performance')._data;
  
  // Tween between old and new values
  let progress = 0;
  const animate = () => {
    progress += 0.05;
    
    const interpolatedData = {
      type: 'FeatureCollection',
      features: currentData.features.map((feature, i) => ({
        ...feature,
        properties: {
          ...feature.properties,
          revenue: lerp(
            feature.properties.revenue,
            newData[i].revenue,
            progress
          )
        }
      }))
    };
    
    map.getSource('store-performance').setData(interpolatedData);
    
    if (progress < 1) requestAnimationFrame(animate);
  };
  
  animate();
};
```

**Performance Considerations:**
- Excellent performance (GPU-accelerated)
- Can render 1000+ extruded features smoothly
- Transitions built into Mapbox GL JS

**Implementation Complexity:** ⭐⭐ (2/5)

---

### 6. Particle System Traffic Flow

**Visual Description:**  
Thousands of tiny particles flowing along roads. Density = traffic volume. Speed = average speed. Color = congestion level.

**Use Case for Site Selection:**  
- Highly engaging visualization for presentations
- Show real-time traffic patterns
- Identify traffic bottlenecks and flow patterns
- Create "wow factor" for executive demos

**Implementation Approach:**
```javascript
// Custom WebGL layer for particle system
const ParticleLayer = {
  id: 'traffic-particles',
  type: 'custom',
  
  particles: [],
  
  onAdd(map, gl) {
    // Create particle positions along road network
    this.particles = this.initializeParticles(roadNetwork, 5000);
    
    // Setup WebGL buffers and shaders
    this.program = createParticleShader(gl);
    this.buffer = gl.createBuffer();
  },
  
  initializeParticles(roads, count) {
    const particles = [];
    
    for (let i = 0; i < count; i++) {
      // Random road segment
      const road = roads[Math.floor(Math.random() * roads.length)];
      const point = turf.along(road, Math.random() * turf.length(road));
      
      particles.push({
        position: point.geometry.coordinates,
        velocity: road.properties.speed * 0.001,
        color: getColorBySpeed(road.properties.speed),
        progress: Math.random()
      });
    }
    
    return particles;
  },
  
  render(gl, matrix) {
    // Update particle positions
    this.particles.forEach(p => {
      p.progress += p.velocity;
      if (p.progress > 1) p.progress = 0;
      
      // Interpolate along road segment
      p.position = this.interpolatePosition(p);
    });
    
    // Draw all particles in single draw call
    this.drawParticles(gl, this.particles, matrix);
  }
};

map.addLayer(ParticleLayer);
```

**Simplified Canvas-Based Alternative:**
```javascript
// Easier but less performant
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');

map.addSource('particles', {
  type: 'canvas',
  canvas: canvas,
  coordinates: bounds,
  animate: true
});

function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  particles.forEach(p => {
    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
    ctx.fill();
  });
  
  requestAnimationFrame(render);
}
```

**Performance Considerations:**
- WebGL: Can handle 10,000+ particles at 60fps
- Canvas: Limit to <1000 particles
- Use spatial indexing to only render visible particles

**Implementation Complexity:**  
- WebGL: ⭐⭐⭐⭐⭐ (5/5)  
- Canvas: ⭐⭐⭐⭐ (4/5)

---

### 7. Competitive Heatmap (Real-Time Updates)

**Visual Description:**  
Live-updating heatmap showing competitive intensity. Multiple stores create overlapping zones. Color gradient shows competition density.

**Use Case for Site Selection:**  
- Identify saturated markets (red zones)
- Find underserved areas (blue/green zones)
- Visualize competitive pressure in real-time
- Simulate impact of new store locations

**Implementation Approach:**
```javascript
// Calculate competitive pressure at each point
const calculateCompetitivePressure = (point, competitors) => {
  let pressure = 0;
  
  competitors.forEach(comp => {
    const distance = turf.distance(point, comp.location, { units: 'miles' });
    const influence = comp.size / Math.pow(distance, 2); // Gravity model
    pressure += influence;
  });
  
  return pressure;
};

// Create heatmap grid
const createCompetitiveHeatmap = (bounds, competitors, resolution) => {
  const grid = [];
  const cellSize = resolution; // miles
  
  for (let lat = bounds.south; lat < bounds.north; lat += cellSize) {
    for (let lon = bounds.west; lon < bounds.east; lon += cellSize) {
      const point = [lon, lat];
      const pressure = calculateCompetitivePressure(point, competitors);
      
      grid.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: point },
        properties: { pressure }
      });
    }
  }
  
  return { type: 'FeatureCollection', features: grid };
};

map.addLayer({
  id: 'competitive-heatmap',
  type: 'heatmap',
  source: {
    type: 'geojson',
    data: createCompetitiveHeatmap(viewport, competitors, 0.1)
  },
  paint: {
    'heatmap-weight': [
      'interpolate', ['linear'], ['get', 'pressure'],
      0, 0,
      10, 1
    ],
    'heatmap-color': [
      'interpolate', ['linear'], ['heatmap-density'],
      0, 'rgba(0, 255, 0, 0)',      // Green: low competition
      0.5, 'rgba(255, 255, 0, 0.5)', // Yellow: medium
      1, 'rgba(255, 0, 0, 0.9)'      // Red: high competition
    ],
    'heatmap-radius': 50,
    'heatmap-intensity': 1.5
  }
});

// Real-time update when adding potential site
const addPotentialSite = (location) => {
  competitors.push({
    location,
    size: predictedStoreSize,
    type: 'potential'
  });
  
  // Recalculate and update heatmap
  const newHeatmap = createCompetitiveHeatmap(viewport, competitors, 0.1);
  map.getSource('competitive-heatmap').setData(newHeatmap);
};
```

**Performance Considerations:**
- Pre-calculate grid at appropriate resolution (balance detail vs. performance)
- Update only affected grid cells when adding/removing competitors
- Use web worker for calculations if grid is large

**Implementation Complexity:** ⭐⭐⭐⭐ (4/5)

---

### 8. Time-Lapse Visualization (Historical Growth)

**Visual Description:**  
Animated playback showing how an area developed over time. Stores appear/disappear, demographics shift, traffic patterns evolve.

**Use Case for Site Selection:**  
- Show historical growth trends
- Predict future development
- Identify emerging neighborhoods
- Demonstrate market saturation over time

**Implementation Approach:**
```javascript
// Historical snapshots
const historicalData = {
  '2015': { stores: [...], population: [...], traffic: [...] },
  '2016': { stores: [...], population: [...], traffic: [...] },
  // ... through 2026
};

let currentYear = 2015;

// Layer for stores with temporal filtering
map.addLayer({
  id: 'historical-stores',
  type: 'circle',
  source: {
    type: 'geojson',
    data: allStoresWithTimestamps
  },
  filter: ['<=', ['get', 'opened_year'], currentYear],
  paint: {
    'circle-radius': [
      'interpolate', ['linear'],
      ['-', currentYear, ['get', 'opened_year']],
      0, 8,   // Just opened
      5, 6,   // 5 years old
      10, 5   // 10 years old
    ],
    'circle-color': [
      'interpolate', ['linear'],
      ['-', currentYear, ['get', 'opened_year']],
      0, '#00ff00',   // Bright green: new
      5, '#ffff00',   // Yellow: established
      10, '#ff6600'   // Orange: mature
    ],
    'circle-opacity': 0.8
  }
});

// Time scrubber
const playTimeLapse = () => {
  const startYear = 2015;
  const endYear = 2026;
  
  const animate = () => {
    currentYear += 1;
    
    if (currentYear > endYear) currentYear = startYear;
    
    // Update filters
    map.setFilter('historical-stores', 
      ['<=', ['get', 'opened_year'], currentYear]
    );
    
    // Update population layer
    map.getSource('population').setData(historicalData[currentYear].population);
    
    // Update UI
    document.getElementById('year-display').textContent = currentYear;
    
    setTimeout(animate, 500); // 2 years per second
  };
  
  animate();
};
```

**Performance Considerations:**
- Use filter expressions instead of swapping data sources (faster)
- Pre-load all historical data
- Use data-driven styling to avoid layer recreation

**Implementation Complexity:** ⭐⭐⭐ (3/5)

---

## Advanced Mapbox GL JS Features

### 1. Expressions (Data-Driven Styling)

**What We're Likely Missing:**  
Expressions are the secret weapon of Mapbox GL JS. They allow incredibly powerful data-driven styling without JavaScript.

**Advanced Expression Examples:**

**Conditional Styling:**
```javascript
// Color-code traffic counts with thresholds
'circle-color': [
  'case',
  ['<', ['get', 'traffic_count'], 1000], '#fee5d9',
  ['<', ['get', 'traffic_count'], 5000], '#fcae91',
  ['<', ['get', 'traffic_count'], 10000], '#fb6a4a',
  '#cb181d'
]
```

**Math Operations:**
```javascript
// Calculate and visualize store performance index
'fill-extrusion-height': [
  '*',
  [
    '+',
    ['/', ['get', 'monthly_revenue'], 1000],
    ['*', ['get', 'customer_count'], 0.1],
    ['*', ['get', 'avg_transaction'], 5]
  ],
  10 // Scale factor
]
```

**String Manipulation:**
```javascript
// Dynamic labels with formatting
'text-field': [
  'concat',
  ['get', 'store_name'],
  '\n',
  '$',
  ['to-string', ['round', ['get', 'monthly_revenue']]],
  'K'
]
```

**Zoom-Based Transitions:**
```javascript
// Smooth size transitions as you zoom
'circle-radius': [
  'interpolate', ['exponential', 2],
  ['zoom'],
  10, ['*', ['get', 'importance'], 2],
  15, ['*', ['get', 'importance'], 8],
  18, ['*', ['get', 'importance'], 20]
]
```

**Date/Time Operations:**
```javascript
// Show only recent data
'circle-opacity': [
  'interpolate', ['linear'],
  ['-', ['number', ['get', 'timestamp']], Date.now()],
  -86400000, 1,    // Last 24 hours: full opacity
  -604800000, 0.3  // Last week: faded
]
```

**Implementation Complexity:** ⭐⭐ (2/5) - Already using basic expressions

---

### 2. 3D Terrain & Extrusions

**Advanced 3D Capabilities:**

**Terrain Elevation:**
```javascript
map.addSource('mapbox-dem', {
  type: 'raster-dem',
  url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
  tileSize: 512,
  maxzoom: 14
});

map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 });

// Visualize stores on actual terrain
// Great for hilly/mountainous regions
```

**Custom 3D Buildings:**
```javascript
// Not just store data - extrude building footprints
map.addLayer({
  id: 'custom-3d-buildings',
  source: 'composite',
  'source-layer': 'building',
  type: 'fill-extrusion',
  minzoom: 15,
  paint: {
    'fill-extrusion-color': [
      'case',
      ['boolean', ['feature-state', 'selected'], false],
      '#ff0000', // Selected building in red
      '#aaa'
    ],
    'fill-extrusion-height': [
      'interpolate', ['linear'], ['zoom'],
      15, 0,
      15.05, ['get', 'height']
    ],
    'fill-extrusion-base': ['get', 'min_height'],
    'fill-extrusion-opacity': 0.6
  }
});
```

**Implementation Complexity:** ⭐⭐ (2/5)

---

### 3. Custom Layers (WebGL)

**When to Use:**  
When you need complete rendering control - particle systems, custom effects, advanced animations.

**Example: Heatmap with Custom Decay:**
```javascript
const CustomHeatmapLayer = {
  id: 'custom-heatmap',
  type: 'custom',
  
  onAdd(map, gl) {
    // Compile shaders
    const vertexShader = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
    this.program = linkProgram(gl, vertexShader, fragmentShader);
    
    // Create texture for heatmap
    this.texture = gl.createTexture();
    this.framebuffer = gl.createFramebuffer();
  },
  
  render(gl, matrix) {
    // Custom rendering logic
    gl.useProgram(this.program);
    
    // Set uniforms
    gl.uniformMatrix4fv(this.matrixLocation, false, matrix);
    gl.uniform1f(this.decayLocation, 0.95); // Custom decay rate
    
    // Draw
    gl.drawArrays(gl.POINTS, 0, this.pointCount);
  }
};
```

**Implementation Complexity:** ⭐⭐⭐⭐⭐ (5/5)

---

### 4. Sky Layers

**Use Case:**  
Atmospheric lighting for time-of-day visualizations.

```javascript
map.addLayer({
  id: 'sky',
  type: 'sky',
  paint: {
    'sky-type': 'atmosphere',
    'sky-atmosphere-sun': [0.0, 90.0], // Sun position
    'sky-atmosphere-sun-intensity': 15
  }
});

// Animate sun position for time-lapse
function setSunPosition(hour) {
  const sunAngle = (hour / 24) * 360 - 90;
  map.setPaintProperty('sky', 'sky-atmosphere-sun', [
    sunAngle, 
    Math.max(0, 90 - Math.abs(sunAngle - 90))
  ]);
}
```

**Implementation Complexity:** ⭐ (1/5)

---

## Data Integration Strategies

### Managing 7k+ Traffic Count Features

**Current Approach (Client-Side GeoJSON):**
```
❌ 7000+ features loaded in browser
❌ Slow initial load
❌ No persistence between sessions
❌ Difficult to update/sync
```

**Recommended Approach:**

**Option 1: Datasets API (Best for Frequently Updated Data)**
```javascript
// One-time: Upload to Datasets
const uploadTrafficData = async (features) => {
  // Create dataset
  const dataset = await createDataset('traffic-counts');
  
  // Batch upload features
  for (const feature of features) {
    await putFeature(dataset.id, feature.id, feature);
  }
  
  // Convert to tileset for rendering
  await publishDataset(dataset.id);
};

// In app: Reference dataset as source
map.addSource('traffic', {
  type: 'vector',
  url: `mapbox://username.dataset-id`
});

// Update individual features
const updateTrafficCount = async (locationId, newCount) => {
  await fetch(`/datasets/v1/${username}/${datasetId}/features/${locationId}`, {
    method: 'PUT',
    body: JSON.stringify({
      ...existingFeature,
      properties: { 
        ...existingFeature.properties, 
        count: newCount, 
        updated: Date.now() 
      }
    })
  });
};
```

**Option 2: Mapbox Tiling Service (Best for Large Static Data)**
```javascript
// Generate tileset from GeoJSON
// Command-line or API
tilesets upload-source username traffic-source ./traffic-counts.geojson

// Create recipe (styling rules)
const recipe = {
  version: 1,
  layers: {
    traffic: {
      source: 'mapbox://tileset-source/username/traffic-source',
      minzoom: 0,
      maxzoom: 16,
      features: {
        attributes: {
          allowed_output: [
            'id',
            'count',
            'location_type',
            'last_updated'
          ]
        }
      }
    }
  }
};

// Publish tileset
tilesets publish username.traffic-tileset recipe.json

// In app: Super fast vector tiles
map.addSource('traffic', {
  type: 'vector',
  url: 'mapbox://username.traffic-tileset'
});
```

**Performance Comparison:**

| Approach | Initial Load | Update Speed | Best For |
|----------|--------------|--------------|----------|
| Client-side JSON | 5-10s (7k features) | Instant (local) | <1k features |
| Datasets API | <1s (vector tiles) | Fast (API call) | Frequently updated |
| Tiling Service | <1s (optimized tiles) | Slow (re-publish) | Large, static data |

**Recommendation:** Use **Datasets API** for traffic counts (enable real-time updates) + **Tiling Service** for parcels/boundaries (large, static).

---

### Real-Time Data Streaming

**WebSocket Pattern:**
```javascript
const ws = new WebSocket('wss://your-api.com/traffic-updates');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  
  // Update specific feature in source
  const source = map.getSource('traffic');
  const features = source._data.features;
  
  const featureIndex = features.findIndex(f => f.id === update.id);
  if (featureIndex !== -1) {
    features[featureIndex].properties.count = update.count;
    source.setData({ type: 'FeatureCollection', features });
  }
};
```

**Server-Sent Events (SSE) Pattern:**
```javascript
const eventSource = new EventSource('/api/traffic-stream');

eventSource.onmessage = (event) => {
  const updates = JSON.parse(event.data);
  
  // Batch update for better performance
  batchUpdateFeatures(map, 'traffic', updates);
};

function batchUpdateFeatures(map, sourceId, updates) {
  const source = map.getSource(sourceId);
  const data = source._data;
  
  updates.forEach(update => {
    const feature = data.features.find(f => f.id === update.id);
    if (feature) {
      Object.assign(feature.properties, update.properties);
    }
  });
  
  source.setData(data);
}
```

**Implementation Complexity:** ⭐⭐⭐ (3/5)

---

### Vector Tile Optimization

**Best Practices:**

1. **Simplify Geometries at Different Zoom Levels**
```javascript
// In tileset recipe
{
  layers: {
    parcels: {
      minzoom: 12,
      maxzoom: 16,
      tiles: {
        bbox: [-180, -85, 180, 85],
        geometry: {
          // Simplify more at lower zooms
          simplification: 'zoom'
        }
      }
    }
  }
}
```

2. **Filter Features by Zoom**
```javascript
// Don't show all stores at country-level zoom
map.addLayer({
  id: 'stores',
  type: 'circle',
  source: 'stores',
  minzoom: 10, // Only show zoomed in
  filter: [
    'any',
    ['>=', ['zoom'], 14], // Always show when close
    ['>=', ['get', 'importance'], 8] // Show important stores earlier
  ]
});
```

3. **Use Appropriate Tile Sizes**
```javascript
// Larger tiles = fewer requests, larger downloads
map.addSource('optimized', {
  type: 'vector',
  tiles: ['https://api.mapbox.com/v4/{tileset}/{z}/{x}/{y}.mvt'],
  tileSize: 512, // Default is 512, can use 256 for more granular
  maxzoom: 14
});
```

---

## Unique/Creative Use Cases

### 1. Animated Customer Flow Models

**Concept:** Simulate customer movement from residential areas to stores using gravity model + animated particles.

**Implementation:**
```javascript
// Calculate customer attraction using Huff model
const calculateHuffProbability = (customer, store, allStores) => {
  const distance = turf.distance(customer, store);
  const attractiveness = store.size / Math.pow(distance, 2);
  
  const totalAttraction = allStores.reduce((sum, s) => {
    const d = turf.distance(customer, s);
    return sum + (s.size / Math.pow(d, 2));
  }, 0);
  
  return attractiveness / totalAttraction;
};

// Create flow lines
const createCustomerFlows = (residentialBlocks, stores) => {
  const flows = [];
  
  residentialBlocks.forEach(block => {
    stores.forEach(store => {
      const probability = calculateHuffProbability(block, store, stores);
      
      if (probability > 0.1) { // Only show significant flows
        flows.push({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [block.coordinates, store.coordinates]
          },
          properties: {
            volume: block.population * probability,
            probability
          }
        });
      }
    });
  });
  
  return { type: 'FeatureCollection', features: flows };
};

// Animate particles along flows
// (Use particle system from earlier)
```

**Business Value:** Visualize which areas feed which stores; identify opportunities to capture underserved populations.

---

### 2. Catchment Area Battles

**Concept:** Two competing stores fight for territory. Animated border shows the dividing line shifting as you change store attributes.

```javascript
// Calculate Voronoi tessellation
const createVoronoiTerritories = (stores) => {
  const points = turf.featureCollection(
    stores.map(s => turf.point(s.coordinates, { id: s.id, size: s.size }))
  );
  
  // Weighted Voronoi based on store size
  const voronoi = turf.voronoi(points, { bbox: mapBounds });
  
  return voronoi;
};

// Animate territory expansion
const animateTerritoryChange = (oldTerritories, newTerritories) => {
  let step = 0;
  const steps = 30;
  
  const animate = () => {
    const interpolated = interpolatePolygons(
      oldTerritories, 
      newTerritories, 
      step / steps
    );
    
    map.getSource('territories').setData(interpolated);
    
    step++;
    if (step <= steps) requestAnimationFrame(animate);
  };
  
  animate();
};
```

---

### 3. Predictive Opportunity Zones (AI-Driven)

**Concept:** Machine learning model predicts ideal store locations. Visualize as glowing zones with confidence levels.

```javascript
// ML model outputs probability grid
const opportunityZones = await fetch('/api/ml/predict-zones', {
  method: 'POST',
  body: JSON.stringify({
    demographics: selectedDemographics,
    traffic: trafficData,
    competitors: competitorLocations
  })
});

// Visualize as contoured heatmap
map.addLayer({
  id: 'opportunity-zones',
  type: 'heatmap',
  source: {
    type: 'geojson',
    data: opportunityZones
  },
  paint: {
    'heatmap-weight': ['get', 'probability'],
    'heatmap-color': [
      'interpolate', ['linear'], ['heatmap-density'],
      0, 'rgba(0, 0, 255, 0)',      // Blue: low probability
      0.5, 'rgba(255, 255, 0, 0.5)', // Yellow: medium
      1, 'rgba(0, 255, 0, 0.9)'      // Green: high probability
    ],
    'heatmap-intensity': 2
  }
});

// Add glow effect to high-confidence zones
map.addLayer({
  id: 'opportunity-glow',
  type: 'circle',
  source: {
    type: 'geojson',
    data: highConfidencePoints
  },
  paint: {
    'circle-radius': 40,
    'circle-color': '#00ff00',
    'circle-blur': 1,
    'circle-opacity': [
      'interpolate', ['linear'], ['get', 'confidence'],
      0.7, 0.3,
      1.0, 0.8
    ]
  }
});
```

---

## Priority Recommendations

### Quick Wins (High Value, Low Effort)

| Feature | Value | Effort | Time to Implement | Cost |
|---------|-------|--------|-------------------|------|
| **Data-Driven Expressions** | ⭐⭐⭐⭐⭐ | ⭐⭐ | 1 week | $0 |
| Dynamic color-coding, responsive sizing, computed labels | Traffic counts by threshold, store performance indicators | Refactor existing layers | Already in GL JS | Free |
| **3D Extrusions** | ⭐⭐⭐⭐⭐ | ⭐ | 3 days | $0 |
| Population density, revenue visualization | Instant 3D visualization of metrics | Add fill-extrusion layers | Already in GL JS | Free |
| **Time Slider for Traffic** | ⭐⭐⭐⭐ | ⭐⭐⭐ | 1 week | $0 |
| Show traffic patterns by hour | Identify peak times | Filter expression + UI slider | Already in GL JS | Free |
| **Improved Isochrones** | ⭐⭐⭐⭐ | ⭐ | 2 days | $0* |
| Traffic-aware, time-based routing | More accurate catchment areas | Add depart_at parameter | API calls (within free tier) | Free* |

**Total Quick Wins:** 2-3 weeks, $0 additional cost

---

### Strategic Investments (High Value, High Effort)

| Feature | Value | Effort | Time to Implement | Cost |
|---------|-------|--------|-------------------|------|
| **Matrix API Integration** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 2 weeks | $50-200/mo |
| Multi-point competitive analysis | Calculate all competitor distances | API integration + viz | Paid tier likely needed | Est. $100/mo |
| **Datasets API Migration** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 3-4 weeks | $0 |
| Server-side data management | Scale to 100k+ features, real-time updates | Migrate 7k+ features | Backend development | Free tier adequate |
| **Custom WebGL Layer** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 4-6 weeks | $0 |
| Particle systems, custom effects | "Wow factor" for demos | Advanced WebGL programming | Already in GL JS | Free |
| **Predictive ML Zones** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 8-12 weeks | Variable |
| AI-driven site recommendations | Data science + prediction model | ML pipeline + API + viz | Model development + cloud costs | $500-2000/mo |

**Total Strategic:** 4-6 months, $50-500/mo ongoing

---

### Nice-to-Haves (Low Effort Experiments)

| Feature | Value | Effort | Time to Implement |
|---------|-------|--------|-------------------|
| **Static Images API** | ⭐⭐⭐ | ⭐ | 1 day |
| PDF reports with maps | Simple URL-based | Already in free tier |
| **Sky Layer** | ⭐⭐ | ⭐ | 2 hours |
| Time-of-day atmosphere | Single layer config | Aesthetic improvement |
| **Animated Markers** | ⭐⭐⭐ | ⭐⭐ | 3 days |
| Pulsing store locations | CSS + symbol layer | Visual polish |
| **Geocoding Autocomplete** | ⭐⭐⭐⭐ | ⭐⭐ | 1 week |
| Better address search | Replace current geocoder | UX improvement |

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4) - $0 Cost

**Goal:** Maximize current GL JS capabilities without new APIs.

**Week 1: Expressions & Dynamic Styling**
- [ ] Refactor traffic count layer with data-driven colors
- [ ] Add zoom-responsive sizing
- [ ] Implement computed labels (traffic volume, store performance)
- [ ] Test performance with 7k+ features

**Week 2: 3D Visualizations**
- [ ] Add fill-extrusion layer for population density
- [ ] Create 3D bars for store revenue
- [ ] Implement smooth transitions on data updates
- [ ] Add pitch/bearing controls

**Week 3: Time-Based Animations**
- [ ] Build time slider component (React)
- [ ] Implement hourly traffic filter
- [ ] Create heatmap animation (24-hour cycle)
- [ ] Add play/pause controls

**Week 4: Isochrone Improvements**
- [ ] Add traffic-aware isochrones
- [ ] Implement time-of-day routing (depart_at)
- [ ] Create comparison view (AM vs PM)
- [ ] Style with gradient colors

**Deliverable:** Significantly enhanced visualizations with zero additional cost.

---

### Phase 2: Data Infrastructure (Weeks 5-8) - $0-50/mo

**Goal:** Migrate to server-side data management.

**Week 5: Datasets API Setup**
- [ ] Create Mapbox datasets for traffic counts
- [ ] Build upload script (one-time migration)
- [ ] Test read/write operations
- [ ] Benchmark performance vs. client-side

**Week 6: Integration**
- [ ] Update map sources to use Datasets
- [ ] Implement real-time update API
- [ ] Build admin interface for data management
- [ ] Add optimistic updates (client-side prediction)

**Week 7: Tiling Service**
- [ ] Upload parcel data to Tiling Service
- [ ] Create tileset recipes
- [ ] Optimize zoom-level simplification
- [ ] Replace client-side parcel rendering

**Week 8: Testing & Optimization**
- [ ] Load testing (10k+ concurrent users)
- [ ] Performance monitoring
- [ ] Error handling & retry logic
- [ ] Documentation

**Deliverable:** Scalable data architecture supporting 100k+ features.

---

### Phase 3: Advanced Analytics (Weeks 9-12) - $100-200/mo

**Goal:** Add competitive analysis and route optimization.

**Week 9: Matrix API Integration**
- [ ] Build Matrix API wrapper service
- [ ] Create multi-point comparison UI
- [ ] Visualize travel time matrices
- [ ] Add export functionality (CSV, PDF)

**Week 10: Competitive Analysis**
- [ ] Implement competitive heatmap
- [ ] Add Voronoi territory visualization
- [ ] Build "catchment area battles" animation
- [ ] Create territory shift simulation

**Week 11: Directions API**
- [ ] Add route planning from stores
- [ ] Implement delivery zone modeling
- [ ] Create turn-by-turn directions
- [ ] Add traffic-aware routing

**Week 12: Integration & Polish**
- [ ] Combine Matrix + Directions + Isochrones
- [ ] Build unified "site analysis" workflow
- [ ] Create presentation mode
- [ ] User testing & refinement

**Deliverable:** Complete competitive analysis toolkit.

---

### Phase 4: Advanced Visualizations (Weeks 13-18) - Optional

**Goal:** Create unique, differentiated visualizations.

**Week 13-14: Particle Systems**
- [ ] Build WebGL particle layer
- [ ] Implement traffic flow animation
- [ ] Optimize for 60fps performance
- [ ] Add controls (speed, density)

**Week 15-16: Predictive Modeling**
- [ ] Train ML model on historical data
- [ ] Build opportunity zone predictor
- [ ] Create confidence visualization
- [ ] Add "what-if" scenario modeling

**Week 17-18: Custom Interactions**
- [ ] Build drag-to-compare tool
- [ ] Add drawing tools (custom areas)
- [ ] Implement snapshot/bookmark system
- [ ] Create shareable report links

**Deliverable:** Industry-leading visualization platform.

---

## Cost Summary

### Free Tier Usage (Sufficient for MVP)

| API | Free Tier | Expected Usage | Status |
|-----|-----------|----------------|--------|
| **Mapbox GL JS** | Unlimited | Core platform | ✅ Free forever |
| **Vector Tiles** | 200k tile loads/mo | ~50k/mo | ✅ Well within limit |
| **Datasets API** | 480 reads/min, 40 writes/min | ~100 reads/min | ✅ Free tier OK |
| **Isochrone** | 100k requests/mo | ~5k/mo | ✅ Free tier OK |
| **Geocoding** | 100k requests/mo | ~2k/mo | ✅ Free tier OK |
| **Static Images** | 100k requests/mo | ~1k/mo | ✅ Free tier OK |

**Total Cost with Free Tiers:** $0/month

---

### Paid Tier Estimates (When You Scale)

| API | Usage Scenario | Estimated Cost |
|-----|----------------|----------------|
| **Matrix API** | 10k elements/day (competitive analysis) | $50/mo |
| **Directions** | 5k routes/day (delivery planning) | $25/mo |
| **Tiling Service** | 500k tiles/mo (initial), then updates | $15/mo after initial |
| **Geocoding** | 200k requests/mo (autocomplete heavy) | $50/mo |

**Total Paid Tier:** $100-200/month (only if you significantly exceed free tier)

---

### Development Time Estimates

- **Phase 1 (Foundation):** 4 weeks, 1 developer
- **Phase 2 (Data Infrastructure):** 4 weeks, 1 developer + 0.5 backend dev
- **Phase 3 (Advanced Analytics):** 4 weeks, 1 developer
- **Phase 4 (Advanced Viz):** 6 weeks, 1 developer + 0.5 data scientist (optional)

**Total:** 3-4 months for core platform

---

## Key Takeaways

### What to Build First

1. **Week 1:** Data-driven expressions (instant visual upgrade, $0)
2. **Week 2:** 3D extrusions (huge impact, minimal effort)
3. **Week 3:** Time slider for traffic (unique insight)
4. **Week 4:** Traffic-aware isochrones (better than competitors)

**In 1 month:** You'll have a dramatically better platform at zero additional cost.

### What NOT to Build (Yet)

- ❌ **Custom WebGL layers** - Too much effort, diminishing returns until you've exhausted GL JS features
- ❌ **Real-time streaming** - Overkill unless you have live data sources
- ❌ **Video layers** - Cool but not valuable for site selection
- ❌ **ML predictions** - Build data foundation first, ML later

### The Golden Rule

> **Use Mapbox GL JS expressions before reaching for custom code.**

90% of dynamic visualizations can be achieved with expressions alone. They're:
- Faster (GPU-accelerated)
- Easier to maintain
- Zero runtime cost
- Better performance

Only build custom WebGL when expressions can't do it.

---

## Technical Best Practices

### Performance

1. **Vector Tiles > GeoJSON** for >1000 features
2. **Expressions > JavaScript** for styling
3. **Filter > Hide** features (don't remove layers)
4. **Simplify geometries** at lower zooms
5. **Limit real-time updates** to <60fps

### Data Management

1. **Datasets API** for frequently updated data (<10k features)
2. **Tiling Service** for large static data (>10k features)
3. **GeoJSON** for small dynamic data (<1k features)
4. **CDN caching** for tilesets (12-hour TTL)

### User Experience

1. **Progressive disclosure:** Show simple first, add detail on zoom
2. **Loading states:** Never show blank map
3. **Smooth transitions:** 300-500ms is ideal
4. **Responsive design:** Mobile-first for field work
5. **Accessibility:** Keyboard controls, ARIA labels

---

## Resources & Next Steps

### Essential Documentation
- [Mapbox GL JS Examples](https://docs.mapbox.com/mapbox-gl-js/example/) - 100+ copy-paste examples
- [Expression Reference](https://docs.mapbox.com/style-spec/reference/expressions/) - Complete syntax guide
- [API Playground](https://docs.mapbox.com/playground/) - Test APIs interactively

### Recommended Learning Path
1. **Week 1:** Master expressions (spend a full day in the playground)
2. **Week 2:** Explore all GL JS examples (copy/paste/modify)
3. **Week 3:** Build one advanced viz end-to-end
4. **Week 4:** Optimize and polish

### Community & Support
- [Mapbox Community Forum](https://github.com/mapbox/mapbox-gl-js/discussions)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/mapbox-gl-js) (mapbox-gl-js tag)
- [Mapbox Discord](https://discord.gg/mapbox)

---

## Conclusion

**You already have 80% of what you need.** Mapbox GL JS is incredibly powerful out-of-the-box. Before adding any new APIs:

1. Fully leverage **expressions** for dynamic styling
2. Use **3D extrusions** for dramatic visualizations  
3. Implement **time-based filtering** for traffic analysis
4. Enhance **isochrones** with traffic awareness

**Then** layer on:
- Datasets API (data management)
- Matrix API (competitive analysis)
- Tiling Service (performance at scale)

This research shows a clear path to building a world-class site selection platform while staying lean on costs and complexity.

**Start with Phase 1. Ship something impressive in 4 weeks. Then iterate.**

Good luck! 🚀
