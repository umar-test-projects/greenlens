# GreenLens Amplify HTTPS hosting

Current air temperature is fetched directly by the browser from Open-Meteo using rounded area coordinates, Celsius, `current=temperature_2m` and Unix timestamps. It is independent of the satellite processing route and needs no AWS infrastructure change. The UI includes provider attribution, a weather time, unavailable/retry states, and a 15-minute refresh. The free endpoint is intended for the non-commercial demo. Source and usage details: [weather documentation](https://open-meteo.com/en/docs), [provider terms](https://open-meteo.com/en/terms).

The GPS satellite update adds `VITE_SATELLITE_URL=https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/satellite` alongside the existing query URL. These are public endpoint URLs in ignored `.env.production.local`. Build with `npm run build`, zip the contents of `dist` so `index.html` is at the archive root, and upload through Amplify manual deployment. The synthetic `/tests/satellite-preview.html` fixture is a development entry and is excluded from the production bundle. Delivery evidence is recorded in [deployment.md](deployment.md).

On a phone, open the HTTPS site, choose Tools → Use my location and allow GPS. Vegetation loads first; Surface heat uses a separate Landsat acquisition. Retry measurements checks failed jobs after their cooldown. Clouds and invalid samples can leave individual cells without data; select another measured cell to inspect nearby observations. Camera access remains optional for the 3D view.

Live site: **https://production.d3piecnpvqjn3g.amplifyapp.com**

Amplify manual hosting succeeded in this account while direct CloudFront distribution creation remains blocked by AWS account verification. This is the interim frontend hosting environment. The SAM API and private measured-data bucket are unchanged.

## Resources

- Region: `ap-south-1`
- App name: `greenlens-hosting`
- App ID: `d3piecnpvqjn3g`
- Platform: `WEB`, no Git provider, automatic builds disabled
- Branch: `production`, stage `PRODUCTION`
- Initial manual deployment job: `1`, `SUCCEED` for DEPLOY and VERIFY
- API: `https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/query`
- API stack: `greenlens-api`, `AllowedOrigin=https://production.d3piecnpvqjn3g.amplifyapp.com`

The Vite build uses **VITE_QUERY_URL**. The React application is static; it does not use `REACT_APP_API_URL` or require a server-side runtime. ZIP files contain the contents of `dist`, with `index.html` at the root. Only the public build is uploaded, never the project root or environment files.

## Publish an update

Run in the project root with the existing authenticated AWS CLI profile:

```powershell
$awsCli = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$env:VITE_QUERY_URL = 'https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/query'
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Remove-Item Env:VITE_QUERY_URL
Compress-Archive -Path dist/* -DestinationPath .aws-sam/greenlens-frontend.zip -Force

$upload = (& $awsCli amplify create-deployment --app-id d3piecnpvqjn3g --branch-name production --region ap-south-1 --output json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'CreateDeployment failed' }
# The upload URL is temporary authorization: keep it in memory and do not log it.
$uploaded = Invoke-WebRequest -Method Put -Uri $upload.zipUploadUrl -InFile .aws-sam/greenlens-frontend.zip -ContentType application/zip -TimeoutSec 180
if ($uploaded.StatusCode -ne 200) { throw 'ZIP upload failed' }
& $awsCli amplify start-deployment --app-id d3piecnpvqjn3g --branch-name production --job-id $upload.jobId --region ap-south-1 --query 'jobSummary.{Id:jobId,Status:status}' --output json
# Check this job until its status is SUCCEED or FAILED.
& $awsCli amplify get-job --app-id d3piecnpvqjn3g --branch-name production --job-id $upload.jobId --region ap-south-1 --query 'job.{Summary:summary.{Id:jobId,Status:status},Steps:steps[].{Name:stepName,Status:status}}' --output json
```

The app's response headers are defined by `deployment/amplify-custom-headers.yaml` and were supplied as the app's `customHeaders` field. After modifying those headers, update the app's `customHeaders` with the YAML contents and redeploy the build. Do not add a blanket HTML rewrite for missing JavaScript or data files.

For API updates, continue using the existing SAM template and pass the exact hosting origin:

```powershell
.\.sam-venv\Scripts\sam.exe deploy --template-file .aws-sam/build/template.yaml --stack-name greenlens-api --region ap-south-1 --resolve-s3 --capabilities CAPABILITY_IAM --parameter-overrides 'DataBucket=greenlens-data-636993911888-ap-south-1' 'AllowedOrigin=https://production.d3piecnpvqjn3g.amplifyapp.com' --no-execute-changeset
```

Review the API change set before executing it. The hosting migration changed only `QueryApi` CORS through CloudFormation; it did not replace the API or redeploy Lambda code. Allowed browser origin is the public Amplify site only. Development still uses the same-origin Vite-to-local-SAM proxy; production builds viewed at localhost cannot call the deployed API from that excluded origin.

## Verify

```powershell
.\.venv\Scripts\python.exe deployment/verify_frontend.py https://production.d3piecnpvqjn3g.amplifyapp.com
.\.venv\Scripts\python.exe backend/verify_deployed.py https://y6yl9bz1u1.execute-api.ap-south-1.amazonaws.com/query --origin https://production.d3piecnpvqjn3g.amplifyapp.com
```

The frontend verifier checks every uploaded file against the local production build with SHA256, root HTML, required response headers, HTTP-to-HTTPS redirect and missing-file 404 responses. The API verifier checks CORS, the three summaries and their exact measured citations, no-data responses and invalid input. These commands make network requests that can incur AWS usage charges.

Open the public site in Android Chrome and iOS Safari and perform the README real-phone checklist. HTTPS and permission policy are configured, but physical camera, GPS and compass acceptance must still be tested by the team.

## Direct CloudFront migration

The failed `greenlens-hosting` CloudFormation stack remains `ROLLBACK_COMPLETE`, with its empty retained private bucket. It has not been deleted. Once AWS verifies the account, remove/replace that failed stack with authorization and deploy `deployment/hosting.yaml`. Change the API origin to the new CloudFront URL, publish a matching frontend snapshot, and verify it before retiring Amplify. The Amplify app and original CloudFormation stack share a display name but are separate resources.

## Primary sources

- [AWS manual hosting and ZIP-root requirements](https://docs.aws.amazon.com/amplify/latest/userguide/manual-deploys.html)
- [CreateDeployment upload URL](https://docs.aws.amazon.com/amplify/latest/APIReference/API_CreateDeployment.html)
- [StartDeployment](https://docs.aws.amazon.com/amplify/latest/APIReference/API_StartDeployment.html)
- [Custom response headers](https://docs.aws.amazon.com/amplify/latest/userguide/custom-headers.html)
