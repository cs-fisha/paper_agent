"""Refresh local arXiv metadata snapshot from Kaggle and notify via Feishu.

- Downloads Cornell-University/arxiv via the kaggle CLI (must be installed and
  authenticated; uses ~/.kaggle/access_token or kaggle.json).
- Replaces data/arxiv/arxiv-metadata-oai-snapshot.json atomically: download to
  a temp dir, swap, then delete the previous file only after the new one passes
  a basic sanity check.
- Sends a Feishu text message on success AND failure, so silent failure can't
  hide. Webhook URL is read from FEISHU_WEBHOOK_URL (looks in .env automatically
  if python-dotenv is installed).
- A file lock guards against overlapping runs (cron + manual).

Designed to be invoked by cron without any args:

    /path/to/python /path/to/paper_agent/tools/refresh_arxiv_snapshot.py
"""

from __future__ import annotations

import errno
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):  # type: ignore
        return False

import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "arxiv"
TARGET = DATA_DIR / "arxiv-metadata-oai-snapshot.json"
TMP_DIR = DATA_DIR / ".tmp_refresh"
LOCK_FILE = DATA_DIR / ".refresh.lock"
LOG_FILE = PROJECT_ROOT / "logs" / "refresh_arxiv_snapshot.log"

KAGGLE_DATASET = "Cornell-University/arxiv"
# Kaggle ships a JSON snapshot whose name is stable across releases.
KAGGLE_INNER_NAME = "arxiv-metadata-oai-snapshot.json"

# Used for the Feishu message subject + lock file content.
HOST = socket.gethostname()


def setup_logging() -> logging.Logger:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("refresh_arxiv_snapshot")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(sh)
    return logger


def send_feishu(text: str, logger: logging.Logger) -> None:
    """Best-effort Feishu notification — failure here must not raise."""

    webhook = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    if not webhook:
        logger.warning("FEISHU_WEBHOOK_URL not set; skipping notification")
        return

    payload = json.dumps(
        {"msg_type": "text", "content": {"text": text}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        logger.info(f"Feishu notify HTTP {resp.status}: {body[:200]}")
    except Exception as exc:  # pragma: no cover
        logger.error(f"Feishu notify failed: {exc}")


def acquire_lock(logger: logging.Logger) -> int:
    """Acquire an exclusive lock file or exit non-zero if held."""

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            try:
                content = LOCK_FILE.read_text(encoding="utf-8")
            except Exception:
                content = "<unreadable>"
            logger.error(f"Lock held by: {content.strip()}")
            send_feishu(
                f"⚠️ arXiv 元数据刷新被锁阻止\n"
                f"主机：{HOST}\n"
                f"已有进程持有：{content.strip()}\n"
                f"路径：{LOCK_FILE}",
                logger,
            )
            sys.exit(2)
        raise
    os.write(fd, f"pid={os.getpid()} host={HOST} start={datetime.now().isoformat()}\n".encode())
    return fd


def release_lock(fd: int) -> None:
    try:
        os.close(fd)
    finally:
        try:
            LOCK_FILE.unlink()
        except FileNotFoundError:
            pass


def human_gb(num_bytes: int) -> str:
    return f"{num_bytes / 1e9:.2f} GB"


def file_stats(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    st = path.stat()
    return {
        "size": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }


def first_line_valid_json(path: Path) -> bool:
    """Cheap sanity check: snapshot is JSONL; first non-empty line must parse."""

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                return False
            # Snapshot records always carry an 'id' field.
            return isinstance(obj, dict) and "id" in obj
    return False


def kaggle_download(logger: logging.Logger) -> Path:
    """Download the Kaggle dataset zip into TMP_DIR and return its path."""

    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True)

    kaggle_bin = os.getenv("KAGGLE_BIN", "").strip() or shutil.which("kaggle") or "kaggle"

    cmd = [
        kaggle_bin,
        "datasets",
        "download",
        "-d",
        KAGGLE_DATASET,
        "-p",
        str(TMP_DIR),
    ]
    logger.info(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60 * 60,  # 1h hard cap
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"kaggle download failed (exit={proc.returncode})\n"
            f"stdout: {proc.stdout[-1000:]}\n"
            f"stderr: {proc.stderr[-1000:]}"
        )
    logger.info(f"kaggle stdout tail: {proc.stdout[-300:]}")

    zips = list(TMP_DIR.glob("*.zip"))
    if not zips:
        raise RuntimeError(f"No .zip file produced in {TMP_DIR}")
    if len(zips) > 1:
        logger.warning(f"Multiple zips found, using newest: {zips}")
        zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0]


def extract_snapshot(zip_path: Path, logger: logging.Logger) -> Path:
    """Extract the JSON snapshot from the downloaded zip."""

    logger.info(f"Extracting {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # Prefer the well-known canonical name; fall back to first .json.
        target_name = next(
            (n for n in names if n.endswith(KAGGLE_INNER_NAME)),
            next((n for n in names if n.lower().endswith(".json")), None),
        )
        if target_name is None:
            raise RuntimeError(f"No .json file found in zip: names={names[:10]}")
        zf.extract(target_name, path=TMP_DIR)
    extracted = TMP_DIR / target_name
    if not extracted.exists():
        raise RuntimeError(f"Extracted file missing: {extracted}")
    return extracted


def atomic_swap(new_file: Path, logger: logging.Logger) -> Optional[Path]:
    """Move new_file into place, keeping the old file as .bak until we verify."""

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    backup: Optional[Path] = None
    if TARGET.exists():
        backup = TARGET.with_suffix(TARGET.suffix + ".bak")
        if backup.exists():
            backup.unlink()
        logger.info(f"Backing up old snapshot to {backup}")
        os.replace(TARGET, backup)
    logger.info(f"Promoting {new_file} -> {TARGET}")
    os.replace(new_file, TARGET)
    return backup


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("refresh_arxiv_snapshot start")
    logger.info(f"target: {TARGET}")

    lock_fd = acquire_lock(logger)
    start = time.time()
    before = file_stats(TARGET)
    backup_path: Optional[Path] = None

    try:
        zip_path = kaggle_download(logger)
        zip_size = zip_path.stat().st_size
        logger.info(f"Downloaded zip: {human_gb(zip_size)}")

        new_file = extract_snapshot(zip_path, logger)
        new_size = new_file.stat().st_size
        logger.info(f"Extracted JSON: {human_gb(new_size)}")

        # Sanity check before swap — refuse obvious garbage so we keep the old
        # snapshot intact when Kaggle returns a partial file.
        if new_size < 1_000_000_000:  # under 1 GB is definitely wrong
            raise RuntimeError(
                f"Extracted snapshot suspiciously small ({human_gb(new_size)}); aborting."
            )
        if not first_line_valid_json(new_file):
            raise RuntimeError("Extracted snapshot's first line is not valid JSONL")

        backup_path = atomic_swap(new_file, logger)

        # Cleanup temp dir; keep .bak as the single rolling backup.
        shutil.rmtree(TMP_DIR, ignore_errors=True)

        after = file_stats(TARGET)
        elapsed = time.time() - start
        size_delta = (after["size"] - before["size"]) if before else after["size"]

        msg = (
            "✅ arXiv 元数据快照更新成功\n"
            f"主机：{HOST}\n"
            f"时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"旧 mtime：{before['mtime'] if before else '（无旧文件）'}\n"
            f"旧大小：{human_gb(before['size']) if before else '—'}\n"
            f"新大小：{human_gb(after['size'])} （Δ {size_delta/1e6:+.1f} MB）\n"
            f"下载 zip：{human_gb(zip_size)}\n"
            f"耗时：{elapsed/60:.1f} min\n"
            f"路径：{TARGET}"
        )
        logger.info(msg)
        send_feishu(msg, logger)
        return 0

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(f"Refresh failed: {exc}\n{tb}")

        # If the swap had already happened, restore from .bak so we never lose
        # the working snapshot to a partial upgrade.
        if backup_path and backup_path.exists() and not TARGET.exists():
            try:
                os.replace(backup_path, TARGET)
                logger.info("Restored snapshot from backup after failed swap")
            except Exception as restore_exc:
                logger.error(f"Backup restore failed: {restore_exc}")

        # Always clean temp dir; harmless if missing.
        shutil.rmtree(TMP_DIR, ignore_errors=True)

        after = file_stats(TARGET)
        msg = (
            "❌ arXiv 元数据快照更新失败\n"
            f"主机：{HOST}\n"
            f"时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"错误：{exc}\n"
            f"旧文件保留：{'是' if after else '否'}"
            + (f"（mtime={after['mtime']}）" if after else "")
            + f"\n日志：{LOG_FILE}"
        )
        send_feishu(msg, logger)
        return 1
    finally:
        release_lock(lock_fd)
        logger.info("refresh_arxiv_snapshot end")


if __name__ == "__main__":
    sys.exit(main())
