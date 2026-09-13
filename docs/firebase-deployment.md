# Production deployment

Pushes to `main` deploy the Python API to Cloud Run and the React frontend to
Firebase Hosting after the `backend` and `frontend` CI checks pass. Pull requests
run validation only. There are no preview environments.

The frontend uses site `sublynt` in Firebase project `nuvorima`. The API runs as
`sublynt-api` in project `invoiceparse-java`, region `northamerica-northeast2`,
with private bucket `sublynt-production-982607010629` and Artifact Registry
repository `sublynt`. These are separate from the existing InvoiceParse service.

Hosting explicitly targets site `sublynt`. `npm run build:hosting --prefix frontend`
generates its configuration, including SPA routing, security headers, API-specific
CSP and immutable caching for hashed assets. Generated configuration is ignored.

## GitHub variables

| Variable | Purpose |
| --- | --- |
| `FIREBASE_PROJECT_ID` | Firebase project containing the site |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Full Google OIDC provider name |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | Deployment identity |
| `GCP_BACKEND_PROJECT_ID` | Backend resources project |
| `GCP_REGION` | Cloud Run and Artifact Registry region |
| `SUBLYNT_STORAGE_BUCKET` | Private production job bucket |
| `GCP_RUNTIME_SERVICE_ACCOUNT` | Runtime identity with access only to the job bucket |
| `VITE_API_URL` | Public HTTPS API URL ending in `/api/v1` |

`VITE_API_URL` is embedded at build time and must not contain credentials. Firebase
cannot inject it at runtime. Rebuild the frontend after changing it.

## Storage and runtime

Local development uses SQLite and local files. Setting `SUBLYNT_STORAGE_BUCKET`
selects Cloud Storage instead: each job is one private JSON object containing its
metadata, source subtitle, generated subtitle and change log. Cloud Run requires
no database server and does not rely on its container filesystem for persistence.

Generation preconditions make writes atomic and reject concurrent changes with
HTTP 409. A transform cannot resurrect a deleted job. Job IDs are random UUIDs;
knowing an ID permits access, as in the local application. There is no user login.

The API denies access 24 hours after creation. Configure bucket lifecycle deletion
with `daysSinceCustomTime: 1`; each object retains the original job creation time
as its custom time even after a transform. Physical deletion is asynchronous.
Disable object versioning and soft delete for this temporary-upload bucket.

Cloud Run uses one CPU, 512 MiB memory, zero minimum instances, one maximum
instance and one concurrent request. It scales to zero when idle. Runtime
credentials have object access on the Sublynt bucket only. The public API allows
CORS from the two Sublynt Firebase origins and returns `Cache-Control: no-store`.

## Cost safeguards

Production enables the same processing limits as InvoiceParse: five POST requests
per client address and 30 globally per 600-second window, with one processing
request at a time. GET and DELETE requests have separate limits of 60 per client
and 300 globally per window, so reaching the processing limit still permits
preview, download and deletion. Rejections return 429 and `Retry-After`; a busy
processor returns 503. The frontend displays the API error message.

Counters are in memory and reset on container restart, as in InvoiceParse. Client
limits use the server-provided peer address and do not trust arbitrary forwarded
headers; users behind the same proxy may share a limit. The global limit remains
independent of client identity. These safeguards reduce usage but are not a hard
monetary ceiling: rejected traffic, storage and network usage can still cost money.

The shared billing account's existing CA$20 monthly alert already covers this
backend. It is alerts-only and does not shut down resources. It was not changed.
No project-wide Cloud Run spending stop was added, because that would also affect
InvoiceParse and any other Cloud Run services in the shared project.

## Authentication and deployment

The `sublynt` OIDC provider lives inside `nuvorima-github`, accepts this repository's
`main` push workflow only, and leaves the existing shared `github` provider untouched.
There are no service-account keys. Firebase Hosting permissions are project-wide;
the Hosting manifest explicitly targets Sublynt, but that is not an IAM boundary.

The deployment account needs Hosting Admin and Service Usage Consumer in the
Hosting project, Cloud Run Developer on the Sublynt service and Service Usage
Consumer in the backend project, Artifact Registry Writer on the Sublynt repository, and Service Account
User on the Sublynt runtime account. Initial public invocation is configured by
the owner; CI updates the existing service without managing its IAM policy.

The workflow deploys the backend before the frontend; changes must preserve API
compatibility during that interval. Roll back backend revisions and Hosting
releases separately when needed. Container images are tagged with the commit SHA.

## Verification

Run backend lint, format, type and test checks plus frontend lint, tests and the
Hosting build. Cloud storage tests cover fresh service instances, concurrent
transforms, deletion races and expiry. After deploying, verify upload, transform,
preview, download and delete through the live browser, plus CORS and persistence
across separate API requests. A successful Hosting upload alone is insufficient.
