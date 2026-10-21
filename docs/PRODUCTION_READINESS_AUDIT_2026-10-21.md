# NCET VerifyFlow production-readiness audit

**Observed:** 21 October 2026, 21:04 Asia/Kolkata  
**Live service:** ncet-verifyflow on Render  
**Source:** hackerncet/tuxnestsite main, deployed commit e069f73d1879be29239b9a1ea507729e7f8023a1  
**Scope:** public profile and performance pages; supplied admin, HOD, and staff sign-ins; task and complaint panels; notifications; one authorized synthetic task submission; Render service, database, deployment, and metric evidence; GitHub CI/security checks; student portfolio UI follow-up.

This is a focused release audit, not a penetration test or institutional approval. The production AI gate remained disabled. The synthetic task submission described below was the only production data change made during this run.

## Verified release state

- Render reports the service connected to https://github.com/hackerncet/tuxnestsite, branch main, with automatic deploys on commit. It runs one instance on the free plan.
- Admin, HOD, and staff sign-ins succeeded on the Render hostname. Role-specific dashboards loaded. No account, password, rule, complaint, or HOD decision was changed.
- The HOD complaints dashboard loaded and showed zero cases. The HOD task dashboard loaded three records; the staff view showed one assigned test task and its inbox.
- The user-provided student profile at /students/profile/1NC24CS146 loads as a student-owned portfolio with projects first, share and PDF actions, and an edit/publish path.
- Follow-up release PR #69 improved the project gallery and made the student edit/publish action explicit. After the live deploy, the profile rendered with four project cards and its action opened the student portal sign-in route. The editor source confirms students can publish/unpublish and save portfolio updates; an authenticated student save was not exercised because no student credentials were supplied. No student data was changed.
- The live /plot page reported one browser sample: LCP 944 ms, CLS 0.000, TTFB 256 ms, 5.3 KB transferred, and a successful /healthz response in 373 ms. INP was not measured because no qualifying interaction occurred. These are one-visit measurements, not field percentiles.
- Render metrics for the queried 24-hour period returned memory samples, with the latest around 260 MB. CPU, HTTP request-count, and latency series returned no usable samples; no live p95 latency conclusion can be drawn.
- GitHub Actions for PR #66 head 39c0091cce715199dfd37d96525f2af4b75c6ceb completed successfully: NCET VerifyFlow CI run 983 and NCET Security Audit run 399.
- The notification inbox showed a new staff task notice and HOD submission/verification notices. Render request logs show /api/alerts/inbox requests at approximately 1.5-second intervals, matching the intended refresh cadence.

## Authorized production workflow simulation

Using the existing synthetic task ncet-workflow-test.pdf (task 3) and the existing staff account, the task's reference PDF was downloaded from the app and submitted through the staff upload control. Render logged POST /api/tasks/3/submit as 201 Created. Deterministic processing completed and moved the task to manual review; the UI clearly said the HOD should review the findings manually and that no AI decision was assumed. The HOD inbox received both submission-started and verification-completed notices.

The submitted file and task record remain in production in manual review. No task was deleted, no student was created or deleted, no inbox item was marked read, and no HOD approval/rejection was issued. AI-provider calls were not tested or requested.

## Findings and actions

| Priority | Finding | Evidence and recommended action |
|---|---|---|
| High | The custom hostname does not complete TLS negotiation. | Browser navigation to https://ncet.paladuguganeshnaidu.tech/app returns ERR_SSL_VERSION_CIPHER_MISMATCH before the app loads. Earlier DNS checks showed the hostname resolving to Render, but the current Render dashboard session redirects to sign-in and the connector does not expose domain-certificate controls. Fix/verify the domain and certificate in the authenticated Render dashboard before using that hostname for logins. |
| High | Passwords were shared in the task and used for the three successful Render sign-ins. | The values are intentionally omitted. Rotate them through the supported account-management flow and store replacements in the operator's password manager. |
| High | Render Blueprint configuration sets SCAN_MODE=off and defines no scanner service. | This is a repository configuration finding; the effective secret environment was not read. Before accepting untrusted institutional documents, configure a reachable malware scanner with fail-closed behavior or keep uploads restricted to controlled pilot use. |
| High | The active database is a free instance named test and expires 14 November 2026. | The live task submission updated task 3 to manual_review in that database at 2026-10-21 14:55:17Z, confirming it serves the running app. The older 3dulpin-db is suspended for billing after its 9 October expiry. Both instances list inbound access as 0.0.0.0/0. Take and verify a backup, restrict access to required sources, and migrate to durable managed storage before expiry. |
| High | Render compute is free tier with one instance. | Free capacity can sleep and does not guarantee always-on verification work. Move to always-on compute and a separately monitored worker before promising institutional deadlines. |
| Medium | Render service health-check configuration is out of sync with the repository Blueprint. | render.yaml declares healthCheckPath: /healthz, and the endpoint returns healthy, but the live service settings still report an empty path. Sync the Blueprint or set the live service field, then re-read the service configuration to confirm. |
| Medium | Render HTTP latency and request metrics are unavailable in the queried series. | Add operational telemetry and alerting for request latency, worker queue age/failures, and database/storage health. The /plot page is intentionally a local browser sample and is not site-wide telemetry. |
| High | Render's commit webhook repeatedly deployed older main revisions after newer releases. | After PR #69 merged 2d460e3, a delayed new_commit event for a65eb62 started and became live, so 2d460e3 had to be redeployed manually. After PR #70 advanced main to e069f73, another delayed new_commit event for 2d460e3 became live; a manual deployment then restored e069f73. /healthz confirmed e069f73. Investigate Render's GitHub webhook/event queue and verify the deployed SHA after every merge until the branch-head deployment is reliable. |
| Medium | VPS auto-deployment is not proven active. | The repository includes a one-command Ubuntu installer and a main-to-VPS workflow, but deployment is gated by VPS_DEPLOY_ENABLED and private SSH/host/origin secrets. No VPS host was available to verify a real deployment. Configure the values privately and verify a controlled deployment before relying on automatic updates. |
| Medium | Student-authenticated production workflows remain unverified. | The supplied test accounts are admin, HOD, and staff. Student account creation, private requests/replies, contribution requests, and student notifications still need an authorized non-production or disposable student account. |
| Medium | Backup recovery and retention have not been demonstrated. | Confirm backup schedule, retention, restore procedure, upload retention, and encryption. Run a restore drill before handling sensitive academic records. |
| Low | Full external penetration and load testing have not been performed. | Passing application tests, Chromium checks, Bandit, and dependency scans is useful release evidence but does not prove resistance to real-world attacks or capacity under representative load. Arrange an authorized independent review before institution-wide use. |

## Release gate

The Render hostname is usable for continued controlled pilot checks, but the evidence does not support a claim of 100% correctness or unrestricted production readiness. Resolve custom-domain TLS, rotate task-shared passwords, enable fail-closed malware scanning, and establish durable database backups and always-on processing before accepting sensitive records at scale. Keep AI disabled until the institution explicitly configures and approves a provider.


## Student portfolio release and deployment recheck — 21 October 2026, 20:48 IST

- PR #69 merged into main as commit 2d460e3af53f5df1957fbac9e3525da4a6d1fdb7. It creates responsive project cards, labels the owner action “Student: edit & publish”, and clarifies public/private profile behavior while retaining the NCET navy/orange theme.
- Render deployment dep-dbcdeluq1p3s73d320kg completed successfully. The live /healthz response reported commit 2d460e3af53f5df1957fbac9e3525da4a6d1fdb7, and the live profile displayed the updated action and project section.
- The edit link opened /students/portal#portfolio and showed the student sign-in page. No student credentials were provided, so no authenticated portfolio save/publish was submitted. No student record was changed.
- Render then delivered a delayed new_commit deployment for a65eb62ecb2849223977698201641a8d7bebd8c3, which temporarily replaced the newer release. A second manual deployment restored 2d460e3. This is direct evidence that Render auto-deploy is currently unreliable even though the service reports autoDeploy=yes and autoDeployTrigger=commit.
- The service's current repository blueprint declares healthCheckPath: /healthz, but Render's live service settings still show an empty path. The Blueprint-to-service sync has not been verified.


## Repeated Render commit-order check — 21 October 2026, 21:04 IST

- PR #70 advanced GitHub main to e069f73d1879be29239b9a1ea507729e7f8023a1 at 15:27:27Z. Render later processed a delayed new_commit event for the previous 2d460e3 commit and made it live at 15:29:54Z.
- A manual deployment of the actual main head e069f73 started at 15:31:49Z and became live at 15:33:28Z. A fresh browser request to /healthz returned {\"ok\":true,\"commit\":\"e069f73d1879be29239b9a1ea507729e7f8023a1\"}.
- The pattern confirms automatic deploy delivery is out of order across successive main commits. Keep the post-merge exact-SHA smoke gate and investigate the Render event queue; do not rely on the service's autoDeploy=yes flag as proof that the latest main commit is live.


## Render state refresh — 21 October 2026, 21:16 IST

- GitHub main and the latest completed Render deployment both report commit 9b51ad0510cb03270d9b01bdf1355947417a19d8. Render lists that deployment as live, triggered by API, and completed at 15:42:34Z. The exact-SHA live health check was confirmed after the deploy.
- Render still reports automatic deploys enabled for commits on main, a free plan, and one configured instance. The earlier out-of-order webhook finding remains relevant; this refresh confirms the current head is live at this observation time only.
- In the queried 75-minute metrics window, CPU and memory returned samples. Memory ranged from about 103 MB to a peak of about 258 MiB; the latest sample was about 230 MiB. HTTP latency and request-count series remained empty, so these data do not establish an application-wide latency baseline.
- The service configuration still reports an empty healthCheckPath despite render.yaml declaring /healthz. The Blueprint/service configuration mismatch remains open.
