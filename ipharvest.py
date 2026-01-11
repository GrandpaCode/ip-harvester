import requests
import socket
import sys
import os
import json
from datetime import datetime

# [get_subdomains and enumerate_ips functions remain the same]

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 harvest.py <domain1> <domain2> ...")
        sys.exit(1)

    domains_to_process = sys.argv[1:]
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db_file = "master_infrastructure_db.json"
    MAX_HISTORY = 2 
    
    # Initialize Master Structure if it doesn't exist
    db = {
        "metadata": {"last_id": 0, "updated": timestamp},
        "domains": {} # High-level grouping by Root Domain
    }

    if os.path.exists(db_file):
        with open(db_file, 'r') as f:
            try:
                db = json.load(f)
            except json.JSONDecodeError:
                pass

    current_id = db["metadata"].get("last_id", 0)

    for root_domain in domains_to_process:
        root_domain = root_domain.lower()
        print(f"[*] Processing: {root_domain}")
        
        # Ensure the domain exists in our structure
        if root_domain not in db["domains"]:
            db["domains"][root_domain] = {"index": {}, "history": {}}

        subdomains = get_subdomains(root_domain)
        
        for sub in subdomains:
            new_ips = enumerate_ips(sub)
            if not new_ips:
                continue

            previous_entry = db["domains"][root_domain]["index"].get(sub, {})
            previous_ips = previous_entry.get("ips", [])

            # (N, N-1) Change Detection
            if set(new_ips) != set(previous_ips):
                current_id += 1
                record = {
                    "id": current_id,
                    "subdomain": sub,
                    "timestamp": timestamp,
                    "ips": new_ips
                }

                # Update current state
                db["domains"][root_domain]["index"][sub] = record

                # Update sliding window history
                if sub not in db["domains"][root_domain]["history"]:
                    db["domains"][root_domain]["history"][sub] = []
                
                db["domains"][root_domain]["history"][sub].append(record)
                
                # Enforce N, N-1
                if len(db["domains"][root_domain]["history"][sub]) > MAX_HISTORY:
                    db["domains"][root_domain]["history"][sub] = db["domains"][root_domain]["history"][sub][-MAX_HISTORY:]
                
                print(f"  [+] Change: {sub} (New ID: {current_id})")

    db["metadata"]["last_id"] = current_id
    db["metadata"]["updated"] = timestamp

    # Save the master file
    with open(db_file + ".tmp", 'w') as f:
        json.dump(db, f, indent=4)
    os.replace(db_file + ".tmp", db_file)

    print(f"[*] Master DB updated. Current Global ID: {current_id}")

if __name__ == "__main__":
    main()
