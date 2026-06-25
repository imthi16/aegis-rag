# Threat Model

> Source: [`../CLAUDE.md`](../CLAUDE.md) §0, §9. Expanded as security-relevant
> modules (auth/RBAC §6.3, audit §6.15) land.

## Assets

- Regulated document corpus and its classifications.
- Audit trail (must be tamper-evident).
- Secrets: `JWT_SECRET_KEY`, `AUDIT_HMAC_KEY`, DB credentials.

## Trust boundaries

- Browser ↔ nginx ↔ backend ↔ (Postgres, Ollama, FAISS) — all backend
  dependencies live on the private `aegis_net`; the airgap overlay removes
  external DNS and published ports (Golden Rule 1).

## Threats & mitigations (initial)

| Threat | Mitigation |
|---|---|
| Data exfiltration via model/telemetry callouts | Zero egress; `HF_HUB_OFFLINE=1` et al. set before import; airgap network overlay |
| Cross-classification leakage in answers/citations | RBAC enforced at the retrieval candidate set (§6.3, §6.9), re-asserted on hydrate |
| Audit tampering | Hash-chained + HMAC `audit_log`; `aegis_audit` role has INSERT/SELECT only; verifier endpoint |
| Hallucinated/unsupported answers | CRAG correction + faithfulness grading; mandatory citations; explicit "insufficient evidence" |
| Secret leakage | Secrets only in `.env`; never logged; prod refuses placeholder secrets |
| Token theft | Short-lived access tokens; refresh rotation/revocation; in-memory storage on client |
| Privilege escalation | `require_roles` gates; fail-closed on auth/RBAC errors |

## Open items (tracked as modules land)

- Rate limiting (`slowapi`) on auth + query endpoints.
- Upload validation (type/size) and parser hardening.
- Append-only DB trigger on `audit_log`.
