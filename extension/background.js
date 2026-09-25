/* Copyright (c) 2026 Haikal. All rights reserved.
 * Polban Auto Absen — background service worker (MV3)
 * Trigger gate + force-nav ke /ajar/absen (bypass popup alert).
 *
 * Dua tugas:
 *  1) TRIGGER: saat user menekan "Mulai Absen", catat tab tujuan sebagai
 *     "triggered". Content script HANYA berjalan bila tab-nya triggered —
 *     jadi membuka situs akademik langsung (tanpa lewat extension) TIDAK
 *     menjalankan flow.
 *  2) FORCE-NAV: memaksa navigasi ke /ajar/absen tanpa terpengaruh popup
 *     alert halaman (alert memblokir load + menahan content script, tapi
 *     tidak menahan service worker).
 */

const HOME = 'https://akademik.polban.ac.id/';
const DEFAULT_TARGET = 'https://akademik.polban.ac.id/ajar/absen';

async function getTarget() {
  const c = await chrome.storage.sync.get(['targetUrl']);
  return c.targetUrl || DEFAULT_TARGET;
}

function isAkademik(url) {
  return typeof url === 'string' && url.startsWith('https://akademik.polban.ac.id');
}
function isAbsen(url, target) {
  return url.startsWith(target) || /\/ajar\/absen/.test(url);
}
function isLogin(url) {
  const u = new URL(url);
  return u.pathname === '/' || u.pathname === '';
}

/* ---------- 1) Trigger management ---------- */

// Tandai tab sebagai triggered (dipanggil popup saat "Mulai Absen").
async function armTab(tabId) {
  const { armed = {} } = await chrome.storage.session.get('armed');
  armed[tabId] = Date.now();
  await chrome.storage.session.set({ armed });
}
async function isArmed(tabId) {
  const { armed = {} } = await chrome.storage.session.get('armed');
  return !!armed[tabId];
}
async function disarmTab(tabId) {
  const { armed = {} } = await chrome.storage.session.get('armed');
  delete armed[tabId];
  await chrome.storage.session.set({ armed });
}

// Content script menanyakan apakah ia boleh jalan di tab ini.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || !msg.type) return;
  if (msg.type === 'PAA_SHOULD_RUN') {
    const tabId = sender.tab && sender.tab.id;
    isArmed(tabId).then((ok) => sendResponse({ run: ok }));
    return true; // async
  }
  if (msg.type === 'PAA_DONE') {
    // Flow selesai (sudah di halaman absen) -> lepas trigger supaya
    // navigasi manual berikutnya tidak ikut ke-run.
    const tabId = sender.tab && sender.tab.id;
    disarmTab(tabId).then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg.type === 'PAA_START') {
    (async () => {
      const target = await getTarget();
      const tabs = await chrome.tabs.query({ url: 'https://akademik.polban.ac.id/*' });
      let tab;
      if (tabs.length > 0) {
        tab = tabs[0];
        await chrome.tabs.update(tab.id, { active: true, url: HOME });
        await chrome.windows.update(tab.windowId, { focused: true });
      } else {
        tab = await chrome.tabs.create({ url: HOME, active: true });
      }
      await armTab(tab.id);
      sendResponse({ ok: true, target });
    })();
    return true;
  }
});

/* ---------- 2) Force-nav (hanya untuk tab yang triggered) ---------- */

let redirecting = {};
async function maybeRedirect(tabId, url) {
  if (!isAkademik(url)) return;
  if (!(await isArmed(tabId))) return; // bukan tab trigger -> jangan sentuh
  const target = await getTarget();
  if (isAbsen(url, target)) { redirecting[tabId] = false; return; }
  if (isLogin(url)) return; // halaman login -> biarkan content script login dulu
  if (redirecting[tabId]) return;
  redirecting[tabId] = true;
  try { await chrome.tabs.update(tabId, { url: target }); } catch (e) {}
  setTimeout(() => { redirecting[tabId] = false; }, 4000);
}

chrome.webNavigation.onCommitted.addListener((d) => {
  if (d.frameId === 0) maybeRedirect(d.tabId, d.url);
});
chrome.webNavigation.onDOMContentLoaded.addListener((d) => {
  if (d.frameId === 0) maybeRedirect(d.tabId, d.url);
});

// Bersihkan state saat tab ditutup
chrome.tabs.onRemoved.addListener((tabId) => { disarmTab(tabId); delete redirecting[tabId]; });
