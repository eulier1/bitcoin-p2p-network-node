import concurrent.futures
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
# version / verack
# ---------------------------------------------------------------------------
def build_version_payload(remote_ip: str, remote_port: int,
                          start_height: int = 0, relay: bool = False) -> bytes:
    """
    version payload layout:
      int32   version
      uint64  services
      int64   timestamp
      net_addr addr_recv   (26)
      net_addr addr_from   (26)
      uint64  nonce
      var_str user_agent
      int32   start_height
      bool    relay        (BIP 37, protocol >= 70001)
    """
    return (
        struct.pack("<iQq", PROTOCOL_VERSION, 0, int(time.time()))
        + encode_net_addr(remote_ip, remote_port)
        + encode_net_addr("0.0.0.0", 0)
        + os.urandom(8)
        + encode_varstr(USER_AGENT)
        + struct.pack("<i", start_height)
        + struct.pack("<?", relay)
    )


def build_version_message(remote_ip: str, remote_port: int) -> bytes:
    return pack_message("version", build_version_payload(remote_ip, remote_port))


def build_verack_message() -> bytes:
    """verack has an empty payload, so it is just a header."""
    return pack_message("verack")


def parse_version_payload(payload: bytes) -> dict:
    if len(payload) < 85:  # fixed fields (80) + 1-byte empty var_str + height(4)
        raise ProtocolError("version payload too short")
    version, services, timestamp = struct.unpack_from("<iQq", payload, 0)
    # skip addr_recv (26) + addr_from (26)
    (nonce,) = struct.unpack_from("<Q", payload, 72)
    user_agent, offset = decode_varstr(payload, 80)
    (start_height,) = struct.unpack_from("<i", payload, offset)
    return {
        "version": version,
        "services": services,
        "timestamp": timestamp,
        "nonce": nonce,
        "user_agent": user_agent.decode("utf-8", errors="replace"),
        "start_height": start_height,
    }


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


def probe_node(ip, port=PORT):
    """
    Connect, send our `version`, and read what the node sends back.

    We deliberately do NOT complete the handshake: we never send `verack`,
    so the node will eventually drop us. Returns a dict describing the node
    if it answered with a valid `version` message, otherwise None.
    """
    info = None
    got_verack = False
    try:
        with socket.create_connection((ip, port), timeout=TIMEOUT) as sock:
            sock.settimeout(TIMEOUT)
            sock.sendall(build_version_message(ip, port))
            for _ in range(MAX_MESSAGES):
                command, payload = read_message(sock)
                if command == "version":
                    info = parse_version_payload(payload)
                elif command == "verack":
                    got_verack = True
                # anything else (sendcmpct, ping, ...) is ignored
                if info and got_verack:
                    break
    except (OSError, ProtocolError, struct.error, IndexError):
        pass  # timeouts, resets, garbage: keep whatever we already parsed

    if info is None:
        return None
    info["ip"] = ip
    info["verack"] = got_verack
    return info


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

    verified = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for result in executor.map(probe_node, candidates):
            if result:
                print(f"[+] {result['ip']}  v{result['version']}  "
                      f"height={result['start_height']}  {result['user_agent']}  "
                      f"verack={result['verack']}")
                verified.append(result)

    print("\n=========================================")
    print(f"Total candidates tested: {len(candidates)}")
    print(f"Nodes that answered with a valid version: {len(verified)}")

    if verified:
        save_to_file(verified, OUTPUT_FILE)
    else:
        print("No verified nodes were found to persist.")


if __name__ == "__main__":
    main()