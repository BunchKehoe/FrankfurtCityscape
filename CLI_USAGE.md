# GeoJSON Cleanup CLI Tool

This CLI tool processes GeoJSON files to clean and enhance the data according to specific requirements.

## Usage

```bash
python3 geojson_cleanup_cli.py <input_file> [--output-dir <directory>]
```

### Arguments

- `input_file`: Path to the input GeoJSON file (required)
- `--output-dir` or `-o`: Output directory for cleaned file and reports (optional, defaults to same directory as input file)

### Examples

```bash
# Clean a GeoJSON file in the current directory
python3 geojson_cleanup_cli.py PlacesToVisit4.geojson

# Clean a GeoJSON file and save output to a specific directory
python3 geojson_cleanup_cli.py PlacesToVisit4.geojson --output-dir ./cleaned

# Clean a GeoJSON file with full paths
python3 geojson_cleanup_cli.py /path/to/input/places.geojson --output-dir /path/to/output
```

## What the tool does

1. **Text Cleaning**:
   - Replaces newline characters (`\n`) in title fields with spaces
   - Fixes common Unicode encoding errors for German characters (ä, ö, ü, ß, etc.)

2. **Field Removal**:
   - Removes unwanted fields: `offsetX`, `locked`, `marker-size`, `labelStyle`
   - Also removes legacy fields: `text`, `anchor`, `icon`, `tooltip`, `textPosition`, `stroke`, `rotate`, `offsetY`

3. **Duplicate Detection**:
   - Finds potential duplicate entries based on title similarity (>85% match)
   - Groups similar titles for manual review

4. **Wikipedia Enhancement**:
   - Adds Wikipedia field to entries that don't already have one
   - **Enhanced Language Detection**: Automatically detects appropriate languages based on location context (supports English, German, French, Spanish, Italian, Dutch, Danish, Czech)
   - **Intelligent Translation**: Translates common place-related terms (church, castle, museum, etc.) to target languages before searching
   - **Fuzzy Search**: Uses Wikipedia's search API to find related articles even when exact title matches aren't found
   - **Multi-language Search**: Searches across multiple relevant languages for each location
   - **Quality Preference**: Prefers longer articles with language priority: English > German > others
   - Handles entries without Wikipedia articles gracefully

## Output Files

The tool generates several files:

1. **`<input_name>_cleaned.geojson`**: The cleaned GeoJSON file
2. **`cleanup_summary.txt`**: Summary report of all changes made
3. **`potential_duplicates.txt`**: List of potential duplicate title groups for manual review
4. **`wikipedia_not_found.txt`**: List of titles for which no Wikipedia articles were found
5. **`unicode_errors_review.txt`**: List of titles with potential Unicode issues requiring manual review (if any)

## Requirements

- Python 3.6+
- `requests` library for Wikipedia API access
- Internet connection for Wikipedia lookups

## Error Handling

- If Wikipedia API is unavailable, entries will be added to the "not found" list
- Unicode errors are reported but don't stop processing
- Invalid JSON files will produce an error message and exit

## Notes

- The tool respects existing Wikipedia fields and won't overwrite them
- Wikipedia API calls include small delays to be respectful to the service
- Language detection tries to determine appropriate Wikipedia languages based on location context (supports 8 languages)
- Fuzzy search and translation help find Wikipedia articles even when exact matches aren't available
- All reports are saved to the repository for version control and review