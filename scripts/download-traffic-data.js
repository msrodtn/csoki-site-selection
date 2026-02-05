#!/usr/bin/env node
/**
 * Download Traffic Data from State DOT Services
 * 
 * Downloads traffic count data (AADT) from state ArcGIS services,
 * converts to clean GeoJSON, and prepares for Mapbox tileset upload.
 * 
 * Usage:
 *   node download-traffic-data.js IA
 *   node download-traffic-data.js NE
 *   node download-traffic-data.js all
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// State DOT ArcGIS services
const STATE_SERVICES = {
  IA: {
    name: 'Iowa',
    url: 'https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Data_view/FeatureServer/10',
    fields: 'AADT,ROUTEID,STATESIGNED,COUNTYSIGNED,AADT_YEAR',
    maxRecords: 2000,  // Service limit per request
  },
  // Add more states here as we find their services
  // NE: { name: 'Nebraska', url: '...', fields: '...' },
  // NV: { name: 'Nevada', url: '...', fields: '...' },
};

const OUTPUT_DIR = path.join(__dirname, '../data/traffic');

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

/**
 * Fetch data from ArcGIS REST service
 */
async function fetchArcGISData(url, params) {
  return new Promise((resolve, reject) => {
    const queryString = new URLSearchParams(params).toString();
    const fullUrl = `${url}/query?${queryString}`;
    
    console.log(`Fetching: ${fullUrl.substring(0, 100)}...`);
    
    https.get(fullUrl, (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
        } catch (e) {
          reject(new Error(`Failed to parse JSON: ${e.message}`));
        }
      });
    }).on('error', (err) => {
      reject(err);
    });
  });
}

/**
 * Download traffic data for a state with pagination
 */
async function downloadState(stateCode) {
  const service = STATE_SERVICES[stateCode];
  if (!service) {
    console.error(`Unknown state: ${stateCode}`);
    console.log(`Available: ${Object.keys(STATE_SERVICES).join(', ')}`);
    process.exit(1);
  }

  console.log(`\n📥 Downloading ${service.name} traffic data...`);

  try {
    const allFeatures = [];
    let offset = 0;
    const pageSize = service.maxRecords || 2000;
    let hasMore = true;

    // Paginate through all records
    while (hasMore) {
      console.log(`   Fetching records ${offset} - ${offset + pageSize}...`);

      const geojson = await fetchArcGISData(service.url, {
        where: '1=1',
        outFields: service.fields,
        returnGeometry: 'true',
        f: 'geojson',
        resultRecordCount: pageSize,
        resultOffset: offset,
      });

      if (geojson.features && geojson.features.length > 0) {
        allFeatures.push(...geojson.features);
        offset += geojson.features.length;

        // Check if there are more records
        hasMore = geojson.properties?.exceededTransferLimit ||
                  geojson.features.length === pageSize;
      } else {
        hasMore = false;
      }
    }

    if (allFeatures.length === 0) {
      console.error('❌ No features returned!');
      return;
    }

    console.log(`✅ Downloaded ${allFeatures.length} road segments`);

    // Clean up the GeoJSON
    const cleaned = {
      type: 'FeatureCollection',
      features: allFeatures.map(feature => ({
        type: 'Feature',
        geometry: feature.geometry,
        properties: {
          aadt: feature.properties.AADT || 0,
          route: feature.properties.ROUTEID || feature.properties.STATESIGNED || 'Unknown',
          year: feature.properties.AADT_YEAR || null,
        },
      })),
    };

    // Save to file
    const outputPath = path.join(OUTPUT_DIR, `${stateCode.toLowerCase()}-traffic.geojson`);
    fs.writeFileSync(outputPath, JSON.stringify(cleaned, null, 2));

    console.log(`💾 Saved to: ${outputPath}`);
    console.log(`📊 File size: ${(fs.statSync(outputPath).size / 1024 / 1024).toFixed(2)} MB`);

    // Print stats
    const aadtValues = cleaned.features.map(f => f.properties.aadt).filter(v => v > 0);
    if (aadtValues.length > 0) {
      const min = Math.min(...aadtValues);
      const max = Math.max(...aadtValues);
      const avg = Math.round(aadtValues.reduce((a, b) => a + b, 0) / aadtValues.length);

      console.log(`\n📈 AADT Stats:`);
      console.log(`   Min: ${min.toLocaleString()} vehicles/day`);
      console.log(`   Max: ${max.toLocaleString()} vehicles/day`);
      console.log(`   Avg: ${avg.toLocaleString()} vehicles/day`);
    }

    return outputPath;

  } catch (error) {
    console.error(`❌ Error: ${error.message}`);
    process.exit(1);
  }
}

/**
 * Main
 */
async function main() {
  const stateArg = process.argv[2];
  
  if (!stateArg) {
    console.log('Usage: node download-traffic-data.js <STATE_CODE>');
    console.log('');
    console.log('Available states:');
    Object.entries(STATE_SERVICES).forEach(([code, service]) => {
      console.log(`  ${code} - ${service.name}`);
    });
    console.log('');
    console.log('Or use "all" to download all states');
    process.exit(0);
  }
  
  if (stateArg.toUpperCase() === 'ALL') {
    for (const code of Object.keys(STATE_SERVICES)) {
      await downloadState(code);
    }
  } else {
    await downloadState(stateArg.toUpperCase());
  }
  
  console.log('\n✅ Done! Next steps:');
  console.log('   1. Install Mapbox CLI: npm install -g @mapbox/mapbox-sdk-cli');
  console.log('   2. Upload to Mapbox: mapbox upload <username>.<tileset-id> data/traffic/ia-traffic.geojson');
  console.log('   3. Update frontend to use tileset URL');
  console.log('');
}

main();
