# SenseCraft HMI API and MCP Handoff

API research, template sources and implementation instructions for SenseCraft
HMI. The repository includes the implemented Google Calendar Today template;
it does not contain an MCP server implementation.

## Table of Contents

- [API field notes](docs/sensecraft-hmi-api.md)
- [MCP implementation brief](docs/mcp-implementation-brief.md)
- [Agenda rebuild runbook (Italian)](docs/sensecraft-agenda-rebuild.md)
- [Private publication workflow and diagram](docs/sensecraft-private-publication.md)
- [Template sources (Italian)](templates/README.md)
- [TODO](TODO.md)
- [Changelog](CHANGELOG.md)
- [Source and installation boundaries](#source-and-installation-boundaries)
- [License](LICENSE)

## Source and installation boundaries

Reusable code and runtime artwork are versionable under
`templates/google-calendar-today/`. Editable installation settings live in
ignored `sensecraft.local.json` at the project root; the API key is in ignored
`.env`. Generated layouts, caches and API captures remain in ignored `.private/`.
The template's settings are supported through an API helper; its graphical
preferences panel remains a design proposal.

## Evidence scope

The documents distinguish official platform documentation, behavior observed in the public web application's JavaScript bundle, authorized live API probes, inspected renderer output, and account writes. The service does not publish an OpenAPI specification in the sources examined. Undocumented request and response details are explicitly marked for verification.

## License

Original project documentation and artwork are licensed under [CC BY 4.0](LICENSE).
Template code is licensed under [MIT](templates/google-calendar-today/LICENSE).
These licenses do not apply to Seeed's services, trademarks, or third-party
content cited here.
