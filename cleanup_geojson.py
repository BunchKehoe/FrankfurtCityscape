#!/usr/bin/env python3
"""
Script to clean up PlacesToVisit4.geojson file according to requirements:
1. Replace \n characters in title field with spaces
2. Fix unicode errors in title field (mainly ä, ö, ü, ß)
3. Find potential duplicates based on title variations
4. Remove specified unused fields
"""

import json
import re
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
    Returns list of groups of similar titles.
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

def clean_geojson():
    """Main function to clean the GeoJSON file."""
    print("Loading PlacesToVisit4.geojson...")
    
    with open('PlacesToVisit4.geojson', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Loaded {len(data['features'])} features")
    
    # Statistics
    newline_fixes = 0
    unicode_fixes = 0
    unicode_errors = []
    titles = []
    fields_removed = defaultdict(int)
    
    # Fields to remove
    fields_to_remove = {'text', 'anchor', 'icon', 'tooltip', 'textPosition', 'stroke', 'rotate', 'offsetY'}
    
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
        
        # Step 4: Remove unwanted fields
        for field in list(properties.keys()):
            if field in fields_to_remove:
                del properties[field]
                fields_removed[field] += 1
    
    # Step 3: Find duplicates
    print("\nAnalyzing for potential duplicates...")
    duplicates = find_potential_duplicates(titles)
    
    # Save cleaned data
    print("\nSaving cleaned GeoJSON...")
    with open('PlacesToVisit4_cleaned.geojson', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Generate reports
    print("\nGenerating reports...")
    
    # Summary report
    with open('cleanup_summary.txt', 'w', encoding='utf-8') as f:
        f.write("PlacesToVisit4.geojson Cleanup Summary\n")
        f.write("="*50 + "\n\n")
        f.write(f"Total features processed: {len(data['features'])}\n\n")
        
        f.write("Changes made:\n")
        f.write(f"- Newline fixes in titles: {newline_fixes}\n")
        f.write(f"- Unicode fixes in titles: {unicode_fixes}\n")
        f.write(f"- Potential duplicate groups found: {len(duplicates)}\n\n")
        
        f.write("Fields removed:\n")
        for field, count in fields_removed.items():
            f.write(f"- {field}: {count} occurrences\n")
    
    # Unicode errors report
    if unicode_errors:
        with open('unicode_errors_review.txt', 'w', encoding='utf-8') as f:
            f.write("Unicode Errors Requiring Manual Review\n")
            f.write("="*50 + "\n\n")
            f.write(f"Found {len(unicode_errors)} titles with potential unicode issues:\n\n")
            
            for error in unicode_errors:
                f.write(f"Index {error['index']}:\n")
                f.write(f"  Original: {repr(error['original'])}\n")
                f.write(f"  Current:  {repr(error['current'])}\n")
                f.write(f"  Issue:    {error['error']}\n\n")
    
    # Duplicates report
    if duplicates:
        with open('potential_duplicates.txt', 'w', encoding='utf-8') as f:
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
    print(f"- Found {len(duplicates)} groups of potential duplicates")
    print(f"- Removed fields: {dict(fields_removed)}")
    print(f"\nFiles created:")
    print(f"- PlacesToVisit4_cleaned.geojson (cleaned data)")
    print(f"- cleanup_summary.txt (summary report)")
    if unicode_errors:
        print(f"- unicode_errors_review.txt (unicode issues for manual review)")
    if duplicates:
        print(f"- potential_duplicates.txt (potential duplicates for manual review)")

if __name__ == "__main__":
    clean_geojson()