#!/usr/bin/env python3
# Copyright (c) 2026 Haikal. All rights reserved.
# Polban Auto Absen -- engine HTTP/Playwright (dipakai windows/*.bat & termux/*.sh)
"""Auto-login + auto-klik tombol absen biru di akademik.polban.ac.id/ajar/absen.

Engine:
  http  requests + BeautifulSoup (ringan, default)
  pw    Playwright (fallback bila halaman pakai ajax berat)

Output:
  Semua status & log tampil di live TUI dashboard (lihat tui.py) -- sama seperti
  versi Linux. Jatuh ke mode plain text otomatis bila rich tidak terpasang,
  terminal non-interaktif, atau dijalankan dengan --once / --plain.
"""

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests  # noqa: F401  (dipakai di engine http & dump)
from bs4 import BeautifulSoup  # noqa: F401  (dipakai untuk parse HTML)

# Python embedded (windows/python) memakai file python311._pth yang menyalakan
# isolated mode: folder SKRIP tidak otomatis masuk sys.path -- titik '.' di _pth
# menunjuk ke folder python.exe, bukan ke folder auto_absen.py. Tanpa baris ini
# `import tui` gagal walau tui.py ada di sebelahnya.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from tui import create_dashboard, Dashboard
except ImportError as _e:  # tui.py benar-benar tidak ada
    print(f"ERROR: modul UI dashboard tidak bisa dimuat: {_e}")
    print(f"       Pastikan tui.py ada di: {_HERE}")
    raise SystemExit(1)

BASE = "https://akademik.polban.ac.id"
STATE_FILE = Path(__file__).resolve().parent / ".clicked.json"

# Timeout adaptif: (connect, read). Lebih pendek agar tidak menunggu lama di
# koneksi lambat; requests akan retry di lapisan loop.
TIMEOUT = (10, 20)


def _env_candidates():
    yield os.environ.get("POLBAN_ENV")
    yield Path(__file__).resolve().parent / ".env"
    yield Path.cwd() / ".env"
    yield Path(__file__).resolve().parent.parent / ".env"


def load_env():
    """Muat KEY=VALUE dari .env. Simbol (# ! @ spasi) di nilai dipertahankan."""
    for cand in _env_candidates():
        if not cand:
            continue
        p = Path(cand)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            os.environ[k] = v
        return str(p)
    return None


ENV_PATH_USED = load_env()

USERNAME = os.environ.get("POLBAN_USERNAME", "")
PASSWORD = os.environ.get("POLBAN_PASSWORD", "")
TARGET_URL = os.environ.get("POLBAN_TARGET_URL", f"{BASE}/ajar/absen")
INTERVAL = int(os.environ.get("POLBAN_INTERVAL", "60"))
DELAY_MIN = float(os.environ.get("POLBAN_DELAY_MIN", "1.2"))
DELAY_MAX = float(os.environ.get("POLBAN_DELAY_MAX", "2.6"))
MAX_RETRY = int(os.environ.get("POLBAN_MAX_RETRY", "5"))
RETRY_WAIT = float(os.environ.get("POLBAN_RETRY_WAIT", "2.5"))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


# ---------------------------------------------------------------
# TUI instance (global, di-set di main) + helper log
# ---------------------------------------------------------------
tui: Dashboard = None  # type: ignore


def _emit(code, msg, level="info"):
    """Kirim satu baris ke activity log TUI. Sebelum TUI hidup (validasi .env,
    mode --dump) jatuh ke print biasa."""
    if tui is None:
        print(f"[{time.strftime('%H:%M:%S')}] [{code}] {msg}", flush=True)
    else:
        tui.push_event(code, msg, level=level)


def log(code, msg):        _emit(code, msg, "info")
def log_ok(code, msg):     _emit(code, msg, "ok")
def log_fail(code, msg):   _emit(code, msg, "fail")
def log_warn(code, msg):   _emit(code, msg, "warn")
def log_info(code, msg):   _emit(code, msg, "info")


def jitter(a=DELAY_MIN, b=DELAY_MAX):
    time.sleep(random.uniform(a, b))


def countdown_sleep(seconds: int):
    """Sleep dengan countdown yang di-update di TUI tiap detik."""
    for remaining in range(seconds, 0, -1):
        tui.set_countdown(remaining)
        time.sleep(1)
    tui.set_countdown(0)


def load_state():
    try:
        d = json.loads(STATE_FILE.read_text())
        if d.get("_d") == date.today().isoformat():
            return set(d.get("s", []))
    except Exception:
        pass
    return set()


def save_state(s: set):
    STATE_FILE.write_text(json.dumps({"_d": date.today().isoformat(), "s": sorted(s)}))


def classify_classes(classes):
    c = set(classes or [])
    if "btn-success" in c:
        return "green"
    if "btn-danger" in c:
        return "red"
    if "btn-warning" in c:
        return "orange"
    if "btn-primary" in c or "btn-info" in c:
        return "blue"
    return "unknown"


def _is_login_page(url: str, html: str) -> bool:
    return 'name="username"' in html and 'name="password"' in html


def http_login(sess):
    """Login + verifikasi. Return HTML halaman absen bila sukses, else None.
    HTML dikembalikan supaya bisa dipakai ulang (user-info + scan pertama)
    tanpa GET tambahan -- hemat request di koneksi lambat."""
    sess.post(f"{BASE}/laman/login",
              data={"username": USERNAME, "password": PASSWORD, "submit": ""},
              allow_redirects=True, timeout=TIMEOUT)
    chk = sess.get(TARGET_URL, allow_redirects=True, timeout=TIMEOUT)
    ok = not _is_login_page(chk.url, chk.text)
    if ok:
        if tui:
            tui.set_auth_status("OK -- Authenticated")
        log_ok("LOGIN", "Authenticated")
    else:
        if tui:
            tui.set_auth_status("GAGAL -- Kredensial salah")
        log_fail("LOGIN", f"GAGAL -- dilempar ke {chk.url}")
    return chk.text if ok else None


def _parse_user_header(teks, info):
    """Parse 'NIM NAMA JURUSAN' -> isi info{nim,nama,jurusan}."""
    tokens = teks.split()
    if tokens and tokens[0].isdigit():
        info["nim"] = tokens[0]
        rest = tokens[1:]
        ji = len(rest)
        for i, tok in enumerate(rest):
            if ("-" in tok) or re.match(r"^D\d", tok) or tok.lower().startswith("teknik"):
                ji = i
                break
        info["nama"] = " ".join(rest[:ji]).strip()
        info["jurusan"] = " ".join(rest[ji:]).strip()
    elif teks:
        info["nama"] = teks
    return info


def fetch_user_info(sess, html=None):
    """Ambil NIM/nama/jurusan dari .user-header. Bila `html` diberikan, pakai itu
    (hemat 1 GET)."""
    info = {"nim": USERNAME, "nama": "", "jurusan": ""}
    try:
        if html is None:
            html = sess.get(TARGET_URL, allow_redirects=True, timeout=TIMEOUT).text
        uh = BeautifulSoup(html, "html.parser").select_one(".user-header")
        if uh:
            teks = " ".join(uh.get_text(" ", strip=True).split())
            _parse_user_header(teks, info)
    except Exception as e:
        log_warn("USER", f"gagal baca info user: {e}")
    return info


def skip_reason(color: str) -> str:
    return {
        "green":  "sudah absen (dihitung berhasil)",
        "orange": "belum buka -- dosen belum membuka sesi absen",
        "red":    "belum waktunya -- di luar jam absensi",
        "unknown": "warna tidak dikenali -- dilewati demi keamanan",
    }.get(color, "tidak perlu diklik")


def _is_nav_or_logout(el) -> bool:
    href = (el.get("href") or "").lower()
    txt = el.get_text(" ", strip=True).lower()
    return bool(re.search(r"logout|keluar|login|profil|profile", href)
                or re.search(r"logout|keluar|profil|profile", txt))


# Absen via AJAX seperti yang dilakukan JavaScript halaman (dan extension).
ABSEN_ENDPOINT = f"{BASE}/ajar/absen/absensi_awal"


def _td_text(row, idx):
    tds = row.find_all("td")
    return tds[idx].get_text(" ", strip=True) if idx < len(tds) else ""


def _parse_row_action(row, btn):
    """Bangun aksi absen satu baris: POST AJAX dgn param dari sel tabel."""
    data = {
        "ja":  _td_text(row, 5),
        "jb":  _td_text(row, 6),
        "mk":  _td_text(row, 2),
        "dsn": _td_text(row, 1).split("-")[0].strip(),
        "tp":  _td_text(row, 4),
        "kls": "",
    }
    kls_inp = row.find("input", id="kls")
    if kls_inp and kls_inp.get("value"):
        data["kls"] = kls_inp["value"].strip()

    # sig/key unik+stabil per-baris: matkul sama dibedakan oleh dosen.
    dosen = _td_text(row, 1)
    nama_mk = _td_text(row, 3) or _td_text(row, 2)
    jam = _td_text(row, 7)
    return {
        "sig": f"{nama_mk}|{dosen}|{jam}",
        "key": f"{nama_mk}|{dosen}",
        "kind": "ajax", "url": ABSEN_ENDPOINT, "data": data,
        "nama_mk": nama_mk, "dosen": dosen, "jam": jam,
        "label": f"{nama_mk} ({jam})",
    }


def http_find_blue(sess, html=None):
    """Return (actions, skips) dari tabel #jadwal. (None, None) bila sesi mati.
    Bila `html` diberikan, parse itu langsung (hemat 1 GET)."""
    if html is None:
        r = sess.get(TARGET_URL, allow_redirects=True, timeout=TIMEOUT)
        if _is_login_page(r.url, r.text):
            return None, None
        html = r.text
    elif _is_login_page(TARGET_URL, html):
        return None, None
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="jadwal") or soup.find("table")
    actions, skips = [], []
    if not table:
        return actions, skips

    for row in table.find_all("tr"):
        btn = next((c for c in row.find_all(["a", "button"])
                    if any("btn" in x for x in (c.get("class") or []))), None)
        if btn is None or _is_nav_or_logout(btn):
            continue

        color = classify_classes(btn.get("class"))
        btn_txt = " ".join(btn.get_text(" ", strip=True).split()) or btn.get("value", "")
        dosen = _td_text(row, 1)
        nama_mk = _td_text(row, 3) or _td_text(row, 2)
        jam = _td_text(row, 7)
        sig = f"{btn_txt}|{nama_mk}|{dosen}|{jam}"

        if color != "blue":
            reason = "disabled" if btn.has_attr("disabled") else skip_reason(color)
            skips.append((color, sig, reason))
            continue
        if btn.has_attr("disabled"):
            skips.append((color, sig, "disabled"))
            continue
        actions.append(_parse_row_action(row, btn))
    return actions, skips


def _still_blue(sess, key: str, html=None) -> bool:
    """True bila baris `key` (nama_mk|dosen) masih biru. Cocok by konten, bukan index.
    Bila `html` diberikan, parse itu (hemat 1 GET)."""
    acts, _ = http_find_blue(sess, html=html)
    if acts is None:
        return False
    return any(a.get("key") == key or a["sig"].startswith(key) for a in acts)


def _response_indicates_success(resp) -> bool:
    """Heuristik ringan: response POST absen dianggap sukses bila status 2xx dan
    body TIDAK mengandung penanda gagal. Menghindari GET ulang tiap retry."""
    try:
        if resp is None or not (200 <= resp.status_code < 300):
            return False
        body = (resp.text or "").lower()
        # Penanda kegagalan umum dari AJAX CodeIgniter
        for bad in ("gagal", "error", "tidak bisa", "bukan waktu", "sudah absen",
                    "belum dibuka", "invalid", "false"):
            if bad in body:
                return False
        return True
    except Exception:
        return False


def _do_request(sess, a):
    if a["kind"] == "ajax":
        headers = {"X-Requested-With": "XMLHttpRequest",
                   "Referer": TARGET_URL, "Origin": BASE}
        return sess.post(a["url"], data=a["data"], headers=headers, timeout=TIMEOUT)
    if a["kind"] == "get":
        return sess.get(a["url"], timeout=TIMEOUT)
    return sess.post(a["url"], data=a["data"], timeout=TIMEOUT)


def http_run_once(sess, clicked: set, html=None, first_run: bool = False):
    actions, skips = http_find_blue(sess, html=html)
    if actions is None:
        log_warn("SESSION", "Sesi habis -- re-login...")
        tui.set_auth_status("Sesi habis -- re-login...")
        if http_login(sess) is None:
            return False
        actions, skips = http_find_blue(sess)
        actions = actions or []
        skips = skips or []

    # Tabel jadwal di TUI di-update in-place (tidak dicetak ulang tiap siklus)
    changed = tui.update_jadwal(actions, skips)

    counts = {}
    for color, _, _ in (skips or []):
        counts[color] = counts.get(color, 0) + 1
    summary = (f"{len(actions)} siap absen | {counts.get('green', 0)} sudah absen | "
               f"{counts.get('orange', 0)} belum buka | {counts.get('red', 0)} belum waktunya")
    tui.set_last_scan(f"{time.strftime('%H:%M:%S')} ({summary})")

    # Activity log hanya diisi saat ada yang penting -- bukan tiap siklus,
    # supaya ring buffer tidak penuh oleh scan yang sama berulang.
    #
    # Rincian per matkul (sudah absen / belum buka / belum waktunya) TIDAK
    # ditulis ke log: semuanya sudah tampil di tabel "Jadwal Hari Ini" lengkap
    # dengan alasannya. Di mode plain (tanpa tabel) daftar itu dicetak oleh
    # PlainDashboard.update_jadwal.
    if first_run:
        log_info("SCAN", f"Scan awal: {summary}")
    elif actions:
        log_ok("SCAN", f"Ditemukan {len(actions)} matkul siap absen!")
    elif changed:
        log_info("JADWAL", f"Status jadwal berubah: {summary}")

    if not actions:
        return True

    for a in actions:
        sig = a["sig"]
        if sig in clicked:
            # Sudah diklik di siklus sebelumnya hari ini -- status sudah terlihat
            # di tabel, jadi tidak perlu bikin baris log tiap siklus.
            continue
        log_info("ABSEN", f"target: {a.get('label', sig)[:70]}")
        done = False
        for attempt in range(1, MAX_RETRY + 1):
            jitter()
            try:
                resp = _do_request(sess, a)
            except Exception as e:
                log_fail("ERROR", f"request gagal (percobaan {attempt}): {e} -- {sig[:40]}")
                continue
            time.sleep(RETRY_WAIT)
            # Deteksi sukses cepat dari response POST (tanpa GET ulang).
            # Hanya 1 GET konfirmasi bila response ambigu (tidak jelas sukses/gagal).
            if _response_indicates_success(resp):
                log_ok("ABSEN", f"BERHASIL (percobaan {attempt}): {a.get('nama_mk', sig)[:55]}")
                tui.mark_result(sig, success=True, nama=a.get('nama_mk', ''))
                clicked.add(sig)
                save_state(clicked)
                done = True
                break
            # Response ambigu/gagal -> konfirmasi 1x GET apakah tombol masih biru.
            if not _still_blue(sess, a.get("key", sig)):
                log_ok("ABSEN", f"BERHASIL (percobaan {attempt}, dikonfirmasi): "
                                f"{a.get('nama_mk', sig)[:50]}")
                tui.mark_result(sig, success=True, nama=a.get('nama_mk', ''))
                clicked.add(sig)
                save_state(clicked)
                done = True
                break
            log_warn("RETRY", f"percobaan {attempt}/{MAX_RETRY} masih biru, tekan lagi "
                              f"-- {a.get('nama_mk', sig)[:45]}")
        if not done:
            log_fail("ABSEN", f"GAGAL setelah {MAX_RETRY} percobaan: "
                              f"{a.get('nama_mk', sig)[:50]}. "
                              "Kemungkinan request ditolak server / bukan waktu absen.")
            tui.mark_result(sig, success=False, nama=a.get('nama_mk', ''))
    return True


def engine_http(loop: bool):
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": UA, "Referer": BASE + "/",
        "Accept-Encoding": "gzip, deflate",   # kompresi -> lebih kecil di koneksi lambat
        "Connection": "keep-alive",           # reuse TCP -> hemat handshake
    })
    html = http_login(sess)          # login + ambil HTML absen sekaligus
    if html is None:
        tui.stop()
        sys.exit(2)
    # Pakai HTML yang sama untuk identitas & scan pertama -- hemat 2 GET.
    tui.set_user_info(fetch_user_info(sess, html=html))
    if ENV_PATH_USED:
        log_info("CONFIG", f"{ENV_PATH_USED} (NIM {USERNAME})")
    clicked = load_state()
    log_info("ENGINE", f"HTTP aktif. interval={INTERVAL}s loop={loop}")
    first = True
    while True:
        tui.increment_cycle()
        try:
            http_run_once(sess, clicked, html=html if first else None, first_run=first)
        except Exception as e:
            log_fail("ERROR", f"siklus: {e}")
        first = False
        if not loop:
            break
        countdown_sleep(INTERVAL)


# ---- Engine Playwright (fallback) ----
CLASSIFY_JS = """(btn) => {
  const c = btn.className || '';
  if (/\\bbtn-success\\b/.test(c)) return 'green';
  if (/\\bbtn-danger\\b/.test(c))  return 'red';
  if (/\\bbtn-warning\\b/.test(c)) return 'orange';
  if (/\\bbtn-(primary|info)\\b/.test(c)) return 'blue';
  const bg = getComputedStyle(btn).backgroundColor;
  const m = bg.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
  if (!m) return 'unknown';
  const [r,g,b] = [+m[1],+m[2],+m[3]];
  if (b > r && b > g) return 'blue';
  if (g > r && g > b) return 'green';
  if (r > 180 && g > 120 && g < 200 && b < 120) return 'orange';
  if (r > g && r > b) return 'red';
  return 'unknown';
}"""

SIG_JS = """(btn) => {
  const t = el => ((el && (el.innerText || el.textContent)) || '');
  const row = btn.closest('tr');
  const rowTxt = row ? t(row).replace(/\\s+/g,' ').trim().slice(0,80) : '';
  return t(btn).replace(/\\s+/g,' ').trim() + '|' + rowTxt;
}"""


def pw_click_pass(page, clicked: set):
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    if page.locator('form#fm input[name="username"]').count():
        pw_login(page)
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)
    btns = page.locator("table a.btn, table button.btn, table input.btn, "
                        ".content a.btn, .content button.btn, .content input.btn, "
                        "body a.btn, body button.btn, body input.btn")
    found = 0
    for i in range(btns.count()):
        b = btns.nth(i)
        try:
            if b.get_attribute("disabled") is not None:
                continue
            if b.evaluate(CLASSIFY_JS) != "blue":
                continue
            sig = b.evaluate(SIG_JS)
            if sig in clicked:
                continue
            found += 1
            log_info("ABSEN", f"target (pw): {sig[:70]}")
            b.scroll_into_view_if_needed()
            jitter()
            b.click(timeout=8000)
            log_ok("ABSEN", f"BERHASIL (pw): {sig[:55]}")
            # Engine pw hanya punya sig 'teks_tombol|teks_baris' -- nama matkul
            # diambil dari sig oleh TUI.
            tui.mark_result(sig, success=True)
            clicked.add(sig)
            save_state(clicked)
            page.wait_for_timeout(random.randint(1000, 2000))
        except Exception as e:
            log_fail("ERROR", f"klik pw: {e}")
    tui.set_last_scan(f"{time.strftime('%H:%M:%S')} ({found} siap absen)")


def pw_login(page):
    page.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
    page.fill('form#fm input[name="username"]', USERNAME)
    page.fill('form#fm input[name="password"]', PASSWORD)
    jitter(0.4, 0.9)
    page.click('form#fm button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    tui.set_auth_status("OK -- Authenticated")
    log_ok("LOGIN", "Authenticated (pw)")


def pw_fetch_user_info(page):
    info = {"nim": USERNAME, "nama": "", "jurusan": ""}
    try:
        if page.locator(".user-header").count():
            teks = " ".join(page.locator(".user-header").first.inner_text().split())
            _parse_user_header(teks, info)
    except Exception as e:
        log_warn("USER", f"gagal baca info user (pw): {e}")
    return info


def engine_pw(loop: bool):
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    clicked = load_state()
    log_info("ENGINE", f"Playwright aktif. interval={INTERVAL}s loop={loop}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(user_agent=UA, locale="id-ID",
                                  timezone_id="Asia/Jakarta")
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        pw_login(page)
        tui.set_user_info(pw_fetch_user_info(page))
        while True:
            tui.increment_cycle()
            try:
                pw_click_pass(page, clicked)
            except Exception as e:
                log_fail("ERROR", f"siklus pw: {e}")
            if not loop:
                break
            countdown_sleep(INTERVAL)
        browser.close()


def dump_absen_html(path: str = None):
    """Login lalu simpan HTML halaman absen mentah (diagnostik)."""
    out = path or str(Path(__file__).resolve().parent / "absen-dump.html")
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Referer": BASE + "/"})
    if http_login(sess) is None:
        print("Login GAGAL -- cek NIM/password.", file=sys.stderr)
        sys.exit(2)
    r = sess.get(TARGET_URL, allow_redirects=True, timeout=TIMEOUT)
    Path(out).write_text(r.text, encoding="utf-8")
    print(f"HTML halaman absen disimpan ke: {out}")


def main():
    global tui

    ap = argparse.ArgumentParser(description="Polban Auto Absen (Windows .bat / Termux)")
    ap.add_argument("--engine", choices=["http", "pw"],
                    default=os.environ.get("POLBAN_ENGINE", "http"))
    ap.add_argument("--once", action="store_true", help="sekali jalan lalu exit")
    ap.add_argument("--dump", nargs="?", const="", default=None,
                    help="simpan HTML halaman absen lalu exit (diagnostik)")
    ap.add_argument("--plain", action="store_true",
                    help="mode plain text (tanpa live dashboard)")
    ap.add_argument("--no-alt-screen", action="store_true",
                    help="dashboard digambar di layar biasa (tanpa alternate "
                         "screen) -- pakai bila terminal lama tampil kacau")
    args = ap.parse_args()

    if not USERNAME or not PASSWORD:
        print("ERROR: POLBAN_USERNAME / POLBAN_PASSWORD belum terisi.\n", file=sys.stderr)
        if ENV_PATH_USED:
            print(f"  .env ditemukan di: {ENV_PATH_USED} (tapi nilai kosong)", file=sys.stderr)
        else:
            print("  .env tidak ditemukan. Salin .env.example -> .env lalu isi.", file=sys.stderr)
        sys.exit(1)

    if args.dump is not None:
        dump_absen_html(args.dump or None)
        return

    # Dashboard dipakai di semua mode. Bedanya cuma alternate screen:
    #   loop   -> alternate screen (layar bersih seperti htop)
    #   --once -> layar biasa, supaya dashboard TETAP terlihat setelah selesai
    # Plain text hanya kalau diminta (--plain), rich tidak ada, atau output
    # dialihkan ke file (create_dashboard mengecek isatty).
    alt_screen = (not args.no_alt_screen) and (not args.once)
    tui = create_dashboard(plain=args.plain, alt_screen=alt_screen)
    tui.set_engine(args.engine, INTERVAL)
    tui.start()

    try:
        loop = not args.once
        if args.engine == "pw":
            engine_pw(loop)
        else:
            engine_http(loop)
    except KeyboardInterrupt:
        pass
    finally:
        tui.stop()
        tui.render_summary()
        if args.once:
            print("[AutoAbsen] Selesai (sekali jalan).", flush=True)
        else:
            print("[AutoAbsen] Dihentikan. Sampai jumpa!", flush=True)


if __name__ == "__main__":
    main()
