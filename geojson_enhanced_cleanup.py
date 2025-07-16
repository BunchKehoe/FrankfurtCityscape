#!/usr/bin/env python3
"""
Enhanced GeoJSON cleanup script with specific requirements:
1. Check for duplicate entries and save title/coordinates to output file
2. Remove altitude coordinates entirely (keep only longitude and latitude)
3. Standardize color hashes according to specifications
4. Create list of missing Wikipedia entries with title and coordinates
"""

import json
import argparse
import os
import sys
from collections import defaultdict
from difflib import SequenceMatcher


def similarity(a, b):
    """
    Calculate similarity between two strings using SequenceMatcher.
    Args:
        a (str): First string.
        b (str): Second string.
    Returns:
        float: Similarity ratio between 0 and 1.
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_duplicates_with_coords(features):
    """
    Find duplicate entries and return detailed information with coordinates.
    Args:
        features (list): List of GeoJSON features.
    Returns:
        list: List of duplicate groups with title and coordinates.
    """
    duplicates = []
    processed = set()
    
    for i, feature1 in enumerate(features):
        if i in processed:
            continue
            
        props1 = feature1.get('properties', {})
        title1 = props1.get('title', '')
        
        if not title1:
            continue
            
        coords1 = feature1.get('geometry', {}).get('coordinates', [])
        
        similar_group = [{
            'title': title1,
            'coordinates': coords1,
            'feature_index': i
        }]
        processed.add(i)
        
        for j, feature2 in enumerate(features[i+1:], i+1):
            if j in processed:
                continue
                
            props2 = feature2.get('properties', {})
            title2 = props2.get('title', '')
            
            if not title2:
                continue
                
            coords2 = feature2.get('geometry', {}).get('coordinates', [])
            
            # Check exact match after normalization
            norm1 = title1.lower().strip()
            norm2 = title2.lower().strip()
            
            if norm1 == norm2 or similarity(norm1, norm2) > 0.9:
                similar_group.append({
                    'title': title2,
                    'coordinates': coords2,
                    'feature_index': j
                })
                processed.add(j)
        
        if len(similar_group) > 1:
            duplicates.append(similar_group)
    
    return duplicates


def standardize_colors(features):
    """
    Standardize color hashes according to specifications.
    Args:
        features (list): List of GeoJSON features.
    Returns:
        dict: Statistics of color changes.
    """
    color_mappings = {
        '#000000': '#333333',
        '#7c0000': '#333333',
        '#8f1b11': '#a10001',
        '#aa3524': '#a10001',
        '#9b0101': '#a10001',
        '#a43b2d': '#a10001',
        '#1e523d': '#005741',
        '#1d6b53': '#005741',
        '#005943': '#005741'
    }
    
    color_changes = defaultdict(int)
    
    for feature in features:
        props = feature.get('properties', {})
        
        # Check marker-color
        if 'marker-color' in props:
            old_color = props['marker-color']
            if old_color in color_mappings:
                props['marker-color'] = color_mappings[old_color]
                color_changes[f"{old_color} -> {color_mappings[old_color]}"] += 1
        
        # Check markerTextColor
        if 'markerTextColor' in props:
            old_color = props['markerTextColor']
            if old_color in color_mappings:
                props['markerTextColor'] = color_mappings[old_color]
                color_changes[f"text {old_color} -> {color_mappings[old_color]}"] += 1
    
    return dict(color_changes)


def remove_altitude_coordinates(features):
    """
    Remove altitude coordinates, keeping only longitude and latitude.
    Args:
        features (list): List of GeoJSON features.
    Returns:
        int: Number of features modified.
    """
    modified_count = 0
    
    for feature in features:
        geometry = feature.get('geometry', {})
        coords = geometry.get('coordinates', [])
        
        if coords and len(coords) >= 3:
            # Keep only longitude and latitude [lon, lat]
            geometry['coordinates'] = coords[:2]
            modified_count += 1
    
    return modified_count


def find_missing_wikipedia_entries(features):
    """
    Find entries missing Wikipedia links and return with coordinates.
    Args:
        features (list): List of GeoJSON features.
    Returns:
        list: List of entries missing Wikipedia with title and coordinates.
    """
    missing_wikipedia = []
    
    for feature in features:
        props = feature.get('properties', {})
        title = props.get('title', '')
        
        if title and 'Wikipedia' not in props:
            coords = feature.get('geometry', {}).get('coordinates', [])
            missing_wikipedia.append({
                'title': title,
                'coordinates': coords
            })
    
    return missing_wikipedia


def enhanced_cleanup_geojson(input_file, output_dir=None):
    """
    Enhanced cleanup function with specific requirements.
    Args:
        input_file (str): Path to the input GeoJSON file.
        output_dir (str|None): Output directory for cleaned file and reports.
    Returns:
        bool: True if cleaning succeeded, False otherwise.
    """
    # Set up output directory
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_file)) or '.'
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Determine output filename
    input_basename = os.path.basename(input_file)
    name, ext = os.path.splitext(input_basename)
    output_file = os.path.join(output_dir, f"{name}_enhanced{ext}")
    
    print(f"Loading {input_file}...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{input_file}': {e}")
        return False
    
    features = data.get('features', [])
    print(f"Loaded {len(features)} features")
    
    print("\nProcessing features...")
    
    # 1. Find duplicates with coordinates
    print("1. Finding duplicates...")
    duplicates = find_duplicates_with_coords(features)
    
    # 2. Remove altitude coordinates
    print("2. Removing altitude coordinates...")
    altitude_changes = remove_altitude_coordinates(features)
    
    # 3. Standardize colors
    print("3. Standardizing color hashes...")
    color_changes = standardize_colors(features)
    
    # 4. Find missing Wikipedia entries
    print("4. Finding missing Wikipedia entries...")
    missing_wikipedia = find_missing_wikipedia_entries(features)
    
    # Save cleaned data
    print(f"\nSaving enhanced GeoJSON to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Generate reports
    print("\nGenerating reports...")
    
    # Summary report
    summary_file = os.path.join(output_dir, 'enhanced_cleanup_summary.txt')
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"{input_basename} Enhanced Cleanup Summary\n")
        f.write("="*50 + "\n\n")
        f.write(f"Total features processed: {len(features)}\n\n")
        
        f.write("Changes made:\n")
        f.write(f"- Duplicate groups found: {len(duplicates)}\n")
        f.write(f"- Altitude coordinates removed: {altitude_changes}\n")
        f.write(f"- Missing Wikipedia entries: {len(missing_wikipedia)}\n")
        f.write(f"- Color standardizations: {len(color_changes)}\n\n")
        
        f.write("Color changes:\n")
        for change, count in color_changes.items():
            f.write(f"- {change}: {count} occurrences\n")
    
    # Duplicates report with coordinates
    if duplicates:
        duplicates_file = os.path.join(output_dir, 'duplicates_with_coordinates.txt')
        with open(duplicates_file, 'w', encoding='utf-8') as f:
            f.write("Duplicate Entries with Coordinates\n")
            f.write("="*50 + "\n\n")
            f.write(f"Found {len(duplicates)} groups of duplicates:\n\n")
            
            for i, group in enumerate(duplicates, 1):
                f.write(f"Group {i}:\n")
                for entry in group:
                    coords_str = f"[{', '.join(map(str, entry['coordinates']))}]"
                    f.write(f"  - Title: {entry['title']}\n")
                    f.write(f"    Coordinates: {coords_str}\n")
                    f.write(f"    Feature Index: {entry['feature_index']}\n")
                f.write("\n")
    
    # Missing Wikipedia entries with coordinates
    if missing_wikipedia:
        missing_wiki_file = os.path.join(output_dir, 'missing_wikipedia_with_coordinates.txt')
        with open(missing_wiki_file, 'w', encoding='utf-8') as f:
            f.write("Missing Wikipedia Entries with Coordinates\n")
            f.write("="*50 + "\n\n")
            f.write(f"Found {len(missing_wikipedia)} entries without Wikipedia links:\n\n")
            
            for entry in missing_wikipedia:
                coords_str = f"[{', '.join(map(str, entry['coordinates']))}]"
                f.write(f"Title: {entry['title']}\n")
                f.write(f"Coordinates: {coords_str}\n\n")
    
    # Print summary
    print(f"\nEnhanced cleanup completed!")
    print(f"- Found {len(duplicates)} groups of duplicates")
    print(f"- Removed altitude coordinates from {altitude_changes} features")
    print(f"- Standardized colors in {sum(color_changes.values())} features")
    print(f"- Found {len(missing_wikipedia)} entries missing Wikipedia")
    print(f"\nFiles created:")
    print(f"- {output_file} (enhanced cleaned data)")
    print(f"- {summary_file} (summary report)")
    if duplicates:
        print(f"- {os.path.join(output_dir, 'duplicates_with_coordinates.txt')} (duplicates with coordinates)")
    if missing_wikipedia:
        print(f"- {os.path.join(output_dir, 'missing_wikipedia_with_coordinates.txt')} (missing Wikipedia with coordinates)")
    
    return True


def main():
    """
    Main CLI entry point for enhanced geojson cleanup.
    """
    parser = argparse.ArgumentParser(
        description='Enhanced GeoJSON cleanup with duplicate detection, color standardization, and Wikipedia analysis.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s places.geojson
  %(prog)s places.geojson --output-dir ./enhanced
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Path to the input GeoJSON file'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        help='Output directory for cleaned file and reports (default: same as input file)'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)
    
    # Run enhanced cleanup
    success = enhanced_cleanup_geojson(args.input_file, args.output_dir)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
