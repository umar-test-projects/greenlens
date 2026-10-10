# GPS satellite processing: NDVI and surface temperature

Date: 2026-10-10
Status: User approved this written design on 2026-10-11. Implementation awaits review of the implementation plan and selection of its execution method.

## Purpose and agreed scope

GreenLens currently shows measured NDVI and surface temperature in the fixed Aliganj preview. My GPS can load satellite RGB imagery elsewhere, but its measurement cards and AWS summaries have no data outside that historical grid. The user requested satellite processing, first chose NDVI, then added temperature and approved a background AWS processing worker with caching.

The result must let a phone user choose **Use my location**, see actual satellite measurements for the available surrounding area, inspect cells, and request summaries supported by those same measurements. Both NDVI and surface temperature are required. Cloudy or missing observations remain unavailable. These are dated satellite observations; temperature measures the ground surface and NDVI is an index.

The existing Aliganj preview remains an explicitly selected historical reference. Camera frames remain on the phone. GPS requests already disclose coordinates to AWS for summaries; processing will also send the neighborhood request to AWS and search bounds to Earth Search.

## Approach and boundaries

Use the existing API Gateway and lightweight Python query Lambda to accept processing requests, return cached results, and serve summaries. Add a separate Lambda container image with rasterio, NumPy, pyproj, and boto3 for bounded raster processing. Store status and results under a dedicated private S3 processing prefix.

Alternatives considered:

- Browser NDVI plus AWS temperature: uses the current GeoTIFF browser dependency, but introduces separate processing and quality-handling paths and makes measured summaries harder to keep consistent.
- Process both fields inside the current query Lambda: simpler invocation flow, but raster downloads and processing must fit its 28-second request lifetime.
- Selected: asynchronous worker for both fields, with independently published field results. The query Lambda keeps requests short and the phone can display NDVI while temperature is still running.

This work includes processing, cache/status API, GPS measurement display, measured summaries, source labels, tests, and deployment to the existing Amplify site. It does not add a predictive cooling model, AI-generated measurements, custom domains, or account-verification remediation.

## Components and responsibilities

1. **Tile geometry helper:** validates coordinates, assigns a stable projected tile, builds metric cells and geographic footprints. Shared by request handling and processing; it has no network or storage responsibilities.
2. **Processing store and admission helper:** reads and conditionally writes S3 job state, cached results, and a global admission lease. It performs no raster calculations.
3. **Request handler:** exposes the processing route, invokes admitted work asynchronously, and returns typed status or data. It accepts coordinates, never caller-supplied asset URLs or S3 keys.
4. **Raster worker:** discovers scenes, reads bounded raster windows, applies published scaling and masks, aggregates cells, and publishes provenance and field availability.
5. **GPS data hook:** starts a request when a new imagery neighborhood is needed, polls active processing, retains data while moving inside that neighborhood, and cancels obsolete browser requests.
6. **Existing map and summary consumers:** read the processed grid and field-specific provenance. Server-side summaries use server-owned cached data.

Existing functions in `pipeline/build_grid.py` establish the scientific method. Extract only the geometry and raster operations needed for reuse; keep the archived pipeline reproducible. The container build must use a focused worker context rather than copying the workspace, virtual environments, raster downloads, or local environment files.

## Geometry and cache identity

The browser keeps the existing 900 m GPS-centered RGB crop and 9 by 9 display grid. Actual GPS coordinates continue to position the marker.

The worker processes a **2,000 m square with 100 m cells** (20 by 20 cells). Choose a WGS84 UTM projection using the request longitude and hemisphere. Snap its projected center to the nearest 1,000 m on each axis with an explicitly tested half-up rule. Its key contains the processing version, EPSG code, and integer projected center. The 2 km extent covers the full 900 m imagery neighborhood around any anchor within that tile's 1 km ownership square, including its edges.

The frontend keeps the dataset ID selected for its imagery anchor while GPS moves within the loaded imagery footprint, even if the marker crosses the cache tile's ownership boundary. A new imagery anchor selects a new processing tile. A cached tile may also serve another nearby user.

Every measurement cell has a projected footprint and WGS84 center. Lookup transforms the point into the tile projection and selects the containing cell using a documented half-open boundary convention, with the outermost east/south edges included. Do not select arbitrary nearest cells outside coverage or use a geographic bounding box alone at rotated corners. Display-cell centers sample their containing measurement cell; exported measurement coordinates remain available for citations. A 100 m cell average does not resolve an individual tree or building.

Support coordinates from 80 degrees south through 84 degrees north and longitudes from -180 through 180. Reject booleans, nonfinite numbers, and invalid coordinates. If a tile footprint crosses the antimeridian, return an explicit unsupported-area explanation rather than making a near-global bounding-box search. Other unsupported coverage must not substitute Aliganj or mock data.

Completed observations and completed missing-field searches are fresh for **24 hours** after completion, so cloud cover does not trigger repeated paid searches. Network/provider failures use a **60-second retry cooldown**, not the daily no-observation cache. A partial generation stays readable for 24 hours but an explicit retry can attempt its failed field after the cooldown. An expired result triggers a new generation; it is not silently presented as fresh.

## Scene selection and processing

Search Earth Search v1 separately for `sentinel-2-l2a` and `landsat-c2-l2`, covering the tile and looking back at most two years through the request time. Request at most 12 scenes per dataset, sorted newest first with scene cloud cover below 20 percent. Attempt at most four suitable scenes per field within the worker time budget. Require the selected assets to cover the complete target square after reprojection.

Scene-level cloud cover is a search filter; per-pixel masks determine usable measurements. Select the newest attempted scene with at least one valid aggregated cell. Keep the selected scene's cloud-masked cells null; do not mosaic cells from different dates under one provenance record. If none qualifies, that field has `no_data` with an explanation.

Only consume recognized Sentinel asset hosts and Landsat `usgs-landsat/collection02/level-2/standard/oli-tirs/` S3 assets discovered by the server. Require Landsat 8 or 9 surface-temperature products and all required quality assets. Never follow an arbitrary user URL or send AWS credentials to the browser.

### NDVI

- Read Sentinel red, near-infrared, and scene-classification assets using their own georeferencing and a 10 m target grid. Resample with nearest neighbor for reproducibility and categorical masks.
- Apply each reflectance band's own STAC scale and offset; missing or invalid scale metadata makes the scene unusable.
- Accept SCL classes 4, 5, and 6; exclude fill, clouds, shadows, snow, and invalid pixels.
- Require positive raw red/NIR values, nonnegative scaled reflectances, and a positive denominator.
- Calculate `(NIR - red) / (NIR + red)`. Values outside [-1, 1] or nonfinite values are invalid.
- A 100 m cell requires at least 50 percent valid 10 m samples. Average valid samples and round to four decimal places; otherwise export `null`.

### Surface temperature

- Read the Landsat Collection 2 Level-2 ST_B10 product (`lwir11`) and `qa_pixel`/`qa_radsat` assets with authenticated bounded Requester Pays reads.
- Convert valid digital numbers with `DN * 0.00341802 + 149 - 273.15` to degrees Celsius.
- Exclude DN fill/nonpositive values, QA_PIXEL bits 0 through 5, and nonzero QA_RADSAT. A QA_RADSAT value of zero must remain valid during reprojection; use a distinct destination nodata value.
- Reuse the archived pipeline's nearest-neighbor 10 m working grid and the same 50 percent valid-sample aggregation. Repeated samples do not increase the native thermal resolution; metadata and UI retain the approximately 100 m thermal-resolution caveat.
- Missing surface-temperature/emissivity coverage remains null. Do not substitute brightness temperature or infer temperature from RGB or NDVI.

Publish NDVI as soon as its processing attempt completes, before beginning the temperature attempt. A failed field does not discard a successful field. Each field has its own scene, acquisition time, processing description, valid-cell count, and availability reason. RGB imagery can come from a different acquisition; label its date separately and never imply it is the measurement source without a matching scene ID.

The worker has a **300-second timeout**, initially **2,048 MB memory** and **1,024 MB ephemeral storage**. Network calls have bounded timeouts and retries; check remaining invocation time between candidate scenes and fields. Reserve at least 20 seconds to publish final state. Raster operations use windowed reads, not full-scene downloads. A stage that cannot complete inside the budget yields a retryable error for that field.

## Job lifecycle, duplicate prevention, and account limits

The account's current Lambda concurrency limit in Mumbai is **10**, verified on 2026-10-10. The design does not rely on reserving concurrency that would require a higher account quota.

Admit at most **one uncached processing job globally** through a conditional S3 lease. Existing jobs and ready-cache reads do not acquire another slot. A request for a different uncached tile while the slot is occupied receives `429 PROCESSING_BUSY` and a 15-second retry interval. The UI waits and explains that processing capacity is busy.

The global lease has a random generation ID and **420-second expiry**. Configure asynchronous Lambda events with maximum age **60 seconds** and zero function-error retries. The admitted queue lifetime plus the 300-second worker timeout fits within the lease. Duplicate delivery is still possible, so worker startup conditionally changes its matching job generation from `queued` to `processing`; duplicates that cannot claim the transition exit before downloading assets.

Use S3 `If-None-Match: *` to create missing state and ETag-based `If-Match` to replace it. A conditional conflict rereads the winning state. Acquire the admission lease before committing and invoking a new job. If the job claim loses a race, release the lease conditionally. If invocation is rejected, conditionally record an error and release admission. If an API or worker crashes between steps, lease expiry allows recovery; clients do not poll forever.

Lifecycle: `queued -> processing -> ready | partial | no_data | error`. Pending states may already include NDVI data. `partial` means at least one field succeeded and the other failed due to a retryable provider/processing error; `ready` can include a field with a completed `no_data` search. Both fields without observations produce `no_data`. Read-only polling never automatically launches a second generation.

Results are immutable per generation. Publish a complete JSON result before conditionally pointing the matching state at it. An old worker must not overwrite or release a newer generation. Mark admission released with a conditional write rather than deleting a lock that another request could have replaced.

Once a lease expires, a polling request returns an expired-job error with a retry action. Retrying creates a new admitted generation subject to the cooldown. If the earlier generation published usable partial measurements, preserve them as explicitly dated partial results while attempting the failed field again.

## API contract

Add **POST `/satellite`** on the existing HTTP API, with the same exact Amplify CORS origin and existing request throttling. Inputs are either:

- Start or fetch a fresh tile: `{lat, lng}`.
- Poll an admitted job: `{lat, lng, jobId}`.
- Explicitly retry a failed field/job after its cooldown: `{lat, lng, retryFailed: true}`. This does not refresh fields with completed observations or completed no-observation searches inside their 24-hour freshness window. The worker carries their grid and provenance forward into the new generation and retries only fields with retryable errors.

Validate body size and coordinate types, derive the tile server-side, and validate the job ID format and its relationship to that tile. `retryFailed` must be a boolean and cannot be combined with `jobId`. Job IDs identify a tile and generation; they do not grant access to arbitrary S3 keys. A polling job ID is required to avoid repeated failed requests starting work without a user retry. Ordinary start/fetch requests reuse fresh partial results or return the cached failure/cooldown; only an explicit retry starts a replacement for a failed generation.

Responses include `jobId`, `datasetId`, `status`, `retryAfterSeconds`, `fieldStatus`, and, when available, `grid` and `metadata`. The grid preserves the existing numeric-or-null `ndvi`/`tempC` fields and adds projection, center, footprints, and cell rows/columns. Metadata preserves the existing provenance structure and adds generation/cache timestamps and availability reasons.

- HTTP 202: `queued` or `processing`, including available partial field data.
- HTTP 200: fresh `ready`, `partial`, or `no_data` result.
- HTTP 400: malformed request or unsupported geometry, with a clear code.
- HTTP 429: admission busy or API throttling; bounded retry without duplicate work.
- HTTP 503: retryable service failure or expired job, with a sanitized error.

Keep **POST `/query`** backward compatible. Requests without `datasetId` retain the existing archived behavior. GPS summaries pass the current processed `datasetId`; the server loads only that generation's cached result, checks projected coverage, and uses its provenance with existing deterministic summary functions. A missing, expired, or invalid dataset returns a typed error or no-coverage response and never silently switches to the archived grid.

Partial data can support local summaries; comparison or planting-survey results that need missing fields must explicitly state insufficient measured evidence. Every citation's value, coordinates, scene, and date must match the cached generation. No client-supplied measurement array becomes summary evidence.

## Phone behavior

- **Use my location** starts RGB loading and measurement processing for the same GPS anchor. Vegetation opens first so the earlier NDVI stage is visible; the user can switch to Surface heat while it processes.
- Keep the map usable as measurements load. Show concise stage text, field-specific availability, a measured acquisition date, and retry controls for failed requests.
- Apply the processed grid in both 3D survey and Camera / AR modes. Use the dynamic grid for heat range, card readings, tint, source records, and summary dataset ID.
- Display cells map to their containing measurement cells. Clear a stale selected display cell when its neighborhood changes.
- GPS jitter inside a loaded or pending imagery footprint does not start another processing request. Poll approximately every three seconds; honor busy/retry responses with at least 15 seconds between retries and stop automatic waiting after eight minutes with a manual retry action.
- Cancel obsolete browser requests on mode/anchor changes and ignore responses from old generations. Leaving the screen does not cancel admitted AWS work; its result can populate the cache.
- During replacement, older measurements are usable only where their actual footprint covers the requested point, with their own dates. Outside that footprint the reading shows loading or no data.
- Clearing location or denying permission removes GPS readings. Mock mode remains explicitly synthetic and makes no real processing request.
- Replace the current statements that all GPS measurements are limited to Aliganj. Explain each observation's date and cloud/coverage limits. RGB enhancement remains display-only.

## Infrastructure and data handling

Extend the existing SAM stack with the worker image, its log group and asynchronous configuration, API route, and scoped permissions. Use an ECR repository for the worker image. The query package includes pyproj for authoritative tile geometry, while rasterio and NumPy remain in the worker container. Keep the processing cache in a separate private, encrypted S3 bucket with public-access blocking and seven-day lifecycle expiry, so the archived data bucket's configuration does not need replacement. Both roles can access only the required processing objects; Landsat source reads belong only to the worker role, and the query role invokes only this worker.

Keep seven-day log retention. Log bounded operational status and error categories; omit precise GPS coordinates, questions, credentials, signed URLs, and raw provider responses. Cached tile centers are spatially quantized; camera media is never uploaded.

This remains a public demo with the current API throttling, one-job admission limit, bounded work, and daily cache. CORS is a browser policy, not authentication. Lambda compute, ECR storage, S3 cache operations, and Landsat Requester Pays reads incur charges. A scene selection attempt never requests a full raster file.

## Verification and delivery criteria

Before deployment, verify:

1. Scientific fixtures: independent red/NIR offsets, zero and invalid reflectance, cloudy SCL classes, differing raster resolutions, exact 50 percent aggregation boundary, known Landsat Celsius conversion, fill/cloud/saturation masks, and valid zero QA_RADSAT.
2. Geometry: projected cell containment, rotated footprint corners, tile boundaries, both hemispheres, movement within the 900 m crop, no false coverage, and unsupported antimeridian tiles.
3. State: concurrent claims, duplicate worker events, admission busy, invocation failure, expired leases, partial results, cache expiry, and old generations failing to overwrite new ones.
4. API and citations: malformed input rejection, polling without side effects, dataset ownership/coverage, partial-field summaries, exact citation-to-result equality, and regression checks for existing Aliganj and mock behavior.
5. Frontend: loading, NDVI before temperature, acquisition dates, dynamic heat range, retries, mode changes, stale-response cancellation, 3D/AR consistency, and no repeated work from GPS jitter.
6. An independent bounded raster check at the public Bengaluru landmark already used by `tests/gps-preview.jsx` (12.9767, 77.5929), comparing selected-cell values and masks with direct official-source window reads. No private phone location is needed for this check.

Build and validate the SAM resources and worker image. Review the resulting CloudFormation change set before execution within the approved deployment scope. Deploy the API/worker first, verify processing plus cached replay and measured summaries, then rebuild and deploy the frontend to `https://production.d3piecnpvqjn3g.amplifyapp.com/`. Verify static assets, CORS, and a phone-sized browser flow. Physical-phone GPS/camera permission behavior can only be confirmed on the user's device.

The feature is complete when a location outside Aliganj produces measured NDVI and available Landsat surface temperature with matching source dates, the map and summaries agree, and cloudy/unavailable observations remain explicitly unavailable. The existing failed direct-CloudFront hosting stack is outside this change.

## Evidence and references

- Repository baseline: `src/location-imagery.js`, `src/useLocationImagery.js`, `src/main.jsx`, `src/QueryPanel.jsx`, `pipeline/build_grid.py`, `backend/src/app.py`, `backend/src/service.py`, and `template.yaml`.
- AWS account access checked on 2026-10-10. A Requester Pays HEAD request succeeded for Bengaluru Landsat scene `LC08_L2SP_144051_20260908_02_T1`, acquired 2026-09-08. This verifies source access, not cloud-free ground coverage or calculated values.
- [Earth Search](https://github.com/Element84/earth-search/blob/main/README.md): Sentinel and Landsat catalogs.
- [USGS Landsat surface temperature](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature): temperature scaling and missing-product coverage.
- [USGS Landsat quality bands](https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands): pixel and saturation flags.
- [AWS Landsat dataset registry](https://registry.opendata.aws/usgs-landsat/): source bucket and Requester Pays.
- [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html): create/replace preconditions.
- [Lambda asynchronous configuration](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-configuring.html): event age and retry settings.
- [Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html): packaging and runtime limits.

## Design review

Self-review checks completed: no undecided placeholders; scoped to GPS measurements and their consumers; distinct source dates; consistent 900 m display and 2 km cache geometry; independent field availability; bounded work under the account's observed concurrency quota; explicit crash/timeout and duplicate recovery; compatible legacy query behavior. The user approved this written design on 2026-10-11. The implementation plan must be reviewed and an execution method selected before implementation begins.
