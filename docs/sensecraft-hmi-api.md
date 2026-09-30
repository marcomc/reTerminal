# SenseCraft HMI API Field Notes

**Research snapshot:** 2026-09-30. The live site may change independently of these notes. Product documentation recently calls the platform SenseCraft Seeedash; the web path and API host still use the SenseCraft HMI name.

## Contents

- [Evidence and limits](#evidence-and-limits)
- [Hosts and request behavior](#hosts-and-request-behavior)
- [Authentication](#authentication)
- [Response envelope and errors](#response-envelope-and-errors)
- [Template data model](#template-data-model)
- [Template operations](#template-operations)
- [Google Calendar integration](#google-calendar-integration)
- [Discovered endpoint inventory](#discovered-endpoint-inventory)
- [Live probes and authorized writes](#live-probes-and-authorized-writes)
- [Device battery and solar fields](#device-battery-and-solar-fields-2026-09-30-evidence)
- [Agenda feasibility evidence](#agenda-feasibility-evidence-2026-09-30)
- [Open questions for implementation](#open-questions-for-implementation)
- [Sources](#sources)

## Evidence and limits

|Label|Meaning|
|---|---|
|**Official docs**|First-party Seeed documentation or repository. It documents user workflows, not a REST API contract.|
|**Client-observed**|Current JavaScript bundle contains the route, method, query construction, or payload fields. This is evidence of the website's client contract, not a promise of API stability.|
|**Live-probed**|A read-only HTTP request was made to the live API host on the snapshot date.|
|**Unverified**|The client exposes an endpoint but this research did not establish its complete schema, permission behavior, or response.|

The official documentation repository is public and describes the canvas editor, AI generation, community templates, data integrations, device pairing, and deployment. It does not publish OpenAPI/Swagger or a supported third-party programmatic API contract [1]. The initial implementation source was `/hmi/assets/index-8bAktItP.js` (observed 2026-09-29; SHA-256 `bdc8770cec79ba360576defbeda28bb8229b3cbeba9c8b657959994f5bbbadfc`). The later 2026-09-30 feasibility check rediscovered `/hmi/assets/index-BfhBsgWz.js` from the HTML entry point; its current evidence is recorded below. Earlier endpoint observations are historical unless rechecked against that bundle.

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
- The store has `token`, `refreshToken`, `sensecraftApiKey`, and `isAuthenticated` properties. Although the field name alone did not establish authentication support, a live request verified that an account API key is accepted by account routes using the `api-key` header.
- On 2026-09-29, an account API key authenticated `GET /api/v2/auth/profile` when sent as `api-key: <key>` (**live-probed**; no profile details were retained).
- The same key was rejected as either raw `Authorization: <key>` or `Authorization: Bearer <key>`. Use the `api-key` header for this tested credential.

### Integration implication

Account access was verified with an API key in the `api-key` request header. Raw and Bearer `Authorization` formats failed in the same profile probe. The SPA also has a token-based `login_sensecraft` call; that is a separate client path. The official docs still do not publish this REST authentication contract, so do not infer token lifecycle, broad permissions, or long-term stability from the observed request alone.

The MCP should accept the account API key from a protected environment/configuration provider, send it in the `api-key` header, and fail closed on 401. Never request, log, echo, persist in tool output, or commit passwords, refresh tokens, or API keys. Do not implement browser login, account registration, or token harvesting as part of the MCP. Add refresh support only after Seeed documents the supported non-browser flow and its cookie requirements.

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

**Live write evidence, 2026-09-30:** page `PUT` can return application code `200`
without a `result` field. An authoring helper initially raised `KeyError` after
that successful write; fresh page readback established that all six configured
calendar records had persisted. Accept an absent mutation result, verify the
resource separately, and recover the remaining deployment step without repeating
the save or thumbnail upload merely because local response parsing failed.

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

On 2026-09-29, a live account create confirmed that `thumbnail` cannot be empty: the API returned application code `4304` with “Template thumbnail cannot be empty.” The create succeeded after uploading an original PNG through `POST /api/v1/oss/file/upload` as multipart fields `file` and `type=image`, then passing `result.file_url` as `thumbnail`. The successful `POST /api/v2/user/template` response had application code `200` and `result.id`; this response did not include audit status. This is a confirmed account write, not proof of publication approval or public visibility. The created item was an E1002 layout at `800x480`, using `data` and `api_data` as JSON-encoded strings and an existing workspace `record_page_id`.

The create response alone does not reveal visibility or audit status. A readback of the created template on 2026-09-29 found `audit_status: 0` in the authenticated account list; public detail returned `code: 4301` (“Template not found”). The deployed SPA defines audit states `0=PENDING`, `1=APPROVED`, `2=REJECTED`, `3=REMOVED` (**client-observed**). This is consistent with moderation before public listing, but the exact transition and publication policy remain unverified. An MCP must report the observed audit state and must not claim community publication until public detail/list confirms it.

The current SPA's template editor sends `PUT /api/v2/user/template` with `id`, `name`, `description`, `thumbnail`, `images`, `device_models`, `resolutions`, `dithers`, `category_ids`, `tags`, `api_data`, and `data`; `data` and `api_data` are JSON-encoded strings, and `category_ids` is an integer array. An authorized live update using this shape returned application code `200`. Readback confirmed the changed layout while its audit state remained `0`; public detail still returned `4301`. This verifies the editor's observed update shape and one account update, not every layout schema or publication approval.

The account template-list response represents `category_ids` as objects with
`id`, `name`, and `sort`, but the editor reduces the selected category to an
integer array before `PUT`. Sending the readback objects unchanged produced
application code `400` (“request parameter error”). Normalizing them to integer
IDs allowed an authorized description-only update to return code `200`; the
description read back correctly and audit status remained `0`. An MCP that
round-trips template records must normalize this field for update requests.

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
|Update|`PUT /api/v2/user/template`|Editor payload fields and JSON-string types are described above; one live update succeeded|Persistent write; require explicit target and diff|
|Delete|`DELETE /api/v2/user/template`|Body `{ "id": <id> }`|Destructive; require explicit confirmation|
|Apply count|`POST /api/v2/user/template/{id}/apply`|The current UI calls this after creating a workspace page and consumes the returned `apply_count`; this endpoint alone is not shown creating the page|Account mutation; do not treat it as the complete apply workflow|
|Like/unlike|`POST /api/v2/user/template/like/{id}`|Mutation|Account mutation; leave out of initial MCP|

## Google Calendar integration

The first-party client implements Google Calendar authorization and configuration in the layout editor (**client-observed**, 2026-09-29). The editor calls `GET /api/v2/calendar/authorize?redirect_uri=...`; on callback it reads `session_id`, stores it in the local integration config, lists calendars, selects the primary calendar by default when available, and lets the user choose calendar IDs before loading data. The visible editor flow says: authorize with Google, choose calendars, then click **Load Data**. The calendar selector is searchable and supports choosing calendar IDs from the connected Google account (**live UI observed**).

The client calls `GET /api/v2/calendar/list?session_id=...`, then `GET /api/v2/calendar/events`. A live probe found that the calendar-list request returns application code `401` without the account `api-key` header and code `200` when that header is present. The response places records in `result.calendarList`; observed record fields include `id`, `summary`, `accessRole`, `description`, `hidden`, `primary`, `selected`, and `timeZone`. The list response did not include calendar colors. Never retain account-specific records in project documentation.

Event queries use `session_id`, `type`, `calendar_ids` (comma-separated), and `time_zone`; date-range mode also supplies millisecond `start` and `end`. Observed event types include `1` for today's events, `2` for a week/day schedule, `3` for month events, and `4` for a specific date range. Event results are read from `result.events`. A live event record contained `id`, `calendarId`, `summary`, `description`, `location`, `start`, `end`, and `status`, but no calendar display name or color. A further authenticated probe on 2026-09-30 returned the same event-field shape and no calendar-level summary, name, or color metadata. The editor turns the response into API-backed calendar, list, or schedule components. These parameter semantics are client-observed and should be rechecked against the live bundle before implementation.

The deployed list renderer supports per-field custom transforms. The SPA executes a `customFunction` with `value`, `formatDate`, and `Math`; the transform sees the current field value, not sibling fields or a calendar metadata lookup. A row's `secondaryText.fields[]` supports a per-field `style.color`, which can render a colored marker when a page has a mapping from `calendarId` to the installer's chosen calendars. This mapping is account-specific and must not be copied into a public template. Generic templates can receive `calendarId` from events, but the events API does not provide the calendar's display name or color for a reliable name/color join.

A live page readback on 2026-09-30 confirmed that a `secondaryText.fields[]` entry can use `dataKey: "calendarId"` and `dataTransform.type: "custom"` with `options.customFunction` to map a selected ID to a label such as `"XY ●"`; the field's `style.color` colors both the initials and filled dot. A private page can hold an ID-to-label transform for its installer's selected calendars. Never copy that mapping or its IDs into a reusable template. The template readback instead has three generic marker fields that derive labels from the event's calendar ID and use fixed color styles. Those ID-derived labels distinguish sources but are not guaranteed to match calendar display names; name initials need per-installer calendar-list metadata and a mapping step.

A live synthetic render confirmed that the E1002 preview places the event title on one line and the time with its two-letter label and colored dot on the secondary line. The template's generic transforms provide a portable fallback; they do not perform a calendar-name lookup. That native-list configuration does not join event records to calendar-list summaries. The later uploaded-HTML path uses an explicit private mapping.

For HTML card previews, the SPA posts {url, resolution} to POST /render/preview (client-observed). A separate live-probed layout request with {layout, resolution, img_format, dither} also returned image/png. On 2026-09-30, a preview-only clone using listConfig.dataSource type direct with synthetic rows rendered event titles, times, two-character labels, and three distinct style colors. Keep synthetic rows out of saved templates; the saved template data source remains API-backed. The current SPA enum maps dither 0 to black-and-white and dither 3 to E6 full color; the E1002 editor profile defaults to E6.

The current client bundle exposes a template-import boundary (**client-observed**, bundle hash above). Before creating a page from a marketplace template, the UI rewrites a Google Calendar data URL's `session_id` from the installer's locally stored Google Calendar session. If the URL contains a sanitized/missing session placeholder and the installer has no stored session, the UI reports Google Calendar as missing and stops before page creation. This path does not launch OAuth or the calendar picker and does not rewrite `calendar_ids`. Installers must connect Google Calendar and configure their selected calendar IDs in the editor; do not claim that marketplace installation performs consent and selection automatically.

The UI's full apply sequence first rebuilds the template layout and creates a workspace page through the page-creation path; only after that succeeds does it call `POST /api/v2/user/template/{id}/apply` to refresh template apply statistics. The sequence is client-observed, not a tested server contract for third-party clients. A portable template must not contain the owner's session, calendar IDs, or name-to-ID marker mapping. The event API exposes only `calendarId`, so generic ID-derived initials and color buckets are possible; true calendar-name initials require per-installer metadata and a mapping step that the renderer does not perform automatically.

Public layout details observed for E1002 include `calendarConfig.calendarType: "google-calendar-month"`, an API-backed `tableConfig.dataSource` pointing to `/api/v2/calendar/events`, and `api_data.platforms.googleCalendar: {"included":true,"sanitized":true}`. A public template's calendar URL displayed a redacted `session_id`; never copy that value. The client-side import behavior above is not evidence that the server rewrites a template or prompts for OAuth. Require a separate owner-authorized OAuth/configuration step and verify calendar IDs before relying on the source.

Calendar authorization and revocation access the user's Google account. Keep these routes out of an initial general-purpose MCP server unless an explicitly scoped OAuth flow is designed and reviewed. Never log session IDs, event payloads, calendar IDs, or OAuth callback URLs.

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
|`GET`|`/api/v2/user/page/detail?page_id={id}`|Workspace-page detail; page_id is required by the client. Using id returned application code 400 in a live probe.|
|`GET`|`/api/v2/user/page/deployed-devices?page_id={id}`|`page_id` required; optional `type`. Returns `{page_id, devices}` with page-to-device playlist assignments; it does not report physical screen state.|
|`GET`|`/api/v2/user/playlist`|List playlists.|
|`POST`|`/api/v2/user/playlist`|Create playlist; body passed through.|
|`PUT`|`/api/v2/user/playlist`|Update playlist.|
|`DELETE`|`/api/v2/user/playlist`|Delete playlist.|
|`GET`|`/api/v2/user/playlist/pages`|List pages in playlist.|
|`POST`|`/api/v2/user/playlist/upsert_pages`|Add/update playlist membership.|
|`GET`|`/api/v2/user/device/playlist`|Playlist view scoped to device.|

#### My Designs, My Photos, and My Playlist

The account UI's **My Designs** and **My Photos** are both backed by
`GET /api/v2/user/page` (**live-probed 2026-09-29**). The client builds query
parameters `page`, `page_size`, `types` (comma-separated when multiple types
are requested), and `resolution`. Observed page `type` values are `layout`
for designs and `img` for photos. The photo filter is `types=img`;
`types=image` and `types=photo` returned no records in the probe. Responses
include a `total` and page records with fields such as `id`, `name`, `type`,
`resolution`, and `created_at`. Do not confuse these workspace pages with
community templates; they are separate API collections.

**My Playlist** is backed by `GET /api/v2/user/playlist` with `page` and
`page_size` and optional `mac_address` (**client-observed**; account list
live-probed). Fetching pages within one playlist uses
`GET /api/v2/user/playlist/pages?playlist_id={id}`. Listing membership is
read-only; adding or changing membership uses a separate mutation route.

For a device-assigned playlist, the client reads
`GET /api/v2/user/device/playlist?mac_address=...`. A live response contained
page entries with `kind`, `sort`, and `source_page_id`; snapshot entries use
`kind: "snapshot"` and can have an entry `id` different from their source
page ID. Match a source page by `source_page_id` when checking membership.
The observed upsert body is `{playlist_id, pages:[{id, sort, kind?}]}`;
preserve `kind: "snapshot"` for existing snapshots and omit `kind` for a
normal workspace page.

The deployed client bundle clarifies item normalization (**client-observed,
2026-09-30**): a playlist entry is treated as a snapshot when
`kind === "snapshot"` or `source_page_id` is present; serialization preserves
the snapshot entry's own `id` and `kind`, while a workspace page is sent as
`{id: page.id, sort}`. Reorder and removal flows send the complete intended
`pages` array to `upsert_pages`. A live probe attempting to replace an existing
snapshot with its workspace `source_page_id` returned code `200` but did not
produce the expected normal-page entry on readback. Removing that snapshot
worked, but the subsequent add did not satisfy the normal-page postcondition;
the original playlist was restored. Do not infer replacement semantics from a
successful response alone; read back playlist membership before proceeding.

### Devices, deployment, data, sharing, and calendar

|Method|Path|Notes|
|---|---|---|
|`GET`|`/api/v2/user/device/list`|Account devices; live response result is an array with fields including online_status and current_app.|
|`GET`|`/api/v2/user/device/detail/{id}`|Device detail.|
|`POST`|`/api/v2/user/device/config`|Device configuration mutation.|
|`POST`|`/api/v2/user/device/deploy`|Deploy content to device; SPA sends `mode` with either `playlist_id` or `page_ids`, plus `mac_addresses`; external/device-visible side effect.|
|`POST`|`/api/v1/user/bind/{id}`|Bind device; body `{device_name}`.|
|`PUT`|`/api/v1/user/device/{id}`|Rename; body `{device_name}`.|
|`GET`|`/api/v1/user/device/{id}`|Device info.|
|`GET`|`/api/v1/user/device/status/{id}`|Device status.|
|`POST`|`/api/v1/user/device/{id}/unbind`|Unbind device.|
|`GET`|`/api/v1/user/device/iot_data/{id}`|Device telemetry; numeric account device ID and `api-key` header live-verified. Battery is `result.battery.level`; charging is `result.battery.charging`.|
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
|`POST`|`/render/preview`|HTML preview uses url and resolution; a live layout probe also accepted layout, resolution, image format, and dither and returned a rendered image blob.|
|`POST`|`/api/v1/oss/file/upload`|Multipart fields `file` and `type`; template publishing uses the returned `file_url` for a required thumbnail.|

These routes carry higher operational risk or involve external services. They are outside the initial template MCP scope. Do not implement deployment, device binding, account removal, or integration revocation as incidental features.

The observed playlist deployment request is `POST /api/v2/user/device/deploy`
with `{"mode":"refresh","playlist_id":...,"mac_addresses":[...]}`. The
current SPA also supports a direct page refresh with
`{"mode":"refresh","page_ids":[...],"mac_addresses":[...]}`; the
single-page form was both client-observed and live-probed on 2026-09-30. Both
authorized refresh calls returned application code `200`. The device stayed
online, but its `current_app` remained null after playlist and direct-page
refreshes, so API acceptance does not prove a completed physical screen update.

The deployed-devices read uses `page_id` and optionally `type`; a live
authenticated request returned `result: {page_id, devices}`. Device assignment
records include `device_name`, `mac_address`, `playlist_id`, `playlist_type`,
and `typed`. This confirms the service-side page/playlist association, not
device receipt or display refresh.

## Live probes and authorized writes

On 2026-09-30, an authorized template create/readback verified a sanitized live Google Calendar E1002 layout. The saved layout retained an API-backed calendar-events source and an OAuth-session placeholder, with no creator calendar IDs or timezone; readback confirmed dither 3 and three marker fields. Audit status remained pending, and public detail returned application code 4301, so public visibility was not established.

Initial public and read-only probes used Python standard-library urllib on 2026-09-29 without browser cookies or account credentials. Additional authenticated probes and explicitly authorized writes were performed on 2026-09-30 with the ignored local .env key in the api-key header; account data and credentials were not retained:

|Request|Result|
|---|---|
|`GET https://sensecraft-hmi-api.seeed.cc/api/v2/template/category`|`code: 200`; 9 categories returned.|
|`GET .../api/v2/template/featured?page=1&page_size=1`|`code: 200`; page envelope and template record returned (`total: 141` at probe time).|
|`GET .../api/v2/template/list?page=1&page_size=1`|`code: 200`; page envelope and template record returned (`total: 538` at probe time).|
|`GET .../api/v2/template/detail/9`|`code: 200`; public template detail returned.|
|`GET .../api/v2/auth/profile`|application `code: 401`, `User unauthorized`.|
|`GET .../api/v2/user/template?page=1&page_size=1`|application `code: 401`, `User unauthorized`.|
|Authenticated `GET .../api/v2/auth/profile` with `api-key` header|API `code: 200`. Raw and Bearer `Authorization` forms returned API `code: 401`. No profile fields were retained.|
|Authenticated `GET .../api/v2/user/page?page=1&page_size=100`|API `code: 200`; workspace pages returned. Account-specific names and IDs are omitted.|
|Authenticated `GET` .../api/v2/user/page/detail?page_id={id}`|API `code: 200`; using id instead returned application `code: 400`.|
|Authenticated page filters `types=layout` and `types=img`|Each returned matching records; `types=image` and `types=photo` returned none.|
|Authenticated `GET .../api/v2/user/playlist?page=1&page_size=100`|API `code: 200`; playlist records returned. Account-specific names and IDs are omitted.|
|Authenticated `GET` .../api/v2/user/device/list`|API `code: 200`; result was a direct array of device records. Values are omitted.|
|Authenticated `GET .../api/v2/user/page/deployed-devices?page_id={id}&type=layout`|API `code: 200`; result contained the requested page ID and device/playlist assignment records. Account values are omitted.|
|Authenticated `GET` .../api/v2/calendar/events`|API `code: 200`; event records include calendarId but no calendar-level name or color fields.|

Counts and sample records are time-dependent. Earlier probes were reads only. On 2026-09-29, an explicitly authorized template create and update succeeded after using a PNG thumbnail; update readback showed a today-only `800x480` layout, dither `3`, three per-field marker transforms, and audit status `0`. Public detail returned `code: 4301`, so community visibility was not established. No account identifiers, event titles, calendar IDs, or session values are retained here.

The same authorized session added the private page to the device-assigned
playlist while preserving its two existing snapshots. Readback found the new
entry by `source_page_id`; a refresh deploy returned application code
`200`, and the device remained online. An API render preview of the playlist
snapshot showed today's event rows with initials and color markers. The deploy
response and playlist readback do not prove that the physical display completed
its refresh. Credentials were read from the ignored local `.env` and used
only in the `api-key` header.

On 2026-09-30, an authorized update to the private calendar page returned application code 200; a page detail readback using page_id confirmed the updated per-calendar labels and three distinct colors. A subsequent refresh deploy returned code 200 and playlist readback retained the page. The device was online, but current_app was null, so physical screen delivery remains unverified.

A later read-only check fetched the device-playlist snapshot with
`GET /api/v2/user/page/detail?page_id={snapshot_entry_id}&kind=snapshot` and
the source workspace page with `page_id={source_page_id}`. Their `data`,
resolution, and dither matched; the snapshot still contained the API-backed
calendar events source and the three custom marker fields. A refresh deploy
returned code `200` and the device remained online, but `current_app` remained
null after a follow-up read. This confirms API acceptance and layout agreement,
not a physical display update.

The authenticated device page in the browser still showed a playlist-card
thumbnail dated 2026-09-29 after a successful 2026-09-30 refresh
(**browser-observed**). Treat that card image as potentially cached UI content,
not as a live screenshot of the E1002 display; no fresh physical-screen image
or device-side acknowledgement was available.

## Open questions for implementation

1. Obtain the official account-auth contract; the account API key header was live-tested, but its support and lifecycle are undocumented.
2. Establish token expiry, refresh flow, and whether cookies are mandatory.
3. Confirm server defaults for template creation, including thumbnail upload, audit status, and public visibility; one update payload is verified, but full update semantics remain unknown.
4. Determine whether template create is private, public, moderated, or offers a visibility/audit field. Confirm safe delete/update semantics.
5. Inspect public detail records for representative `layout` and image pages; document `data`, `api_data`, dither values, and image upload/ownership rules.
6. Verify query parameter names and pagination bounds against endpoint behavior; names in the route inventory follow the current client bundle.
7. Ask Seeed whether these routes are supported for third-party integrations, their rate limits, and their compatibility/versioning policy.

## Sources

1. Seeed Solution, official SenseCraft HMI documentation repository and overview: <https://github.com/Seeed-Solution/sensecraft-hmi-docs> and <https://github.com/Seeed-Solution/sensecraft-hmi-docs/blob/main/src/content/docs/en/overview/index.md>
2. Seeed Solution, official AI generation guide: <https://github.com/Seeed-Solution/sensecraft-hmi-docs/blob/main/src/content/docs/en/guides/ai_gen/index.md>
3. Seeed Solution, official workspace guide: <https://github.com/Seeed-Solution/sensecraft-hmi-docs/blob/main/src/content/docs/en/guides/workspace/index.md>
4. Live SPA entry point: <https://sensecraft.seeed.cc/hmi>; latest bundle examined on 2026-09-30: `https://sensecraft.seeed.cc/hmi/assets/index-BfhBsgWz.js`. Rediscover the path from HTML before relying on it.
5. Public API samples: <https://sensecraft-hmi-api.seeed.cc/api/v2/template/category>, `.../api/v2/template/featured?page=1&page_size=1`, `.../api/v2/template/list?page=1&page_size=1`, and `.../api/v2/template/detail/9` (live-probed 2026-09-29).

## Device battery and solar fields: 2026-09-30 evidence

- **Live HTTP probe:** `GET /api/v1/user/device/iot_data/{device_id}`
  with the account `api-key` returned application code `200`. Use the numeric
  device ID from the account device list. Supplying its MAC address instead
  returned application code `400` in this probe. The result includes
  `battery.level` (numeric percentage) and `battery.charging`. Values and
  device identifiers are deliberately omitted.
- **Live renderer probe:** a preview-only `type: "data"` element with
  `dataKey: "result.battery.level"`, the telemetry URL, and authenticated
  `dataHeaders` rendered the same numeric level returned by the device API.
  This proves a dynamic battery value can be placed in a layout; the battery
  icon, percentage suffix, and physical panel rendering still need their
  own layout checks. No page or template was changed by this probe.
- **Current web client:** the HTML entry point references
  `/hmi/assets/index-BfhBsgWz.js`, SHA256
  `c354c1e002de5a7a1248a2b7c55ccbee1b51482dd093fceba5ae9cddb89f6aef`.
  Its device field configuration uses the telemetry URL, account API key,
  and `result.battery.level`. Re-discover asset paths from HTML; the old
  bundle URL returned HTML rather than the expected JavaScript.
- **Client-observed solar fields:** the weather configuration uses
  `https://api.open-meteo.com/v1/forecast`, daily `sunrise` and `sunset`
  values, indexed data keys, and separate icon/time visibility options.
  This is evidence of editor bindings, not a live solar-data or accuracy
  verification. No native lunar phase binding was identified in the
  inspected client; this does not establish that no other API supports it.
- **Device delivery evidence:** a user report on 2026-09-30 confirmed that
  the prior agenda appeared on the physical display. Keep that report
  separate from API refresh acceptance and future layout delivery checks.

## Agenda feasibility evidence: 2026-09-30

These are results of the earlier feasibility probes, reconciled with the
agreed implementation scope. This documentation update did not rerun them.
The agenda requirements and fallbacks are canonical in the
[implementation brief](mcp-implementation-brief.md#agenda-layout-implementation-contract).

### Live HTTP results

|Probe|Established result|Limit|
|---|---|---|
|Authenticated calendar list|Application code `200`; records expose names and IDs but no color field|Resolve the installer's choices by ID; ambiguous or changed names require reconciliation.|
|Calendar events, `type=4`, millisecond `start`/`end`, `calendar_ids`, `time_zone`|Application code `200` for a three-day interval; returned calendar IDs belonged to the submitted selection|This probe did not establish ten-calendar capacity, exact boundary filtering, dynamic date rollover, sorting, or future-day grouping.|
|Device telemetry|Application code `200`; numeric battery level present|No fresh device delivery or battery icon proof.|
|Open-Meteo forecast with coordinates and timezone|HTTP `200`; four daily dates with `sunrise` and `sunset`|Does not prove a native city search menu, solar accuracy, or automatic light/dark selection.|

### Client observations

- The rediscovered bundle was 9,059,661 bytes, SHA-256
  `c354c1e002de5a7a1248a2b7c55ccbee1b51482dd093fceba5ae9cddb89f6aef`.
- One locale mapping lists `en`, `zh`, `ja`, `es`, `de`, `fr`, `nl`, and
  `pl`, with no `it`. This is not proof that every date transform rejects
  Italian. Inspect the rendered date output before selecting a workaround.
- The client includes `htmlConfig.htmlUrl`, SVG image handling, gradients,
  and field transforms executed with `value`, `formatDate`, and `Math`.
  Client support does not establish equivalent execution by the cloud
  renderer. An HTML URL is a remotely fetched source, not proof that inline
  HTML or arbitrary scripts execute inside the template.
- The inspected list conversion uses a common primary-text style. No
  confirmed contract provides independent per-row title fitting, a minimum
  adaptive font size, or right-pinned markers with automatic space recovery.
- No render-time contract for date-based background selection, sunset-based
  mode selection, or lunar phase was established. Absence of a confirmed
  contract is a research gap, not proof of impossibility.

### Preview acceptance is not visual verification

Seven synthetic `POST /render/preview` cases returned HTTP `200`, MIME
`image/png`, and PNG signatures: static SVG, custom-transform SVG,
array-to-SVG transform, list field styles, date locales, image opacity,
and an HTML URL. Their contents were inspected during the authorized implementation:
static SVG rendered; both unfetched SVG transforms were blank; list fields
shared a style and wrapped; the submitted date formats/locales were ignored;
image opacity values produced identical red patches; the HTML URL rendered
the remote page. These outcomes apply to those exact payloads.

The opacity case used an image `opacity` property; it did not test the newly
requested white/black overlay layer. The locale case submitted `it`, `en`,
and `fr`; it did not establish correct Italian weekday output. The static
SVG case included a gradient and internal opacity; neither its visibility
nor its suitability for a live API-backed agenda has been verified.

These were disposable previews. They did not save templates, update pages,
or deploy content. Inspect the images and prove behavior on successive
SenseCraft renders before promoting any case to a supported feature.

### Native composition probes: 2026-09-30

- **Rendered evidence:** a `rectangle` above a red image with `fill` set to
  `rgba(255,255,255,0)`, `rgba(255,255,255,0.5)`, and
  `rgba(255,255,255,1)` produced uncovered, dithered intermediate, and fully
  covered patches. This verifies the white veil independently of the ignored
  image `opacity` property. No intensity asset variants are needed for this path.
- **Rendered evidence:** API-backed `data` and `text` elements executed custom
  transforms. Binding `dataKey: "daily"` passed the complete Open-Meteo daily
  object; the transform rendered its array length and first sunrise. Thus a
  transform can receive an object or array when the data key selects one.
  Earlier field-only observations do not forbid an explicit whole-object binding.
- **Rendered evidence:** a `date` element with a custom transform using
  `new Date()` and a weekday array rendered an Italian weekday. The tested
  native date transform still showed the default US date despite its submitted
  format. A complete timezone-aware Italian header remains to be verified.
- **Rendered evidence:** four fetched custom-image cases (`data`/`image`, raw
  SVG/data URI) displayed only the supplied static `src` fallback. These
  payloads did not replace image content from the transform. Do not advertise
  dynamic SVG support on this evidence.
- **Client observation:** city search uses Photon (`photon.komoot.io/api/`),
  then Open-Meteo geocoding (`geocoding-api.open-meteo.com/v1/search`). Records
  provide coordinates; timezone may require a follow-up. This is a first-party
  city configuration capability, not a custom menu requirement.
- **Client and live rendered evidence:** the HTML upload widget calls the OSS
  upload endpoint with multipart `type=document`. A nonprivate, self-contained
  HTML probe uploaded successfully, and its native `htmlConfig.htmlUrl` element
  rendered the text written by its inline JavaScript, including render time.
  Native uploaded HTML is therefore a candidate for self-contained decoration
  logic without an external running application. Repeat rendering and async
  provider fetch behavior still require verification. Uploaded HTML is media;
  never place keys, Google sessions, event records, or account IDs in it.

These probes changed no workspace pages or templates. The document upload is
persistent media; save its returned URL privately and avoid duplicate uploads.

### Native HTML calendar execution: 2026-09-30

- **Live HTTP evidence:** the events endpoint returned application code `200`
  without an account `api-key` header when supplied with the already authorized
  Google `session_id`. The calendar-list endpoint's earlier key requirement is
  separate. Treat the Google session as a capability credential; do not call
  this anonymous access to public calendar data.
- **Rendered evidence:** an uploaded, account-independent HTML document parsed
  session/calendar/timezone parameters from its private URL fragment and fetched
  events with `credentials: "omit"`. The native HTML preview displayed code
  `200` and the expected event count. The uploaded document contained no key,
  session or account calendar records. The private layout URL is still sensitive.
- **Rendered evidence:** a second preview of the same uploaded script showed a
  later execution timestamp. Another uploaded document fetched and displayed
  Open-Meteo sunrise and sunset. This establishes repeated inline execution and
  provider fetching in the native HTML renderer, not device refresh delivery.
- **Rendered evidence:** `Intl.DateTimeFormat` with `it-IT` and an explicit
  timezone produced the correct Italian weekday and `DD-MM-YYYY` output.
- **Rendered evidence:** returning a Promise or a fetch Promise from a native
  field custom transform fell back to the original bound object. Do not depend
  on asynchronous native field transforms; async code works in uploaded HTML.
- **Rendered evidence:** native text `wrap`, `ellipsis`, and `autoFontSize`
  properties made no difference in the three submitted overflow previews.
  Browser text measurement and CSS masking inside native HTML are a separate
  implementation path that must be previewed before claiming title fitting.
- **Live HTTP evidence:** calendar `type=2` returned occurrences spanning six
  days before and six days after the probe date, including across a month
  boundary. This contradicts interpreting this result as only a calendar week.
  Some event starts predated the range, so client filtering is still required.
  Exact range semantics and behavior at a later date remain to be verified.

Portable HTML templates must strip the private session, calendar records and
battery authentication from the fragment (and any legacy native telemetry field). First-party import does not transfer a Google session
into `htmlConfig.htmlUrl`; document a separate installation configuration step.

### Saved native agenda and deployment: 2026-09-30

**Authorized account writes and inspected renderer output.** The implementation
uses a self-contained HTML media artifact with optional authenticated telemetry
read inside the document. Source mockups and monthly artwork remain unchanged; native CSS crops
mockup lettering out of decorative regions. Full-resolution originals were
preserved and referenced through uploaded media.

|Capability|Evidence|Practical limit|
|---|---|---|
|Italian header and clock|Inspected native previews use Italian weekday, `DD-MM-YYYY`, 24-hour clock and an explicit timezone|Interface translations cover Italian, English, French, German and Spanish; event titles are not translated.|
|Upcoming agenda|Live previews read selected calendars, retain ongoing events and omit ended timed events, group future dates and show a remaining-event count|Today plus three following civil dates; available space determines visible rows. Active multi-day all-day entries count today.|
|Long titles|Inspected long-title previews use measured browser text, bounded font reduction and a CSS tail mask|Implementation default: title 28 down to 25 px; timed starts remain 28 px.|
|Calendar identity|Inspected previews show plain colored initials and dot at the right; hiding both increases title width|Four modes are supported; E6 dithering constrains reproduced colors.|
|Decoration|Inspected Epiphany, monthly, manual-theme and dark previews show the native veil and selection logic|Integer intensity 0–100; no separate rendered-intensity asset set is required.|
|Night mode|A production preview before sunset was light; another at the returned sunset time was dark, with the same automatic-mode settings|Uses Open-Meteo local solar times on rendering; missing solar data falls back to the saved manual mode. This is renderer proof, not a physical panel observation.|
|Astronomy and battery|Inspected previews show daily solar times, a lunar icon/trend label and live battery percentage below the clock|Moon phase uses a mean synodic calculation and is indicative. The battery icon is an outline; the percentage is live.|
|Ten calendars|An authenticated ten-ID events request returned code `200`; every returned calendar ID belonged to the requested selection|Some selected calendars had no returned events; this verifies request acceptance and filtering, not ten simultaneous visible sources.|

Fifty-one focused checks against both development and compiled production sources verified twelve monthly
selections, holiday dates, seasonal hemisphere switching, five weekday languages,
far-offset civil dates, event filtering, cancellation handling and deduplication.
These semantic checks supplement the inspected native previews; they are not
physical-device tests. Production media contains no synthetic events or simulated
clock input. The saved private layout and sanitized reusable layout were each
read back and compared exactly with their candidate JSON.

**Thumbnail and deployment findings:**

- Multipart upload accepts `type=thumbnail`, matching the current client.
- A partial `PUT /api/v2/user/page` body `{id, thumbnail}` preserved the layout,
  resolution and dither in readback. This establishes that specific metadata
  update; it does not establish unrestricted PATCH semantics for all fields.
- After refresh deployment, the account device's `device_image` equalled the
  page thumbnail URL. Fetching it returned exactly the demonstrative thumbnail
  bytes, despite a different live layout preview. Updating the private page
  thumbnail to a real preview changed `device_image` accordingly. Treat this
  field as authoring/display-card metadata, not a physical screenshot or receipt.
- A direct refresh deployment returned code `200`. Device assignment contained
  the target source page; its snapshot data exactly matched the saved layout.
  Existing unrelated membership was preserved. A later snapshot preview executed
  the production document again with updated time and live data.
- The device remained online and `current_app` was null. No fresh physical screen
  confirmation or device-side render acknowledgement was available. Do not reuse
  an earlier user confirmation for this revision.
- Device telemetry reported `sensor_data.dataaccess.interval: 1800` seconds
  (30 minutes). This is the observed ordinary refresh setting, not a guarantee
  of exact rendering or delivery time; solar/theme changes appear on a later
  ordinary refresh rather than at an independently scheduled transition.
- Updating the existing reusable template retained audit status `0`. No new
  marketplace create/publish request was issued; public availability is unproven.
- Device detail returned the same account device field family as device listing.
  The authenticated third-party-data read returned an empty object in this run.
- The live device record's `board` is an object; use `board.type` for the model
  identifier (`reterminal_e1002` in this check), not a direct string comparison
  against `board`. Its additional network fields are private device metadata.

**Configuration boundary:** the inspected HTML editor exposes its source URL and
preview dimensions, not a schema for custom template checkboxes, calendar mapping
or numeric intensity controls. The runtime accepts these settings in the private
URL fragment, but automatic first-party onboarding into that fragment is not
established. Use a one-shot API authoring/configuration helper after first-party
Google consent; it can list the connected calendars, validate 1–10 choices,
resolve city coordinates through the existing geocoding provider and save the
fragment settings. This helper does not run during display updates. Keep the
missing integrated native settings form in the deferred backlog.

The one-shot configuration helper also produced inspected native previews with
intensity `37`, initials-only markers, dot-only markers, hidden timezone or
astronomy fields, English labels and city coordinates resolved by Open-Meteo
geocoding. These preview-only changes did not alter the installed settings.
Ten negative configuration checks rejected invalid counts, duplicates, enum
values, booleans, intensity bounds, coordinates and title-size bounds. The helper
updates both layout data and its real private thumbnail when saving; it does not
copy that preview into the portable template.

The final inspected dark preview exposed low contrast for blue/green calendar
markers against black and decorative artwork. The native HTML now retains the
selected fill colors, adds a white text outline in dark mode and a contrasting
rim to dots. Treat palette and background contrast as preview postconditions;
configured RGB values alone do not establish legibility after E6 dithering.

### Native HTML battery styling revision: 2026-09-30

**Inspected native renderer evidence.** The uploaded HTML fetched
`GET /api/v1/user/device/iot_data/{device_id}` using `api-key` from a private
fragment binding and `credentials: "omit"`. Light and dark previews displayed
the live percentage, transparent background and theme-colored outline icon.
This replaces the separate native percentage field whose styling was fixed.
The public uploaded document contains no key or device ID; portable layouts
remove the entire `batteryBinding` record and disable battery display.

The first production candidate failed because fixture stripping removed the new
helper definitions, despite passing JavaScript syntax validation. Source-level
checks did not cover that compiled artifact. The build boundary was corrected;
all 51 semantic checks now run against the compiled document too, including
`0%`, missing telemetry, rounding and invalid percentage bounds. A native preview
must contain the agenda and live percentage before save/deployment acceptance.

### Event end filtering and selection evidence: 2026-09-30

Authorized reads returned explicit `start.dateTime` and `end.dateTime` values
with timezone offsets. Use the end instant to expire timed events; start-based
filtering incorrectly removes ongoing entries. Displaying a smaller end time is
native HTML composition and requires no additional endpoint.

A selected-calendar rolling `type=2` read and explicit `type=4` millisecond-window
reads returned the same next-day event times. Searching the connected calendars
found the reported missing evening entry in an unselected calendar. This was
selection evidence, not evidence of an API row limit; do not silently broaden
calendar selection or record private event/calendar details in documentation.

A later one-day `type=4` probe returned a timed occurrence on the following day,
after the submitted end instant. This does not establish a strict exclusive
`[start, end)` range contract: the service may use civil-day or inclusive-end
semantics. Keep precise boundary filtering in the consumer and verify it against
returned timestamps rather than treating code `200` as proof of range semantics.

An authorized selection expansion to six distinct calendars was previewed with
the existing one-shot helper. New all-day and timed entries occupied earlier
rows, leaving later events in the remaining-count footer. Membership in the
fetched dataset does not guarantee simultaneous visibility: preserve chronological
ordering and admit only complete rows that fit, rather than prioritizing a named
later event to make a diagnostic screenshot pass.

The revised renderer retains the 44 px row pitch, measures container and element
heights, and fills all complete rows that fit. The row region uses y=88–461
without changing the event pitch. It has no fixed visible-event cap;
a future date heading requires room for at least one event. Source and compiled
semantic checks cover active/expired/overnight events and a 100-event input.

### Concurrent editor save evidence: 2026-09-30

A fresh page read after deployment differed from the deployed snapshot: editor
canvas metadata had changed and the HTML URL pointed to the preceding document,
while decoded installation settings were identical. Do not infer the actor or
mechanism from this readback alone. A device container can remain `800x480` while
root `stageSize` reflects a larger editor canvas. Preview reconciliation against
the device resolution before saving; preserve unrelated editor metadata and
verify both page data and deployed snapshot again after the final write.
