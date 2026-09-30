# Google Calendar Today configurator

Local Python web application for configuring and privately publishing the agenda.
The installed HTML runs in SenseCraft after this application stops.

## Table of Contents

- [Launch](#launch)
- [Connect and configure](#connect-and-configure)
- [Preview, save and publish](#preview-save-and-publish)
- [Storage and recovery](#storage-and-recovery)
- [Validation](#validation)
- [Evidence and limits](#evidence-and-limits)

## Launch

From the repository root, on macOS or Linux with Python 3.10+ and IANA timezone data:

```sh
python3 templates/google-calendar-today/configurator
```

No Python package installation or local login is required. The standard-library
server binds only to `127.0.0.1`, opens the default browser and prints the URL.
An occupied port falls back to an available port. If automatic browser opening
fails, open the printed URL manually. Stop with Ctrl-C; interrupted publication
keeps its durable progress for retry.

```sh
python3 templates/google-calendar-today/configurator --port 8766
python3 templates/google-calendar-today/configurator --no-browser
```

The validated display profile is E1002, `800×480`, dither `3`. Incompatible
devices remain visible but cannot be selected. Do not run the CLI helpers
concurrently against the same installation. Configurator processes serialize
complete operations and durable writes with private advisory lock files beside
the connection JSON; a competing operation receives a busy response. Do not
remove those lock files while a process is running.

## Connect and configure

1. Open **Configura o aggiorna le connessioni**.
2. If necessary, use **Apri gestione API Key**. In SenseCraft choose
   **User Profile → Account & Security → API Key**, then paste the key into
   the masked field and choose **Verifica e collega**. It is validated by a
   read-only profile request and saved locally; the saved value is never returned
   to the browser.
3. Choose **Collega Google**. Existing valid authorization is reused.
   Otherwise follow **Autorizza con Google**. If the browser does not return,
   use SenseCraft's native private-page editor to connect Google Calendar and
   save that page. Return here, refresh pages, select the page under
   **Pagina con Google collegato**, and choose **Importa connessione**.
4. Select the display. Keep the existing agenda destination or select a saved
   compatible agenda page. Without an existing destination, publication creates
   a private page named **Google Calendar Today**.
5. Select 1–10 owned or subscribed calendars and set each one's initials and
   color. Choose dot, initials, both or neither.
6. Configure language, city/timezone, optional indicators, themes, intensity,
   light/dark/solar behavior and title-size bounds. Disabled controls preserve
   their previous values. The clock is always visible.

The five agenda languages affect dates and labels, not event titles. City
search uses Open-Meteo and stores its coordinates/timezone. Solar mode and
monthly/seasonal/holiday rules execute in SenseCraft on its normal refresh;
they do not need a local scheduler. Background intensity is an integer 0–100,
with slider and number arrows. Calendar markers and the start-time font remain
independent of title fitting.

## Preview, save and publish

| Action | Effect |
| --- | --- |
| **Genera anteprima** | Render unsaved form values through SenseCraft; no preference promotion or page/device mutation |
| **Salva locale** | Persist preferences and selected device locally; no publication |
| **Salva e pubblica** | Confirm local save plus private page publication and display refresh |

Preview may upload missing source/artwork and cache their URLs. The displayed
PNG comes from the actual renderer. Editing after a preview marks it stale.
Publication uploads required media/thumbnail, preserves existing editor metadata,
saves the private page, reads it back, deploys and verifies the assignment and
snapshot. Nothing is published to the marketplace.

Progress and classified errors appear in the panel. Cancellation in the dialog
performs no publication. A browser reload rejoins an active in-process job;
if the process stopped, retry the pending publication with the same saved values.
The last successful publication date survives restart.

## Storage and recovery

| Location | Contents |
| --- | --- |
| Root `sensecraft.local.json` | Preferences and calendar mapping |
| Root `sensecraft.connection.local.json` | API key, Google session, resource IDs, durable upload cache/journal and last published settings |
| `.private/native-agenda/` | Regenerable compiled document, layouts, previews and private backups |

Both root JSON files are ignored and written atomically with `0600` permissions.
The prior combined configuration and legacy `.env` key are migrated. Key
precedence is explicit `SENSECRAFT_API_KEY` → connection JSON → legacy `.env`.
The `.env` file is parsed as data and never sourced. A pasted replacement key is
refused while a different explicit environment override is active. Switching
accounts isolates prior resource/session/cache bindings in a private recovery
history instead of sending them to the new account.

Deleting `.private/` allows reconstruction from the durable files without losing
valid authorization or preferences. Last-published recovery is a confirmed local
action; it does not change the remote page. Publication resumes its durable
journal and reconciles readback before repeating writes. A fresh page uses a
unique temporary name during creation recovery, then the exact final name.

An upload with a lost response stops automatic retry. **Gestisci upload incerto**
requires confirmation before clearing only incomplete local upload intents.
A remote orphan may remain: no reliable upstream upload inventory/idempotency
contract was verified. Completed uploads and account pages are preserved.
Remote removal and Google revocation remain manual actions in SenseCraft/Google.

## Validation

```sh
python3 -m unittest discover -s templates/google-calendar-today/tests
node templates/google-calendar-today/scripts/check.js
node templates/google-calendar-today/tests/check_frontend.js
```

Isolated simulated browser scenarios, with fictional account data:

```sh
python3 templates/google-calendar-today/tests/test_frontend.py --serve-ui-fixture
python3 templates/google-calendar-today/tests/test_frontend.py --serve-ui-fixture --scenario fresh
```

Other scenarios: `expired`, `uncertain`, `slow`, `deploy-fail`. Their thumbnail
PNG is a fixture, not remote-render proof. Stop each fixture with Ctrl-C.
See the [QA matrix](../../../docs/sensecraft-configurator-qa.md) for actual evidence.

## Evidence and limits

- Local HTTP mutations require exact Host/Origin, JSON and a per-server CSRF
  token. No CORS or panel login is exposed. OAuth uses an expiring nonce and
  same-browser HttpOnly cookie; provider callback errors are redacted.
- Native OAuth accepts a loopback redirect request, but full provider return
  support is recorded separately in the [API notes](../../../docs/sensecraft-hmi-api.md).
  The guided native-page import is the supported fallback.
- Source/snapshot equality proves service-side publication, not physical display
  refresh. The clock corresponds to the most recent render.
- Lunar phase is approximate. Polar/missing solar data uses the selected fallback
  light/dark mode. Later dates without forecast data show unavailable solar times.
- The battery key is included only in the private layout fragment, not the
  uploaded HTML source. Protect account layouts as credentials; never export
  private fragments or screenshots to Git.
