
import socket

import pytest

from app.security.host_validation import (
    validate_database_host,
    HostValidationError
)


def test_public_ip_is_allowed():
    """Allow a valid public IPv4 address."""

    result = validate_database_host("8.8.8.8")

    assert result == "8.8.8.8"


def test_public_hostname_is_allowed(monkeypatch):
    """Allow a hostname resolving to a public IP."""

    monkeypatch.setattr(
        "app.security.host_validation.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 0)
            )
        ]
    )

    result = validate_database_host("example.com")

    assert result == "example.com"


def test_localhost_allowed_in_development():
    """Allow localhost when explicitly enabled."""

    result = validate_database_host(
        "localhost",
        allow_localhost=True
    )

    assert result == "localhost"


def test_localhost_rejected_in_production():
    """Reject localhost by default."""

    with pytest.raises(HostValidationError):
        validate_database_host("localhost")


def test_loopback_ip_allowed_in_development():
    """Allow loopback IP in local development."""

    result = validate_database_host(
        "127.0.0.1",
        allow_localhost=True
    )

    assert result == "127.0.0.1"


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.0.10",
        "192.168.1.10",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fc00::1"
    ]
)
def test_unsafe_ip_addresses_rejected(host):
    """Reject private, loopback, link-local and unspecified IPs."""

    with pytest.raises(HostValidationError):
        validate_database_host(host)


def test_hostname_resolving_to_private_ip_rejected(monkeypatch):
    """Reject hostnames that resolve to private addresses."""

    monkeypatch.setattr(
        "app.security.host_validation.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.10", 0)
            )
        ]
    )

    with pytest.raises(HostValidationError):
        validate_database_host("internal.example.com")


def test_hostname_with_mixed_public_and_private_ips_rejected(monkeypatch):
    """Reject a hostname if any resolved address is unsafe."""

    monkeypatch.setattr(
        "app.security.host_validation.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 0)
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.10", 0)
            )
        ]
    )

    with pytest.raises(HostValidationError):
        validate_database_host("mixed.example.com")


def test_unresolvable_hostname_rejected(monkeypatch):
    """Reject hostnames that cannot be resolved."""

    def raise_dns_error(*args, **kwargs):
        raise socket.gaierror("Name resolution failed")

    monkeypatch.setattr(
        "app.security.host_validation.socket.getaddrinfo",
        raise_dns_error
    )

    with pytest.raises(HostValidationError):
        validate_database_host("invalid.example")


@pytest.mark.parametrize(
    "host",
    [
        "",
        "   ",
        "example.com/path",
        "https://example.com",
        "example.com database",
        "a" * 254
    ]
)
def test_invalid_host_inputs_rejected(host):
    """Reject malformed host values."""

    with pytest.raises(HostValidationError):
        validate_database_host(host)


@pytest.mark.parametrize(
    "host",
    [
        None,
        123,
        [],
        {}
    ]
)
def test_non_string_host_rejected(host):
    """Reject values that are not strings."""

    with pytest.raises(HostValidationError):
        validate_database_host(host)
