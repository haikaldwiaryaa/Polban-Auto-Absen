#!/usr/bin/env python3
# Copyright (c) 2026 Haikal. All rights reserved.
# Polban Auto Absen — TUI module (rich-based live dashboard)
# Hanya UI layer. Tidak mengandung engine logic.
"""
Modern terminal dashboard for Polban Auto Absen (Linux).

Dua mode:
  1. Live dashboard (default) — rich.live.Live, panel di-update in-place.
  2. Plain fallback           — non-interactive terminal atau --plain.

Prinsip:
  - Tidak ada print() berulang. Semua lewat Live context.
  - Tabel jadwal hanya berubah visual saat status berubah.
  - Countdown timer mengisi jeda antar-scan.
  - Ring buffer log 15 entri, tidak scroll tak terbatas.
"""

import shutil
import time
from collections import deque
from datetime import datetime
from threading import Lock

try:
    from rich.align import Align
    from rich.columns import Columns
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.padding import Padding
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


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

SUBTITLE = "Polban Auto Absen -- Linux v2.0"


def print_ascii_banner():
    """Cetak ASCII art ke stdout dengan block indentation akurat."""
    cols = shutil.get_terminal_size((80, 24)).columns
    lines = ASCII_BANNER.strip("\n").splitlines()
    max_len = max(len(l) for l in lines)
    pad = " " * max(0, (cols - max_len) // 2)
    for line in lines:
        print(pad + line)
    print(SUBTITLE.center(cols))
    print()


# ---------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------
STATUS_LABELS = {
    "blue":    "SIAP ABSEN",
    "green":   "SUDAH ABSEN",
    "orange":  "BELUM BUKA",
    "red":     "DI LUAR JADWAL",
    "unknown": "TIDAK DIKENALI",
    "clicked": "BERHASIL",
    "failed":  "GAGAL",
    "waiting": "MENUNGGU...",
}

STATUS_STYLES = {
    "blue":    "bold cyan",
    "green":   "bold green",
    "orange":  "yellow",
    "red":     "bold red",
    "unknown": "dim",
    "clicked": "bold green",
    "failed":  "bold red",
    "waiting": "bold yellow",
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
    __slots__ = ("nama", "jam", "status", "detail")

    def __init__(self, nama: str, jam: str = "", status: str = "unknown",
                 detail: str = ""):
        self.nama = nama
        self.jam = jam
        self.status = status
        self.detail = detail


class LogEntry:
    """Satu baris di activity log."""
    __slots__ = ("timestamp", "code", "message", "level")

    def __init__(self, code: str, message: str, level: str = "info"):
        self.timestamp = time.strftime("%H:%M:%S")
        self.code = code
        self.message = message
        self.level = level


# ---------------------------------------------------------------
# TUI Dashboard (rich)
# ---------------------------------------------------------------
class Dashboard:
    """Live terminal dashboard. Thread-safe."""

    MAX_LOG = 15

    def __init__(self, plain: bool = False):
        self._plain = plain or not HAS_RICH
        self._lock = Lock()

        # State
        self._user_info = {"nim": "", "nama": "", "jurusan": ""}
        self._auth_status = "..."
        self._last_scan_info = "Menunggu scan awal..."
        self._engine = "http"
        self._interval = 60
        self._countdown = 0
        self._jadwal: list[MataKuliah] = []
        self._log: deque[LogEntry] = deque(maxlen=self.MAX_LOG)
        self._cycle_count = 0

        # Rich objects
        if not self._plain:
            self._console = Console()
            self._live: Live | None = None

    # -- public API --------------------------------------------------

    def set_user_info(self, info: dict):
        with self._lock:
            self._user_info = info

    def set_auth_status(self, status: str):
        with self._lock:
            self._auth_status = status

    def set_last_scan(self, info: str):
        with self._lock:
            self._last_scan_info = info
        self._refresh()

    def set_engine(self, engine: str, interval: int):
        with self._lock:
            self._engine = engine
            self._interval = interval

    def set_countdown(self, seconds: int):
        with self._lock:
            self._countdown = seconds
        self._refresh()

    def increment_cycle(self):
        with self._lock:
            self._cycle_count += 1

    def update_jadwal(self, actions: list, skips: list) -> bool:
        """Rebuild tabel jadwal dari actions (biru) dan skips.
        Return True jika ada perubahan status dibanding scan sebelumnya."""
        with self._lock:
            old_states = {mk.nama: mk.status for mk in self._jadwal}
            jadwal = []
            # Skips dulu (sudah absen / belum buka / dll.)
            for color, sig, reason in (skips or []):
                parts = sig.split("|", 1)
                nama = parts[-1].strip() if len(parts) > 1 else sig
                mk = MataKuliah(
                    nama=nama[:50],
                    jam="",
                    status=color,
                    detail=reason,
                )
                jadwal.append(mk)
            # Actions (biru / siap klik)
            for a in (actions or []):
                mk = MataKuliah(
                    nama=a.get("nama_mk", a.get("sig", "?"))[:50],
                    jam="",
                    status="blue",
                    detail="siap absen",
                )
                jadwal.append(mk)

            changed = False
            for mk in jadwal:
                if mk.nama in old_states and old_states[mk.nama] != mk.status:
                    changed = True
            if len(old_states) != len(jadwal) and len(old_states) > 0:
                changed = True

            self._jadwal = jadwal
        self._refresh()
        return changed

    def mark_result(self, sig: str, success: bool):
        """Update status matkul setelah diklik."""
        with self._lock:
            target = sig.split("|")[0].strip()
            for mk in self._jadwal:
                if target in mk.nama:
                    mk.status = "clicked" if success else "failed"
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

        # screen=True mengaktifkan Alternate Screen Buffer (seperti vim, nano, htop, btop)
        # Layar bersih tanpa riwayat shell di atasnya, dan tidak bisa di-scroll keluar
        self._live = Live(
            self._build_layout(),
            console=self._console,
            refresh_per_second=2,
            screen=True,
        )
        self._live.start()

    def stop(self):
        """Hentikan live dashboard."""
        if hasattr(self, "_live") and self._live:
            self._live.stop()
            self._live = None

    # -- internal ----------------------------------------------------

    def _refresh(self):
        if self._plain or self._live is None:
            return
        try:
            self._live.update(self._build_layout())
        except Exception:
            pass  # Jangan crash karena render error

    def _build_banner(self) -> Group:
        """Render banner ASCII art di dalam alternate screen buffer."""
        term_height = self._console.size.height if hasattr(self, "_console") else 24
        if term_height >= 22:
            return Group(
                Align.center(Text(ASCII_BANNER.strip("\n"), style="bold cyan")),
                Align.center(Text(SUBTITLE, style="dim white")),
                Text(""),
            )
        else:
            return Group(
                Align.center(Text(">>> POLBAN AUTO ABSEN <<<", style="bold cyan")),
                Align.center(Text(SUBTITLE, style="dim white")),
                Text(""),
            )

    def _build_layout(self) -> Panel:
        """Render full dashboard sebagai satu Panel."""
        parts = []

        # -- ASCII Art Header --
        parts.append(self._build_banner())

        # -- Identity + status bar ---
        parts.append(self._build_status_bar())
        parts.append(Text(""))

        # -- Jadwal table ---
        parts.append(self._build_jadwal_panel())
        parts.append(Text(""))

        # -- Activity log ---
        parts.append(self._build_log_panel())

        outer = Panel(
            Group(*parts),
            title="[bold]POLBAN AUTO ABSEN[/bold]",
            subtitle=f"[dim]v2.0 linux | siklus #{self._cycle_count} | Ctrl+C untuk keluar[/dim]",
            border_style="bright_blue",
            padding=(1, 2),
            expand=True,
        )
        return outer

    def _build_status_bar(self) -> Panel:
        """Panel identitas + status."""
        info = self._user_info
        nama = info.get("nama", "") or "-"
        nim = info.get("nim", "") or "-"
        jurusan = info.get("jurusan", "") or ""

        auth = self._auth_status
        auth_style = "green" if "OK" in auth or "Authenticated" in auth else "red"

        countdown_m = self._countdown // 60
        countdown_s = self._countdown % 60
        countdown_str = f"{countdown_m:02d}:{countdown_s:02d}"

        tgl = datetime.now().strftime("%A, %d %B %Y")

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
        lines.append("  Hasil Scan : ", style="dim")
        lines.append(f"{self._last_scan_info}\n")
        lines.append("  Engine     : ", style="dim")
        lines.append(f"{self._engine}   ")
        lines.append("Interval : ", style="dim")
        lines.append(f"{self._interval}s   ")
        lines.append("Next scan : ", style="dim")
        lines.append(countdown_str, style="bold cyan")

        return Panel(lines, title="[bold]Identitas[/bold]", border_style="dim")

    def _build_jadwal_panel(self) -> Panel:
        """Tabel jadwal matkul hari ini."""
        table = Table(
            show_header=True,
            header_style="bold",
            expand=True,
            show_lines=False,
            pad_edge=True,
        )
        table.add_column("No", style="dim", width=4, justify="right")
        table.add_column("Mata Kuliah", ratio=3)
        table.add_column("Status", ratio=1, justify="center")
        table.add_column("Keterangan", ratio=2, style="dim")

        if not self._jadwal:
            table.add_row("", "[dim]Belum ada data jadwal[/dim]", "", "")
        else:
            for i, mk in enumerate(self._jadwal, 1):
                style = STATUS_STYLES.get(mk.status, "")
                label = STATUS_LABELS.get(mk.status, mk.status.upper())
                table.add_row(
                    str(i),
                    mk.nama,
                    Text(label, style=style),
                    mk.detail,
                )

        return Panel(
            table,
            title="[bold]Jadwal Hari Ini[/bold]",
            border_style="dim",
        )

    def _build_log_panel(self) -> Panel:
        """Ring buffer activity log."""
        if not self._log:
            content = Text("  Belum ada aktivitas.", style="dim")
        else:
            content = Text()
            for entry in self._log:
                lvl_style = LEVEL_STYLES.get(entry.level, "")
                tag = LEVEL_TAGS.get(entry.level, "[--]")
                content.append(f"  {entry.timestamp}  ", style="dim")
                content.append(f"{tag} ", style=lvl_style)
                content.append(f"[{entry.code}] ", style="bold")
                content.append(f"{entry.message}\n")

        return Panel(
            content,
            title=f"[bold]Log Aktivitas ({len(self._log)} terakhir)[/bold]",
            border_style="dim",
        )


# ---------------------------------------------------------------
# Plain-text fallback (no rich)
# ---------------------------------------------------------------
class PlainDashboard(Dashboard):
    """Fallback ketika rich tidak tersedia atau --plain dipakai."""

    def __init__(self):
        super().__init__(plain=True)

    def start(self):
        print_ascii_banner()
        info = self._user_info
        print(f"  Nama    : {info.get('nama', '-')}")
        print(f"  NIM     : {info.get('nim', '-')}")
        if info.get("jurusan"):
            print(f"  Jurusan : {info['jurusan']}")
        print(f"  Status  : {self._auth_status}")
        print(f"  Engine  : {self._engine}  Interval : {self._interval}s")
        print("-" * 56)

    def update_jadwal(self, actions, skips):
        """Pada plain mode, tidak perlu rebuild tabel — log saja sudah cukup."""
        return super().update_jadwal(actions, skips)

    def set_countdown(self, seconds):
        # Plain mode: tidak render countdown
        with self._lock:
            self._countdown = seconds


def create_dashboard(plain: bool = False) -> Dashboard:
    """Factory: buat Dashboard yang tepat berdasar kemampuan terminal."""
    if plain or not HAS_RICH:
        return PlainDashboard()
    # Cek apakah stdout adalah terminal interaktif
    import sys
    if not sys.stdout.isatty():
        return PlainDashboard()
    return Dashboard()
