"""Safe URL download with comprehensive SSRF protection and resource limits."""

from __future__ import annotations

import asyncio
import inspect
import ipaddress
import socket
import time
import urllib.parse
from dataclasses import dataclass

import aiohttp
from aiohttp.resolver import DefaultResolver

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB
HEAD_TIMEOUT = 10
GET_TIMEOUT = 1500
CHUNK_SIZE = 8192

# A 2 GiB transfer is ~262k chunks; reporting every chunk would flood whatever
# UI sits behind the callback. Report on whichever of these fires first.
PROGRESS_INTERVAL_BYTES = 1024 * 1024
PROGRESS_INTERVAL_SECONDS = 1.0

# Networks that MUST NEVER be reached by a user-supplied URL.
# Includes localhost, RFC1918, cloud metadata, Docker bridge, CGNAT, link-local, IPv4-mapped IPv6, etc.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),          # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),           # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),        # RFC1918 (includes Docker default 172.17.0.0/16)
    ipaddress.ip_network("192.168.0.0/16"),       # RFC1918
    ipaddress.ip_network("169.254.0.0/16"),       # link-local (cloud metadata)
    ipaddress.ip_network("::1/128"),              # IPv6 loopback
    ipaddress.ip_network("::/128"),               # IPv6 unspecified
    ipaddress.ip_network("fe80::/10"),            # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),             # IPv6 ULA (RFC4193)
    ipaddress.ip_network("100.64.0.0/10"),        # CGNAT (RFC6598)
    ipaddress.ip_network("172.20.0.0/14"),        # Docker IPv6 bridge
    ipaddress.ip_network("0.0.0.0/8"),            # "this network"
    ipaddress.ip_network("224.0.0.0/4"),          # multicast
    ipaddress.ip_network("240.0.0.0/4"),          # reserved
    ipaddress.ip_network("::ffff:0:0/96"),        # IPv4-mapped IPv6
    ipaddress.ip_network("198.18.0.0/15"),        # benchmark testing
    ipaddress.ip_network("192.0.2.0/24"),         # documentation (TEST-NET-1)
    ipaddress.ip_network("198.51.100.0/24"),      # documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),       # documentation (TEST-NET-3)
    ipaddress.ip_network("2001:db8::/32"),        # IPv6 documentation
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
    "instance-data",
}

# Allowed schemes for user downloads.
_ALLOWED_SCHEMES = {"http", "https"}

# Explicit ports a user-supplied URL may target. Without this, a routable IP is
# enough to reach internal services that merely happen to be listening on a
# public interface (Redis 6379, SMTP 25, Elasticsearch 9200, …).
_ALLOWED_PORTS = {80, 443}

# Max redirects to follow
_MAX_REDIRECTS = 10

_REDIRECT_STATUSES = (301, 302, 303, 307, 308)
_REQUEST_HEADERS = {"User-Agent": "ZipperBot/1.0"}


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


def _is_blocked_hostname(host: str) -> bool:
    h = host.lower().strip("[]")
    if h in _BLOCKED_HOSTNAMES:
        return True
    if h.endswith(".local") or h.endswith(".internal") or h.endswith(".localhost"):
        return True
    return False


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    for net in _BLOCKED_NETWORKS:
        try:
            if ip in net:
                return True
        except TypeError:
            continue
    return False


def _is_blocked_address(ip_str: str) -> bool:
    """Blocklist check for a raw address string; unparseable input is refused."""
    try:
        ip = ipaddress.ip_address(ip_str.split("%")[0])
    except ValueError:
        return True
    return _is_blocked_ip(ip)


class SSRFGuardedResolver(DefaultResolver):
    """Resolver that re-checks every address in the answer aiohttp is about to use.

    Validating the URL up front is not sufficient on its own: the pre-flight
    check and the connection each performed their own DNS lookup, so an
    attacker-controlled nameserver answering with a short TTL could return a
    public address for the check and an internal one for the connect (DNS
    rebinding). aiohttp connects only to addresses this resolver hands back, so
    filtering here closes that window. The original hostname is preserved in the
    result, which keeps TLS SNI and the Host header intact.
    """

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET):
        if _is_blocked_hostname(host):
            raise SSRFBlocked(f"hostname {host!r} is blocked")

        infos = await super().resolve(host, port, family)
        allowed = [info for info in infos if not _is_blocked_address(info["host"])]
        if not allowed:
            raise SSRFBlocked(f"host {host!r} resolves only to blocked addresses")
        return allowed


def _guarded_session(timeout: aiohttp.ClientTimeout) -> aiohttp.ClientSession:
    """Build a session whose every connection attempt passes the SSRF blocklist."""
    connector = aiohttp.TCPConnector(resolver=SSRFGuardedResolver(), use_dns_cache=False)
    return aiohttp.ClientSession(timeout=timeout, connector=connector)


async def _validate_url_target(url: str, timeout: float = HEAD_TIMEOUT) -> urllib.parse.ParseResult:
    """Pre-flight validation of scheme, port, host, and resolved addresses.

    This rejects hostile URLs early so the user gets a clear error, but it is not
    the last line of defence — ``SSRFGuardedResolver`` re-checks the addresses at
    connect time.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise DownloadFailed(f"scheme {parsed.scheme!r} not allowed")
    if not parsed.netloc or not parsed.hostname:
        raise DownloadFailed("no host in URL")

    try:
        port = parsed.port
    except ValueError:
        raise DownloadFailed("invalid port in URL")
    if port is not None and port not in _ALLOWED_PORTS:
        raise SSRFBlocked(f"port {port} not allowed")

    host = parsed.hostname.strip("[]")
    if _is_blocked_hostname(host):
        raise SSRFBlocked(f"hostname {host!r} is blocked")

    # If the host is already an IP literal
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise SSRFBlocked(f"host {host!r} is a blocked IP address")
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, None, type=socket.SOCK_STREAM),
            timeout=timeout,
        )
    except Exception as e:
        raise DownloadFailed(f"DNS resolution failed for {host!r}: {e}")

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise SSRFBlocked(f"host {host!r} resolves to blocked address {ip}")

    return parsed


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DownloadResult:
    path: str
    content_length: int


async def _emit_progress(progress_callback, current: int, total: int) -> None:
    """Invoke a sync or async ``(current, total)`` progress callback.

    The callback is awaited inline rather than spawned as a task so that an
    exception it raises (e.g. pyrogram's ``StopTransmission`` used to signal a
    user cancellation) propagates into the download loop and aborts the transfer.
    """
    result = progress_callback(current, total)
    if inspect.isawaitable(result):
        await result


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
    Download `url` to `dest_path` under strict SSRF, redirect, and size constraints.

    - Validates scheme, port, host, and DNS on every redirect hop, and re-checks
      the resolved addresses at connect time via ``SSRFGuardedResolver``.
    - Uses allow_redirects=False so no unverified redirects can occur.
    - Streams the body, enforcing `max_bytes` during the read loop.
    - On any failure, cleans up the partial file.
    """
    current_url = url
    redirect_count = 0
    client_timeout = aiohttp.ClientTimeout(total=get_timeout, connect=head_timeout)

    async with _guarded_session(client_timeout) as session:
        while redirect_count <= _MAX_REDIRECTS:
            await _validate_url_target(current_url, timeout=head_timeout)

            try:
                resp = await session.get(
                    current_url,
                    allow_redirects=False,
                    headers=_REQUEST_HEADERS,
                )
            except SSRFBlocked:
                raise
            except Exception as e:
                raise DownloadFailed(f"HTTP request failed: {e}")

            # Check for redirect status
            if resp.status in _REDIRECT_STATUSES:
                resp.close()
                redirect_count += 1
                if redirect_count > _MAX_REDIRECTS:
                    raise RedirectLimitExceeded("too many redirects")
                location = resp.headers.get("Location")
                if not location:
                    raise DownloadFailed("redirect without Location header")
                current_url = urllib.parse.urljoin(current_url, location)
                continue

            if resp.status != 200:
                resp.close()
                raise DownloadFailed(f"HTTP {resp.status}")

            # 200 OK -> Check Content-Length if present
            content_length_hdr = resp.headers.get("Content-Length")
            declared_length = int(content_length_hdr) if content_length_hdr and content_length_hdr.isdigit() else None
            if declared_length is not None and declared_length > max_bytes:
                resp.close()
                raise DownloadTooLarge(f"declared size {declared_length} exceeds limit {max_bytes}")

            # Stream body
            written = 0
            reported_bytes = 0
            reported_at = 0.0
            try:
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
                            raise DownloadTooLarge(f"download exceeded {max_bytes} bytes (got {written})")
                        f.write(chunk)
                        if progress_callback:
                            now = time.monotonic()
                            if (
                                written - reported_bytes >= PROGRESS_INTERVAL_BYTES
                                or now - reported_at >= PROGRESS_INTERVAL_SECONDS
                            ):
                                reported_bytes = written
                                reported_at = now
                                await _emit_progress(progress_callback, written, declared_length or written)
                if progress_callback and written != reported_bytes:
                    # Throttling can swallow the last chunks; emit the true final
                    # size so the caller never ends up stuck below 100%.
                    await _emit_progress(progress_callback, written, declared_length or written)
            except BaseException:
                # BaseException rather than Exception: a cancelled task raises
                # CancelledError, and a partial file left on disk would keep
                # counting against the user's storage quota.
                resp.close()
                try:
                    import os
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                except OSError:
                    pass
                raise
            finally:
                resp.close()

            return DownloadResult(path=dest_path, content_length=written)

    raise RedirectLimitExceeded("too many redirects")


async def safe_head(
    url: str,
    *,
    timeout: float = HEAD_TIMEOUT,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> tuple[int | None, str]:
    """
    Perform a safe HEAD pre-check with manual hop-by-hop redirect verification.

    Returns (content_length, final_url). Raises SafeDownloadError on any problem.
    Shares the SSRF-guarded connector with :func:`safe_download` so both paths
    enforce the same blocklist at connect time.
    """
    current_url = url
    redirect_count = 0
    client_timeout = aiohttp.ClientTimeout(total=timeout, connect=timeout)

    async with _guarded_session(client_timeout) as session:
        while redirect_count <= _MAX_REDIRECTS:
            await _validate_url_target(current_url, timeout=timeout)

            try:
                resp = await session.head(
                    current_url,
                    allow_redirects=False,
                    headers=_REQUEST_HEADERS,
                )
            except SSRFBlocked:
                raise
            except Exception as e:
                raise DownloadFailed(f"HEAD request failed: {e}")

            try:
                if resp.status in _REDIRECT_STATUSES:
                    redirect_count += 1
                    if redirect_count > _MAX_REDIRECTS:
                        raise RedirectLimitExceeded("too many redirects")
                    location = resp.headers.get("Location")
                    if not location:
                        raise DownloadFailed("redirect without Location header")
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue

                # Only a successful response describes the body. Servers that
                # answer 405/404 to HEAD still send a Content-Length for their
                # error page, which must not be mistaken for the file size.
                declared = None
                if resp.status in (200, 206):
                    content_length = resp.headers.get("Content-Length")
                    declared = int(content_length) if content_length and content_length.isdigit() else None

                if declared is not None and declared > max_bytes:
                    raise DownloadTooLarge(f"declared size {declared} exceeds limit {max_bytes}")

                return declared, current_url
            finally:
                resp.close()

    raise RedirectLimitExceeded("too many redirects")

    raise RedirectLimitExceeded("too many redirects")