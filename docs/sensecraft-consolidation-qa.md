# Private agenda consolidation: verification

Verified on 2026-09-30. This covers the CLI/private-page consolidation;
the graphical configurator is a separate delivery phase.

## PR unit

| Field | Contract |
| --- | --- |
| Behavior | Restore/update an existing private agenda without a reusable template |
| Boundary | Versioned source/artwork, durable root configuration, private uploads/page/device refresh |
| Acceptance | Lossless migration, removable generated state, private-only persistence, editor metadata preserved, native preview and snapshot readback |
| Non-goals | Graphical configurator, new-account wizard, public sharing, MCP, other display profiles |
| Dependency | The next PR adds a GUI; this CLI behavior is complete independently |

## Executed checks

| Requirement | Evidence | Result |
| --- | --- | --- |
| Durable migration | Tests for separated credentials, empty connection values and interrupted-write retry | Pass |
| Disposable generated state | Remove generated state in a temporary fixture; preferences and connections remain available | Pass |
| Private page only | Mocked persistence records no template routes | Pass |
| Editor metadata | Fixture preserves stage size, editor metadata, unrelated children/root nodes; removes only legacy battery | Pass |
| Preview isolation | Fixture proves preview-only sends no thumbnail upload/page save and does not promote the persisted expectation | Pass |
| Production/privacy checks | Explicit exceptions; 11 Python tests pass normally and with `-O` | Pass |
| Runtime semantics | 53 checks pass on source and uploaded production artifact, including active-event end, day +4 and 100 events | Pass |
| Artwork inventory | SHA-256 matches for 48 backgrounds; dimensions match across 24 light/dark pairs | Pass |
| Artwork visual inspection | Light/dark contact sheets for all themes/months inspected; no embedded UI/event text observed | Pass |
| Credential privacy | Actual local key/session/calendar values absent from versionable text; both persistent files mode 0600 | Pass |
| Native preview | Actual SenseCraft production render inspected; transparent dark battery, times, markers and readable text | Pass |
| Private publication | Page saved and exact-read back; refresh accepted; assigned snapshot equals the reconciled persisted layout | Pass |
| Subsequent live read | Configured calendar events read successfully; deployed snapshot rendered again | Pass |
| Code/docs lint | Ruff check/format, Markdown lint and whitespace checks | Pass |
| Independent review | Three substantive findings fixed and re-reviewed; stale forecast documentation corrected | Pass |

Private API captures, previews, backups and resource identifiers remain in
ignored state. The portable candidate is a sanitized local export, not a
public or reusable template submission.

## Findings closed

- Recoverable migration writes the connection before removing legacy bindings
  from preferences; both files have owner-only permissions.
- Private page persistence has no dependency on the withdrawn template.
- Ten-calendar probing is optional; the normal verifier reads the selection.
- Persistence records `persisted-private.json` after exact readback, so snapshot
  verification includes preserved editor metadata rather than the build canvas.
- Operational guards remain effective under optimized Python.
- Future events have no fixed three-day normalization cutoff. Missing solar
  forecast dates are unavailable; no invented times are presented.

## Evidence boundaries

These results establish local tests, inspected native rendering and API/snapshot
verification. They do not establish a newly observed physical-screen refresh.
The full configurator QA matrix and final merged-main validation remain required
by the [delivery specification](sensecraft-configurator-goal.md).
