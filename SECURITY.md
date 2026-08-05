# Security Policy

## Reporting a vulnerability

This is a portfolio project, not a production service. If you find a security
issue, please open a GitHub issue describing it, or email the maintainer listed
on the profile. There is no bug bounty.

## What this repository does about security

- **CI security gate** (`.github/workflows/security.yml`): every push and pull
  request runs Semgrep (SAST), pip-audit (dependency CVEs), Trivy (filesystem +
  Dockerfile/compose misconfiguration), and gitleaks (committed secrets). A
  single gate job (`scripts/security_gate.py`) aggregates the results and fails
  the build on any finding of HIGH severity or above.
- **Accepted risks** are tracked in `security/baseline.json`. Each entry must
  carry a reason and an expiry date; the gate rejects entries that lack either
  or that have expired, so nothing is muted silently or forever.
- **Findings and fixes** are documented in [`SECURITY-AUDIT.md`](./SECURITY-AUDIT.md),
  one row per vulnerability, each with a proof-of-concept and a regression test.
- **Threat model**: [`docs/threat-model.md`](./docs/threat-model.md).

## Supported versions

The `main` branch only.
