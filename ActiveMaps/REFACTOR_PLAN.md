# PlacesToVisitScript.html — Refactor Plan (v2)

## Overview

**Greenfield rewrite** of the `<script>` block of `PlacesToVisitScript.html`. Fixes 6 bugs, eliminates mobile/desktop code duplication (~90% identical), removes dead code, and adds 6 new features.

**File:** `ActiveMaps/PlacesToVisitScript.html`  
**Scope:** Lines 13–85 (`<script>` block only). CSS and HTML markup (lines 1–12) are untouched.  
**Backup:** `PlacesToVisitScript.html.bak`  
**Approach:** Write the entire new `<script>` block from scratch as clean, readable, well-structured code. Drop it in to replace lines 13–85.

---

## Current Problems (6 Bugs/Issues)

### Bug 1 — Fragile URL Slug Matching
- **Location:** `applyLocationConfig()` → `currentUrl.includes(slug)`
- **Problem:** `includes()` matches partial strings. A slug like `"berg"` would match a URL containing `"nuremberg"`.
- **Fix:** Split the URL pathname into segments and match against those:
  ```js
  const segments = new URL(currentUrl).pathname.split('/');
  if (segments.includes(slug)) { ... }
  ```

### Bug 2 — Massive Mobile/Desktop Code Duplication
- **Problem:** The mobile and desktop branches each define their own copies of:
  - Layer definitions (cultural-landscapes, national-parks, railroads, vineyards, places-icons-regional, places-icons-city) — 100% identical
  - `applyPlacesFilter()` — 100% identical
  - `setupLegendFilters()` — 100% identical
  - `activeFilters` Set — 100% identical
  - Map controls (NavigationControl, FullscreenControl, GeolocateControl, ScaleControl) — 100% identical
  - Aria label setup via `setTimeout` — 100% identical
  - Click-to-Wikipedia handlers — 100% identical
  - Cursor pointer handlers — 100% identical
- **Fix:** Extract all shared logic into top-level functions called from both branches. Only branch on:
  - `cooperativeGestures: true` (mobile only)
  - Legend UI (mobile uses toggle button + overlay; desktop uses inline sidebar with resize check)
  - Popup behavior (desktop has hover popups; mobile uses direct click-to-Wikipedia)

### Bug 3 — Desktop `addSources()` Inconsistency
- **Problem:** Mobile uses `addSources(map)` (the shared function). Desktop manually calls `map.addSource(...)` for each source individually, duplicating the URLs already in `SOURCES`.
- **Fix:** Desktop should use `addSources(map)` like mobile does.

### Bug 4 — Popup Listener Leak (Desktop)
- **Problem:** `map.on("mouseenter", (e) => { ... })` (no layer filter) fires on every mouse move over the map. Each time, it queries `.mapboxgl-popup` and attaches new `mouseenter`/`mouseleave` listeners to the popup element — accumulating duplicate listeners.
- **Fix:** Attach popup hover listeners once per popup creation (inside `setupPlacesLayerEvents`), not on every generic mouseenter.

### Bug 5 — Unused `historical-regions` Source
- **Problem:** `SOURCES` includes `"historical-regions": "mapbox://jcbunch3.cmd6clxb92tlo1ns8ro5qgig8"` but no layer is ever created for it. It wastes a tile request.
- **Fix:** Remove it from `SOURCES`.

### Bug 6 — Jarring Snap Instead of Animation
- **Problem:** `applyLocationConfig()` calls `map.setCenter()` and `map.setZoom()` after map construction, causing a visible snap.
- **Fix:** **Replaced entirely by Feature 1 (fitBounds).** We no longer store center/zoom at all — we compute a bounding box from the polygon geometry and pass it as `bounds` in the Map constructor. No setCenter/setZoom, no snap, no animation needed. The map starts at the correct view.

---

## New Features (6)

### Feature 1 — `map.fitBounds()` from Polygon Geometry
- **What:** Instead of reading `properties.coordinates` (lat/lng/zoom) from the dataset, compute the actual bounding box from each feature's polygon `geometry.coordinates`. Store the bbox in `locationConfig`. Use the `bounds` option in the `Map()` constructor to frame the region perfectly regardless of screen size.
- **Why:** The current center/zoom approach is not working reliably. `fitBounds` adapts to any viewport.
- **Implementation:**
  ```js
  // In loadLocationConfig():
  function computeBbox(geometry) {
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    const rings = geometry.type === 'MultiPolygon'
      ? geometry.coordinates.flat()
      : geometry.coordinates;
    for (const ring of rings) {
      for (const [lng, lat] of ring) {
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }
    return [[minLng, minLat], [maxLng, maxLat]];
  }

  // Store bbox instead of center/zoom:
  locationConfig[urlSlug] = computeBbox(feature.geometry);

  // In Map constructor:
  const bbox = getLocationBbox();
  new mapboxgl.Map({
    bounds: bbox,  // replaces center + zoom
    fitBoundsOptions: { padding: isMobile ? 30 : 60 },
    ...
  });
  ```
- **Removes:** `properties.coordinates` parsing, `MOBILE_ZOOM_OFFSET` constant, `applyLocationConfig()` function entirely.

### Feature 2 — Sky Layer for 3D Terrain
- **What:** Add an atmospheric sky layer to complement the existing `setTerrain()` call.
- **Implementation:**
  ```js
  map.addLayer({
    id: 'sky',
    type: 'sky',
    paint: {
      'sky-type': 'atmosphere',
      'sky-atmosphere-sun': [0.0, 90.0],
      'sky-atmosphere-sun-intensity': 15
    }
  });
  ```
- **Where:** Inside `map.on('load')`, right after `setTerrain()`.

### Feature 3 — `map.on('idle')` Instead of `setTimeout`
- **What:** Replace `setTimeout(() => {...}, 1000)` for ARIA label setup with `map.once('idle', () => {...})`.
- **Why:** `idle` fires when the map is done rendering. It's reliable regardless of network speed; the 1-second timeout may fire too early on slow connections or too late on fast ones.
- **Implementation:**
  ```js
  map.once('idle', () => {
    // set ARIA labels
    // set role/tabindex on legend items
  });
  ```

### Feature 4 — `hash: true` for Shareable URLs
- **What:** Add `hash: true` to the Map constructor options.
- **Effect:** Zoom/lat/lng appended to URL hash (e.g., `#5.1/52.5/8.8`). Users can bookmark or share specific map views.
- **Implementation:** Single line in Map constructor:
  ```js
  new mapboxgl.Map({ ..., hash: true });
  ```

### Feature 5 — Icon/Text Display Priority
Three sub-requirements for how places render:

**5a. City entries: icon + text always visible, above all other markers**
- City entries are already in their own layer (`places-icons-city`) rendered AFTER `places-icons-regional`, so they're visually on top.
- **Add `text-allow-overlap: true`** to the city layer so city text is never culled by the collision algorithm.
- Keep `icon-allow-overlap: true` (already set).

**5b. Red (#a10001) entries: above everything except city**
- In `places-icons-regional`, use `symbol-sort-key` that gives red entries the HIGHEST value within the layer (rendered last = visually on top):
  ```js
  "symbol-sort-key": ["case",
    ["in", ["get", "marker-color"],
      ["literal", ["#a10001", "#8f1b11", "#aa3524", "#9b0101", "#a43b2d"]]],
    100,   // red: rendered last (on top) within this layer
    ["match", ["get", "marker-symbol"],
      ["circle-sm", "square-sm", "mountain"], 5,
      ["monument", "museum", "religious-christian", "religious-islam", "religious-jewish"], 3,
      1
    ]
  ]
  ```
- Also set `text-allow-overlap: true` on the regional layer so red entry text is never hidden. (This makes ALL regional text always-visible, which is fine since we already have `icon-allow-overlap: true`.)

**5c. Dynamic text position relative to icon**
- Already using `text-variable-anchor` with 8 positions: `["top","bottom","left","right","top-left","top-right","bottom-left","bottom-right"]`
- Mapbox automatically picks the best position to avoid collisions.
- Keep `text-radial-offset` expression (0.5 for red city, 1 for others) for spacing.

### Feature 6 — `flyTo()` for Programmatic Navigation (Future-Proofing)
- **What:** Although the initial view is now set via `bounds` in the constructor (no animation needed), any future programmatic navigation should use `map.flyTo()` instead of `setCenter()`/`setZoom()`.
- **Not needed now** but the architecture is designed to make this easy to add later.

---

## Dead Code to Remove

| Code | Location | Reason |
|------|----------|--------|
| `const currentLocation = window.location.href;` | Line 73 (approx) | Never referenced anywhere |
| `const DESKTOP_STYLE = "mapbox://styles/..."` | Line 15 | Same value as `MOBILE_STYLE`; desktop branch uses its own local `desktopMapLayer` variable anyway |
| `const desktopMapLayer = "mapbox://styles/..."` | Desktop branch | Redundant — use single `MAP_STYLE` constant |
| `MOBILE_STYLE` constant | Line 14 | Rename to single `MAP_STYLE` |
| Source verification `if(!map.getSource(...))` blocks | Desktop `map.on("load")` | Sources were just added on the line above; these checks can never fail |

---

## Refactored Architecture

### Constants (top of script)

```js
const MAPBOX_TOKEN = "pk.eyJ1IjoiamNidW5jaDMiLCJhIjoiY2t6NzM0em9uMGlvbzMwbWdkbmR5N2loaCJ9.eKquRAbhpJDDshFFKtd9Yw";
const MAP_STYLE = "mapbox://styles/jcbunch3/cljssqa5h01ch01o4adoyhdlt";
const DEFAULT_CENTER = [8.8, 52.5];
const DEFAULT_ZOOM_DESKTOP = 5.1;
const DEFAULT_ZOOM_MOBILE = 4;
const DATASET_ID = 'cmljrq0xj0pp11mpcywksh76c';
const USERNAME = 'jcbunch3';

const SOURCES = {
  places: "mapbox://jcbunch3.cmd6clxb92tlo1ns8ro5qgig8-0g7n5",
  "cultural-landscapes": "mapbox://jcbunch3.9b7pcnhy",
  "national-parks": "mapbox://jcbunch3.clkc6qkel2xr42aleuq3sjnsq-0zrfg",
  railroads: "mapbox://jcbunch3.8o05xvpq",
  vineyards: "mapbox://jcbunch3.86vjg7du",
  "mapbox-dem": "mapbox://mapbox.mapbox-terrain-dem-v1"
};
// NOTE: "historical-regions" REMOVED — no layer uses it
// NOTE: MOBILE_STYLE, DESKTOP_STYLE, desktopMapLayer all REMOVED — single MAP_STYLE
// NOTE: MOBILE_ZOOM_OFFSET REMOVED — fitBounds handles viewport adaptation

const DEFAULT_ACTIVE_FILTERS = [
  'city','circle-sm','square-sm','monument','museum','crosshammer',
  'lookout-360','religious-christian','religious-jewish','mountain','food','restaurant'
];
```

### Data Flow

```
loadLocationConfig()
  ├─ Fetch all features from Historical Regions v2 dataset (paginated)
  ├─ For each feature with a url + polygon geometry:
  │   ├─ Extract URL slug from properties.url
  │   └─ Compute bounding box from geometry.coordinates (NOT properties.coordinates)
  └─ Store in locationConfig: { slug: [[minLng,minLat],[maxLng,maxLat]] }

initializeMap()
  ├─ Determine isMobile (window.innerWidth <= 991)
  ├─ Look up URL slug → get bbox from locationConfig
  ├─ Create Map with `bounds: bbox` (or center/zoom defaults if no match)
  │   └─ Includes: hash:true, cooperativeGestures (mobile only)
  └─ map.on('load'):
      ├─ addSources(map)
      ├─ setTerrain + addSkyLayer
      ├─ addOverlayLayers(map)
      ├─ addPlacesLayers(map)         ← shared layout/paint, 2 layers
      ├─ addMapControls(map)
      ├─ applyPlacesFilter(map, filters)
      ├─ if mobile: setupMobileLegend + setupMobileClickEvents
      │  else:      setupDesktopLegend + setupDesktopPopups
      └─ map.once('idle'): setupAriaLabels
```

### Shared Functions

#### `loadLocationConfig()` — MODIFIED (Feature 1)
- Same pagination logic (limit=100, start cursor)
- **Changed:** For each feature, compute `computeBbox(feature.geometry)` instead of parsing `properties.coordinates`
- **Changed:** Store `locationConfig[slug] = [[minLng,minLat],[maxLng,maxLat]]` instead of `{center, zoom}`
- Requires feature to have both `properties.url` AND valid polygon geometry

#### `computeBbox(geometry)` — NEW (Feature 1)
- Handles both `Polygon` and `MultiPolygon` geometry types
- Returns `[[minLng, minLat], [maxLng, maxLat]]`

#### `getLocationBbox()` — NEW (replaces `getLocationFromUrl`, fixes Bug 1)
- Splits `window.location.pathname` by `/` into segments (fixes fragile matching)
- Returns the bbox for the first matching slug, or `null`
```js
function getLocationBbox() {
  const segments = window.location.pathname.split('/');
  for (const [slug, bbox] of Object.entries(locationConfig)) {
    if (segments.includes(slug)) {
      console.log('Matched location:', slug);
      return bbox;
    }
  }
  return null;
}
```

#### `addSources(map)` — unchanged
Iterates `SOURCES` object, adds each as vector or raster-dem.

#### `addSkyLayer(map)` — NEW (Feature 2)
```js
function addSkyLayer(map) {
  map.addLayer({
    id: 'sky',
    type: 'sky',
    paint: {
      'sky-type': 'atmosphere',
      'sky-atmosphere-sun': [0.0, 90.0],
      'sky-atmosphere-sun-intensity': 15
    }
  });
}
```

#### `addOverlayLayers(map)` — NEW (fixes Bug 2)
Adds all overlay layers in order:
1. `cultural-landscapes-fill` (visibility: none — toggled on by user)
2. `cultural-landscapes-label` (visibility: none)
3. `national-parks-fill` (visibility: visible)
4. `national-parks-label` (visibility: visible)
5. `railroads` (visibility: visible)
6. `vineyards` (visibility: visible)

Layer configs are identical to current code — just extracted into one shared function.

#### `getPlacesLayout()` — NEW
Returns the shared `layout` object used by both places layers:
- `icon-image`: match expression mapping marker-symbol → icon name
- `icon-size`: 1.3
- `icon-allow-overlap`: true
- `icon-ignore-placement`: true
- `symbol-sort-key`: **UPDATED** for Feature 5b — red entries get 100, others sorted by type
- `text-field`: `["get", "title"]`
- `text-font`: match expression by marker-symbol
- `text-size`: case expression by marker-color + marker-symbol
- `text-variable-anchor`: 8 positions (Feature 5c — dynamic positioning)
- `text-radial-offset`: case expression
- `text-allow-overlap`: **true** (Feature 5a/5b)
- `text-optional`: false

#### `getPlacesPaint()` — NEW
Returns the shared `paint` object:
- `text-color`: match expression by marker-color
- `text-halo-color`: `"#ffffff"`
- `text-halo-width`: 1.5
- `icon-opacity`: 1
- `text-opacity`: 1

#### `addPlacesLayers(map)` — NEW
Adds two layers using shared layout/paint:
1. `places-icons-regional` (minzoom 0, maxzoom 14, filter: `["!=", ["get","zoom"], "city"]`)
2. `places-icons-city` (minzoom 12, maxzoom 22, filter: `["==", ["get","zoom"], "city"]`)

City layer rendered AFTER regional → always on top visually (Feature 5a).

#### `addMapControls(map)` — NEW
Adds (identical for mobile and desktop):
- `NavigationControl` (top-right)
- `FullscreenControl` (top-right)
- `GeolocateControl` (top-right, enableHighAccuracy, trackUserLocation, showUserHeading)
- `ScaleControl` (bottom-right, metric, maxWidth 100)

#### `setupAriaLabels(map, legendSelector)` — NEW (Feature 3)
Uses `map.once('idle')` instead of `setTimeout(1000)`:
```js
function setupAriaLabels(map, legendSelector) {
  map.once('idle', () => {
    const ariaMap = {
      '.mapboxgl-ctrl-fullscreen': 'Toggle fullscreen view',
      '.mapboxgl-ctrl-geolocate': 'Find my location',
      '.mapboxgl-ctrl-zoom-in': 'Zoom in',
      '.mapboxgl-ctrl-zoom-out': 'Zoom out',
      '.mapboxgl-ctrl-compass': 'Reset map rotation'
    };
    Object.entries(ariaMap).forEach(([sel, label]) => {
      const el = document.querySelector(sel);
      if (el) el.setAttribute('aria-label', label);
    });
    document.querySelectorAll(legendSelector + ' .legend-item').forEach(item => {
      item.setAttribute('role', 'button');
      item.setAttribute('tabindex', '0');
      item.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); item.click(); }
      });
    });
  });
}
```

#### `createLayerToggle(map, filter)` — unchanged
Returns a toggle function for overlay layer pairs/singles.

#### `toggleLayerPair(map, fillId, labelId)` — unchanged
#### `toggleSingleLayer(map, layerId)` — unchanged

#### `applyPlacesFilter(map, filters)` — MODIFIED
Moved `map` to explicit parameter (was closure). Logic unchanged.

#### `setupLegendFilters(overlay, map, activeFilters, applyFilter)` — MODIFIED
Takes explicit parameters: the overlay element, map instance, activeFilters Set, and the filter callback. Shared between mobile and desktop.

#### `setupDesktopPopups(map)` — NEW (fixes Bug 4)
All popup state encapsulated in closure:
```js
function setupDesktopPopups(map) {
  let popup = null, popupTimeout = null, showPopupTimeout = null;

  function clearTimers() { ... }
  function removePopup() { ... }

  function setupPlacesLayerEvents(layerId) {
    map.on("mouseenter", layerId, (e) => {
      map.getCanvas().style.cursor = "pointer";
      clearTimers();
      removePopup();
      // Show popup after 1s delay
      showPopupTimeout = setTimeout(() => {
        popup = new mapboxgl.Popup(...)
          .trackPointer()
          .setLngLat(e.lngLat)
          .setHTML(popupContent)
          .addTo(map);

        // Attach hover listeners ONCE per popup (fixes Bug 4)
        const el = popup.getElement();
        el.addEventListener('mouseenter', () => { ... clear dismiss timer ... });
        el.addEventListener('mouseleave', () => { ... start dismiss timer ... });

        // Wire close + wikipedia buttons
      }, 1000);
    });

    map.on("mouseleave", layerId, () => { ... dismiss after 1s ... });
    map.on("click", layerId, (e) => { ... open Wikipedia ... });
  }

  setupPlacesLayerEvents("places-icons-regional");
  setupPlacesLayerEvents("places-icons-city");

  // Generic click to dismiss popup (excluding clicks on popup itself)
  map.on("click", (e) => {
    if (!e.originalEvent.target.closest('.mapboxgl-popup')) removePopup();
  });
}
```

**Key fix:** The old code had `map.on("mouseenter", (e) => {...})` (NO layer filter) which fired on every mouse move and re-attached listeners to the popup element each time. Now popup hover listeners are attached once inside the `setTimeout` callback when a popup is created.

#### `setupMobileClickEvents(map)` — NEW
Simple click-to-Wikipedia handlers for both place layers + cursor pointer handlers. No popups on mobile.

### `initializeMap()` — Rewritten

```js
function initializeMap() {
  mapboxgl.accessToken = MAPBOX_TOKEN;
  const isMobile = window.innerWidth <= 991;

  // 1. Check for region bbox match (Feature 1)
  const bbox = getLocationBbox();

  // 2. Build map constructor options
  const mapOptions = {
    container: "map",
    style: MAP_STYLE,
    cooperativeGestures: isMobile,
    optimizeForTerrain: true,
    fadeDuration: 300,
    crossSourceCollisions: true,
    hash: true  // Feature 4
  };

  if (bbox) {
    // Use fitBounds via constructor — no snap (Feature 1)
    mapOptions.bounds = bbox;
    mapOptions.fitBoundsOptions = { padding: isMobile ? 30 : 60 };
  } else {
    // Default view
    mapOptions.center = DEFAULT_CENTER;
    mapOptions.zoom = isMobile ? DEFAULT_ZOOM_MOBILE : DEFAULT_ZOOM_DESKTOP;
  }

  const map = new mapboxgl.Map(mapOptions);
  map.on('error', (e) => console.error('Map error:', e.error));

  // 3. On load — all shared setup
  map.on("load", () => {
    addSources(map);
    map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 });
    addSkyLayer(map);                   // Feature 2
    addOverlayLayers(map);
    addPlacesLayers(map);
    addMapControls(map);

    const activeFilters = new Set(DEFAULT_ACTIVE_FILTERS);
    applyPlacesFilter(map, Array.from(activeFilters));

    // 4. Only divergence: legend UI + interaction style
    if (isMobile) {
      setupMobileLegend(map, activeFilters);
      setupMobileClickEvents(map);
    } else {
      setupDesktopLegend(map, activeFilters);
      setupDesktopPopups(map);
    }

    // 5. ARIA labels on idle (Feature 3)
    setupAriaLabels(map, isMobile ? '#legend-mobile' : '#legend');
  });
}
```

### Mobile Legend — `setupMobileLegend(map, activeFilters)`
- Gets `#legend-mobile`, `#legend-toggle`, `#legend-close` elements
- Sets innerHTML via `getLegend()`
- Wires toggle/close buttons
- Calls `setupLegendFilters(overlay, map, activeFilters, applyPlacesFilter)`

### Desktop Legend — `setupDesktopLegend(map, activeFilters)`
- Gets `#legend` element
- Sets innerHTML via `getLegend()`, shows it
- `checkLegendVisibility()` + resize listener
- Calls `setupLegendFilters(overlay, map, activeFilters, applyPlacesFilter)`

---

## What Stays the Same

- **CSS** (line 4) — completely untouched
- **HTML structure** (lines 5–12) — completely untouched
- **`getLegend()` function** — returns the same HTML string
- **Mapbox style URL** — `mapbox://styles/jcbunch3/cljssqa5h01ch01o4adoyhdlt`
- **Tileset IDs and source-layer names** — all unchanged
- **Overlay layer configs** — same paint/layout properties
- **Icon-image match expression** — same marker-symbol → icon mapping
- **Text-color match expression** — same marker-color → color mapping
- **Popup HTML template** — same structure (close button, title, Wikipedia button)
- **Dataset ID** — `cmljrq0xj0pp11mpcywksh76c`
- **Visual appearance** — same map style, same legend layout, same popups

## What Changes

| Before | After | Why |
|--------|-------|-----|
| `properties.coordinates` (lat/lng/zoom) | `computeBbox(geometry)` | Feature 1: fitBounds from polygon |
| `map.setCenter()` + `map.setZoom()` | `bounds` in Map constructor | Feature 1: no snap |
| No sky layer | `addSkyLayer(map)` | Feature 2: depth for 3D terrain |
| `setTimeout(1000)` for ARIA | `map.once('idle')` | Feature 3: reliable timing |
| No hash | `hash: true` | Feature 4: shareable URLs |
| City text can be culled | `text-allow-overlap: true` on city layer | Feature 5a |
| Red entries have no sort priority | `symbol-sort-key` gives red entries highest value | Feature 5b |
| Two 90%-identical branches | Shared functions, branch only for legend + interactions | Bug 2 fix |
| Desktop manually adds sources | Uses shared `addSources(map)` | Bug 3 fix |
| Generic mouseenter re-attaches popup listeners | Listeners attached once per popup creation | Bug 4 fix |
| `historical-regions` in SOURCES | Removed | Bug 5 fix |
| `currentUrl.includes(slug)` | `pathname.split('/').includes(slug)` | Bug 1 fix |

---

## Execution Strategy

1. **Write the complete new `<script>...</script>` block** as clean, readable, indented JavaScript
2. **Replace lines 13–85** of PlacesToVisitScript.html with the new script block
3. **Verify** no syntax errors

This is a greenfield rewrite of the script portion only. The CSS and HTML divs remain byte-for-byte identical.

---

## Verification Checklist

### Bug Fixes
- [ ] URL slug matching works for known slugs (e.g., `carinthia`, `upper-palatinate`)
- [ ] URL slug matching does NOT false-match partial strings (e.g., `berg` ≠ `nuremberg`)
- [ ] No duplicate code between mobile and desktop branches
- [ ] Desktop uses `addSources(map)` (not manual source additions)
- [ ] Popup hover listeners not accumulated (check with DevTools event listeners)
- [ ] `historical-regions` source NOT requested (check Network tab)
- [ ] No dead variables (`currentLocation`, `DESKTOP_STYLE`, `desktopMapLayer`)

### New Features
- [ ] Region pages: map fits to polygon bounding box (check multiple regions)
- [ ] Non-region pages: map shows default center/zoom
- [ ] Sky layer visible when tilting map in 3D
- [ ] ARIA labels set reliably (no race condition with rendering)
- [ ] URL hash updates when panning/zooming (e.g., `#5.1/52.5/8.8`)
- [ ] Navigating to a hash URL restores that view
- [ ] City markers: text always visible, never culled by collision
- [ ] Red (#a10001) markers: visually above other non-city markers
- [ ] Text position adjusts dynamically to avoid collisions

### Core Functionality
- [ ] File loads without JS errors in browser console
- [ ] Location config loads from dataset (check console log for count)
- [ ] Mobile: legend toggle/close works
- [ ] Mobile: click-to-Wikipedia works on both place layers
- [ ] Desktop: hover popup appears after ~1s delay
- [ ] Desktop: popup has working Wikipedia button and close button
- [ ] Desktop: popup dismisses on mouseleave after ~1s
- [ ] Desktop: hovering over popup keeps it open
- [ ] Desktop: legend sidebar shows/hides based on container width
- [ ] All overlay toggles work (national parks, railroads, vineyards, cultural landscapes off→on)
- [ ] Filter toggles work (clicking legend items filters place icons)
- [ ] Terrain/3D exaggeration visible
- [ ] Map controls present (nav, fullscreen, geolocate, scale)
