#!/usr/bin/env python3
"""
CLI tool to clean up GeoJSON files according to requirements:
1. Replace \n characters in title field with spaces
2. Fix unicode errors in title field (mainly ä, ö, ü, ß)
3. Find potential duplicates based on title variations and save to repository
4. Remove specified unused fields: offsetX, locked, marker-size, labelStyle
5. Add Wikipedia field with article URLs, preferring longest articles and English > German
"""

import json
import re
import argparse
import os
import sys
import time
from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import quote
import requests


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


def detect_language_context(title):
    """
    Try to detect if a title suggests a specific language context.
    Returns suggested languages in order of preference.
    """
    title_lower = title.lower()
    
    # German-speaking regions/countries indicators
    german_indicators = [
        'deutschland', 'germany', 'österreich', 'austria', 'schweiz', 'switzerland',
        'deutschland', 'wien', 'vienna', 'berlin', 'münchen', 'munich', 'zürich',
        'salzburg', 'innsbruck', 'graz', 'linz', 'bern', 'geneva', 'basel'
    ]
    
    # Check for German context
    for indicator in german_indicators:
        if indicator in title_lower:
            return ['de', 'en']
    
    # Default to English first, then German
    return ['en', 'de']


def search_wikipedia_article(title, languages=['en', 'de']):
    """
    Search for a Wikipedia article about the given title.
    Returns (url, language, length) of the best article found, or (None, None, 0) if not found.
    """
    best_article = None
    best_length = 0
    best_lang = None
    best_url = None
    
    for lang in languages:
        try:
            # Search for the article
            search_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
            
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if it's a valid article (not disambiguation, etc.)
                if data.get('type') == 'standard':
                    # Get full article to check length
                    content_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/html/{quote(title)}"
                    content_response = requests.get(content_url, timeout=10)
                    
                    if content_response.status_code == 200:
                        content_length = len(content_response.text)
                        article_url = data.get('content_urls', {}).get('desktop', {}).get('page', '')
                        
                        # Prefer longer articles, but with language preference
                        if (content_length > best_length or 
                            (content_length == best_length and lang == 'en' and best_lang != 'en') or
                            (content_length == best_length and lang == 'de' and best_lang not in ['en'])):
                            best_length = content_length
                            best_lang = lang
                            best_url = article_url
            
            # Add small delay to be respectful to Wikipedia API
            time.sleep(0.1)
            
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"  Warning: Error searching Wikipedia ({lang}) for '{title}': {e}")
            continue
    
    return best_url, best_lang, best_length


def clean_geojson(input_file, output_dir=None):
    """Main function to clean the GeoJSON file."""
    
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
    wikipedia_not_found = []
    
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
            
            # Step 5: Add Wikipedia field
            if 'Wikipedia' not in properties:
                print(f"  Searching Wikipedia for: {properties['title']}")
                
                # Detect preferred languages for this title
                preferred_languages = detect_language_context(properties['title'])
                
                # Search for Wikipedia article
                wiki_url, wiki_lang, wiki_length = search_wikipedia_article(
                    properties['title'], preferred_languages
                )
                
                if wiki_url:
                    properties['Wikipedia'] = wiki_url
                    wikipedia_added += 1
                    print(f"    Found: {wiki_url} ({wiki_lang}, {wiki_length} chars)")
                else:
                    wikipedia_not_found.append(properties['title'])
                    print(f"    Not found")
            else:
                wikipedia_skipped += 1
        
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
        f.write(f"- Wikipedia entries added: {wikipedia_added}\n")
        f.write(f"- Wikipedia entries skipped (already present): {wikipedia_skipped}\n")
        f.write(f"- Titles without Wikipedia articles: {len(wikipedia_not_found)}\n")
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
    
    # Wikipedia not found report (saved to repository as requested)
    if wikipedia_not_found:
        not_found_file = os.path.join(output_dir, 'wikipedia_not_found.txt')
        with open(not_found_file, 'w', encoding='utf-8') as f:
            f.write("Titles Without Wikipedia Articles\n")
            f.write("="*40 + "\n\n")
            f.write(f"Found {len(wikipedia_not_found)} titles without Wikipedia articles:\n\n")
            
            for title in sorted(wikipedia_not_found):
                f.write(f"- {title}\n")
    
    # Print summary
    print(f"\nCleanup completed!")
    print(f"- Fixed {newline_fixes} titles with newlines")
    print(f"- Fixed {unicode_fixes} titles with unicode issues")
    print(f"- Found {len(unicode_errors)} titles needing manual unicode review")
    print(f"- Added {wikipedia_added} Wikipedia entries")
    print(f"- Skipped {wikipedia_skipped} entries (Wikipedia already present)")
    print(f"- Could not find Wikipedia articles for {len(wikipedia_not_found)} titles")
    print(f"- Found {len(duplicates)} groups of potential duplicates")
    print(f"- Removed fields: {dict(fields_removed)}")
    print(f"\nFiles created:")
    print(f"- {output_file} (cleaned data)")
    print(f"- {summary_file} (summary report)")
    if unicode_errors:
        print(f"- {os.path.join(output_dir, 'unicode_errors_review.txt')} (unicode issues for manual review)")
    if duplicates:
        print(f"- {os.path.join(output_dir, 'potential_duplicates.txt')} (potential duplicates for manual review)")
    if wikipedia_not_found:
        print(f"- {os.path.join(output_dir, 'wikipedia_not_found.txt')} (titles without Wikipedia articles)")
    
    return True


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Clean up GeoJSON files with unicode fixes, duplicate detection, field removal, and Wikipedia enhancement.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s places.geojson
  %(prog)s places.geojson --output-dir ./cleaned
  %(prog)s /path/to/places.geojson --output-dir /path/to/output
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
    
    # Run cleanup
    success = clean_geojson(args.input_file, args.output_dir)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()