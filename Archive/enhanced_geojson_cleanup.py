#!/usr/bin/env python3
"""
Enhanced GeoJSON cleanup script that:
1. Replace \n characters in title field with spaces
2. Fix unicode errors in title field (mainly ä, ö, ü, ß)
3. Find potential duplicates based on title variations
4. Remove specified unused fields
5. Add empty Wikipedia fields to entries
6. Optionally add a "zoom" field with a specific value to all entries

This version skips the Wikipedia lookup for faster processing.
"""

import json
import re
import os
import sys
import time
import argparse
from collections import defaultdict
from difflib import SequenceMatcher

def similarity(a, b):
    """Calculate similarity between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def fix_unicode_errors(text):
    """
    Fix common unicode encoding errors for German characters.
    Returns (fixed_text, was_fixed, error_description)
    """
    original = text
    
    # Common unicode error patterns for German characters
    replacements = {
        # ä variations
        'Ã¤': 'ä',
        'Ã\x84': 'Ä', 
        'ä': 'ä',  # already correct
        'Ä': 'Ä',  # already correct
        
        # ö variations  
        'Ã¶': 'ö',
        'Ã\x96': 'Ö',
        'ö': 'ö',  # already correct
        'Ö': 'Ö',  # already correct
        
        # ü variations
        'Ã¼': 'ü',
        'Ã\x9c': 'Ü', 
        'ü': 'ü',  # already correct
        'Ü': 'Ü',  # already correct
        
        # ß variations
        'ÃŸ': 'ß',
        'Ã\x9f': 'ß',
        'ß': 'ß',  # already correct
        
        # Other common issues
        'Ã©': 'é',
        'Ã¨': 'è',
        'Ã¡': 'á',
        'Ã ': 'à',
        'Ã­': 'í',
        'Ã³': 'ó',
        'Ãº': 'ú',
    }
    
    fixed = text
    for pattern, replacement in replacements.items():
        if pattern in fixed:
            fixed = fixed.replace(pattern, replacement)
    
    was_fixed = fixed != original
    error_desc = None
    
    # Check for remaining potential unicode issues
    if any(ord(c) > 127 for c in fixed):
        # Check if it contains characters that might be corruption
        suspicious_chars = []
        for c in fixed:
            if ord(c) > 127 and c not in 'äöüßÄÖÜáéíóúàèñç':
                suspicious_chars.append(c)
        
        if suspicious_chars:
            error_desc = f"Suspicious characters: {set(suspicious_chars)}"
    
    return fixed, was_fixed, error_desc


def find_potential_duplicates(titles):
    """
    Find potential duplicates based on title similarity.
    Args:
        titles (list of str): List of titles to check.
    Returns:
        list: Groups (lists) of similar titles.
    """
    duplicates = []
    processed = set()
    
    for i, title1 in enumerate(titles):
        if i in processed:
            continue
            
        similar_group = [title1]
        processed.add(i)
        
        for j, title2 in enumerate(titles[i+1:], i+1):
            if j in processed:
                continue
                
            # Check exact match after normalization
            norm1 = re.sub(r'\s+', ' ', title1.lower().strip())
            norm2 = re.sub(r'\s+', ' ', title2.lower().strip())
            
            if norm1 == norm2:
                similar_group.append(title2)
                processed.add(j)
            elif similarity(norm1, norm2) > 0.85:  # High similarity threshold
                similar_group.append(title2)
                processed.add(j)
        
        if len(similar_group) > 1:
            duplicates.append(similar_group)
    
    return duplicates


def clean_geojson(input_file, output_dir=None, add_zoom=None):
    """
    Main function to clean the GeoJSON file with empty Wikipedia fields.
    Args:
        input_file (str): Path to the input GeoJSON file.
        output_dir (str|None): Output directory for cleaned file and reports.
        add_zoom (str|None): If provided, adds a "zoom" field with this value to all entries.
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
    output_file = os.path.join(output_dir, f"{name}_cleaned{ext}")
    
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
    
    print(f"Loaded {len(data['features'])} features")
    
    # Statistics
    newline_fixes = 0
    unicode_fixes = 0
    unicode_errors = []
    titles = []
    fields_removed = defaultdict(int)
    wikipedia_added = 0
    wikipedia_skipped = 0
    zoom_added = 0
    
    # Fields to remove (updated list)
    fields_to_remove = {
        'text', 'anchor', 'icon', 'tooltip', 'textPosition', 'stroke', 'rotate', 'offsetY',
        'offsetX', 'locked', 'marker-size', 'labelStyle'
    }
    
    print("\nProcessing features...")
    
    for i, feature in enumerate(data['features']):
        properties = feature['properties']
        
        # Step 1: Fix newlines in title
        if 'title' in properties:
            original_title = properties['title']
            
            # Replace newlines with spaces
            if '\n' in original_title:
                properties['title'] = original_title.replace('\n', ' ')
                newline_fixes += 1
            
            # Step 2: Fix unicode errors
            fixed_title, was_unicode_fixed, unicode_error = fix_unicode_errors(properties['title'])
            
            if was_unicode_fixed:
                properties['title'] = fixed_title
                unicode_fixes += 1
            
            if unicode_error:
                unicode_errors.append({
                    'index': i,
                    'original': original_title,
                    'current': properties['title'],
                    'error': unicode_error
                })
            
            titles.append(properties['title'])
            
            # Step 5: Add empty Wikipedia field
            if 'Wikipedia' not in properties:
                properties['Wikipedia'] = ""
                wikipedia_added += 1
            else:
                wikipedia_skipped += 1
                
            # Step 6: Add zoom field if requested
            if add_zoom is not None:
                properties['zoom'] = add_zoom
                zoom_added += 1
        
        # Step 4: Remove unwanted fields
        for field in list(properties.keys()):
            if field in fields_to_remove:
                del properties[field]
                fields_removed[field] += 1
    
    # Step 3: Find duplicates
    print("\nAnalyzing for potential duplicates...")
    duplicates = find_potential_duplicates(titles)
    
    # Save cleaned data
    print(f"\nSaving cleaned GeoJSON to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Generate reports in output directory
    print("\nGenerating reports...")
    
    # Summary report
    summary_file = os.path.join(output_dir, 'cleanup_summary.txt')
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"{input_basename} Cleanup Summary\n")
        f.write("="*50 + "\n\n")
        f.write(f"Total features processed: {len(data['features'])}\n\n")
        
        f.write("Changes made:\n")
        f.write(f"- Newline fixes in titles: {newline_fixes}\n")
        f.write(f"- Unicode fixes in titles: {unicode_fixes}\n")
        f.write(f"- Empty Wikipedia entries added: {wikipedia_added}\n")
        f.write(f"- Wikipedia entries skipped (already present): {wikipedia_skipped}\n")
        if add_zoom:
            f.write(f"- Zoom field added with value '{add_zoom}': {zoom_added}\n")
        f.write(f"- Potential duplicate groups found: {len(duplicates)}\n\n")
        
        f.write("Fields removed:\n")
        for field, count in fields_removed.items():
            f.write(f"- {field}: {count} occurrences\n")
    
    # Unicode errors report
    if unicode_errors:
        unicode_file = os.path.join(output_dir, 'unicode_errors_review.txt')
        with open(unicode_file, 'w', encoding='utf-8') as f:
            f.write("Unicode Errors Requiring Manual Review\n")
            f.write("="*50 + "\n\n")
            f.write(f"Found {len(unicode_errors)} titles with potential unicode issues:\n\n")
            
            for error in unicode_errors:
                f.write(f"Index {error['index']}:\n")
                f.write(f"  Original: {repr(error['original'])}\n")
                f.write(f"  Current:  {repr(error['current'])}\n")
                f.write(f"  Issue:    {error['error']}\n\n")
    
    # Duplicates report (saved to repository as requested)
    if duplicates:
        duplicates_file = os.path.join(output_dir, 'potential_duplicates.txt')
        with open(duplicates_file, 'w', encoding='utf-8') as f:
            f.write("Potential Duplicates Requiring Manual Review\n")
            f.write("="*50 + "\n\n")
            f.write(f"Found {len(duplicates)} groups of potential duplicates:\n\n")
            
            for i, group in enumerate(duplicates, 1):
                f.write(f"Group {i}:\n")
                for title in group:
                    f.write(f"  - {repr(title)}\n")
                f.write("\n")
    
    # Print summary
    print(f"\nCleanup completed!")
    print(f"- Fixed {newline_fixes} titles with newlines")
    print(f"- Fixed {unicode_fixes} titles with unicode issues")
    print(f"- Found {len(unicode_errors)} titles needing manual unicode review")
    print(f"- Added {wikipedia_added} empty Wikipedia entries")
    print(f"- Skipped {wikipedia_skipped} entries (Wikipedia already present)")
    if add_zoom:
        print(f"- Added 'zoom' field with value '{add_zoom}' to {zoom_added} entries")
    print(f"- Found {len(duplicates)} groups of potential duplicates")
    print(f"- Removed fields: {dict(fields_removed)}")
    print(f"\nFiles created:")
    print(f"- {output_file} (cleaned data)")
    print(f"- {summary_file} (summary report)")
    if unicode_errors:
        print(f"- {os.path.join(output_dir, 'unicode_errors_review.txt')} (unicode issues for manual review)")
    if duplicates:
        print(f"- {os.path.join(output_dir, 'potential_duplicates.txt')} (potential duplicates for manual review)")
    
    return True


def main():
    """
    Main CLI entry point for enhanced_geojson_cleanup.py.
    Parses arguments and runs the cleaning process.
    """
    parser = argparse.ArgumentParser(
        description='Clean up GeoJSON files with unicode fixes, duplicate detection, field removal, empty Wikipedia fields, and optional zoom field addition.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s places.geojson
  %(prog)s places.geojson --output-dir ./cleaned
  %(prog)s places.geojson --add-zoom city
  %(prog)s /path/to/places.geojson --output-dir /path/to/output --add-zoom city
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
    
    parser.add_argument(
        '--add-zoom', '-z',
        help='Add a "zoom" field with the specified value to all entries'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)
    
    # Run cleanup
    success = clean_geojson(args.input_file, args.output_dir, args.add_zoom)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
