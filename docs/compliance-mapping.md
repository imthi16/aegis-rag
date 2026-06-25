# Compliance Field Mapping

> Source: [`../CLAUDE.md`](../CLAUDE.md) §11. Each audited action maps to at
> least one framework below. Expanded as the audit subsystem (§6.15) lands.

| Framework | Control | How Aegis RAG satisfies it |
|---|---|---|
| **HIPAA** | §164.312(b) Audit controls | `audit_log` append-only hash chain; `query.executed` / `document.*` records with actor, resource, outcome, timestamp; `verify_chain` integrity attestation |
| **EU AI Act** | Art. 12 Record-keeping | Automatic event logging over the lifecycle → `audit_log` + `query_log` |
| **EU AI Act** | Art. 13 Transparency | Citations + faithfulness score + EvidencePanel expose the basis of each answer |
| **DORA** | ICT risk, logging, resilience | Structured logs, audit trail, health/readiness probes, deterministic offline operation |
| **GDPR / FADP / PDPL** | Data minimization, locality | All processing on-premise; no egress; least-privilege DB roles; classification + RBAC; logs avoid PII payloads |
| **DIFC Reg 10 / FINMA** | Auditable access control, tamper-evidence | RBAC at retrieval; hash-chained records; admin role separation; `/audit/export` |

## Audited actions (minimum)

`auth.login`, `auth.login_failed`, `auth.refresh`, `auth.logout`,
`document.ingested`, `document.deleted`, `query.executed`, `query.denied`,
`role.assigned`, `role.revoked`, `audit.verified`, `eval.run`.

> Rule of thumb: if an action grants access to, modifies, or produces regulated
> content, log it (fail-closed) and map it here.
