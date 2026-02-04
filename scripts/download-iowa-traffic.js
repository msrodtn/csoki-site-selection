#!/usr/bin/env node
const https = require('https');
const fs = require('fs');
const path = require('path');

const url = 'https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Data_view/FeatureServer/10/query?where=1=1&outFields=AADT,ROUTE_NAME&returnGeometry=true&f=geojson&resultRecordCount=10000';
const output = path.join(__dirname, '../data/iowa-traffic.geojson');

console.log('Downloading Iowa traffic data...\n');

https.get(url, (res) => {
  let data = '';
  res.on('data', (chunk) => { data += chunk; });
  res.on('end', () => {
    const dir = path.dirname(output);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(output, data);
    const features = JSON.parse(data).features.length;
    console.log(`✅ Downloaded ${features} road segments`);
    console.log(`💾 Saved to: ${output}\n`);
    console.log('Next: mapbox upload YOUR_USERNAME.iowa-traffic data/iowa-traffic.geojson');
  });
}).on('error', (err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
