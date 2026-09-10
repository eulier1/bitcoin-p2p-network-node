import socket

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

def query_dns_seed(seed_domain):
    """
    Queries a DNS seed and returns a set of IP addresses.
    Mimics the behavior of running 'dig <seed_domain>'.
    """
    node_ips = set()
    try:
        addr_info = socket.getaddrinfo(seed_domain, 8333, 0, socket.SOCK_STREAM)
        
        for item in addr_info:
            ip = item[4][0]
            node_ips.add(ip)
            
    except socket.gaierror as e:
        print(f"[!] DNS resolution failed for {seed_domain}: {e}")
    except Exception as e:
        print(f"[!] An error occurred querying {seed_domain}: {e}")
        
    return node_ips

def main():
    print("Starting Bitcoin DNS Seed Discovery...\n")
    
    total_unique_nodes = set()

    for seed in BITCOIN_DNS_SEEDS:
        print(f"--- Querying seed: {seed} ---")
        ips = query_dns_seed(seed)
        
        if not ips:
            continue
            
        for ip in ips:
            print(f"Node found: {ip}")
            total_unique_nodes.add(ip)
            
        print(f"-> {len(ips)} nodes retrieved from {seed}\n")

    print("=========================================")
    print(f"Total unique Bitcoin nodes discovered: {len(total_unique_nodes)}")

if __name__ == "__main__":
    main()