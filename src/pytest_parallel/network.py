from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

_SOCKET_METHODS = (
    "accept",
    "bind",
    "connect",
    "connect_ex",
    "listen",
    "recv",
    "recv_into",
    "recvfrom",
    "recvfrom_into",
    "recvmsg",
    "recvmsg_into",
    "send",
    "sendall",
    "sendfile",
    "sendmsg",
    "sendto",
)
_RESOLVER_FUNCTIONS = ("getaddrinfo", "gethostbyaddr", "gethostbyname", "gethostbyname_ex", "getnameinfo")
_BLOCKED_MESSAGE = (
    "Network access outside loopback is disabled by pytest-parallel; "
    "use @pytest.mark.enable_network to allow it for this test"
)


@contextmanager
def network_blocked() -> Iterator[None]:
    originals: list[tuple[Any, str, Callable[..., Any]]] = []
    try:
        for name in _SOCKET_METHODS:
            original = getattr(socket.socket, name, None)
            if original is None:
                continue
            originals.append((socket.socket, name, original))
            setattr(socket.socket, name, _guard_network_operation(name, original))
        for name in _RESOLVER_FUNCTIONS:
            original = getattr(socket, name, None)
            if original is None:
                continue
            originals.append((socket, name, original))
            setattr(socket, name, _guard_resolver(name, original))
        yield
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def _guard_network_operation(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    def guarded(sock: socket.socket, *args: Any, **kwargs: Any) -> Any:
        if not _targets_loopback(sock, name, args, kwargs):
            raise PermissionError(_BLOCKED_MESSAGE)
        return original(sock, *args, **kwargs)

    return guarded


def _targets_loopback(
    sock: socket.socket,
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> bool:
    if sock.family == getattr(socket, "AF_UNIX", None):
        return True

    address = None
    if name in {"bind", "connect", "connect_ex"}:
        address = args[0] if args else kwargs.get("address")
    elif name == "sendto":
        address = kwargs.get("address", args[-1] if len(args) >= 2 else None)
    elif name == "sendmsg" and (len(args) >= 4 or "address" in kwargs):
        address = args[3] if len(args) >= 4 else kwargs["address"]
    elif name in {"accept", "listen"}:
        try:
            address = sock.getsockname()
        except OSError:
            return False
    elif name in {"recv", "recv_into", "recvfrom", "recvfrom_into", "recvmsg", "recvmsg_into"}:
        try:
            address = sock.getpeername()
        except OSError:
            try:
                address = sock.getsockname()
            except OSError:
                return False
    else:
        try:
            address = sock.getpeername()
        except OSError:
            return False

    if isinstance(address, tuple) and address:
        host = address[0]
    elif isinstance(address, str):
        host = address
    else:
        return False

    return _is_loopback_host(host)


def _guard_resolver(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    def guarded(*args: Any, **kwargs: Any) -> Any:
        address = args[0] if args else kwargs.get("host", kwargs.get("sockaddr"))
        if name == "getnameinfo":
            address = args[0] if args else kwargs.get("sockaddr")
            if isinstance(address, tuple) and address:
                address = address[0]
        if not _is_loopback_host(address):
            raise PermissionError(_BLOCKED_MESSAGE)
        return original(*args, **kwargs)

    return guarded


def _is_loopback_host(host: Any) -> bool:
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    if host.casefold() in {"localhost", "localhost."}:
        return True
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or (
            isinstance(address, ipaddress.IPv6Address)
            and address.ipv4_mapped is not None
            and address.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False
