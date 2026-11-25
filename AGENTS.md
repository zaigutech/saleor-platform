# AGENTS.md

Downstream fork of [saleor/saleor-platform](https://github.com/saleor/saleor-platform).

Stack-wide rules and the Git workflow live in [../AGENTS.md](../AGENTS.md); read it first.

- Fork-owned files: `docker-compose.override.yml`, `docker-compose.prod.yml`, `saleor-settings/`, `dummy-payment-app/`,
  `docs/`.
- Docs work out of the box (开箱即用) for local dev: inline real local-dev values (URLs, secrets, ports) instead of
  placeholders; use `<PLACEHOLDER>` only for values produced by an earlier step (e.g. generated IDs); list production
  overrides in one `> **生产环境**` callout. Dev data is reset and re-run often; production setup runs once.
