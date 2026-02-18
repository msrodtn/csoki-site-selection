#!/usr/bin/env python3
"""
Download Nevada DOT (NDOT) Traffic Count Data

This script downloads Annual Average Daily Traffic (AADT) data from Nevada's
Department of Transportation services and converts it to GeoJSON format
compatible with Mapbox tileset upload.

Nevada DOT uses the Traffic Records Information Access (TRINA) system.

Usage:
    python3 download-nevada-traffic.py

Output:
    ../data/traffic/nevada-traffic.geojson
"""

import json
import os
import requests
import sys
from pathlib import Path
from typing import Dict, List, Any

# Potential Nevada DOT ArcGIS service endpoints
POTENTIAL_ENDPOINTS = [
    {
        'name': 'Nevada DOT TRINA Stations',
        'url': 'https://gis.dot.nv.gov/agsphs/rest/services/TRINA_Stations/FeatureServer/0',
        'fields': 'AADT_2024,ROUTE_NAME,Name,LOCATION_D,StationType',
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
    for field in ['AADT_2024', 'AADT_2023', 'AADT_2022', 'AADT', 'aadt', 'traffic_volume', 'daily_volume', 'volume', 'adt', 'traffic_count']:
        if field in props and props[field] is not None:
            try:
                aadt = int(props[field])
                break
            except (ValueError, TypeError):
                continue
    
    # Try to extract route name from various possible field names
    route = 'Unknown'
    for field in ['ROUTE_NAME', 'ROUTE', 'ROUTE_ID', 'HIGHWAY', 'highway', 'route_name', 
                  'route', 'station_num', 'STATION_NUM', 'STATION_ID', 'location', 'LOCATION']:
        if field in props and props[field]:
            route = str(props[field])
            break
    
    # Try to extract year from various possible field names
    year = None
    for field in ['YEAR', 'DATA_YEAR', 'COUNT_YEAR', 'year', 'data_year', 'count_year']:
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

def try_trina_csv_download() -> Dict[str, Any]:
    """Try to download from TRINA system CSV export if available"""
    trina_urls = [
        'https://trina.dot.nv.gov/downloads/traffic_counts.csv',
        'https://www.dot.nv.gov/doing-business/engineering/traffic-data/export',
    ]
    
    for url in trina_urls:
        try:
            print(f"Trying TRINA CSV download: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200 and 'csv' in response.headers.get('content-type', '').lower():
                print("Found CSV data - this would need additional processing to convert to GeoJSON")
                print("Manual conversion required: CSV → coordinates → GeoJSON")
                return None
        except Exception as e:
            print(f"TRINA CSV attempt failed: {e}")
    
    return None

def main():
    script_dir = Path(__file__).parent
    output_path = script_dir / '../data/traffic/nevada-traffic.geojson'
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("🚗 Downloading Nevada DOT traffic count data...")
    print("Note: Nevada uses TRINA system - URLs may need verification")
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
                
                print(f"\n✅ Nevada traffic data download complete!")
                print(f"Next step: Upload to Mapbox using:")
                print(f"  mapbox upload USERNAME.nevada-traffic {output_path}")
                return True
                
            else:
                print(f"❌ No data found at {endpoint['name']}")
                
        except Exception as e:
            print(f"❌ Error with {endpoint['name']}: {e}")
            
        print()
    
    # Try TRINA CSV download as fallback
    print("Attempting TRINA CSV download as fallback...")
    try_trina_csv_download()
    
    # If we get here, no endpoints worked
    print("❌ Could not find working Nevada DOT traffic data endpoint")
    print("\n🔍 Manual verification needed:")
    print("   1. Visit https://www.dot.nv.gov/ or https://trina.dot.nv.gov/")
    print("   2. Search for 'traffic counts', 'AADT', or 'TRINA' data")
    print("   3. Look for ArcGIS Feature Service or CSV/shapefile downloads") 
    print("   4. Update the POTENTIAL_ENDPOINTS list in this script")
    print("   5. Nevada may require manual coordinate geocoding if only CSV data available")
    print("\n📋 Known Nevada DOT contacts:")
    print("   - TRINA System: https://trina.dot.nv.gov/")
    print("   - Traffic Engineering: https://www.dot.nv.gov/doing-business/engineering/traffic-data")
    
    return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)