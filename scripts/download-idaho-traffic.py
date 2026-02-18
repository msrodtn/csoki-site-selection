#!/usr/bin/env python3
"""
Download Idaho Transportation Department (ITD) Traffic Count Data

This script downloads Annual Average Daily Traffic (AADT) data from Idaho's
Transportation Department ArcGIS services and converts it to GeoJSON format
compatible with Mapbox tileset upload.

Usage:
    python3 download-idaho-traffic.py

Output:
    ../data/traffic/idaho-traffic.geojson
"""

import json
import os
import requests
import sys
from pathlib import Path
from typing import Dict, List, Any

# Potential Idaho ITD ArcGIS service endpoints
POTENTIAL_ENDPOINTS = [
    {
        'name': 'ITD AADT 1999-Present (MapServer)',
        'url': 'https://gis.itd.idaho.gov/arcgisprod/rest/services/ArcGISOnline/IdahoTransportationLayersForOpenData/MapServer/50',
        'fields': 'AADT,Route,Year_,Segment,MilepostFrom,MilepostTo,DescriptionFrom,DescriptionTo',
    },
]

def fetch_arcgis_data(url: str, fields: str, max_records: int = 2000) -> Dict[str, Any]:
    """Fetch data from ArcGIS REST service with pagination"""
    all_features = []
    offset = 0
    
    print(f"Fetching data from: {url}")
    
    while True:
        params = {
            'where': '1=1',
            'outFields': fields,
            'returnGeometry': 'true',
            'f': 'geojson',
            'resultRecordCount': max_records,
            'resultOffset': offset,
        }
        
        try:
            print(f"  Requesting records {offset} - {offset + max_records}...")
            response = requests.get(f"{url}/query", params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'features' not in data or not data['features']:
                print(f"  No more features found at offset {offset}")
                break
                
            features = data['features']
            all_features.extend(features)
            print(f"  Got {len(features)} features")
            
            # Check if there are more records
            if len(features) < max_records:
                break
                
            offset += len(features)
            
        except requests.RequestException as e:
            print(f"  Error fetching data: {e}")
            if offset == 0:  # No data fetched yet
                return None
            else:  # Partial data fetched
                break
        except json.JSONDecodeError as e:
            print(f"  Error parsing JSON response: {e}")
            return None
    
    if not all_features:
        return None
        
    return {
        'type': 'FeatureCollection',
        'features': all_features
    }

def normalize_properties(feature: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize feature properties to match Iowa format"""
    props = feature.get('properties', {})
    
    # Try to extract AADT value from various possible field names
    aadt = 0
    for field in ['AADT', 'aadt', 'traffic_volume', 'daily_volume', 'volume', 'adt', 
                  'traffic_count', 'avg_daily_traffic', 'annual_adt']:
        if field in props and props[field] is not None:
            try:
                aadt = int(props[field])
                break
            except (ValueError, TypeError):
                continue
    
    # Try to extract route name from various possible field names
    route = 'Unknown'
    for field in ['ROUTE_NAME', 'ROUTE', 'ROUTE_ID', 'RT_NAME', 'HIGHWAY', 'highway', 
                  'route_name', 'route', 'station_id', 'STATION_ID', 'SITE_ID', 'site_id',
                  'location_id', 'LOCATION_ID', 'counter_id', 'COUNTER_ID']:
        if field in props and props[field]:
            route = str(props[field])
            break
    
    # Try to extract year from various possible field names
    year = None
    for field in ['Year_', 'YEAR', 'DATA_YEAR', 'COUNT_YEAR', 'year', 'data_year', 'count_year', 'yr']:
        if field in props and props[field] is not None:
            try:
                year = int(props[field])
                break
            except (ValueError, TypeError):
                continue
    
    return {
        'aadt': aadt,
        'route': route,
        'year': year or 2023  # Default to 2023 if no year found
    }

def clean_geojson(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and normalize GeoJSON to match Iowa format"""
    cleaned_features = []
    
    for feature in raw_data.get('features', []):
        # Skip features without geometry
        if not feature.get('geometry') or not feature['geometry'].get('coordinates'):
            continue
            
        # Skip features without AADT data
        props = normalize_properties(feature)
        if props['aadt'] <= 0:
            continue
            
        cleaned_feature = {
            'type': 'Feature',
            'geometry': feature['geometry'],
            'properties': props
        }
        
        cleaned_features.append(cleaned_feature)
    
    return {
        'type': 'FeatureCollection',
        'features': cleaned_features
    }

def try_itd_shapefile_download() -> Dict[str, Any]:
    """Try to find ITD shapefile downloads"""
    shapefile_urls = [
        'https://gis.itd.idaho.gov/data/downloads/traffic_counts.zip',
        'https://apps.itd.idaho.gov/gisdata/traffic/traffic_counts.shp',
    ]
    
    for url in shapefile_urls:
        try:
            print(f"Trying ITD shapefile download: {url}")
            response = requests.head(url, timeout=10)  # HEAD request to check existence
            if response.status_code == 200:
                print("Found potential shapefile - would need ogr2ogr conversion to GeoJSON")
                print("Manual conversion: unzip → ogr2ogr -f GeoJSON output.geojson input.shp")
                return None
        except Exception as e:
            print(f"Shapefile check failed: {e}")
    
    return None

def main():
    script_dir = Path(__file__).parent
    output_path = script_dir / '../data/traffic/idaho-traffic.geojson'
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("🚗 Downloading Idaho Transportation Department (ITD) traffic count data...")
    print("Note: URLs may need verification - ITD service endpoints change frequently")
    print()
    
    # Try each potential endpoint until we find one that works
    for i, endpoint in enumerate(POTENTIAL_ENDPOINTS, 1):
        print(f"Attempt {i}: Trying {endpoint['name']}")
        
        try:
            raw_data = fetch_arcgis_data(endpoint['url'], endpoint['fields'])
            
            if raw_data and raw_data.get('features'):
                print(f"✅ Successfully found data source: {endpoint['name']}")
                print(f"   Raw features: {len(raw_data['features'])}")
                
                # Clean and normalize the data
                cleaned_data = clean_geojson(raw_data)
                
                if not cleaned_data['features']:
                    print("❌ No valid traffic count features found after cleaning")
                    continue
                
                # Save to file
                with open(output_path, 'w') as f:
                    json.dump(cleaned_data, f, indent=2)
                
                print(f"💾 Saved {len(cleaned_data['features'])} road segments to {output_path}")
                
                # Print statistics
                aadt_values = [f['properties']['aadt'] for f in cleaned_data['features'] 
                             if f['properties']['aadt'] > 0]
                
                if aadt_values:
                    print(f"\n📈 AADT Statistics:")
                    print(f"   Min: {min(aadt_values):,} vehicles/day")
                    print(f"   Max: {max(aadt_values):,} vehicles/day")
                    print(f"   Avg: {sum(aadt_values) // len(aadt_values):,} vehicles/day")
                
                # Print file size
                file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"   File size: {file_size_mb:.2f} MB")
                
                print(f"\n✅ Idaho traffic data download complete!")
                print(f"Next step: Upload to Mapbox using:")
                print(f"  mapbox upload USERNAME.idaho-traffic {output_path}")
                return True
                
            else:
                print(f"❌ No data found at {endpoint['name']}")
                
        except Exception as e:
            print(f"❌ Error with {endpoint['name']}: {e}")
            
        print()
    
    # Try ITD shapefile download as fallback
    print("Attempting ITD shapefile download as fallback...")
    try_itd_shapefile_download()
    
    # If we get here, no endpoints worked
    print("❌ Could not find working Idaho ITD traffic data endpoint")
    print("\n🔍 Manual verification needed:")
    print("   1. Visit https://apps.itd.idaho.gov/ or https://gis.itd.idaho.gov/")
    print("   2. Search for 'traffic counts', 'AADT', or 'traffic volume' data")
    print("   3. Look for ArcGIS Feature Service, shapefile, or CSV downloads") 
    print("   4. Update the POTENTIAL_ENDPOINTS list in this script")
    print("   5. Idaho may provide data as shapefiles requiring ogr2ogr conversion")
    print("\n📋 Known Idaho ITD resources:")
    print("   - ITD Apps Portal: https://apps.itd.idaho.gov/")
    print("   - ITD GIS Data: https://gis.itd.idaho.gov/")
    print("   - Transportation Data: https://itd.idaho.gov/data/")
    
    return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)