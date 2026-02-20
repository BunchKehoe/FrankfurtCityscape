#!/usr/bin/env python3
"""
Script to clean GeoJSON properties by removing fields not in the allowed list.
"""

import json

# Define allowed property fields
ALLOWED_FIELDS = {
    "empireDesc",
    "regionDesc",
    "name",
    "empireIcoUrl",
    "regionIcoUrl",
    "url",
    "desc",
    "empire",
    "region",
    "subtitle",
    "icoUrl",
    "regionUrl",
    "empireUrl"
}

def clean_geojson_properties(input_file, output_file):
    """
    Clean GeoJSON by removing properties not in the allowed list.
    
    Args:
        input_file: Path to input GeoJSON file
        output_file: Path to output cleaned GeoJSON file
    """
    # Read the GeoJSON file
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    # Track statistics
    total_features = len(geojson_data.get('features', []))
    fields_removed = {}
    
    # Process each feature
    for i, feature in enumerate(geojson_data.get('features', [])):
        if 'properties' in feature:
            # Get current property keys
            current_keys = list(feature['properties'].keys())
            
            # Find keys to remove
            keys_to_remove = [key for key in current_keys if key not in ALLOWED_FIELDS]
            
            # Remove unwanted keys
            for key in keys_to_remove:
                del feature['properties'][key]
                fields_removed[key] = fields_removed.get(key, 0) + 1
    
    # Write cleaned GeoJSON
    print(f"Writing cleaned data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    
    # Print summary
    print(f"\n✓ Processed {total_features} features")
    if fields_removed:
        print(f"\nRemoved fields:")
        for field, count in sorted(fields_removed.items()):
            print(f"  - {field}: {count} occurrences")
    else:
        print("\nNo fields needed to be removed.")
    
    print(f"\n✓ Cleaned GeoJSON saved to: {output_file}")

if __name__ == "__main__":
    input_file = "HistoricalRegions (1).geojson"
    output_file = "HistoricalRegions_cleaned.geojson"
    
    clean_geojson_properties(input_file, output_file)
