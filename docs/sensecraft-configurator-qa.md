# Google Calendar Today configurator: QA record

This matrix records checks made on 2026-09-30 for the local configurator and
the `800×480` E1002 profile. Browser cases used the actual UI. Fictional
fixture accounts exercised failure paths; the private integration used the
existing account and display. Private captures and the full 141-case browser
ledger are kept under ignored `.private/configurator-qa/`.

## Evidence levels

| Level | Meaning |
| --- | --- |
| Unit/fixture | Controlled Python or JavaScript behavior; no upstream proof |
| Browser | Control, state and responsive UI observed in the local browser |
| Render | Actual `/render/preview` returned a PNG for the submitted layout |
| API/readback | SenseCraft page and device state read after writes |
| Service snapshot | Assigned layout and service image; no physical screen observation |

All 141 browser cases passed. The theme filters were counted by **visible**
cards: 12 months, 14 other themes, 26 total. Hidden cards remain in the DOM.

## Control and behavior matrix

| Requirement or control | Executed check | Result |
| --- | --- | --- |
| Start, loopback binding, occupied port, URL, browser failure and shutdown | Unit/fixture; native Safari opened the actual local URL; Ctrl-C stopped the server | Pass |
| Host, Origin, JSON and CSRF protections; path traversal | HTTP unit/fixture negative cases | Pass |
| Missing/invalid API key, masked input, read-only validation and account isolation | Browser onboarding; unit/fixture key rotation and write failure | Pass |
| Native Google connection, expired state and reconnect guidance | Browser; existing consent reused by live API | Pass |
| Guided import from saved native private page | Browser and live validation of imported session | Pass |
| Provider callback nonce, cookie, expiry and replay | HTTP fixture | Pass in fixture; complete provider return unverified |
| Device and private page selectors; list placeholder resolution | Browser, live detail read and unit/fixture | Pass |
| Calendar refresh, search, owned/subscribed selection | Browser and real account list | Pass |
| One to ten calendars, zero and eleventh rejected | Browser; unit/fixture validator | Pass |
| Per-calendar initials/color, mapping retained after search | Browser; unit/fixture | Pass |
| Marker: both, initials, dot, neither | Four browser options; compiled renderer checks | Pass |
| Italian, English, French, German, Spanish | Five browser options; source and production semantics | Pass |
| City search and selection; timezone validation | Browser; unit/fixture city and invalid zone | Pass |
| Clock always visible; optional timezone label | Browser toggles and source semantics | Pass |
| Independent sunrise, sunset, moon and battery toggles | Eight browser states; renderer semantics | Pass |
| Battery zero, unavailable and dark contrast | Controlled renderer checks; live preview showed available battery after ID fix | Pass |
| Manual gallery: 26 themes, each in light and dark | 52 browser selections, loaded image thumbnails | Pass |
| Automatic months/seasons with holiday override on/off | Four browser combinations; controlled date checks | Pass |
| Hemisphere auto/north/south and Carnival rule | Five browser choices; controlled date checks | Pass |
| Solar automatic mode and both missing-data fallbacks | Browser and controlled renderer checks | Pass |
| Intensity 0–100, intermediate values, number arrows, slider keyboard | Browser endpoints/intermediates and one-point steps; validator | Pass |
| Title and minimum font 24–32, invalid bounds | Browser options and negative case; renderer semantics | Pass |
| Birthday exclusion and preservation of other all-day events | Browser toggle and controlled renderer checks | Pass |
| Active vs ended events, multi-day events, long titles and fade | Controlled source and compiled renderer semantics | Pass |
| Subsequent-day fill without event-count cap; fixed time font | Controlled renderer checks | Pass |
| Unsaved native preview, stale marker and no page mutation | Browser; unit/fixture; live renderer PNG | Pass |
| Save locally without remote publication | Browser; unit/fixture | Pass |
| Publish dialog, focus, cancel, confirm and progress | Browser and HTTP fixture | Pass |
| Existing private page update, assignment and snapshot | Live API/readback and service snapshot | Pass |
| Fresh page create, exact name and lost-create reconciliation | First-install browser fixture; unit/fixture | Pass in fixture; live fresh-account create unverified |
| Partial deploy retry, uncertain upload and explicit recovery | Browser fixtures and unit/fixture | Pass |
| Browser reload during job and durable last-published recovery | Browser; unit/fixture | Pass |
| Restart settings and legacy migration | Browser persistence; unit/fixture | Pass |
| Delete disposable `.private/` and reconstruct | Unit/fixture plus isolated copy of durable configs; no upload call | Pass |
| Desktop/mobile width and two-to-one-column layout | Browser viewport checks | Pass |
| No reusable template or public publication | Live API page-only flow and resource inspection | Pass for existing installation |
| Private data excluded from tracked files and UI | Diff audit; key masked; ignored local artifacts | Pass |
| Runtime after configurator shutdown | Local port closed, then live `/render/preview` and assignment/snapshot verification | Pass at service level |

## Integrated validation

The authorized live publication retained the prior preferences, saved the
private page, verified its exact readback, refreshed the assigned display and
verified the device snapshot. The shared CLI verifier independently reconciled
selected calendar reads, assignment and saved layout. After the local panel
stopped, SenseCraft rendered the persisted layout again as PNG. The uploaded
source document uses HTTPS resources and has no localhost dependency.

The isolated reconstruction copied only the two ignored root JSON files into a
temporary directory with no `.private/`. It recreated the compiled layout from
the durable upload cache, retained preferences and valid Google session, and
made zero upload calls. The original private state was left intact.

The physical display was not observed during this QA run. The complete Google
provider consent-to-loopback return and a live fresh-account creation remain
unverified. Native-page import was verified as the working Google fallback;
first installation and create recovery passed with controlled fixtures.

## Commands

```sh
python3 -m unittest discover -s templates/google-calendar-today/tests
node templates/google-calendar-today/scripts/check.js
node templates/google-calendar-today/tests/check_frontend.js
ruff check templates/google-calendar-today/configurator templates/google-calendar-today/scripts templates/google-calendar-today/tests
ruff format --check templates/google-calendar-today/configurator templates/google-calendar-today/scripts templates/google-calendar-today/tests
```

These commands must be rerun after the final product edit and on merged `main`.
