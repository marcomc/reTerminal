# SenseCraft HMI API Field Notes

**Research snapshot:** 2026-09-29. The live site may change independently of these notes. Product documentation recently calls the platform SenseCraft Seeedash; the web path and API host still use the SenseCraft HMI name.

## Contents

- [Evidence and limits](#evidence-and-limits)
- [Hosts and request behavior](#hosts-and-request-behavior)
- [Authentication](#authentication)
- [Response envelope and errors](#response-envelope-and-errors)
- [Template data model](#template-data-model)
- [Template operations](#template-operations)
- [Discovered endpoint inventory](#discovered-endpoint-inventory)
- [Read-only probes](#read-only-probes)
- [Open questions for implementation](#open-questions-for-implementation)
- [Sources](#sources)

## Evidence and limits

|Label|Meaning|
|---|---|
|**Official docs**|First-party Seeed documentation or repository. It documents user workflows, not a REST API contract.|
|**Client-observed**|Current JavaScript bundle contains the route, method, query construction, or payload fields. This is evidence of the website's client contract, not a promise of API stability.|
|**Live-probed**|A read-only HTTP request was made to the live API host on the snapshot date.|
|**Unverified**|The client exposes an endpoint but this research did not establish its complete schema, permission behavior, or response.|

The official documentation repository is public and describes the canvas editor, AI generation, community templates, data integrations, device pairing, and deployment. It does not publish OpenAPI/Swagger or a supported third-party programmatic API contract [1]. The implementation source is the deployed SPA bundle loaded by `https://sensecraft.seeed.cc/hmi`: `/hmi/assets/index-8bAktItP.js` (observed 2026-09-29; bundle size about 8.98 MB).

The inventory below records the routes discovered in that bundle. Some dynamic URLs appear in more than one request construction path. It is intended as a discovery map, not an assertion that every route is safe or useful as an MCP tool.

## Hosts and request behavior

|Host|Use observed in app|Evidence|
|---|---|---|
|`https://sensecraft-hmi-api.seeed.cc`|HMI REST API (`Dn` constant)|Client-observed; live-probed|
|`https://sensecraft-auth.seeed.cc/authapi`|SenseCraft account refresh endpoint (`/api/v1/auth/refreshToken`)|Client-observed|
|`https://sensecraft-data-api.seeed.cc`|Data integration service|Client-observed; endpoint catalogue not fully mapped here|
|`https://sensecap.seeed.cc`|SenseCAP service|Client-observed|
|`https://sensecraft.seeed.cc/hmi`|SPA origin|Client-observed|

The SPA uses a shared HTTP client (`kr`) for the HMI API. JSON requests use Axios-style `{url, method, data, headers}` arguments; multipart upload explicitly sets `Content-Type: multipart/form-data`. The precise default headers, timeout, retry policy, and response interceptor behavior should be rechecked against the bundle at implementation time. The client contains a refresh URL constructed as `https://sensecraft-auth.seeed.cc/authapi/api/v1/auth/refreshToken?refreshToken=...` and sends it with `credentials: "include"`. Do not assume a refresh token alone is sufficient outside the browser; the endpoint also relies on browser cookies.

## Authentication

### What was verified

- `GET /api/v2/auth/profile` without credentials returned HTTP 200 with JSON `{"code":401,"message":"User unauthorized"}` (**live-probed**).
- `GET /api/v2/user/template?page=1&page_size=1` without credentials returned the same application-level unauthorized response (**live-probed**).
- A browser-side login call exists at `POST /api/v2/auth/login_sensecraft` and the SPA supplies an `Authorization` header whose value is a token held in its auth store (**client-observed**).
- The store has `token`, `refreshToken`, `sensecraftApiKey`, and `isAuthenticated` properties. `sensecraftApiKey` is an app setting/state field; the bundle evidence does **not** establish it as authentication for HMI account routes.

### Integration implication

Treat account access as bearer-token authentication only after confirming the exact header value format and token lifecycle with a valid account session. The bundle passes the token as the raw `Authorization` header value for `login_sensecraft`; do not silently assume it is either raw JWT or `Bearer <JWT>` for every endpoint. In particular, an API key supplied for a separate data provider must not be mistaken for a SenseCraft account credential.

The MCP should initially accept a short-lived access token via a protected environment/configuration provider and fail closed on 401. Never request, log, echo, persist in tool output, or commit passwords, refresh tokens, or API keys. Do not implement browser login, account registration, or token harvesting as part of the MCP. Add refresh support only after Seeed documents the supported non-browser flow and its cookie requirements.

## Response envelope and errors

Successful probes returned JSON shaped like:

```json
{
  "code": 200,
  "result": {"...": "..."},
  "message": "success"
}
```

List responses observed include `result.total`, `result.page`, `result.page_size`, and a resource array (for example `templates`). Unauthorized responses use HTTP 200 with application `code: 401`; clients must inspect both HTTP status and the JSON `code`. Other application codes and error mappings remain unverified. The MCP should return a concise, structured tool error for transport failures, HTTP errors, invalid JSON, and non-200 application codes. Redact authorization material and avoid dumping raw response bodies when they may contain user data.

## Template data model

The public template list/detail response showed these fields on 2026-09-29:

|Field|Observed shape|Notes|
|---|---|---|
|`id`|integer|Public template ID.|
|`author`|object with `id`, `name`, `avatar`, `count`|Public author metadata.|
|`page_type`|string, e.g. `layout`|Image pages also appear in UI; allowed values need validation.|
|`name`|string|Template name.|
|`thumbnail`|URL string|OSS-hosted preview.|
|`images`|array of URL strings|Media associated with template.|
|`device_models`|array of strings, e.g. `reterminal_e1004`|Device compatibility.|
|`resolutions`|array of strings, e.g. `1200x1600`|Display dimensions.|
|`dithers`|array of integers|Dither modes; mapping is not fully documented here.|
|`api_data`|JSON-encoded string|Data-platform inclusion/sanitization metadata.|
|`tags`|array of strings|Search/category metadata.|
|`license_url`|string|May be empty.|
|`commercial`|boolean|Public listing field.|
|`description`|string|User-facing description.|

Full detail records may include other fields (notably `data` and audit/status metadata); do not use the list projection as a complete create/update schema.

### Create payload proven by client source

When a user publishes a template from a workspace page, the SPA calls `POST /api/v2/user/template` with this shape (**client-observed**):

```json
{
  "name": "...",
  "description": "...",
  "thumbnail": "...",
  "images": ["..."],
  "page_type": "layout",
  "device_models": ["reterminal_e1001"],
  "resolutions": ["800x480"],
  "dithers": [0],
  "category_ids": [1],
  "tags": ["..."],
  "data": "...",
  "api_data": "...",
  "record_page_id": 123
}
```

The UI takes template content from a workspace record. For layout pages it parses and normalizes the page data, then serializes it to `data`; `api_data` is serialized separately. It sends the category as an array with zero or one integer. It passes the current page type, ID, template deployment device models, display resolution, and dither mode. Missing `data` yields a placeholder `{"platforms":{}}` in one branch. Avoid constructing arbitrary `data` until the layout schema has been learned from real, public template detail responses and validated by a successful test save.

The client does not reveal whether a create is private or community-visible by default, or whether publishing triggers moderation. Official docs describe community templates and adding AI-generated results to a workspace, but do not specify create visibility (see [1] and [2]). The MCP's first create operation must make visibility explicit only if the API schema supports it; otherwise report the server's returned state and verify by reading the user's templates.

## Template operations

|Operation|Request|Observed inputs / result|Risk|
|---|---|---|---|
|Browse featured|`GET /api/v2/template/featured`|`page`, `page_size`, `feature_type`, `device_model`, `keyword`, `sort`, `order`; returns `templates` page|Read-only|
|Browse marketplace|`GET /api/v2/template/list`|`page`, `page_size`, `keyword`, `device_model`, `resolution`, `tag`, `author_id`, repeated `category_ids`, `sort_by`, `sort_order`; returns `templates` page|Read-only|
|Categories|`GET /api/v2/template/category`|Returns `categories` with `id`, `name`, optional description and sort|Read-only|
|Detail|`GET /api/v2/template/detail/{id}`|Public template detail|Read-only|
|Related|`GET /api/v2/template/related`|Query construction includes template ID and `limit` (exact parameter names should be checked in current bundle)|Read-only|
|My templates|`GET /api/v2/user/template`|`page`, `page_size`, `keyword`, `device_model`, `resolution`, `tag`, `sort_by`, `sort_order`|Account read|
|Liked templates|`GET /api/v2/user/template/likes`|Similar page/search filters; account read|Account read|
|Create/publish|`POST /api/v2/user/template`|Payload in prior section; response ID consumed by UI|Persistent write; explicit user intent required|
|Update|`PUT /api/v2/user/template`|JSON data object; UI wrapper does not expose schema|Persistent write; require explicit target and diff|
|Delete|`DELETE /api/v2/user/template`|Body `{ "id": <id> }`|Destructive; require explicit confirmation|
|Apply to workspace|`POST /api/v2/user/template/{id}/apply`|Body construction needs current bundle/API verification|Creates/changes workspace page; require explicit intent|
|Like/unlike|`POST /api/v2/user/template/like/{id}`|Mutation|Account mutation; leave out of initial MCP|

The SPA also has follow/unfollow user routes. They are not needed for template authoring and should not be exposed by an initial MCP.

## Discovered endpoint inventory

These route/method pairs are **client-observed**. `{...}` means a path parameter or query assembled by the app. Query/body schemas not called out above remain unverified. `/api/v1` and `/api/v2` coexist.

### Auth, account, and settings

|Method|Path|Notes|
|---|---|---|
|`POST`|`/api/v2/auth/login_sensecraft`|App supplies token in `Authorization`; request body `{}`.|
|`GET`|`/api/v2/auth/profile`|Profile; unauthorized probe documented above.|
|`PUT`|`/api/v2/auth/profile`|Profile update; body passed through.|
|`GET`|`/api/v2/user/settings`|Settings; failure is swallowed by a non-fatal settings loader.|
|`PUT`|`/api/v2/user/settings`|Settings update; body passed through.|
|`DELETE`|`/api/v2/user/account`|Body `{"confirm":true}`; destructive account deletion. Never expose in MCP.|
|`GET`|`/api/v2/user/public/{id}`|Public profile lookup.|
|`POST`|`/api/v2/public/avatar`|Multipart/public avatar route; exact payload unclear.|

### AI generation and uploads

|Method|Path|Notes|
|---|---|---|
|`POST`|`/api/v1/user/ai/layout`|Body `{input, conversation_id}`; 90-second client timeout.|
|`GET`|`/api/v1/user/ai/layout/conversations`|List conversations.|
|`GET`|`/api/v1/user/ai/layout/conversations/{id}`|Read one conversation.|
|`DELETE`|`/api/v1/user/ai/layout/conversations/{id}`|Delete conversation.|
|`POST`|`/api/v1/user/ai/image`|Body `{input}`; 60-second timeout.|
|`GET`|`/api/v1/user/ai/image/history`|Image generation history.|
|`GET`|`/api/v1/user/ai/usage`|Usage quota.|
|`POST`|`/api/v1/oss/file/upload`|Multipart upload.|

AI generation may consume account quota and create stored assets; expose only as an explicitly invoked, cost-aware tool after the owner requests that capability.

### Templates and social features

|Method|Path|Notes|
|---|---|---|
|`GET`|`/api/v2/template/featured`|Featured query; see template operations.|
|`GET`|`/api/v2/template/list`|Community marketplace query.|
|`GET`|`/api/v2/template/detail/{id}`|Public detail.|
|`GET`|`/api/v2/template/category`|Category list.|
|`GET`|`/api/v2/template/related`|Related templates.|
|`GET`|`/api/v2/user/template`|My templates.|
|`POST`|`/api/v2/user/template`|Create/publish template.|
|`PUT`|`/api/v2/user/template`|Update template.|
|`DELETE`|`/api/v2/user/template`|Delete template; body includes ID.|
|`GET`|`/api/v2/user/template/likes`|Liked templates.|
|`POST`|`/api/v2/user/template/like/{id}`|Like/unlike template.|
|`POST`|`/api/v2/user/template/{id}/apply`|Apply template to workspace.|
|`POST`|`/api/v2/user/follow/{id}`|Follow user.|
|`DELETE`|`/api/v2/user/follow/{id}`|Unfollow user.|

### Workspace pages and playlists

|Method|Path|Notes|
|---|---|---|
|`GET`|`/api/v2/user/page`|Paginated/query-filtered workspace pages.|
|`POST`|`/api/v2/user/page`|Create page; body passed through from editor.|
|`PUT`|`/api/v2/user/page`|Update page; body passed through.|
|`DELETE`|`/api/v2/user/page`|Delete page; body passed through.|
|`DELETE`|`/api/v2/user/page/batch`|Body `{ids: [...]}`; destructive.|
|`GET`|`/api/v2/user/page/detail`|Query-string detail lookup.|
|`GET`|`/api/v2/user/page/deployed-devices`|Query-string filter for deployments.|
|`GET`|`/api/v2/user/playlist`|List playlists.|
|`POST`|`/api/v2/user/playlist`|Create playlist; body passed through.|
|`PUT`|`/api/v2/user/playlist`|Update playlist.|
|`DELETE`|`/api/v2/user/playlist`|Delete playlist.|
|`GET`|`/api/v2/user/playlist/pages`|List pages in playlist.|
|`POST`|`/api/v2/user/playlist/upsert_pages`|Add/update playlist membership.|
|`GET`|`/api/v2/user/device/playlist`|Playlist view scoped to device.|

### Devices, deployment, data, sharing, and calendar

|Method|Path|Notes|
|---|---|---|
|`GET`|`/api/v2/user/device/list`|Account devices.|
|`GET`|`/api/v2/user/device/detail/{id}`|Device detail.|
|`POST`|`/api/v2/user/device/config`|Device configuration mutation.|
|`POST`|`/api/v2/user/device/deploy`|Deploy content to device; external/device-visible side effect.|
|`POST`|`/api/v1/user/bind/{id}`|Bind device; body `{device_name}`.|
|`PUT`|`/api/v1/user/device/{id}`|Rename; body `{device_name}`.|
|`GET`|`/api/v1/user/device/{id}`|Device info.|
|`GET`|`/api/v1/user/device/status/{id}`|Device status.|
|`POST`|`/api/v1/user/device/{id}/unbind`|Unbind device.|
|`GET`|`/api/v1/user/device/iot_data/{id}`|IoT data query; route also appears with another dynamic argument.|
|`GET`|`/api/v1/user/device/third_data/{id}`|Third-party data; one call supplies `api-key` header.|
|`POST`|`/api/v1/user/device/push_data`|Push data; body unclear.|
|`POST`|`/api/v2/share/{id}/generate`|Generate share link; body passed through.|
|`GET`|`/api/v2/share/detail/{id}`|Read share details.|
|`POST`|`/api/v2/share/{id}/sync`|Sync share; body may be `{}`.|
|`DELETE`|`/api/v2/share/{id}/cancel`|Cancel/delete share link.|
|`GET`|`/api/v2/calendar/authorize`|Query `redirect_uri`; starts OAuth flow.|
|`GET`|`/api/v2/calendar/list`|Query-built calendar list.|
|`GET`|`/api/v2/calendar/events`|Query-built event listing.|
|`DELETE`|`/api/v2/calendar/revoke`|Query `session_id`; revokes integration.|

These routes carry higher operational risk or involve external services. They are outside the initial template MCP scope. Do not implement deployment, device binding, account removal, or integration revocation as incidental features.

## Read-only probes

Performed on 2026-09-29 from this workspace using Python's standard-library `urllib`, no browser cookies, no Authorization header, and no API key:

|Request|Result|
|---|---|
|`GET https://sensecraft-hmi-api.seeed.cc/api/v2/template/category`|`code: 200`; 9 categories returned.|
|`GET .../api/v2/template/featured?page=1&page_size=1`|`code: 200`; page envelope and template record returned (`total: 141` at probe time).|
|`GET .../api/v2/template/list?page=1&page_size=1`|`code: 200`; page envelope and template record returned (`total: 538` at probe time).|
|`GET .../api/v2/template/detail/9`|`code: 200`; public template detail returned.|
|`GET .../api/v2/auth/profile`|application `code: 401`, `User unauthorized`.|
|`GET .../api/v2/user/template?page=1&page_size=1`|application `code: 401`, `User unauthorized`.|

Counts and sample records are time-dependent. Probes were reads only; no login, create, update, delete, AI generation, or device operation was attempted.

## Open questions for implementation

1. Obtain a supported, non-browser authentication method from Seeed, including whether the account API accepts a documented API key, OAuth token, or only browser-issued access tokens.
2. Establish the exact `Authorization` format, token expiry, refresh flow, and whether cookies are mandatory.
3. Capture a real, owner-authorized create/update request and response with secrets removed. Confirm mandatory fields and server defaults.
4. Determine whether template create is private, public, moderated, or offers a visibility/audit field. Confirm safe delete/update semantics.
5. Inspect public detail records for representative `layout` and image pages; document `data`, `api_data`, dither values, and image upload/ownership rules.
6. Verify query parameter names and pagination bounds against endpoint behavior; names in the route inventory follow the current client bundle.
7. Ask Seeed whether these routes are supported for third-party integrations, their rate limits, and their compatibility/versioning policy.

## Sources

1. Seeed Solution, official SenseCraft HMI documentation repository and overview: <https://github.com/Seeed-Solution/sensecraft-hmi-docs> and <https://github.com/Seeed-Solution/sensecraft-hmi-docs/blob/main/src/content/docs/en/overview/index.md>
2. Seeed Solution, official AI generation guide: <https://github.com/Seeed-Solution/sensecraft-hmi-docs/blob/main/src/content/docs/en/guides/ai_gen/index.md>
3. Seeed Solution, official workspace guide: <https://github.com/Seeed-Solution/sensecraft-hmi-docs/blob/main/src/content/docs/en/guides/workspace/index.md>
4. Live SPA entry point: <https://sensecraft.seeed.cc/hmi>; deployed bundle observed at `https://sensecraft.seeed.cc/hmi/assets/index-8bAktItP.js`.
5. Public API samples: <https://sensecraft-hmi-api.seeed.cc/api/v2/template/category>, `.../api/v2/template/featured?page=1&page_size=1`, `.../api/v2/template/list?page=1&page_size=1`, and `.../api/v2/template/detail/9` (live-probed 2026-09-29).
