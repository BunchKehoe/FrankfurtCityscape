#!/usr/bin/env python3
"""
Filter GeoJSON features by removing those missing at least half of the required properties.
"""

import json

# Required properties from the template
REQUIRED_PROPERTIES = [
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
]

def is_property_missing(value):
    """
    Check if a property value is considered missing.
    
    Args:
        value: Property value to check
    
    Returns:
        True if missing (None, empty string, or whitespace only)
    """
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False

def count_missing_properties(feature):
    """
    Count how many required properties are missing from a feature.
    
    Args:
        feature: GeoJSON feature object
    
    Returns:
        Tuple of (missing_count, missing_property_names)
    """
    properties = feature.get('properties', {})
    missing_count = 0
    missing_names = []
    
    for prop_name in REQUIRED_PROPERTIES:
        value = properties.get(prop_name)
        if is_property_missing(value):
            missing_count += 1
            missing_names.append(prop_name)
    
    return missing_count, missing_names

def filter_incomplete_features(input_file, output_file):
    """
    Filter GeoJSON by removing features missing at least half of required properties.
    
    Args:
        input_file: Path to input GeoJSON file
        output_file: Path to output filtered GeoJSON file
    """
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    original_count = len(geojson_data.get('features', []))
    threshold = len(REQUIRED_PROPERTIES) / 2
    
    print(f"\nTotal required properties: {len(REQUIRED_PROPERTIES)}")
    print(f"Threshold for removal: missing {threshold:.1f} or more properties\n")
    
    # Track statistics
    kept_features = []
    removed_features = []
    missing_stats = {}
    
    # Process each feature
    for i, feature in enumerate(geojson_data.get('features', [])):
        missing_count, missing_names = count_missing_properties(feature)
        
        # Track statistics
        if missing_count not in missing_stats:
            missing_stats[missing_count] = 0
        missing_stats[missing_count] += 1
        
        # Keep or remove based on threshold
        if missing_count >= threshold:
            name = feature.get('properties', {}).get('name', f'Feature {i+1}')
            removed_features.append({
                'index': i,
                'name': name,
                'missing_count': missing_count,
                'missing_properties': missing_names
            })
        else:
            kept_features.append(feature)
    
    # Update GeoJSON with filtered features
    geojson_data['features'] = kept_features
    
    # Write filtered GeoJSON
    print(f"Writing filtered data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    
    # Print summary
    print(f"\n{'='*80}")
    print("FILTERING SUMMARY")
    print(f"{'='*80}\n")
    
    print(f"Original features: {original_count}")
    print(f"Kept features: {len(kept_features)}")
    print(f"Removed features: {len(removed_features)}")
    print(f"Retention rate: {len(kept_features)/original_count*100:.1f}%\n")
    
    # Print statistics by missing count
    print("Distribution of missing properties:")
    for missing_count in sorted(missing_stats.keys()):
        status = "✓ KEPT" if missing_count < threshold else "✗ REMOVED"
        print(f"  Missing {missing_count:2d} properties: {missing_stats[missing_count]:3d} features [{status}]")
    
    # Print sample removed features
    if removed_features:
        print(f"\n{'='*80}")
        print("SAMPLE REMOVED FEATURES")
        print(f"{'='*80}\n")
        
        for item in removed_features[:10]:
            print(f"• {item['name']} (missing {item['missing_count']}/{len(REQUIRED_PROPERTIES)})")
            print(f"  Missing: {', '.join(item['missing_properties'][:5])}")
            if len(item['missing_properties']) > 5:
                print(f"           ... and {len(item['missing_properties']) - 5} more")
            print()
        
        if len(removed_features) > 10:
            print(f"... and {len(removed_features) - 10} more removed features\n")
    
    print(f"\n✓ Filtered GeoJSON saved to: {output_file}")
    
    return {
        'original_count': original_count,
        'kept_count': len(kept_features),
        'removed_count': len(removed_features),
        'removed_features': removed_features
    }

if __name__ == "__main__":
    input_file = "HistoricalRegions_cleaned.geojson"
    output_file = "HistoricalRegions_filtered.geojson"
    
    results = filter_incomplete_features(input_file, output_file)
    
    print(f"\n✓ Complete!")
