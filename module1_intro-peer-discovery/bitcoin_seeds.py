import socket
import concurrent.futures

BITCOIN_DNS_SEEDS = [
    "seed.bitcoin.sipa.be",          # Pieter Wuille
    "dnsseed.bluematt.me",           # Matt Corallo
    "dnsseed.bitcoin.dashjr.org",    # Luke Dashjr
    "seed.bitcoinstats.com",         # Christian Decker
    "seed.bitcoin.jonasschnelli.ch", # Jonas Schnelli
    "seed.btc.petertodd.org",        # Peter Todd
    "seed.bitcoin.sprovoost.nl",     # Sjors Provoost
    "dnsseed.emzy.de",               # Stephan Wegner
    "seed.bitcoin.wiz.biz"           # Jason Maurice
]

PORT = 8333
TIMEOUT = 3.0
OUTPUT_FILE = "active_bitcoin_nodes.txt"

def query_dns_seed(seed_domain):
    """
    Queries a DNS seed and returns a set of IP addresses.
    Mimics the behavior of running 'dig <seed_domain>'.
    """
    node_ips = set()
    try:
        addr_info = socket.getaddrinfo(seed_domain, PORT, 0, socket.SOCK_STREAM)
        for item in addr_info:
            ip = item[4][0]
            node_ips.add(ip)
    except socket.gaierror as e:
        print(f"[!] DNS resolution failed for {seed_domain}: {e}")
    except Exception as e:
        print(f"[!] An error occurred querying {seed_domain}: {e}")
    return node_ips

def check_tcp_connection(ip):
    """
    Attempts to establish a TCP connection to the node.
    Returns the IP if successful, None otherwise.
    """
    try:
        # socket.create_connection handles both IPv4 and IPv6 transparently
        with socket.create_connection((ip, PORT), timeout=TIMEOUT):
            return ip
    except (socket.timeout, socket.error, ConnectionRefusedError):
        return None

def save_to_file(active_nodes, filename):
    """
    Persists the list of active IPs to a local text file.
    """
    try:
        with open(filename, 'w') as f:
            for node in sorted(active_nodes):
                f.write(f"{node}\n")
        print(f"\n[+] Successfully saved {len(active_nodes)} active nodes to '{filename}'")
    except IOError as e:
        print(f"\n[!] Failed to save to file: {e}")

def main():
    print("Starting Bitcoin DNS Seed Discovery...\n")
    total_unique_nodes = set()

    # 1. Discover Candidates via DNS
    for seed in BITCOIN_DNS_SEEDS:
        print(f"--- Querying seed: {seed} ---")
        ips = query_dns_seed(seed)
        if not ips:
            continue
        total_unique_nodes.update(ips)
        print(f"-> {len(ips)} nodes retrieved from {seed}")

    print("\n=========================================")
    print(f"Total unique candidates discovered: {len(total_unique_nodes)}")
    print("=========================================\n")
    print(f"Testing TCP connections on port {PORT} (this may take a moment)...")

    # 2. Verify Candidates via TCP (using threading for speed)
    active_nodes = set()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        # Map the check_tcp_connection function to all unique IPs
        future_to_ip = {executor.submit(check_tcp_connection, ip): ip for ip in total_unique_nodes}
        
        for future in concurrent.futures.as_completed(future_to_ip):
            result = future.result()
            if result:
                print(f"[+] Active node found: {result}")
                active_nodes.add(result)

    print("\n=========================================")
    print(f"Total candidates tested: {len(total_unique_nodes)}")
    print(f"Total active TCP nodes: {len(active_nodes)}")
    
    # 3. Persist the Results
    if active_nodes:
        save_to_file(active_nodes, OUTPUT_FILE)
    else:
        print("No active nodes were found to persist.")

if __name__ == "__main__":
    main()