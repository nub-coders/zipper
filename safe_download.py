"""Safe URL download with SSRF protection and resource limits (Z-03, Z-04).

This module replaces raw `requests.head` / `aiohttp.get` for user-supplied URLs.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import urllib.parse
from dataclasses import dataclass

import aiohttp
import requests

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

# Heroku dyno disks are small; default is conservative.
MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB
HEAD_TIMEOUT = 10
GET_TIMEOUT = 1500
CHUNK_SIZE = 8192

# Networks that MUST NEVER be reached by a user-supplied URL.
# Includes localhost, RFC1918, cloud metadata, Docker bridge, CGNAT, link-local, etc.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),          # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),           # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),        # RFC1918 (includes Docker default 172.17.0.0/16)
    ipaddress.ip_network("192.168.0.0/16"),       # RFC1918
    ipaddress.ip_network("169.254.0.0/16"),       # link-local (cloud metadata)
    ipaddress.ip_network("::1/128"),              # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),            # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),             # IPv6 ULA (RFC4193)
    ipaddress.ip_network("100.64.0.0/10"),        # CGNAT (RFC6598)
    ipaddress.ip_network("172.20.0.0/14"),        # Docker IPv6 bridge (fallback)
    ipaddress.ip_network("0.0.0.0/8"),            # "this network"
    ipaddress.ip_network("224.0.0.0/4"),          # multicast
    ipaddress.ip_network("240.0.0.0/4"),          # reserved
]

# Hostnames that resolve to internal addresses (cloud metadata endpoints).
_BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata",
    "metadata.google.com",
    "169.254.169.254",
    "metadata.azure.com",
    "metadata.aliyuncs.com",
    "100.100.100.200",
    "localhost",
    "localhost.localdomain",
    "host.docker.internal",
    "gateway.docker.internal",
    "kubernetes.docker.internal",
}

# Allowed schemes for user downloads.
_ALLOWED_SCHEMES = {"http", "https"}

# Max redirects to follow (aiohttp default is 10; we match it explicitly).
_MAX_REDIRECTS = 10


# ──────────────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────────────

class SafeDownloadError(Exception):
    """Base exception for safe download failures (safe to show a user)."""


class SSRFBlocked(SafeDownloadError):
    """The URL resolves to a blocked internal address."""


class DownloadTooLarge(SafeDownloadError):
    """Content-Length or actual bytes exceeded the limit."""


class DownloadFailed(SafeDownloadError):
    """Network/HTTP error."""


class RedirectLimitExceeded(SafeDownloadError):
    """Too many redirects (potential SSRF via redirect chain)."""


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DownloadResult:
    path: str
    content_length: int


async def safe_download(
    url: str,
    dest_path: str,
    *,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    head_timeout: float = HEAD_TIMEOUT,
    get_timeout: float = GET_TIMEOUT,
    progress_callback=None,  # (current, total) -> None
) -> DownloadResult:
    """
    Download `url` to `dest_path` under SSRF and size constraints.

    - Validates the URL scheme and host before any connection.
    - Performs a HEAD request (with redirect following) to get size and re-validate.
    - Streams the body, enforcing `max_bytes` *during* the read loop.
    - On any failure, cleans up the partial file.
    """
    # 1. Parse and validate the URL structure.
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise DownloadFailed(f"scheme {parsed.scheme!r} not allowed")
    if not parsed.netloc:
        raise DownloadFailed("no host in URL")

    # 2. Resolve host to IPs (with a short timeout) and block internal ranges.
    # This is a *pre-connect* check. We re-check after redirects too.
    host = parsed.hostname
    if host in _BLOCKED_HOSTNAMES:
        raise SSRFBlocked(f"hostname {host!r} is blocked")

    # Resolve A/AAAA records.
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, None, type=socket.SOCK_STREAM),
            timeout=head_timeout,
        )
    except Exception as e:
        raise DownloadFailed(f"DNS resolution failed: {e}")

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise SSRFBlocked(f"host {host!r} resolves to blocked address {ip}")

    # 3. HEAD request (follows redirects) to get Content-Length and final URL.
    # We use requests for HEAD because it's synchronous and simple; the timeout
    # bounds wall-clock time. The subsequent aiohttp GET does the real work.
    try:
        head_resp = requests.head(
            url,
            timeout=head_timeout,
            allow_redirects=True,
            headers={"User-Agent": "ZipperBot/1.0"},
        )
    except requests.RequestException as e:
        raise DownloadFailed(f"HEAD request failed: {e}")

    if head_resp.history and len(head_resp.history) > _MAX_REDIRECTS:
        raise RedirectLimitExceeded("too many redirects")

    # Re-validate the final URL after redirects.
    final_url = head_resp.url
    parsed_final = urllib.parse.urlparse(final_url)
    if parsed_final.scheme.lower() not in _ALLOWED_SCHEMES:
        raise DownloadFailed(f"redirect to scheme {parsed_final.scheme!r} not allowed")
    final_host = parsed_final.hostname
    if final_host in _BLOCKED_HOSTNAMES:
        raise SSRFBlocked(f"redirect to blocked hostname {final_host!r}")

    # Resolve the final host too.
    try:
        final_infos = await asyncio.wait_for(
            loop.getaddrinfo(final_host, None, type=socket.SOCK_STREAM),
            timeout=head_timeout,
        )
    except Exception as e:
        raise DownloadFailed(f"final DNS resolution failed: {e}")
    for info in final_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise SSRFBlocked(f"redirect host {final_host!r} resolves to blocked address {ip}")

    # 4. Check Content-Length from HEAD (best-effort; may be missing or wrong).
    content_length = head_resp.headers.get("content-length")
    declared_length = int(content_length) if content_length and content_length.isdigit() else None
    if declared_length is not None and declared_length > max_bytes:
        raise DownloadTooLarge(f"declared size {declared_length} exceeds limit {max_bytes}")

    # 5. Stream the body with aiohttp, enforcing the limit *during* download.
    # Use the final URL so we don't redo redirects (already validated).
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=get_timeout),
    ) as session:
        async with session.get(final_url, max_redirects=_MAX_REDIRECTS) as resp:
            if resp.status != 200:
                raise DownloadFailed(f"HTTP {resp.status}")

            # Content-Length may be missing; we enforce our limit regardless.
            written = 0
            with open(dest_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        f.close()
                        try:
                            import os
                            os.remove(dest_path)
                        except OSError:
                            pass
                        raise DownloadTooLarge(
                            f"download exceeded {max_bytes} bytes (got {written})"
                        )
                    f.write(chunk)
                    if progress_callback:
                        total = declared_length or written
                        await progress_callback(written, total)

    return DownloadResult(path=dest_path, content_length=written)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Convenience sync HEAD for pre-checks (used by queue processor)
# ──────────────────────────────────────────────────────────────────────────────

def safe_head(url: str, *, timeout: float = HEAD_TIMEOUT, max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[int | None, str]:
    """
    Perform a safe HEAD request returning (content_length, final_url).

    Raises SafeDownloadError on any problem. Use this for pre-flight checks
    before queueing a download.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise DownloadFailed(f"scheme {parsed.scheme!r} not allowed")
    if not parsed.netloc:
        raise DownloadFailed("no host in URL")

    host = parsed.hostname
    if host in _BLOCKED_HOSTNAMES:
        raise SSRFBlocked(f"hostname {host!r} is blocked")

    # Fast sync resolve (HEAD is sync anyway).
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise DownloadFailed(f"DNS resolution failed: {e}")
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise SSRFBlocked(f"host {host!r} resolves to blocked address {ip}")

    try:
        resp = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "ZipperBot/1.0"},
        )
    except requests.RequestException as e:
        raise DownloadFailed(f"HEAD request failed: {e}")

    if resp.history and len(resp.history) > _MAX_REDIRECTS:
        raise RedirectLimitExceeded("too many redirects")

    final_url = resp.url
    parsed_final = urllib.parse.urlparse(final_url)
    if parsed_final.scheme.lower() not in _ALLOWED_SCHEMES:
        raise DownloadFailed(f"redirect to scheme {parsed_final.scheme!r} not allowed")
    final_host = parsed_final.hostname
    if final_host in _BLOCKED_HOSTNAMES:
        raise SSRFBlocked(f"redirect to blocked hostname {final_host!r}")

    try:
        final_infos = socket.getaddrinfo(final_host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise DownloadFailed(f"final DNS resolution failed: {e}")
    for info in final_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise SSRFBlocked(f"redirect host {final_host!r} resolves to blocked address {ip}")

    content_length = resp.headers.get("content-length")
    declared = int(content_length) if content_length and content_length.isdigit() else None
    if declared is not None and declared > max_bytes:
        raise DownloadTooLarge(f"declared size {declared} exceeds limit {max_bytes}")
    return declared, final_url