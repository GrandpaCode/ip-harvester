import requests
import socket
import sys
import os
import json
from datetime import datetime

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
                clean_name = name.replace("*.", "").strip().lower()
                if clean_name.endswith(target_domain):
                    found_domains.add(clean_name)
        return sorted(list(found_domains))
    except Exception as e:
        print(f"API Error: {e}", file=sys.stderr)
        return []

def enumerate_ips(domain):
    """Enumerate all IPv4 addresses for a domain."""
    ips = set()
    try:
        results = socket.getaddrinfo(domain, None, socket.AF_INET)
        for res in results:
            ips.add(res[4][0])
    except (socket.gaierror, socket.timeout):
        pass 
    return sorted(list(ips))

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 harvest.py <domain>")
        sys.exit(1)

    root_domain = sys.argv[1].lower()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    output_file = f"{root_domain}_db.json"
    
    # Slotted history for (N, N-1) support
    MAX_HISTORY = 2 
    
    # Initialize or Load Database
    db = {
        "metadata": {"last_id": 0, "root_domain": root_domain, "updated": timestamp},
        "index": {}, 
        "history": {} 
    }

    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            try:
                db = json.load(f)
            except json.JSONDecodeError:
                pass

    print(f"[*] Starting harvest for {root_domain}...")
    subdomains = get_subdomains(root_domain)
    current_id = db["metadata"].get("last_id", 0)

    for sub in subdomains:
        new_ips = enumerate_ips(sub)
        if not new_ips:
            continue

        # Get existing state from Index
        previous_entry = db["index"].get(sub, {})
        previous_ips = previous_entry.get("ips", [])

        # Only record if the IP pool has actually changed
        if set(new_ips) != set(previous_ips):
            current_id += 1
            record = {
                "id": current_id,
                "subdomain": sub,
                "timestamp": timestamp,
                "ips": new_ips
            }

            # Update Index (Current State)
            db["index"][sub] = record

            # Update History (Sliding Window for N, N-1)
            if sub not in db["history"]:
                db["history"][sub] = []
            
            db["history"][sub].append(record)
            
            # Enforce (N, N-1) bloat control
            if len(db["history"][sub]) > MAX_HISTORY:
                db["history"][sub] = db["history"][sub][-MAX_HISTORY:]
            
            print(f" [+] Change detected: {sub} (ID: {current_id})")

    # Update Global Metadata
    db["metadata"]["last_id"] = current_id
    db["metadata"]["updated"] = timestamp

    # Atomic Save
    with open(output_file + ".tmp", 'w') as f:
        json.dump(db, f, indent=4)
    os.replace(output_file + ".tmp", output_file)

    print(f"[*] Update complete. Database saved to {output_file}")

if __name__ == "__main__":
    main()
