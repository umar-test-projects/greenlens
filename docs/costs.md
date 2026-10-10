# Running costs and stopping the demo

Uploading source code to a GitHub repository does not deploy AWS resources. This project has no GitHub Actions workflow, and its Amplify hosting uses manual deployments rather than automatic Git builds. Repository hosting is available on GitHub Free; optional paid GitHub features are separate.

GreenLens is not guaranteed to run for free. Check the actual AWS account plan, credit balance and expiry in Billing before deployment. An active Free account plan does not incur cash charges until it moves to a paid plan; resources still consume eligible credits. AWS can close an unupgraded Free account when the free period ends or credits run out. Certain account actions, such as joining AWS Organizations, automatically upgrade a Free account to a paid plan. See [AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

| Resource | Possible ongoing cost |
| --- | --- |
| Amplify Hosting | Stored deployments and traffic served to visitors; cloud builds if enabled later. The current project builds locally and uploads manually. |
| API Gateway and Lambda | Requests and execution, including polling, retries and invalid callers. The public API has no authentication. |
| Satellite worker | Raster reads, request/data-transfer charges and Lambda execution for new uncached neighborhoods. Landsat reads explicitly accept requester-pays charges. |
| ECR | Storage for the worker container image, even when no one visits the app. |
| S3 | Satellite archive, processing cache and SAM deployment artifacts. Versioned artifact buckets can retain old versions. |
| CloudWatch Logs | Log ingestion and storage. Application logs expire after seven days. |
| Cost Explorer API | Billing checks are themselves chargeable API requests; console viewing is separate. |

The application checks account-wide monthly reported charges before admitting new satellite generations, reserves USD 1 per admitted generation and USD 1 margin, and rejects admission if billing is unavailable or the conservative USD 10 threshold would be reached. This only limits new satellite processing. It does not stop Amplify, ordinary API calls, storage or unrelated AWS services, and billing is delayed. API throttling also does not impose a monthly spending ceiling. A USD 10 AWS Budget and its alerts are monitoring, not a hard account spending lock.

AWS does not provide a strict USD 10 account-wide spending cutoff through Budgets. Budget actions can restrict permissions or stop supported instances after a threshold is reported, but billing updates are delayed and existing hosting/storage charges can continue. Keeping an account on the Free plan prevents cash charges while that plan remains active; it does not limit credit consumption to USD 10. Do not upgrade to Paid or perform an automatic-upgrade action if zero cash charges are required. See [budget update frequency and limits](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html) and [supported budget actions](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-controls.html).

For fewer credit-consuming resources, keep automatic builds, provisioned concurrency, WAF, custom domains and scheduled jobs disabled unless needed. Before wider public use, authenticate the processing API and apply per-client limits. Do not assume the Free plan's credits make a public endpoint unlimited.

To retire the demo, first back up source and required public data. Then remove the separate Amplify app, API stack, worker-image companion stack/repository, and project-specific buckets and their versions when their data is no longer needed. The processing bucket has a Retain policy and survives API stack deletion. The SAM-managed artifact bucket may be shared by other deployments; inspect it before cleanup. Deleting the failed direct CloudFront stack alone does not stop Amplify or the API. Cleanup is destructive and should be explicitly authorized.

Pricing references: [Amplify](https://aws.amazon.com/amplify/pricing/), [Lambda](https://aws.amazon.com/lambda/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/), [S3](https://aws.amazon.com/s3/pricing/), [ECR](https://aws.amazon.com/ecr/pricing/), [CloudWatch](https://aws.amazon.com/cloudwatch/pricing/), [Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/), [AWS Budget limits](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html), [GitHub plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans).
