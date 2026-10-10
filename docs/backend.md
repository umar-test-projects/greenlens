# Step 4: satellite data summaries

The team chose to skip AI after Bedrock rejected requests in both the API and
console playground. The active backend has no Strands dependency, Bedrock call,
model configuration or Bedrock IAM permission. The support request is historical
context only; it is not required to run this demo.

SAM exposes `POST /query`. Lambda reads measured cells and provenance from
private S3 and formats cited sentences using fixed calculations. The frontend
offers explicit choices instead of free-form AI chat. Camera frames stay on the
device; selections and coordinates go to AWS. The `greenlens-api` stack is
deployed in `ap-south-1` at `https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/query`.
The frontend is live at `https://production.d3piecnpvqjn3g.amplifyapp.com` through
Amplify; API CORS allows that exact origin. Direct CloudFront provisioning remains
blocked by AWS account verification. See [deployment status](deployment.md) and
the [Amplify runbook](amplify-hosting.md).

Verified locally: eight backend tests, twelve frontend tests, Vite production
build, SAM lint and Docker container build pass. The rebuilt Lambda returned
HTTP 200 with 100 S3-backed cells and two citations for local conditions.
Its first local request took 43 seconds on this Windows checkout; a warm survey
request through Vite took 1.4 seconds. Browser checks passed for all three
summaries, source expansion and disabling summaries in Mock preview. On October
10, 2026, all 22 current frontend tests and eight backend tests passed. Seven
deployed API checks passed, including citation/grid agreement, allowed and
disallowed CORS origins, no-data and HTTP 400 handling. The first observed
deployed summary took 4.34 seconds; warm comparison and planting requests took
0.20 and 0.19 seconds from this computer. These are individual observations,
not a latency benchmark. A production browser preview confirmed all three
summaries and source expansion against AWS. The public Amplify site also passed
all three browser summaries and source expansion; its 21 frontend files match
the local production build exactly and seven live API checks passed with the
Amplify origin. Phone hardware testing remains outstanding.

## Summaries

- Local temperature and vegetation: nearest grid cell, NDVI, surface temperature
  and acquisition dates.
- Nearby comparison: local cell and coolest measured cell within 500 m. These
  observations do not establish why a street is hotter.
- Planting survey: lowest NDVI among the warmer half of paired cells within
  500 m. Check space, ownership, utilities and existing trees on site.

The API also recognizes `What if we plant N trees?` for 1–1000 trees, returning
`status: unavailable` and `deltaTempC: null`. No cooling effect is invented.
Unknown questions return a supported-summary explanation with no citations.
See the API contract for exact questions; this is not natural-language
understanding. Missing values stay null; out-of-area requests return `no_data`.
S3 failure returns a sanitized HTTP 503.

## Setup and tests (PowerShell, repository root)

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/src/requirements.txt
.\.venv\Scripts\python.exe -m venv .sam-venv
.\.sam-venv\Scripts\python.exe -m pip install aws-sam-cli==1.167.0
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
npm.cmd test
npm.cmd run build
```

Use the existing AWS CLI login; if expired, refresh it without putting
credentials into files or chat:

```powershell
& 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' login --region ap-south-1
$env:SAM_CLI_TELEMETRY='0'
.\.sam-venv\Scripts\sam.exe validate --lint --region ap-south-1
.\.venv\Scripts\python.exe backend/smoke.py
.\.venv\Scripts\python.exe backend/smoke.py --question 'Where should we plant trees here?'
```

The smoke test reads real S3, which can incur small read charges. No model
tokens are billed. Expect HTTP 200, `answer.mode: data_summary`, measured sources
and dates. Unit tests use local fixtures and make no AWS requests.

## SAM local API

Start Docker Desktop in Linux-container mode. The first build downloads an
image; add `--skip-pull-image` on later builds when it is already cached.

```powershell
.\.sam-venv\Scripts\sam.exe build --use-container
.\.venv\Scripts\python.exe backend/prepare_local.py
.\.sam-venv\Scripts\sam.exe local start-api --template .aws-sam/build/local-template.yaml --port 3001 --region ap-south-1 --profile default --skip-pull-image --warm-containers EAGER
```

Windows bind-mounted SDK imports are slow on this checkout. The generated
local-only template allows 90 seconds for initialization; deployment remains
28 seconds. In another terminal, warm the container before phone testing:

```powershell
$body = @{ lat = 26.8879107; lng = 80.9494493; heading = 0; question = 'What are the temperature and NDVI here?' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:3001/query -Method Post -ContentType application/json -Body $body -TimeoutSec 110
npm.cmd run dev
```

Keep SAM running to reuse the warm container. Vite proxies `/query` to port
3001, including requests through the HTTPS phone tunnel. The frontend aborts
after 30 seconds. SAM passes temporary credentials to Docker; deployed Lambda
uses its execution role. Never deploy `local-template.yaml`; deploy the normal
28-second template.

## Browser / phone test

1. The labelled **Aliganj preview** loads first. Under **Explore this area**, tap
   **Local conditions**, **Compare nearby** and **Planting areas**. Expect
   expandable measured sources. Summary results use the reference pin/GPS;
   the separate view card describes the directional grid cell ahead.
2. Compare the citations with `public/data/grid.json` and provenance; historical
   surface temperature must not be described as air temperature.
3. Open **Controls & sources** and select Mock preview: summary buttons are disabled. With My GPS outside
   coverage, expect No data and no measurements for that location.
4. Change location or summary during a request: stale answers must not appear.
5. Stop SAM and retry: show a data-service error while retaining overlays.

Repeat through HTTPS on Android Chrome and iOS Safari. Real-phone hardware
verification must be performed by the team. Temporary tunnels are for testing;
final hosting is S3 + CloudFront.

## Deployment and costs

The template grants S3 GetObject only for `data/grid.json` and
`data/provenance.json`, with seven-day logs and API throttling at one request/s,
burst two. It creates no database or VPC. Deployment can incur S3, Lambda,
API Gateway, CloudWatch and CloudFront charges. No Bedrock access is needed.

Step 5 must set `AllowedOrigin` to the CloudFront origin and build with
`VITE_QUERY_URL` set to the deployed QueryUrl. Publish matching frontend and S3
snapshots. Throttling is best-effort, not a billing cap. The demo API has no
user authentication; remove hackathon resources when no longer needed.
# GPS processing worker

The processing extension adds a private seven-day S3 cache, a raster-processing Lambda container, and `POST /satellite` to the existing HTTP API. The query Lambda remains Python 3.12 with a 28-second timeout. The worker runs at 2,048 MB with a 300-second timeout, publishes NDVI before Landsat temperature, and uses conditional S3 state changes to avoid duplicate reads. Global admission permits one new job at a time without reserved concurrency.

Before new admission, Cost Explorer verifies current-month account charges. Each generation consumes a conservative $1 reservation plus a $1 allowance for other deployment costs; eight generations are the maximum when reported charges are near zero. Reaching the guard blocks new work for the month. This protects processing spend while billing updates are delayed; it does not control unrelated account services. The query role has Cost Explorer read permission, and source Landsat access belongs only to the worker. Cache roles need ListBucket on the exact private cache bucket to distinguish missing keys from permission errors.
