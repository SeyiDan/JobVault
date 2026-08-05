/**
 * Unit tests for escape.js. Run with:  node --test test/
 *
 * These pin the exact bug the previous esc() had: it did not escape the double
 * quote, so a scraped value could break out of an HTML attribute.
 */
const { test } = require('node:test');
const assert = require('node:assert');
const { escHtml, escUrl } = require('../escape.js');

test('escHtml escapes the double quote (the attribute-breakout char)', () => {
  assert.ok(escHtml('a"b').includes('&quot;'));
  assert.ok(!escHtml('a"b').includes('"'));
});

test('escHtml escapes all five significant characters', () => {
  assert.strictEqual(escHtml(`&<>"'`), '&amp;&lt;&gt;&quot;&#39;');
});

test('escHtml neutralizes an attribute-breakout XSS payload', () => {
  // Placed in an attribute: title="${escHtml(payload)}". The attack works only
  // if a raw quote survives to close the attribute early. Once every quote is
  // encoded, the rest is inert text inside the title, not markup.
  const payload = 'Engineer" onmouseover="steal()';
  const out = escHtml(payload);
  assert.ok(!out.includes('"'), 'no raw quote may survive to break out of the attribute');
  const rendered = `<a title="${out}">x</a>`;
  assert.strictEqual(rendered.match(/"/g).length, 2, 'exactly the two delimiter quotes remain');
});

test('escHtml handles null and undefined without throwing', () => {
  assert.strictEqual(escHtml(null), '');
  assert.strictEqual(escHtml(undefined), '');
});

test('escUrl blocks the javascript: scheme', () => {
  assert.strictEqual(escUrl('javascript:alert(1)'), '');
  assert.strictEqual(escUrl('  JavaScript:alert(1)'), '');
});

test('escUrl blocks data: and unknown schemes', () => {
  assert.strictEqual(escUrl('data:text/html,<script>'), '');
  assert.strictEqual(escUrl('vbscript:msgbox'), '');
});

test('escUrl passes http(s) and mailto through, escaped', () => {
  assert.strictEqual(escUrl('https://example.com/x'), 'https://example.com/x');
  assert.ok(escUrl('https://x/?a="b').includes('&quot;'));
  assert.strictEqual(escUrl('mailto:a@b.com'), 'mailto:a@b.com');
});
