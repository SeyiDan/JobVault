/**
 * Output-encoding helpers for untrusted strings (job titles, companies, tags,
 * and other fields scraped from arbitrary third-party pages or imported from a
 * user-supplied file).
 *
 * Why this file exists: the previous per-file esc() built a text node and read
 * back innerHTML. That escapes &, <, and > but NOT the double quote, because a
 * quote only needs escaping when a string is serialized inside an attribute
 * value, and text-node serialization never does that. So esc() was safe in text
 * position but broken inside href="..." / title="..." / data-*="...", where a
 * scraped value like  ">" onmouseover="..."  could break out of the attribute.
 *
 * escHtml escapes all five HTML-significant characters and is correct in both
 * text and attribute context. escUrl additionally rejects any scheme that is not
 * http(s) or mailto, closing off javascript: URIs in href.
 */
(function (root) {
  var HTML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

  function escHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return HTML[c];
    });
  }

  var SAFE_SCHEME = /^(https?:|mailto:)/i;

  function escUrl(value) {
    var s = String(value == null ? '' : value).trim();
    // Allow protocol-relative and root-relative URLs; reject everything with an
    // unsafe or unknown scheme (javascript:, data:, vbscript:, ...).
    if (s.startsWith('//') || s.startsWith('/')) return escHtml(s);
    if (SAFE_SCHEME.test(s)) return escHtml(s);
    return '';
  }

  var api = { escHtml: escHtml, escUrl: escUrl };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;         // Node (unit tests)
  }
  root.JV = api;                  // browser (extension pages)
})(typeof self !== 'undefined' ? self : this);
