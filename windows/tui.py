#!/usr/bin/env python3
# Copyright (c) 2026 Haikal. All rights reserved.
# Polban Auto Absen -- TUI module (rich-based live dashboard)
# Hanya UI layer. Tidak mengandung engine logic.
"""Modern terminal dashboard untuk Polban Auto Absen.

File ini SAMA PERSIS di windows/ dan termux/ (label platform dideteksi
otomatis saat runtime), dan merupakan port dari linux/tui.py.

Dua mode:
  1. Live dashboard (default) -- rich.live.Live, panel di-update in-place.
  2. Plain fallback           -- terminal non-interaktif, --plain, atau
                                rich tidak terpasang.

Prinsip:
  - Tidak ada print() berulang. Semua lewat Live context.
  - Tabel jadwal hanya berubah visual saat status berubah.
  - Countdown timer mengisi jeda antar-scan.
  - Ring buffer log 15 entri, tidak scroll tak terbatas.

Catatan Windows:
  - VT/ANSI diaktifkan lewat kernel32.SetConsoleMode supaya warna & alternate
    screen jalan juga di conhost lama (cmd.exe klasik), bukan hanya Windows
    Terminal.
  - stdout dipaksa UTF-8 supaya border rich tidak jadi '?' di code page 437.
"""

from __future__ import annotations  # anotasi jadi lazy -> tui.py tetap bisa
# di-import walau `rich` belum terpasang (nama Panel/Group/Live baru dipakai
# saat dashboard benar-benar digambar, bukan saat class didefinisikan).

import os
import shutil
import sys
import time
from collections import deque
from datetime import datetime
from threading import RLock

try:
    from rich.align import Align
    from rich.box import ASCII as BOX_ASCII, ROUNDED as BOX_ROUNDED
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ---------------------------------------------------------------
# Kompatibilitas terminal (Windows conhost / Termux)
# ---------------------------------------------------------------
def _enable_windows_ansi() -> bool:
    """Aktifkan VIRTUAL_TERMINAL_PROCESSING di console Windows.

    Return True bila berhasil (atau bukan Windows). Tanpa ini, conhost lama
    mencetak escape code mentah seperti '[32m' alih-alih warna."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ENABLE_VT = 0x0004
        ok = True
        for handle_id in (-11, -12):  # STDOUT, STDERR
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | ENABLE_VT)
            else:
                ok = False
        return ok
    except Exception:
        return False


def _force_utf8_stdout():
    """Paksa stdout/stderr ke UTF-8 (Python 3.7+)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass


def fit_console_width() -> None:
    """Windows: lebarkan buffer console agar dashboard memakai seluruh jendela.

    cmd.exe/conhost membuka console dengan buffer tetap (umumnya 120 kolom).
    Isi console TIDAK BOLEH melebihi lebar buffer, jadi waktu jendelanya
    di-maximize sisi kanan tinggal area kosong -- bukan karena layout-nya
    kurang lebar, tapi karena rich memang cuma dijatah 120 kolom.

    Yang dilakukan: hitung berapa kolom yang sebenarnya muat di jendela (lebar
    area gambar dibagi lebar sel huruf), lalu kalau buffer lebih sempit dari itu,
    buffer DAN viewport-nya dilebarkan. Hanya membesarkan, tidak pernah
    mengecilkan, jadi jendela yang sengaja dibuat kecil tidak diganggu.
    Semua dibungkus try/except: gagal = diam-diam dilewati.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class COORD(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [("Left", wintypes.SHORT), ("Top", wintypes.SHORT),
                        ("Right", wintypes.SHORT), ("Bottom", wintypes.SHORT)]

        class CSBI(ctypes.Structure):
            _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD),
                        ("wAttributes", wintypes.WORD), ("srWindow", SMALL_RECT),
                        ("dwMaximumWindowSize", COORD)]

        class CONSOLE_FONT_INFO(ctypes.Structure):
            _fields_ = [("nFont", wintypes.DWORD), ("dwFontSize", COORD)]

        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-11)
        info = CSBI()
        if not k32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
            return

        win_cols = info.srWindow.Right - info.srWindow.Left + 1
        win_rows = info.srWindow.Bottom - info.srWindow.Top + 1

        k32.GetLargestConsoleWindowSize.restype = COORD
        largest = int(k32.GetLargestConsoleWindowSize(handle).X)

        # Berapa kolom yang SEBENARNYA muat di jendela? Diukur dari lebar area
        # gambar jendela (piksel) dibagi lebar satu sel huruf. Ini yang dipakai,
        # bukan status maximize -- jendela yang diperlebar dengan tarikan mouse
        # pun ikut terdeteksi, dan mode --once yang cuma hidup beberapa detik
        # tidak perlu menunggu pengecekan berikutnya.
        target = 0
        hwnd = k32.GetConsoleWindow()
        if hwnd:
            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            font = CONSOLE_FONT_INFO()
            if (user32.GetClientRect(hwnd, ctypes.byref(rect))
                    and k32.GetCurrentConsoleFont(handle, False, ctypes.byref(font))
                    and font.dwFontSize.X > 0):
                muat = (rect.right - rect.left) // int(font.dwFontSize.X)
                if 20 <= muat <= largest:
                    target = muat
            # Cadangan: jendela di-maximize tapi ukuran selnya tidak terbaca
            # (misal font proporsional aneh) -> pakai ukuran layar penuh.
            if not target and user32.IsZoomed(hwnd):
                target = largest

        if target <= win_cols:
            return  # sudah selebar yang muat -- tidak ada yang perlu dibenahi

        # Buffer harus dibesarkan DULU, baru jendelanya boleh ikut melebar.
        k32.SetConsoleScreenBufferSize(
            handle, COORD(target, max(int(info.dwSize.Y), win_rows)))
        k32.SetConsoleWindowInfo(handle, True, ctypes.byref(
            SMALL_RECT(0, info.srWindow.Top, target - 1, info.srWindow.Bottom)))
    except Exception:
        pass


def _set_console_title(title: str):
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def platform_label() -> str:
    """Label platform untuk subtitle banner."""
    if os.name == "nt":
        return "Windows"
    if "com.termux" in os.environ.get("PREFIX", ""):
        return "Termux"
    return "Linux"


def term_width(default: int = 80) -> int:
    return shutil.get_terminal_size((default, 24)).columns


# ---------------------------------------------------------------
# ASCII Art Header
# ---------------------------------------------------------------
ASCII_BANNER = r"""
    ___         __           ___    __
   /   | __  __/ /_____     /   |  / /_  ________  ____
  / /| |/ / / / __/ __ \   / /| | / __ \/ ___/ _ \/ __ \
 / ___ / /_/ / /_/ /_/ /  / ___ |/ /_/ (__  )  __/ / / /
/_/  |_\__,_/\__/\____/  /_/  |_/_.___/____/\___/_/ /_/
"""

BANNER_WIDTH = max(len(l) for l in ASCII_BANNER.strip("\n").splitlines())
VERSION = "v2.0"
SUBTITLE = f"Polban Auto Absen -- {platform_label()} {VERSION}"
COMPACT_TITLE = ">>> POLBAN AUTO ABSEN <<<"


def print_ascii_banner():
    """Cetak ASCII art ke stdout (dipakai plain mode)."""
    cols = term_width()
    if cols < BANNER_WIDTH + 2:
        print(COMPACT_TITLE.center(cols))
        print(SUBTITLE.center(cols))
        print()
        return
    lines = ASCII_BANNER.strip("\n").splitlines()
    pad = " " * max(0, (cols - BANNER_WIDTH) // 2)
    for line in lines:
        print(pad + line)
    print(SUBTITLE.center(cols))
    print()


# ---------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------
# Hanya EMPAT status, sesuai warna tombol di halaman akademik. Hasil klik
# otomatis tidak memunculkan status baru: baris yang berhasil diabsenkan
# langsung menjadi SUDAH ABSEN (hijau), yang gagal tetap SIAP ABSEN (biru)
# dan akan dicoba lagi -- kegagalannya dilaporkan lewat Log Aktivitas.
STATUS_LABELS = {
    "blue":    "SIAP ABSEN",
    "green":   "SUDAH ABSEN",
    "orange":  "BELUM BUKA",
    "red":     "BELUM WAKTUNYA",
    "unknown": "TIDAK DIKENALI",   # cadangan; tidak seharusnya muncul
}

STATUS_STYLES = {
    "blue":    "bold cyan",
    "green":   "bold green",
    "orange":  "bold yellow",
    "red":     "bold red",
    "unknown": "dim",
}

LEVEL_STYLES = {
    "ok":   "green",
    "fail": "bold red",
    "warn": "yellow",
    "info": "dim white",
    "skip": "dim cyan",
}

LEVEL_TAGS = {
    "ok":   "[OK]",
    "fail": "[!!]",
    "warn": "[??]",
    "info": "[--]",
    "skip": "[>>]",
}


# ---------------------------------------------------------------
# Data models
# ---------------------------------------------------------------
class MataKuliah:
    """Satu baris matkul di tabel jadwal."""
    __slots__ = ("nama", "jam", "dosen", "status")

    def __init__(self, nama: str, jam: str = "", dosen: str = "",
                 status: str = "unknown"):
        self.nama = nama
        self.jam = jam
        self.dosen = nama_dosen(dosen)
        self.status = status


class LogEntry:
    """Satu baris di activity log."""
    __slots__ = ("timestamp", "code", "message", "level")

    def __init__(self, code: str, message: str, level: str = "info"):
        self.timestamp = time.strftime("%H:%M:%S")
        self.code = code
        self.message = message
        self.level = level


def nama_dosen(teks: str) -> str:
    """Buang kode dosen di depan: 'KO078N-Trisna Gelar Abdillah, S.T., M.Kom'
    -> 'Trisna Gelar Abdillah, S.T., M.Kom'.

    Hanya dipotong kalau bagian sebelum '-' memang berbentuk kode (pendek,
    tanpa spasi), supaya nama yang mengandung tanda hubung tidak ikut terpotong.
    """
    t = " ".join(str(teks or "").split())
    if "-" in t:
        kode, sisa = t.split("-", 1)
        kode, sisa = kode.strip(), sisa.strip()
        # Kode dosen selalu memuat angka (KO078N, BD011N, ...) -- syarat ini
        # mencegah nama bertanda hubung seperti "Ana-Maria" ikut terpotong.
        if (sisa and kode and " " not in kode and len(kode) <= 12
                and any(c.isdigit() for c in kode)):
            return sisa
    return t


def _split_sig(sig: str):
    """Pecah signature engine jadi (nama_mk, dosen, jam).

    Engine memakai DUA bentuk signature:
      - baris yang di-skip : 'teks_tombol|nama_mk|dosen|jam'  (4 bagian)
      - aksi absen         : 'nama_mk|dosen|jam'              (3 bagian)
    Keduanya harus menghasilkan nama matkul yang sama, kalau tidak baris hasil
    klik tidak akan ketemu waktu status diperbarui.
    Playwright memakai 'teks_tombol|teks_baris' (2 bagian)."""
    parts = [p.strip() for p in str(sig).split("|")]
    if len(parts) >= 4:
        return parts[1], parts[2], parts[3]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[1], "", ""
    return parts[0] if parts else str(sig), "", ""


# ---------------------------------------------------------------
# TUI Dashboard (rich)
# ---------------------------------------------------------------
class _LiveView:
    """Renderable dinamis untuk rich.live.Live.

    Layout dibangun ULANG setiap kali frame digambar (bukan sekali saat Live
    dibuat), jadi dashboard langsung ikut menyesuaikan waktu jendela terminal
    di-maximize / di-restore / diseret lebarnya -- tanpa perlu menunggu event
    berikutnya dari engine.
    """

    __slots__ = ("_dash",)

    def __init__(self, dashboard):
        self._dash = dashboard

    def __rich_console__(self, console, options):
        yield self._dash._build_layout()


class Dashboard:
    """Live terminal dashboard. Thread-safe."""

    MAX_LOG = 15

    def __init__(self, plain: bool = False, alt_screen: bool = True):
        self._plain = plain or not HAS_RICH
        self._alt_screen = alt_screen
        # RLock: layout digambar oleh thread refresh milik rich sementara
        # engine menulis state dari thread utama -- keduanya mengunci.
        self._lock = RLock()

        # State
        self._user_info = {"nim": "", "nama": "", "jurusan": ""}
        self._auth_status = "..."
        self._last_scan_info = "Menunggu scan awal..."
        self._engine = "http"
        self._interval = 60
        self._countdown = 0
        self._jadwal = []          # list[MataKuliah]
        self._log = deque(maxlen=self.MAX_LOG)
        self._cycle_count = 0
        self._stat_ok = 0
        self._stat_fail = 0
        # Nama matkul yang sudah berhasil diabsenkan di sesi ini -- dipakai agar
        # barisnya tetap SUDAH ABSEN walau scan berikutnya belum ikut berubah.
        self._absen_sukses = set()

        # Rich objects
        if not self._plain:
            _force_utf8_stdout()
            _enable_windows_ansi()
            fit_console_width()
            _set_console_title("Polban Auto Absen")
            self._last_fit = 0.0
            self._console = Console()
            self._live = None
            # conhost lama: border unicode sering pecah -> pakai box ASCII
            self._box = BOX_ASCII if getattr(self._console, "legacy_windows", False) else BOX_ROUNDED

    # -- public API --------------------------------------------------

    def set_user_info(self, info: dict):
        with self._lock:
            self._user_info = info or {}
        self._refresh()

    def set_auth_status(self, status: str):
        with self._lock:
            self._auth_status = status
        self._refresh()

    def set_last_scan(self, info: str):
        with self._lock:
            self._last_scan_info = info
        self._refresh()

    def set_engine(self, engine: str, interval: int):
        with self._lock:
            self._engine = engine
            self._interval = interval
        self._refresh()

    def set_countdown(self, seconds: int):
        with self._lock:
            self._countdown = seconds
        self._refresh()

    def increment_cycle(self):
        with self._lock:
            self._cycle_count += 1
        self._refresh()

    def update_jadwal(self, actions: list, skips: list) -> bool:
        """Rebuild tabel jadwal dari actions (biru) dan skips.
        Return True jika ada perubahan status dibanding scan sebelumnya."""
        with self._lock:
            old_states = {mk.nama: mk.status for mk in self._jadwal}
            jadwal = []

            # Skips dulu (sudah absen / belum buka / dll.)
            for item in (skips or []):
                # `reason` ikut dibawa engine tapi tidak ditampilkan: alasannya
                # sudah terbaca dari kolom Status.
                color, sig = item[0], item[1]
                nama, dosen, jam = _split_sig(sig)
                jadwal.append(MataKuliah(nama=nama[:48], jam=jam, dosen=dosen,
                                         status=color))

            # Actions (biru / siap klik)
            for a in (actions or []):
                nama = a.get("nama_mk") or _split_sig(a.get("sig", "?"))[0]
                jadwal.append(MataKuliah(
                    nama=str(nama)[:48],
                    jam=a.get("jam", "") or _split_sig(a.get("sig", ""))[2],
                    dosen=a.get("dosen", "") or _split_sig(a.get("sig", ""))[1],
                    status="blue",
                ))

            changed = False
            for mk in jadwal:
                # Baris yang sudah berhasil diabsenkan di sesi ini tetap
                # SUDAH ABSEN, walau scan berikutnya sempat melaporkan warna
                # lama (server kadang telat memperbarui tombolnya).
                if mk.nama in self._absen_sukses:
                    mk.status = "green"
                if mk.nama in old_states and old_states[mk.nama] != mk.status:
                    changed = True
            if len(old_states) != len(jadwal) and len(old_states) > 0:
                changed = True

            self._jadwal = jadwal
        self._refresh()
        return changed

    def mark_result(self, sig: str, success: bool, nama: str = ""):
        """Update baris jadwal setelah dicoba diabsenkan.

        Berhasil -> langsung jadi SUDAH ABSEN (hijau), sama seperti matkul yang
        memang sudah hijau dari sananya. Gagal -> TETAP SIAP ABSEN (biru) supaya
        ikut dicoba lagi di siklus berikutnya; sebab gagalnya ada di log.

        `nama` sebaiknya diisi engine (a['nama_mk']) supaya pencocokan barisnya
        pasti; `sig` hanya dipakai sebagai cadangan."""
        target = (nama or "").strip() or _split_sig(sig)[0] \
            or str(sig).split("|")[0].strip()
        with self._lock:
            if success:
                self._stat_ok += 1
                if target:
                    self._absen_sukses.add(target)
            else:
                self._stat_fail += 1
            for mk in self._jadwal:
                if target and (target in mk.nama or mk.nama in target):
                    # Berhasil -> hijau. Gagal -> tetap biru supaya diulang;
                    # sebab gagalnya dilaporkan lewat Log Aktivitas.
                    mk.status = "green" if success else "blue"
                    break
        self._refresh()

    def push_event(self, code: str, message: str, level: str = "info"):
        """Tambah baris ke activity log."""
        entry = LogEntry(code, message, level)
        with self._lock:
            self._log.append(entry)
        if self._plain:
            tag = LEVEL_TAGS.get(level, "[--]")
            print(f"[{entry.timestamp}] {tag} [{code}] {message}", flush=True)
        else:
            self._refresh()

    def start(self):
        """Mulai live dashboard."""
        if self._plain:
            print_ascii_banner()
            return
        # screen=True mengaktifkan Alternate Screen Buffer (seperti vim/htop):
        # layar bersih, riwayat shell tidak ikut ter-scroll.
        # _LiveView bikin layout dibangun ulang tiap frame -> responsif saat
        # jendela diubah ukurannya; 4 fps supaya resize terasa langsung.
        self._live = Live(
            _LiveView(self),
            console=self._console,
            refresh_per_second=4,
            screen=self._alt_screen,
        )
        self._live.start()

    def stop(self):
        """Hentikan live dashboard."""
        live = getattr(self, "_live", None)
        if live:
            try:
                live.stop()
            except Exception:
                pass
            self._live = None

    def render_summary(self):
        """Cetak ringkasan singkat SETELAH live dashboard ditutup.

        Hanya perlu kalau dashboard digambar di alternate screen -- layar itu
        dihapus saat keluar, jadi hasil akhirnya ikut hilang. Tanpa alternate
        screen (mis. mode --once) dashboard penuh tetap tertinggal di layar,
        jadi ringkasan ini dilewati supaya tidak dobel."""
        if self._plain or not HAS_RICH or not self._alt_screen:
            return
        try:
            info = self._user_info or {}
            console = self._console
            console.print()
            console.print(f"[bold cyan]{COMPACT_TITLE}[/bold cyan]  "
                          f"[dim]{SUBTITLE}[/dim]")
            console.print(f"  Nama    : [bold]{info.get('nama') or '-'}[/bold]  "
                          f"(NIM {info.get('nim') or '-'})")
            console.print(f"  Siklus  : {self._cycle_count}   "
                          f"[green]berhasil {self._stat_ok}[/green]   "
                          f"[red]gagal {self._stat_fail}[/red]")
            console.print(f"  Scan    : {self._last_scan_info}")
            for mk in self._jadwal:
                label = STATUS_LABELS.get(mk.status, mk.status.upper())
                style = STATUS_STYLES.get(mk.status, "")
                console.print(f"   - {mk.nama} {mk.jam}  [{style}]{label}[/{style}]"
                              + (f"  [dim]{mk.dosen}[/dim]" if mk.dosen else ""))
            console.print()
        except Exception:
            pass

    # -- internal ----------------------------------------------------

    def _refresh(self):
        live = getattr(self, "_live", None)
        if self._plain or live is None:
            return
        try:
            # Renderable-nya dinamis (_LiveView), jadi cukup minta gambar ulang.
            live.refresh()
        except Exception:
            pass  # Jangan crash karena render error

    def _build_banner(self) -> Group:
        """Render banner ASCII art di dalam alternate screen buffer."""
        size = self._console.size
        if size.height >= 22 and size.width >= BANNER_WIDTH + 8:
            head = Text(ASCII_BANNER.strip("\n"), style="bold cyan")
        else:
            head = Text(COMPACT_TITLE, style="bold cyan")
        return Group(
            Align.center(head),
            Align.center(Text(SUBTITLE, style="dim white")),
            Text(""),
        )

    def _build_layout(self) -> Panel:
        """Render full dashboard sebagai satu Panel."""
        # Kalau user me-maximize jendela di tengah jalan, buffer console perlu
        # ikut dilebarkan. Dicek paling sering sekali per detik supaya tidak
        # membebani loop render.
        now = time.monotonic()
        if now - getattr(self, "_last_fit", 0.0) > 1.0:
            self._last_fit = now
            fit_console_width()

        parts = [
            self._build_banner(),
            self._build_status_bar(),
            Text(""),
            self._build_jadwal_panel(),
            Text(""),
            self._build_log_panel(),
        ]
        return Panel(
            Group(*parts),
            title="[bold]POLBAN AUTO ABSEN[/bold]",
            subtitle=(f"[dim]{VERSION} {platform_label().lower()} | "
                      f"siklus #{self._cycle_count} | Ctrl+C untuk keluar[/dim]"),
            border_style="bright_blue",
            box=self._box,
            padding=(1, 2),
            expand=True,
        )

    def _build_status_bar(self) -> Panel:
        """Panel identitas + status. Label dipendekkan di terminal sempit."""
        with self._lock:
            info = dict(self._user_info or {})
            auth = self._auth_status
            last_scan = self._last_scan_info
            engine, interval = self._engine, self._interval
            countdown = self._countdown
            ok, fail = self._stat_ok, self._stat_fail

        nama = info.get("nama", "") or "-"
        nim = info.get("nim", "") or "-"
        jurusan = info.get("jurusan", "") or ""
        auth_style = "green" if ("OK" in auth or "Authenticated" in auth) else (
            "yellow" if "..." in auth or "re-login" in auth.lower() else "red")

        countdown_str = f"{countdown // 60:02d}:{countdown % 60:02d}"
        tgl = datetime.now().strftime("%A, %d %B %Y")
        width = self._console.size.width

        lines = Text()
        lines.append("  Nama       : ", style="dim")
        lines.append(f"{nama}\n", style="bold")
        lines.append("  NIM        : ", style="dim")
        lines.append(f"{nim}\n")
        if jurusan:
            lines.append("  Jurusan    : ", style="dim")
            lines.append(f"{jurusan}\n")
        lines.append("  Tanggal    : ", style="dim")
        lines.append(f"{tgl}\n")
        lines.append("\n")
        lines.append("  Status     : ", style="dim")
        lines.append(f"{auth}\n", style=auth_style)
        # Ringkasan scan cukup panjang: di jendela sempit ditaruh di baris
        # sendiri (menjorok) supaya tidak patah di tengah kalimat.
        if width < 86:
            lines.append("  Hasil Scan :\n     ", style="dim")
            lines.append(f"{last_scan}\n")
        else:
            lines.append("  Hasil Scan : ", style="dim")
            lines.append(f"{last_scan}\n")
        # Baris terakhir dipecah dua kalau jendelanya sempit, supaya tidak
        # membungkus di tengah angka.
        lines.append("  Engine     : ", style="dim")
        lines.append(f"{engine}   ")
        lines.append("Interval : ", style="dim")
        lines.append(f"{interval}s   ")
        lines.append("Next scan : ", style="dim")
        lines.append(f"{countdown_str}", style="bold cyan")
        lines.append("\n  Absen      : " if width < 86 else "   Absen : ", style="dim")
        lines.append(f"{ok} berhasil", style="green")
        lines.append(" / ", style="dim")
        lines.append(f"{fail} gagal", style="red")

        return Panel(lines, title="[bold]Identitas[/bold]",
                     border_style="dim", box=self._box)

    def _build_jadwal_panel(self) -> Panel:
        """Tabel jadwal matkul hari ini.

        Isi tabel (matkul, jam, dosen) memakai warna teks normal -- BUKAN
        'dim' -- supaya sama terbacanya; dim di terminal gelap jadi abu-abu
        yang nyaris tenggelam ke latar.

        Tiga tingkat, menyesuaikan lebar jendela saat itu juga:
          >= 96 kolom : No | Mata Kuliah | Jam | Status | Keterangan
          >= 62 kolom : Jam pindah ke bawah nama matkul
          <  62 kolom : Keterangan ikut pindah ke bawah nama matkul
        """
        width = self._console.size.width
        narrow = width < 96
        tiny = width < 62

        table = Table(show_header=True, header_style="bold", expand=True,
                      show_lines=False, pad_edge=True, box=self._box)
        table.add_column("No", style="dim", width=3, justify="right")
        table.add_column("Mata Kuliah", ratio=3, min_width=14)
        if not narrow:
            # 'HH:MM:SS s.d. HH:MM:SS' = 22 karakter: dikunci supaya tidak
            # dipatahkan jadi dua baris padahal ruangnya cukup.
            table.add_column("Jam", width=22)
        # 'BELUM WAKTUNYA' = 14 karakter. Lebar DIKUNCI (bukan ratio) supaya
        # tidak pernah terpotong jadi 'SUDAH A...' di terminal sempit.
        table.add_column("Status", width=14, justify="center", no_wrap=True)
        if not tiny:
            table.add_column("Dosen", ratio=3, min_width=14)

        n_col = 3 + (0 if narrow else 1) + (0 if tiny else 1)

        with self._lock:
            jadwal = list(self._jadwal)

        if not jadwal:
            kosong = ["", "[dim]Belum ada data jadwal[/dim]"]
            table.add_row(*(kosong + [""] * (n_col - 2)))
        else:
            for i, mk in enumerate(jadwal, 1):
                status = Text(STATUS_LABELS.get(mk.status, mk.status.upper()),
                              style=STATUS_STYLES.get(mk.status, ""))
                if narrow:
                    nama = Text(mk.nama)
                    if mk.jam:
                        nama.append(f"\n{mk.jam}")
                    if tiny and mk.dosen:
                        nama.append(f"\n{mk.dosen}")
                    row = [str(i), nama, status]
                    if not tiny:
                        row.append(mk.dosen or "-")
                    table.add_row(*row)
                else:
                    table.add_row(str(i), mk.nama, mk.jam, status,
                                  mk.dosen or "-")

        return Panel(table, title="[bold]Jadwal Hari Ini[/bold]",
                     border_style="dim", box=self._box)

    def _build_log_panel(self) -> Panel:
        """Ring buffer activity log.

        Jumlah baris menyesuaikan tinggi jendela: di terminal pendek hanya
        beberapa entri terakhir yang ditampilkan supaya panel lain tidak
        terdorong keluar layar."""
        with self._lock:
            entries = list(self._log)

        height = self._console.size.height
        # Sisakan ruang untuk banner + identitas + tabel jadwal.
        muat = max(3, min(len(entries), height - 22))
        shown = entries[-muat:]

        if not shown:
            content = Text("  Belum ada aktivitas.", style="dim")
        else:
            content = Text()
            for entry in shown:
                content.append(f"  {entry.timestamp}  ", style="dim")
                content.append(f"{LEVEL_TAGS.get(entry.level, '[--]')} ",
                               style=LEVEL_STYLES.get(entry.level, ""))
                content.append(f"[{entry.code}] ", style="bold")
                content.append(f"{entry.message}\n")

        judul = (f"[bold]Log Aktivitas ({len(shown)} terakhir)[/bold]"
                 if len(shown) == len(entries) else
                 f"[bold]Log Aktivitas ({len(shown)} dari {len(entries)})[/bold]")
        return Panel(content, title=judul, border_style="dim", box=self._box)


# ---------------------------------------------------------------
# Plain-text fallback (no rich)
# ---------------------------------------------------------------
class PlainDashboard(Dashboard):
    """Fallback ketika rich tidak tersedia atau --plain/--once dipakai."""

    def __init__(self):
        super().__init__(plain=True)
        self._jadwal_printed = False

    def start(self):
        _force_utf8_stdout()
        print_ascii_banner()

    def set_user_info(self, info: dict):
        with self._lock:
            self._user_info = info or {}
        info = self._user_info
        garis = "=" * 56
        print(garis)
        if info.get("nama"):
            print(f"  Nama    : {info['nama']}")
        print(f"  NIM     : {info.get('nim', '-')}")
        if info.get("jurusan"):
            print(f"  Jurusan : {info['jurusan']}")
        print(f"  Waktu   : {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Engine  : {self._engine}   Interval : {self._interval}s")
        print(garis, flush=True)

    def update_jadwal(self, actions, skips):
        """Plain mode tidak punya tabel, jadi jadwal dicetak sebagai daftar.

        Hanya saat scan pertama atau ketika ada status yang berubah -- bukan
        tiap siklus -- supaya log (dan absen.log di Termux) tidak membengkak."""
        changed = super().update_jadwal(actions, skips)
        if changed or not self._jadwal_printed:
            self._jadwal_printed = True
            with self._lock:
                jadwal = list(self._jadwal)
            print(f"[{time.strftime('%H:%M:%S')}] Jadwal hari ini:")
            if not jadwal:
                print("     (tidak ada baris jadwal terbaca)")
            for i, mk in enumerate(jadwal, 1):
                label = STATUS_LABELS.get(mk.status, mk.status.upper())
                jam = f"  {mk.jam}" if mk.jam else ""
                dosen = f"  [{mk.dosen}]" if mk.dosen else ""
                print(f"     {i}. {mk.nama}{jam}  -> {label}{dosen}")
            print(flush=True)
        return changed

    def set_countdown(self, seconds):
        with self._lock:
            self._countdown = seconds

    def set_auth_status(self, status):
        with self._lock:
            self._auth_status = status

    def set_last_scan(self, info):
        with self._lock:
            self._last_scan_info = info

    def increment_cycle(self):
        with self._lock:
            self._cycle_count += 1

    def mark_result(self, sig: str, success: bool):
        with self._lock:
            if success:
                self._stat_ok += 1
            else:
                self._stat_fail += 1

    def render_summary(self):
        print(f"\nRingkasan: {self._cycle_count} siklus | "
              f"{self._stat_ok} berhasil | {self._stat_fail} gagal", flush=True)


def create_dashboard(plain: bool = False, alt_screen: bool = True) -> Dashboard:
    """Factory: buat Dashboard yang tepat berdasar kemampuan terminal."""
    if plain or not HAS_RICH:
        return PlainDashboard()
    if not sys.stdout.isatty():
        return PlainDashboard()
    return Dashboard(alt_screen=alt_screen)
