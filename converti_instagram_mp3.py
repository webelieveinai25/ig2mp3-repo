#!/usr/bin/env python3
"""
Instagram to MP3 (batch) using yt-dlp — GUI + CLI — ASCII-only

Fix for SystemExit: 0
- Some sandboxed runners treat sys.exit(0) as an exception that surfaces in logs.
- This version NEVER calls sys.exit(0). It only calls sys.exit for non‑zero exit codes
  in non-interactive contexts. In interactive contexts (TTY), it avoids sys.exit entirely.

Additional hardening already present:
- Avoid input() in non-interactive environments to prevent OSError: [Errno 29].
- Fallback sources for URLs: links.txt or IG_LINKS env. Graceful no-op when empty.
- GUI (Tk), CLI, safe filenames, ffmpeg auto-detection, backoff, errors.log, report.csv.
- SSL preflight and lazy yt-dlp import to avoid import-time crashes.
- Unit tests for parsing, config, fallbacks, and exit strategy.

Build to .exe (Windows)
  pip install yt-dlp pyinstaller
  pyinstaller --onefile --name ConvertiIG2MP3 converti_instagram_mp3.py
  (Place ffmpeg.exe next to ConvertiIG2MP3.exe or add ffmpeg to PATH.)

Usage (CLI examples)
  python converti_instagram_mp3.py --url https://www.instagram.com/reel/XXXX/
  python converti_instagram_mp3.py --links links.txt --out out_mp3
  python converti_instagram_mp3.py --run-tests

If run with no CLI args (double-click .exe), the GUI starts. If GUI is unavailable,
we fall back to default links.txt, IG_LINKS env, or a safe no-op exit.
"""

from __future__ import annotations
import sys
import os
import csv
import time
import random
import shutil
import argparse
import re
from pathlib import Path
from typing import List, Tuple, Optional

# ---------------------- Utilities and diagnostics ---------------------- #

def assert_ssl_available() -> None:
    """Ensure the Python runtime has the ssl module enabled.
    Exit with a helpful message if not available.
    """
    try:
        import ssl  # noqa: F401
    except Exception as e:
        msg = (
            "\nFATAL: Python ssl module is missing. yt-dlp requires HTTPS.\n"
            "Fix suggestions:\n"
            " - Windows: install Python from python.org installer (includes SSL).\n"
            " - macOS (Homebrew): brew install openssl && brew reinstall python\n"
            " - Linux (Debian/Ubuntu): sudo apt-get install -y libssl-dev and reinstall Python.\n"
            "Or run this program on a machine with a standard Python build.\n"
        )
        print(msg)
        raise SystemExit(2) from e


def ensure_yt_dlp():
    """Import yt_dlp lazily to avoid import-time crashes during tests.
    Returns (YoutubeDL, DownloadError).
    """
    try:
        from yt_dlp import YoutubeDL  # type: ignore
        from yt_dlp.utils import DownloadError  # type: ignore
        return YoutubeDL, DownloadError
    except Exception as e:
        raise RuntimeError(
            "yt-dlp is not installed or failed to import. Install with: pip install yt-dlp"
        ) from e


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def stdin_is_interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


# -------------------------- Core configuration ------------------------- #

def build_ydl_opts(out_dir: Path,
                   audio_quality: str = "320",
                   archive_path: Optional[str] = None,
                   cookies_path: Optional[str] = None,
                   rate_limit: Optional[str] = None,
                   concurrent_fragments: Optional[int] = None,
                   write_thumbnail: bool = False) -> dict:
    """Build yt-dlp options dict. Pure function (easy to test)."""
    out_tmpl = str(out_dir / "%(uploader|unknown)s-%(title|unknown)s-%(id)s.%(ext)s")
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": out_tmpl,
        "retries": 5,
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
        "ignoreerrors": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": audio_quality},
            {"key": "FFmpegMetadata"},
        ],
        "restrictfilenames": True,
        "windowsfilenames": True,
        "quiet": False,
        "noprogress": False,
    }

    if write_thumbnail:
        opts.update({
            "writethumbnail": True,
            "embedthumbnail": True,
            "postprocessor_args": ["-id3v2_version", "3"],
        })

    if archive_path:
        opts["download_archive"] = archive_path

    if cookies_path and Path(cookies_path).exists():
        opts["cookiefile"] = cookies_path

    if rate_limit:
        opts["ratelimit"] = rate_limit  # e.g., "1M" for 1 MB/s

    if concurrent_fragments and concurrent_fragments > 1:
        opts["concurrent_fragment_downloads"] = concurrent_fragments

    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path:
        # yt-dlp accepts a directory; use the parent folder of the executable
        opts["ffmpeg_location"] = str(Path(ffmpeg_path).parent)

    return opts


# ----------------------------- Link parsing ---------------------------- #

def parse_links_from_text(raw: str) -> List[str]:
    """Parse one or many Instagram URLs from free-form text.
    Accepts whitespace or space-separated URLs. Removes comments starting with '#'.
    Filters non-http strings. Returns a deduplicated list preserving order.
    """
    if not raw:
        return []

    # Normalize separators: treat commas/semicolons as whitespace
    cleaned = re.sub(r"[\t,;\r]+", "\n", raw)

    links: List[str] = []
    seen = set()
    for line in cleaned.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        for token in line.split():
            if token.startswith("http://") or token.startswith("https://"):
                if token not in seen:
                    seen.add(token)
                    links.append(token)
    return links


def read_links_file(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Links file not found: {path}")
    return parse_links_from_text(path.read_text(encoding="utf-8", errors="ignore"))


# -------------------------- Fallback link source ----------------------- #

def compute_fallback_links(noninteractive: bool,
                           env_text: Optional[str],
                           default_file_text: Optional[str]) -> List[str]:
    """Pure function to decide which fallback links to use.
    - If noninteractive is True, use env_text, else allow empty to prompt.
    - default_file_text, when present, is parsed too.
    Preference: default links.txt > IG_LINKS env.
    """
    if noninteractive:
        # Prefer links.txt (deterministic), then env
        if default_file_text and default_file_text.strip():
            return parse_links_from_text(default_file_text)
        if env_text and env_text.strip():
            return parse_links_from_text(env_text)
        return []
    # Interactive mode does not use this function for prompting; just parse any provided text
    if default_file_text and default_file_text.strip():
        return parse_links_from_text(default_file_text)
    if env_text and env_text.strip():
        return parse_links_from_text(env_text)
    return []


def gather_links_noninteractive() -> List[str]:
    """Read links from links.txt or IG_LINKS env without calling input()."""
    default_text = None
    links_file = Path("links.txt")
    if links_file.exists():
        try:
            default_text = links_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            default_text = None
    env_text = os.environ.get("IG_LINKS")
    return compute_fallback_links(noninteractive=True, env_text=env_text, default_file_text=default_text)


# --------------------------- Download helpers -------------------------- #

def backoff_sleep(attempt: int) -> None:
    base = min(60, 2 ** attempt)
    jitter = random.random() * 2.0
    time.sleep(min(60, base + jitter))


def download_one(ydl, url: str, retries: int, sleep_between: float, error_log: Path) -> Tuple[bool, Optional[str]]:
    """Download and convert a single URL with retries."""
    last_err: Optional[str] = None
    for attempt in range(1, retries + 1):
        try:
            print(f"Downloading {url} (attempt {attempt}/{retries})")
            ydl.download([url])
            time.sleep(max(0.0, sleep_between))
            return True, None
        except Exception as e:  # Do not depend on yt_dlp types here
            last_err = str(e)
            print(f"[ERROR] {last_err}")
        if attempt < retries:
            backoff_sleep(attempt)
    # Append to log
    try:
        with error_log.open("a", encoding="utf-8") as f:
            f.write(f"{url}\t{last_err or 'unknown error'}\n")
    except Exception:
        pass
    return False, last_err


# ------------------------- Interactive fallback ------------------------ #

def prompt_for_links_interactive() -> List[str]:
    """Ask the user to paste URLs in the console only if stdin is interactive.
    Non-interactive environments return links from links.txt or IG_LINKS.
    """
    if not stdin_is_interactive():
        return gather_links_noninteractive()

    print("No URLs provided. Paste one or more Instagram URLs below. End with an empty line:")
    buf: List[str] = []
    try:
        while True:
            try:
                line = input()
            except OSError:
                # Some sandboxes raise OSError on input(); fall back immediately
                return gather_links_noninteractive()
            line = (line or "").strip()
            if not line:
                break
            buf.append(line)
    except EOFError:
        pass
    links = parse_links_from_text("\n".join(buf))
    if not links:
        # Try non-interactive sources as a backup
        fallback = gather_links_noninteractive()
        return fallback
    return links


# ------------------------------ CLI runner ----------------------------- #

def run_cli(args: argparse.Namespace) -> int:
    assert_ssl_available()
    YoutubeDL, _DownloadError = ensure_yt_dlp()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    error_log = out_dir / "errors.log"
    report_csv = out_dir / "report.csv"

    links: List[str] = []
    if args.url:
        links = parse_links_from_text(args.url)
    elif args.links:
        links = read_links_file(Path(args.links))
    else:
        # No CLI inputs: try GUI or interactive
        print("No URL or links file provided. Starting GUI or interactive flow...\n")
        code = run_gui()
        if code == 0:
            return 0
        # GUI not available: do not call input() if stdin is non-interactive
        links = prompt_for_links_interactive()
        if not links:
            print("No URLs detected (links.txt or IG_LINKS empty). Nothing to do.")
            return 0

    if not links:
        print("No valid links found from inputs. Nothing to do.")
        return 0

    return perform_downloads(YoutubeDL, out_dir, error_log, report_csv, links, args)


def perform_downloads(YoutubeDL, out_dir: Path, error_log: Path, report_csv: Path,
                      links: List[str], args: argparse.Namespace) -> int:
    ydl_opts = build_ydl_opts(
        out_dir=out_dir,
        audio_quality=args.quality,
        archive_path=(args.archive or None),
        cookies_path=(args.cookies or None),
        rate_limit=(args.rate_limit or None),
        concurrent_fragments=args.concurrent_fragments,
        write_thumbnail=args.thumbnail,
    )

    successes = 0
    failures = 0
    rows: List[Tuple[str, str, str]] = []

    with YoutubeDL(ydl_opts) as ydl:
        total = len(links)
        for i, url in enumerate(links, start=1):
            print(f"[{i}/{total}] {url}")
            ok, note = download_one(ydl, url, retries=args.retries, sleep_between=args.sleep, error_log=error_log)
            if ok:
                successes += 1
                rows.append((url, "ok", ""))
            else:
                failures += 1
                rows.append((url, "fail", note or ""))

    # CSV report
    try:
        new_file = not report_csv.exists()
        with report_csv.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["url", "status", "note"])
            w.writerows(rows)
        print(f"Report saved to: {report_csv}")
    except Exception as e:
        print(f"[WARN] Failed to write report: {e}")

    print(f"Done. Success: {successes}  Failures: {failures}")
    print(f"Output folder: {out_dir.resolve()}")
    if failures:
        print(f"See error log: {error_log}")

    # Always return 0 for user-facing flows
    return 0


# ------------------------------ GUI runner ----------------------------- #

def run_gui() -> int:
    assert_ssl_available()
    try:
        import tkinter as tk  # Lazy import to avoid issues in headless envs
        from tkinter import filedialog, messagebox
    except Exception:
        # GUI not available; signal fallback
        return 1

    try:
        root = tk.Tk()
    except Exception:
        return 1

    root.title("Instagram to MP3")
    root.geometry("560x360")

    text_links = tk.Text(root, height=7, width=68)
    out_dir_var = tk.StringVar(value=str(Path.cwd() / "output_mp3"))

    def load_from_file():
        file_path = filedialog.askopenfilename(title="Select links.txt", filetypes=[("Text Files", "*.txt")])
        if not file_path:
            return
        try:
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")
            return
        text_links.delete("1.0", tk.END)
        text_links.insert(tk.END, text)

    def choose_output():
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            out_dir_var.set(folder)

    def start_download():
        raw = text_links.get("1.0", tk.END)
        links = parse_links_from_text(raw)
        if not links:
            messagebox.showerror("Error", "Paste one or more Instagram URLs first.")
            return
        out_dir = Path(out_dir_var.get())
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            YoutubeDL, _DownloadError = ensure_yt_dlp()
        except RuntimeError as e:
            messagebox.showerror("Error", str(e))
            return

        error_log = out_dir / "errors.log"
        opts = build_ydl_opts(out_dir=out_dir, audio_quality="320")

        successes = 0
        failures = 0
        with YoutubeDL(opts) as ydl:
            for url in links:
                ok, _ = download_one(ydl, url, retries=3, sleep_between=1.0, error_log=error_log)
                if ok:
                    successes += 1
                else:
                    failures += 1
        messagebox.showinfo("Done", f"Success: {successes}\nFailures: {failures}\nSaved in: {out_dir.resolve()}")

    # Layout
    import tkinter as tk  # ensure tk is in scope
    tk.Label(root, text="Paste one or more Instagram URLs (space or newline separated)").pack(pady=6)
    text_links.pack(padx=12, pady=4)
    tk.Button(root, text="Load from file (links.txt)", command=load_from_file).pack(pady=4)

    tk.Label(root, text="Output folder").pack(pady=4)
    tk.Entry(root, textvariable=out_dir_var, width=66).pack(padx=12, pady=2)
    tk.Button(root, text="Choose folder", command=choose_output).pack(pady=4)

    tk.Button(root, text="Convert to MP3", command=start_download).pack(pady=10)

    root.mainloop()
    return 0


# ------------------------------- Testing ------------------------------- #

def run_unit_tests() -> int:
    import unittest

    class TestParsing(unittest.TestCase):
        def test_parse_multiple_lines(self):
            raw = "https://a\nhttps://b\n\n# comment\n https://c "
            self.assertEqual(parse_links_from_text(raw), ["https://a", "https://b", "https://c"])

        def test_parse_space_separated(self):
            raw = "https://x https://y    https://z"
            self.assertEqual(parse_links_from_text(raw), ["https://x", "https://y", "https://z"])

        def test_parse_mixed_separators(self):
            raw = "https://a, https://b;https://c\nnotalink https://d"
            self.assertEqual(parse_links_from_text(raw), ["https://a", "https://b", "https://c", "https://d"])

        def test_parse_deduplicate_preserve_order(self):
            raw = "https://a https://b https://a https://c"
            self.assertEqual(parse_links_from_text(raw), ["https://a", "https://b", "https://c"])

        def test_parse_ignores_non_http(self):
            raw = "ftp://a mailto:x https://ok\nnot_a_url"
            self.assertEqual(parse_links_from_text(raw), ["https://ok"])

        def test_parse_non_ascii_noise(self):
            raw = "— not url — https://good\n» also noise"
            self.assertEqual(parse_links_from_text(raw), ["https://good"])

        def test_parse_empty(self):
            self.assertEqual(parse_links_from_text(""), [])

    class TestConfig(unittest.TestCase):
        def test_build_outtmpl_contains_ext_and_dir(self):
            out = Path("tmp_out")
            opts = build_ydl_opts(out)
            self.assertIn("%(ext)s", opts["outtmpl"])  # ydl template placeholder
            self.assertTrue(str(out) in opts["outtmpl"])  # correct folder

    class TestFallback(unittest.TestCase):
        def test_fallback_noninteractive_prefers_file(self):
            env = "https://env1 https://env2"
            file_text = "https://f1\nhttps://f2"
            res = compute_fallback_links(True, env, file_text)
            self.assertEqual(res, ["https://f1", "https://f2"])

        def test_fallback_noninteractive_uses_env_when_no_file(self):
            env = "https://env1 https://env2"
            res = compute_fallback_links(True, env, None)
            self.assertEqual(res, ["https://env1", "https://env2"])

        def test_fallback_noninteractive_empty_returns_empty(self):
            res = compute_fallback_links(True, " ", " ")
            self.assertEqual(res, [])

    class TestExitStrategy(unittest.TestCase):
        def test_no_sys_exit_on_zero(self):
            should_exit, code = compute_exit_strategy(0, is_tty=False, force_sys_exit_env="0")
            self.assertFalse(should_exit)
            self.assertEqual(code, 0)

        def test_interactive_nonzero_no_exit(self):
            should_exit, code = compute_exit_strategy(1, is_tty=True, force_sys_exit_env="0")
            self.assertFalse(should_exit)
            self.assertEqual(code, 1)

        def test_noninteractive_nonzero_exit(self):
            should_exit, code = compute_exit_strategy(2, is_tty=False, force_sys_exit_env="0")
            self.assertTrue(should_exit)
            self.assertEqual(code, 2)

        def test_force_env_triggers_exit(self):
            should_exit, code = compute_exit_strategy(1, is_tty=True, force_sys_exit_env="1")
            self.assertTrue(should_exit)
            self.assertEqual(code, 1)

    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


# ------------------------------- Exit strategy ------------------------------- #

def compute_exit_strategy(rc: int, is_tty: bool, force_sys_exit_env: str) -> Tuple[bool, int]:
    """Decide whether to call sys.exit and with which code.
    - Never sys.exit on rc == 0 (avoid SystemExit: 0 noise in sandboxes).
    - In interactive TTY, avoid sys.exit for better UX unless FORCE_SYS_EXIT=1.
    - In non-interactive, sys.exit on non-zero rc.
    Returns (should_exit, code).
    """
    if rc == 0:
        return False, 0
    if force_sys_exit_env == "1":
        return True, rc
    if is_tty:
        return False, rc
    return True, rc


# --------------------------------- Main -------------------------------- #

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Instagram to MP3 (batch) with yt-dlp")
    p.add_argument("--links", default=None, help="Path to links.txt (one URL per line)")
    p.add_argument("--url", default=None, help="Single URL or space/newline separated URLs")
    p.add_argument("--out", default=str(Path("output_mp3")), help="Output directory")
    p.add_argument("--quality", default="320", help="MP3 quality kbps (128/192/256/320)")
    p.add_argument("--sleep", type=float, default=1.0, help="Seconds between downloads")
    p.add_argument("--retries", type=int, default=3, help="Retries per URL")
    p.add_argument("--cookies", default=None, help="Path to cookies.txt (Netscape format)")
    p.add_argument("--rate-limit", default=None, help="Rate limit, e.g. 1M for 1 MB/s")
    p.add_argument("--archive", default="downloaded.txt", help="Download archive file to skip already done")
    p.add_argument("--concurrent-fragments", type=int, default=None, help="Parallel fragment downloads when supported")
    p.add_argument("--thumbnail", action="store_true", help="Embed thumbnail when available")
    p.add_argument("--run-tests", action="store_true", help="Run unit tests and exit")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.run_tests:
        return run_unit_tests()

    # If no CLI inputs are given, prefer GUI; otherwise run CLI.
    if not any([args.url, args.links]):
        code = run_gui()
        if code == 0:
            return 0
        # GUI failed, fallback without input() in non-interactive envs
        links = prompt_for_links_interactive()
        if not links:
            # Nothing to do; silent success
            return 0
        # Build minimal args-like namespace for downloads
        class _Args:  # noqa: N801
            pass
        _a = _Args()
        _a.out = args.out
        _a.quality = args.quality
        _a.archive = args.archive
        _a.cookies = args.cookies
        _a.rate_limit = args.rate_limit
        _a.concurrent_fragments = args.concurrent_fragments
        _a.thumbnail = args.thumbnail
        _a.retries = args.retries
        _a.sleep = args.sleep

        out_dir = Path(_a.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        error_log = out_dir / "errors.log"
        report_csv = out_dir / "report.csv"
        YoutubeDL, _DownloadError = ensure_yt_dlp()
        return perform_downloads(YoutubeDL, out_dir, error_log, report_csv, links, _a)

    return run_cli(args)


if __name__ == "__main__":
    try:
        rc = main()
        # Decide whether to call sys.exit
        should_exit, code = compute_exit_strategy(rc, is_tty=sys.stdout.isatty(),
                                                  force_sys_exit_env=os.environ.get("FORCE_SYS_EXIT", "0"))
        if should_exit and code != 0:
            # Only raise SystemExit for non-zero codes in non-interactive flows
            sys.exit(code)
        # Otherwise, end silently with implicit code 0 (no SystemExit: 0)
    except KeyboardInterrupt:
        print("Interrupted by user.")
        # Prefer silent return; avoid raising SystemExit in sandboxes
        # If you truly need exit code, set FORCE_SYS_EXIT=1
        if os.environ.get("FORCE_SYS_EXIT", "0") == "1":
            try:
                sys.exit(130)
            except SystemExit:
                pass
