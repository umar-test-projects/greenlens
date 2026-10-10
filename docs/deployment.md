# Step 5: AWS deployment

## Website polish and security review — 2026-10-11

Amplify production job 6 succeeded with all 20 frontend files verified by SHA256. The update improves mobile text/touch targets, keeps summaries above expandable source notes, labels the reference area and historical map date, and supports keyboard dismissal/focus restoration. CSP enforcement and immediate HTML cache revalidation were verified on the published site. Tests: 43 frontend and 34 backend passed. Required weather, catalog, S3 range reads and GeoTIFF worker decoding passed under the policy in a browser probe. No new satellite processing job or backend deployment was performed. Security evidence and remaining findings are in [the review](security-review-2026-10-11.md).

## Current air-temperature delivery — 2026-10-11

The main temperature card and tab now show current 2 m air-temperature estimates from Open-Meteo. The card includes the provider link, weather timestamp and area label. GPS coordinates are rounded to two decimal places before the browser request; the Aliganj preview uses its public reference area. Weather refreshes every 15 minutes, requests time out after 15 seconds, and readings expire after one hour from the provider timestamp. Missing, malformed, wrong-unit, expired or failed responses show no air-temperature value. Weather does not fall back to Landsat values. Historical satellite surface heat remains explicitly labelled in the map legend and summaries, and vegetation is unchanged.

Frontend source commits: `84173be` and `8325771`. All **41** frontend tests passed, including eight weather validation/lifecycle tests. Production build, controlled phone/desktop states and AR display checks passed. The synthetic weather preview is excluded from production. Amplify production job **5** succeeded; all **20** published files matched the final build, and HTTPS redirect, headers and missing-file 404 checks passed. A live browser check showed the public Aliganj reference area's air estimate of **22.6 °C** for **2026-10-11 02:30 IST**, with attribution; this is not the user's GPS location or a phone sensor reading. Initial reference loading now displays Loading rather than Unavailable.

No backend infrastructure update or additional satellite processing job was needed. Before hosting publication, Cost Explorer reported estimated current-month charges of **a small estimated amount**, excluding credits/refunds; billing is delayed. The existing processing budget guard remains enabled. The Open-Meteo endpoint is free for the non-commercial hackathon demo, with no API key or subscription configured. [Weather API documentation](https://open-meteo.com/en/docs), [usage terms](https://open-meteo.com/en/terms).

## GPS satellite delivery — 2026-10-11

The `greenlens-api` update completed without resource replacement. `/satellite` invokes `greenlens-api-SatelliteWorker-nquBDblJbwbZ`, with a 300-second timeout, 2,048 MB memory, 1,024 MB temporary storage, 60-second async event age and zero function retries. Its cache bucket is `greenlens-api-processingbucket-le3rweyoxfkm`, encrypted with all public access blocked and seven-day cleanup. The exact Amplify CORS origin and the legacy API throttle remain intact.

The public Bengaluru landmark test completed in 44.28 seconds including cold start, polling and summaries. Both immutable revisions were observed, NDVI before temperature. Dataset: `p1-32643-781000-1436000.622b3c7345e34e34a1ec8ac4d6dc162a.final`. It contains 239 valid NDVI cells and 99 valid temperature cells; masked cells remain null. The landmark's exact cell had no valid observation. Local, comparison and planting summaries at a measured nearby cell returned 2, 3 and 4 exact-value citations. Replaying the request reused the same job and final dataset.

Sources: Sentinel-2 `S2B_43PGQ_20260512_0_L2A`, acquired 2026-05-12; Landsat `LC08_L2SP_144051_20260908_02_T1`, acquired 2026-09-08. Independent 100 m source-window calculations matched cell [0,0]: NDVI 0.5679 and temperature 37.8665 °C. The independent calculation imports no worker numerical helpers. Official STAC records came from Earth Search search-by-ID after the item lookup timed out; raster verification ran successfully in Linux after the desktop reader stalled.

Validation: 33 frontend, 34 backend and 22 pipeline tests passed; SAM lint, Linux imports and 12 image scientific/worker/verifier fixtures passed. Seven deployed legacy API/CORS checks passed. Controlled phone-width and desktop previews covered NDVI-first, final temperature, no observation, busy, provider error, denied GPS, AR summaries and revision changes. Browser testing does not validate physical phone camera, GPS or compass hardware.

The user's $10 constraint is interpreted as current-month account charges. Before deployment, Cost Explorer reported a small estimated amount (estimated, delayed). Runtime admission reserves USD 1 per uncached generation and USD 1 margin and stops new processing conservatively; cache reads remain available. This is an application processing guard, not an account-wide AWS spending lock. Other AWS traffic and delayed billing can still affect final charges. The worker image's uncompressed size gives a conservative full-month ECR storage estimate of USD 0.11349822710 at [AWS's USD 0.10/GB-month price](https://aws.amazon.com/ecr/pricing/), before free-tier eligibility or compressed-size reductions.

**Public HTTPS site:** https://production.d3piecnpvqjn3g.amplifyapp.com. The frontend is deployed through Amplify manual hosting and the SAM API allows its exact origin. See the [Amplify runbook](amplify-hosting.md) for current hosting updates. The direct S3 + CloudFront approach below remains available after account verification.

The hosting stack is defined in `deployment/hosting.yaml`; the API uses the normal `template.yaml` and its 28-second Lambda timeout. Both deploy in `ap-south-1`. Hosting uses a separate private AES256-encrypted S3 bucket, CloudFront origin access control restricted to this distribution, HTTPS redirects and response security headers. Bucket owner enforced disables ACLs. The bucket is retained if its stack is removed.

The CloudFront cache policy has minimum TTL zero so it honors revalidation of HTML and data. Hashed Vite assets can be cached for one year. Missing files remain HTTP errors; there is no catch-all HTML response. PriceClass_200 includes Indian edge locations.

## Resources

The direct CloudFront deployment is blocked by AWS account verification. The `greenlens-hosting` CloudFormation stack rolled back to `ROLLBACK_COMPLETE`; its empty retained S3 bucket is `greenlens-hosting-sitebucket-8dpohxqbzc8x`. It created no distribution. All four public-access blocks and AES256 encryption were verified on the retained bucket. The [prepared AWS Support request](cloudfront-support-request.md) records the exact AWS error. Following the user's supplied support guidance, Amplify app `d3piecnpvqjn3g`, branch `production`, manually deployed job `1` successfully and supplies the public HTTPS site. No failed-stack deletion was needed for this deployment.

The API stack `greenlens-api` reached `UPDATE_COMPLETE` after changing CORS to `https://production.d3piecnpvqjn3g.amplifyapp.com`. Its QueryUrl is `https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/query`; Lambda is `greenlens-api-QueryFunction-hDHyPjNvABCR`. No wildcard CORS is used. The Lambda is active with Python 3.12, 512 MB memory and a 28-second timeout; deployed throttling is one request/s with burst two, and logs retain seven days.

SAM created deployment-artifact bucket `aws-sam-cli-managed-default-samclisourcebucket-cwp2tqz9y2rr` through its managed stack. No frontend files have been uploaded to the empty retained hosting bucket, because it has no usable CloudFront distribution.

Local `.env.production.local` sets the public API endpoint for production builds and is git-ignored; development continues using the existing SAM proxy. The current `dist` build is connected to AWS and was uploaded to Amplify. Local production previews render the frontend but cannot call the deployed API from localhost, which is now excluded by CORS. Use the public Amplify site for deployed summaries or local Vite development with SAM for local testing.

The existing measured-data bucket is `greenlens-data-636993911888-ap-south-1`; it is separate from the frontend bucket. Lambda can read only `data/grid.json` and `data/provenance.json`. API throttling remains one request per second with burst two, and logs expire after seven days. This deployment adds no AI service.

## Deploy or update (PowerShell, project root)

Use the existing default AWS profile. If expired, refresh with `aws login --region ap-south-1`, then verify the account with `aws sts get-caller-identity`. The initial deployment used account `636993911888`.

Before retrying hosting after AWS verification, the failed `greenlens-hosting` stack must be removed with authorization, or deploy under a new stack name and update the commands below. The retained bucket is not removed with the failed stack; it is empty and can be explicitly removed separately if no longer needed. Do not deploy repeatedly while AWS still denies account verification.

```powershell
$awsCli = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$env:SAM_CLI_TELEMETRY = '0'
npm.cmd test
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.sam-venv\Scripts\cfn-lint.exe deployment/hosting.yaml
.\.sam-venv\Scripts\sam.exe validate --lint --region ap-south-1

# Review the hosting change set before executing it.
& $awsCli cloudformation deploy --template-file deployment/hosting.yaml --stack-name greenlens-hosting --region ap-south-1 --no-execute-changeset --tags Project=GreenLens Purpose=Hackathon
# Inspect the returned ARN with describe-change-set and describe-events.
# Execute it with cloudformation execute-change-set after review.

$hosting = (& $awsCli cloudformation describe-stacks --stack-name greenlens-hosting --region ap-south-1 --output json | ConvertFrom-Json).Stacks[0]
$siteUrl = ($hosting.Outputs | Where-Object OutputKey -eq 'SiteUrl').OutputValue
$siteBucket = ($hosting.Outputs | Where-Object OutputKey -eq 'SiteBucket').OutputValue
$distributionId = ($hosting.Outputs | Where-Object OutputKey -eq 'DistributionId').OutputValue

.\.sam-venv\Scripts\sam.exe build --use-container --skip-pull-image
.\.sam-venv\Scripts\sam.exe deploy --template-file .aws-sam/build/template.yaml --stack-name greenlens-api --region ap-south-1 --resolve-s3 --capabilities CAPABILITY_IAM --parameter-overrides "DataBucket=greenlens-data-636993911888-ap-south-1" "AllowedOrigin=$siteUrl" --no-execute-changeset
# Inspect the returned API change set and describe-events; then execute it.

$apiStack = (& $awsCli cloudformation describe-stacks --stack-name greenlens-api --region ap-south-1 --output json | ConvertFrom-Json).Stacks[0]
$queryUrl = ($apiStack.Outputs | Where-Object OutputKey -eq 'QueryUrl').OutputValue
$env:VITE_QUERY_URL = $queryUrl
npm.cmd run build
Remove-Item Env:VITE_QUERY_URL

# Upload assets before the page that references them. Keep older hashed assets
# available to open browser tabs; this command does not delete remote files.
& $awsCli s3 cp dist/ "s3://$siteBucket/" --recursive --exclude index.html --exclude 'data/*' --cache-control 'public,max-age=31536000,immutable' --region ap-south-1 --only-show-errors
& $awsCli s3 cp dist/data/ "s3://$siteBucket/data/" --recursive --cache-control 'public,max-age=0,must-revalidate' --region ap-south-1 --only-show-errors
& $awsCli s3 cp dist/index.html "s3://$siteBucket/index.html" --content-type text/html --cache-control 'public,max-age=0,must-revalidate' --region ap-south-1 --only-show-errors
& $awsCli cloudfront create-invalidation --distribution-id $distributionId --paths '/*'
```

Run commands individually and stop on a nonzero exit code. The deployment must reach `CREATE_COMPLETE` or `UPDATE_COMPLETE` before publishing the frontend. Compare downloaded copies of the data bucket's two JSON files with the frontend copies using SHA256; publish matching snapshots. Future data updates require a Lambda recycle/redeployment because its data is cached within each execution environment.

## Verification

Verified October 10, 2026: frontend 22/22 tests, backend 8/8 tests, SAM lint, hosting cfn-lint and AWS template validation, Lambda container build and Vite production build. Downloaded data-bucket grid/provenance SHA256 hashes matched the frontend copies.

Seven live API checks passed using `backend/verify_deployed.py` with the Amplify origin: allowed preflight, unrelated origin excluded, all three summaries with exact citation/grid/provenance agreement, outside coverage and invalid input. First observed summary during this check: 4.09 s; warm comparison and planting survey: 0.12 s each. Browser checks on the public Amplify site passed for all three AWS summaries and measured-source expansion. All 21 frontend files, including images, font, data and lazy imagery chunks, matched the local production build by SHA256. Root HTML returned 200, missing assets and environment-file paths returned 404, HTTP redirected to HTTPS and response security headers were present. Deployed S3 read permissions remain limited to the two expected objects. Direct CloudFront-specific tests remain pending for that optional migration; physical phone testing is still outstanding.

Rerun live checks with:

```powershell
.\.venv\Scripts\python.exe backend/verify_deployed.py https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/query --origin https://production.d3piecnpvqjn3g.amplifyapp.com
.\.venv\Scripts\python.exe deployment/verify_frontend.py https://production.d3piecnpvqjn3g.amplifyapp.com
```

After migrating to direct CloudFront, pass `--origin $siteUrl` instead. The API verification script makes billable HTTP API requests and paces them below the configured throttle.

- HTTPS `/`, JavaScript/CSS chunks, fonts, imagery and both measured JSON files load.
- HTTP redirects to HTTPS, anonymous S3 reads fail, and nonexistent assets remain errors.
- The API preflight permits POST and Content-Type from SiteUrl; an unrelated origin gets no allow-origin response.
- The three supported summaries return measured sources. Outside coverage returns No data; invalid input returns HTTP 400.
- Browser summary buttons and source expansion work on the deployed site.
- Repeat the README phone checklist in Android Chrome and iOS Safari. Browser automation cannot verify physical camera, GPS accuracy or compass hardware.

## Cleanup

Remove hackathon resources when no longer needed: disable and remove the CloudFront distribution/hosting stack, remove the API stack, and explicitly empty/remove the retained hosting bucket when its contents are no longer needed. The existing satellite-data bucket and SAM-managed deployment-artifact bucket are separate resources; do not remove them blindly. Request throttling is not a billing cap. S3, CloudFront, API Gateway, Lambda and CloudWatch usage can incur charges.

Amplify is a separate app, not part of the failed CloudFormation stack. Retire its `production` branch/app only once the public demo is no longer needed or migration has been verified. Amplify hosting usage can also incur charges.

## AWS references

- [CloudFront access to private S3 using OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [Cache policy TTL behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cache-key-understand-cache-policy.html)

Amplify frontend deployment 3 succeeded after the recovery review fixes. All 20 published files matched the local build; HTTPS redirects, security headers and missing-file 404 checks passed. The final Cost Explorer check reported a small estimated amount, before delayed new charges. The published phone-width view retains the Aliganj preview and waits for actual GPS before enabling measured summaries.


## Final recovery review and corrective delivery

A fresh whole-feature reviewer found two Important recovery defects and no Critical or Minor findings. Both were reproduced with failing tests and fixed in one pass: a busy response now preserves explicit retry intent, and a timed-out partial worker carries forward fresh NDVI with its original expiry. The integration regression verifies that the replacement worker processes only temperature.

Commit `7a87732` contains the corrections. SAM rebuilt successfully; its reviewed change set changed QueryFunction code and the dependent QueryApi integration reference only, with no replacement or failed validation events. The stack reached UPDATE_COMPLETE and QueryFunction became Active/Successful at 2026-10-10T20:40:10Z. The raster worker image was unchanged. Cached live checks retained generation `622b3c7345e34e34a1ec8ac4d6dc162a`, both measured fields and exact summary citations; all seven legacy API/CORS checks passed again.

Amplify production job **3** succeeded. All **20** published files matched the corrected local build; HTTPS redirect, security headers and missing-file 404 checks passed. Phone-width browser checks confirmed that GPS mode clears Aliganj readings, waits for location access and disables summaries until measurements are available. No physical phone permissions or sensors were tested. Final suites passed: **33 frontend, 34 backend, 22 pipeline, 12 Linux image fixtures**; SAM lint and both production builds passed.

The final Cost Explorer check reported estimated current-month charges of **a small estimated amount**, excluding credits/refunds. This value is delayed and does not include all new deployment, storage, request or Cost Explorer charges yet. The conservative processing reservations remain enabled under the user's USD 10 ceiling.

Execution rulings, in order:

1. Interpret the ceiling as current-month account charges and reserve USD 1 per new generation plus USD 1 margin; refuse processing when billing cannot be verified. Cost if wrong: processing may stop earlier than actual spend requires.
2. Use the existing checkout on a feature branch because the initial application files were untracked and would be absent in a new worktree. Cost if wrong: less filesystem isolation; unrelated files must be preserved.
3. Persist a monthly budget stop and reject exhausted reservations before another Cost Explorer call. Cost if wrong: conservative shutdown until the next billing month.
4. Report physical camera, GPS and compass testing as unverified because no physical phone is available. Cost if wrong: device-specific permission or sensor issues remain undetected.

Deferred minor findings: none. Source commits remain on `codex/gps-satellite-processing`; no merge or push was requested.
