# Step 3 — Sector New E, Aliganj

## GPS satellite extension

The runtime worker reads a bounded 2 km UTM tile at 10 m, aggregates 100 m cells, and publishes an immutable NDVI revision before a final temperature revision. NDVI uses Sentinel-2 reflectance scales/offsets and SCL classes 4/5/6. Landsat surface temperature uses ST_B10 × 0.00341802 + 149 − 273.15, clear QA_PIXEL bits 0–5, and zero QA_RADSAT. Each cell requires at least 50 percent valid samples. Search is limited to two years, 12 scenes, and four candidate attempts per field; incomplete scenes are skipped. Dates remain specific to each successful source. No-data searches are distinct from retryable provider errors. Observation cache freshness is 24 hours, with seven-day private-bucket cleanup.

The user's map pin resolves to **26.8879107, 80.9494493**. `data/area.json` defines a 1,000 × 1,000 m square in WGS84 / UTM zone 44N (`EPSG:32644`), with 100 × 100 m cells. The exported bounding box encloses that projected square. Cell centres are transformed back to WGS84 degrees.

## Current result

- Sentinel-2 scene: `S2B_44RMQ_20250407_0_L2A`, acquired **2025-04-07T05:21:31.703Z**. Red, NIR and SCL read anonymously from the actual `sentinel-cogs` AWS S3 bucket using HTTP range reads.
- Landsat: `LC09_L2SP_144041_20250406_02_T1`, acquired **2025-04-06**. Bounded thermal and quality-band reads used AWS Requester Pays. All 100 cells have valid NDVI and surface temperature.
- `public/data/grid.json` uses the agreed schema. `public/data/provenance.json` contains scene, date, asset URLs, processing, caveats and valid-cell counts. Both were uploaded to `s3://greenlens-data-636993911888-ap-south-1/data/` in Mumbai. Downloaded copies matched local SHA256 hashes. All four public-access blocks are enabled; bucket encryption is AES256. The frontend currently serves the matching checked-in snapshot.
- Catalog selection: Earth Search v1, bounding box around the pin, Sentinel search 2025-04-01 to 2025-06-15, first 30 results sorted locally by scene cloud cover. This is a deliberately archived demo snapshot, not a claim to the latest imagery. Source STAC records are saved in `data/*-item.json`; builds reuse them without silently selecting another date.

## Reproduce on Windows

Install Python 3.12+ if needed. In PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s pipeline -v
.\.venv\Scripts\python.exe pipeline/build_grid.py
npm.cmd test
npm.cmd run build
```

Do not recreate `.venv` if it already exists. A local virtual environment was created during this task using the bundled Python runtime. No activation script is necessary, so PowerShell's script policy does not affect these Python commands.

The build defaults to anonymous Sentinel reads only. It creates no AWS resources. Runtime dependencies are isolated from the mobile app; the app only downloads small JSON files.

## Method and missing data

Read nearest-neighbour 10 m samples in the projected 1 km square. Convert each Sentinel reflectance band using its own STAC `raster:bands` scale and offset. Compute per-pixel NDVI; reject nodata, negative reflectances, zero denominators and values outside [-1,1]. Keep SCL classes 4,5,6 only (vegetation, bare/not vegetated, water). All other classifications including cloud/shadow/snow/uncertain pixels are excluded. Compute each 100 m mean only if at least half of the 10 m samples are valid. Otherwise return null. This conservative mask may omit valid pixels; it must never fill them with mock values.

For Landsat, ST_B10 DN × 0.00341802 + 149 − 273.15 gives Celsius. Exclude DN=0, QA_PIXEL bits 0–5 (fill, dilated cloud, cirrus, cloud, shadow, snow), and any QA_RADSAT flag. Read native 30 m rasters onto the processing grid with nearest-neighbour, then aggregate to 100 m. Thermal native resolution is approximately 100 m; this does not create finer thermal information. Cloud-adjacent temperature artifacts and emissivity uncertainty can persist. It is surface temperature, not air temperature.

If enabled, NDVI and temperature retain their different acquisition dates. A one-day pairing supports an illustrative historical comparison, not a causal estimate of tree cooling.

## Temperature access options

1. Download official ST_B10, QA_PIXEL and QA_RADSAT rasters from USGS EarthExplorer using your own account; place them in a local directory, retaining original names:

```powershell
.\.venv\Scripts\python.exe pipeline/build_grid.py --landsat-dir 'C:\path\to\official-files'
```

2. With an existing AWS CLI login, explicitly enable Requester Pays. **This can charge S3 requests and data transfer to your AWS account.** This path was used for the current snapshot. The wrapper passes temporary CLI credentials to the raster process in memory; it never writes or prints them.

```powershell
.\.venv\Scripts\python.exe pipeline/build_grid_aws.py --profile default --requester-pays
```

If access fails, the command fails rather than generating substituted temperatures. The paid path has been exercised with the real thermal rasters. A regression test ensures reprojection preserves valid zero QA flags and marks pixels outside coverage as missing. Source nodata is retained; bands without nodata use 65535 as the destination sentinel.

## S3 upload

Upload just the grid and metadata to the existing private bucket; no public ACL is needed. The later Lambda reads them with its IAM role; CloudFront hosting is Step 5. S3 storage/PUT/GET and transfer may incur charges. To repeat the completed upload (use the full AWS CLI executable path if `aws` is not on PATH):

```powershell
aws s3 cp public/data/grid.json s3://greenlens-data-636993911888-ap-south-1/data/grid.json --region ap-south-1 --content-type application/json
aws s3 cp public/data/provenance.json s3://greenlens-data-636993911888-ap-south-1/data/provenance.json --region ap-south-1 --content-type application/json
aws s3api head-object --bucket greenlens-data-636993911888-ap-south-1 --key data/grid.json --region ap-south-1
```

Do not pass a public bucket URL to the frontend yet; it currently loads same-origin files. This avoids adding CORS or public-bucket access for the prototype.

## Phone acceptance test

Refresh the working HTTPS link. Select **Aliganj snapshot · fixed reference**. Green / NDVI is selected automatically; real satellite cards, source date and historical warning must appear. This mode uses the map pin independently of your current GPS, so it is explicitly a preview. Rotate or drag to change bearings.

Switch to Heat: surface-temperature cards and the **2025-04-06** date appear. NDVI uses **2025-04-07**. Switch to Mock preview: synthetic labels return. Switch to My GPS: real cells appear only inside the exported bounding box; outside, denied GPS, or missing dataset produces no data. Disable network and reload to check unavailable-data behavior. No real-phone validation of Step 3 has yet been reported.

## Primary sources

- [AWS Sentinel-2 COG registry](https://registry.opendata.aws/sentinel-2-l2a-cogs/)
- [Earth Search Sentinel scale/offset guidance](https://github.com/Element84/earth-search/blob/main/docs/collections/sentinel-2-l2a.md#gainoffset-in-items-after-jan-25-2022)
- [AWS USGS Landsat registry and Requester Pays](https://registry.opendata.aws/usgs-landsat/)
- [USGS Level-2 products and temperature scaling](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products)

STAC source records include asset definitions and QA bit descriptions for the exact selected scenes.
