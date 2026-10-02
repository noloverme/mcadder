#!/usr/bin/env python3
"""
Scanner for Minecraft Java servers.

1. Status-ping (SLP) host:25000-26000 to check alive.
2. If alive -> Login attempt with random valid nick.
3. Classify:
   - valid      = Login Success (no kick)
   - whitelisted= Disconnect with "whitelist" in reason (dropped)
   - warning    = alive but kick with other reason / encryption / plugin / etc.
   - offline    = no SLP response (not stored)

Connections can go directly or via http/socks4/socks5 proxies
(single URL or a list with round-robin).

stdlib only: asyncio + struct + json + zlib + random.
"""

import asyncio
import json
import random
import socket
import string
import struct
import time
import zlib

DEFAULT_PROTOCOL = 767  # 1.21.x, used for Status + Login Start (overridden by real protocol after ping)
STATUS_TIMEOUT = 2.5
LOGIN_TIMEOUT = 8.0
PING_CONCURRENCY = 1000
LOGIN_CONCURRENCY = 80

WHITELIST_MARKERS = ("whitelist", "white-list", "white_list", "not whitelisted")


# ------------------------------------------------------------------ utils

def random_nick(prefix="Player") -> str:
    """Valid offline nick: [a-zA-Z0-9_]{3,16}."""
    suffix_len = max(3, min(16 - len(prefix), 6))
    alphabet = string.ascii_letters + string.digits + "_"
    # ensure it starts with a letter
    body = "".join(random.choice(alphabet) for _ in range(suffix_len))
    nick = (prefix + body)[:16]
    if len(nick) < 3:
        nick = (nick + "123")[:16]
    return nick


def encode_varint(value: int) -> bytes:
    out = bytearray()
    value &= 0xFFFFFFFF
    for _ in range(5):
        part = value & 0x7F
        value >>= 7
        if value:
            out.append(part | 0x80)
        else:
            out.append(part)
            break
    return bytes(out)


def decode_varint(buf: bytes, offset: int = 0):
    num = 0
    for i in range(5):
        if offset + i >= len(buf):
            return None, 0  # not enough data
        b = buf[offset + i]
        num |= (b & 0x7F) << (7 * i)
        if not (b & 0x80):
            if num & (1 << 31):
                num -= 1 << 32
            return num, i + 1
    raise ValueError("VarInt too big")


def pack_string(s: str) -> bytes:
    b = s.encode("utf-8")
    return encode_varint(len(b)) + b


def pack_packet(packet_id: int, payload: bytes) -> bytes:
    body = encode_varint(packet_id) + payload
    return encode_varint(len(body)) + body


def build_handshake(host: str, port: int, protocol: int, next_state: int) -> bytes:
    payload = (
        encode_varint(protocol)
        + pack_string(host)
        + struct.pack(">H", port)
        + encode_varint(next_state)
    )
    return pack_packet(0x00, payload)


def build_status_request() -> bytes:
    return pack_packet(0x00, b"")


def offline_uuid(nick: str) -> bytes:
    """Offline-mode UUID like vanilla: MD5('OfflinePlayer:'+nick) with v3 bits."""
    import hashlib
    h = hashlib.md5(("OfflinePlayer:" + nick).encode("utf-8")).digest()
    b = bytearray(h)
    b[6] = (b[6] & 0x0F) | 0x30  # version 3
    b[8] = (b[8] & 0x3F) | 0x80  # variant RFC4122
    return bytes(b)


def build_login_start(nick: str, protocol: int) -> bytes:
    payload = pack_string(nick)
    if protocol >= 764:
        # 1.20.2+ (764): Login Hello = String name + UUID player_id.
        # No signature bool. Offline UUID so the packet decodes on vanilla/ViaVersion.
        payload += offline_uuid(nick)
    elif protocol >= 759:
        # 1.19-1.20.1 (759-763): String name + bool has_sig_data
        payload += b"\x00"  # no signature
    # <759: just the name
    return pack_packet(0x00, payload)


def build_plugin_response(message_id: int) -> bytes:
    # Login Plugin Response: message id varint + successful bool(false) = no data
    payload = encode_varint(message_id) + b"\x00"
    return pack_packet(0x02, payload)


async def read_varint(reader: asyncio.StreamReader) -> int:
    num = 0
    for i in range(5):
        raw = await reader.readexactly(1)
        b = raw[0]
        num |= (b & 0x7F) << (7 * i)
        if not (b & 0x80):
            if num & (1 << 31):
                num -= 1 << 32
            return num
    raise ValueError("VarInt too big")


async def read_packet(reader: asyncio.StreamReader, compression_threshold: int = -1):
    """Returns (packet_id, payload_bytes). Handles optional compression."""
    length = await read_varint(reader)
    if length < 0 or length > 4 * 1024 * 1024:
        raise ValueError(f"Bad packet length: {length}")
    data = await reader.readexactly(length)
    if compression_threshold >= 0:
        uncompressed_len, n = decode_varint(data, 0)
        if uncompressed_len is None:
            raise ValueError("Truncated compressed packet")
        rest = data[n:]
        if uncompressed_len == 0:
            raw = rest  # not compressed
        else:
            raw = zlib.decompress(rest)
        packet_id, m = decode_varint(raw, 0)
        return packet_id, raw[m:]
    else:
        packet_id, m = decode_varint(data, 0)
        return packet_id, data[m:]


def read_string(buf: bytes, offset: int = 0):
    length, n = decode_varint(buf, offset)
    if length is None:
        raise ValueError("Truncated string")
    start = offset + n
    s = buf[start:start + length].decode("utf-8", errors="replace")
    return s, start + length


def chat_to_text(raw_json: str, limit: int = 300) -> str:
    """Best-effort human readable text from disconnect JSON."""
    try:
        obj = json.loads(raw_json)
    except Exception:
        return raw_json[:limit]
    try:
        parts = []

        def walk(o):
            if isinstance(o, str):
                parts.append(o)
            elif isinstance(o, dict):
                t = o.get("translate")
                if isinstance(t, str):
                    parts.append(t)
                txt = o.get("text")
                if isinstance(txt, str) and txt:
                    parts.append(txt)
                for k in ("extra", "with"):
                    v = o.get(k)
                    if isinstance(v, list):
                        for e in v:
                            walk(e)
            elif isinstance(o, list):
                for e in o:
                    walk(e)

        walk(obj)
        text = " ".join(p for p in parts if p).strip()
        if text:
            return text[:limit]
        return raw_json[:limit]
    except Exception:
        return raw_json[:limit]


def is_whitelist_kick(raw_json: str) -> bool:
    low = raw_json.lower()
    return any(m in low for m in WHITELIST_MARKERS)


# ------------------------------------------------------------------ proxies
# http (CONNECT) / socks4(a) / socks5(h), stdlib only, single URL or list.

class ProxyError(Exception):
    """Proxy itself failed (unreachable, auth, handshake)."""


class TargetRefused(Exception):
    """Proxy is alive but reports the target unreachable (≈ conn refused)."""


def parse_proxy(s: str) -> dict:
    """Parse 'socks5://[user:pass@]host:port', 'http://host:port', 'socks4://...'.
    Bare 'host:port' defaults to socks5. Returns dict usable by ProxyPool."""
    from urllib.parse import urlparse, unquote
    s = s.strip().strip("\"'")
    if not s:
        raise ValueError("empty proxy")
    if "://" not in s:
        s = "socks5://" + s
    u = urlparse(s)
    scheme = u.scheme.lower()
    if scheme in ("socks5", "socks5h"):
        ptype = "socks5"
    elif scheme in ("socks4", "socks4a"):
        ptype = "socks4"
    elif scheme in ("http", "https"):
        ptype = "http"
    else:
        raise ValueError(f"unknown proxy scheme: {scheme} (use http/socks4/socks5)")
    host = u.hostname
    if not host:
        raise ValueError(f"bad proxy, no host: {s}")
    port = u.port or (8080 if ptype == "http" else 1080)
    username = unquote(u.username) if u.username else None
    password = unquote(u.password) if u.password else None
    return {
        "type": ptype,
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "tls": scheme == "https",
        "remote_dns": ptype in ("socks5", "http") or scheme in ("socks4a", "socks5h"),
        "raw": s,
    }


def load_proxies(lines) -> list:
    """One proxy URL per line, '#' comments and blanks ignored."""
    out = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(parse_proxy(s))
    return out


class ProxyPool:
    """Round-robin over proxies with dead-proxy skipping (sync, asyncio-safe)."""

    DEAD_AFTER_CONSEC_FAIL = 30

    def __init__(self, proxies: list):
        if not proxies:
            raise ValueError("empty proxy list")
        self.proxies = list(proxies)
        self._i = 0
        self.stats = {id(p): {"ok": 0, "fail": 0, "consec": 0, "dead": False}
                      for p in self.proxies}

    def next(self) -> dict:
        n = len(self.proxies)
        for _ in range(n):
            p = self.proxies[self._i % n]
            self._i += 1
            if not self.stats[id(p)]["dead"]:
                return p
        p = self.proxies[self._i % n]  # all dead -> still try
        self._i += 1
        return p

    def report(self, proxy: dict, ok: bool):
        st = self.stats.get(id(proxy))
        if st is None:
            return
        if ok:
            st["ok"] += 1
            st["consec"] = 0
        else:
            st["fail"] += 1
            st["consec"] += 1
            if st["consec"] >= self.DEAD_AFTER_CONSEC_FAIL:
                st["dead"] = True

    def summary(self):
        ok = sum(s["ok"] for s in self.stats.values())
        fail = sum(s["fail"] for s in self.stats.values())
        dead = sum(1 for s in self.stats.values() if s["dead"])
        return ok, fail, dead


async def _socks5_tunnel(reader, writer, target_host, target_port, proxy, timeout):
    if proxy["username"]:
        writer.write(b"\x05\x02\x00\x02")
    else:
        writer.write(b"\x05\x01\x00")
    await writer.drain()
    ver, method = await asyncio.wait_for(reader.readexactly(2), timeout)
    if ver != 0x05:
        raise ProxyError(f"socks5 bad greeting reply: {ver:#x}")
    if method == 0x02:
        if not proxy["username"]:
            raise ProxyError("socks5 proxy requires auth")
        u = proxy["username"].encode("utf-8")
        pw = (proxy["password"] or "").encode("utf-8")
        if len(u) > 255 or len(pw) > 255:
            raise ProxyError("socks5 credentials too long")
        writer.write(b"\x05" + bytes([len(u)]) + u + bytes([len(pw)]) + pw)
        await writer.drain()
        v, status = await asyncio.wait_for(reader.readexactly(2), timeout)
        if status != 0x00:
            raise ProxyError("socks5 auth failed")
    elif method != 0x00:
        raise ProxyError(f"socks5 no acceptable auth method ({method:#x})")
    hb = target_host.encode("utf-8")  # remote DNS: proxy resolves
    if len(hb) > 255:
        raise ProxyError("target hostname too long for socks5")
    writer.write(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + struct.pack(">H", target_port))
    await writer.drain()
    hdr = await asyncio.wait_for(reader.readexactly(4), timeout)
    ver, rep, _, atyp = hdr[0], hdr[1], hdr[2], hdr[3]
    if ver != 0x05:
        raise ProxyError("socks5 bad connect reply")
    if atyp == 0x01:
        await asyncio.wait_for(reader.readexactly(4 + 2), timeout)
    elif atyp == 0x03:
        ln = (await asyncio.wait_for(reader.readexactly(1), timeout))[0]
        await asyncio.wait_for(reader.readexactly(ln + 2), timeout)
    elif atyp == 0x04:
        await asyncio.wait_for(reader.readexactly(16 + 2), timeout)
    else:
        raise ProxyError(f"socks5 bad ATYP {atyp:#x}")
    if rep != 0x00:
        if rep in (0x04, 0x05):  # host unreachable / conn refused -> target side
            raise TargetRefused(f"socks5 target unreachable ({rep:#x})")
        raise ProxyError(f"socks5 connect rejected ({rep:#x})")


async def _socks4_tunnel(reader, writer, target, target_port, proxy, timeout):
    try:
        ip_bytes = socket.inet_aton(target)
        is_ip = True
    except OSError:
        is_ip = False
        ip_bytes = None
    user = (proxy["username"] or "").encode("utf-8")
    if is_ip:
        req = b"\x04\x01" + struct.pack(">H", target_port) + ip_bytes + user + b"\x00"
    elif proxy.get("remote_dns"):  # socks4a: hostname after userid
        tb = target.encode("utf-8")
        req = (b"\x04\x01" + struct.pack(">H", target_port) + b"\x00\x00\x00\x01"
               + user + b"\x00" + tb + b"\x00")
    else:
        raise ProxyError("socks4 needs a numeric IPv4 (no remote DNS); use socks5/socks4a/http")
    writer.write(req)
    await writer.drain()
    rep = await asyncio.wait_for(reader.readexactly(8), timeout)
    if rep[0] != 0x00:
        raise ProxyError("socks4 bad reply")
    if rep[1] == 0x5A:
        return
    if rep[1] == 0x5B:  # rejected / refused -> target side
        raise TargetRefused("socks4 target rejected")
    raise ProxyError(f"socks4 rejected ({rep[1]:#x})")


async def _http_tunnel(reader, writer, target_host, target_port, proxy, timeout):
    import base64
    lines = [f"CONNECT {target_host}:{target_port} HTTP/1.1",
             f"Host: {target_host}:{target_port}"]
    if proxy["username"]:
        cred = base64.b64encode(
            f"{proxy['username']}:{proxy['password'] or ''}".encode("utf-8")).decode("ascii")
        lines.append(f"Proxy-Authorization: Basic {cred}")
    writer.write(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
    await writer.drain()
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = await asyncio.wait_for(reader.read(4096), timeout)
        if not chunk:
            break
        buf += chunk
        if len(buf) > 65536:
            raise ProxyError("http proxy header too big")
    head = buf.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1", errors="replace")
    status_line = head.split("\r\n", 1)[0] if head else ""
    parts = status_line.split()
    code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    if 200 <= code < 300:
        return
    if code in (502, 503, 504):  # proxy alive, target unreachable
        raise TargetRefused(f"http proxy: target unreachable ({status_line[:80]})")
    raise ProxyError(f"http proxy refused: {status_line[:100] or 'no response'}")


async def open_tunneled(target_host, target_port, timeout, proxy, target_ip=None):
    """TCP to proxy + tunnel to target. Returns (reader, writer)."""
    ph, pp = proxy["host"], proxy["port"]
    try:
        if proxy.get("tls"):
            import ssl
            ctx = ssl.create_default_context()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ph, pp, ssl=ctx), timeout)
        else:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ph, pp), timeout)
    except Exception as e:
        raise ProxyError(f"proxy {ph}:{pp} unreachable: {type(e).__name__}: {e}")
    try:
        if proxy["type"] == "socks5":
            await _socks5_tunnel(reader, writer, target_host, target_port, proxy, timeout)
        elif proxy["type"] == "socks4":
            await _socks4_tunnel(reader, writer, target_ip or target_host,
                                 target_port, proxy, timeout)
        else:
            await _http_tunnel(reader, writer, target_host, target_port, proxy, timeout)
    except Exception:
        try:
            writer.close()
        except Exception:
            pass
        raise
    return reader, writer


async def resolve_one(host: str, timeout: float = 5.0) -> str:
    """Local IPv4 resolve (for socks4 / direct fast path)."""
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(
        loop.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM),
        timeout)
    return infos[0][4][0]


async def _open_target(host, port, timeout, connect_ip=None, proxy_pool=None, _retry=True):
    """Open TCP to a Minecraft server directly or via proxy pool.

    Returns (reader, writer). Target-side refusal surfaces as
    ConnectionRefusedError (counts as offline), proxy breakage as ProxyError
    (retried once with the next proxy).
    """
    if proxy_pool is None:
        dest = connect_ip or host
        return await asyncio.wait_for(asyncio.open_connection(dest, port), timeout)
    proxy = proxy_pool.next()
    tip = None
    if proxy["type"] == "socks4" and not proxy.get("remote_dns"):
        tip = connect_ip
        if not tip or tip == host:
            tip = await resolve_one(host, timeout=timeout)
    try:
        rw = await open_tunneled(host, port, timeout, proxy, target_ip=tip)
    except TargetRefused:
        proxy_pool.report(proxy, True)  # proxy fine, target closed
        raise ConnectionRefusedError(f"target {host}:{port} refused (via proxy)")
    except ProxyError:
        proxy_pool.report(proxy, False)
        if _retry:
            return await _open_target(host, port, timeout, connect_ip, proxy_pool, _retry=False)
        raise
    proxy_pool.report(proxy, True)
    return rw


async def test_proxy(proxy: dict, host: str, port: int, timeout: float = 6.0) -> bool:
    """True if the proxy itself answers (tunnel up or clean target-refused)."""
    try:
        tip = None
        if proxy["type"] == "socks4" and not proxy.get("remote_dns"):
            tip = await resolve_one(host, timeout)
        reader, writer = await open_tunneled(host, port, timeout, proxy, target_ip=tip)
        try:
            writer.close()
        except Exception:
            pass
        return True
    except TargetRefused:
        return True
    except Exception:
        return False


async def filter_working_proxies(proxies: list, host: str, port: int,
                                 timeout: float = 6.0) -> list:
    """Concurrently drop dead proxies; test target may be closed (still proves proxy)."""
    async def one(p):
        return p if await test_proxy(p, host, port, timeout) else None
    res = await asyncio.gather(*[one(p) for p in proxies])
    return [p for p in res if p is not None]


# ------------------------------------------------------------------ SLP ping

async def status_ping(host: str, port: int, timeout: float = STATUS_TIMEOUT,
                    connect_ip: str | None = None, proxy_pool=None):
    """Returns dict(protocol, version_name, motd, players_online...) or raises.

    connect_ip: cached IP to open TCP to (handshake still uses `host` for vhost routing).
    proxy_pool: ProxyPool or None (direct). With socks5/http DNS stays remote.
    """
    t0 = time.monotonic()
    # single timeout for the whole SLP exchange (connect + handshake + response);
    # closed ports fail fast (RST), filtered ones burn the full timeout.
    reader, writer = await _open_target(host, port, timeout, connect_ip, proxy_pool)
    try:
        writer.write(build_handshake(host, port, DEFAULT_PROTOCOL, next_state=1))
        writer.write(build_status_request())
        await writer.drain()

        pid, payload = await asyncio.wait_for(
            read_packet(reader), timeout=max(0.5, timeout - (time.monotonic() - t0))
        )
        if pid != 0x00:
            raise ValueError(f"Unexpected status packet id {pid:#x}")
        json_str, _ = read_string(payload, 0)
        info = json.loads(json_str)
        ping_ms = int((time.monotonic() - t0) * 1000)

        version = info.get("version", {}) or {}
        players = info.get("players", {}) or {}
        desc = info.get("description", "")
        if isinstance(desc, dict):
            motd = chat_to_text(json.dumps(desc), 200)
        else:
            motd = str(desc)[:200]
        return {
            "protocol": int(version.get("protocol", DEFAULT_PROTOCOL)),
            "version_name": str(version.get("name", "?")),
            "motd": motd,
            "players_online": players.get("online"),
            "players_max": players.get("max"),
            "ping_ms": ping_ms,
            "raw": info,
        }
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# ------------------------------------------------------------------ Login attempt

async def try_login(host: str, port: int, protocol: int, nick: str,
                    timeout: float = LOGIN_TIMEOUT, connect_ip: str | None = None,
                    proxy_pool=None):
    """
    Returns (category, reason):
      ("valid", "Login Success ...")
      ("whitelisted", <kick text>)
      ("warning", <reason>)
    Raises on connect failure (caller treats as offline — but we call it only for alive hosts).
    """
    reader, writer = await _open_target(host, port, timeout, connect_ip, proxy_pool)
    compression_threshold = -1
    try:
        writer.write(build_handshake(host, port, protocol, next_state=2))
        writer.write(build_login_start(nick, protocol))
        await writer.drain()

        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return "warning", "login timeout (no final packet)"
            pid, payload = await asyncio.wait_for(
                read_packet(reader, compression_threshold), timeout=left
            )

            if pid == 0x00:  # Disconnect
                try:
                    reason_json, _ = read_string(payload, 0)
                except Exception:
                    reason_json = payload.decode("utf-8", errors="replace")
                text = chat_to_text(reason_json)
                if is_whitelist_kick(reason_json):
                    return "whitelisted", text
                return "warning", f"kicked: {text}"

            elif pid == 0x01:  # Encryption Request -> online-mode
                try:
                    server_id, off = read_string(payload, 0)
                except Exception:
                    server_id = "?"
                return "warning", "online-mode (encryption required, need premium)"

            elif pid == 0x02:  # Login Success -> no whitelist kick
                try:
                    # payload: uuid string? + username (depends on version)
                    # just confirm success
                    return "valid", "Login Success (no kick)"
                except Exception:
                    return "valid", "Login Success"

            elif pid == 0x03:  # Set Compression
                threshold, _ = decode_varint(payload, 0)
                compression_threshold = int(threshold)
                continue

            elif pid == 0x04:  # Login Plugin Request (Velocity/Bungee etc.)
                # answer "not understood" and keep waiting for the real verdict
                try:
                    msg_id, _ = decode_varint(payload, 0)
                except Exception:
                    msg_id = 0
                writer.write(build_plugin_response(int(msg_id)))
                await writer.drain()
                continue

            else:
                # unknown login packet — keep waiting (e.g. custom)
                continue
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# ------------------------------------------------------------------ orchestration

class ScanResult(dict):
    pass


async def resolve_hosts(hosts, timeout: float = 5.0):
    """Resolve each unique hostname once -> {host: ip}. Falls back to host itself."""
    import socket
    loop = asyncio.get_running_loop()
    mapping: dict[str, str] = {}

    async def one(h: str):
        try:
            infos = await asyncio.wait_for(
                loop.getaddrinfo(h, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM),
                timeout,
            )
            v4 = [i for i in infos if i[0] == socket.AF_INET]
            chosen = (v4 or infos)[0]
            mapping[h] = chosen[4][0]
        except Exception:
            mapping[h] = h

    uniq = sorted(set(hosts))
    for i in range(0, len(uniq), 50):
        await asyncio.gather(*[one(h) for h in uniq[i:i + 50]])
    return mapping


async def check_one(host: str, port: int, label: str,
                    status_timeout: float, login_timeout: float,
                    connect_ip: str | None = None, proxy_pool=None):
    """Ping then (if alive) login. Never raises — returns ScanResult."""
    try:
        info = await status_ping(host, port, timeout=status_timeout,
                                 connect_ip=connect_ip, proxy_pool=proxy_pool)
    except Exception:
        return ScanResult(host=host, port=port, label=label,
                          category="offline", reason="no SLP response",
                          protocol=None, motd="", ping_ms=None)
    protocol = info.get("protocol") or DEFAULT_PROTOCOL
    nick = random_nick()
    try:
        category, reason = await try_login(host, port, protocol, nick,
                                           timeout=login_timeout,
                                           connect_ip=connect_ip, proxy_pool=proxy_pool)
    except asyncio.TimeoutError:
        category, reason = "warning", "login timeout"
    except asyncio.IncompleteReadError:
        category, reason = "warning", "connection closed by server (anti-bot? no disconnect packet)"
    except (ConnectionRefusedError, ConnectionResetError, OSError) as e:
        category, reason = "warning", f"login connect failed: {e}"
    except Exception as e:
        category, reason = "warning", f"login error: {type(e).__name__}: {e}"

    extra = f" [{info.get('version_name')}]" if info.get("version_name") else ""
    if category == "valid":
        reason = f"{reason}{extra} nick={nick}"
    elif category == "warning":
        reason = f"{reason}{extra}"
    return ScanResult(host=host, port=port, label=label,
                      category=category, reason=reason,
                      protocol=protocol, motd=info.get("motd", ""),
                      ping_ms=info.get("ping_ms"),
                      version_name=info.get("version_name", ""))


async def scan_targets(targets, concurrency: int = PING_CONCURRENCY,
                       status_timeout: float = STATUS_TIMEOUT,
                       login_timeout: float = LOGIN_TIMEOUT,
                       login_concurrency: int = LOGIN_CONCURRENCY,
                       on_progress=None, proxies=None):
    """
    Two-phase scan (fast):
      phase 1 (ping sweep): SLP all targets with high concurrency, short timeout.
      phase 2 (login): only alive hosts, low concurrency, full login timeout.

    targets: list of (host, port, label).
    proxies: None (direct), list of parse_proxy() dicts, or a ProxyPool.
      Round-robin across connections; dead proxies are skipped.
    Returns list[ScanResult] with ONLY alive hosts (valid/warning/whitelisted).
    Offline count = len(targets) - len(returned).
    on_progress(done, total_alive, result) is called for each login verdict.
    """
    total = len(targets)
    if total == 0:
        return []

    pool = None
    if proxies is not None:
        pool = proxies if isinstance(proxies, ProxyPool) else ProxyPool(proxies)

    # --- DNS once per host (skipped for proxies with remote DNS) ---
    need_dns = pool is None or any(
        p["type"] == "socks4" and not p.get("remote_dns") for p in pool.proxies)
    ip_map = await resolve_hosts([h for h, _, _ in targets]) if need_dns else {}

    # --- phase 1: ping sweep (queue workers, bounded tasks, no result hoarding) ---
    alive: list[tuple] = []  # (host, port, label, info, ip)
    ping_q: asyncio.Queue = asyncio.Queue()
    for t in targets:
        ping_q.put_nowait(t)
    ping_done = 0
    t_start = time.monotonic()

    async def ping_worker():
        nonlocal ping_done
        while True:
            try:
                h, p, lb = ping_q.get_nowait()
            except asyncio.QueueEmpty:
                return
            ip = ip_map.get(h, h) if need_dns else None
            try:
                info = await status_ping(h, p, timeout=status_timeout,
                                         connect_ip=ip, proxy_pool=pool)
                alive.append((h, p, lb, info, ip))
            except Exception:
                pass
            ping_done += 1
            if ping_done % 2000 == 0 or ping_done == total:
                el = time.monotonic() - t_start
                rate = ping_done / max(el, 0.01)
                eta = (total - ping_done) / max(rate, 0.01)
                print(f"\rPING [{ping_done}/{total}] alive={len(alive)} "
                      f"{rate:.0f}/s ETA {eta:.0f}s", end="", flush=True)
            ping_q.task_done()

    n_ping = max(1, min(concurrency, total))
    await asyncio.gather(*[asyncio.create_task(ping_worker()) for _ in range(n_ping)])
    el = time.monotonic() - t_start
    print(f"\rPING [{total}/{total}] alive={len(alive)} "
          f"{total / max(el, 0.01):.0f}/s done in {el:.0f}s")

    if not alive:
        return []

    # --- phase 2: login only alive (dozens, not thousands) ---
    login_q: asyncio.Queue = asyncio.Queue()
    for a in alive:
        login_q.put_nowait(a)
    results: list = []
    login_done = 0
    n_alive = len(alive)

    async def login_worker():
        nonlocal login_done
        while True:
            try:
                h, p, lb, info, ip = login_q.get_nowait()
            except asyncio.QueueEmpty:
                return
            protocol = info.get("protocol") or DEFAULT_PROTOCOL
            nick = random_nick()
            try:
                category, reason = await try_login(h, p, protocol, nick,
                                                   timeout=login_timeout,
                                                   connect_ip=ip, proxy_pool=pool)
            except asyncio.TimeoutError:
                category, reason = "warning", "login timeout"
            except asyncio.IncompleteReadError:
                category, reason = "warning", "connection closed by server (anti-bot? no disconnect packet)"
            except (ConnectionRefusedError, ConnectionResetError, OSError) as e:
                category, reason = "warning", f"login connect failed: {e}"
            except Exception as e:
                category, reason = "warning", f"login error: {type(e).__name__}: {e}"
            extra = f" [{info.get('version_name')}]" if info.get("version_name") else ""
            if category == "valid":
                reason = f"{reason}{extra} nick={nick}"
            elif category in ("warning", "whitelisted"):
                reason = f"{reason}{extra}"
            r = ScanResult(host=h, port=p, label=lb, category=category, reason=reason,
                           protocol=protocol, motd=info.get("motd", ""),
                           ping_ms=info.get("ping_ms"),
                           version_name=info.get("version_name", ""))
            results.append(r)
            login_done += 1
            if on_progress:
                try:
                    on_progress(login_done, n_alive, r)
                except Exception:
                    pass
            login_q.task_done()

    n_login = max(1, min(login_concurrency, n_alive))
    await asyncio.gather(*[asyncio.create_task(login_worker()) for _ in range(n_login)])
    return results


def _parse_line_local(line):
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "|" in s:
        name, ip = s.split("|", 1)
        name, ip = name.strip(), ip.strip()
        if not ip:
            return None
        return (name if name else None, ip)
    return (None, s)


def build_targets_from_lines(lines, port_from: int = 25000, port_to: int = 26000):
    """
    lines: raw lines from localips.txt (may be 'Name|host' or 'host' or 'host:port').
    Returns list[(host, port, label)].
    - 'host' without port -> expand to port_from..port_to.
    - 'host:port' -> single target.
    """
    targets = []
    for line in lines:
        p = _parse_line_local(line)
        if not p:
            continue
        name, ip = p
        ip = ip.strip()
        host, port = None, None
        # naive host:port split (ignore IPv6)
        if ip.count(":") == 1 and ip.rsplit(":", 1)[1].strip().isdigit():
            h, ps = ip.rsplit(":", 1)
            host, port = h.strip(), int(ps.strip())
        if host and port:
            label = name or f"{host}:{port}"
            # label for servers.dat: keep base name if given
            targets.append((host, port, label))
        else:
            host = ip
            base = name or host
            for prt in range(port_from, port_to + 1):
                targets.append((host, prt, f"{base}-{prt}"))
    return targets


def split_results(results):
    valid = [r for r in results if r.get("category") == "valid"]
    warning = [r for r in results if r.get("category") == "warning"]
    whitelisted = [r for r in results if r.get("category") == "whitelisted"]
    offline = [r for r in results if r.get("category") == "offline"]
    return valid, warning, whitelisted, offline


def results_to_lines(results):
    """Convert ScanResults to localips.txt-style lines: 'Label|host:port'."""
    out = []
    for r in results:
        label = str(r.get("label", ""))
        addr = f"{r['host']}:{r['port']}"
        if not label or label == addr:
            out.append(addr)
        elif "|" in label:
            out.append(label)  # already formatted
        else:
            out.append(f"{label}|{addr}")
    return out
