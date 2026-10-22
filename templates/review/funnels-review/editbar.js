/* editbar.js — inline copy editing with named versions, for static pages.
 *
 * Nothing renders unless the page is opened with ?edit=<key> (remembered afterwards),
 * so ad traffic and clients never see it.
 *
 * Versions are non-destructive: the built HTML is always the base, and a version is a
 * set of overrides applied on top. Promote one into the build when you want it live.
 *
 * Storage is pluggable. Default is this browser only. Point STORE at 'remote' once
 * /api/versions is backed by a database and versions become shareable by URL.
 */
(function () {
  'use strict';

  var EDIT_KEY = 'shelly';           // shared secret, obfuscation not security, see README
  var STORE = 'local';               // 'local' | 'remote'
  var NS = 'sx-versions';
  var ALLOWED = /^(B|I|EM|STRONG|BR|SPAN|A|SUP|SUB|U|MARK|SMALL)$/;
  var SKIP = /^(SCRIPT|STYLE|NOSCRIPT|SVG|PATH|IMG|PICTURE|SOURCE|VIDEO|AUDIO|CANVAS|IFRAME|INPUT|SELECT|TEXTAREA|OPTION|LABEL|HEAD|META|LINK|TITLE)$/;

  var qs = new URLSearchParams(location.search);

  /* ---------- gate ---------- */
  var unlocked = false;
  try {
    if (qs.get('edit') === EDIT_KEY) { localStorage.setItem(NS + ':ok', '1'); unlocked = true; }
    else if (localStorage.getItem(NS + ':ok') === '1') unlocked = true;
    if (qs.get('edit') === 'off') { localStorage.removeItem(NS + ':ok'); unlocked = false; }
  } catch (e) { /* private mode */ }

  // Campaign traffic never sees the bar, even on an unlocked browser. Same rule the
  // page's internal nav follows: clicking your own ad must look like a customer's visit.
  var AD = /^(utm_|fbclid|gclid|ttclid|msclkid|twclid|li_fat_id|igshid)/i;
  var adClick = Array.prototype.some.call(Array.from(qs.keys()), function (k) { return AD.test(k); });
  if (adClick && qs.get('edit') !== EDIT_KEY) return;

  var viewing = qs.get('v');
  if (!unlocked && !viewing) return;

  /* ---------- stable, content addressed keys ---------- */
  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0).toString(36);
  }
  function norm(s) { return (s || '').replace(/\s+/g, ' ').trim(); }

  var nodes = [];      // {el, key, base}
  var byKey = {};

  // Take the deepest element that owns its text. A heading whose variants live in
  // child spans must not be editable as a whole, or editing it destroys the spans
  // the page switches between.
  function index() {
    nodes = []; byKey = {};
    var seen = {};
    Array.prototype.forEach.call(document.body.querySelectorAll('*'), function (el) {
      if (SKIP.test(el.tagName) || el.closest('#edbar') || el.closest('svg')) return;
      if (el.closest('[data-ed]')) return;                    // an ancestor already owns this text
      if (el.isContentEditable && !el.hasAttribute('data-ed')) { /* fine */ }

      var own = norm(Array.prototype.filter.call(el.childNodes, function (n) { return n.nodeType === 3; })
        .map(function (n) { return n.textContent; }).join(' '));
      if (own.length < 2) return;

      // children may only be inline formatting, otherwise this is a container
      var inlineOnly = Array.prototype.every.call(el.children, function (c) { return ALLOWED.test(c.tagName); });
      if (!inlineOnly) return;

      var k = el.tagName + ':' + hash(norm(el.textContent));
      seen[k] = (seen[k] || 0) + 1;
      if (seen[k] > 1) k += '#' + seen[k];
      el.setAttribute('data-ed', k);
      var rec = { el: el, key: k, base: el.innerHTML };
      nodes.push(rec); byKey[k] = rec;
    });
    return nodes.length;
  }

  /* ---------- storage ---------- */
  var Store = {
    local: {
      list: function () { try { return JSON.parse(localStorage.getItem(NS) || '[]'); } catch (e) { return []; } },
      save: function (all) { localStorage.setItem(NS, JSON.stringify(all)); return Promise.resolve(); },
      get: function (id) { return Promise.resolve(this.list().filter(function (v) { return v.id === id; })[0] || null); },
      put: function (v) { var a = this.list().filter(function (x) { return x.id !== v.id; }); a.push(v); return this.save(a).then(function () { return v; }); },
      del: function (id) { return this.save(this.list().filter(function (v) { return v.id !== id; })); },
      all: function () { return Promise.resolve(this.list()); }
    },
    remote: {
      base: '/api/versions',
      all: function () { return fetch(this.base + '?page=' + encodeURIComponent(page())).then(r => r.json()).then(d => d.versions || []); },
      get: function (id) { return fetch(this.base + '?id=' + encodeURIComponent(id)).then(r => r.json()).then(d => d.version || null); },
      put: function (v) { return fetch(this.base, { method: 'POST', headers: { 'content-type': 'application/json', 'x-edit-key': EDIT_KEY }, body: JSON.stringify(v) }).then(r => r.json()).then(d => d.version); },
      del: function (id) { return fetch(this.base + '?id=' + encodeURIComponent(id), { method: 'DELETE', headers: { 'x-edit-key': EDIT_KEY } }).then(r => r.json()); }
    }
  }[STORE];

  function page() { return location.pathname.replace(/\/$/, '') || '/'; }
  function uid() { return Date.now().toString(36) + Math.floor(Math.random() * 1e6).toString(36); }

  /* ---------- apply / collect ---------- */
  var current = null;   // the loaded version object
  var dirty = {};       // key -> html, edits made since load

  function applyEdits(edits) {
    var missing = 0, hit = 0;
    Object.keys(edits || {}).forEach(function (k) {
      var rec = byKey[k];
      if (!rec) { missing++; return; }
      rec.el.innerHTML = edits[k];
      rec.el.setAttribute('data-ed-changed', '1');
      hit++;
    });
    return { hit: hit, missing: missing };
  }

  function clean(el) {
    Array.prototype.forEach.call(el.querySelectorAll('*'), function (n) {
      if (!ALLOWED.test(n.tagName)) { n.replaceWith(document.createTextNode(n.textContent)); return; }
      Array.prototype.slice.call(n.attributes).forEach(function (a) {
        if (n.tagName === 'A' && a.name === 'href') return;
        if (a.name === 'class') return;
        n.removeAttribute(a.name);
      });
    });
  }

  /* ---------- editing ---------- */
  var editing = false;

  // The bar wraps to two or three rows on a phone, so reserve its real height
  // rather than a guess, or the last section of the page hides behind it.
  function reserve() {
    var h = bar ? bar.offsetHeight : 0;
    document.documentElement.style.paddingBottom = (editing || viewing) ? (h + 14) + 'px' : '';
  }
  window.addEventListener('resize', reserve);

  function setEditing(on) {
    editing = on;
    document.documentElement.classList.toggle('ed-on', on);
    nodes.forEach(function (rec) {
      if (on) {
        rec.el.setAttribute('contenteditable', 'true');
        rec.el.setAttribute('spellcheck', 'false');
      } else {
        rec.el.removeAttribute('contenteditable');
      }
    });
    reserve();
    paint();
  }

  function record(el) {
    var k = el.getAttribute('data-ed');
    var rec = byKey[k];
    if (!rec) return;
    if (norm(el.innerHTML) === norm(rec.base)) { delete dirty[k]; el.removeAttribute('data-ed-changed'); }
    else { dirty[k] = el.innerHTML; el.setAttribute('data-ed-changed', '1'); }
    paint();
  }

  // Record on every keystroke, but never rewrite the DOM here: mutating a
  // contenteditable while someone types collapses the caret to the start and
  // scatters their characters. Sanitising waits until they leave the field.
  document.addEventListener('input', function (e) {
    if (!editing) return;
    var el = e.target.closest && e.target.closest('[data-ed]');
    if (el) record(el);
  }, true);

  document.addEventListener('blur', function (e) {
    if (!editing) return;
    var el = e.target.closest && e.target.closest('[data-ed]');
    if (!el) return;
    clean(el);
    record(el);
  }, true);

  // plain text on paste, so a paste from Word cannot import styling
  document.addEventListener('paste', function (e) {
    if (!editing || !e.target.closest('[data-ed]')) return;
    e.preventDefault();
    var t = (e.clipboardData || window.clipboardData).getData('text/plain');
    document.execCommand('insertText', false, t);
  });

  function edits() {
    var out = {};
    if (current && current.edits) Object.keys(current.edits).forEach(function (k) { out[k] = current.edits[k]; });
    Object.keys(dirty).forEach(function (k) { out[k] = dirty[k]; });
    return out;
  }
  function countChanged() { return Object.keys(edits()).length; }

  /* ---------- version actions ---------- */
  function loadVersion(id) {
    if (!id) {
      nodes.forEach(function (r) { r.el.innerHTML = r.base; r.el.removeAttribute('data-ed-changed'); });
      current = null; dirty = {}; paint(); return Promise.resolve();
    }
    return Promise.resolve(Store.get(id)).then(function (v) {
      if (!v) { toast('Version not found'); return; }
      nodes.forEach(function (r) { r.el.innerHTML = r.base; r.el.removeAttribute('data-ed-changed'); });
      current = v; dirty = {};
      var r = applyEdits(v.edits);
      if (r.missing) toast(r.missing + ' edit' + (r.missing > 1 ? 's' : '') + ' no longer match this page');
      paint();
    });
  }

  function saveVersion() {
    var e = edits();
    if (!Object.keys(e).length) { toast('Nothing changed yet'); return; }
    var name = prompt('Name this version', current ? current.name : 'Draft ' + new Date().toISOString().slice(5, 16).replace('T', ' '));
    if (!name) return;
    var v = {
      id: current && current.name === name ? current.id : uid(),
      page: page(), name: name, edits: e,
      updatedAt: new Date().toISOString(),
      count: Object.keys(e).length
    };
    Promise.resolve(Store.put(v)).then(function () {
      current = v; dirty = {};
      refresh().then(function () { sel.value = v.id; paint(); toast('Saved "' + name + '"'); });
    });
  }

  function exportAll() {
    Promise.resolve(Store.all()).then(function (all) {
      var blob = new Blob([JSON.stringify({ page: page(), exported: new Date().toISOString(), versions: all }, null, 2)], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'versions' + page().replace(/\//g, '-') + '.json';
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
    });
  }

  function importFile() {
    var i = document.createElement('input');
    i.type = 'file'; i.accept = 'application/json';
    i.onchange = function () {
      var f = i.files[0]; if (!f) return;
      f.text().then(function (txt) {
        var d = JSON.parse(txt);
        var list = d.versions || [];
        var n = 0;
        var step = list.reduce(function (p, v) { return p.then(function () { n++; return Store.put(v); }); }, Promise.resolve());
        step.then(function () { refresh().then(function () { toast('Imported ' + n + ' version' + (n > 1 ? 's' : '')); }); });
      });
    };
    i.click();
  }

  /* ---------- UI ---------- */
  var bar, sel, cnt;
  function css() {
    var s = document.createElement('style');
    s.textContent = [
      '#edbar{position:fixed;left:0;right:0;bottom:0;z-index:99999;display:flex;gap:8px;align-items:center;flex-wrap:wrap;',
      'padding:10px 14px;background:#0e1113;color:#f4f6f7;font:500 13px/1.2 ui-sans-serif,-apple-system,"Segoe UI",sans-serif;',
      'box-shadow:0 -2px 20px rgba(0,0,0,.25)}',
      '#edbar button,#edbar select{font:inherit;border-radius:6px;border:1px solid #333c40;background:#1a2226;color:#e9eef0;padding:7px 11px;cursor:pointer;min-height:34px}',
      '#edbar button:hover{background:#243036}',
      '#edbar button:focus-visible,#edbar select:focus-visible{outline:2px solid #4594D1;outline-offset:2px}',
      '#edbar button.on{background:#4594D1;border-color:#4594D1;color:#fff}',
      '#edbar .sp{flex:1}',
      '#edbar .cnt{font-variant-numeric:tabular-nums;opacity:.75;font-size:12px}',
      '#edbar .lbl{opacity:.55;font-size:11px;letter-spacing:.08em;text-transform:uppercase}',
      'html.ed-on [data-ed]{outline:1px dashed rgba(69,148,209,.55);outline-offset:2px;border-radius:2px}',
      'html.ed-on [data-ed]:focus{outline:2px solid #4594D1;background:rgba(69,148,209,.07)}',
      '[data-ed-changed]{background:rgba(242,165,22,.16)}',
            '#edtoast{position:fixed;left:50%;bottom:70px;transform:translateX(-50%);z-index:100000;background:#0e1113;color:#fff;',
      'padding:9px 14px;border-radius:8px;font:500 13px ui-sans-serif,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.3)}',
      '@media print{#edbar,#edtoast{display:none}}'
    ].join('');
    document.head.appendChild(s);
  }

  function toast(msg) {
    var t = document.getElementById('edtoast');
    if (t) t.remove();
    t = document.createElement('div');
    t.id = 'edtoast'; t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2600);
  }

  function btn(label, fn, title) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = label; if (title) b.title = title;
    b.addEventListener('click', fn);
    return b;
  }

  function paint() {
    if (!cnt) return;
    var n = countChanged();
    cnt.textContent = n ? n + ' change' + (n > 1 ? 's' : '') : 'no changes';
    bar.querySelector('[data-role=toggle]').classList.toggle('on', editing);
    bar.querySelector('[data-role=toggle]').textContent = editing ? 'Editing' : 'Edit off';
  }

  function refresh() {
    return Promise.resolve(Store.all()).then(function (all) {
      var mine = all.filter(function (v) { return !v.page || v.page === page(); });
      var keep = sel.value;
      sel.innerHTML = '<option value="">Original (built)</option>';
      mine.sort(function (a, b) { return (b.updatedAt || '').localeCompare(a.updatedAt || ''); })
        .forEach(function (v) {
          var o = document.createElement('option');
          o.value = v.id; o.textContent = v.name + ' (' + (v.count || Object.keys(v.edits || {}).length) + ')';
          sel.appendChild(o);
        });
      if (keep) sel.value = keep;
      return mine;
    });
  }

  function build() {
    css();
    bar = document.createElement('div');
    bar.id = 'edbar';
    bar.setAttribute('role', 'toolbar');
    bar.setAttribute('aria-label', 'Copy editing');

    var t = btn('Edit off', function () { setEditing(!editing); });
    t.setAttribute('data-role', 'toggle');
    bar.appendChild(t);

    var lbl = document.createElement('span');
    lbl.className = 'lbl'; lbl.textContent = 'version';
    bar.appendChild(lbl);

    sel = document.createElement('select');
    sel.setAttribute('aria-label', 'Version');
    sel.addEventListener('change', function () { loadVersion(sel.value); });
    bar.appendChild(sel);

    bar.appendChild(btn('Save', saveVersion, 'Save the current changes as a named version'));
    bar.appendChild(btn('Duplicate', function () {
      if (!current) { toast('Load a version first'); return; }
      current = { id: null, name: current.name + ' copy', edits: edits() };
      saveVersion();
    }, 'Save these changes as a new version'));
    bar.appendChild(btn('Delete', function () {
      if (!sel.value) { toast('Pick a version first'); return; }
      if (!confirm('Delete this version? The built page is not affected.')) return;
      Promise.resolve(Store.del(sel.value)).then(function () { loadVersion(''); refresh().then(function () { toast('Deleted'); }); });
    }));

    var sp = document.createElement('span'); sp.className = 'sp'; bar.appendChild(sp);

    cnt = document.createElement('span'); cnt.className = 'cnt'; bar.appendChild(cnt);

    bar.appendChild(btn('Link', function () {
      if (!sel.value) { toast('Pick a version first'); return; }
      var u = location.origin + location.pathname + '?v=' + sel.value;
      navigator.clipboard.writeText(u).then(function () {
        toast(STORE === 'local' ? 'Copied. Opens in this browser only until the store is live.' : 'Review link copied');
      });
    }, 'Copy a link that opens the page with this version applied'));
    bar.appendChild(btn('Export', exportAll, 'Download every version on this page as JSON'));
    bar.appendChild(btn('Import', importFile, 'Load versions from a JSON file'));
    bar.appendChild(btn('Hide', function () {
      try { localStorage.removeItem(NS + ':ok'); } catch (e) {}
      bar.remove(); setEditing(false);
      toast('Hidden. Add ?edit=' + EDIT_KEY + ' to bring it back.');
    }));

    document.body.appendChild(bar);
    reserve();
  }

  /* ---------- boot ---------- */
  function boot() {
    var n = index();
    if (!n) return;

    if (viewing) {
      // A visitor opening a review link: apply, then reveal, so no flash of the original.
      Promise.resolve(Store.get(viewing)).then(function (v) {
        if (v) { current = v; applyEdits(v.edits); }
        document.documentElement.style.visibility = '';
        if (unlocked) { build(); refresh().then(function () { sel.value = viewing; paint(); }); }
      });
      return;
    }
    build();
    refresh().then(paint);
  }

  if (viewing) document.documentElement.style.visibility = 'hidden';
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
