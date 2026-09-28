import socket
import struct
import time
import hashlib

# Protocol Constants
MAGIC = bytes.fromhex("f9beb4d9")
TARGET_IP = "127.0.0.1"
TARGET_PORT = 8333

def double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def pack_message(command: str, payload: bytes = b"") -> bytes:
    cmd = command.encode("ascii").ljust(12, b"\x00")
    return MAGIC + cmd + struct.pack("<I", len(payload)) + double_sha256(payload)[:4] + payload

def encode_varint(n: int) -> bytes:
    if n < 0xFD: return struct.pack("<B", n)
    if n <= 0xFFFF: return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF: return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)

def build_client_version():
    """Builds a version payload matching the Satoshi client in the image."""
    services = 0xc09  # NETWORK, WITNESS, NETWORK_LIMITED, P2P_V2
    timestamp = int(time.time())
    addr_recv = b"\x00" * 26
    addr_from = b"\x00" * 26
    nonce = 0x1933cc4f7e470cc1
    user_agent = b"/Satoshi:30.2.0/"
    
    payload = (
        struct.pack("<iQq", 70016, services, timestamp) +
        addr_recv + addr_from + struct.pack("<Q", nonce) +
        (encode_varint(len(user_agent)) + user_agent) +
        struct.pack("<i", 131) + struct.pack("<?", True)
    )
    return pack_message("version", payload)

def run_test():
    print(f"Connecting to node listener at {TARGET_IP}:{TARGET_PORT}...")
    
    try:
        with socket.create_connection((TARGET_IP, TARGET_PORT), timeout=5) as sock:
            print("[+] Connected. Sending handshake sequence...")
            
            # 1. Send our version message
            sock.sendall(build_client_version())
            time.sleep(0.5) # Give the server time to process and log
            
            # 2. Send wtxidrelay (0 bytes)
            sock.sendall(pack_message("wtxidrelay"))
            time.sleep(0.2)
            
            # 3. Send sendaddrv2 (0 bytes)
            sock.sendall(pack_message("sendaddrv2"))
            time.sleep(0.2)
            
            # 4. Send verack (0 bytes)
            sock.sendall(pack_message("verack"))
            time.sleep(0.5)
            
            # 5. Send getaddr (0 bytes)
            sock.sendall(pack_message("getaddr"))
            time.sleep(0.2)
            
            # 6. Send sendcmpct (9 bytes: 1 byte bool + 8 byte uint64 version)
            cmpct_payload = struct.pack("<?Q", True, 2)
            sock.sendall(pack_message("sendcmpct", cmpct_payload))
            time.sleep(0.5)
            
            print("[+] Test sequence complete. Check the listener's terminal output!")
            
    except ConnectionRefusedError:
        print("[-] Connection refused. Ensure the listener script is running first.")
    except Exception as e:
        print(f"[-] Error during test: {e}")

if __name__ == "__main__":
    run_test()