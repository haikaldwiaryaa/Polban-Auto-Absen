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
  // Teks dari halaman (nama matkul, pesan error) selalu di-escape sebelum
  // masuk innerHTML panel.
  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

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
      /* Palet & struktur disamakan dengan live TUI dashboard versi Linux:
         banner -> panel Identitas -> tabel Jadwal -> Log Aktivitas. */
      /* Ukuran panel ikut jendela: 430px kalau muat, menyusut sendiri saat
         browser di-restore / layar kecil. Tinggi dibatasi proporsi viewport,
         jadi panel tidak pernah keluar layar baik di-maximize maupun tidak. */
      #paa-panel{position:fixed;bottom:14px;right:14px;z-index:2147483647;
        width:min(430px,calc(100vw - 28px));
        max-height:min(78vh,760px);min-height:120px;
        overflow:hidden;
        background:#0d1117;border:1px solid #1f6feb;border-radius:12px;color:#e6edf3;
        font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;
        box-shadow:0 10px 36px rgba(0,0,0,.6);display:flex;flex-direction:column}
      #paa-panel.paa-min{max-height:36px}
      #paa-panel.paa-min #paa-scroll,#paa-panel.paa-min #paa-foot{display:none}
      #paa-head{display:flex;align-items:center;gap:8px;padding:8px 10px;background:#161b22;
        border-bottom:1px solid #30363d;user-select:none;cursor:move}
      #paa-dot{width:9px;height:9px;border-radius:50%;background:#8b949e;flex:none;
        box-shadow:0 0 0 3px rgba(139,148,158,.15)}
      #paa-dot.ok{background:#3fb950;box-shadow:0 0 0 3px rgba(63,185,80,.18)}
      #paa-dot.fail{background:#f85149;box-shadow:0 0 0 3px rgba(248,81,73,.18)}
      #paa-dot.run{background:#d29922;box-shadow:0 0 0 3px rgba(210,153,34,.18)}
      #paa-title{font-weight:700;letter-spacing:.8px;flex:1;white-space:nowrap;overflow:hidden;
        text-overflow:ellipsis;color:#58a6ff;font-size:11.5px}
      #paa-count{color:#8b949e;font-size:11px;white-space:nowrap}
      #paa-head button{background:#21262d;border:1px solid #30363d;color:#e6edf3;border-radius:5px;
        padding:2px 7px;cursor:pointer;font-size:11px;line-height:1.4}
      #paa-head button:hover{background:#30363d}
      #paa-scroll{overflow-y:auto;flex:1;padding:8px;display:flex;flex-direction:column;gap:8px}
      #paa-scroll::-webkit-scrollbar{width:8px}
      #paa-scroll::-webkit-scrollbar-thumb{background:#30363d;border-radius:4px}
      .paa-card{border:1px solid #30363d;border-radius:8px;background:#161b22}
      .paa-card-t{font-size:10.5px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;
        color:#8b949e;padding:5px 9px;border-bottom:1px solid #30363d}
      .paa-card-b{padding:7px 9px}
      /* -- Identitas -- */
      .paa-kv{display:grid;grid-template-columns:78px 1fr;gap:1px 8px}
      .paa-kv dt{color:#8b949e}
      .paa-kv dd{margin:0;word-break:break-word}
      .paa-kv dd b{color:#fff}
      .paa-hr{height:1px;background:#21262d;margin:6px 0}
      .paa-auth-ok{color:#3fb950;font-weight:700}
      .paa-auth-bad{color:#f85149;font-weight:700}
      .paa-auth-wait{color:#d29922;font-weight:700}
      .paa-next{color:#39d0d8;font-weight:700}
      /* -- Tabel jadwal -- */
      #paa-jadwal table{width:100%;border-collapse:collapse;font-size:11px}
      #paa-jadwal th{text-align:left;color:#8b949e;font-weight:700;padding:4px 6px;
        border-bottom:1px solid #30363d;white-space:nowrap}
      #paa-jadwal td{padding:4px 6px;border-bottom:1px solid #1c2128;vertical-align:top}
      #paa-jadwal tr:last-child td{border-bottom:0}
      #paa-jadwal{overflow-x:hidden}
      #paa-jadwal table{table-layout:fixed}
      #paa-jadwal .num{color:#8b949e;text-align:right;width:20px}
      #paa-jadwal col.c-mk{width:40%}
      #paa-jadwal col.c-st{width:24%}
      #paa-jadwal .mk{color:#e6edf3}
      /* Alasan versi ringkas, hanya dipakai saat kolom Keterangan disembunyikan */
      #paa-jadwal .ket-inline{display:none}
      #paa-jadwal .jam{display:block;color:#8b949e;font-size:10px;margin-top:1px}
      #paa-jadwal .ket{color:#8b949e}
      #paa-jadwal .empty{color:#8b949e;padding:8px 6px;text-align:center}
      .paa-badge{display:inline-block;padding:1px 6px;border-radius:999px;font-size:10px;
        font-weight:700;white-space:nowrap;border:1px solid}
      .st-blue{color:#39d0d8;border-color:#1f6feb;background:rgba(31,111,235,.12)}
      .st-green{color:#3fb950;border-color:#238636;background:rgba(35,134,54,.12)}
      .st-orange{color:#d29922;border-color:#9e6a03;background:rgba(210,153,34,.12)}
      .st-red{color:#f85149;border-color:#8c2320;background:rgba(248,81,73,.12)}
      .st-unknown{color:#8b949e;border-color:#30363d;background:#1c2128}
      /* -- Log aktivitas -- */
      #paa-body{max-height:190px;overflow-y:auto;padding:5px 7px}
      #paa-body::-webkit-scrollbar{width:8px}
      #paa-body::-webkit-scrollbar-thumb{background:#30363d;border-radius:4px}
      .paa-e{padding:2px 6px;border-left:3px solid #30363d;margin:2px 0;border-radius:3px;
        background:#1c2128;word-break:break-word;font-size:11px}
      .paa-e .t{color:#8b949e;margin-right:6px}
      .paa-e .tag{font-weight:700;margin-right:5px}
      .paa-e .st{font-weight:700;margin-right:6px;color:#c9d1d9}
      .paa-e.info{border-color:#58a6ff}.paa-e.info .tag{color:#58a6ff}
      .paa-e.ok{border-color:#3fb950}.paa-e.ok .tag{color:#3fb950}
      .paa-e.warn{border-color:#d29922}.paa-e.warn .tag{color:#d29922}
      .paa-e.fail{border-color:#f85149}.paa-e.fail .tag{color:#f85149}
      /* -- Footer -- */
      #paa-foot{display:flex;justify-content:space-between;gap:8px;padding:5px 10px;
        background:#161b22;border-top:1px solid #30363d;color:#8b949e;font-size:10.5px;
        flex-wrap:wrap}
      /* -- Responsif: jendela kecil / layar sempit -- */
      @media (max-width:760px){
        #paa-panel{left:8px;right:8px;bottom:8px;width:auto;max-width:none;
          max-height:min(70vh,560px)}
        #paa-jadwal col.c-mk{width:46%}
        #paa-jadwal col.c-st{width:30%}
        #paa-jadwal .ket{display:none}        /* alasan pindah ke bawah nama */
        #paa-jadwal th:last-child{display:none}
        #paa-jadwal .ket-inline{display:block;color:#8b949e;font-size:10px;margin-top:2px}
        .paa-kv{grid-template-columns:66px 1fr}
      }
      @media (max-height:620px){
        #paa-panel{max-height:88vh}
        #paa-body{max-height:120px}
      }`;
    (document.head || document.documentElement).appendChild(st);
  }

  const stats = { ok: 0, fail: 0, skip: 0 };
  let panelMin = false, manualScan = false;

  // State yang ditampilkan dashboard (mirror dari TUI versi Linux).
  const ui = {
    nama: '', nim: '', jurusan: '',
    auth: 'Menunggu...', lastScan: 'Menunggu scan awal...',
    nextIn: 0, passes: 0,
  };
  // sig -> 'clicked' | 'failed' : hasil klik, menimpa warna mentah dari DOM.
  const results = Object.create(null);
  let jadwalRows = [];

  const LEVEL_TAG = { ok: '[OK]', fail: '[!!]', warn: '[??]', info: '[--]' };
  // Hanya EMPAT status, sama persis dengan engine (tui.py). Hasil klik
  // otomatis tidak bikin status baru: yang berhasil langsung jadi SUDAH ABSEN,
  // yang gagal tetap SIAP ABSEN dan dicoba lagi -- sebabnya ada di log.
  const STATUS_LABEL = {
    blue: 'SIAP ABSEN', green: 'SUDAH ABSEN', orange: 'BELUM BUKA',
    red: 'BELUM WAKTUNYA', unknown: 'TIDAK DIKENALI',
  };

  function mmss(sec) {
    const s = Math.max(0, Math.floor(sec));
    return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
  }
  function tanggalPanjang() {
    try {
      return new Date().toLocaleDateString('id-ID',
        { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
    } catch (e) { return new Date().toDateString(); }
  }

  function ensurePanel() {
    injectCss();
    if ($('#paa-panel')) return;
    const el = document.createElement('div');
    el.id = 'paa-panel';
    el.innerHTML =
      '<div id="paa-head">' +
      '  <span id="paa-dot"></span>' +
      '  <span id="paa-title">POLBAN AUTO ABSEN</span>' +
      '  <span id="paa-count"></span>' +
      '  <button id="paa-scan" title="Scan sekarang">&#9654;</button>' +
      '  <button id="paa-clear" title="Bersihkan log">&#129529;</button>' +
      '  <button id="paa-toggle" title="Minimize">&mdash;</button>' +
      '</div>' +
      '<div id="paa-scroll">' +
      '  <section class="paa-card"><div class="paa-card-t">Identitas</div>' +
      '    <div class="paa-card-b" id="paa-ident"></div></section>' +
      '  <section class="paa-card"><div class="paa-card-t">Jadwal Hari Ini</div>' +
      '    <div id="paa-jadwal"></div></section>' +
      '  <section class="paa-card"><div class="paa-card-t" id="paa-log-t">Log Aktivitas</div>' +
      '    <div id="paa-body"></div></section>' +
      '</div>' +
      '<div id="paa-foot"><span id="paa-foot-l">v2.0 extension</span>' +
      '<span id="paa-foot-r"></span></div>';
    document.body.appendChild(el);
    $('#paa-toggle').onclick = () => {
      panelMin = !panelMin;
      el.classList.toggle('paa-min', panelMin);
      $('#paa-toggle').textContent = panelMin ? '▢' : '—';
    };
    $('#paa-clear').onclick = () => { $('#paa-body').innerHTML = ''; renderFoot(); };
    $('#paa-scan').onclick = () => { manualScan = true; ui.nextIn = 0; scanAndClick(); };
    renderIdent();
    renderJadwal();
    renderFoot();
    updateHead();
    startTicker();
  }

  // Countdown "next scan" + jam berjalan, 1 detik sekali (seperti TUI).
  let ticker = null;
  function startTicker() {
    if (ticker) return;
    ticker = setInterval(() => {
      if (ui.nextIn > 0) ui.nextIn--;
      renderIdent();
      renderFoot();
    }, 1000);
  }

  function renderIdent() {
    const box = $('#paa-ident'); if (!box) return;
    const authCls = /OK|Authenticated|Berhasil/i.test(ui.auth) ? 'paa-auth-ok'
                  : /Menunggu|login|navigasi/i.test(ui.auth) ? 'paa-auth-wait' : 'paa-auth-bad';
    const rows = [
      ['Nama', `<b>${esc(ui.nama || '-')}</b>`],
      ['NIM', esc(ui.nim || cfg.username || '-')],
    ];
    if (ui.jurusan) rows.push(['Jurusan', esc(ui.jurusan)]);
    rows.push(['Tanggal', esc(tanggalPanjang())]);
    let html = '<dl class="paa-kv">';
    rows.forEach(([k, v]) => { html += `<dt>${k}</dt><dd>${v}</dd>`; });
    html += '</dl><div class="paa-hr"></div><dl class="paa-kv">';
    html += `<dt>Status</dt><dd class="${authCls}">${esc(ui.auth)}</dd>`;
    html += `<dt>Hasil Scan</dt><dd>${esc(ui.lastScan)}</dd>`;
    html += `<dt>Next scan</dt><dd><span class="paa-next">${mmss(ui.nextIn)}</span>` +
            ` &nbsp;<span style="color:#8b949e">poll ${Math.round(cfg.pollMs / 1000)}s</span></dd>`;
    html += '</dl>';
    box.innerHTML = html;
  }

  function renderJadwal() {
    const box = $('#paa-jadwal'); if (!box) return;
    if (!jadwalRows.length) {
      box.innerHTML = '<div class="empty">Belum ada data jadwal</div>';
      return;
    }
    // Jam ditaruh sebaris di bawah nama matkul (panel sempit, 430px) supaya
    // kolom Keterangan tetap terbaca -- isinya sama dengan tabel TUI.
    let html = '<table><colgroup><col><col class="c-mk"><col class="c-st"><col></colgroup>' +
               '<thead><tr><th class="num">No</th>' +
               '<th>Mata Kuliah</th><th>Status</th><th>Keterangan</th></tr></thead><tbody>';
    jadwalRows.forEach((r, i) => {
      html += `<tr><td class="num">${i + 1}</td>` +
              `<td><span class="mk">${esc(r.nama)}</span>` +
              (r.jam ? `<span class="jam">${esc(r.jam)}</span>` : '') +
              `<span class="ket-inline">${esc(r.detail)}</span></td>` +
              `<td><span class="paa-badge st-${r.status}">` +
              `${STATUS_LABEL[r.status] || r.status.toUpperCase()}</span></td>` +
              `<td class="ket">${esc(r.detail)}</td></tr>`;
    });
    box.innerHTML = html + '</tbody></table>';
  }

  function renderFoot() {
    const l = $('#paa-foot-l'), r = $('#paa-foot-r');
    if (l) l.textContent = `v2.0 extension | scan #${ui.passes}`;
    if (r) r.textContent = `${now()} | ${stats.ok} berhasil / ${stats.fail} gagal`;
    const t = $('#paa-log-t');
    const body = $('#paa-body');
    if (t && body) t.textContent = `Log Aktivitas (${body.children.length} terakhir)`;
  }

  function updateHead(status) {
    const dot = $('#paa-dot'), cnt = $('#paa-count');
    if (!dot || !cnt) return;
    if (status) dot.className = status;
    else if (stats.fail > 0) dot.className = 'fail';
    else if (stats.ok > 0) dot.className = 'ok';
    cnt.textContent = `OK ${stats.ok} | GAGAL ${stats.fail} | SKIP ${stats.skip}`;
  }

  const pendingLogs = [];
  function plog(level, stage, msg) {
    console.log(`[AutoAbsen][${stage}]`, msg);
    if (!document.body) { pendingLogs.push([level, stage, msg]); return; }
    ensurePanel();
    const body = $('#paa-body'); if (!body) return;
    const e = document.createElement('div');
    e.className = 'paa-e ' + level;
    // Format baris disamakan dengan TUI:  HH:MM:SS  [OK] [STAGE] pesan
    e.innerHTML = `<span class="t">${now()}</span>` +
                  `<span class="tag">${LEVEL_TAG[level] || '[--]'}</span>` +
                  `<span class="st">[${esc(stage)}]</span>${esc(String(msg))}`;
    body.appendChild(e);
    while (body.children.length > 120) body.removeChild(body.firstChild);
    body.scrollTop = body.scrollHeight;
    if (level === 'ok') stats.ok++;
    if (level === 'fail') stats.fail++;
    // stats.skip di-set dari hasil scan (lihat scanAndClick), bukan dari log.
    updateHead(level === 'fail' ? 'fail' : level === 'ok' ? 'ok' : 'run');
    renderFoot();
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
      ui.auth = 'GAGAL -- Kredensial salah'; renderIdent();
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
    ui.auth = 'Login dikirim, menunggu...'; ui.nim = cfg.username; renderIdent();
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
      ui.auth = 'Login OK -- menuju halaman absen'; renderIdent();
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
  function colorLabel(c) { return { blue: 'biru (siap absen)', green: 'hijau (sudah absen)', orange: 'kuning (belum buka)', red: 'merah (belum waktunya)', unknown: 'tidak dikenal' }[c] || c; }

  // Alasan detail kenapa sebuah tombol di-skip, berdasarkan warnanya.
  function skipReason(color) {
    switch (color) {
      case 'green':  return 'sudah absen (dihitung berhasil)';
      case 'orange': return 'belum buka — dosen belum membuka sesi absen';
      case 'red':    return 'belum waktunya — di luar jam absensi';
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
        results[sig] = 'clicked'; buildJadwal(attendanceButtons());
        await markClicked(sig);
        return true;
      }
      if (res === 'gone') {
        plog('ok', 'VERIFIKASI', `SUCCESS — halaman/DOM berubah setelah klik (percobaan ${attempt}): ${sig.slice(0, 60)}`);
        results[sig] = 'clicked'; buildJadwal(attendanceButtons());
        await markClicked(sig);
        return true;
      }
      plog('warn', 'VERIFIKASI', `Percobaan ${attempt}/${cfg.maxRetry}: masih ${colorLabel(res)}, tekan lagi... — ${sig.slice(0, 55)}`);
    }
    plog('fail', 'VERIFIKASI', `GAGAL — tombol tidak jadi hijau setelah ${cfg.maxRetry} percobaan: ${sig.slice(0, 60)}. Kemungkinan request ditolak server / bukan waktu absen.`);
    results[sig] = 'failed'; buildJadwal(attendanceButtons());
    return false;
  }

  // Ambil nama matkul / jam / dosen dari baris tabel jadwal.
  // Urutan sel sama dengan yang dipakai engine python:
  //   td1=dosen  td2=kode mk  td3=nama mk  td7=jam
  function rowInfo(btn) {
    const row = btn.closest('tr');
    if (!row) return { nama: textOf(btn).replace(/\s+/g, ' ').trim(), jam: '', dosen: '' };
    const td = row.querySelectorAll('td');
    const cell = (i) => (td[i] ? textOf(td[i]).replace(/\s+/g, ' ').trim() : '');
    return {
      nama: cell(3) || cell(2) || textOf(btn).replace(/\s+/g, ' ').trim(),
      jam: cell(7),
      dosen: cell(1),
    };
  }

  // Bangun ulang isi tabel "Jadwal Hari Ini" dari tombol yang ada di halaman.
  function buildJadwal(btns) {
    jadwalRows = btns.map((b) => {
      const info = rowInfo(b);
      const sig = signatureOf(b);
      const color = classify(b);
      // Berhasil diabsenkan -> ikut hijau (SUDAH ABSEN). Gagal -> tetap biru
      // supaya ikut dicoba lagi di polling berikutnya.
      const status = results[sig] === 'clicked' ? 'green' : color;
      const detail = results[sig] === 'clicked' ? 'sudah absen (diabsenkan otomatis)'
                   : results[sig] === 'failed' && color === 'blue'
                     ? 'percobaan gagal -- akan diulang'
                   : color === 'blue' ? 'siap absen -- akan diklik'
                   : skipReason(color);
      return { nama: info.nama.slice(0, 48), jam: info.jam, status, detail };
    });
    renderJadwal();
  }

  let scanning = false, passes = 0, lastColorMap = '';
  async function scanAndClick() {
    if (scanning) return;
    scanning = true; passes++;
    try {
      const btns = attendanceButtons();
      const counts = { blue: 0, green: 0, orange: 0, red: 0, unknown: 0 };
      btns.forEach(b => counts[classify(b)]++);

      // Panel dashboard: tabel + status bar di-update in-place tiap scan.
      buildJadwal(btns);
      ui.passes = passes;
      ui.nextIn = Math.round(cfg.pollMs / 1000);
      ui.lastScan = `${now()} (${counts.blue} siap absen | ${counts.green} sudah absen | ` +
                    `${counts.orange} belum buka | ${counts.red} belum waktunya)`;
      // Counter SKIP di header dihitung dari hasil scan, bukan dari jumlah baris
      // log -- barisnya memang sengaja tidak dibuat lagi.
      stats.skip = counts.green + counts.orange + counts.red + counts.unknown;
      renderIdent();
      renderFoot();

      // Log aktivitas hanya diisi saat scan pertama, ada tombol biru, atau
      // status berubah — supaya tidak penuh oleh scan berulang yang sama.
      const colorMap = btns.map(b => signatureOf(b) + '=' + classify(b)).join(';');
      const changed = colorMap !== lastColorMap;
      const verbose = passes === 1 || counts.blue > 0 || changed;
      lastColorMap = colorMap;

      if (verbose) {
        plog('info', 'SCAN', `#${passes}: ${btns.length} tombol — biru:${counts.blue} hijau:${counts.green} orange:${counts.orange} merah:${counts.red} lain:${counts.unknown}`);
      }
      if (!verbose) return;   // finally{} tetap melepas flag scanning

      // Tombol non-biru TIDAK dicatat satu per satu ke log: status & alasannya
      // sudah tampil di tabel "Jadwal Hari Ini" di atas. Di sini cukup tandai
      // yang hijau sebagai sudah-diklik supaya tidak diproses lagi hari ini.
      for (const b of btns) {
        if (classify(b) !== 'green') continue;
        const sig = signatureOf(b);
        if (!(await alreadyClicked(sig))) await markClicked(sig);
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
    ui.nama = info.nama;
    ui.nim = info.nim || cfg.username;
    ui.jurusan = info.jurusan;
    ui.auth = 'OK -- Authenticated';
    renderIdent();
    plog('info', 'USER', `${ui.nama || '(nama tidak terbaca)'} — NIM ${ui.nim}`);
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
      ui.auth = 'OK -- Authenticated'; renderIdent();
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
