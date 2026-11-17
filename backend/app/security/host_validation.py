
import ipaddress
import socket

from urllib.parse import urlsplit


class HostValidationError(ValueError):
    """Raised when an external database host is not allowed."""


def validate_database_host(host, allow_localhost=False):
    """
    Validate a database hostname or IP address.

    Args:
        host: Database server hostname or IP address.
        allow_localhost: Allow loopback addresses in local development.

    Returns:
        str: Validated hostname.

    Raises:
        HostValidationError: If the host is invalid or unsafe.
    """

    if not isinstance(host, str):
        raise HostValidationError("Database host must be a string.")

    host = host.strip()

    if not host or len(host) > 253:
        raise HostValidationError("Invalid database host.")

    if any(char.isspace() for char in host):
        raise HostValidationError("Database host contains whitespace.")

    if "://" in host or "/" in host or "\\" in host:
        raise HostValidationError(
            "Enter a hostname or IP address, not a URL."
        )

    if host.lower() == "localhost":
        if allow_localhost:
            return host

        raise HostValidationError(
            "Localhost connections are not allowed."
        )

    try:
        ip_addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            results = socket.getaddrinfo(
                host,
                None,
                type=socket.SOCK_STREAM
            )

            ip_addresses = list({
                ipaddress.ip_address(result[4][0])
                for result in results
            })

        except (socket.gaierror, ValueError):
            raise HostValidationError(
                "Database hostname could not be resolved."
            )

    if not ip_addresses:
        raise HostValidationError(
            "Database hostname has no valid IP addresses."
        )

    for address in ip_addresses:
        if address.is_loopback and allow_localhost:
            continue

        if not address.is_global:
            raise HostValidationError(
                "Database host resolves to a non-public IP address."
            )

    return host
