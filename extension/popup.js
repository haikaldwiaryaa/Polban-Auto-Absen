/* Polban Auto Absen — popup script
 * Klik "Mulai Absen" -> kirim pesan ke background untuk buka/aktifkan
 * tab akademik, lalu tutup popup. Flow login->nav->klik jalan di tab.
 */

async function getCfg() {
  return chrome.storage.sync.get(['username', 'password', 'targetUrl']);
}

// Tampilkan status kredensial
(async () => {
  const c = await getCfg();
  document.getElementById('nim').textContent = c.username ? c.username : '(belum diisi)';
  if (!c.username || !c.password) {
    document.getElementById('warn').style.display = 'block';
  }
})();

document.getElementById('open-options').addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

document.getElementById('start').addEventListener('click', async () => {
  const c = await getCfg();
  if (!c.username || !c.password) {
    document.getElementById('warn').style.display = 'block';
    return; // jangan tutup popup kalau kredensial belum ada
  }

  // Tandai flow dipicu user (content script membaca ini)
  await chrome.storage.local.set({ paa_state: 'triggered' });

  // Minta background membuka/mengaktifkan tab akademik (lebih andal daripada
  // chrome.tabs dari popup, dan bekerja walau ada popup/alert yang memblokir).
  try {
    await chrome.runtime.sendMessage({ type: 'PAA_START' });
  } catch (e) {
    // Fallback: buka langsung kalau message gagal
    try { await chrome.tabs.create({ url: 'https://akademik.polban.ac.id/', active: true }); } catch {}
  }

  window.close(); // tutup popup -> flow berjalan di tab
});
