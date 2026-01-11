import requests
import socket
import sys
import os
import csv
from datetime import datetime

def get_subdomains(target_domain):
    """Fetch subdomains using the Certspotter API."""
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
    """Returns a list of all unique IPs (v4) associated with a domain."""
    ips = set()
    try:
        # AF_INET restricts to IPv4; change to AF_UNSPEC for both v4 and v6
        results = socket.getaddrinfo(domain, None, socket.AF_INET)
        for res in results:
            ips.add(res[4][0])
    except (socket.gaierror, socket.timeout):
        pass 
    return list(ips)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 harvest.py <domain>")
        sys.exit(1)

    root_domain = sys.argv[1].lower()
    timestamp = datetime.now().strftime('%m/%d/%Y')
    final_output = f"ipharvest.csv"

    print(f"Step 1: Discovering subdomains for {root_domain}...")
    subdomains = get_subdomains(root_domain)

    if subdomains:
        print(f"Step 2: Enumerating IPs for {len(subdomains)} subdomains...")
        file_exists = os.path.isfile(final_output)

        with open(final_output, "a", newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            if not file_exists:
                writer.writerow(["Date", "RootDomain", "Subdomain", "IP"])
            
            for sub in subdomains:
                ip_list = enumerate_ips(sub)
                
                if ip_list:
                    for ip in ip_list:
                        writer.writerow([timestamp, root_domain, sub, ip])
                else:
                    # Log as unresolved so you know the domain was found but didn't respond
                    writer.writerow([timestamp, root_domain, sub, "0.0.0.0"])
        
        print(f"Success: History updated at {final_output}")
    else:
        print("Discovery failed or returned no results.")

if __name__ == "__main__":
    main()
