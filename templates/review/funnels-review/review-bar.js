/* The comment layer Shelly uses inside a page.
   Loads only when the URL carries ?review=<token>, so ad traffic never sees it.
   Click anywhere on the page to pin a comment. Leave as many as you like.
   Everything goes to /api/review as an append-only event, same store as the review page. */
(function () {
  var q = new URLSearchParams(location.search);
  var TOKEN = q.get('review');
  if (!TOKEN || !/^[a-zA-Z0-9_-]{6,64}$/.test(TOKEN)) return;

  var ITEM = 'page:' + (location.pathname.replace(/^\/|\.html$|\/$/g, '') || 'home');
  var who = '';
  try { who = localStorage.getItem('sxrv:who') || ''; } catch (e) {}
  var comments = [], state = null, picking = false;

  var CSS = '\
.rb-bar{position:fixed;right:16px;bottom:16px;z-index:2147483000;display:flex;align-items:center;gap:8px;background:#fff;border:1px solid #E3EAF0;border-radius:999px;box-shadow:0 12px 30px rgba(18,21,25,.18);padding:8px 10px;font:600 14.5px/1.2 Manrope,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:#121519}\
.rb-bar button{font:inherit;border:1.5px solid #E3EAF0;background:#fff;color:#121519;border-radius:999px;padding:9px 14px;cursor:pointer;min-height:40px}\
.rb-bar button:hover{background:#F0F4F7}\
.rb-bar button.pri{background:linear-gradient(90deg,#4594D1 20.17%,#003C82 101.68%);color:#fff;border-color:transparent}\
.rb-bar button.on{background:#172351;color:#fff;border-color:#172351}\
.rb-bar .cnt{background:#E8F2FA;color:#1F6FA8;border-radius:999px;padding:4px 9px;font-size:13px}\
.rb-bar .ok{color:#156B43}\
.rb-pin{position:absolute;z-index:2147482000;width:28px;height:28px;border-radius:50% 50% 50% 4px;background:#172351;color:#fff;display:flex;align-items:center;justify-content:center;font:700 13px/1 Manrope,Arial,sans-serif;cursor:pointer;box-shadow:0 6px 16px rgba(18,21,25,.3);transform:translate(-4px,-28px)}\
.rb-pin.mine{background:#1F6FA8}\
.rb-pop{position:absolute;z-index:2147482500;width:min(320px,90vw);background:#fff;border:1px solid #E3EAF0;border-radius:14px;box-shadow:0 18px 44px rgba(18,21,25,.22);padding:14px;font:400 14.5px/1.5 Manrope,Arial,sans-serif;color:#121519}\
.rb-pop textarea{width:100%;min-height:80px;border:1px solid #E3EAF0;border-radius:10px;padding:10px;font:inherit;resize:vertical}\
.rb-pop .row{display:flex;gap:8px;margin-top:10px;justify-content:flex-end}\
.rb-pop button{font:600 14px/1.2 Manrope,Arial,sans-serif;border-radius:10px;padding:9px 14px;cursor:pointer;border:1.5px solid #E3EAF0;background:#fff;min-height:40px}\
.rb-pop button.pri{background:linear-gradient(90deg,#4594D1 20.17%,#003C82 101.68%);color:#fff;border-color:transparent}\
.rb-pop .q{font-size:12.5px;color:#5C6672;margin-bottom:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\
.rb-pop .head{font-weight:600;margin-bottom:6px}\
.rb-pop .meta{font-size:12.5px;color:#5C6672;margin-top:6px}\
.rb-list{position:fixed;right:16px;bottom:74px;z-index:2147482800;width:min(340px,92vw);max-height:60vh;overflow:auto;background:#fff;border:1px solid #E3EAF0;border-radius:16px;box-shadow:0 18px 44px rgba(18,21,25,.22);padding:8px;font:400 14px/1.5 Manrope,Arial,sans-serif}\
.rb-list h4{margin:8px 10px;font:600 15px/1.2 Manrope,Arial,sans-serif}\
.rb-list .it{padding:10px;border-top:1px solid #E3EAF0;cursor:pointer}\
.rb-list .it:hover{background:#F0F4F7}\
.rb-list .it b{font-size:13px;color:#1F6FA8}\
.rb-list .it p{margin:2px 0 0}\
.rb-list .it small{color:#5C6672;font-size:12.5px}\
.rb-picking,.rb-picking *{cursor:crosshair !important}\
.rb-hint{position:fixed;left:50%;transform:translateX(-50%);top:14px;z-index:2147483000;background:#172351;color:#fff;border-radius:999px;padding:9px 16px;font:600 14px/1.2 Manrope,Arial,sans-serif;box-shadow:0 10px 26px rgba(18,21,25,.25)}\
@media(max-width:560px){.rb-bar{right:10px;bottom:10px;left:10px;justify-content:space-between;padding:8px}.rb-bar button{padding:9px 10px;font-size:13.5px}}';

  var css = document.createElement('style'); css.textContent = CSS; document.head.appendChild(css);
  var hide = document.createElement('style'); hide.textContent = '#sxnav{display:none!important}'; document.head.appendChild(hide);

  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function api(body) {
    return fetch('/api/review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ token: TOKEN }, body)) });
  }
  function path(node) {
    if (!node || node === document.body) return 'body';
    if (node.id) return '#' + CSS.escape(node.id);
    var parts = [];
    while (node && node.nodeType === 1 && node !== document.body && parts.length < 6) {
      var p = node.parentElement; if (!p) break;
      var i = Array.prototype.indexOf.call(p.children, node) + 1;
      parts.unshift(node.tagName.toLowerCase() + ':nth-child(' + i + ')');
      node = p;
    }
    return 'body > ' + parts.join(' > ');
  }
  function askName() {
    if (who) return true;
    var n = prompt('Your name, so we know whose comment it is');
    if (!n) return false;
    who = n.trim(); try { localStorage.setItem('sxrv:who', who); } catch (e) {}
    return true;
  }

  // ---------- bar
  var bar = el('div', 'rb-bar');
  var bComment = el('button', '', 'Leave a comment');
  var bCount = el('button', '', '<span class="cnt">0</span> comments');
  var bApprove = el('button', 'pri', 'Approve this page');
  var status = el('span', 'ok', '');
  // Comments were taken off the pages: the reviewer approves or asks for a change, and
  // we pick the detail up with them directly. Existing comments stay readable.
  bar.appendChild(bCount); bar.appendChild(bApprove); bar.appendChild(status);
  document.addEventListener('DOMContentLoaded', function () { document.body.appendChild(bar); });
  if (document.readyState !== 'loading') document.body.appendChild(bar);

  var hint = null;
  function setPicking(on) {
    picking = on;
    document.documentElement.classList.toggle('rb-picking', on);
    bComment.classList.toggle('on', on);
    bComment.textContent = on ? 'Click the spot' : 'Leave a comment';
    if (on && !hint) { hint = el('div', 'rb-hint', 'Click anywhere on the page to put the comment there. Escape to cancel.'); document.body.appendChild(hint); }
    if (!on && hint) { hint.remove(); hint = null; }
  }
  bComment.addEventListener('click', function () { if (!askName()) return; setPicking(!picking); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { setPicking(false); closePop(); } });

  document.addEventListener('click', function (e) {
    if (!picking) return;
    if (bar.contains(e.target)) return;
    e.preventDefault(); e.stopPropagation();
    setPicking(false);
    var target = e.target.closest('p,h1,h2,h3,li,img,figure,section,div,button,a') || document.body;
    var r = target.getBoundingClientRect();
    openPop({
      sel: path(target),
      ox: e.clientX - r.left, oy: e.clientY - r.top,
      y: e.pageY,
      quote: (target.textContent || '').trim().slice(0, 120),
    }, e.pageX, e.pageY);
  }, true);

  // ---------- popover
  var pop = null;
  function closePop() { if (pop) { pop.remove(); pop = null; } }
  function openPop(anchor, x, y) {
    closePop();
    pop = el('div', 'rb-pop');
    pop.innerHTML = '<div class="head">Your comment</div>' + (anchor.quote ? '<div class="q">on: ' + anchor.quote.replace(/[<&]/g, '') + '</div>' : '') +
      '<textarea placeholder="What should change here?"></textarea><div class="row"><button data-x>Cancel</button><button class="pri" data-s>Save</button></div>';
    pop.style.left = Math.min(x, window.scrollX + document.documentElement.clientWidth - 340) + 'px';
    pop.style.top = (y + 10) + 'px';
    document.body.appendChild(pop);
    var ta = pop.querySelector('textarea'); ta.focus();
    pop.querySelector('[data-x]').onclick = closePop;
    pop.querySelector('[data-s]').onclick = function () {
      var text = ta.value.trim(); if (!text) { ta.focus(); return; }
      var id = 'c' + Date.now() + Math.random().toString(36).slice(2, 6);
      var ev = { item: ITEM, decision: 'note', comment: text, who: who, id: id, anchor: anchor };
      comments.push(ev); render(); closePop();
      api(ev).then(function (r) { flash(r.ok ? 'Comment saved' : 'Saved here, will retry'); }).catch(function () { flash('Saved here, will retry'); });
    };
  }

  function flash(t) { status.textContent = t; setTimeout(function () { if (status.textContent === t) status.textContent = ''; }, 2200); }

  // ---------- pins and list
  var pins = [];
  function render() {
    pins.forEach(function (p) { p.remove(); }); pins = [];
    comments.forEach(function (c, i) {
      var a = c.anchor || {}; var x = 0, y = a.y || 0;
      var t = null;
      try { t = a.sel ? document.querySelector(a.sel) : null; } catch (e) {}
      if (t) { var r = t.getBoundingClientRect(); x = window.scrollX + r.left + (a.ox || 0); y = window.scrollY + r.top + (a.oy || 0); }
      var pin = el('button', 'rb-pin' + (c.who === who ? ' mine' : ''), String(i + 1));
      pin.title = (c.who || 'Someone') + ': ' + c.comment;
      pin.style.left = Math.max(4, x) + 'px'; pin.style.top = Math.max(30, y) + 'px';
      pin.onclick = function (e) { e.stopPropagation(); showComment(c, i + 1, x, y); };
      document.body.appendChild(pin); pins.push(pin);
    });
    // nothing can be commented on any more, so the counter only shows if there is something to read
    bCount.innerHTML = '<span class="cnt">' + comments.length + '</span> comment' + (comments.length === 1 ? '' : 's');
    bCount.hidden = comments.length === 0;
    if (state && state.decision === 'approved') { bApprove.textContent = 'Approved'; bApprove.classList.remove('pri'); }
  }
  function showComment(c, n, x, y) {
    closePop();
    pop = el('div', 'rb-pop');
    pop.innerHTML = '<div class="head">Comment ' + n + '</div><p>' + c.comment.replace(/[<&]/g, '') + '</p>' +
      '<div class="meta">' + (c.who || 'Someone').replace(/[<&]/g, '') + ' · ' + new Date(c.at || Date.now()).toLocaleString() + '</div>' +
      '<div class="row"><button data-x>Close</button><button data-r>Remove</button></div>';
    pop.style.left = Math.min(x, window.scrollX + document.documentElement.clientWidth - 340) + 'px';
    pop.style.top = (y + 26) + 'px';
    document.body.appendChild(pop);
    pop.querySelector('[data-x]').onclick = closePop;
    pop.querySelector('[data-r]').onclick = function () {
      comments = comments.filter(function (o) { return o.id !== c.id; }); render(); closePop();
      api({ item: ITEM, decision: 'resolve', comment: c.id, who: who });
    };
  }

  var list = null;
  bCount.addEventListener('click', function () {
    if (list) { list.remove(); list = null; return; }
    list = el('div', 'rb-list', '<h4>' + comments.length + ' comment' + (comments.length === 1 ? '' : 's') + ' on this page</h4>');
    comments.forEach(function (c, i) {
      var it = el('div', 'it', '<b>' + (i + 1) + '</b> <small>' + (c.who || 'Someone').replace(/[<&]/g, '') + '</small><p>' + c.comment.replace(/[<&]/g, '') + '</p>');
      it.onclick = function () { var p = pins[i]; if (p) { window.scrollTo({ top: parseInt(p.style.top, 10) - 140, behavior: 'smooth' }); p.click(); } };
      list.appendChild(it);
    });
    document.body.appendChild(list);
  });

  bApprove.addEventListener('click', function () {
    if (!askName()) return;
    if (comments.length && !confirm('There are ' + comments.length + ' comments on this page. Approve it anyway?')) return;
    state = { decision: 'approved' };
    api({ item: ITEM, decision: 'approved', comment: '', who: who }).then(function () { flash('Page approved'); });
    render();
  });

  // ---------- load what is already there
  fetch('/api/review?token=' + encodeURIComponent(TOKEN)).then(function (r) { return r.json(); }).then(function (d) {
    comments = (d.comments || []).filter(function (c) { return c.item === ITEM; });
    state = (d.state || {})[ITEM] || null;
    render();
  }).catch(function () { render(); });
  addEventListener('resize', render);
})();
