from __future__ import annotations

import http.client
import socket
import ssl
from urllib.parse import urljoin, urlsplit

from agentsentry.config import Settings
from agentsentry.schemas import digest
from .filesystem import BoundaryError
from .registry import network_target


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, ip):
        super().__init__(host, port, timeout=5)
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)


class PinnedHTTPS(PinnedHTTP):
    def connect(self):
        raw = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(
            raw, server_hostname=self.host
        )


def request(
    settings: Settings, url: str, method: str, body: str, expected_version: str
):
    # Every redirect re-enters host/IP validation. Credential-bearing headers are not accepted.
    original_host = urlsplit(url).hostname
    for _ in range(4):
        host, _, addresses = network_target(settings, url)
        if digest(addresses) != expected_version:
            raise BoundaryError("DESTINATION_CHANGED")
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        conn = (PinnedHTTPS if parts.scheme == "https" else PinnedHTTP)(
            host, port, addresses[0]
        )
        try:
            conn.request(
                method,
                (parts.path or "/") + ("?" + parts.query if parts.query else ""),
                body.encode(),
                {"Content-Type": "text/plain; charset=utf-8", "Host": parts.netloc},
            )
            result = conn.getresponse()
            if result.status in {301, 302, 303, 307, 308}:
                target = urljoin(url, result.getheader("Location") or "")
                # Do not replay potentially sensitive request bodies across authorities.
                if urlsplit(target).hostname != original_host:
                    raise BoundaryError("CROSS_ORIGIN_REDIRECT_DENIED")
                if parts.scheme == "https" and urlsplit(target).scheme != "https":
                    raise BoundaryError("HTTPS_DOWNGRADE_DENIED")
                # An exact user/approval URL does not authorize another path/port.
                # The caller must submit the redirect target as a new guarded call.
                raise BoundaryError("REDIRECT_REQUIRES_NEW_ACTION")
            raw = result.read(settings.max_file + 1)
            if len(raw) > settings.max_file:
                raise BoundaryError("RESPONSE_BUDGET_EXCEEDED")
            return {
                "status": result.status,
                "body": raw.decode("utf-8", errors="replace"),
            }
        finally:
            conn.close()
    raise BoundaryError("REDIRECT_BUDGET_EXCEEDED")
