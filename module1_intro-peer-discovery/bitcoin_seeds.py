import hashlib
import ipaddress
import os
import socket
import struct
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BITCOIN_DNS_SEEDS = [
    "seed.bitcoin.sipa.be",          # Pieter Wuille
    "dnsseed.bluematt.me",           # Matt Corallo
    "dnsseed.bitcoin.dashjr.org",    # Luke Dashjr
    "seed.bitcoinstats.com",         # Christian Decker
    "seed.bitcoin.jonasschnelli.ch", # Jonas Schnelli
    "seed.btc.petertodd.org",        # Peter Todd
    "seed.bitcoin.sprovoost.nl",     # Sjors Provoost
    "dnsseed.emzy.de",               # Stephan Wegner
    "seed.bitcoin.wiz.biz",          # Jason Maurice
]
PORT = 8333
TIMEOUT = 3.0
OUTPUT_FILE = "active_bitcoin_nodes.txt"

# Protocol constants
MAGIC = bytes.fromhex("f9beb4d9")   # mainnet start string
PROTOCOL_VERSION = 70016
USER_AGENT = b"/btc-seed-probe:0.1/"
HEADER_SIZE = 24                    # magic(4) + command(12) + length(4) + checksum(4)
MAX_PAYLOAD = 4_000_000             # we only expect small pre-handshake messages
MAX_MESSAGES = 8                    # stop reading after this many messages


class ProtocolError(Exception):
    """Raised when a peer sends something that isn't valid Bitcoin P2P data."""


# ---------------------------------------------------------------------------
# Serialization primitives
# ---------------------------------------------------------------------------
def double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def encode_varint(n: int) -> bytes:
    """Bitcoin CompactSize integer."""
    if n < 0xFD:
        return struct.pack("<B", n)
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)


def decode_varint(data: bytes, offset: int = 0):
    """Returns (value, new_offset)."""
    prefix = data[offset]
    if prefix < 0xFD:
        return prefix, offset + 1
    if prefix == 0xFD:
        return struct.unpack_from("<H", data, offset + 1)[0], offset + 3
    if prefix == 0xFE:
        return struct.unpack_from("<I", data, offset + 1)[0], offset + 5
    return struct.unpack_from("<Q", data, offset + 1)[0], offset + 9


def encode_varstr(b: bytes) -> bytes:
    return encode_varint(len(b)) + b


def decode_varstr(data: bytes, offset: int = 0):
    length, offset = decode_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise ProtocolError("var_str runs past end of payload")
    return data[offset:end], end


def encode_net_addr(ip: str, port: int, services: int = 0) -> bytes:
    """
    26-byte network address as used inside the version message
    (no timestamp field there): services(8 LE) + IPv6/IPv4-mapped(16) + port(2 BE).
    """
    addr = ipaddress.ip_address(ip.split("%")[0])  # drop any IPv6 zone id
    if addr.version == 4:
        packed = b"\x00" * 10 + b"\xff\xff" + addr.packed
    else:
        packed = addr.packed
    return struct.pack("<Q", services) + packed + struct.pack(">H", port)


# ---------------------------------------------------------------------------
# Message envelope
# ---------------------------------------------------------------------------
def pack_message(command: str, payload: bytes = b"") -> bytes:
    """Wrap a payload in the 24-byte P2P header."""
    cmd = command.encode("ascii")
    if len(cmd) > 12:
        raise ValueError("command too long")
    return (
        MAGIC
        + cmd.ljust(12, b"\x00")
        + struct.pack("<I", len(payload))
        + double_sha256(payload)[:4]
        + payload
    )


def unpack_header(header: bytes):
    """Returns (command, payload_length, checksum)."""
    if len(header) != HEADER_SIZE:
        raise ProtocolError("short header")
    if header[:4] != MAGIC:
        raise ProtocolError("bad magic")
    command = header[4:16].rstrip(b"\x00").decode("ascii", errors="replace")
    (length,) = struct.unpack("<I", header[16:20])
    return command, length, header[20:24]


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ProtocolError("connection closed by peer")
        buf.extend(chunk)
    return bytes(buf)


def read_message(sock: socket.socket):
    """Read one full message. Returns (command, payload)."""
    command, length, checksum = unpack_header(recv_exact(sock, HEADER_SIZE))
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"payload too large: {length}")
    payload = recv_exact(sock, length) if length else b""
    if double_sha256(payload)[:4] != checksum:
        raise ProtocolError("checksum mismatch")
    return command, payload


# ---------------------------------------------------------------------------
# Discovery + probing
# ---------------------------------------------------------------------------
def query_dns_seed(seed_domain):
    """Queries a DNS seed and returns a set of IP addresses."""
    node_ips = set()
    try:
        addr_info = socket.getaddrinfo(seed_domain, PORT, 0, socket.SOCK_STREAM)
        for item in addr_info:
            node_ips.add(item[4][0])
    except socket.gaierror as e:
        print(f"[!] DNS resolution failed for {seed_domain}: {e}")
    except Exception as e:
        print(f"[!] An error occurred querying {seed_domain}: {e}")
    return node_ips


def save_to_file(nodes, filename):
    """Persist results as tab-separated: ip, protocol version, height, user agent."""
    try:
        with open(filename, "w") as f:
            for n in sorted(nodes, key=lambda n: n["ip"]):
                f.write(f"{n['ip']}\t{n['version']}\t{n['start_height']}\t{n['user_agent']}\n")
        print(f"\n[+] Saved {len(nodes)} verified nodes to '{filename}'")
    except IOError as e:
        print(f"\n[!] Failed to save to file: {e}")


def main():
    print("Starting Bitcoin DNS Seed Discovery...\n")
    candidates = set()

    for seed in BITCOIN_DNS_SEEDS:
        print(f"--- Querying seed: {seed} ---")
        ips = query_dns_seed(seed)
        if not ips:
            continue
        candidates.update(ips)
        print(f"-> {len(ips)} nodes retrieved from {seed}")

    print("\n=========================================")
    print(f"Total unique candidates discovered: {len(candidates)}")
    print("=========================================\n")
    print(f"Probing port {PORT} with version messages (no handshake)...")

    print("\n=========================================")
    print(f"Total candidates tested: {len(candidates)}")


if __name__ == "__main__":
    main()