#!/usr/bin/env python3
"""
Pi-hole Prometheus exporter
Queries Pi-hole's FTL database directly to get comprehensive metrics
"""

import os
import time
import requests
import subprocess
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from collections import defaultdict

PIHOLE_HOST = os.getenv("PIHOLE_HOSTNAME", "pihole")
PIHOLE_PORT = os.getenv("PIHOLE_PORT", "80")
PIHOLE_PASSWORD = os.getenv("PIHOLE_PASSWORD", "")
PIHOLE_PROTOCOL = os.getenv("PIHOLE_PROTOCOL", "http")
PIHOLE_CONTAINER = os.getenv("PIHOLE_CONTAINER", "pihole")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9617"))
USE_VOLUME_MOUNT = os.getenv("USE_VOLUME_MOUNT", "false").lower() == "true"
FTL_DB_PATH = "/etc/pihole/pihole-FTL.db"

metrics_cache = {}
per_client_metrics = {}
top_domains = []
top_clients = []
query_types = {}
upstream_servers = {}
top_permitted_domains = []
top_blocked_domains = []
cache_time = 0
CACHE_TTL = 30


def query_ftl_database(query):
    """Execute SQL query on Pi-hole FTL database"""
    try:
        if USE_VOLUME_MOUNT:
            # Direct database access via mounted volume
            import sqlite3
            conn = sqlite3.connect(FTL_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            # Convert Row objects to dicts
            return [dict(row) for row in rows]
        else:
            # Query the FTL database via docker exec
            cmd = [
                "docker", "exec", PIHOLE_CONTAINER,
                "sqlite3", "/etc/pihole/pihole-FTL.db",
                "-json", query
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse JSON output from sqlite3
                lines = [line for line in result.stdout.strip().split('\n') if line.strip()]
                if lines:
                    return [json.loads(line) for line in lines]
        return []
    except Exception as e:
        print(f"Error querying FTL database: {e}")
        import traceback
        traceback.print_exc()
        return []


def fetch_pihole_stats():
    """Fetch comprehensive stats from Pi-hole v6 API"""
    global metrics_cache, per_client_metrics, top_domains, top_clients, cache_time
    global query_types, upstream_servers, top_permitted_domains, top_blocked_domains

    try:
        # Pi-hole v6 API endpoint
        api_base = f"{PIHOLE_PROTOCOL}://{PIHOLE_HOST}:{PIHOLE_PORT}"
        
        # Get stats summary from Pi-hole v6 API
        try:
            resp = requests.get(f"{api_base}/api/stats/summary", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                queries = data.get("queries", {})
                clients_data = data.get("clients", {})
                gravity = data.get("gravity", {})
                
                # Extract metrics from v6 API response
                total_queries = queries.get("total", 0)
                blocked_queries = queries.get("blocked", 0)
                forwarded_queries = queries.get("forwarded", 0)
                cached_queries = queries.get("cached", 0)
                active_clients = clients_data.get("active", 0)
                total_clients = clients_data.get("total", 0)
                domains_blocked = gravity.get("domains_being_blocked", 0)
                
                metrics_cache = {
                    "dns_queries_total": float(total_queries),
                    "dns_blocked_total": float(blocked_queries),
                    "dns_forwarded_total": float(forwarded_queries),
                    "dns_cached_total": float(cached_queries),
                    "clients_total": float(total_clients),
                    "devices_total": float(total_clients),
                    "devices_active_24h": float(active_clients),
                    "dns_queries_24h": float(total_queries),
                    "dns_blocked_24h": float(blocked_queries),
                    "dns_forwarded_24h": float(forwarded_queries),
                    "dns_cached_24h": float(cached_queries),
                    "clients_24h": float(active_clients),
                    "gravity_domains": float(domains_blocked),
                }
                
                # Extract query types from v6 API
                query_types_data = queries.get("types", {})
                query_types = {}
                for qtype, count in query_types_data.items():
                    query_types[qtype] = float(count)
                
                print(f"Pi-hole v6 API: {total_queries} queries, {blocked_queries} blocked, {active_clients} clients")
            else:
                print(f"Pi-hole v6 API returned {resp.status_code}")
                metrics_cache = {
                    "dns_queries_total": 0.0,
                    "dns_blocked_total": 0.0,
                    "dns_forwarded_total": 0.0,
                    "dns_cached_total": 0.0,
                    "clients_total": 0.0,
                    "devices_total": 0.0,
                    "devices_active_24h": 0.0,
                    "dns_queries_24h": 0.0,
                    "dns_blocked_24h": 0.0,
                    "dns_forwarded_24h": 0.0,
                    "dns_cached_24h": 0.0,
                    "clients_24h": 0.0,
                    "gravity_domains": 0.0,
                }
        except Exception as e:
            print(f"Error fetching from Pi-hole v6 API: {e}")
            metrics_cache = {
                "dns_queries_total": 0.0,
                "dns_blocked_total": 0.0,
                "dns_forwarded_total": 0.0,
                "dns_cached_total": 0.0,
                "clients_total": 0.0,
                "devices_total": 0.0,
                "devices_active_24h": 0.0,
                "dns_queries_24h": 0.0,
                "dns_blocked_24h": 0.0,
                "dns_forwarded_24h": 0.0,
                "dns_cached_24h": 0.0,
                "clients_24h": 0.0,
                "gravity_domains": 0.0,
            }

        # Get top domains from v6 API
        try:
            resp = requests.get(f"{api_base}/api/stats/top_domains", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                top_domains = []
                top_permitted_domains = []
                # v6 API returns {"domains": [{"domain": "...", "count": N}, ...]}
                for item in data.get("domains", []):
                    domain = item.get("domain", "unknown")
                    count = item.get("count", 0)
                    top_domains.append({
                        "domain": domain,
                        "queries": float(count),
                        "blocked": 0.0,
                    })
                    top_permitted_domains.append({
                        "domain": domain,
                        "queries": float(count),
                    })
                print(f"Got {len(top_domains)} top domains")
        except Exception as e:
            print(f"Error fetching top domains: {e}")
            top_domains = []
            top_permitted_domains = []

        # Get blocked domains from queries API
        try:
            resp = requests.get(f"{api_base}/api/queries?length=500", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                blocked_counts = {}
                for q in data.get("queries", []):
                    status = q.get("status", "")
                    if "GRAVITY" in status or "DENY" in status or "BLOCK" in status:
                        domain = q.get("domain", "unknown")
                        blocked_counts[domain] = blocked_counts.get(domain, 0) + 1
                
                top_blocked_domains = []
                for domain, count in sorted(blocked_counts.items(), key=lambda x: -x[1])[:20]:
                    top_blocked_domains.append({
                        "domain": domain,
                        "queries": float(count),
                    })
                print(f"Got {len(top_blocked_domains)} blocked domains")
        except Exception as e:
            print(f"Error fetching blocked domains: {e}")
            top_blocked_domains = []

        # Get top clients from v6 API
        try:
            resp = requests.get(f"{api_base}/api/stats/top_clients", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                per_client_metrics = {}
                top_clients = []
                # v6 API returns {"clients": [{"ip": "...", "name": "...", "count": N}, ...]}
                for item in data.get("clients", []):
                    client_ip = item.get("ip", "unknown")
                    client_name = item.get("name", "") or client_ip
                    count = item.get("count", 0)
                    per_client_metrics[client_ip] = {
                        "queries": float(count),
                        "blocked": 0.0,
                        "cached": 0.0,
                        "forwarded": 0.0,
                    }
                    top_clients.append({
                        "mac": "",
                        "name": client_name,
                        "ip": client_ip,
                        "queries": float(count),
                    })
                print(f"Got {len(top_clients)} clients")
        except Exception as e:
            print(f"Error fetching top clients: {e}")
            per_client_metrics = {}
            top_clients = []

        # Get upstreams from v6 API
        try:
            resp = requests.get(f"{api_base}/api/stats/upstreams", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                upstream_servers = {}
                for upstream in data.get("upstreams", []):
                    name = upstream.get("name", upstream.get("ip", "unknown"))
                    count = upstream.get("count", 0)
                    upstream_servers[name] = float(count)
                print(f"Got {len(upstream_servers)} upstreams")
        except Exception as e:
            print(f"Error fetching upstreams: {e}")
            upstream_servers = {}

        cache_time = time.time()
        print(f"Fetched stats: {len(per_client_metrics)} clients, {len(top_domains)} domains")
        print(f"Query types: {len(query_types)}, Upstream servers: {len(upstream_servers)}")
        print(f"Metrics cache: queries_total={metrics_cache.get('dns_queries_total', 0)}, clients={metrics_cache.get('clients_total', 0)}")
        return True

    except Exception as e:
        print(f"Error fetching Pi-hole stats: {e}")
        import traceback
        traceback.print_exc()
        return False
def escape_label_value(value):
    """Escape label values for Prometheus format"""
    if value is None:
        return "unknown"
    value = str(value)
    # Replace problematic characters
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    return value


def format_metrics():
    """Format metrics in Prometheus text format"""
    lines = []

    # Overall statistics
    lines.extend([
        "# HELP pihole_dns_queries_total Total DNS queries",
        "# TYPE pihole_dns_queries_total counter",
        f"pihole_dns_queries_total {metrics_cache.get('dns_queries_total', 0)}",
        "",
        "# HELP pihole_dns_blocked_total Total blocked DNS queries",
        "# TYPE pihole_dns_blocked_total counter",
        f"pihole_dns_blocked_total {metrics_cache.get('dns_blocked_total', 0)}",
        "",
        "# HELP pihole_dns_forwarded_total Total forwarded DNS queries",
        "# TYPE pihole_dns_forwarded_total counter",
        f"pihole_dns_forwarded_total {metrics_cache.get('dns_forwarded_total', 0)}",
        "",
        "# HELP pihole_dns_cached_total Total cached DNS queries",
        "# TYPE pihole_dns_cached_total counter",
        f"pihole_dns_cached_total {metrics_cache.get('dns_cached_total', 0)}",
        "",
        "# HELP pihole_clients_total Total unique clients",
        "# TYPE pihole_clients_total gauge",
        f"pihole_clients_total {metrics_cache.get('clients_total', 0)}",
        "",
        "# HELP pihole_dns_queries_24h DNS queries in last 24 hours",
        "# TYPE pihole_dns_queries_24h gauge",
        f"pihole_dns_queries_24h {metrics_cache.get('dns_queries_24h', 0)}",
        "",
        "# HELP pihole_dns_blocked_24h Blocked queries in last 24 hours",
        "# TYPE pihole_dns_blocked_24h gauge",
        f"pihole_dns_blocked_24h {metrics_cache.get('dns_blocked_24h', 0)}",
        "",
        "# HELP pihole_dns_forwarded_24h Forwarded queries in last 24 hours",
        "# TYPE pihole_dns_forwarded_24h gauge",
        f"pihole_dns_forwarded_24h {metrics_cache.get('dns_forwarded_24h', 0)}",
        "",
        "# HELP pihole_dns_cached_24h Cached queries in last 24 hours",
        "# TYPE pihole_dns_cached_24h gauge",
        f"pihole_dns_cached_24h {metrics_cache.get('dns_cached_24h', 0)}",
        "",
        "# HELP pihole_clients_24h Unique clients in last 24 hours",
        "# TYPE pihole_clients_24h gauge",
        f"pihole_clients_24h {metrics_cache.get('clients_24h', 0)}",
        "",
        "# HELP pihole_devices_total Total network devices (by MAC address)",
        "# TYPE pihole_devices_total gauge",
        f"pihole_devices_total {metrics_cache.get('devices_total', 0)}",
        "",
        "# HELP pihole_devices_active_24h Active network devices in last 24 hours",
        "# TYPE pihole_devices_active_24h gauge",
        f"pihole_devices_active_24h {metrics_cache.get('devices_active_24h', 0)}",
        "",
        "# HELP pihole_gravity_domains Total domains in gravity blocklist",
        "# TYPE pihole_gravity_domains gauge",
        f"pihole_gravity_domains {metrics_cache.get('gravity_domains', 0)}",
        "",
    ])

    # Per-client metrics
    lines.append("# HELP pihole_client_queries_total DNS queries per client (24h)")
    lines.append("# TYPE pihole_client_queries_total gauge")
    for client, stats in per_client_metrics.items():
        client_escaped = escape_label_value(client)
        lines.append(f'pihole_client_queries_total{{client="{client_escaped}"}} {stats["queries"]}')

    lines.append("")
    lines.append("# HELP pihole_client_blocked_total Blocked queries per client (24h)")
    lines.append("# TYPE pihole_client_blocked_total gauge")
    for client, stats in per_client_metrics.items():
        client_escaped = escape_label_value(client)
        lines.append(f'pihole_client_blocked_total{{client="{client_escaped}"}} {stats["blocked"]}')

    lines.append("")
    lines.append("# HELP pihole_client_cached_total Cached queries per client (24h)")
    lines.append("# TYPE pihole_client_cached_total gauge")
    for client, stats in per_client_metrics.items():
        client_escaped = escape_label_value(client)
        lines.append(f'pihole_client_cached_total{{client="{client_escaped}"}} {stats["cached"]}')

    lines.append("")
    lines.append("# HELP pihole_client_forwarded_total Forwarded queries per client (24h)")
    lines.append("# TYPE pihole_client_forwarded_total gauge")
    for client, stats in per_client_metrics.items():
        client_escaped = escape_label_value(client)
        lines.append(f'pihole_client_forwarded_total{{client="{client_escaped}"}} {stats["forwarded"]}')

    # Top domains
    lines.append("")
    lines.append("# HELP pihole_domain_queries_total DNS queries per domain (24h)")
    lines.append("# TYPE pihole_domain_queries_total gauge")
    for domain_info in top_domains[:20]:  # Limit to top 20 for performance
        domain = escape_label_value(domain_info["domain"])
        lines.append(f'pihole_domain_queries_total{{domain="{domain}"}} {domain_info["queries"]}')

    lines.append("")
    lines.append("# HELP pihole_domain_blocked_total Blocked queries per domain (24h)")
    lines.append("# TYPE pihole_domain_blocked_total gauge")
    for domain_info in top_domains[:20]:
        domain = escape_label_value(domain_info["domain"])
        lines.append(f'pihole_domain_blocked_total{{domain="{domain}"}} {domain_info["blocked"]}')

    # Client network info
    lines.append("")
    lines.append("# HELP pihole_network_client_queries_total Total queries per network client")
    lines.append("# TYPE pihole_network_client_queries_total gauge")
    for client_info in top_clients:
        mac = escape_label_value(client_info["mac"])
        name = escape_label_value(client_info["name"])
        ip = escape_label_value(client_info["ip"])
        lines.append(f'pihole_network_client_queries_total{{mac="{mac}",name="{name}",ip="{ip}"}} {client_info["queries"]}')

    # Query types
    lines.append("")
    lines.append("# HELP pihole_query_type_total DNS queries by type (24h)")
    lines.append("# TYPE pihole_query_type_total gauge")
    for qtype, count in query_types.items():
        qtype_escaped = escape_label_value(qtype)
        lines.append(f'pihole_query_type_total{{type="{qtype_escaped}"}} {count}')

    # Upstream servers
    lines.append("")
    lines.append("# HELP pihole_upstream_queries_total Queries forwarded to upstream servers (24h)")
    lines.append("# TYPE pihole_upstream_queries_total gauge")
    for server, count in upstream_servers.items():
        server_escaped = escape_label_value(server)
        lines.append(f'pihole_upstream_queries_total{{server="{server_escaped}"}} {count}')

    # Top permitted domains
    lines.append("")
    lines.append("# HELP pihole_top_permitted_domains_total Top permitted domains (24h)")
    lines.append("# TYPE pihole_top_permitted_domains_total gauge")
    for domain_info in top_permitted_domains[:20]:
        domain = escape_label_value(domain_info["domain"])
        lines.append(f'pihole_top_permitted_domains_total{{domain="{domain}"}} {domain_info["queries"]}')

    # Top blocked domains
    lines.append("")
    lines.append("# HELP pihole_top_blocked_domains_total Top blocked domains (24h)")
    lines.append("# TYPE pihole_top_blocked_domains_total gauge")
    for domain_info in top_blocked_domains[:20]:
        domain = escape_label_value(domain_info["domain"])
        lines.append(f'pihole_top_blocked_domains_total{{domain="{domain}"}} {domain_info["queries"]}')

    return "\n".join(lines)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint"""

    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(format_metrics().encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def background_fetcher():
    """Background thread to periodically fetch Pi-hole stats"""
    while True:
        fetch_pihole_stats()
        time.sleep(CACHE_TTL)


if __name__ == "__main__":
    print(f"Starting Pi-hole exporter on port {EXPORTER_PORT}")
    print(f"Pi-hole container: {PIHOLE_CONTAINER}")
    print(f"Pi-hole host: {PIHOLE_HOST}:{PIHOLE_PORT}")

    # Initial fetch
    fetch_pihole_stats()

    # Start background fetcher thread
    fetcher = Thread(target=background_fetcher, daemon=True)
    fetcher.start()

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    print(f"Listening on http://0.0.0.0:{EXPORTER_PORT}/metrics")
    server.serve_forever()
