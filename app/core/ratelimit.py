"""Pembatas laju permintaan (NFR keamanan).

Jendela bergulir di memori per kunci. Cukup untuk satu proses/instance; bila
backend dijalankan multi-instance, pindah ke Redis dengan API yang sama.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import Request

from app.core.config import settings

_lock = threading.Lock()
_buckets: dict[str, list[float]] = {}


@dataclass(frozen=True)
class Quota:
    allowed: bool
    remaining: int
    limit: int
    retry_after: int


def consume(key: str, *, limit: int, window_seconds: int) -> Quota:
    """Catat satu permintaan untuk `key`; tolak bila sudah mencapai `limit`."""
    now = time.monotonic()
    window_start = now - window_seconds
    with _lock:
        hits = [t for t in _buckets.get(key, []) if t > window_start]
        if len(hits) >= limit:
            retry = int(window_seconds - (now - hits[0])) + 1
            _buckets[key] = hits
            return Quota(False, 0, limit, max(1, retry))
        hits.append(now)
        _buckets[key] = hits
        return Quota(True, limit - len(hits), limit, 0)


def purge() -> None:
    """Buang kunci yang sudah tidak aktif (dipanggil berkala/jika membengkak)."""
    cutoff = time.monotonic() - 24 * 3600
    with _lock:
        for key in [k for k, v in _buckets.items() if not v or v[-1] < cutoff]:
            _buckets.pop(key, None)


def reset() -> None:
    """Kosongkan seluruh hitungan. Hanya untuk uji dan alat bantu lokal."""
    with _lock:
        _buckets.clear()


def client_ip(request: Request) -> str:
    """IP pengirim. Hanya memakai `x-forwarded-for` bila TRUST_PROXY aktif.

    shortcut: di baliknya proxy, header itu palsu jika TRUST_PROXY=0, sehingga
    semua pengguna ikut tercampur. Upgrade: naikkan limit per IP atau pindahkan
    pencatatan kuota ke Redis saat deployment multi-instance.
    """
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"
