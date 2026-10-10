# GreenLens contract v1 — Step 4

## GPS processing extension

The new `POST /satellite` accepts `{lat,lng}`, polling `{lat,lng,jobId}`, or explicit failed-field retry `{lat,lng,retryFailed:true}`. It returns queued/processing (HTTP 202), cached ready/partial/no_data (200), invalid request (400), busy (429, retry after 15 seconds), or sanitized service/budget failure (503). Successful partial responses can contain NDVI while temperature is still running. Job IDs name a generation; dataset IDs add an immutable `ndvi` or `final` revision. `POST /query` accepts an optional `datasetId` so citations match that exact shown result. Missing IDs retain the historical Aliganj contract below.

Processing uses 2 km projected tiles with 400 cells, per-field cloud masks and provenance, and 24-hour freshness. The browser still displays a 900 m GPS-centered crop. New jobs require verified billing and a conservative reservation under the user's $10 monthly account ceiling. Budget stops are persistent for the billing month; repeated requests do not keep making billable billing checks. This extension is deployed; measured delivery evidence is recorded in `deployment.md`.

The SAM Lambda implements POST /query using fixed data summaries, with no AI model. Vite development proxies /query to the SAM local API on port 3001 unless VITE_QUERY_URL overrides it. Mock preview runs locally and cannot submit real-data summary requests. The API stack is deployed at `https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/query`. The frontend is live through Amplify at `https://production.d3piecnpvqjn3g.amplifyapp.com`, which is the exact allowed browser origin. Direct CloudFront provisioning awaits AWS account verification. See [deployment status](deployment.md).

## Grid (S3 object)

```json
{
  "bbox": [80.9447, 26.84535, 80.9477, 26.84805],
  "cellSizeM": 100,
  "cells": [{"lat":26.8476,"lng":80.9462,"ndvi":0.22,"tempC":37}]
}
```

- WGS84 degrees. `bbox` is `[west, south, east, north]`. Coordinates represent cell centres. Size is metres, nominal in the synthetic fixture; the real pipeline must use a projected metric grid.
- `ndvi`: number in [-1,1] or `null`. This is a vegetation index, **not** green-cover percentage.
- `tempC`: land surface temperature in Celsius or `null`; it is **not** air temperature.
- Missing/cloud-masked values are `null`, never 0 as a missing-data marker. Outside coverage returns an empty `cells` array.
- The example and fixture origin (26.8467, 80.9462) are synthetic test coordinates. The real demo reference is 26.8879107, 80.9494493 in Sector New E, Aliganj.

## POST /query

```json
{"lat":26.8879107,"lng":80.9494493,"heading":0,"question":"Why is this block hotter?"}
```

Latitude [-90,90], longitude [-180,180], heading [0,360), question a nonblank string up to 1000 characters. The backend validates the request and returns HTTP 400 for invalid input. Booleans and nonfinite coordinates are rejected. Missing GPS must not trigger an invented/default location. Heading is approximate and may be manually set; the tools compare the surrounding area regardless of heading.

HTTP 200 body:

```json
{
 "layers": {
   "source":"mock",
   "status":"ok",
   "grid": {"bbox":[80.9447,26.84535,80.9477,26.84805],"cellSizeM":100,"cells":[{"lat":26.8476,"lng":80.9462,"ndvi":0.22,"tempC":37}]}
 },
 "answer":null,
 "scenario":null
}
```

`layers.source`: `mock`, `satellite`, or `none`. `layers.status`: `ok` or `no_data`. No coverage is HTTP 200 with status `no_data` and `cells: []`. Network/provider failure is HTTP 503 with `{"error":{"code":"SERVICE_UNAVAILABLE","message":"Data service unavailable"}}`; the frontend must not silently substitute mock observations.

The example above is the legacy synthetic response. Real API responses use `layers.source: satellite` and `answer: {text, mode: "data_summary", citations, toolsUsed}`. Citations have `{id, tool, lat, lng, field, value, unit, dataset, sceneId, acquiredAt}`; every value comes from an executed data function. The text references IDs such as [S1]. The server formats fixed sentences from measured results, without model calls. `layers.provenance` embeds actual `{field, dataset, sceneId, acquiredAt, processing, ...}` records. Different acquisition dates remain distinct. No-data responses contain an explanation with empty citations.

Recognized questions (case-insensitive, repeated whitespace normalized): `What are the temperature and NDVI here?`, `What is the temperature here?`, `How does this cell compare with nearby cells?`, `Why is this block hotter?`, `Where should we plant trees here?`, and `What if we plant N trees?` (integer 1–1000). Other questions return a supported-summary explanation with empty citations. The frontend exposes the first, third and fifth as explicit choices; it does not present a free-form chat.

`scenario` is normally null. Planting what-if queries return `{status:"unavailable", nTrees:20, deltaTempC:null, reason:"..."}` from simulate_planting until Step 6 defines a method. No cooling number is invented.

## Mock interaction

Opt into **Mock preview** explicitly under Controls & sources. The directional reading card and Three.js patch use bearing from the fixture origin and a nominal 70° horizontal field of view, without terrain/object anchoring or camera calibration. One card shows the sampled cell closest to the current heading among projected cells. Summary requests continue to use the reference pin or actual GPS position, not that directional cell. Green tint intensity represents NDVI on a clamped 0–1 display scale; negative NDVI uses the lowest colour. The heat legend and patch share a range rounded outward from all measured temperatures in the snapshot (currently 41–45 °C for Aliganj). A dataset with no temperatures has no heat range. Null-valued cells have no coloured patch. The centre fixture cell is null and is not placed on a bearing.

The overlay loads same-origin `/data/grid.json` plus `/data/provenance.json`. The default Aliganj preview is explicitly labelled and independent of GPS. My GPS mode returns cells only inside the dataset bounding box; unavailable/denied GPS and out-of-coverage positions show No data. Use my location requests GPS separately from Start camera. The query API reads matching files from S3. The provenance file wraps records in `{source, area, generatedAt, provenance, temperatureStatus, validCells, caveats}`; the API embeds its `provenance` array. Step 5 must publish matching frontend and S3 snapshots together.

