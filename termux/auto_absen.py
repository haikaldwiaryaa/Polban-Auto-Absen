#!/usr/bin/env python3
# Copyright (c) 2026 Haikal. All rights reserved.
# Polban Auto Absen — engine HTTP/Playwright untuk auto-login & auto-klik
# tombol absen biru di akademik.polban.ac.id/ajar/absen.
# Dipakai oleh: windows/*.bat dan termux/*.sh
"""
Polban Auto Absen — engine HTTP/Playwright (Windows .bat & Termux)
Dual engine:
  --engine http : requests + BeautifulSoup (ringan, tanpa browser)
  --engine pw   : Playwright (render penuh, fallback bila absen pakai ajax)

Flow: login (POST /laman/login) -> GET /ajar/absen -> cari tombol BIRU
(btn-primary / btn-info) -> replay request absen (GET href atau POST form).
Anti-duplikat per-hari via state file. Config dari .env (lihat .env.example).
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

BASE = "https://akademik.polban.ac.id"
STATE_FILE = Path(__file__).resolve().parent / ".clicked.json"

# ---------------------------------------------------------------
# Config — cari .env di beberapa lokasi (urutan prioritas):
#   1) POLBAN_ENV (env var, path eksplisit)
#   2) folder skrip ini (vps/.env)
#   3) working directory (cwd/.env)
#   4) folder induk (../.env)
# ---------------------------------------------------------------
def _env_candidates():
    yield os.environ.get("POLBAN_ENV")
    yield Path(__file__).resolve().parent / ".env"
    yield Path.cwd() / ".env"
    yield Path(__file__).resolve().parent.parent / ".env"


def load_env():
    """Muat KEY=VALUE dari .env. Nilai dipertahankan apa adanya
    (simbol #, !, @, spasi aman). Hanya baris ber-awal '#' yang di-skip."""
    for cand in _env_candidates():
        if not cand:
            continue
        p = Path(cand)
        if not (p.is_file()):
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
        return str(p)  # kembalikan path yang dipakai (untuk log)
    return None


ENV_PATH_USED = load_env()

USERNAME = os.environ.get("POLBAN_USERNAME", "")
PASSWORD = os.environ.get("POLBAN_PASSWORD", "")
TARGET_URL = os.environ.get("POLBAN_TARGET_URL", f"{BASE}/ajar/absen")
INTERVAL = int(os.environ.get("POLBAN_INTERVAL", "60"))
DELAY_MIN = float(os.environ.get("POLBAN_DELAY_MIN", "1.2"))
DELAY_MAX = float(os.environ.get("POLBAN_DELAY_MAX", "2.6"))
MAX_RETRY = int(os.environ.get("POLBAN_MAX_RETRY", "5"))        # maks klik ulang per tombol
RETRY_WAIT = float(os.environ.get("POLBAN_RETRY_WAIT", "2.5"))  # jeda antar klik ulang (detik)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}] [AutoAbsen]", *a, flush=True)


# ---- Log terstruktur (kode + ikon) supaya gampang di-maintenance ----
# Kode status: LOGIN / SCAN / SKIP / KLIK / ABSEN / RETRY / ERROR / SESSION
def _emit(icon, code, msg):
    log(f"{icon} [{code}] {msg}")

def log_ok(code, msg):      _emit("✅", code, msg)
def log_fail(code, msg):    _emit("❌", code, msg)
def log_warn(code, msg):    _emit("⚠️ ", code, msg)
def log_info(code, msg):    _emit("ℹ️ ", code, msg)
def log_skip(color, reason, sig):  _emit("⏭️ ", "SKIP", f"({color}) {reason} — {sig[:60]}")


def jitter(a=DELAY_MIN, b=DELAY_MAX):
    time.sleep(random.uniform(a, b))

# ---------------------------------------------------------------
# State anti-duplikat (per hari)
# ---------------------------------------------------------------
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

# ---------------------------------------------------------------
# ENGINE 1: HTTP (requests + bs4) — tanpa browser
# ---------------------------------------------------------------
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
    """Halaman login = ada form#fm DENGAN input username+password.
    Cek via URL /laman/login saja TIDAK cukup (bisa jadi redirect sementara)."""
    if 'name="username"' in html and 'name="password"' in html:
        return True
    # URL /laman/login yang MASIH menampilkan form = login
    return False


def http_login(sess):
    """Login CodeIgniter. Return True bila benar-benar terautentikasi.

    Perbaikan bug: dulu hanya cek 'tidak ada form login di response POST',
    yang bisa SALAH POSITIF (POST gagal tapi form tidak ke-render). Sekarang
    diverifikasi dengan GET halaman absen — kalau dilempar balik ke form
    login, berarti kredensial salah / sesi tidak terbentuk."""
    r = sess.post(f"{BASE}/laman/login",
                  data={"username": USERNAME, "password": PASSWORD, "submit": ""},
                  allow_redirects=True, timeout=30)
    # Verifikasi nyata: ambil halaman absen, pastikan TIDAK dilempar ke login
    chk = sess.get(TARGET_URL, allow_redirects=True, timeout=30)
    ok = not _is_login_page(chk.url, chk.text)
    log("Login", f"OK (terautentikasi, {chk.url})" if ok else
                 f"GAGAL — kredensial salah/sesi tidak terbentuk (dilempar ke {chk.url})")
    return ok


def fetch_user_info(sess):
    """Ambil NIM, nama, jurusan dari elemen .user-header halaman akademik.
    Format asli di HTML: 'NIM NAMA JURUSAN' (misal '25....... NAMA LENGKAP
    D3-Teknik Informatika'). Return dict {nim, nama, jurusan}."""
    from bs4 import BeautifulSoup
    info = {"nim": USERNAME, "nama": "", "jurusan": ""}
    try:
        r = sess.get(TARGET_URL, allow_redirects=True, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        uh = soup.select_one(".user-header")
        if not uh:
            return info
        teks = " ".join(uh.get_text(" ", strip=True).split())
        # Format asli: '<NIM> <NAMA...> <JURUSAN>'.
        # Jurusan = token yang mengandung '-' atau diawali pola D3/D4/Teknik.
        tokens = teks.split()
        if tokens and tokens[0].isdigit():
            info["nim"] = tokens[0]
            rest = tokens[1:]
            ji = len(rest)  # index mulai jurusan
            for i, tok in enumerate(rest):
                if ("-" in tok) or re.match(r"^D\d", tok) or tok.lower().startswith("teknik"):
                    ji = i
                    break
            info["nama"] = " ".join(rest[:ji]).strip()
            info["jurusan"] = " ".join(rest[ji:]).strip()
        else:
            # Fallback: tidak ada NIM digit di depan — simpan mentah sebagai nama
            if teks:
                info["nama"] = teks
    except Exception as e:
        log_warn("USER", f"gagal baca info user: {e}")
    return info


def print_header(info):
    """Cetak banner identitas rapi di awal log, sebelum flow absen."""
    garis = "=" * 56
    log(garis)
    log("  POLBAN AUTO ABSEN")
    log(garis)
    if info.get("nama"):
        log(f"  Nama   : {info['nama']}")
    log(f"  NIM    : {info.get('nim') or USERNAME}")
    log(f"  Waktu  : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(garis)


def skip_reason(color: str) -> str:
    """Alasan detail kenapa tombol non-biru di-skip, per warna."""
    return {
        "green":  "sudah absen (dihitung berhasil)",
        "orange": "belum bisa diklik — dosen belum membuka sesi absen",
        "red":    "belum bisa diklik — di luar jadwal/waktu absensi",
        "unknown": "warna tidak dikenali — dilewati demi keamanan",
    }.get(color, "tidak perlu diklik")


def classify_el(el) -> str:
    """Klasifikasi warna tombol dari class (bs4 Tag). Samakan dgn content.js."""
    return classify_classes(el.get("class"))


# Selector tombol absen — selaras dgn content.js yang sudah terbukti berhasil:
# cakup table / .content / body, semua elemen ber-class btn + button + input.
BTN_SELECTOR = ("table a.btn, table button.btn, table input.btn, "
                ".content a.btn, .content button.btn, .content input.btn, "
                "body a.btn, body button.btn, body input.btn")


def _is_nav_or_logout(el) -> bool:
    """True bila elemen ini link navigasi/logout/login — harus di-skip."""
    href = (el.get("href") or "").lower()
    txt = el.get_text(" ", strip=True).lower()
    return bool(re.search(r"logout|keluar|login|profil|profile", href)
                or re.search(r"logout|keluar|profil|profile", txt))


# ---------------------------------------------------------------------------
# Absen via AJAX — mereplikasi persis apa yang dilakukan JavaScript halaman
# (dan yang diklik extension). Endpoint: POST /ajar/absen/absensi_awal
# Parameter dibaca dari sel tabel #jadwal + input hidden #kls.
# ---------------------------------------------------------------------------
ABSEN_ENDPOINT = f"{BASE}/ajar/absen/absensi_awal"


def _td_text(row, idx):
    """Teks sel ke-idx dari baris (strip). Mengikuti JS: td:eq(idx)."""
    tds = row.find_all("td")
    if idx < len(tds):
        return tds[idx].get_text(" ", strip=True)
    return ""


def _parse_row_action(row, btn):
    """Bangun aksi absen untuk satu baris: POST AJAX dengan param dari sel.
    Mengikuti JS:
      dsn = td:eq(1) split('-')[0]   (kode dosen)
      mk  = td:eq(2)                  (kode mata kuliah)
      tp  = td:eq(4)                  (teori/praktek)
      ja  = td:eq(5)                  (awal jam ke)
      jb  = td:eq(6)                  (akhir jam ke)
      kls = <input id=kls>.value      (kelas, misal 2A-JTK)
    """
    dsn_full = _td_text(row, 1)
    dsn = dsn_full.split("-")[0].strip()
    data = {
        "ja":  _td_text(row, 5),
        "jb":  _td_text(row, 6),
        "mk":  _td_text(row, 2),
        "dsn": dsn,
        "tp":  _td_text(row, 4),
        "kls": "",
    }
    kls_inp = row.find("input", id="kls") or row.find("input", {"id": "kls"})
    if kls_inp and kls_inp.get("value"):
        data["kls"] = kls_inp["value"].strip()

    # Signature untuk anti-duplikat & log (nama matkul + jam)
    nama_mk = _td_text(row, 3) or _td_text(row, 2)
    jam = _td_text(row, 7)
    sig = f"{nama_mk}|{jam}".strip("|")
    return {"sig": sig, "kind": "ajax", "url": ABSEN_ENDPOINT, "data": data,
            "nama_mk": nama_mk}


def http_find_blue(sess):
    """GET halaman absen, baca tabel #jadwal. Return (actions, skips):
      actions = list aksi absen untuk tombol BIRU (belum absen & waktunya)
      skips   = list (color, sig, alasan) baris yang di-skip
    Return (None, None) bila sesi mati (dilempar ke login)."""
    from bs4 import BeautifulSoup
    r = sess.get(TARGET_URL, allow_redirects=True, timeout=30)
    if _is_login_page(r.url, r.text):
        return None, None
    soup = BeautifulSoup(r.text, "html.parser")

    # Batasi ke tabel absen #jadwal — supaya tombol header (Profil/Logout)
    # TIDAK ikut terdeteksi (ini penyebab 'unknown/Profile' di log).
    table = soup.find("table", id="jadwal") or soup.find("table")
    actions, skips = [], []
    if not table:
        return actions, skips

    for row in table.find_all("tr"):
        # Tombol aksi di baris ini (anchor/button ber-class btn)
        btn = None
        for cand in row.find_all(["a", "button"]):
            cls = cand.get("class") or []
            if any("btn" in c for c in cls):
                btn = cand
                break
        if btn is None:
            continue
        if _is_nav_or_logout(btn):
            continue

        color = classify_classes(btn.get("class"))
        btn_txt = " ".join(btn.get_text(" ", strip=True).split()) or btn.get("value", "")
        nama_mk = _td_text(row, 3) or _td_text(row, 2)
        jam = _td_text(row, 7)
        sig = f"{btn_txt}|{nama_mk} {jam}".strip()

        if color != "blue":
            reason = "disabled" if btn.has_attr("disabled") else skip_reason(color)
            skips.append((color, sig, reason))
            continue
        if btn.has_attr("disabled"):
            skips.append((color, sig, "disabled"))
            continue

        # Tombol biru -> bangun aksi AJAX dari sel tabel
        actions.append(_parse_row_action(row, btn))
    return actions, skips


def _still_blue(sess, sig: str) -> bool:
    """True bila tombol `sig` MASIH biru (belum berhasil). False bila sudah
    hilang dari daftar biru (berhasil) atau halaman melempar ke login."""
    acts, _ = http_find_blue(sess)
    if acts is None:
        return False  # sesi mati -> diperlakukan selesai; pemanggil akan re-login
    return any(a["sig"] == sig for a in acts)


def _do_request(sess, a):
    """Kirim request absen. kind:
      ajax -> POST AJAX (X-Requested-With) ke endpoint, persis seperti jQuery halaman.
      get  -> GET link; post -> POST form."""
    if a["kind"] == "ajax":
        headers = {
            "X-Requested-With": "XMLHttpRequest",   # jQuery $.ajax
            "Referer": TARGET_URL,
            "Origin": BASE,
        }
        return sess.post(a["url"], data=a["data"], headers=headers, timeout=30)
    if a["kind"] == "get":
        return sess.get(a["url"], timeout=30)
    return sess.post(a["url"], data=a["data"], timeout=30)


def http_run_once(sess, clicked: set):
    actions, skips = http_find_blue(sess)
    if actions is None:
        log_warn("SESSION", "Sesi habis — re-login...")
        if not http_login(sess):
            return False
        actions, skips = http_find_blue(sess)
        actions = actions or []
        skips = skips or []

    # Ringkasan scan: hitung per warna (informatif untuk maintenance).
    counts = {}
    for color, _, _ in (skips or []):
        counts[color] = counts.get(color, 0) + 1
    log_info("SCAN", f"{len(actions)} biru siap-klik | "
                     f"hijau:{counts.get('green',0)} orange:{counts.get('orange',0)} "
                     f"merah:{counts.get('red',0)} lain:{counts.get('unknown',0)}")

    # Laporkan alasan skip untuk tiap tombol non-biru (detail per matkul).
    for color, sig, reason in (skips or []):
        log_skip(color, reason, sig)

    if not actions:
        log_info("SCAN", "Tidak ada tombol biru (sudah absen / dosen belum buka / di luar jadwal).")
        return True

    for a in actions:
        sig = a["sig"]
        if sig in clicked:
            log_info("KLIK", f"skip (sudah diklik hari ini): {sig[:60]}")
            continue
        log_info("ABSEN", f"target: {sig[:70]}")
        # Retry sampai tombol hilang dari daftar biru (= sukses) atau MAX_RETRY.
        done = False
        for attempt in range(1, MAX_RETRY + 1):
            jitter()
            try:
                _do_request(sess, a)
            except Exception as e:
                log_fail("ERROR", f"request gagal (percobaan {attempt}): {e} — {sig[:50]}")
                continue
            time.sleep(RETRY_WAIT)
            if not _still_blue(sess, sig):
                log_ok("ABSEN", f"BERHASIL (percobaan {attempt}): {sig[:55]}")
                clicked.add(sig)
                save_state(clicked)
                done = True
                break
            log_warn("RETRY", f"percobaan {attempt}/{MAX_RETRY} masih biru, tekan lagi — {sig[:50]}")
        if not done:
            log_fail("ABSEN", f"GAGAL setelah {MAX_RETRY} percobaan: {sig[:60]}. "
                             "Kemungkinan request ditolak server / bukan waktu absen.")
    return True


def engine_http(loop: bool):
    import requests
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA,
                         "Referer": BASE + "/"})
    if not http_login(sess):
        sys.exit(2)
    # Banner identitas di awal, sebelum flow absen.
    print_header(fetch_user_info(sess))
    clicked = load_state()
    log(f"Engine HTTP aktif. interval={INTERVAL}s loop={loop}")
    while True:
        try:
            http_run_once(sess, clicked)
        except Exception as e:
            log_fail("ERROR", f"siklus: {e}")
        if not loop:
            break
        log(f"Tidur {INTERVAL}s...")
        time.sleep(INTERVAL)

# ---------------------------------------------------------------
# ENGINE 2: Playwright — render penuh + auto-accept dialog konfirmasi
# ---------------------------------------------------------------
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
    # Kalau dilempar ke login -> login ulang
    if page.locator('form#fm input[name="username"]').count():
        pw_login(page)
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)
    btns = page.locator("table a.btn, table button.btn, table input.btn, "
                        ".content a.btn, .content button.btn, .content input.btn, "
                        "body a.btn, body button.btn, body input.btn")
    n = btns.count()
    found = 0
    for i in range(n):
        b = btns.nth(i)
        try:
            if b.get_attribute("disabled") is not None:
                continue
            color = b.evaluate(CLASSIFY_JS)
            if color != "blue":
                continue
            sig = b.evaluate(SIG_JS)
            if sig in clicked:
                continue
            found += 1
            log("ABSEN (pw) ->", sig[:70])
            b.scroll_into_view_if_needed()
            jitter()
            b.click(timeout=8000)
            clicked.add(sig)
            save_state(clicked)
            page.wait_for_timeout(random.randint(1000, 2000))
        except Exception as e:
            log("ERROR klik pw:", e)
    if found == 0:
        log("Tidak ada tombol biru (sudah absen / dosen belum buka / di luar jadwal).")


def pw_login(page):
    page.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
    page.fill('form#fm input[name="username"]', USERNAME)
    page.fill('form#fm input[name="password"]', PASSWORD)
    jitter(0.4, 0.9)
    page.click('form#fm button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    log("Login (pw) submitted")


def pw_fetch_user_info(page):
    """Ambil NIM, nama, jurusan dari .user-header (versi Playwright)."""
    info = {"nim": USERNAME, "nama": "", "jurusan": ""}
    try:
        if page.locator(".user-header").count() == 0:
            return info
        teks = " ".join(page.locator(".user-header").first.inner_text().split())
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
        else:
            if teks:
                info["nama"] = teks
    except Exception as e:
        log_warn("USER", f"gagal baca info user (pw): {e}")
    return info


def engine_pw(loop: bool):
    from playwright.sync_api import sync_playwright
    clicked = load_state()
    log(f"Engine Playwright aktif. interval={INTERVAL}s loop={loop}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(user_agent=UA, locale="id-ID",
                                  timezone_id="Asia/Jakarta")
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())  # auto-accept confirm()
        pw_login(page)
        # Banner identitas di awal, sebelum flow absen.
        print_header(pw_fetch_user_info(page))
        while True:
            try:
                pw_click_pass(page, clicked)
            except Exception as e:
                log_fail("ERROR", f"siklus pw: {e}")
            if not loop:
                break
            log(f"Tidur {INTERVAL}s...")
            time.sleep(INTERVAL)
        browser.close()

# ---------------------------------------------------------------
def dump_absen_html(path: str = None):
    """Login lalu simpan HTML halaman absen mentah ke file — untuk diagnostik
    (misal tombol biru tidak terdeteksi). File berisi HTML mentah; JANGAN
    di-commit / dibagikan publik karena memuat data sesi."""
    import requests
    out = path or str(Path(__file__).resolve().parent / "absen-dump.html")
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Referer": BASE + "/"})
    if not http_login(sess):
        print("Login GAGAL — cek NIM/password.", file=sys.stderr)
        sys.exit(2)
    r = sess.get(TARGET_URL, allow_redirects=True, timeout=30)
    Path(out).write_text(r.text, encoding="utf-8")
    log(f"HTML halaman absen disimpan ke: {out}")
    log("Buka file itu, cari tombol absen, lalu kirim strukturnya untuk penyesuaian selector.")


def main():
    ap = argparse.ArgumentParser(description="Polban Auto Absen (Windows .bat / Termux)")
    ap.add_argument("--engine", choices=["http", "pw"],
                    default=os.environ.get("POLBAN_ENGINE", "http"),
                    help="http=requests ringan (default), pw=Playwright")
    ap.add_argument("--once", action="store_true",
                    help="sekali jalan lalu exit (untuk cron)")
    ap.add_argument("--dump", nargs="?", const="", default=None,
                    help="simpan HTML halaman absen ke file lalu exit (diagnostik)")
    args = ap.parse_args()

    if not USERNAME or not PASSWORD:
        print("ERROR: POLBAN_USERNAME / POLBAN_PASSWORD belum terisi.\n", file=sys.stderr)
        if ENV_PATH_USED:
            print(f"  .env ditemukan di: {ENV_PATH_USED}", file=sys.stderr)
            print("  → tapi nilai masih kosong. Pastikan format:\n"
                  "       POLBAN_USERNAME=NIM_kamu\n"
                  "       POLBAN_PASSWORD=password_kamu\n"
                  "    (tanpa kutip, tanpa spasi di sekitar '=')", file=sys.stderr)
        else:
            print("  .env TIDAK ditemukan. Dicari di (urutan):", file=sys.stderr)
            print("    1. env var POLBAN_ENV", file=sys.stderr)
            print(f"    2. {Path(__file__).resolve().parent / '.env'}", file=sys.stderr)
            print(f"    3. {Path.cwd() / '.env'}", file=sys.stderr)
            print(f"    4. {Path(__file__).resolve().parent.parent / '.env'}", file=sys.stderr)
            print("  → salin .env.example jadi .env lalu isi.", file=sys.stderr)
        sys.exit(1)

    if ENV_PATH_USED:
        log(f"Config: {ENV_PATH_USED} (NIM {USERNAME})")

    if args.dump is not None:
        dump_absen_html(args.dump or None)
        return

    loop = not args.once
    if args.engine == "pw":
        engine_pw(loop)
    else:
        engine_http(loop)


if __name__ == "__main__":
    main()
