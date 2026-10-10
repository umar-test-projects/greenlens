# GreenLens security review — 11 October 2026

Scope: the React frontend, `/query` and `/satellite` handlers, satellite source readers, deployment templates, live Amplify headers, API configuration, two S3 buckets, and the Lambda execution policies. This was a source review with bounded live checks; no load attack or new satellite processing job was run.

## Findings and changes

| Severity | Finding | Result |
| --- | --- | --- |
| Medium | Amplify responses lacked a Content Security Policy. | Added a policy with explicit application/data origins, blocked inline JavaScript, JavaScript eval, framing, object embedding, forms and base-URL changes. Browser compatibility checks passed with actual weather, catalog, S3 range reads and GeoTIFF worker decoding. |
| Medium | The public demo API accepts unauthenticated callers. CORS restricts browsers but does not authenticate clients. | Documented remaining availability/cost exposure. Existing live throttles are 1 request/second with a burst of 2. New satellite generations require verified billing and conservative reservations; a single global lease prevents parallel processing admission. Someone can still consume the demo's limited processing allowance. Before broader public use, add an authenticated or server-issued admission mechanism and per-client limits. |
| Low | The deployment operator is using AWS root credentials. | Runtime Lambda roles are scoped to the two archive files, processing prefixes and worker invocation, with basic execution logging. Deployment access should move to a dedicated least-privilege identity. No credentials or IAM access were created or expanded during this review. |
| Low in the current request flow | The local environment and existing worker image contain pip 25.0.1, which has installation-time advisories. | Updated the local installer to 26.2.1 using a SHA256-verified wheel from the official PyPI release. The deployed worker still contains the older installer; update it during the next image maintenance deployment. The API does not accept packages or invoke pip, and the image build uses trusted PyPI binary wheels. This does not make the affected installer vulnerability-free. |

The CSP permits inline styles because React/Three.js use style attributes, blob workers/images/media for on-device rendering, and `wasm-unsafe-eval` plus data fetches for bundled GeoTIFF codecs. It does not permit arbitrary JavaScript eval or remote scripts. Required connection origins are the existing API Gateway, Open-Meteo, Earth Search and the two allowlisted Sentinel S3 hosts. Configuration: `deployment/amplify-custom-headers.yaml`.

HTML now requests immediate cache revalidation so phones receive updated asset references. Current air temperature retains its source time and weather attribution; historical imagery and surface heat have explicit acquisition dates.

## Evidence

- `npm audit`: zero reported vulnerabilities in frontend production and development dependencies.
- `pip-audit`: after the local installer update, all 57 installed local Python packages had no reported advisories. The older worker image's installer finding remains separately listed above.
- Secret-pattern scan: 265 source/build files and Git-history blobs checked; no matching access keys, private keys or provider tokens. Environment files and deployment archives remain ignored and excluded from the published build.
- Frontend: 43 tests passed, including keyboard dismissal/focus restoration; production build passed with the existing bundle-size and mixed-import warnings.
- Backend: 34 tests passed. Inputs reject booleans, nonfinite/out-of-range coordinates, excessive payloads and malformed dataset IDs. Responses use generic errors with `Cache-Control: no-store`; logs omit precise GPS, questions and provider response details.
- Live checks: malformed `/query` and `/satellite` requests and a traversal-style dataset ID returned 400. An unsupported script-containing question was not echoed and produced no citations. An untrusted browser origin was not allowed. Anonymous reads of the archive grid and processing admission object returned 403.
- Both S3 buckets have all four public-access blocks enabled and only owner ACL grants. Processing cache encryption is AES256; cache lifecycle and seven-day log retention remain configured.
- Live Lambda inline policies match the template's scoped permissions. Neither execution role has an administrator policy; both attach AWSLambdaBasicExecutionRole for logging. Cost Explorer uses its required service-wide resource scope.
- Satellite worker asset validation accepts only HTTPS Sentinel hosts and the official Landsat S3 product prefix. The browser reads allowlisted Sentinel hosts. React renders summary strings as text and has no HTML injection sink in these flows.
- Camera frames stay on the device; camera, GPS and compass requests occur from user controls. Weather uses rounded area coordinates. The site has no session cookies, login tokens, payments or user file-upload endpoint.
- Mobile checks at 320 × 568 and 390 × 844, plus desktop: enlarged controls, no narrow-phone page overflow, no temperature/control overlap, reachable summary actions, and Escape returning focus to Tools. Physical camera/GPS/compass hardware was not retested by this review.

## Cost and practical limits

Before publication, Cost Explorer reported estimated monthly charges of a small estimated amount excluding credits/refunds. This is delayed billing, not a guarantee of final charges or an account-wide spending cap. The existing $10 processing guard remains enabled. No new AWS resource, paid model, authentication provider or satellite generation was added.

The local worker image inventory audit checked 19 Python packages excluding the AWS-provided runtime interface package; only pip had reported advisories (six distinct advisory records, with duplicate feed entries). No other audited worker library had a reported advisory. This review does not cover every AWS account setting or a vulnerability scan of container OS packages. The immutable container inventory was not changed by this frontend deployment.

## Verified deployment

Amplify production job 6 succeeded. All 20 deployed files match the local production build by SHA256. Root and index responses enforce the CSP; the root has `max-age=0` cache revalidation. HTTP redirects to HTTPS, absent assets and environment files return 404, and the existing permissions, framing, referrer and MIME-sniffing protections remain present. Browser inspection of the live 390 × 844 site confirmed the polished controls, visible preview badge, dated historic imagery and the modeless tools panel. The live Local conditions action returned a successful dated surface-temperature/NDVI summary with two measured citations under the enforced policy.

References: [AWS Amplify custom headers](https://docs.aws.amazon.com/amplify/latest/userguide/setting-custom-headers.html), [MDN script policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/script-src), [MDN worker policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/worker-src).
