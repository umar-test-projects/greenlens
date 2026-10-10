# GPS Satellite Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Display measured Sentinel-2 NDVI and available Landsat surface temperature at phone GPS locations outside Aliganj, with matching measured summaries and source dates.

**Architecture:** Extend the existing HTTP API with an asynchronous processing route and server-owned cached datasets. A separate raster-processing Lambda container publishes NDVI before temperature. A conditional S3 admission lease permits one uncached job globally; the phone retains an imagery neighborhood and polls that job without starting duplicate work.

**Tech Stack:** React 19, Vite 7, Three.js, existing geotiff/proj4, Python 3.12, rasterio/NumPy/pyproj, boto3, SAM, API Gateway HTTP API, Lambda, private S3, ECR, Amplify manual hosting.

**Spec:** [Approved GPS satellite-processing design](../specs/2026-10-10-gps-satellite-processing-design.md), approved 2026-10-11.

**Status:** The user instructed completion using this plan on 2026-10-11, with a $10 AWS spending ceiling. Native execution selected; implementation, deployment and fresh final review are complete. Both Important review findings were fixed with RED→GREEN regressions, all suites passed, and the corrections were redeployed and verified. Amplify production job 3 is live; delivery evidence and all execution rulings are in docs/deployment.md.

## Global Constraints

- Latest user constraint: stop AWS work if charges exceed $10. Conservatively interpret this as current-month account charges. Before new uncached work, check Cost Explorer and reserve $1 per admitted generation plus a $1 non-job margin; refuse admission at the ceiling or when billing cannot be verified. Keep monthly reservations in the conditional admission record. Cached reads do not reserve a generation. This deliberately limits distinct paid jobs while billing data is delayed.

- Browser imagery: 900 m crop, 9 by 9 display cells, actual GPS marker; processing tile: 2,000 m square, 100 m cells, 20 by 20 cells.
- Snap projected centers to 1,000 m using half-up rounding. UTM geometry covers latitudes [-80, 84] and longitudes [-180, 180]; reject antimeridian-crossing tiles explicitly.
- Preserve numeric-or-null NDVI/tempC, actual acquisition dates, and field-specific provenance. Do not fabricate measurements, air temperatures, canopy percentages, or cooling predictions.
- NDVI: independent STAC band scales/offsets, SCL 4/5/6, valid reflectances, [-1, 1] result, at least 50 percent valid 10 m samples per 100 m cell, four decimal places.
- Temperature: ST_B10 scale 0.00341802, Kelvin offset 149, Celsius offset -273.15; QA_PIXEL bits 0–5 clear; QA_RADSAT exactly zero; at least 50 percent valid samples. Preserve valid zero quality flags.
- Search at most two years, 12 scenes per dataset, scene cloud cover below 20 percent, newest first, at most four candidate attempts per field; no full-scene downloads.
- Worker: 300-second timeout, 2,048 MB memory, 1,024 MB temporary storage, 20-second publication margin. Global lease: 420 seconds. Async maximum age: 60 seconds; function-error retries: zero.
- Observation/no-observation freshness: 24 hours. Failure retry cooldown: 60 seconds. Busy retry: 15 seconds. Ordinary polling: approximately three seconds; automatic waiting ends at eight minutes.
- Account 636993911888; region ap-south-1; existing stack greenlens-api. Current verified Lambda concurrency is 10; do not depend on a reserved-concurrency increase.
- Preserve existing API throttle (one request/second, burst two), exact Amplify CORS origin, legacy Aliganj requests, explicitly synthetic mock mode, seven-day logs, and camera-on-device behavior.
- New processing cache: separate private encrypted S3 bucket, public-access blocking, seven-day lifecycle. Do not replace the archived bucket or delete the failed CloudFront stack.
- Deployment is to https://production.d3piecnpvqjn3g.amplifyapp.com, app d3piecnpvqjn3g, branch production. Never print credentials or signed upload URLs.

## Review Focus

1. Two phones requesting different tiles simultaneously: one is admitted and the other receives a bounded busy response (Task 2).
2. A response arrives after the user switches modes or imagery anchors: discard it without changing current readings (Task 6).
3. Temperature finishes after a user opens an NDVI summary: each summary stays tied to its exact immutable revision (Tasks 4 and 7).
4. Retrying a failed field near the successful field's 24-hour expiry: retain its original freshness deadline, not a new lifetime (Tasks 2 and 3).
5. A scene covers only part of the 2 km tile or crosses a coordinate boundary: skip it or reject unsupported geometry without inventing coverage (Tasks 1 and 3).

## Working directory and file map

Use the current checkout at `C:/Users/abdul/OneDrive/Documents/ChatGPT/env hack`. Only the design is currently tracked; most existing application files are untracked. A new worktree would omit the application. Preserve these files, stage only explicit task paths, and never bulk-stage `.env*`, virtual environments, downloaded raster data, or build output. Start an execution branch named `codex/gps-satellite-processing` if it does not already exist. Do not reset or clean the checkout.

New backend files:

- `backend/src/satellite_geometry.py`: canonical tiles, IDs, projected containment.
- `backend/src/satellite_store.py`: S3 state/result operations and admission leases.
- `backend/src/satellite_api.py`: processing request validation, start/poll/retry, async invocation.
- `backend/tests/test_satellite_geometry.py`, `test_satellite_store.py`, `test_satellite_api.py`: focused offline tests with injected clients/time.

New processing files:

- `pipeline/satellite_rasters.py`: bounded raster reads, field calculations, catalog selection.
- `pipeline/satellite_worker.py`: worker lifecycle, independent field publication, timeout budget.
- `pipeline/requirements-worker.txt`, `Dockerfile.satellite`, `.dockerignore`: focused container build.
- `pipeline/test_satellite_rasters.py`, `test_satellite_worker.py`: scientific and lifecycle tests.

New frontend files:

- `src/satellite.js`: typed fetch/result validation and polling controller.
- `src/useSatelliteMeasurements.js`: React adapter to controller, mode and imagery-anchor lifetime.
- `src/measurement-grid.js`: projected measurement mapping and selected source lookup.
- Corresponding `src/*.test.js`: Node tests with injected fetch, time, and projection fixtures.
- `tests/satellite-preview.html`, `tests/satellite-preview.jsx`: development-only, visibly labeled controlled UI fixture, excluded from production builds.

Modify only relevant consumers: `backend/src/app.py`, `service.py`, `requirements.txt`; `template.yaml`; `src/main.jsx`, `useLocationImagery.js`, `location-imagery.js`, `QueryPanel.jsx`, `query.js`; `vite.config.js`; `.env.example`; existing targeted tests and documentation. New delivery checks: `backend/verify_satellite.py` and `pipeline/verify_satellite_window.py`.

## Shared contracts

Use JSON dictionaries/TypedDict definitions in `satellite_geometry.py`, not a new application framework.

- `Tile`: `{id, epsg, center: {x,y}, bounds: [west,south,east,north], bbox, footprint, cellSizeM:100, rows:20, columns:20}`. Projected bounds use metres; bbox/footprint use WGS84.
- Tile ID: `p1-{epsg}-{integerX}-{integerY}`. Parse strictly and reconstruct canonical geometry instead of accepting arbitrary bounds.
- Job ID: `{tileId}.{uuidHex}`; result/dataset ID: `{tileId}.{uuidHex}.{revision}`, where revision is `ndvi` or `final`. A summary names an exact published revision; polling names the generation.
- `FieldStatus`: `{status: pending|processing|ready|no_data|error, reason, completedAt, expiresAt, retryAfterAt}`. Completed no-data searches have freshness; provider errors have cooldowns.
- Result: `{datasetId, grid, metadata, fieldStatus}`. Grid cells include row, column, centers, footprints, ndvi, tempC. Metadata includes provenance, validCells, generatedAt, expiresAt, and field availability.
- S3 keys: `states/{tileId}.json`, `results/{tileId}/{uuidHex}/{revision}.json`, `admission/global.json`. Put a revision once; state points to the current available revision. Both browser and server keep earlier revision IDs meaningful while fresh.
- State: `{jobId, tile, generation, status, createdAt, leaseExpiresAt, resultId, fieldStatus}` plus S3 ETag outside the JSON body. A new generation can carry successful fields from a previous result.
- Public processing response: `{jobId, datasetId|null, status, retryAfterSeconds, fieldStatus, grid?, metadata?}`. Never include an ETag, internal S3 key, or lease token.

### Task 1: Canonical metric tiles and containment

**Files:** Create `backend/src/satellite_geometry.py`, `backend/tests/test_satellite_geometry.py`; modify `backend/src/requirements.txt` to add a Python-3.12-compatible pinned pyproj wheel.

**Interfaces:** Produce `tile_for_location(lat: float, lng: float) -> Tile`, `tile_from_id(tile_id: str) -> Tile`, `build_cells(tile: Tile) -> list[dict]`, `cell_index(grid: dict, lat: float, lng: float) -> int | None`, and `parse_dataset_id(value: str) -> tuple[str,str,str]`. No rasterio/NumPy import in the query package.

- [x] **Step 1: Write failing geometry tests.** Pin half-up rounding, both hemispheres, 400 cells, footprint boundaries, unsupported latitude/dateline, and malformed IDs. Include `test_display_neighborhood_fits_tile` for all four extremes of the 1 km ownership square.

```python
tile = tile_for_location(12.9767, 77.5929)
self.assertEqual(tile['rows'], 20)
self.assertEqual(tile['columns'], 20)
self.assertEqual(tile['center']['x'] % 1000, 0)
self.assertEqual(len(build_cells(tile)), 400)
self.assertEqual(tile_from_id(tile['id']), tile)
```

- [x] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_satellite_geometry.py -v`. Expected: failure because the module/signatures do not exist.
- [x] **Step 3: Implement the interfaces.** Use pyproj `Transformer(..., always_xy=True)`. Row zero is north, column zero west. Include north/west edges, choose the east/south cell at internal boundaries, and include the outer east/south edge in the last cell. Validate finite values before projection. Reject wrapped geographic bounds. Resolve the pyproj pin against available Linux Python 3.12 wheels before locking it.
- [x] **Step 4: Rerun the focused command.** Expected: all geometry tests pass, including false coverage at rotated bbox corners and 950 m maximum crop extent from tile center.
- [x] **Step 5: Commit only the three task files** with message `feat: add canonical satellite tile geometry`.

### Task 2: Cached generations and one-job admission

**Files:** Create `backend/src/satellite_store.py`, `backend/tests/test_satellite_store.py`.

**Interfaces:** Consume Task 1 types/ID parsers. Produce `SatelliteStore(client, bucket: str)`, with `read_state(tile_id) -> dict|None`, `acquire(owner: str, now: datetime) -> dict|None`, `release(lease: dict) -> bool`, `create_job(tile, generation, now, carry=None) -> dict`, `claim_worker(job_id, now) -> dict|None`, `publish(job_id, revision, result, terminal_status, now) -> bool`, and `read_result(dataset_id, now) -> dict`. State/lease reads include their ETag under a private wrapper, not public response fields. Typed domain errors distinguish busy, stale, missing, and conditional conflicts.

- [x] **Step 1: Write failing fake-S3 tests.** Fake conditional writes enforce IfMatch/IfNoneMatch and expose deterministic interleavings. Include `test_two_distinct_tiles_share_one_slot`, `test_duplicate_worker_claim_is_noop`, `test_crash_claim_expires`, `test_old_generation_cannot_publish_or_release`, `test_result_revisions_are_immutable`, and `test_retry_preserves_success_expiry`.

```python
lease = store.acquire('job-a', now)
self.assertEqual((lease['expiresAt'] - now).total_seconds(), 420)
self.assertIsNone(store.acquire('job-b', now))
self.assertIsNotNone(store.acquire('job-b', now + timedelta(seconds=421)))
self.assertFalse(store.release(lease))
```

- [x] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_satellite_store.py -v`. Expected: new store tests fail.
- [x] **Step 3: Implement the store interfaces.** Read the AWS Python SDK skill's S3/configuration/error-handling references. Reuse clients, bound JSON objects to 1 MB, reject nonfinite output, sign conditional writes, and reread conflicts. Release admission by conditional replacement, not deletion. Pending jobs expire at their lease deadline. Preserve carried fields' original `expiresAt`; result expiry is the earliest completed field expiry. Every published NDVI/final revision has its own immutable dataset ID. Error cooldown is 60 seconds; observation freshness is 86,400 seconds.
- [x] **Step 4: Rerun store and geometry tests.** Expected: all pass, including interrupted state/admission operations recovering after expiry and old revisions remaining queryable until their original expiry.
- [x] **Step 5: Commit the two files** with message `feat: cache satellite jobs with conditional admission`.

### Task 3: Scientific raster processing and asynchronous worker

**Files:** Create `pipeline/satellite_rasters.py`, `satellite_worker.py`, `requirements-worker.txt`, `Dockerfile.satellite`, `.dockerignore`, `test_satellite_rasters.py`, `test_satellite_worker.py`. Modify `pipeline/build_grid.py` only to share its bounded asset-read helper when needed; preserve its archived outputs and CLI.

**Interfaces:** Consume `Tile`, `build_cells`, and Task 2 store. Produce `read_asset(asset: dict, tile: dict, *, paid=False, local=None) -> numpy.ndarray`, `ndvi_cells(red, nir, scl, red_meta, nir_meta) -> list[float|None]`, `temperature_cells(dn, qa, saturation) -> list[float|None]`, `process_field(field: str, tile: dict, deadline: float) -> dict`, and `satellite_worker.handler(event: dict, context) -> dict`. A field result contains values, FieldStatus, and an optional provenance record; it does not mutate cached state itself.

- [x] **Step 1: Write failing scientific tests.** Use tiny local GeoTIFFs, independent reflectance metadata, SCL at 20 m, and known thermal digital numbers. Pin the 50/100 versus 49/100 validity boundary, zero QA_RADSAT survival, cloud/shadow/snow/fill exclusion, and no full-file fallback. Use injected catalog/readers for `test_partial_scene_is_skipped`, `test_four_attempt_limit`, and `test_latest_valid_scene_is_selected_without_mosaic`.

```python
red = np.full((200, 200), 2000)
nir = np.full((200, 200), 5000)
scl = np.full((200, 200), 4)
values = ndvi_cells(red, nir, scl,
    {'scale': .0001, 'offset': -.1}, {'scale': .0001, 'offset': 0})
self.assertEqual(values[0], .6667)
self.assertAlmostEqual(temperature_cells(
    np.full((200, 200), 45000), np.zeros((200, 200)),
    np.zeros((200, 200)))[0], 29.6609, places=4)
```

- [x] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest discover -s pipeline -p test_satellite_rasters.py -v` and the corresponding `test_satellite_worker.py` command. Expected: missing new interfaces cause failures.
- [x] **Step 3: Implement field processing.** Reuse bounded rasterio window/VRT behavior from the archived pipeline, validate catalog assets before reads, verify complete target coverage, and preserve nodata semantics. Use the exact masks, scaling, scene/attempt limits, and deadline from the spec. Build the container from explicit `COPY` paths for worker files and shared backend modules; omit workspace/environment files. Pin Linux Python 3.12 wheels for rasterio/NumPy/pyproj and use the existing boto3 pin if compatible. Fail packaging verification rather than silently changing the runtime.
- [x] **Step 4: Implement `handler`.** Claim the generation before acquiring any raster assets; verify its admission owner. Publish `ndvi` before starting Landsat, then `final`. Honor carried successful fields. Top-level status: any successful field plus retryable error -> partial; both no_data -> no_data; any error with no successful field -> error; otherwise -> ready. Provider errors never become a completed no-observation search. Stop attempts with 20 seconds remaining, publish sanitized reasons, and conditionally release admission. No precise coordinates/provider bodies in logs.
- [x] **Step 5: Run pipeline tests**, including archived `test_processing.py` and `test_raster_read.py`. Expected: pass, with worker tests proving publication order, temperature failure retaining NDVI, both-empty behavior, duplicate events doing zero reads, and hard-timeout recovery via the lease.
- [x] **Step 6: Commit explicit task files** with message `feat: process masked satellite NDVI and temperature`.

### Task 4: Processing API and measured GPS summaries

**Files:** Create `backend/src/satellite_api.py`, `backend/tests/test_satellite_api.py`; modify `backend/src/app.py`, `service.py`, and `backend/tests/test_service.py`.

**Interfaces:** Produce `satellite_api.handle(body: dict, store, lambda_client, now) -> tuple[int,dict,dict]` (status/body/headers). `app.handler` routes `POST /satellite` by API Gateway routeKey/path; events without a path remain legacy queries for existing unit/local callers. Extend `validate_query` to preserve an optional validated `datasetId`. `DataTools` consumes dynamic grids through Task 1 containment while retaining legacy nearest-cell behavior for archived grids.

- [x] **Step 1: Write failing API tests.** Cover start/poll/retry bodies, booleans, NaN, oversized/base64 bodies, malformed IDs, mismatched jobs, and disallowed retry+jobId combination. Pin read-only polling, fresh-cache reuse, invocation rejection cleanup, 429/15-second busy behavior, and sanitized 503s. Add `test_summary_uses_exact_revision_after_temperature_arrives` and partial-field citation tests.

```python
old = store.read_result(ndvi_dataset_id, now)
answer = query_with_dataset(ndvi_dataset_id)
self.assertEqual(old['grid']['cells'][0]['tempC'], None)
self.assertTrue(all(c['field'] == 'ndvi' for c in answer['citations']))
lambda_client.invoke.assert_not_called()  # polling/cache/summary do not start work
```

- [x] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v`. Expected: new route/dataset tests fail and existing archived tests stay meaningful.
- [x] **Step 3: Implement request lifecycle.** Acquire admission before job creation/invocation; invoke the configured worker with `InvocationType='Event'` and only canonical job identity. For pending states return 202, completed results 200, validation 400, busy 429, retryable failures 503. Return `Retry-After` where relevant. Polling does not start replacement work; only retryFailed can retry an errored field during freshness. Fetch query datasets from the exact immutable result ID, validate actual footprint and expiry, and never fall back to Aliganj for a supplied ID.
- [x] **Step 4: Adapt deterministic summaries.** Reuse the existing sentences/citations. A local summary can cite partial NDVI; no thermal comparison or planting candidate is invented when required paired data is missing. Detect all-null field coverage explicitly. Metadata must contain a matching provenance record for every non-null cited field.
- [x] **Step 5: Rerun backend tests.** Expected: all pass, including legacy Aliganj outputs, invalid/missing/expired datasets, independent source dates, and exact citation-to-revision equality.
- [x] **Step 6: Commit explicit backend paths** with message `feat: expose satellite jobs and cached GPS summaries`.

### Task 5: Deployable worker and API resources

**Files:** Modify `template.yaml`, `backend/src/requirements.txt`, `.env.example`, `vite.config.js`, `docs/backend.md`, `docs/api-contract.md`; create `backend/tests/test_satellite_template.py`.

**Interfaces:** Template exports `SatelliteUrl` alongside existing `QueryUrl`. Query environment adds `PROCESSING_BUCKET` and `PROCESSOR_FUNCTION`; worker receives `PROCESSING_BUCKET`. Frontend reads public `VITE_SATELLITE_URL`; local Vite proxies `/satellite` to SAM port 3001.

- [x] **Step 1: Add template assertions** for the extra POST route, unchanged archive IAM keys/CORS/throttle, private cache lifecycle, 300/2048/1024 worker settings, 60-second async age and zero retries, and absence of reserved concurrency. Use a YAML loader that preserves CloudFormation intrinsic values rather than string-count-only assertions.
- [x] **Step 2: Run the template test.** Expected: missing resources/properties fail.
- [x] **Step 3: Add SAM resources and scoped IAM.** Create a cache bucket retained on stack deletion, seven-day lifecycle/logs, worker image metadata, and explicit AWS::Lambda::EventInvokeConfig. Use SAM's image-repository support to package ECR artifacts. Worker has cache read/write and GetObject on the required Landsat prefix; query has cache read/write and InvokeFunction on only this worker. No S3 public endpoint or full wildcard account policy. Keep query runtime Python 3.12, timeout 28 seconds, and memory 512 MB.
- [x] **Step 4: Validate and build:** `.\.sam-venv\Scripts\sam.exe validate --lint --region ap-south-1`, then `sam.exe build --use-container`. Expected: both pass; query pyproj wheel imports in Linux, worker rasterio imports and scientific fixtures pass inside the image. Inspect the built image contents for environment/workspace files. Build is not a deployment.
- [x] **Step 5: Commit task paths** with message `infra: add bounded satellite processing resources`.

### Task 6: Phone processing client and neighborhood lifetime

**Files:** Create `src/satellite.js`, `satellite.test.js`, `useSatelliteMeasurements.js`, `measurement-grid.js`, `measurement-grid.test.js`; modify `src/useLocationImagery.js`, `src/location-imagery.js`, `src/location-imagery.test.js`.

**Interfaces:** Produce `sendSatellite(payload, signal, fetcher=fetch, url='/satellite') -> Promise<response>`, `createSatelliteController({request,onUpdate,now,setTimer,clearTimer}) -> {start(anchor),retry(),stop()}`, `useSatelliteMeasurements(enabled, anchor, url) -> {result,status,fieldStatus,loading,retry}`, `mapMeasurements(displayGrid, measuredGrid) -> grid`, and `measurementSource(metadata, layer) -> provenance|null`. Extend the imagery hook's return with `measurementAnchor` while preserving existing callers.

- [x] **Step 1: Write failing Node tests** with injected fake timers/fetch. Include jitter reusing anchor, movement replacing anchor, busy retry at 15 seconds, normal polling at three seconds, timeout at 480 seconds, manual retryFailed, bad JSON/provider response, partial NDVI arrival, and late responses after stop/mode change. Pin projected containment and no measurements at rotated bbox corners.

```javascript
assert.equal(requestCountAfterMovingWithinCrop, 1);
assert.equal(busyRetryDelayMs, 15000);
assert.equal(normalPollDelayMs, 3000);
assert.equal(updatesAfterStoppedResponse, 0);
assert.equal(mapMeasurements(outsideGrid, measured).cells[0].ndvi, null);
```

- [x] **Step 2: Run** `node --test src/satellite.test.js src/measurement-grid.test.js src/location-imagery.test.js`. Expected: new modules/interfaces fail.
- [x] **Step 3: Implement request validation and controller.** Respect structured errors and Retry-After; API Gateway throttle responses can lack the domain error format. Bounded busy responses can retry a start, but job errors require manual retryFailed. Poll using the original anchor and job ID. Version callbacks so obsolete promises cannot update UI; stop timers and abort browser fetches at eight minutes or mode changes.
- [x] **Step 4: Add the React adapter and anchor export.** Publish the anchor when the imagery hook accepts a pending neighborhood, allowing imagery and measurement work to start together. Retain it with a successfully loaded crop; canceled replacements restore the loaded crop's anchor. Measurement results remain usable only inside their footprints. Use existing proj4 for authoritative frontend projected lookup; keep legacy attachment tests intact.
- [x] **Step 5: Rerun focused Node tests.** Expected: pass, including ownership-boundary movement retaining the same dataset and selected-source lookup never returning the Aliganj date for dynamic measurements.
- [x] **Step 6: Commit explicit source/test paths** with message `feat: load GPS satellite measurements without duplicate jobs`.

### Task 7: Measured map cards, sources, and summaries

**Files:** Modify `src/main.jsx`, `QueryPanel.jsx`, `query.js`, `query.test.js`, `layers.test.js`, `tests/gps-preview.jsx`; create `tests/satellite-preview.html`, `tests/satellite-preview.jsx`; update `README.md`, `docs/data-pipeline.md`.

**Interfaces:** QueryPanel adds `{datasetId=null, measurementStatus=null}` props. In My GPS it submits only when a usable dataset exists, includes that ID, and clears a displayed answer when the result revision changes. Legacy Aliganj/mock behavior is preserved. The controlled development fixture injects labeled measurements/statuses; it is not a public production data source.

- [x] **Step 1: Add failing tests/controlled states** for NDVI-only, completed two-field, clouds/no-data, busy, provider failure, and delayed final revision. Pin query payload preserving datasetId and heat range deriving from GPS measurements rather than archived values.

```javascript
assert.equal(gpsPayload.datasetId, shownDatasetId);
assert.deepEqual(temperatureRange([{tempC:29.66},{tempC:33.1}]), [29,34]);
assert.equal(measurementSource(dynamicMetadata,'green').sceneId, ndviSceneId);
assert.equal(measurementSource(dynamicMetadata,'heat').sceneId, landsatSceneId);
```

- [x] **Step 2: Run** `npm.cmd test`. Expected: new behavior tests fail.
- [x] **Step 3: Connect both view modes.** Use the dynamic grid in 3D and Camera / AR; map it to imagery cells where needed. Use my location opens Vegetation. Surface heat can show its own processing/unavailability message. Dates and source records come from the selected field; RGB imagery date remains separate. Derive heat tint/legend from measured GPS cells. Remove fixed-Aliganj coverage wording from GPS copy.
- [x] **Step 4: Connect summaries and stale-result handling.** Carry datasetId, disable summary actions until a usable dynamic revision exists, reset selection on neighborhood changes, and clear old answers on dataset revision changes. Preserve successful partial data and offer retry only for retryable fields/jobs. Keep exact GPS and camera privacy copy accurate.
- [x] **Step 5: Run `npm.cmd test` and `npm.cmd run build`.** Then inspect the controlled fixture at 390 by 844 and desktop sizes through browser tools. Expected: NDVI appears before temperature, final source dates differ correctly, denied GPS clears readings, and switching modes while a response is pending does not restore stale values. Exercise both 3D and AR displays without claiming physical hardware validation.
- [x] **Step 6: Commit task paths** with message `feat: show GPS satellite layers and matching summaries`.

### Task 8: Live scientific checks and deployment

**Files:** Create `backend/verify_satellite.py`, `pipeline/verify_satellite_window.py`; modify `docs/deployment.md`, `docs/amplify-hosting.md`, and this plan's completion checkboxes. Reuse `backend/verify_deployed.py` and `deployment/verify_frontend.py`.

**Interfaces:** `verify_satellite.py SATELLITE_URL QUERY_URL --origin SITE` starts/polls the public Bengaluru sample, validates result/summary/citation consistency, records dataset/scene IDs, and verifies a cached repeat. `verify_satellite_window.py RESULT_JSON` independently reads bounded official source windows around selected result cells and compares masks/calculations without calling the worker's numerical helpers. Both scripts use a single `main()` entry point and never log credentials or signed URLs.

- [x] **Step 1: Test the verifiers against offline response/source fixtures.** A changed citation, temperature scaling, mask, or scene date must fail. The independent verifier checks at least one selected field cell and one masked/fill fixture; measured equality tolerance is the four-decimal rounding precision. Clearly separate no-observation coverage from verifier/provider errors.
- [x] **Step 2: Run final local checks:** `npm.cmd test`, backend unittest discovery, focused pipeline processing/worker/raster tests, SAM lint, Linux image fixture tests, and Vite build. Expected: all appropriate checks pass. Omit unrelated optional AI super-resolution downloads.
- [x] **Step 3: Refresh deployment context.** Verify AWS account, session, Docker, deployed API outputs and exact CORS. Earlier user authorization permits `aws login` if expired; use the signing-in skill and preserve that authorization without asking again. Package ECR image/SAM artifacts and create a no-execute change set for greenlens-api with the current DataBucket and exact Amplify AllowedOrigin. Inspect resource changes and CloudFormation describe-events; stop and revise any unexpected replacement/deletion.
- [x] **Step 4: Execute the scoped API change set and wait for UPDATE_COMPLETE.** Verify worker image state is Active, cache policy is private, IAM is scoped, and async age/retries match the plan. Do not deploy the frontend on an unsuccessful backend update.
- [x] **Step 5: Run the live satellite verifier at public Bengaluru**, pace API requests under the one-request/second throttle, and save its bounded result under ignored `.aws-sam/`. Verify partial publication when observed, final measurements/availability, exact citations, and cached replay with no new generation. Run the independent raster-window check on its reported source scenes, then the existing seven legacy API/CORS checks. Coverage may be cloudy; if a field is unavailable, inspect another candidate public location within the approved bounded scene search and record the actual limitation. Never label invented or stale values successful.
- [x] **Step 6: Publish the frontend.** Set the public QueryUrl/SatelliteUrl in ignored production build configuration, build, zip the contents of dist with index.html at archive root, and use Amplify create-deployment/upload/start-deployment. Keep upload URLs in memory. Wait for SUCCEED, then run `deployment/verify_frontend.py` to compare published hashes/headers and inspect the live site at phone size.
- [x] **Step 7: Record measured delivery evidence**, dates, scene IDs, available fields, processing duration, cache replay, summary checks, and physical-phone limits in deployment docs. Commit only code/docs/verifier changes with message `test: verify and deliver GPS satellite processing`. Report the live URL and concise phone steps; do not claim phone hardware testing from browser emulation.

## Self-review and execution handoff

Spec coverage: geometry/cache -> Tasks 1–2; scientific masks/selection/publication -> Task 3; route and exact-evidence summaries -> Task 4; deployment resources -> Task 5; polling/cancellation -> Task 6; phone displays and provenance -> Task 7; independent verification and delivery -> Task 8. Every Review Focus condition has a named owning test above. Interfaces consistently distinguish job IDs from immutable dataset revision IDs. Secrets and generated artifacts remain outside commits.

The work is one feature with shared interfaces, not independent projects. **Native** execution in the existing checkout follows the user's instruction to complete the build using this plan. The eight tasks depend directly on each other's geometry, job, and result contracts, and the account's single-job processing limit makes parallel live checks counterproductive. Execution uses the executing-plans skill and includes a fresh whole-feature reviewer after implementation. The spending ceiling takes precedence over deployment and paid verification.


