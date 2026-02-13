#!/usr/bin/env python3
"""
Upload GeoJSON data to Mapbox Datasets API.

Required: Mapbox access token with 'datasets:write' scope.
"""

import json
import requests
import time
import sys

class MapboxDatasetUploader:
    def __init__(self, username, access_token):
        """
        Initialize the Mapbox Dataset uploader.
        
        Args:
            username: Mapbox username
            access_token: Mapbox access token with datasets:write scope
        """
        self.username = username
        self.access_token = access_token
        self.base_url = "https://api.mapbox.com/datasets/v1"
    
    def create_dataset(self, name, description=""):
        """
        Create a new empty dataset.
        
        Args:
            name: Name of the dataset
            description: Optional description
        
        Returns:
            Dataset ID if successful, None otherwise
        """
        url = f"{self.base_url}/{self.username}"
        params = {"access_token": self.access_token}
        data = {
            "name": name,
            "description": description
        }
        
        print(f"Creating dataset '{name}'...")
        response = requests.post(url, params=params, json=data)
        
        if response.status_code == 200:
            dataset = response.json()
            dataset_id = dataset['id']
            print(f"✓ Dataset created successfully!")
            print(f"  ID: {dataset_id}")
            print(f"  Name: {dataset['name']}")
            return dataset_id
        else:
            print(f"✗ Error creating dataset: {response.status_code}")
            print(f"  {response.text}")
            return None
    
    def upload_feature(self, dataset_id, feature):
        """
        Upload a single feature to a dataset.
        
        Args:
            dataset_id: ID of the dataset
            feature: GeoJSON feature object
        
        Returns:
            True if successful, False otherwise
        """
        feature_id = feature.get('id', str(hash(json.dumps(feature))))
        url = f"{self.base_url}/{self.username}/{dataset_id}/features/{feature_id}"
        params = {"access_token": self.access_token}
        
        response = requests.put(url, params=params, json=feature)
        
        return response.status_code == 200
    
    def upload_geojson(self, dataset_id, geojson_file, batch_size=10, delay=1.5):
        """
        Upload all features from a GeoJSON file to a dataset.
        
        Args:
            dataset_id: ID of the dataset
            geojson_file: Path to GeoJSON file
            batch_size: Number of features to upload before showing progress
            delay: Delay in seconds between batches (to respect rate limits)
        
        Returns:
            Dictionary with upload statistics
        """
        print(f"\nReading {geojson_file}...")
        with open(geojson_file, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        features = geojson_data.get('features', [])
        total_features = len(features)
        
        print(f"Found {total_features} features to upload")
        print(f"Uploading in batches of {batch_size} with {delay}s delays...")
        print()
        
        successful = 0
        failed = 0
        failed_features = []
        
        for i, feature in enumerate(features):
            # Upload feature
            if self.upload_feature(dataset_id, feature):
                successful += 1
            else:
                failed += 1
                name = feature.get('properties', {}).get('name', f'Feature {i+1}')
                failed_features.append(name)
            
            # Show progress
            if (i + 1) % batch_size == 0 or (i + 1) == total_features:
                progress = (i + 1) / total_features * 100
                print(f"Progress: {i + 1}/{total_features} ({progress:.1f}%) - "
                      f"✓ {successful} succeeded, ✗ {failed} failed")
                
                # Delay to respect rate limits (40 writes per minute)
                if (i + 1) < total_features:
                    time.sleep(delay)
        
        print()
        print(f"{'='*80}")
        print("UPLOAD COMPLETE")
        print(f"{'='*80}")
        print(f"Total features: {total_features}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        if failed_features:
            print(f"\nFailed features:")
            for name in failed_features[:10]:
                print(f"  - {name}")
            if len(failed_features) > 10:
                print(f"  ... and {len(failed_features) - 10} more")
        
        return {
            'total': total_features,
            'successful': successful,
            'failed': failed,
            'failed_features': failed_features
        }
    
    def get_dataset_info(self, dataset_id):
        """
        Get information about a dataset.
        
        Args:
            dataset_id: ID of the dataset
        
        Returns:
            Dataset information dictionary
        """
        url = f"{self.base_url}/{self.username}/{dataset_id}"
        params = {"access_token": self.access_token}
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            return None

def main():
    # CONFIGURATION - Update these values
    MAPBOX_USERNAME = input("Enter your Mapbox username [jcbunch3]: ").strip() or "jcbunch3"
    MAPBOX_ACCESS_TOKEN = input("Enter your Mapbox access token (with datasets:write scope): ").strip() or "sk.eyJ1IjoiamNidW5jaDMiLCJhIjoiY21saWtnOGhyMDJvZjNncjlpYmozODN0cCJ9.Xzx4FcBZhY7LmnLn8Ci8Ew"
    
    if not MAPBOX_USERNAME or not MAPBOX_ACCESS_TOKEN:
        print("Error: Username and access token are required!")
        sys.exit(1)
    
    # Dataset details
    DATASET_NAME = "HistoricalRegions_v2.0"
    DATASET_DESCRIPTION = "Historical regions of Central Europe with detailed properties"
    GEOJSON_FILE = "HistoricalRegions_filtered.geojson"
    
    # Create uploader
    uploader = MapboxDatasetUploader(MAPBOX_USERNAME, MAPBOX_ACCESS_TOKEN)
    
    # Create dataset
    dataset_id = uploader.create_dataset(DATASET_NAME, DATASET_DESCRIPTION)
    
    if not dataset_id:
        print("Failed to create dataset. Exiting.")
        sys.exit(1)
    
    # Upload features
    print(f"\nDataset URL: https://studio.mapbox.com/datasets/{MAPBOX_USERNAME}/{dataset_id}/")
    
    confirm = input("\nProceed with upload? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Upload cancelled.")
        sys.exit(0)
    
    stats = uploader.upload_geojson(dataset_id, GEOJSON_FILE)
    
    # Get final dataset info
    print("\nFetching final dataset information...")
    dataset_info = uploader.get_dataset_info(dataset_id)
    
    if dataset_info:
        print(f"\n{'='*80}")
        print("DATASET INFORMATION")
        print(f"{'='*80}")
        print(f"Name: {dataset_info['name']}")
        print(f"ID: {dataset_info['id']}")
        print(f"Features: {dataset_info['features']}")
        print(f"Size: {dataset_info['size']:,} bytes")
        print(f"Created: {dataset_info['created']}")
        print(f"Modified: {dataset_info['modified']}")
        print(f"\nDataset URL: https://studio.mapbox.com/datasets/{MAPBOX_USERNAME}/{dataset_id}/")
        print(f"Tileset URL: https://studio.mapbox.com/tilesets/")
    
    print("\n✓ Upload complete!")
    print("\nNext steps:")
    print("1. Visit the dataset in Mapbox Studio")
    print("2. Export to tileset for use in maps")
    print("3. Use the tileset ID in your Mapbox GL JS applications")

if __name__ == "__main__":
    main()
