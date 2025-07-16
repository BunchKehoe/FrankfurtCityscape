# FrankfurtCityscape

## CLI Tools: GeoJSON Cleanup

This project includes a command-line tool for cleaning and enhancing GeoJSON files containing places to visit. The tool can:

- Remove literal `\n` characters from titles
- Fix common unicode errors (especially for German and European characters)
- Remove unused/unwanted fields (e.g., `offsetX`, `locked`, `marker-size`, `labelStyle`)
- Detect and report potential duplicate place names
- Add a `Wikipedia` field with the best-matching article URL (preferring English, then German, and longest articles)
- Generate summary and error reports

### Usage

1. **Install Python 3** (if not already installed)
2. **Install dependencies** (requests):
   ```bash
   pip3 install requests
   ```
3. **Run the CLI tool:**
   ```bash
   python3 geojson_cleanup_cli.py path/to/yourfile.geojson
   # or specify an output directory:
   python3 geojson_cleanup_cli.py path/to/yourfile.geojson --output-dir path/to/outputdir
   ```

#### Example

```bash
python3 geojson_cleanup_cli.py PlacesToVisit4.geojson --output-dir ./cleaned
```

This will process your GeoJSON file and write cleaned data and reports to the specified output directory.

### Output

The tool will generate:
- A cleaned GeoJSON file (with `_cleaned` suffix)
- `cleanup_summary.txt` (summary of changes)
- `unicode_errors_review.txt` (if any unicode issues need manual review)
- `potential_duplicates.txt` (if any duplicate titles are found)
- `wikipedia_not_found.txt` (if any titles have no Wikipedia article)

### Functionality

- **Unicode Fixes:** Automatically corrects common encoding errors for German and other European characters in titles.
- **Duplicate Detection:** Finds groups of similar or duplicate place names for manual review.
- **Wikipedia Enhancement:** Searches for the best Wikipedia article for each place, using fuzzy search and translation.
- **Field Cleanup:** Removes unused or unwanted fields from each feature's properties.

### For Developers

All major functions in `geojson_cleanup_cli.py` are documented with docstrings. See the code for details on each function's purpose and arguments.
