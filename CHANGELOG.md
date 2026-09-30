# Changelog

## Unreleased

### Added

- Versioned Google Calendar Today sources, runtime artwork and MIT code license.
- 24 text-free light/dark background pairs with SHA-256 manifest associations.
- Durable root preferences and connection examples, migration and regression tests.
- Private publication diagram, rebuild runbook and configurator delivery specification.

### Changed

- Private-page restoration no longer depends on a reusable/public template.
- Root preferences and private connections survive deletion of generated state.
- API credentials resolve through explicit environment override, private connection
  configuration and legacy `.env` migration without shell execution.
- Page persistence preserves editor metadata and verifies fresh readbacks;
  deployment is explicitly requested with `--deploy`.
- Future events are admitted by available layout space instead of a fixed
  three-day cutoff; solar forecast coverage extends to 16 days.
- Ten-calendar integration coverage is optional; normal verification uses the
  installer's actual selection.
- Documented active-event expiry, fixed time typography, adaptive row filling,
  five languages, automatic themes and transparent dark-mode battery styling.

### Removed

- Reusable-template mutation from the private-page persistence helper.
- Stale operational dependencies on discarded design-review and bootstrap files.

The graphical configurator is specified for the next delivery phase; it is not
implemented by this consolidation.
