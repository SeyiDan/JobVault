# Security Audit: JobVault

A self-conducted security review of the JobVault backend (FastAPI) and its MV3
Chrome extension. Each finding has a proof-of-concept or a regression test.

- **Regression tests:** `cd backend && pytest -m security` (8 tests), plus
  `node --test test/escape.test.js` (7 tests) for the extension.
- **Full backend suite:** 16 → 24 passing.
- **CI gate:** `.github/workflows/security.yml` runs Semgrep, Trivy, gitleaks,
  pip-audit, and an ESLint `no-unsanitized` pass, and blocks HIGH+ findings.

## Findings

| ID | Finding | CWE | Severity | Evidence |
|----|---------|-----|----------|----------|
| JV-01 | Stored XSS: `esc()` did not escape `"`, so scraped/imported data broke out of HTML attributes | [CWE-79](https://cwe.mitre.org/data/definitions/79.html) | **High** | `security/poc/xss-poc.md`, `test/escape.test.js` |
| JV-02 | Backend booted with a known placeholder JWT signing key | [CWE-798](https://cwe.mitre.org/data/definitions/798.html) | High | `test_settings_rejects_placeholder_secret` |
| JV-03 | Malformed token subject (`UUID(sub)`) returned HTTP 500 | [CWE-703](https://cwe.mitre.org/data/definitions/703.html) | Medium | `test_malformed_subject_returns_401_not_500` |
| JV-04 | `/jobs/import` read unbounded, no content-type check, crashed on bad input | [CWE-400](https://cwe.mitre.org/data/definitions/400.html) | Medium | `test_import_rejects_oversized_file`, `test_import_rejects_malformed_json` |
| JV-05 | Dependencies fully unpinned; a clean install and scan were not reproducible | [CWE-1104](https://cwe.mitre.org/data/definitions/1104.html) | Low | `backend/requirements.txt` now pinned |
| JV-06 | 24-hour token lifetime with no refresh or revocation | [CWE-613](https://cwe.mitre.org/data/definitions/613.html) | Low | lifetime cut to 60 min |

## JV-01, in detail (the headline)

Both `jobs.js` and `popup.js` defined an `esc()` that set `textContent` on a div
and read back `innerHTML`. Serializing a **text node** escapes `&`, `<`, `>` but
**not** the double quote, because a quote is only significant inside an attribute
value. `esc()` was therefore safe in text position and unsafe in attribute
position, and it was used in attribute position, e.g.

```js
`<a href="${esc(job.url)}" title="${esc(job.title)}">...`
```

The taint is real: `content.js` scrapes `innerText` from arbitrary third-party
job pages, and `POST /jobs/import` accepts an attacker-supplied file. A title of
`Engineer" onmouseover="..."` closes `title="` early and injects a live event
handler that can read the JWT out of `chrome.storage.local`. Full walk-through
and payload in `security/poc/`.

**Fix.** `escape.js` provides `escHtml` (escapes all five significant chars,
correct in text and attribute context) and `escUrl` (rejects any scheme but
http(s)/mailto, killing `javascript:` in `href`). Both `esc()` bodies delegate to
`JV.escHtml`; the `href` uses `escUrl` and gains `rel="noopener noreferrer"`.
`eslint-plugin-no-unsanitized` runs in CI so a new raw-`innerHTML` sink is caught
at lint time; the existing render sinks carry a reviewed `eslint-disable` line
each stating why they are safe.

## Notes on honesty

- **JV-04** hardens the endpoint; validating each row through the `JobCreate`
  schema instead of `.get()` chains is a further improvement not yet made.
- **JV-06**: shortening the lifetime is the mitigation available without building
  refresh-token rotation. There is still no revocation; a leaked token is valid
  until it expires.
- **Not yet addressed** (tracked, lower exploitability): password strength policy,
  `manifest.json` `<all_urls>` host permission, mass-assignment allowlist on job
  update, moving the token from `chrome.storage.local` to `session`, and the
  root-user backend Dockerfile. These are real and belong in a follow-up.
- **ecdsa PYSEC-2026-1325** from pip-audit is triaged as unreachable (HS256, not
  ECDSA) in `security/baseline.json` with an expiry, not silently muted.
