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
    """
    Calculate similarity between two strings using SequenceMatcher.
    Args:
        a (str): First string.
        b (str): Second string.
    Returns:
        float: Similarity ratio between 0 and 1.
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def fix_unicode_errors(text):
    """
    Fix common unicode encoding errors for German and other European characters.
    Args:
        text (str): Input string to fix.
    Returns:
        tuple: (fixed_text, was_fixed, error_description)
            fixed_text (str): The corrected string.
            was_fixed (bool): True if any replacements were made.
            error_description (str|None): Description of suspicious characters, if any.
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


def detect_language_context(title):
    """
    Try to detect if a title suggests a specific language context.
    Args:
        title (str): The place title to analyze.
    Returns:
        list: Suggested language codes in order of preference.
    """
    title_lower = title.lower()
    
    # Language context indicators
    language_indicators = {
        'de': [
            'deutschland', 'germany', 'österreich', 'austria', 'schweiz', 'switzerland',
            'wien', 'vienna', 'berlin', 'münchen', 'munich', 'zürich', 'salzburg', 
            'innsbruck', 'graz', 'linz', 'bern', 'geneva', 'basel', 'hamburg', 'köln',
            'cologne', 'frankfurt', 'stuttgart', 'düsseldorf', 'dortmund', 'essen',
            'bremen', 'dresden', 'hannover', 'nürnberg', 'nuremberg'
        ],
        'fr': [
            'france', 'paris', 'lyon', 'marseille', 'toulouse', 'nice', 'nantes',
            'strasbourg', 'montpellier', 'bordeaux', 'lille', 'rennes', 'reims',
            'le havre', 'saint-étienne', 'toulon', 'grenoble', 'dijon', 'angers',
            'nîmes', 'villeurbanne', 'saint-denis', 'argenteuil', 'rouen', 'mulhouse',
            'caen', 'nancy', 'metz', 'versailles', 'tours', 'amiens', 'limoges',
            'aix-en-provence', 'brest', 'nanterre', 'créteil', 'avignon', 'poitiers'
        ],
        'nl': [
            'netherlands', 'holland', 'amsterdam', 'rotterdam', 'the hague', 'utrecht',
            'eindhoven', 'tilburg', 'groningen', 'almere', 'breda', 'nijmegen',
            'enschede', 'haarlem', 'arnhem', 'zaanstad', 'amersfoort', 'apeldoorn',
            's-hertogenbosch', 'hoofddorp', 'maastricht', 'leiden', 'dordrecht',
            'zoetermeer', 'zwolle', 'deventer', 'delft', 'alkmaar', 'leeuwarden'
        ],
        'da': [
            'denmark', 'copenhagen', 'aarhus', 'odense', 'aalborg', 'esbjerg',
            'randers', 'kolding', 'horsens', 'vejle', 'roskilde', 'herning',
            'silkeborg', 'næstved', 'fredericia', 'viborg', 'køge', 'holstebro',
            'taastrup', 'slagelse', 'hillerød', 'sønderborg', 'svendborg', 'hjørring'
        ],
        'cs': [
            'czech republic', 'czechia', 'prague', 'brno', 'ostrava', 'plzen',
            'liberec', 'olomouc', 'české budějovice', 'hradec králové', 'ústí nad labem',
            'pardubice', 'zlín', 'kladno', 'most', 'opava', 'frýdek-místek',
            'karviná', 'jihlava', 'teplice', 'děčín', 'karlovy vary', 'jablonec nad nisou'
        ],
        'it': [
            'italy', 'rome', 'milan', 'naples', 'turin', 'palermo', 'genoa',
            'bologna', 'florence', 'bari', 'catania', 'venice', 'verona',
            'messina', 'padua', 'trieste', 'brescia', 'prato', 'taranto',
            'modena', 'reggio calabria', 'reggio emilia', 'perugia', 'livorno',
            'ravenna', 'cagliari', 'foggia', 'rimini', 'salerno', 'ferrara'
        ],
        'es': [
            'spain', 'madrid', 'barcelona', 'valencia', 'seville', 'zaragoza',
            'málaga', 'murcia', 'palma', 'las palmas', 'bilbao', 'alicante',
            'córdoba', 'valladolid', 'vigo', 'gijón', 'hospitalet', 'vitoria',
            'coruña', 'granada', 'elche', 'oviedo', 'badalona', 'cartagena',
            'terrassa', 'jerez', 'sabadell', 'santa cruz', 'pamplona', 'almería'
        ]
    }
    
    # Check for specific language contexts
    detected_languages = set()
    
    for lang, indicators in language_indicators.items():
        for indicator in indicators:
            if indicator in title_lower:
                detected_languages.add(lang)
                break
    
    # Build language preference list
    if detected_languages:
        # If we detected specific languages, prioritize them
        languages = list(detected_languages)
        # Always include English and German as fallbacks
        if 'en' not in languages:
            languages.append('en')
        if 'de' not in languages:
            languages.append('de')
        return languages
    
    # Default to English first, then German
    return ['en', 'de']


def translate_basic_terms(title, target_language):
    """
    Perform basic translation of common travel/place-related terms.
    This is a simple approach for common words that appear in place names.
    Args:
        title (str): The place title to translate.
        target_language (str): Target language code (e.g., 'de', 'fr').
    Returns:
        str: Title with common terms translated if possible.
    """
    # Common travel/place terms translations
    translations = {
        'en': {
            'church': 'church', 'cathedral': 'cathedral', 'museum': 'museum', 
            'castle': 'castle', 'palace': 'palace', 'bridge': 'bridge',
            'tower': 'tower', 'square': 'square', 'park': 'park', 
            'garden': 'garden', 'station': 'station', 'airport': 'airport',
            'university': 'university', 'library': 'library', 'theater': 'theater',
            'opera': 'opera', 'restaurant': 'restaurant', 'hotel': 'hotel',
            'market': 'market', 'street': 'street', 'avenue': 'avenue',
            'old town': 'old town', 'city center': 'city center'
        },
        'de': {
            'church': 'kirche', 'cathedral': 'dom', 'museum': 'museum',
            'castle': 'schloss', 'palace': 'palast', 'bridge': 'brücke',
            'tower': 'turm', 'square': 'platz', 'park': 'park',
            'garden': 'garten', 'station': 'bahnhof', 'airport': 'flughafen',
            'university': 'universität', 'library': 'bibliothek', 'theater': 'theater',
            'opera': 'oper', 'restaurant': 'restaurant', 'hotel': 'hotel',
            'market': 'markt', 'street': 'straße', 'avenue': 'allee',
            'old town': 'altstadt', 'city center': 'stadtzentrum'
        },
        'fr': {
            'church': 'église', 'cathedral': 'cathédrale', 'museum': 'musée',
            'castle': 'château', 'palace': 'palais', 'bridge': 'pont',
            'tower': 'tour', 'square': 'place', 'park': 'parc',
            'garden': 'jardin', 'station': 'gare', 'airport': 'aéroport',
            'university': 'université', 'library': 'bibliothèque', 'theater': 'théâtre',
            'opera': 'opéra', 'restaurant': 'restaurant', 'hotel': 'hôtel',
            'market': 'marché', 'street': 'rue', 'avenue': 'avenue',
            'old town': 'vieille ville', 'city center': 'centre-ville'
        },
        'es': {
            'church': 'iglesia', 'cathedral': 'catedral', 'museum': 'museo',
            'castle': 'castillo', 'palace': 'palacio', 'bridge': 'puente',
            'tower': 'torre', 'square': 'plaza', 'park': 'parque',
            'garden': 'jardín', 'station': 'estación', 'airport': 'aeropuerto',
            'university': 'universidad', 'library': 'biblioteca', 'theater': 'teatro',
            'opera': 'ópera', 'restaurant': 'restaurante', 'hotel': 'hotel',
            'market': 'mercado', 'street': 'calle', 'avenue': 'avenida',
            'old town': 'casco antiguo', 'city center': 'centro de la ciudad'
        },
        'it': {
            'church': 'chiesa', 'cathedral': 'cattedrale', 'museum': 'museo',
            'castle': 'castello', 'palace': 'palazzo', 'bridge': 'ponte',
            'tower': 'torre', 'square': 'piazza', 'park': 'parco',
            'garden': 'giardino', 'station': 'stazione', 'airport': 'aeroporto',
            'university': 'università', 'library': 'biblioteca', 'theater': 'teatro',
            'opera': 'opera', 'restaurant': 'ristorante', 'hotel': 'hotel',
            'market': 'mercato', 'street': 'via', 'avenue': 'viale',
            'old town': 'centro storico', 'city center': 'centro città'
        },
        'nl': {
            'church': 'kerk', 'cathedral': 'kathedraal', 'museum': 'museum',
            'castle': 'kasteel', 'palace': 'paleis', 'bridge': 'brug',
            'tower': 'toren', 'square': 'plein', 'park': 'park',
            'garden': 'tuin', 'station': 'station', 'airport': 'luchthaven',
            'university': 'universiteit', 'library': 'bibliotheek', 'theater': 'theater',
            'opera': 'opera', 'restaurant': 'restaurant', 'hotel': 'hotel',
            'market': 'markt', 'street': 'straat', 'avenue': 'laan',
            'old town': 'oude stad', 'city center': 'stadscentrum'
        },
        'da': {
            'church': 'kirke', 'cathedral': 'domkirke', 'museum': 'museum',
            'castle': 'slot', 'palace': 'palads', 'bridge': 'bro',
            'tower': 'tårn', 'square': 'plads', 'park': 'park',
            'garden': 'have', 'station': 'station', 'airport': 'lufthavn',
            'university': 'universitet', 'library': 'bibliotek', 'theater': 'teater',
            'opera': 'opera', 'restaurant': 'restaurant', 'hotel': 'hotel',
            'market': 'marked', 'street': 'gade', 'avenue': 'boulevard',
            'old town': 'gamle by', 'city center': 'bymidte'
        },
        'cs': {
            'church': 'kostel', 'cathedral': 'katedrála', 'museum': 'muzeum',
            'castle': 'hrad', 'palace': 'palác', 'bridge': 'most',
            'tower': 'věž', 'square': 'náměstí', 'park': 'park',
            'garden': 'zahrada', 'station': 'nádraží', 'airport': 'letiště',
            'university': 'univerzita', 'library': 'knihovna', 'theater': 'divadlo',
            'opera': 'opera', 'restaurant': 'restaurace', 'hotel': 'hotel',
            'market': 'trh', 'street': 'ulice', 'avenue': 'třída',
            'old town': 'staré město', 'city center': 'centrum města'
        }
    }
    
    # Get translations for target language
    target_translations = translations.get(target_language, {})
    if not target_translations:
        return title
    
    # Convert title to lowercase for matching
    title_lower = title.lower()
    translated_title = title
    
    # Replace English terms with target language terms
    for english_term, translated_term in target_translations.items():
        if english_term in title_lower:
            # Case-preserving replacement
            translated_title = re.sub(
                re.escape(english_term), 
                translated_term, 
                translated_title, 
                flags=re.IGNORECASE
            )
    
    return translated_title


def fuzzy_search_wikipedia(title, language, max_results=5):
    """
    Perform fuzzy search on Wikipedia using the opensearch API.
    Args:
        title (str): The search query.
        language (str): Wikipedia language code.
        max_results (int): Maximum number of results to return.
    Returns:
        list: Tuples of (page_title, page_url, summary_length).
    """
    try:
        # Use opensearch API for fuzzy search
        search_url = f"https://{language}.wikipedia.org/w/api.php"
        params = {
            'action': 'opensearch',
            'search': title,
            'limit': max_results,
            'namespace': 0,
            'format': 'json'
        }
        
        response = requests.get(search_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # opensearch returns [query, [titles], [descriptions], [urls]]
            if len(data) >= 4:
                titles = data[1]
                descriptions = data[2]
                urls = data[3]
                
                results = []
                for i, (page_title, url) in enumerate(zip(titles, urls)):
                    # Try to get page summary to estimate length
                    try:
                        summary_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(page_title)}"
                        summary_response = requests.get(summary_url, timeout=5)
                        
                        summary_length = 0
                        if summary_response.status_code == 200:
                            summary_data = summary_response.json()
                            if summary_data.get('type') == 'standard':
                                # Estimate length from extract
                                extract = summary_data.get('extract', '')
                                summary_length = len(extract) * 10  # Rough estimate
                        
                        results.append((page_title, url, summary_length))
                        
                        # Small delay to be respectful
                        time.sleep(0.1)
                        
                    except Exception as e:
                        # If we can't get summary, still include the result
                        results.append((page_title, url, 0))
                
                return results
        
        return []
        
    except Exception as e:
        print(f"  Warning: Error in fuzzy search for '{title}' in {language}: {e}")
        return []


def search_wikipedia_article(title, languages=['en', 'de']):
    """
    Search for a Wikipedia article about the given title using translation and fuzzy search.
    Args:
        title (str): The place title to search for.
        languages (list): List of language codes to try, in order.
    Returns:
        tuple: (url, language, length) of the best article found, or (None, None, 0) if not found.
    """
    best_article = None
    best_length = 0
    best_lang = None
    best_url = None
    
    for lang in languages:
        try:
            # First try direct lookup with original title
            search_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
            response = requests.get(search_url, timeout=10)
            
            direct_results = []
            if response.status_code == 200:
                data = response.json()
                if data.get('type') == 'standard':
                    article_url = data.get('content_urls', {}).get('desktop', {}).get('page', '')
                    extract_length = len(data.get('extract', '')) * 10  # Rough estimate
                    direct_results.append((title, article_url, extract_length))
            
            # Translate title for this language
            translated_title = translate_basic_terms(title, lang)
            
            # Perform fuzzy search with original title
            fuzzy_results = fuzzy_search_wikipedia(title, lang, max_results=3)
            
            # If we translated the title, also search with translated terms
            if translated_title != title:
                translated_fuzzy_results = fuzzy_search_wikipedia(translated_title, lang, max_results=3)
                fuzzy_results.extend(translated_fuzzy_results)
            
            # Combine all results
            all_results = direct_results + fuzzy_results
            
            # Find best result for this language
            for page_title, url, length in all_results:
                if length > 0:  # Only consider articles with content
                    # Language preference: en > de > others, but longer articles can override
                    is_better = (
                        length > best_length or
                        (length >= best_length * 0.8 and lang == 'en' and best_lang != 'en') or
                        (length >= best_length * 0.9 and lang == 'de' and best_lang not in ['en'])
                    )
                    
                    if is_better:
                        best_length = length
                        best_lang = lang
                        best_url = url
            
            # Add delay between languages
            time.sleep(0.2)
            
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"  Warning: Error searching Wikipedia ({lang}) for '{title}': {e}")
            continue
    
    return best_url, best_lang, best_length


def clean_geojson(input_file, output_dir=None):
    """
    Main function to clean the GeoJSON file.
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
                print(f"    Languages to search: {', '.join(preferred_languages)}")
                
                # Search for Wikipedia article with enhanced fuzzy search and translation
                wiki_url, wiki_lang, wiki_length = search_wikipedia_article(
                    properties['title'], preferred_languages
                )
                
                if wiki_url:
                    properties['Wikipedia'] = wiki_url
                    wikipedia_added += 1
                    print(f"    Found: {wiki_url} ({wiki_lang}, ~{wiki_length} chars)")
                else:
                    wikipedia_not_found.append(properties['title'])
                    print(f"    Not found in any language")
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
    """
    Main CLI entry point for geojson_cleanup_cli.py.
    Parses arguments and runs the cleaning process.
    """
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