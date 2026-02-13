#!/usr/bin/env python3
"""
Calculate bounding box and center for each feature in a GeoJSON file.
The center is the center of the bounding box, not the polygon centroid.
"""

import json
import math

def get_coordinates_from_geometry(geometry):
    """Extract all coordinate pairs from any geometry type."""
    coords = []
    geom_type = geometry.get('type')
    coordinates = geometry.get('coordinates', [])
    
    def flatten_coords(coord_array, depth=0):
        """Recursively flatten coordinate arrays."""
        if not coord_array:
            return
        
        # Check if this is a coordinate pair [lon, lat]
        if isinstance(coord_array[0], (int, float)):
            coords.append(coord_array)
        else:
            # It's a nested array, recurse
            for item in coord_array:
                flatten_coords(item, depth + 1)
    
    flatten_coords(coordinates)
    return coords

def calculate_bounding_box(coords):
    """Calculate bounding box from list of [lon, lat] coordinates."""
    if not coords:
        return None
    
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    
    return {
        'min_lon': min(lons),
        'max_lon': max(lons),
        'min_lat': min(lats),
        'max_lat': max(lats)
    }

def calculate_bbox_center(bbox):
    """Calculate center point of bounding box."""
    return {
        'lon': (bbox['min_lon'] + bbox['max_lon']) / 2,
        'lat': (bbox['min_lat'] + bbox['max_lat']) / 2
    }

def calculate_zoom_level(bbox, map_width_px=1200, map_height_px=800):
    """
    Calculate appropriate zoom level to fit bounding box on screen.
    Uses Mercator projection approximation.
    """
    # Get bounding box dimensions in degrees
    lon_diff = bbox['max_lon'] - bbox['min_lon']
    lat_diff = bbox['max_lat'] - bbox['min_lat']
    
    # Add padding (10% on each side = 20% total)
    lon_diff *= 1.2
    lat_diff *= 1.2
    
    # Calculate zoom level based on width (longitude)
    # 360 degrees = world width at zoom 0
    # Each zoom level doubles the map size
    zoom_lon = math.log2(360 * map_width_px / (256 * lon_diff))
    
    # Calculate zoom level based on height (latitude)
    # This is more complex due to Mercator projection
    # Using simplified formula
    zoom_lat = math.log2(170 * map_height_px / (256 * lat_diff))
    
    # Use the smaller zoom level to ensure everything fits
    zoom = min(zoom_lon, zoom_lat)
    
    # Clamp between reasonable values
    return max(1, min(18, round(zoom)))

def calculate_regional_bounding_boxes(geojson_data):
    """
    Calculate combined bounding boxes for all features grouped by 'region' property.
    
    Args:
        geojson_data: GeoJSON data structure
    
    Returns:
        Dictionary mapping region names to their combined bounding box info
    """
    # Group features by region
    region_groups = {}
    
    for feature in geojson_data.get('features', []):
        region = feature.get('properties', {}).get('region')
        
        if not region:
            continue
        
        if region not in region_groups:
            region_groups[region] = []
        
        # Extract coordinates
        geometry = feature.get('geometry', {})
        coords = get_coordinates_from_geometry(geometry)
        
        if coords:
            region_groups[region].extend(coords)
    
    # Calculate bounding box for each region
    regional_bboxes = {}
    
    for region, coords in region_groups.items():
        if coords:
            bbox = calculate_bounding_box(coords)
            center = calculate_bbox_center(bbox)
            zoom = calculate_zoom_level(bbox)
            
            regional_bboxes[region] = {
                'bbox': bbox,
                'center': center,
                'zoom': zoom,
                'feature_count': len([f for f in geojson_data['features'] 
                                     if f.get('properties', {}).get('region') == region])
            }
    
    return regional_bboxes

def process_geojson(input_file, output_file=None):
    """
    Process GeoJSON file and add bounding box information to each feature.
    Adds both individual feature centers and regional centers based on grouped features.
    
    Args:
        input_file: Path to input GeoJSON file
        output_file: Optional path for output. If provided, saves enhanced GeoJSON.
    
    Returns:
        Tuple of (features_metadata, regional_metadata)
    """
    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    # First, calculate regional bounding boxes
    print("Calculating regional bounding boxes...")
    regional_bboxes = calculate_regional_bounding_boxes(geojson_data)
    
    print(f"Found {len(regional_bboxes)} unique regions")
    
    features_metadata = []
    
    # Process each feature
    for i, feature in enumerate(geojson_data.get('features', [])):
        # Get feature name and region
        name = feature.get('properties', {}).get('name', f'Feature {i+1}')
        region = feature.get('properties', {}).get('region')
        
        # Extract coordinates
        geometry = feature.get('geometry', {})
        coords = get_coordinates_from_geometry(geometry)
        
        if not coords:
            print(f"  ⚠ Warning: No coordinates found for feature {i+1} ({name})")
            continue
        
        # Calculate individual feature bounding box
        bbox = calculate_bounding_box(coords)
        center = calculate_bbox_center(bbox)
        zoom = calculate_zoom_level(bbox)
        
        # Remove old flat attributes if they exist
        for old_attr in ['latitude', 'longitude', 'zoom', 'reg_latitude', 'reg_longitude', 'reg_zoom']:
            if old_attr in feature['properties']:
                del feature['properties'][old_attr]
        
        # Add individual feature coordinates to properties as nested object
        feature['properties']['coordinates'] = {
            'latitude': center['lat'],
            'longitude': center['lon'],
            'zoom': zoom
        }
        
        # Add regional coordinates if region exists
        if region and region in regional_bboxes:
            reg_info = regional_bboxes[region]
            feature['properties']['regional_coordinates'] = {
                'latitude': reg_info['center']['lat'],
                'longitude': reg_info['center']['lon'],
                'zoom': reg_info['zoom']
            }
        else:
            # If no region, set to null or same as individual
            feature['properties']['regional_coordinates'] = {
                'latitude': center['lat'],
                'longitude': center['lon'],
                'zoom': zoom
            }
        
        # Store metadata
        metadata = {
            'index': i,
            'id': feature.get('id'),
            'name': name,
            'region': region,
            'bounding_box': bbox,
            'center': center,
            'zoom': zoom,
            'bbox_width': bbox['max_lon'] - bbox['min_lon'],
            'bbox_height': bbox['max_lat'] - bbox['min_lat']
        }
        
        if region and region in regional_bboxes:
            metadata['regional_center'] = regional_bboxes[region]['center']
            metadata['regional_zoom'] = regional_bboxes[region]['zoom']
        
        features_metadata.append(metadata)
    
    # Save enhanced GeoJSON
    if output_file:
        print(f"\nSaving enhanced GeoJSON to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)
        print("✓ Enhanced GeoJSON saved")
    
    return features_metadata, regional_bboxes

def print_summary(metadata, regional_bboxes):
    """Print summary of bounding box calculations."""
    print(f"\n{'='*80}")
    print(f"BOUNDING BOX SUMMARY")
    print(f"{'='*80}\n")
    
    print(f"Features processed: {len(metadata)}")
    print(f"Unique regions: {len(regional_bboxes)}\n")
    
    # Show regional bounding boxes
    print(f"{'='*80}")
    print("REGIONAL BOUNDING BOXES")
    print(f"{'='*80}\n")
    
    for region, info in sorted(regional_bboxes.items())[:10]:
        print(f"Region: {region}")
        print(f"  Features: {info['feature_count']}")
        print(f"  Center: [{info['center']['lon']:.6f}, {info['center']['lat']:.6f}]")
        print(f"  Zoom: {info['zoom']}")
        print()
    
    if len(regional_bboxes) > 10:
        print(f"... and {len(regional_bboxes) - 10} more regions\n")
    
    # Show sample features
    print(f"{'='*80}")
    print("SAMPLE FEATURES")
    print(f"{'='*80}\n")
    
    for item in metadata[:5]:  # Show first 5
        print(f"Feature: {item['name']}")
        print(f"  Region: {item.get('region', 'None')}")
        print(f"  Individual Center: [{item['center']['lon']:.6f}, {item['center']['lat']:.6f}]")
        print(f"  Individual Zoom: {item['zoom']}")
        if 'regional_center' in item:
            print(f"  Regional Center: [{item['regional_center']['lon']:.6f}, {item['regional_center']['lat']:.6f}]")
            print(f"  Regional Zoom: {item['regional_zoom']}")
        print()
    
    if len(metadata) > 5:
        print(f"... and {len(metadata) - 5} more features\n")
    
    # Save metadata to JSON files
    print("Saving metadata to bbox_metadata.json...")
    with open('bbox_metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print("✓ Metadata saved")
    
    print("\nSaving regional metadata to regional_metadata.json...")
    regional_list = [
        {
            'region': region,
            'feature_count': info['feature_count'],
            'latitude': info['center']['lat'],
            'longitude': info['center']['lon'],
            'zoom': info['zoom'],
            'bounding_box': info['bbox']
        }
        for region, info in regional_bboxes.items()
    ]
    with open('regional_metadata.json', 'w', encoding='utf-8') as f:
        json.dump(regional_list, f, ensure_ascii=False, indent=2)
    print("✓ Regional metadata saved")

if __name__ == "__main__":
    input_file = "HistoricalRegions_cleaned.geojson"
    output_file = "HistoricalRegions_cleaned.geojson"  # Overwrite with enhanced version
    
    metadata, regional_bboxes = process_geojson(input_file, output_file)
    print_summary(metadata, regional_bboxes)
    
    print(f"\n✓ Complete! Processed {len(metadata)} features in {len(regional_bboxes)} regions")
    print(f"  - Feature metadata saved to: bbox_metadata.json")
    print(f"  - Regional metadata saved to: regional_metadata.json")
    print(f"  - Enhanced GeoJSON saved to: {output_file}")
    print(f"\nAdded properties to each feature:")
    print(f"  - coordinates: {{ latitude, longitude, zoom }} (individual feature center)")
    print(f"  - regional_coordinates: {{ latitude, longitude, zoom }} (regional center)")
