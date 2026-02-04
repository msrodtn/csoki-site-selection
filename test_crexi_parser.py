#!/usr/bin/env python3
"""
Test script for Crexi CSV parser.

Tests the parsing and filtering logic with the sample Crexi export.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from app.services.crexi_parser import parse_crexi_csv, filter_opportunities

def main():
    """Test Crexi parser with sample data."""
    sample_file = Path(__file__).parent / 'crexi-sample.xlsx'
    
    if not sample_file.exists():
        print(f"❌ Sample file not found: {sample_file}")
        return 1
    
    print("=" * 60)
    print("Testing Crexi CSV Parser")
    print("=" * 60)
    
    # Test parsing
    print("\n1️⃣  Parsing Crexi CSV...")
    try:
        listings = parse_crexi_csv(str(sample_file))
        print(f"✓ Parsed {len(listings)} listings")
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        return 1
    
    # Show sample listing
    if listings:
        sample = listings[0]
        print(f"\nSample listing:")
        print(f"  - Type: {sample.property_type}")
        print(f"  - Address: {sample.address}, {sample.city}, {sample.state}")
        print(f"  - SqFt: {sample.sqft}")
        print(f"  - Lot Size: {sample.lot_size_acres} acres")
        print(f"  - Price: ${sample.asking_price:,.0f}" if sample.asking_price else "  - Price: N/A")
        print(f"  - URL: {sample.property_link[:60]}...")
    
    # Test filtering
    print("\n2️⃣  Filtering opportunities...")
    try:
        filtered, stats = filter_opportunities(listings)
        print(f"✓ Filtered to {len(filtered)} opportunities")
    except Exception as e:
        print(f"❌ Filtering failed: {e}")
        return 1
    
    # Show stats
    print(f"\n📊 Filtering Statistics:")
    print(f"  Total input:      {stats['total_input']}")
    print(f"  Total filtered:   {stats['total_filtered']}")
    print(f"  Empty land:       {stats['empty_land_count']}")
    print(f"  Small buildings:  {stats['small_building_count']}")
    print(f"  Filter rate:      {stats['filter_rate']}")
    
    # Show examples from each category
    if filtered:
        print(f"\n📋 Sample Opportunities:")
        
        # Empty land example
        empty_land = [l for l in filtered if l.match_category == 'empty_land']
        if empty_land:
            example = empty_land[0]
            print(f"\n  🌾 Empty Land Example:")
            print(f"     Type: {example.property_type}")
            print(f"     Lot: {example.lot_size_acres} acres")
            print(f"     Price: ${example.asking_price:,.0f}" if example.asking_price else "     Price: N/A")
            print(f"     Location: {example.city}, {example.state}")
        
        # Small building example
        small_building = [l for l in filtered if l.match_category == 'small_building']
        if small_building:
            example = small_building[0]
            print(f"\n  🏢 Small Building Example:")
            print(f"     Type: {example.property_type}")
            print(f"     SqFt: {example.sqft:,.0f}" if example.sqft else "     SqFt: N/A")
            print(f"     Units: {example.units}" if example.units else "     Units: N/A")
            print(f"     Price: ${example.asking_price:,.0f}" if example.asking_price else "     Price: N/A")
            print(f"     Location: {example.city}, {example.state}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
