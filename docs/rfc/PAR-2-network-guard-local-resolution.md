# PAR-2: Local hostname and unspecified interface resolution in network guard

Status: draft

## Summary

The network guard intercepts socket method calls and name resolvers to block network operations outside loopback. However, `_guard_resolver` treats `None`, `""`, and local hostnames as disallowed destinations, raising `PermissionError` on standard local server bindings.

## Motivation

Standard Python libraries and test servers (e.g., `http.server`, `urllib`, `asyncio.start_server`, Starlette, Werkzeug) use `socket.getaddrinfo(None, port, flags=socket.AI_PASSIVE)` or `socket.getaddrinfo("", port)` when binding test HTTP/gRPC listeners to local interfaces. Additionally, tests frequently resolve `socket.gethostname()` to test service identity.

Under `network_blocked()`, `_is_loopback_host(address)` returns `False` for `None`, `""`, and local machine hostnames, raising `PermissionError` and preventing standard local mock servers from running.

## Design

Update `_is_loopback_host` and `_guard_resolver` in `network.py`:
1. If `address is None` or `address == ""`, allow resolution if `AI_PASSIVE` is set or the method is binding/listening locally.
2. Cache the machine's local hostname via `socket.gethostname()` and recognize it as a local interface name.
3. Keep external DNS resolutions and non-loopback IP connections blocked.

## Alternatives considered

- **Require `@pytest.mark.enable_network`:** Require any test setting up a local server with `None` or `""` to opt out of network protection entirely. This weakens isolation because actual outbound internet traffic would be permitted during that test.
- **Allow all `getaddrinfo` calls:** Only guard `connect()` / `sendto()`. This would permit DNS leakage during tests.

## Open questions

1. Should binding to `0.0.0.0` (all IPv4 interfaces) or `::` (all IPv6 interfaces) be permitted by default, or restricted strictly to loopback (`127.0.0.1` / `::1`)?
   - *Option A (Recommended):* Permit `0.0.0.0` and `::` for local `bind()` and `listen()` operations, but block `connect()` and outbound traffic.
   - *Option B:* Strictly require `127.0.0.1` / `::1` for all socket binds under the guard.
2. Should `socket.gethostname()` be automatically treated as loopback?
   - *Option A (Recommended):* Yes, allow resolving the local machine's hostname.
   - *Option B:* Require explicit `@pytest.mark.enable_network` for local hostname lookups.

## Decision

Pending owner review.
