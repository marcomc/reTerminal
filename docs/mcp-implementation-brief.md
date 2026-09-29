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
- [Sources](#sources)

## Goal

Build an MCP server that can inspect the public template catalog and, once a supported account credential is available, create and manage templates for the authenticated user's account. The service API is undocumented and was inferred from the deployed first-party web client. Treat it as a fragile integration.

## Supported scope

### Initial read tools

1. `sensecraft_list_template_categories`
2. `sensecraft_search_templates` (marketplace list; filters include keyword, device model, resolution, tag, category IDs, sort and pagination)
3. `sensecraft_get_template`
4. `sensecraft_list_my_templates` (must require authenticated user access)

### Initial write tools

1. `sensecraft_create_template`
2. `sensecraft_update_template` only after the request schema is confirmed
3. `sensecraft_delete_template` only after target confirmation and a separate explicit destructive confirmation argument

Do not expose the broader route inventory by default. In particular, exclude account deletion, auth/login, AI generation, file upload, device binding, deployment, device config, page/playlist bulk mutations, social actions, share revocation, calendar OAuth/revoke, and arbitrary URL fetching. Add those only under separately reviewed capability requests.

## Authentication and configuration

- The initial implementation must have an injectable credential provider and must not assume a user-supplied `SENSECRAFT_API_KEY` works. Live requests demonstrated that public catalog GETs are anonymous, while profile and account-template GETs return `User unauthorized` without session auth.
- Ask Seeed for the official auth contract before claiming supported account writes. Do not automate website login or collect the user's password.
- Until then, allow a short-lived token to be supplied out of band via a protected environment variable/secret store. Confirm whether the token value needs the Bearer authorization scheme. Never put credentials in MCP tool arguments, resource contents, logs, exception strings, or generated documentation.
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

sensecraft_create_template({
  name: non-empty string,
  description?: string,
  page_type: supported page type,
  device_models: non-empty string[],
  resolutions: non-empty string[],
  dithers: integer[],
  category_ids?: integer[],
  tags?: string[],
  thumbnail?: URL,
  images?: URL[],
  data: JSON value or serialized JSON according to verified server contract,
  api_data?: JSON value or serialized JSON according to verified contract,
  record_page_id?: positive integer
})
```

The exact create request types (`data` and `api_data` appear as serialized JSON strings in the website call), required fields, allowed `page_type` values, URL ownership rules, and maximum sizes are unresolved. Match the site's wire contract after a sanitized authenticated capture rather than guessing. Consider accepting structured JSON from MCP callers and serializing it in one adapter layer, but only if tests prove this equals what the API expects.

Return a compact normalized result containing the created ID, name, page type, compatible device/resolution, and server visibility/audit status if returned. Do not return opaque `data` blobs by default. For list/detail tools, optionally expose a `include_layout_data` flag defaulting false.

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

- Do not auto-copy another author's template's `data`, images, license, or API credentials. Template reuse should use the platform's apply flow only after license/permission rules are understood.
- Template create is a persistent write. The client call is `POST /api/v2/user/template`; its payload fields are listed in the API notes.
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

- Supported account-auth scheme and token refresh lifecycle.
- Confirmed create/update payload schemas and response shape.
- Privacy/visibility and moderation behavior for created templates.
- Schema for template page `data` and `api_data`; supported device and dither values.
- API terms, rate limits, availability, and compatibility/version policy.
- A dedicated test account or another safe way to validate writes.

## Sources

- API evidence and complete route inventory: [SenseCraft HMI API Field Notes](sensecraft-hmi-api.md).
- Seeed official docs: <https://github.com/Seeed-Solution/sensecraft-hmi-docs>.
- Live application: <https://sensecraft.seeed.cc/hmi>.
- Public HMI API host: <https://sensecraft-hmi-api.seeed.cc>.
