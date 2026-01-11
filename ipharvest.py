import requests
import socket
import sys
import os
import json
from datetime import datetime

def check_domain_alive(domain):
    """Sanity check: Does the root domain resolve?"""
    try:
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False

def get_subdomains(target_domain):
    """Fetch subdomains from Certspotter API."""
    url = f"https://api.certspotter.com/v1/issuances?domain={target_domain}&include_subdomains=true&expand=dns_names"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
        found_domains = set()
        for entry in data:
            for name in entry.get('dns_names', []):
                # Clean wildcard entries and normalize to lowercase
                clean_name = name.replace("*.", "").strip().lower()
                if clean_name.endswith(target_domain):
                    found_domains.add(clean_name)
        return sorted(list(found_domains))
    except Exception as e:
        print(f"  [!] API Error for {target_domain}: {e}", file=sys.stderr)
        return []

def enumerate_ips(domain):
    """Enumerate all unique IPv4 addresses for a domain."""
    ips = set()
    try:
        # AF_INET forces IPv4
        results = socket.getaddrinfo(domain, None, socket.AF_INET)
        for res in results:
            ips.add(res[4][0])
    except (socket.gaierror, socket.timeout):
        pass 
    return sorted(list(ips))

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ipharvest.py <domain1> <domain2> ...")
        sys.exit(1)

    domains_to_process = sys.argv[1:]
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db_file = "master_infrastructure_db.json"
    MAX_HISTORY = 2 # Supports the (N, N-1) theory
    
    # Load or Initialize Master DB
    db = {"metadata": {"last_id": 0, "updated": timestamp}, "domains": {}}
    if os.path.exists(db_file):
        with open(db_file, 'r') as f:
            try:
                db = json.load(f)
            except json.JSONDecodeError:
                print("[!] Existing DB corrupt, starting fresh.")

    current_id = db["metadata"].get("last_id", 0)

    for root_domain in domains_to_process:
        root_domain = root_domain.lower()
        print(f"[*] Processing: {root_domain}")
        
        # Step 1: Sanity Check
        if not check_domain_alive(root_domain):
            print(f"  [!] Skipping {root_domain}: Root domain does not resolve.")
            continue

        # Step 2: Initialize domain entry if new
        if root_domain not in db["domains"]:
            db["domains"][root_domain] = {"index": {}, "history": {}}

        # Step 3: Harvest and Enumerate
        subdomains = get_subdomains(root_domain)
        for sub in subdomains:
            new_ips = enumerate_ips(sub)
            if not new_ips:
                continue

            previous_entry = db["domains"][root_domain]["index"].get(sub, {})
            previous_ips = previous_entry.get("ips", [])

            # Step 4: (N, N-1) Change Detection
            if set(new_ips) != set(previous_ips):
                current_id += 1
                record = {
                    "id": current_id,
                    "subdomain": sub,
                    "timestamp": timestamp,
                    "ips": new_ips
                }

                # Update Current State
                db["domains"][root_domain]["index"][sub] = record

                # Update Capped History Window
                if sub not in db["domains"][root_domain]["history"]:
                    db["domains"][root_domain]["history"][sub] = []
                
                db["domains"][root_domain]["history"][sub].append(record)
                
                if len(db["domains"][root_domain]["history"][sub]) > MAX_HISTORY:
                    db["domains"][root_domain]["history"][sub] = db["domains"][root_domain]["history"][sub][-MAX_HISTORY:]
                
                print(f"  [+] Change: {sub} (New ID: {current_id})")

    # Finalize Metadata
    db["metadata"]["last_id"] = current_id
    db["metadata"]["updated"] = timestamp

    # Atomic Save
    with open(db_file + ".tmp", 'w') as f:
        json.dump(db, f, indent=4)
    os.replace(db_file + ".tmp", db_file)

    print(f"[*] Master DB updated. Current Global ID: {current_id}")

if __name__ == "__main__":
    main()
