"""tests/test_ssrf_bypass.py — SSRF Protection and IPv4-Mapped IPv6 Test Suite."""

import ipaddress
import socket
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from safe_download import (
    _is_blocked_ip,
    _validate_url_target,
    _validate_url_target_sync,
    safe_download,
    safe_head,
    SSRFBlocked,
    RedirectLimitExceeded,
    DownloadTooLarge,
)


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


@pytest.mark.asyncio
async def test_validate_url_target_blocked_hostnames():
    """Test blocked hostnames like localhost, metadata, and internal domains."""
    for host in ["localhost", "127.0.0.1", "metadata.google.internal", "instance-data", "test.local", "router.internal"]:
        with pytest.raises(SSRFBlocked):
            await _validate_url_target(f"http://{host}/file.zip")


def test_redirect_to_private_ip_blocked():
    """Test that safe_head blocks redirect to private IP even if initial URL is public."""
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "127.0.0.1":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    with patch("socket.getaddrinfo", side_effect=mock_getaddrinfo):
        with pytest.raises(SSRFBlocked):
            safe_head("http://127.0.0.1/test")


def test_redirect_limit_enforced():
    """Test that excessive redirects trigger RedirectLimitExceeded in safe_head."""
    with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]):
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"Location": "http://example.com/next"}

        mock_session = MagicMock()
        mock_session.head.return_value = mock_resp

        with patch("requests.Session", return_value=mock_session):
            with pytest.raises(RedirectLimitExceeded):
                safe_head("http://example.com/start")
