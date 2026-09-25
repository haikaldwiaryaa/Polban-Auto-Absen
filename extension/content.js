/* Copyright (c) 2026 Haikal. All rights reserved.
 * Polban Auto Absen — content script (Chrome MV3)
 * Auto login + auto klik tombol absen BIRU + log panel sukses/gagal.
 */
(async function () {
  'use strict';

  /* ============================================================
   * INJECT SEGERA (document_start) — bypass alert()/confirm() native
   * Halaman menampilkan alert() "Kuesioner Layanan" setelah login;
   * dimatikan sebelum script halaman sempat memanggilnya.
   * ============================================================ */
  (function injectEarly() {
    try {
      const s = document.createElement('script');
      s.textContent = `
        (function(){
          if (window.__paaHooked) return; window.__paaHooked = true;
          const relay=(t,m)=>{ try{ window.dispatchEvent(new CustomEvent('paa-dialog',{detail:{type:t,msg:String(m)}})); }catch(e){} };
          window.alert   = function(m){ relay('alert', m); return undefined; };
          window.confirm = function(m){ relay('confirm', m); return true; };
          try { window.onbeforeunload = null; } catch(e){}
        })();`;
      (document.documentElement || document.head || document).appendChild(s);
      s.remove();
    } catch (e) {}
  })();

  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const rnd = (a, b) => Math.floor(a + Math.random() * (b - a + 1));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const todayStr = () => new Date().toISOString().slice(0, 10);
  const now = () => new Date().toTimeString().slice(0, 8);

  // Tunggu elemen muncul di DOM (event-driven, bukan delay tetap).
  function waitFor(selector, { timeout = 12000, root = document } = {}) {
    return new Promise((resolve) => {
      const found = root.querySelector(selector);
      if (found) return resolve(found);
      const mo = new MutationObserver(() => {
        const el = root.querySelector(selector);
        if (el) { mo.disconnect(); resolve(el); }
      });
      mo.observe(root === document ? document.documentElement : root, { childList: true, subtree: true });
      setTimeout(() => { mo.disconnect(); resolve(root.querySelector(selector)); }, timeout);
    });
  }

  const store = {
    get:      (k) => chrome.storage.sync.get(k),
    set:      (o) => chrome.storage.sync.set(o),
    localGet: (k) => chrome.storage.local.get(k),
    localSet: (o) => chrome.storage.local.set(o),
  };

  const defaults = {
    username: '', password: '',
    targetUrl: 'https://akademik.polban.ac.id/ajar/absen',
    autoLogin: true, autoNav: true, autoClick: true,
    delayMin: 1200, delayMax: 2600, pollMs: 15000, maxPasses: 40,
    maxRetry: 5, retryWaitMs: 2500,
  };
  const cfg = Object.assign({}, defaults, await store.get(Object.keys(defaults)));

  const KEY_CLICKED = 'paa_clicked';
  const KEY_STATE   = 'paa_state';

  async function getClickedSet() {
    const o = await store.localGet(KEY_CLICKED);
    const d = o[KEY_CLICKED];
    return (d && d._d === todayStr()) ? (d.s || {}) : {};
  }
  async function markClicked(sig) {
    const s = await getClickedSet();
    s[sig] = Date.now();
    await store.localSet({ [KEY_CLICKED]: { _d: todayStr(), s } });
  }
  async function alreadyClicked(sig) { return !!(await getClickedSet())[sig]; }

  /* ================= LOG PANEL ================= */
  function injectCss() {
    if ($('#paa-css')) return;
    const st = document.createElement('style');
    st.id = 'paa-css';
    st.textContent = `
      #paa-panel{position:fixed;bottom:14px;right:14px;width:400px;max-height:340px;z-index:2147483647;
        background:#161b22;border:1px solid #30363d;border-radius:10px;color:#e6edf3;
        font:12px/1.5 ui-monospace,Consolas,monospace;box-shadow:0 8px 30px rgba(0,0,0,.5);
        display:flex;flex-direction:column;overflow:hidden}
      #paa-panel.paa-min{max-height:38px}
      #paa-head{display:flex;align-items:center;gap:8px;padding:8px 10px;background:#21262d;user-select:none}
      #paa-dot{width:9px;height:9px;border-radius:50%;background:#8b949e;flex:none}
      #paa-dot.ok{background:#3fb950}#paa-dot.fail{background:#f85149}#paa-dot.run{background:#d29922}
      #paa-title{font-weight:700;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      #paa-count{color:#8b949e;font-size:11px}
      #paa-head button{background:#30363d;border:0;color:#e6edf3;border-radius:5px;padding:2px 8px;cursor:pointer;font-size:11px}
      #paa-body{overflow-y:auto;padding:6px 8px;flex:1}
      .paa-e{padding:3px 6px;border-left:3px solid #30363d;margin:3px 0;border-radius:3px;background:#1c2128;word-break:break-word}
      .paa-e .t{color:#8b949e;margin-right:6px}
      .paa-e .st{font-weight:700;margin-right:6px}
      .paa-e.info{border-color:#58a6ff}.paa-e.info .st{color:#58a6ff}
      .paa-e.ok{border-color:#3fb950}.paa-e.ok .st{color:#3fb950}
      .paa-e.warn{border-color:#d29922}.paa-e.warn .st{color:#d29922}
      .paa-e.fail{border-color:#f85149}.paa-e.fail .st{color:#f85149;background:#3d1f1f}`;
    (document.head || document.documentElement).appendChild(st);
  }

  const stats = { ok: 0, fail: 0, skip: 0 };
  let panelMin = false, manualScan = false;

  function ensurePanel() {
    injectCss();
    if ($('#paa-panel')) return;
    const el = document.createElement('div');
    el.id = 'paa-panel';
    el.innerHTML =
      '<div id="paa-head">' +
      '  <span id="paa-dot"></span><span id="paa-title">Auto Absen</span><span id="paa-count"></span>' +
      '  <button id="paa-scan" title="Scan sekarang">▶</button>' +
      '  <button id="paa-clear" title="Bersihkan log">🧹</button>' +
      '  <button id="paa-toggle" title="Minimize">—</button>' +
      '</div><div id="paa-body"></div>';
    document.body.appendChild(el);
    $('#paa-toggle').onclick = () => { panelMin = !panelMin; el.classList.toggle('paa-min', panelMin); $('#paa-toggle').textContent = panelMin ? '▢' : '—'; };
    $('#paa-clear').onclick = () => { $('#paa-body').innerHTML = ''; };
    $('#paa-scan').onclick = () => { manualScan = true; scanAndClick(); };
    updateHead();
  }

  function updateHead(status) {
    const dot = $('#paa-dot'), cnt = $('#paa-count');
    if (!dot || !cnt) return;
    if (status) dot.className = status;
    else if (stats.fail > 0) dot.className = 'fail';
    else if (stats.ok > 0) dot.className = 'ok';
    cnt.textContent = `✅${stats.ok} ❌${stats.fail} ⏭${stats.skip}`;
  }

  const pendingLogs = [];
  function plog(level, stage, msg) {
    console.log(`[AutoAbsen][${stage}]`, msg);
    if (!document.body) { pendingLogs.push([level, stage, msg]); return; }
    ensurePanel();
    const body = $('#paa-body'); if (!body) return;
    const e = document.createElement('div');
    e.className = 'paa-e ' + level;
    const icon = { info: 'ℹ️', ok: '✅', warn: '⚠️', fail: '❌' }[level] || 'ℹ️';
    e.innerHTML = `<span class="t">${now()}</span><span class="st">${icon}${stage}</span>${msg}`;
    body.appendChild(e);
    while (body.children.length > 120) body.removeChild(body.firstChild);
    body.scrollTop = body.scrollHeight;
    if (level === 'ok') stats.ok++;
    if (level === 'fail') stats.fail++;
    if (level === 'warn' && stage === 'SCAN') stats.skip++;
    updateHead(level === 'fail' ? 'fail' : level === 'ok' ? 'ok' : 'run');
  }

  window.addEventListener('paa-dialog', (ev) => {
    const d = ev.detail || {};
    const short = String(d.msg || '').replace(/\s+/g, ' ').slice(0, 90);
    plog('warn', 'DIALOG', `alert/confirm di-bypass otomatis: "${short}${(d.msg || '').length > 90 ? '…' : ''}"`);
  });

  /* ================= LOGIKA ABSEN ================= */
  function isLoginPage() { return !!$('form#fm input[name="username"]') && !!$('form#fm input[name="password"]'); }

  function setNative(el, val) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
                : el instanceof HTMLSelectElement ? HTMLSelectElement.prototype
                : HTMLInputElement.prototype;
    const d = Object.getOwnPropertyDescriptor(proto, 'value');
    if (d && d.set) d.set.call(el, val); else el.value = val;
    ['focus', 'input', 'change', 'blur'].forEach(ev => el.dispatchEvent(new Event(ev, { bubbles: true })));
  }

  async function doLogin() {
    const st = (await store.localGet(KEY_STATE))[KEY_STATE];
    if (st === 'login_submitted') {
      plog('fail', 'LOGIN', 'Gagal — dilempar balik ke halaman login. Cek NIM/password di Options.');
      await store.localSet({ [KEY_STATE]: 'login_failed' });
      return;
    }
    if (!cfg.autoLogin) { plog('info', 'LOGIN', 'autoLogin nonaktif — login manual.'); return; }
    if (!cfg.username || !cfg.password) { plog('fail', 'LOGIN', 'NIM/password belum diisi. Isi di Options extension.'); return; }
    const form = await waitFor('form#fm');
    const fu = await waitFor('form#fm input[name="username"]');
    const fp = await waitFor('form#fm input[name="password"]');
    if (!fu || !fp || !form) { plog('fail', 'LOGIN', 'Form login tidak ditemukan — struktur halaman berubah?'); return; }
    setNative(fu, cfg.username);
    setNative(fp, cfg.password);
    plog('info', 'LOGIN', `Form terisi (NIM ${cfg.username}), submit...`);
    await sleep(rnd(120, 320));
    await store.localSet({ [KEY_STATE]: 'login_submitted' });
    const btn = await waitFor('form#fm button[type="submit"], form#fm button[name="submit"]');
    try { btn ? btn.click() : form.submit(); } catch { form.submit(); }
  }

  function maybeNavigate() {
    if (!cfg.autoNav) return;
    const onTarget = location.href.startsWith(cfg.targetUrl) || /\/ajar\/absen/.test(location.pathname);
    if (!onTarget && !isLoginPage()) {
      const dari = /\/Mhs/i.test(location.pathname) ? '/Mhs (setelah login)' : location.pathname;
      plog('info', 'NAV', `Dari ${dari} → menuju ${cfg.targetUrl}`);
      store.localSet({ [KEY_STATE]: 'navigating' });
      setTimeout(() => { location.href = cfg.targetUrl; }, rnd(600, 1200));
    }
  }

  function classify(btn) {
    const c = btn.className || '';
    if (/\bbtn-success\b/.test(c)) return 'green';
    if (/\bbtn-danger\b/.test(c))  return 'red';
    if (/\bbtn-warning\b/.test(c)) return 'orange';
    if (/\bbtn-(primary|info)\b/.test(c)) return 'blue';
    const bg = getComputedStyle(btn).backgroundColor;
    const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!m) return 'unknown';
    const [r, g, b] = [+m[1], +m[2], +m[3]];
    if (b > r && b > g) return 'blue';
    if (g > r && g > b) return 'green';
    if (r > 180 && g > 120 && g < 200 && b < 120) return 'orange';
    if (r > g && r > b) return 'red';
    return 'unknown';
  }
  function textOf(el) { return ((el && (el.innerText || el.textContent)) || ''); }
  function signatureOf(btn) {
    const row = btn.closest('tr');
    const rowTxt = row ? textOf(row).replace(/\s+/g, ' ').trim().slice(0, 80) : '';
    return (textOf(btn).replace(/\s+/g, ' ').trim() || (btn.value || '')) + '|' + rowTxt;
  }
  function attendanceButtons() {
    const scope = $('table') || $('.content') || $('body');
    return $$('button, a.btn, input[type="button"], input[type="submit"]', scope).filter(b => {
      const st = getComputedStyle(b);
      if (st.display === 'none' || st.visibility === 'hidden') return false;
      const href = (b.getAttribute('href') || '').toLowerCase();
      const txt = textOf(b).toLowerCase();
      if (/logout|keluar|login/.test(href) || /logout|keluar/.test(txt)) return false;
      if (!/btn/.test(b.className || '')) return false;
      return true;
    });
  }
  // Klik HANYA tombol biru. Selain biru tidak akan merespon, jadi jangan diklik.
  function actionableButtons() { return attendanceButtons().filter(b => !b.disabled && classify(b) === 'blue'); }
  function findBySig(sig) { for (const b of attendanceButtons()) { if (signatureOf(b) === sig) return b; } return null; }
  function colorLabel(c) { return { blue: 'biru', green: 'hijau', orange: 'orange', red: 'merah', unknown: 'tidak dikenal' }[c] || c; }

  // Alasan detail kenapa sebuah tombol di-skip, berdasarkan warnanya.
  function skipReason(color) {
    switch (color) {
      case 'green':  return 'sudah absen (dihitung berhasil)';
      case 'orange': return 'belum bisa diklik — dosen belum membuka sesi absen';
      case 'red':    return 'belum bisa diklik — di luar jadwal/waktu absensi';
      case 'unknown':return 'warna tidak dikenali — dilewati demi keamanan';
      default:       return 'tidak perlu diklik';
    }
  }

  function realClick(el) {
    ['mousedown', 'mouseup', 'click'].forEach(t => el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
    if (typeof el.click === 'function') el.click();
  }

  // Tunggu tombol (cari ulang by sig) berubah jadi HIJAU, polling tiap 300ms.
  // Return 'green' | 'gone' | color terakhir setelah timeout.
  async function waitForGreen(sig, timeoutMs) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeoutMs) {
      const b = findBySig(sig);
      if (!b) return 'gone';                 // DOM/halam berubah -> anggap request terkirim
      const c = classify(b);
      if (c === 'green') return 'green';
      await sleep(300);
    }
    const last = findBySig(sig);
    return last ? classify(last) : 'gone';
  }

  // Klik tombol biru, lalu RETRY sampai jadi hijau (maks cfg.maxRetry percobaan).
  async function clickUntilGreen(btn, sig) {
    for (let attempt = 1; attempt <= cfg.maxRetry; attempt++) {
      // Selalu cari ulang elemen segar (DOM bisa re-render antar percobaan)
      const cur = findBySig(sig) || btn;
      try {
        cur.scrollIntoView({ block: 'center', behavior: 'smooth' });
        await sleep(rnd(cfg.delayMin, cfg.delayMax));
        realClick(cur);
      } catch (e) {
        plog('fail', 'KLIK', `Gagal klik (percobaan ${attempt}): ${sig.slice(0, 60)} — ${e.message}`);
        continue; // coba lagi
      }
      const res = await waitForGreen(sig, cfg.retryWaitMs);
      if (res === 'green') {
        plog('ok', 'VERIFIKASI', `SUCCESS — tombol jadi HIJAU (percobaan ${attempt}): ${sig.slice(0, 60)}`);
        await markClicked(sig);
        return true;
      }
      if (res === 'gone') {
        plog('ok', 'VERIFIKASI', `SUCCESS — halaman/DOM berubah setelah klik (percobaan ${attempt}): ${sig.slice(0, 60)}`);
        await markClicked(sig);
        return true;
      }
      plog('warn', 'VERIFIKASI', `Percobaan ${attempt}/${cfg.maxRetry}: masih ${colorLabel(res)}, tekan lagi... — ${sig.slice(0, 55)}`);
    }
    plog('fail', 'VERIFIKASI', `GAGAL — tombol tidak jadi hijau setelah ${cfg.maxRetry} percobaan: ${sig.slice(0, 60)}. Kemungkinan request ditolak server / bukan waktu absen.`);
    return false;
  }

  let scanning = false, passes = 0;
  async function scanAndClick() {
    if (scanning) return;
    scanning = true; passes++;
    try {
      const btns = attendanceButtons();
      const counts = { blue: 0, green: 0, orange: 0, red: 0, unknown: 0 };
      btns.forEach(b => counts[classify(b)]++);
      plog('info', 'SCAN', `#${passes}: ${btns.length} tombol — biru:${counts.blue} hijau:${counts.green} orange:${counts.orange} merah:${counts.red} lain:${counts.unknown}`);

      // Laporkan alasan skip untuk SETIAP tombol non-biru (detail per matkul).
      for (const b of btns) {
        const color = classify(b);
        if (color === 'blue') continue; // biru -> diklik di bawah
        const sig = signatureOf(b);
        if (color === 'green') {
          if (!(await alreadyClicked(sig))) {
            plog('ok', 'SCAN', `Sudah absen (hijau), skip — dihitung berhasil: ${sig.slice(0, 70)}`);
            await markClicked(sig);
          }
        } else if (!b.disabled) {
          // Orange/merah/warna-lain yang masih enabled tapi BUKAN biru -> jangan diklik.
          plog('warn', 'SCAN', `Skip tombol ${colorLabel(color)}: ${skipReason(color)} — ${sig.slice(0, 60)}`);
        } else {
          plog('info', 'SCAN', `Skip (disabled, ${colorLabel(color)}): ${sig.slice(0, 60)}`);
        }
      }

      // Klik HANYA tombol biru yang belum pernah diklik hari ini.
      const targets = [];
      for (const b of actionableButtons()) {
        if (!(await alreadyClicked(signatureOf(b)))) targets.push(b);
      }
      if (targets.length === 0) {
        plog('info', 'SCAN', 'Tidak ada tombol biru yang perlu diklik (sudah absen / dosen belum buka / di luar jadwal).');
      }
      for (const b of targets) {
        const sig = signatureOf(b);
        const warna = classify(b);
        plog('info', 'KLIK', `Klik (${colorLabel(warna)}) + retry sampai hijau: ${sig.slice(0, 70)}`);
        await clickUntilGreen(b, sig);
      }
    } catch (e) {
      plog('fail', 'SCAN', 'Error tak terduga: ' + e.message);
    } finally {
      scanning = false;
      updateHead();
    }
  }

  /* ================= ORCHESTRATION ================= */
  function flushPending() {
    while (pendingLogs.length) { const [l, s, m] = pendingLogs.shift(); plog(l, s, m); }
  }

  // Ambil NIM/nama/jurusan dari .user-header halaman akademik (format: 'NIM NAMA JURUSAN').
  function readUserInfo() {
    const uh = document.querySelector('.user-header');
    const info = { nim: cfg.username, nama: '', jurusan: '' };
    if (!uh) return info;
    const teks = (uh.innerText || uh.textContent || '').replace(/\s+/g, ' ').trim();
    const tokens = teks.split(' ');
    if (tokens.length && /^\d+$/.test(tokens[0])) {
      info.nim = tokens[0];
      const rest = tokens.slice(1);
      let ji = rest.length;
      for (let i = 0; i < rest.length; i++) {
        if (rest[i].includes('-') || /^D\d/.test(rest[i]) || rest[i].toLowerCase().startsWith('teknik')) { ji = i; break; }
      }
      info.nama = rest.slice(0, ji).join(' ').trim();
      info.jurusan = rest.slice(ji).join(' ').trim();
    } else if (teks) {
      info.nama = teks;
    }
    return info;
  }

  // Tampilkan banner identitas di panel log (sekali), sebelum flow absen.
  let _bannerShown = false;
  function showBanner() {
    if (_bannerShown) return;
    _bannerShown = true;
    const info = readUserInfo();
    plog('info', 'USER', `—— POLBAN AUTO ABSEN ——`);
    if (info.nama) plog('info', 'USER', `Nama: ${info.nama}`);
    plog('info', 'USER', `NIM: ${info.nim || cfg.username}`);
  }

  // Tanya background apakah tab ini di-trigger lewat tombol "Mulai Absen".
  // Kalau TIDAK (user buka situs langsung tanpa extension) -> jangan jalan.
  function shouldRun() {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: 'PAA_SHOULD_RUN' }, (resp) => {
          resolve(!!(resp && resp.run));
        });
      } catch (e) { resolve(false); }
    });
  }

  async function main() {
    // GATE: hanya jalan bila dipicu "Mulai Absen". Bukan saat buka web biasa.
    if (!(await shouldRun())) return;

    ensurePanel();
    flushPending();

    if (isLoginPage()) { await doLogin(); return; }

    const st = (await store.localGet(KEY_STATE))[KEY_STATE];
    if (st === 'login_submitted') {
      plog('ok', 'LOGIN', 'Berhasil — sudah masuk (bukan halaman login).');
      await store.localSet({ [KEY_STATE]: 'logged_in' });
    }

    const onAbsen = /\/ajar\/absen/.test(location.pathname) || location.href.startsWith(cfg.targetUrl);
    if (onAbsen) {
      showBanner();
      plog('ok', 'NAV', 'Sampai di halaman absen.');
      // Beri tahu background flow selesai -> lepas trigger agar kunjungan
      // berikutnya (tanpa tombol) tidak ikut ke-run.
      try { chrome.runtime.sendMessage({ type: 'PAA_DONE' }); } catch (e) {}
      if (!cfg.autoClick) { plog('info', 'SCAN', 'autoClick nonaktif.'); return; }
      scanAndClick();
      const iv = setInterval(() => {
        if (passes >= cfg.maxPasses && !manualScan) { clearInterval(iv); plog('info', 'SCAN', 'Max passes tercapai — polling berhenti. Klik ▶ untuk scan manual.'); return; }
        manualScan = false;
        scanAndClick();
      }, cfg.pollMs);
      const mo = new MutationObserver(() => { if (!scanning) scanAndClick(); });
      mo.observe($('table') || document.body, { childList: true, subtree: true });
      return;
    }
    maybeNavigate();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(main, 300));
  else setTimeout(main, 300);
})();
