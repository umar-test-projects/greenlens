# GreenLens Step 5 Deployment Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task in the current session.

**Goal:** Publish GreenLens at a permanent CloudFront HTTPS URL with a working SAM API.

**Architecture:** A separate CloudFormation hosting stack owns a private encrypted S3 bucket, CloudFront origin access control, cache policy and distribution. The existing SAM stack reads the existing satellite data bucket. Build the frontend with its QueryUrl and restrict API CORS to the hosting origin.

**Tech Stack:** CloudFormation, SAM, AWS CLI, Vite, React, Python 3.12 Lambda.

**Spec:** README.md architecture/build sequence and docs/backend.md deployment requirements.

## Global Constraints

- Use ap-south-1 and the existing GreenLens account/data bucket.
- Deploy the normal 28-second Lambda template, never local-template.yaml.
- No Bedrock, invented data, public S3 ACLs or credentials in frontend files.
- Hardware acceptance remains a team test on Android Chrome and iOS Safari.

## Review Focus

- CloudFront must load the page, images, grid and lazy GPS imagery libraries.
- API preflight must allow the exact deployed origin; arbitrary origins must not be allowed.
- Missing assets must remain errors; HTML must not replace missing JavaScript.
- Data served by the frontend must match the Lambda S3 snapshot.
- Anonymous S3 access must fail while CloudFront access succeeds.

### Task 1: Hosting infrastructure

**Files:** Create deployment/hosting.yaml.
**Interfaces:** Outputs SiteUrl, SiteBucket and DistributionId for API configuration and upload.

- [x] Add private encrypted S3 with retention, OAC restricted to this distribution, HTTPS redirect, compression and a cache policy with minimum TTL zero.
- [x] Validate schema with cfn-lint and review encryption, bucket policy and cache behavior.
- [x] Check account/resources, create a change set, inspect changes and validation events, then execute under the user's Step 5 authorization. Execution blocked by AWS account verification and rolled back.

### Task 2: API and frontend publication

**Files:** Existing template.yaml and src/QueryPanel.jsx; create docs/deployment.md.
**Interfaces:** SAM QueryUrl is the build-time VITE_QUERY_URL. Hosting SiteUrl is AllowedOrigin.

- [x] Run frontend/backend tests and SAM lint; rebuild Lambda with current source/dependencies.
- [x] Compare local grid/provenance hashes with existing private S3 data.
- [x] Create and inspect the API change set, then execute with provisional localhost origin. Hosting-origin update pending.
- [ ] Build with VITE_QUERY_URL; upload immutable hashed assets and revalidating HTML/data; invalidate CloudFront. Build complete; publication awaits distribution.

### Task 3: Live verification and project record

**Files:** Update README.md, docs/backend.md, docs/api-contract.md and docs/deployment.md.

- [ ] Check HTTPS page/assets/data, HTTP redirect, anonymous S3 denial, and missing asset errors.
- [x] Check allowed/disallowed CORS, all three summaries, invalid input and outside-coverage behavior.
- [ ] Open the live site and verify browser summaries and source expansion. Passed on local production preview against AWS; permanent site pending.
- [x] Record deployed resource outputs and evidence, retaining the unperformed phone hardware checks.

## Execution record

Ruling: Execute in the existing checkout because this repository has no initial commit and deployment needs the current untracked application. User explicitly requested Step 5 execution; no additional publishing approval is required.

Initial blocker: AWS CLI session expired; user approved aws login and browser sign-in is pending.

Login completed in account 636993911888. Frontend 22/22 and backend 8/8 tests passed; SAM and hosting schema checks passed. Lambda container build succeeded. Grid/provenance SHA256 match the existing S3 objects.

Hosting change set passed pre-deployment validation and added only six intended resources. Execution failed at SiteDistribution because AWS requires account verification; no template or IAM adjustment can resolve this restriction. CloudFormation rollback retains the new empty hosting bucket by design.

Ruling: Continue the independent API deployment using its existing localhost CORS origin until a real hosting origin exists. Do not broaden CORS or claim permanent hosting is deployed. Save an AWS Support draft without sending it.

API greenlens-api reached CREATE_COMPLETE. Seven live checks passed. The production preview at localhost:5173 fetched all three summaries and expanded measured sources from AWS. Least-privilege S3 policy, Lambda state/timeout/memory, API throttling and log retention verified. Hosting reached ROLLBACK_COMPLETE and has no distribution. The empty retained bucket is private/encrypted. Public API endpoint is stored in git-ignored .env.production.local for builds; local development retains SAM proxy behavior.

Remaining: AWS Support account verification, removal/replacement of failed hosting stack with authorization, successful hosting deployment, CORS origin update, frontend upload, CloudFront verification and real-phone checks. The support draft is docs/cloudfront-support-request.md; no message has been sent.

## Amplify interim hosting continuation

User supplied an AWS support response proposing Amplify manual hosting while CloudFront account verification is processed. Continue the authorized Step 5 deployment using this hosting path. Official AWS docs confirm the manual deployment API and ZIP contents-at-root requirement; whether the service can provision this account's hosting must be established by the deployment itself.

- [x] Create a manual Amplify WEB app and production branch in ap-south-1, with response headers from deployment/amplify-custom-headers.yaml.
- [x] Update the existing SAM stack's AllowedOrigin parameter to the app's exact HTTPS origin via a reviewed CloudFormation change set.
- [x] Build with the existing VITE_QUERY_URL, ZIP dist contents at archive root, upload via CreateDeployment and start the manual job.
- [x] Verify deployment job success, HTTPS assets/data, error paths and all AWS summaries with citations. HTTPS and device permission policy are verified; physical camera/location/compass acceptance remains a team test. The automation's isolated read-only evaluator could not inspect navigator APIs, so no device-API availability claim is made.
- [x] Record the interim public URL, app/job IDs, reusable deployment steps and unperformed phone checks.

Ruling: Retain the failed direct-CloudFront stack and empty bucket during this continuation. The supplied support text does not itself authorize their deletion, and neither is required to deploy Amplify.

Amplify app d3piecnpvqjn3g / production manual job 1 completed SUCCEED for deployment and verification. Public URL: https://production.d3piecnpvqjn3g.amplifyapp.com. The API origin update reached UPDATE_COMPLETE and modified only QueryApi, without replacement. All 21 public files match dist by SHA256; HTTPS root, HTTP redirect, headers and missing-file 404 checks passed. Seven API checks passed with the new origin; browser checks passed for all three summaries and source expansion. The app has been left open as the user-facing result.

Current Step 5 hosting/API deployment is achieved via the Amplify interim route. Direct CloudFront migration remains optional and blocked until AWS account verification is lifted. Physical phone tests are still unperformed and documented in README.md and docs/amplify-hosting.md.
