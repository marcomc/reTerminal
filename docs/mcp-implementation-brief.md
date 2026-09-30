# MCP Implementation Brief: SenseCraft HMI

**Audience:** the agent implementing a separate MCP server. This document is the handoff contract; do not treat it as approval to perform writes to a user's SenseCraft account. Read [the API field notes](sensecraft-hmi-api.md) first.

## Contents

- [Goal](#goal)
- [Supported scope](#supported-scope)
- [Authentication and configuration](#authentication-and-configuration)
- [Tool design](#tool-design)
- [Template creation workflow](#template-creation-workflow)
- [Safety and privacy](#safety-and-privacy)
- [Transport and errors](#transport-and-errors)
- [Build and verification requirements](#build-and-verification-requirements)
- [Unresolved gates](#unresolved-gates)
- [Battery and astronomical display extension](#battery-and-astronomical-display-extension)
- [Agenda layout implementation contract](#agenda-layout-implementation-contract)
- [Sources](#sources)

## Goal

Build an MCP server that can inspect the public template catalog and, using an account API key, access the authenticated account's workspace and manage templates. The service API is undocumented and was inferred from the deployed first-party web client. Treat it as a fragile integration.

## Supported scope

### Initial read tools

1. `sensecraft_list_template_categories`
2. `sensecraft_search_templates` (marketplace list; filters include keyword, device model, resolution, tag, category IDs, sort and pagination)
3. `sensecraft_get_template`
4. `sensecraft_list_my_templates` (must require authenticated user access)
5. `sensecraft_list_my_designs` (workspace list filtered to `types=layout`)
6. `sensecraft_list_my_photos` (workspace list filtered to `types=img`)
7. `sensecraft_list_my_playlists`

### Initial write tools

1. `sensecraft_create_template`
2. `sensecraft_update_template` for an explicit template ID; the first-party payload shape has one authorized live update, but full schema semantics remain limited
3. `sensecraft_delete_template` only after target confirmation and a separate explicit destructive confirmation argument

Do not expose the broader route inventory by default. In particular, exclude account deletion, auth/login, AI generation, file upload, device binding, deployment, device config, page/playlist bulk mutations, social actions, share revocation, calendar OAuth/revoke, and arbitrary URL fetching. Add those only under separately reviewed capability requests.

## Authentication and configuration

- The tested account API key must be sent in the `api-key` header. Raw and Bearer `Authorization` returned application code 401; the `api-key` profile request returned code 200. Keep an injectable credential provider and load `SENSECRAFT_API_KEY` from a secret store or ignored local `.env` file.
- Public catalog GETs work without credentials. Profile, workspace pages, playlists, and user templates need the authenticated `api-key` header.
- Ask Seeed for the official auth contract before claiming supported account writes. Do not automate website login or collect the user's password.
- Never put credentials in MCP tool arguments, resources, logs, exception strings, or generated documentation. The `api-key` value belongs only in the upstream HTTP header.
- Do not refresh tokens automatically until the documented flow is known. The SPA refreshes through `sensecraft-auth.seeed.cc` and includes browser credentials; reproducing that outside a browser is not established.
- Separate anonymous catalog access from authenticated account access. A missing credential should not break the public read tools.

## Tool design

Use typed MCP input schemas with strict bounds and validation. Suggested shapes:

```text
sensecraft_search_templates({
  keyword?: string,
  device_model?: string,
  resolution?: string,
  tag?: string,
  category_ids?: integer[],
  page?: integer = 1,
  page_size?: integer = 20,
  sort_by?: string,
  sort_order?: "asc" | "desc"
})

sensecraft_get_template({id: positive integer})

sensecraft_list_my_templates({
  keyword?: string,
  device_model?: string,
  resolution?: string,
  tag?: string,
  page?: integer = 1,
  page_size?: integer = 20
})

sensecraft_list_my_designs({page?: integer = 1, page_size?: integer = 20,
                            resolution?: string})
sensecraft_list_my_photos({page?: integer = 1, page_size?: integer = 20,
                           resolution?: string})
sensecraft_list_my_playlists({page?: integer = 1, page_size?: integer = 20})

sensecraft_create_template({
  name: non-empty string,
  description?: string,
  page_type: supported page type,
  device_models: non-empty string[],
  resolutions: non-empty string[],
  dithers: integer[],
  category_ids?: integer[],
  tags?: string[],
  thumbnail: URL,
  images?: URL[],
  data: JSON value or serialized JSON according to verified server contract,
  api_data?: JSON value or serialized JSON according to verified contract,
  record_page_id?: positive integer
})
```

The first live account create established that `thumbnail` is required: an empty string returned application code `4304` (“Template thumbnail cannot be empty”). The SPA uploads an image as multipart fields `file` and `type=image` to `POST /api/v1/oss/file/upload`, then uses `result.file_url` as the template thumbnail. A create with a PNG URL succeeded and returned `{ "id": <integer> }` inside `result`; audit status was not included in that response. The successful create used JSON-encoded strings for `data` and `api_data`, but one hand-authored layout save does not validate every component schema or installation behavior. Treat template create as a persistent account mutation and upload as a separate persistent media operation; avoid orphaned uploads on later create failure.

For the MCP, keep thumbnail upload explicit: accept a bounded local image only if upload is deliberately in scope, validate MIME type and size, upload once, then create the template. Never accept arbitrary URLs for server-side fetch. If create fails after upload, report that media may remain in storage. Do not retry an ambiguous create after timeout without readback.

The first-party editor's `PUT /api/v2/user/template` payload is
`{id, name, description, thumbnail, images, device_models, resolutions,
dithers, category_ids, tags, api_data, data}`. It serializes `data` and
`api_data` as JSON strings and sends `category_ids` as an integer array.
One explicitly authorized live update returned application code `200` and
read back successfully; the template remained pending review. Validate the
target template and show the proposed diff before any MCP update.

The authenticated template-list response may expose `category_ids` as objects
with `id`, `name`, and `sort`, while the first-party update payload requires an
integer array. A live update using the readback objects returned application
code `400`; normalizing to the integer IDs produced code `200` and a matching
description readback. Convert the read model to integer IDs before `PUT`.

On 2026-09-30, an authorized create/readback confirmed that a sanitized E1002 template can retain an API-backed Google Calendar source with a session placeholder, no creator calendar IDs, and no creator timezone. Its audit status remained pending and public detail returned application code 4301; report that state and do not claim marketplace visibility.

Google Calendar uses a separate browser OAuth flow. The editor calls `/api/v2/calendar/authorize`, `/api/v2/calendar/list`, and `/api/v2/calendar/events`, and lets a user select calendars before loading. A live probe found that `calendar/list` needs both `session_id` and the account `api-key` header; event records expose `calendarId` but not the calendar display name or color. A live page readback confirmed that a private page can map each selected `calendarId` through `secondaryText.fields[].dataTransform.options.customFunction` to display-name initials plus a filled dot (for example, `"XY ●"`), with `style.color` setting the text and dot color. Build this mapping only from the installer's own calendar-list metadata and selected IDs; never place it in a public template. The reusable template currently uses generic ID-derived labels and three fixed color styles, so labels may not match calendar names. Keep Google authorization out of the initial MCP; do not expose or accept Google session IDs as substitutes for the installer's own consent.

Use `POST /render/preview` to obtain a rendered PNG from a candidate layout before saving or publishing it. The current SPA's E1002 profile uses dither value `3` for E6 full color; `0` is black-and-white. Validate the returned image when relying on per-field colors or text glyphs because a successful layout readback does not prove that the renderer displays them correctly.

A live synthetic preview on 2026-09-30 rendered event titles on the first line and times with two-character calendar-ID labels plus a colored filled dot on the secondary line, using three fixed colors. The sample data was supplied only to a preview clone. Keep fixtures out of the saved template and preserve its live API data source.

The current SPA's template import path substitutes the installer's locally
stored Google Calendar session into the layout before creating a workspace
page. If the sanitized session is missing and no installer session exists, it
warns that Google Calendar is missing and stops. This path does not launch
OAuth, open the calendar picker, or rewrite `calendar_ids`; the installer
must connect Google Calendar, choose calendars, and set the local timezone in the editor.
The UI creates the workspace page first and calls
`POST /api/v2/user/template/{id}/apply` afterward to refresh apply statistics.
Do not present that API endpoint alone as a page-copy operation.

The event API exposes `calendarId` but not calendar display names or colors,
and row transforms receive one field value without sibling metadata. A
portable template can use identifier-derived initials and fixed color styles;
display-name initials need a per-installer metadata join and an ID-to-label
transform in the private page.

The generic marker letters identify the calendar ID and may not match its display name. Do not imply that the first-party template automatically shows name initials or opens a calendar picker during marketplace import.

Device playlists can expose entries as snapshots with an entry `id` distinct
from `source_page_id`. The deployed client preserves snapshots as
`{id: entry.id, sort, kind: "snapshot"}` and submits a normal workspace page
as `{id: page.id, sort}`. A live probe received API code `200` when attempting
to replace a snapshot with its source page ID, but the expected normal-page
membership was not present on readback; the original playlist was restored.
Inspect both playlist membership and snapshot detail before treating an
upsert as a conversion. `GET /api/v2/user/page/detail?page_id={snapshot_id}&kind=snapshot`
can read the snapshot layout; a live comparison matched its `data`, resolution,
and dither to the source workspace page. A refresh response with code `200`
and an online device still did not populate `current_app`, so do not report
physical screen delivery without a separate device-side acknowledgement.

The first-party deploy route supports two observed request forms:
`{mode: "refresh", playlist_id, mac_addresses}` for a playlist and
`{mode: "refresh", page_ids, mac_addresses}` for a single page. The second
form was live-probed successfully, but the device API still returned a null
`current_app` afterward. Keep deployment out of the initial MCP scope and do
not treat HTTP/application success as proof of display delivery.

The authenticated browser device page showed a playlist-card thumbnail with
an older date after the successful refresh. Treat device-card thumbnails as
potentially cached previews; only a fresh device-side acknowledgement or
verified physical-screen image can establish display delivery.

For read-only assignment checks, the first-party client calls
`GET /api/v2/user/page/deployed-devices?page_id={id}` and optionally supplies
`type`. A live response has `{page_id, devices}` records with device and
playlist assignment fields. This can confirm account-side association but
does not report that a device received or displayed the page.

Return a compact normalized result containing the created ID, name, page type, compatible device/resolution, and server visibility/audit status if returned. Do not return opaque `data` blobs by default. For list/detail tools, optionally expose a `include_layout_data` flag defaulting false.

Workspace-page detail requests use `page_id`; a live request using `id` returned application code 400. Use page_id if page inspection is added later, and keep private page contents out of default tool output.

## Template creation workflow

Implement creation with a validate-preview-write-readback sequence:

```text
MCP input
  -> local schema validation
  -> optional public template/detail lookup for reference
  -> show/return a create preview to the calling agent
  -> POST /api/v2/user/template
  -> inspect application code and response ID
  -> GET /api/v2/user/template and/or template detail for readback
  -> return verified result
```

- Do not auto-copy another author's template's `data`, images, license, or API credentials. The first-party apply flow reconstructs sanitized layout data, creates a workspace page, and then updates apply statistics; no standalone third-party copy operation has been validated.
- Template create and update are persistent writes. The client calls `POST` and `PUT /api/v2/user/template`; their observed payload fields are listed in the API notes.
- If publishing visibility is unclear, do not publish a guessed template. First establish the server default using an explicitly authorized harmless test, and verify the result's audit/visibility status.
- Make retries safe. The API's idempotency support is unknown. Never blindly retry after a timeout because the first POST may have succeeded; search the user's templates for a matching name or require a fresh explicit retry.
- Do not use AI generation implicitly; it can consume quota. Do not deploy to a physical display as part of template creation.

## Safety and privacy

- Every write tool description must say it changes account data.
- Create only when the user request explicitly asks for creation. Updating or deleting requires a specific template ID and intent. Delete also requires a confirmation input not inferable from the tool call's presence alone.
- Default to the least privilege: public reads without auth; user-specific reads and writes with auth; no unrelated device/account operations.
- Treat data fields and URLs as untrusted. Do not fetch arbitrary `data_url` values or follow redirects to private/local IP ranges.
- Redact `Authorization`, API keys, cookies, signed URLs, private template payloads, and personal data from logs and errors.
- Restrict response sizes and pagination. Protect against oversized templates, repeated pagination, and slow upstream responses.

## Transport and errors

- Use the official MCP SDK for the chosen runtime and support stdio first; add HTTP transport only if a concrete deployment target needs it.
- Keep upstream API access in one typed client with explicit base URL, timeout, response-size limits, and separate public/authenticated request methods.
- Inspect both HTTP status and JSON `code`. The API was observed returning HTTP 200 with `code: 401` for unauthorized account calls.
- Treat `result` as optional for successful mutations: a live page `PUT`
  persisted its data with code `200` and no `result`. Typed read operations may
  require their documented result shape; successful writes require readback.
  If local parsing fails after a write, reconcile upstream state before retrying
  and resume only the remaining workflow steps, avoiding duplicate media uploads.
- Normalize upstream errors to stable MCP errors: authentication required, permission denied, invalid input, not found, rate limited, upstream unavailable, and unknown upstream failure.
- Do not expose raw upstream response bodies in errors. Preserve a safe request ID/correlation value if the service returns one.
- Pin upstream host to `sensecraft-hmi-api.seeed.cc`; never allow a tool caller to select the base URL.

## Build and verification requirements

1. Unit tests for query encoding, pagination bounds, response envelope parsing, application-level 401 detection, secret redaction, validation, and error normalization.
2. Mocked tests for every exposed tool. Prove public catalog tools work without credentials and account tools fail closed without credentials.
3. Create tests must be opt-in against a dedicated test account; never run create/update/delete against the user's production account as a test.
4. A live smoke test should be read-only unless an isolated test account and disposable template are explicitly configured.
5. Capture provenance: bundle URL/hash/date, API notes version, and whether each API behavior is official, client-observed, or live-probed.
6. Keep the MCP package and docs free of real credentials, user templates, and private response captures.

## Unresolved gates

Do not describe the MCP as ready for account writes until these are resolved:

- Official account-auth contract, full permissions, and token refresh lifecycle.
- Full update semantics across template types, create visibility/audit behavior, and the moderation lifecycle.
- Privacy/visibility and moderation behavior for created templates.
- Full supported schema for template page `data` and `api_data`; component installation behavior, including Google OAuth handoff.
- API terms, rate limits, availability, and compatibility/version policy.
- A dedicated test account or another safe way to validate writes.

## Sources

- API evidence and complete route inventory: [SenseCraft HMI API Field Notes](sensecraft-hmi-api.md).
- Seeed official docs: <https://github.com/Seeed-Solution/sensecraft-hmi-docs>.
- Live application: <https://sensecraft.seeed.cc/hmi>.
- Public HMI API host: <https://sensecraft-hmi-api.seeed.cc>.

## Battery and astronomical display extension

The 2026-09-30 live telemetry and renderer probes establish a dynamic battery
field using `GET /api/v1/user/device/iot_data/{device_id}` and
`result.battery.level`. Resolve the numeric device ID from the authenticated
account list; do not substitute a MAC address. The first-party editor places
the account API key in the element's `dataHeaders`. Keep that binding private
and out of reusable templates, logs, thumbnails with source metadata, and
public exports. The final HTML agenda uses an installer-specific fragment
binding instead, allowing the percentage and icon to share theme styling.
An authenticated service of our own is deferred. Never infer
zero battery from missing telemetry; retain freshness and unavailable states.

Weather editor bindings expose daily sunrise and sunset through Open-Meteo;
an earlier live forecast probe returned four daily dates with both fields.
Verify returned dates, coordinates, timezone, index alignment, and rendered
icons before using them for each visible agenda day. Timezone alone does
not determine solar times: require an explicit city or coordinates. A lunar
phase provider or validated calculation is still needed; no native binding
was identified in the inspected web client. Distinguish waxing and waning
explicitly rather than relying only on a moon glyph's orientation.

The agreed agenda behavior and verified implementation are specified below.
Requested controls are a configuration contract, not proof that the
first-party editor offers equivalent controls. No MCP implementation is
included in this research.

A user confirmed physical delivery of the previous agenda on 2026-09-30.
That confirmation closes the earlier delivery uncertainty for that version
only; do not reuse it as proof that subsequent revisions reached the panel.

## Agenda layout implementation contract

**Agreed 2026-09-30.** This section governs the calendar layout investigation
and its eventual implementation. It does not expand the initial MCP tool
scope or authorize new account writes. Evidence is recorded in the
[API notes](sensecraft-hmi-api.md#agenda-feasibility-evidence-2026-09-30).

### Runtime boundary

- Implement only behavior that SenseCraft itself can execute from the saved
  layout and its data bindings during normal rendering and display refresh.
- Local scripts may inspect, prepare, configure, preview, and save layouts
  through the API when authorized. The installed agenda must not depend on
  those scripts running periodically or remaining online.
- Do not add our own hosted application, remote rendering service, scheduler,
  custom firmware, or Google OAuth application for this phase. External data
  providers already usable from SenseCraft, such as Open-Meteo, are allowed.
- Prefer the fullest layout supported by SenseCraft, then simplify unsupported
  features. The previously proposed periodic-generator architecture is deferred.
- Prove behavior in the actual SenseCraft renderer and on later renders.
  Editor-only JavaScript, accepted JSON, and an uninspected PNG are insufficient.
  A one-time precomputed date or theme does not satisfy an automatic feature.

### Calendar selection and row layout

- Configure **1 to 10 distinct calendars** from the installer's own Google
  calendar list, including subscribed calendars. This is the desired
  configuration bound, not a verified API or native-picker limit.
- Let the installer choose initials and a color for each calendar. Join event
  `calendarId` to the selected list record and retain the mapping in the
  private installation. Do not embed creator IDs or mappings in public exports.
- Support `initials_and_dot`, `initials_only`, `dot_only`, and `none`;
  default to both. Initials are plain colored text without a badge background.
- Keep event times at a fixed font size, independent of title length. Align
  visible calendar markers at the right, including rows with short titles.
- First investigate HTML/SVG composition executed within SenseCraft. If proven,
  maximize title width, reduce only the title to a readable floor, and fade its
  overflowing tail while keeping markers opaque. Reclaiming marker space is
  desirable in this path.
- An HTML component needing a page hosted by us exceeds the runtime boundary.
  Do not treat an accepted `htmlUrl` preview as an embedded execution solution.
- Fallback: separate native fields with a fixed title area; hidden markers may
  leave unused space for decoration. Limited title fitting remains subject to
  renderer proof. If unavailable, document fixed-size truncation and defer the
  adaptive typography. Do not silently shrink the event time or wrap titles.
- A maximum title reduction of **15%** remains an assistant proposal, not an
  approved minimum. Future-day grouping and filtering after the current time
  require their own render-time proof; no periodic script workaround is allowed.

### Header, language, location, and astronomy

- Use the E1002 landscape target `800x480`, E6 dither `3`, and the approved
  header alignment with battery below the clock in the same right column.
- Always show the clock. Use a localized uppercase red agenda heading,
  weekday, and `DD-MM-YYYY` date. Timezone selection and timezone-label
  visibility are separate settings; hiding the label never hides the clock.
- Investigate native date formatting and permitted transforms for Italian.
  Apply only a solution proven in the cloud render. Define template translations
  separately from the SenseCraft editor's own interface language.
- Prefer the native city selector. Establish its actual geocoding source and
  whether the selected city supplies coordinates usable by the weather binding.
  A connected data-provider lookup is acceptable; our own hosted menu is deferred.
- Use the selected city for Open-Meteo solar times. Approximate coordinates are
  sufficient; GPS is unnecessary. A timezone alone does not supply coordinates.
  A representative city per timezone is an alternative pending user selection.
- Provide independent visibility settings for daily sunrise and sunset, today's
  lunar phase with waxing/waning, and battery, wherever the native configuration
  supports them. Keep these indicators compact. No lunar binding is proven;
  defer it if an in-layout calculation or connected provider cannot be verified.

### Backgrounds and ordinary refresh

- Preserve all approved mockups and maintain original decorative assets at full
  intensity. Available themes include plain light/dark, floral, unicorn, LGBTQ,
  four seasons, twelve months, and the selected festivities.
- Investigate automatic selection **at each ordinary SenseCraft render**.
  Automatic mode chooses monthly or seasonal cadence, with an independent
  special-date checkbox. Holiday overrides apply only when that checkbox is on.
- Holiday rules: Easter Sunday; January 6 for Epiphany; October 31 for Halloween;
  December 24 through 26 inclusive for Christmas. Carnival's regional convention
  is unresolved; Shrove Tuesday is a proposal. Seasonal hemisphere/convention
  must be specified before claiming geographically correct automatic seasons.
- Automatic light/dark is independent of manual/automatic background selection.
  Compare current local time with that day's Open-Meteo sunrise and sunset on
  each normal render. Show dark before sunrise and after sunset; retain a
  documented manual fallback if solar values are unavailable.
- No exact sunrise/sunset trigger or additional display-refresh scheduler is
  required. Changes appear at the next ordinary device update.
- If render-time conditions cannot be established, provide manual selection
  and move the missing automatic behavior to the deferred backlog.

### Decoration intensity

1. Investigate a white overlay in light mode and black overlay in dark mode,
   placed above the image and below all text and indicators.
2. Expose an integer intensity `I` from **0 to 100**, with direct entry and
   increment/decrement arrows in steps of **1**, if native controls permit it.
   Overlay opacity is `1 - I / 100`: 100 leaves the image unobscured; 0 hides it.
   Verify the intermediate alpha values in the actual renderer.
3. Time-box this overlay investigation to **one hour** of implementation work.
   It is a future investigation budget; no hour of testing is claimed here.
4. If unsupported, preserve the full-intensity sources and derive **four**
   intensity variants with an image-processing program. Upload those variants
   only during an authorized implementation step. Keep the approved originals.
5. The four percentages are unresolved. **25/50/75/100%** is an assistant
   proposal. Do not treat it as the selected setting or generate it by default.

Opacity variants and overlay intensity affect only decoration. Calendar colors,
text, clock, and astronomical indicators retain their contrast. The configuration
mockup is not proof of native numeric controls or arbitrary template settings;
record the actual editor workflow and any missing control instead of inventing
a custom hosted panel.

### Guided installation and implementation order

Use the first-party SenseCraft procedure: connect Google, select calendars,
configure their initials/colors, timezone and city, then preview the layout.
Document manual steps. Marketplace import alone does not launch this complete
flow. Investigate any missing step before proposing alternatives; do not add
our own OAuth service as a fallback in this phase.

Implementation order after separate authorization:

1. Inspect the saved synthetic previews, including Italian dates and SVG
   transforms; classify actual output rather than HTTP acceptance.
2. Establish which requested settings the native editor can expose, and resolve
   selected calendars by ID with no guesswork from ambiguous names.
3. Prove row composition, city lookup, render-time date/solar decisions, and
   the overlay within the runtime boundary. Document fallbacks per feature.
4. Prepare an API-backed candidate, preview it, and review supported settings.
5. Save/read back and deploy only when the requested implementation scope
   authorizes those operations. Verify later refresh separately from save success.

### Deferred TODO

- [ ] External periodic generators, schedulers, or always-on helper processes.
- [ ] Our own hosted configuration UI, rendering application, or OAuth service.
- [ ] Integrated native settings controls, regional Carnival variants and precise
  lunar ephemerides beyond the implemented native HTML path.
- [ ] Evaluate TRMNL BYOS and device/firmware compatibility as a future research
  option; migration is not selected or authorized now.

Keep these entries deferred. An implementation agent must not promote them to
required infrastructure merely to achieve the mockup.

### Verified native building blocks: 2026-09-30

Use the implementation probe results in the API evidence record:

- Compose the decoration veil as an RGBA rectangle above the background and
  below content. Keep intensity configuration separate from image `opacity`,
  which the tested renderer ignored. Intermediate veil alpha is verified.
- A native API field may bind an entire object/array and transform it. Investigate
  independent row fields from a shared events array for sorting, filtering and
  calendar mapping; a per-field transform is not intrinsically limited to a
  scalar. Preserve live bindings rather than writing a precomputed event list.
- Investigate an explicit weekday/date transform for Italian. Do not rely on
  the date-format probe that rendered US dates instead of the submitted format.
- Custom-image transforms displayed static fallback images in four fetched
  cases. Keep smart SVG composition unproven and retain native field fallback.
- Reuse first-party weather city configuration: Photon search with Open-Meteo
  geocoding fallback, followed by timezone resolution where needed.
- SenseCraft itself accepts uploaded HTML documents and executes inline script
  in a native HTML element. A self-contained uploaded media artifact can be
  investigated within the runtime boundary: it requires no application server
  operated by us. This is not permission to put account credentials or calendar
  data in a publicly fetchable document. Confirm subsequent renders and provider
  loading before adopting automatic decoration or astronomy through this path.

For the general MCP handoff, document HTML media upload and native composition
as separately gated capabilities. Do not silently add them to initial tools or
claim that a successful upload proves every dynamic HTML feature.

### Native HTML implementation path

The authorized implementation uses an uploaded, self-contained SenseCraft HTML
media artifact for composition. Its inline JavaScript executes and fetches
providers during native rendering; no process operated by us remains online.
This is within the agreed SenseCraft runtime boundary.

- Put only account-independent code and decorative asset references in the
  uploaded document. Provide installation settings and the user's Google
  session through the private layout URL fragment. The fragment is sensitive;
  never log, export or publish it. Fragment isolation does not make it a public
  or permanent credential store.
- The verified events endpoint accepts the authorized Google session without
  the account API key. Fetch with browser credentials omitted. Calendar listing
  still needs the account key, so use first-party Google connection and calendar
  selection, followed by an explicit installation mapping step.
- Fetch battery telemetry in the native HTML using a private `batteryBinding`
  fragment record containing `deviceId` and `apiKey`. Keep the key out of uploaded
  HTML, portable exports and logs. This replaces the separate native battery
  field so the percentage and icon share the current theme and transparent
  background. The fragment is as sensitive as private `dataHeaders`.
- Execute async provider reads in the uploaded HTML. Native custom field
  transforms did not await Promises. Use `Intl` for localized dates and browser
  text measurement/CSS masking for titles, subject to actual renderer checks.
- Strip the installation fragment when producing a reusable template. Do not
  claim that marketplace import or a native Google picker automatically updates
  the HTML's configuration. An API authoring helper may configure the private
  layout once; it must not become a periodic runtime dependency.
- The rolling-looking `type=2` response includes future dates across the month
  boundary. Filter/sort its records inside the native document, and verify
  upcoming-day coverage rather than assuming client labels describe the API.

### Implemented configuration contract and handoff

The native HTML agenda was saved and refresh deployment accepted on 2026-09-30.
Private page, reusable template and deployed snapshot readbacks matched their
intended layouts. Follow the API evidence record for the verification limits.
This is an authoring example for a general SenseCraft MCP, not a restriction of
future template tools to calendar content.

#### Layout and media

- Use an `800x480` root group with a full-size `type: "html"` child containing
  `htmlConfig.htmlUrl`; dither is `3`. Battery telemetry is read within that
  document, using a private fragment binding. Public exports omit that binding
  and disable the battery display.
- Upload self-contained HTML as `type=document`; upload decorative images
  separately and place their returned URLs in its media manifest. Keep originals
  and store content hashes to avoid uploading the same version repeatedly.
- Production documents must contain no synthetic event data or simulated clock
  paths. Demonstration thumbnails may use fictional records. A private workspace
  page must have a real preview thumbnail; reusable-template images must remain
  free of the creator's events and account data.
- The verified private thumbnail update is `{id, thumbnail}` via page `PUT`.
  Check unchanged layout, resolution and dither afterward. Page-save readback and
  snapshot equality are separate postconditions from deployment acceptance.
- Never treat `device_image` as a physical display screenshot: in the live check,
  it tracked the supplied page thumbnail byte for byte. Report physical delivery
  only from fresh device-side evidence or a user observation of that revision.
- Read ordinary refresh telemetry separately from save/deploy status. The live
  `sensor_data.dataaccess.interval` was `1800` seconds (30 minutes); this is an
  observed setting, not an exact delivery deadline. Theme and solar mode changes
  take effect when SenseCraft next renders during ordinary device refresh.
- Validate the device model through `board.type`: live device records expose
  `board` as an object containing model and private network metadata. Project
  only necessary capability fields into public results; do not log the object.
- Inspect calendar marker contrast in light and dark dithered previews. Preserve
  chosen fill colors; the implementation adds a white outline to dark-mode
  initials and a contrasting dot rim so blue/green markers remain identifiable.
  General MCP preview validation must assess contrast against the actual artwork.

#### Settings schema

These are runtime settings; they do not imply that the native inspector provides
matching controls. A one-shot configuration helper or a separately authorized
future MCP authoring tool can validate and save them.

|Setting|Accepted values / implementation behavior|
|---|---|
|`language`|`it`, `en`, `fr`, `de`, `es`; affects labels and dates, not event content.|
|`timezone`|Valid IANA name; the clock is always shown.|
|`city`, `latitude`, `longitude`|City configuration with validated coordinates; geocoding supplies the timezone where available.|
|`showTimezone`, `showSunrise`, `showSunset`, `showMoon`, `showBattery`|Independent booleans; battery needs the installer's private telemetry binding.|
|`calendars`|1–10 distinct records from the connected account list, with ID, display name, chosen initials and `#RRGGBB` color. Private installation only.|
|`markerMode`|`initials_and_dot`, `initials_only`, `dot_only`, `none`; default both.|
|`backgroundMode`|`automatic` or `manual`.|
|`cadence`|`months` or `seasons`; implementation default months.|
|`theme`|Plain white/dark, floral, unicorn, LGBTQ, four seasons, twelve month assets and the agreed festivities.|
|`specialDates`|Independent holiday override in automatic mode.|
|`autoDark`, `mode`|Automatic solar comparison or explicit `light`/`dark`; saved manual mode is the unavailable-solar fallback.|
|`intensity`|Integer 0–100, step 1; veil opacity `1 - intensity/100`; implementation default 50.|
|`hemisphere`|`auto`, `north`, `south`; auto follows latitude. Seasons use meteorological month boundaries.|
|`carnivalRule`|`shrove_tuesday` or `none`; default Shrove Tuesday, Easter minus 47 days. Regional alternatives remain a TODO.|
|`excludeBirthdays`|Default true for this installation; filters recognizable all-day birthday summaries even when they belong to an otherwise selected calendar.|
|`titleSize`, `minTitleSize`|Implementation defaults 28 and 25 px; browser measurement shrinks only the title, then fades overflow. Timed-start text remains 28 px.|

The 28-to-25 px range is an implementation default selected during autonomous
work, not the earlier unapproved 15% proposal. Upcoming rows cover today and up
to three following dates as space permits. Skip cancelled entries and timed events whose end is at or before the
current instant; retain active multi-day all-day entries. Deduplicate by calendar ID,
event ID and occurrence start. Use the selected timezone for timed events and
civil-date formatting for all-day values. The lunar display uses a mean synodic
month and identifies waxing/waning; do not advertise ephemeris-level precision.

#### First-party installation and API configuration

1. Connect Google in the SenseCraft data configuration and select calendars from
   the installer's own list. Existing subscriptions are eligible. Do not create
   another OAuth application or substitute the template creator's session.
2. The authoring helper reads that authorized session privately, calls calendar
   list with the account key and builds the selected ID/name/initial/color map.
   Reconcile against the fresh list before saving; reject duplicate or unknown IDs.
3. Configure city/timezone and the settings above. The helper can use the native
   geocoding providers and validate the result. It may preview, save and refresh
   via API once; no local process is needed afterward.
4. Save the private configuration only in the installation's HTML URL fragment.
   Remove the fragment's session and all calendar records from portable exports;
   remove the complete `batteryBinding` record and owner event thumbnails as well.
5. Inspect the real preview, compare saved JSON, deploy, then compare the deployed
   snapshot. Report device-online state separately from physical delivery.

For a future general MCP, document content-independent primitives: native layout
validation, explicit media upload, HTML-component composition, private binding
configuration, portable export sanitization, preview inspection, page readback
and snapshot verification. Calendar-specific mappings sit above those primitives.
Adding upload/deployment/binding tools still requires a deliberate capability
scope expansion beyond the initial tool list; no MCP was implemented here.

#### Battery theme revision: 2026-09-30

- Native HTML fetched the authenticated telemetry endpoint and displayed the live
  percentage in inspected light and dark previews. The background is transparent;
  icon and percentage inherit the agenda ink color, with a small contrast outline.
- Account-independent HTML code reads the key only from the private installation
  fragment and sends it in `api-key` with `credentials: "omit"`. Strip the binding
  on export and do not expose it as a user-editable ordinary setting or log it.
- Missing or invalid telemetry displays `—`; zero remains `0%`. Do not replace
  unavailable readings with a stale constant.
- Validate the compiled production document, not only the development source:
  fixture stripping initially removed the battery helpers too. Fifty-one semantic
  checks now run against both versions, covering missing values and percent bounds.

#### Remaining native limitations

- No integrated settings form with these checkboxes, numeric arrows or per-user
  calendar/color mapping was found in the first-party HTML inspector. Use the
  documented one-shot configuration path; an integrated form remains deferred.
- Marketplace import does not configure the HTML fragment or start the complete
  Google/calendar-selection wizard. Portable templates need the manual native
  Google connection and explicit installation mapping above.
- Regional Carnival conventions beyond Shrove Tuesday and precise lunar
  ephemerides remain deferred. Exact-time sunrise/sunset refresh is unnecessary;
  the next ordinary SenseCraft render applies the current mode.
- Our own hosted services, periodic generators, always-on helpers and firmware
  migration remain outside this phase. Native HTML eliminated the need to defer
  title fitting, date grouping, solar mode selection and theme rules themselves.
- This revision has API deployment evidence and inspected live renderer output;
  no physical-screen confirmation was observed.

The local one-shot helper supports connected-calendar listing and indexed
selection with initials/colors, city geocoding, typed setting updates, preview,
save/readback and optional refresh deployment. Preview-only mode leaves installed
settings unchanged. Save updates the private page's real thumbnail as well as its
data, keeping the device-card preview consistent. Intensity `37`, marker-only
variants and an English/city-selection preview were inspected; ten invalid-input
checks passed. Numeric arrows and checkboxes still require a future integrated
native form: a working boolean or integer setting is not proof of inspector UI.

### Active events and available row space: 2026-09-30 revision

- Keep timed events visible while `end.dateTime` is after the current instant,
  even when they started earlier. Exclude at the exact end boundary. An active
  event that started on a previous date is grouped under today. Without a valid
  end timestamp, use the start as the documented expiry fallback.
- Show the end time below the fixed 28 px start, in a smaller muted font. Preserve
  the existing 44 px row pitch and single-line event title for all visible days.
- Admit rows according to the actual row container height and measured element
  heights, with no fixed event-count cap. The row region spans y=88 through 461
  on the 480 px display; the compact remaining-count footer stays below it. Reserve a date header together with
  at least one row; never leave an orphaned future-day heading at the bottom.
- A missing appointment may belong to an unselected calendar. Compare calendar
  IDs against the connected list before changing layout limits or enlarging the
  selected set. Explicit-window and rolling reads returned the same selected
  next-day entries in this check; a separate calendar held the missing entry.
- Do not assume date-range `type=4` enforces exclusive end timestamps. A live
  one-day probe returned a timed occurrence after the submitted end. Keep
  consumer-side range filtering and expose the observed boundary uncertainty
  in future MCP result metadata; do not advertise exact upstream filtering.
- Selection expansion was exercised with six distinct live calendar records.
  Additional earlier events can push a correctly fetched later event below the
  visible area. Verify selection membership and visual capacity independently;
  keep chronological ordering and report the remaining-event count.
- Fifty-one semantic checks cover ongoing events, exact expiry, overnight events,
  next-day evening entries and a 100-event input without a normalization cap.
  Native preview and deployment verification remain separate evidence gates.

### Concurrent authoring reconciliation

Treat page saves and deployed snapshots as independently changing state. A live
check found a prior HTML source URL in the saved page after newer deployment,
with unchanged decoded settings and added editor canvas/rotation metadata.
Re-read before mutation, back up the complete record, update only the requested
source/binding, preserve unrelated fields and inspect a device-resolution preview.
Root `stageSize` need not equal the device group's dimensions in editor records.
Verify saved page and deployed snapshot after reconciliation; repeated concurrent
changes require coordination with the editor rather than blind repeated writes.

### Private-page lifecycle after template withdrawal: 2026-09-30

The authorized withdrawal evidence in the API notes confirms private page,
Google connection and device snapshot preservation in this installation.
Make reusable-template identity optional in page authoring/deployment tools.
A page-only operation must never recreate a withdrawn template implicitly.
Treat successful mutations without `result` as success envelopes, then verify
resources through readback. Do not infer deletion idempotency or generic cascade
semantics; keep destructive actions separate and explicitly authorized.

Durable local authoring preferences belong in ignored root `sensecraft.local.json`;
connections/API key/session and resource IDs in ignored
`sensecraft.connection.local.json`. `.private/` contains regenerable artifacts.
A future MCP should reuse this configuration boundary, redact private fragments
and distinguish local save, account-page save and device refresh.

### Rendering verification consequences: 2026-09-30

Local review found that a fixed three-day normalization horizon could hide the
next returned event despite available screen space. The HTML consumer now sorts
all non-expired selected events returned by SenseCraft; available row space is
the presentation limit. Solar forecast coverage is 16 days; absent forecast
entries are handled as unavailable rather than inventing times. This is a local
rendering correction, not a new upstream date-range guarantee.

Private-page persistence reconciles editor metadata into the new layout.
Verification must compare against that persisted layout, not the build's
canonical canvas. Operational privacy, production and readback checks must
remain effective under optimized Python execution; use explicit exceptions.
