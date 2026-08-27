"""tests/test_ssrf_bypass.py — SSRF Protection, DNS Rebinding, and IPv4-Mapped IPv6 Test Suite."""

import ipaddress
import socket
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from safe_download import (
    DefaultResolver,
    SSRFGuardedResolver,
    _is_blocked_address,
    _is_blocked_ip,
    _validate_url_target,
    safe_download,
    safe_head,
    SSRFBlocked,
    RedirectLimitExceeded,
    DownloadTooLarge,
)


def _resolve_result(host: str, ip: str, port: int = 80) -> dict:
    """Build an aiohttp ResolveResult entry the way a resolver would return it."""
    return {
        "hostname": host,
        "host": ip,
        "port": port,
        "family": socket.AF_INET,
        "proto": 6,
        "flags": 0,
    }


def _head_response(status: int, headers: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    resp.close = MagicMock()
    return resp


def test_ipv4_blocked_ranges():
    """Verify all critical IPv4 private and link-local ranges are blocked."""
    blocked_ips = [
        "127.0.0.1",
        "127.0.0.2",
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "169.254.169.254",  # AWS/GCP/Azure Metadata
        "100.64.0.1",       # Carrier-grade NAT
        "192.0.2.1",        # TEST-NET-1
        "198.51.100.1",     # TEST-NET-2
        "203.0.113.1",      # TEST-NET-3
        "198.18.0.1",       # Benchmark
        "224.0.0.1",        # Multicast
        "0.0.0.0",          # Current network
    ]
    for ip_str in blocked_ips:
        ip = ipaddress.ip_address(ip_str)
        assert _is_blocked_ip(ip) is True, f"Expected {ip_str} to be blocked"


def test_ipv6_blocked_ranges():
    """Verify IPv6 private, loopback, link-local, and special ranges are blocked."""
    blocked_ips = [
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "fd12:3456:789a::1",
        "ff02::1",          # Multicast
        "2001:db8::1",      # Documentation
    ]
    for ip_str in blocked_ips:
        ip = ipaddress.ip_address(ip_str)
        assert _is_blocked_ip(ip) is True, f"Expected {ip_str} to be blocked"


def test_ipv4_mapped_ipv6_bypass_prevention():
    """CRITICAL: Test that IPv4-mapped IPv6 representations are normalized and blocked."""
    mapped_ips = [
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "::ffff:10.0.0.1",
        "::ffff:192.168.1.1",
        "::ffff:172.16.0.1",
        "::ffff:0.0.0.0",
        "::ffff:100.64.0.1",
    ]
    for mapped_str in mapped_ips:
        ip = ipaddress.ip_address(mapped_str)
        assert _is_blocked_ip(ip) is True, f"Expected IPv4-mapped {mapped_str} to be blocked"


def test_public_ips_allowed():
    """Verify legitimate public IPs are allowed."""
    allowed_ips = [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.216.34",     # example.com
        "2606:2800:220:1:248:1893:25c8:1946",  # example.com IPv6
    ]
    for ip_str in allowed_ips:
        ip = ipaddress.ip_address(ip_str)
        assert _is_blocked_ip(ip) is False, f"Expected public IP {ip_str} to be allowed"


def test_blocked_address_rejects_unparseable_input():
    """An address the blocklist cannot parse must fail closed."""
    assert _is_blocked_address("not-an-ip") is True
    assert _is_blocked_address("") is True
    assert _is_blocked_address("fe80::1%eth0") is True   # scope id stripped, still link-local
    assert _is_blocked_address("93.184.216.34") is False


@pytest.mark.asyncio
async def test_validate_url_target_blocked_hostnames():
    """Test blocked hostnames like localhost, metadata, and internal domains."""
    for host in ["localhost", "127.0.0.1", "metadata.google.internal", "instance-data", "test.local", "router.internal"]:
        with pytest.raises(SSRFBlocked):
            await _validate_url_target(f"http://{host}/file.zip")


@pytest.mark.asyncio
async def test_validate_url_target_rejects_nonstandard_ports():
    """Only 80/443 may be targeted, so internal services on routable IPs stay unreachable."""
    for port in (22, 25, 6379, 8080, 9200):
        with pytest.raises(SSRFBlocked):
            await _validate_url_target(f"http://93.184.216.34:{port}/file.zip")

    # The default ports remain usable.
    assert await _validate_url_target("http://93.184.216.34/file.zip")
    assert await _validate_url_target("https://93.184.216.34:443/file.zip")


# ──────────────────────────────────────────────────────────────────────────────
# DNS rebinding: the resolver used at connect time must re-check the answer
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guarded_resolver_blocks_rebound_answer():
    """A nameserver that answers with an internal address at connect time is refused."""
    resolver = SSRFGuardedResolver()
    rebound = [_resolve_result("evil.example", "169.254.169.254")]

    with patch.object(DefaultResolver, "resolve", new=AsyncMock(return_value=rebound)):
        with pytest.raises(SSRFBlocked):
            await resolver.resolve("evil.example", 80)


@pytest.mark.asyncio
async def test_guarded_resolver_filters_mixed_answers():
    """Blocked addresses are dropped while public ones are still usable."""
    resolver = SSRFGuardedResolver()
    answer = [
        _resolve_result("mixed.example", "127.0.0.1"),
        _resolve_result("mixed.example", "93.184.216.34"),
    ]

    with patch.object(DefaultResolver, "resolve", new=AsyncMock(return_value=answer)):
        allowed = await resolver.resolve("mixed.example", 80)

    assert [entry["host"] for entry in allowed] == ["93.184.216.34"]


@pytest.mark.asyncio
async def test_guarded_resolver_rejects_unparseable_answer():
    """Garbage in the answer must not be treated as a public address."""
    resolver = SSRFGuardedResolver()
    answer = [_resolve_result("weird.example", "totally-not-an-ip")]

    with patch.object(DefaultResolver, "resolve", new=AsyncMock(return_value=answer)):
        with pytest.raises(SSRFBlocked):
            await resolver.resolve("weird.example", 80)


@pytest.mark.asyncio
async def test_guarded_resolver_blocks_hostname_before_lookup():
    """Blocked hostnames are refused without consulting DNS at all."""
    resolver = SSRFGuardedResolver()
    inner = AsyncMock()

    with patch.object(DefaultResolver, "resolve", new=inner):
        with pytest.raises(SSRFBlocked):
            await resolver.resolve("metadata.google.internal", 80)

    inner.assert_not_called()


@pytest.mark.asyncio
async def test_safe_download_blocks_dns_rebinding(tmp_path):
    """Regression: passing the pre-flight check must not be enough to reach an internal host.

    The pre-flight validation is stubbed out to emulate an attacker-controlled
    nameserver returning a public address for the check; the address handed to
    the connector is internal. The download must still be refused.
    """
    dest = tmp_path / "payload.bin"
    rebound = [_resolve_result("rebind.example", "169.254.169.254")]

    with patch("safe_download._validate_url_target", new=AsyncMock()):
        with patch.object(DefaultResolver, "resolve", new=AsyncMock(return_value=rebound)):
            with pytest.raises(SSRFBlocked):
                await safe_download("http://rebind.example/payload.bin", str(dest))

    assert not dest.exists()


# ──────────────────────────────────────────────────────────────────────────────
# safe_head
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_safe_head_blocks_private_ip_literal():
    """safe_head refuses a private target before issuing any request."""
    head = AsyncMock()
    with patch("aiohttp.ClientSession.head", new=head):
        with pytest.raises(SSRFBlocked):
            await safe_head("http://127.0.0.1/test")
    head.assert_not_called()


@pytest.mark.asyncio
async def test_safe_head_blocks_redirect_to_private_ip():
    """A public first hop that redirects to loopback is caught on the next hop."""
    resp = _head_response(302, {"Location": "http://127.0.0.1/internal"})

    with patch("aiohttp.ClientSession.head", new=AsyncMock(return_value=resp)):
        with pytest.raises(SSRFBlocked):
            await safe_head("http://93.184.216.34/start")


@pytest.mark.asyncio
async def test_safe_head_redirect_limit_enforced():
    """An endless redirect chain trips RedirectLimitExceeded."""
    resp = _head_response(302, {"Location": "http://93.184.216.34/next"})

    with patch("aiohttp.ClientSession.head", new=AsyncMock(return_value=resp)):
        with pytest.raises(RedirectLimitExceeded):
            await safe_head("http://93.184.216.34/start")


@pytest.mark.asyncio
async def test_safe_head_returns_declared_size():
    """A 200 response yields its Content-Length and the final URL."""
    resp = _head_response(200, {"Content-Length": "4096"})

    with patch("aiohttp.ClientSession.head", new=AsyncMock(return_value=resp)):
        declared, final_url = await safe_head("http://93.184.216.34/file.zip")

    assert declared == 4096
    assert final_url == "http://93.184.216.34/file.zip"


@pytest.mark.asyncio
async def test_safe_head_ignores_content_length_of_error_page():
    """405/404 bodies describe an error page, not the file, so their size is ignored."""
    resp = _head_response(405, {"Content-Length": "512"})

    with patch("aiohttp.ClientSession.head", new=AsyncMock(return_value=resp)):
        declared, _ = await safe_head("http://93.184.216.34/file.zip")

    assert declared is None


@pytest.mark.asyncio
async def test_safe_head_enforces_max_bytes():
    """A declared size over the cap is rejected up front."""
    resp = _head_response(200, {"Content-Length": str(50 * 1024 * 1024)})

    with patch("aiohttp.ClientSession.head", new=AsyncMock(return_value=resp)):
        with pytest.raises(DownloadTooLarge):
            await safe_head("http://93.184.216.34/big.zip", max_bytes=1024)
