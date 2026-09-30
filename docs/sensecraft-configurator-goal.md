# SenseCraft configurator: autonomous delivery specification

This is the complete specification referenced by the compact Goal below.
It preserves the approved delivery workflow and configuration requirements.
It describes future work; this document is not evidence that implementation,
QA, review, publication or merges have already happened.

## Compact Goal

Paste the following text into the Goal field. When using the composer command,
prefix it with `/goal` followed by a space. The full specification below is incorporated by reference.

```text
Completa autonomamente il consolidamento di reTerminal e il configuratore Python locale Google Calendar Today secondo TUTTI i requisiti di docs/sensecraft-configurator-goal.md: leggilo integralmente prima di agire e rileggilo dopo ogni ripresa. È la specifica completa incorporata in questo goal; non ridurla.

Consegna due PR unite in main e l'applicazione funzionante e testata. Prima consolida il branch attuale e completa scoped-pre-pr-remediation con review-coordinator fino a READY; commit, push, PR verso main, codex-pr-review-remediation-loop fino a esito pulito sull'HEAD corrente e merge. Poi crea un branch feat/ dal main aggiornato, realizza il configuratore, ripeti remediation, PR, review loop e merge. Verifica infine il main risultante.

Crea due chat nel progetto, backend e frontend; sei autorizzato a inviare istruzioni, coordinarle, monitorarle e integrarle. Lavora qui in sequenza, senza worktree obbligatorio; se le chat condividono il checkout evita modifiche e operazioni Git concorrenti. Preserva lavoro estraneo e installazione privata esistente.

Sei autorizzato a dipendenze locali, modifiche, test, browser/computer use, staging, commit, push, PR, commenti di revisione, risoluzione dei problemi e merge, credenziali locali, upload, salvataggio della pagina privata e refresh del dispositivo scelto. Sviluppa tramite API; usa il browser per QA e operazioni non disponibili via API. Non pubblicare template per altri, non creare un MCP o servizi permanenti, non cancellare pagina/dispositivi/account né revocare Google. Non esporre dati personali o segreti.

Implementa tutte le opzioni approvate, setup API key/Google, preview reale senza modifica della pagina, salvataggio locale, conferma "Salva e pubblica", pubblicazione privata con readback, recupero e retry. Mantieni preferenze e connessioni nei due JSON ignorati nella root; .private/ deve essere rigenerabile. Dopo la pubblicazione il template deve funzionare senza l'app o il computer accesi.

QA completo: matrice requisito/prova/esito, test automatici, ogni controllo e opzione nel browser, combinazioni rappresentative, date controllate, limiti/errori, persistenza/migrazione, ricostruzione di .private/, OAuth, preview/save/publish/recovery e integrazione reale. Usa computer use quando serve; correggi e riprova. Distingui test simulati, rendering, API, snapshot e prova fisica.

Aggiorna runbook, diagramma, README, TODO, CHANGELOG e, per ogni scoperta API, sia note API sia brief MCP. Esegui lint e controlli pertinenti. Mantieni evidenza e prossimo passo per ogni iterazione.

Procedi senza domande per scelte ordinarie. Se un impedimento esterno rende impossibile proseguire, completa il lavoro indipendente e riporta tentativi, evidenza, blocco e requisito per riprendere; non dichiarare successo né aggirare i gate. Quote e revisioni pendenti non sono esiti puliti.

Completo solo con due PR revisionate e unite, avvio documentato, tutte le opzioni verificate, pubblicazione privata e runtime autonomo collaudati, test/lint superati e documentazione aggiornata. Consegna comando di avvio, link PR, evidenze QA e limitazioni.
```

## 1. Outcome and operating boundaries

Deliver a local Python configurator for Google Calendar Today inside
`templates/google-calendar-today/configurator/`, after consolidating the
existing project in a first PR. Deliver two reviewed PRs merged into `main`,
then validate the merged application.

- Read applicable `AGENTS.md`, the nearest README, metadata and relevant
  release notes before changes. Before agenda restoration, read
  `docs/sensecraft-agenda-rebuild.md`.
- Inspect current Git state, existing PRs and related project chats.
  Preserve unrelated changes and useful private installation state.
- Begin in the current directory on the current branch. Worktrees are
  optional, used only where necessary to protect or isolate work.
- Prefer sequential execution. Shared checkouts must have one mutation owner
  at a time, including Git operations.
- Make ordinary implementation decisions autonomously, choosing the simplest
  solution compatible with approved requirements. Keep progress updates concise.
- Develop the template through SenseCraft APIs. Use the browser for QA and
  operations unavailable through the APIs.
- The application runs only when configuration is needed. The published
  template must operate in SenseCraft with the local app and computer off.
- Do not add permanent external services, local periodic jobs or an MCP server.

### Scoped authorizations

Activating the compact Goal authorizes these actions within this specification:

- Code, tests, example configuration and documentation changes.
- Necessary dependencies in the project environment.
- Automated tests, browser QA and computer control where needed.
- Branch creation, staging, commits, pushes and the two PRs.
- Review comments/triggers, fixing findings, resolving discussions actually
  fixed and merging after all gates pass.
- Reading and using existing local credentials without exposing their values.
- Necessary resource uploads, private-page creation/update and refresh of the
  selected device for integration verification.
- Creating the two implementation chats, sending coordinating instructions,
  monitoring them and integrating their work.

Publish only to the account's private page. Do not create public/reusable
templates or submit public publication requests. Do not delete the private
page, devices or account, or revoke Google authorization.

Keep personal data, keys, sessions, cookies and real resource identifiers out
of tracked files, documentation and test logs. The project copyright in
`LICENSE` remains the only permitted personal attribution in tracked content.
Keep sensitive screenshots and integration captures in ignored local storage.

## 2. First PR: consolidate the existing implementation

Before starting the configurator:

1. Check the current sources and the results of related project chats.
2. Finish the CLI lifecycle for a private page; remove the dependency on the
   withdrawn reusable template without recreating it.
3. Finish separation of durable preferences, durable connections and generated
   artifacts, with lossless migration of the existing configuration.
4. Inspect final backgrounds, manifest, light/dark associations and rendering.
   Complete pending visual QA. Keep final runtime/reconfiguration assets
   versioned; remove obsolete operational references to decision material.
5. Update README, rebuild guidance, the canonical publication diagram,
   TODO and CHANGELOG.

Run `scoped-pre-pr-remediation` with its companion `review-coordinator` over
the complete first-PR scope, including relevant uncommitted content.
Fix findings until the local result is `READY`.

Commit, push and open PR 1 toward `main`. Use the latest relevant CHANGELOG
release notes for the PR title/body. Attach the PR to the task.

Run `codex-pr-review-remediation-loop`. Check for an existing review before
requesting another. Use one coordinator/ledger per PR; avoid nested or
duplicate review loops. Bind review evidence to the exact current HEAD.

Merge only when local readiness, pushed content, required checks and a clean
review all agree, with no unresolved actionable findings. Pending,
unacknowledged or quota-blocked review is not a clean result.

## 3. Second branch and implementation chats

After PR 1 merges, update `main` and create a new `feat/` branch from that
merged state.

Create two user-visible chats in the reTerminal project:

- Backend: Python server, persistence, SenseCraft/Google integration.
- Frontend: configuration interface and UI verification.

Define contracts, responsibilities and file ownership before edits.
The coordinating chat owns integration and final validation.

The chats may remain open in parallel, but modifications and Git operations
must be sequential when sharing the same checkout. Do not let multiple chats
change the same files concurrently. Use isolation only when needed.

Coordinate with messages and compact status snapshots. Do not create
duplicated review coordinators or review loops for the same PR.

## 4. Local application lifecycle

Provide one documented CLI command that:

- Starts an HTTP server bound exclusively to `127.0.0.1`.
- Opens the default browser automatically.
- Always prints the actual URL, including the selected port.
- Handles an occupied port and failure to open the browser.
- Supports clean shutdown.

Do not require local-panel login. Protect mutation endpoints from requests
originating from other sites.

Read local configuration on launch. Support both first installation and
an existing private page, without dependence on a reusable template.
Removal from the SenseCraft account remains the user's responsibility.

Closing the app must not stop calendar rendering, automatic backgrounds
or automatic dark mode in SenseCraft.

## 5. Durable configuration and migration

Use ignored files in the project root:

| File | Responsibility |
| --- | --- |
| `sensecraft.local.json` | Display preferences and calendar mapping |
| `sensecraft.connection.local.json` | API key, Google connection/session and resource IDs |
| `.private/` | Regenerable cache, previews, generated layouts and recovery artifacts |

Use `sensecraft.connection.local.json` as the canonical API-key store.
Support existing `.env` values through migration and explicit environment
overrides, with documented precedence and no unnecessary divergent copies.

Migrate the existing combined configuration without losing preferences
or valid connections. Use atomic writes and restrictive permissions for
secrets, including `0600` for the connection file.

Deleting `.private/` must allow rebuilding from durable root configuration,
without recreating valid authentication or user preferences.
Expired/revoked sessions still require reconnection.

Version only public-safe examples. Preserve the last successfully published
configuration for recovery and distinguish it from local unsent edits.

## 6. Configuration interface and template behavior

Use the approved panel design as the visual reference, with clean,
readable controls and no unnecessary implementation details in user flows.
Keep the template name device-independent: Google Calendar Today or
Multi Calendar.

### Calendar and presentation options

- Select 1–10 calendars from the authenticated user's Google calendar list,
  including owned and subscribed calendars.
- Set initials and a custom color for each selected calendar.
- Offer four marker modes: dot, initials, both or neither; default to both.
- Offer Italian, English, French, German and Spanish.
- Select a city and timezone.
- Always show the clock; make timezone display optional.
- Make sunrise, sunset, moon phase and battery independently optional.
- Show sunrise/sunset for each displayed day; show moon phase for the current
  day with a recognizable waxing/waning indication.
- Preserve any additional settings already supported by the template.
- Use a compact aligned header, localized weekday and numeric date.
  Keep the approved uppercase accent styling for today's appointments.

### Backgrounds and light/dark settings

Keep the approved artwork, cleaned of sample appointments and interface text:

- White/base and dark/base.
- Floral, unicorn and LGBTQ themes.
- Four seasonal themes.
- Twelve monthly backgrounds.
- Easter, Christmas, Epiphany, Halloween and Italian Carnival themes,
  including the approved Italian Carnival characters.
- Corresponding dark variants.

Offer manual theme selection, or automatic monthly/seasonal selection.
Make special-date overrides independently selectable in automatic mode:
months with/without holidays, seasons with/without holidays.

Maintain these holiday rules:

| Holiday | Override |
| --- | --- |
| Epiphany | January 6 |
| Easter | Easter Sunday |
| Carnival | Shrove Tuesday, Easter minus 47 days |
| Halloween | October 31 |
| Christmas | December 24–26 inclusive |

Offer background intensity as an integer from 0 to 100, with one-point
increments. Prefer a white/light or black/dark overlay so multiple intensity
versions of each image are unnecessary. If the renderer cannot support
this, verify the limitation and use the previously approved discrete-image
fallback, documenting any reduction in granularity.

Offer light, dark or automatic mode based on sunrise/sunset, independent
of manual or automatic background selection. Use the selected location,
timezone and date with the supported solar data source.

Theme and dark-mode decisions must run inside the SenseCraft render at
normal refresh. No exact-transition scheduled refresh or always-running
local application is required.

### Event layout

- Keep active timed events until their end time, rather than hiding them
  after their start. Show no already-ended timed events for today.
- Preserve all-day and multi-day behavior and the selected-calendar filter.
- Keep start-time text at its fixed approved size. Show end time below it,
  smaller and visually secondary, on every displayed day.
- Let titles use the supported horizontal field. Reduce only title text,
  within the approved limited range, then fade overflow.
- Keep calendar markers aligned right, without changing time text size.
- Use available vertical space without an arbitrary event-count cap.
- Show subsequent days when space remains, preserving readable spacing.
- Keep battery background transparent and text/icon readable in dark mode.
  Missing battery shows an unavailable indicator; zero remains `0%`.

For behavior impossible inside SenseCraft, exhaust supported approaches
first, record exact evidence and keep the limitation in TODO for future
firmware/self-hosted work. Do not silently remove a requirement or add a
permanent service to simulate support.

## 7. API key and native Google setup

When the API key is missing:

1. Explain that a SenseCraft connection is required.
2. Offer a button to the verified key-management page.
3. Provide a masked paste field.
4. Validate using a non-mutating request.
5. Save in the ignored connection configuration.

Do not ask users to edit JSON, cookies or session IDs during ordinary setup.

Use SenseCraft's native Google OAuth flow. Investigate whether redirects
can integrate directly with the local app; do not assume unverified support.
Where necessary provide a guided native-browser flow.

Do not introduce an independent hosted Google OAuth application.
Handle missing, invalid, expired and revoked connections, and allow
reconnection and calendar-list refresh. Existing valid consent should be reused.

## 8. Preview, save and private publication

| Action | Behavior |
| --- | --- |
| Preview | Render current unsaved form values without changing the private page |
| Save | Persist local configuration only |
| Publish to SenseCraft | Confirm “Salva e pubblica”, then save locally and publish privately |

Preview must use the actual rendering path rather than a static mockup.
Keep preview generation separate from private-page mutation.

On publication, save local configuration, upload necessary resources,
create/update the private page, preserve relevant existing editor metadata,
and refresh the selected device. Display progress, clear errors and results.

Handle partial failures and safe retries without unnecessary duplicate
pages or uploads. Keep recoverable state and the last published configuration.

Do not treat a successful write response as complete integration proof.
Read back the saved resources, page and device assignment/snapshot.

## 9. Complete autonomous QA

Tests are explicitly authorized. Maintain a traceable matrix linking every
requirement/control/option to its expected result, executed check and outcome.

Run automated checks and use the browser as an application QA tester.
Exercise every individual control and selectable option, plus representative
combinations. Use controlled dates/data for difficult temporal scenarios
and label simulated results separately from live integration.

The coverage matrix must include:

- First launch, fresh installation and existing configuration.
- Every input, selection, toggle and validation rule.
- Restart persistence, migration and reconstruction after deleting `.private/`.
- Unsaved preview with no local promotion or private-page modification.
- Local save with no publication.
- Publication confirmation, cancellation, success and partial-failure recovery.
- Calendar minimum/maximum, ownership/subscriptions, mapping and colors.
- All four calendar-marker modes and layout interaction.
- All five languages, city/timezone changes and always-visible clock.
- Every theme, each light/dark pair and optional holiday overrides.
- Monthly/seasonal transitions, holiday boundaries and solar day/night changes.
- Intensity endpoints and intermediate values, including one-point increments.
- Each independent solar/moon/battery option.
- Active, ended, all-day and multi-day events.
- Long event titles, an empty agenda and a list exceeding screen capacity.
- Subsequent-day filling and stable time-column typography.
- Missing battery, zero battery and dark-mode battery contrast.
- Missing/invalid keys, expired/revoked Google connection and setup retry.
- Network/API failures, safe retries and interrupted publication.
- Occupied port, default-browser opening, browser-opening failure and shutdown.
- No reusable-template dependency and no public publication.
- Secret/personal-data exclusion from tracked artifacts and ordinary UI.
- Runtime operation after the local configurator shuts down.

Use computer control where needed to verify default-browser launch, native
OAuth or behavior outside the web page. Fix failures and rerun affected checks.

Run authorized live integration against the private account/device while
preserving a useful configuration. Use readbacks and, where available,
renderer snapshots to verify template autonomy.

Distinguish automated fixtures, browser rendering, API acceptance, remote
snapshot and physical display proof. Do not claim the last without evidence.
An inaccessible external service or physical observation remains explicitly
unverified rather than a fabricated pass.

## 10. Documentation, second PR and merged-main verification

Document startup, settings, connections, preview, save, private publication,
recovery and actual limitations.

For every new SenseCraft API finding, update together:

- `docs/sensecraft-hmi-api.md`: date, evidence and source type.
- `docs/mcp-implementation-brief.md`: consequence for a future MCP.

Distinguish official docs, web-client observations, live probes and
unverified hypotheses. Keep this work useful for arbitrary future templates,
not just the calendar.

Update the rebuild runbook, canonical publication diagram, README,
TODO and CHANGELOG. Maintain README contents. Run required Markdown lint,
`shellcheck --enable=all` on changed shell scripts and appropriate
code/lint/test checks after the final relevant edit.

When implementation and QA are complete, run scoped remediation until
`READY`, commit, push and open PR 2 toward `main`; attach it to the task.
Use the relevant CHANGELOG notes for its title/body.

Run the Codex PR review/remediation loop on PR 2 until the exact current HEAD
is clean, all required checks pass and actionable findings are resolved.
Do not merge around review gates.

After merging, validate the resulting `main` with appropriate automated
checks and a browser smoke test of the operational flow.

## 11. Iteration policy and completion audit

Between iterations retain what changed, evidence obtained, outstanding
findings and the next useful action. Re-read this specification after a
resume or context transition. Continue useful independent work when one
external dependency is unavailable.

Do not ask for ordinary technical decisions. If an external obstacle makes
further progress impossible, report attempted paths, evidence, the precise
blocker and what would unlock progress. Preserve recoverable state.
Do not mark the Goal complete while required work remains.

Complete only when:

- Both PRs are reviewed and merged into `main`.
- One documented command launches the application.
- Every supported approved option is implemented and verified.
- Private publication and autonomous SenseCraft runtime are tested.
- Durable settings survive reconstruction of disposable artifacts.
- Secrets and personal data remain excluded from Git.
- Documentation is reconciled, lint passes and tests pass.
- Final delivery includes the launch command, both merged PR links,
  concise QA evidence and actual remaining limitations.

## Official Goal guidance

Checked on 2026-09-30:

- [Developer commands](https://developers.openai.com/codex/developer-commands):
  objectives must be non-empty and at most 4,000 characters; put longer
  instructions in a file and point the Goal at it.
- [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex):
  define outcome, verification, constraints, boundaries, iteration policy
  and a blocked stop condition; completion requires evidence.
- [Desktop slash commands](https://learn.chatgpt.com/docs/reference/slash-commands):
  start with `/goal`; the app provides controls to manage the active Goal.
