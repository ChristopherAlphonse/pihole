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
    """Fetch comprehensive stats from Pi-hole FTL database"""
    global metrics_cache, per_client_metrics, top_domains, top_clients, cache_time
    global query_types, upstream_servers, top_permitted_domains, top_blocked_domains

    try:
        # Get overall statistics
        stats_query = """
        SELECT
            (SELECT COUNT(*) FROM queries WHERE timestamp > strftime('%s', 'now', '-24 hours')) as queries_24h,
            (SELECT COUNT(*) FROM queries WHERE status = 1 AND timestamp > strftime('%s', 'now', '-24 hours')) as blocked_24h,
            (SELECT COUNT(*) FROM queries WHERE status = 2 AND timestamp > strftime('%s', 'now', '-24 hours')) as cached_24h,
            (SELECT COUNT(*) FROM queries WHERE status = 3 AND timestamp > strftime('%s', 'now', '-24 hours')) as forwarded_24h,
            (SELECT COUNT(DISTINCT client) FROM queries WHERE timestamp > strftime('%s', 'now', '-24 hours')) as unique_clients_24h,
            (SELECT COUNT(*) FROM queries) as queries_total,
            (SELECT COUNT(*) FROM queries WHERE status = 1) as blocked_total,
            (SELECT COUNT(*) FROM queries WHERE status = 2) as cached_total,
            (SELECT COUNT(*) FROM queries WHERE status = 3) as forwarded_total,
            (SELECT COUNT(DISTINCT client) FROM queries) as unique_clients_total,
            (SELECT COUNT(*) FROM network WHERE hwaddr IS NOT NULL AND hwaddr != '') as devices_total,
            (SELECT COUNT(*) FROM network WHERE hwaddr IS NOT NULL AND hwaddr != '' AND lastQuery > strftime('%s', 'now', '-24 hours')) as devices_active_24h
        """

        stats_result = query_ftl_database(stats_query)
        if stats_result:
            stats = stats_result[0]
            metrics_cache = {
                "dns_queries_total": float(stats.get("queries_total", 0)),
                "dns_blocked_total": float(stats.get("blocked_total", 0)),
                "dns_forwarded_total": float(stats.get("forwarded_total", 0)),
                "dns_cached_total": float(stats.get("cached_total", 0)),
                "clients_total": float(stats.get("unique_clients_total", 0)),
                "devices_total": float(stats.get("devices_total", 0)),
                "devices_active_24h": float(stats.get("devices_active_24h", 0)),
                "dns_queries_24h": float(stats.get("queries_24h", 0)),
                "dns_blocked_24h": float(stats.get("blocked_24h", 0)),
                "dns_forwarded_24h": float(stats.get("forwarded_24h", 0)),
                "dns_cached_24h": float(stats.get("cached_24h", 0)),
                "clients_24h": float(stats.get("unique_clients_24h", 0)),
            }
        else:
            # Fallback: try Pi-hole HTTP API endpoints. Newer Pi-hole versions
            # prefer Bearer token in Authorization header; older APIs accept an
            # auth/password query parameter. Try several endpoints and parse
            # JSON responses for common keys.
            tried = []
            endpoints = [
                f"{PIHOLE_PROTOCOL}://{PIHOLE_HOST}:{PIHOLE_PORT}/api/summary",
                f"{PIHOLE_PROTOCOL}://{PIHOLE_HOST}:{PIHOLE_PORT}/api",
                f"{PIHOLE_PROTOCOL}://{PIHOLE_HOST}:{PIHOLE_PORT}/admin/api.php?summaryRaw",
                f"{PIHOLE_PROTOCOL}://{PIHOLE_HOST}:{PIHOLE_PORT}/admin/api.php?summary",
                f"{PIHOLE_PROTOCOL}://{PIHOLE_HOST}:{PIHOLE_PORT}/admin/api.php",
            ]

            headers = {}
            if PIHOLE_PASSWORD:
                # Try using the provided password/token as a Bearer token first
                headers["Authorization"] = f"Bearer {PIHOLE_PASSWORD}"

            success_api = False
            last_err = None

            for api_url in endpoints:
                try:
                    params = {}
                    # For legacy admin PHP endpoint some installs expect auth param
                    if "admin/api.php" in api_url and "summary" in api_url and "Authorization" not in headers:
                        params = {"auth": PIHOLE_PASSWORD} if PIHOLE_PASSWORD else {}

                    tried.append(api_url)
                    resp = requests.get(api_url, headers=headers, params=params, timeout=8)
                    if resp.status_code != 200:
                        last_err = f"{api_url} returned {resp.status_code}"
                        continue

                    try:
                        data = resp.json()
                    except Exception:
                        last_err = f"{api_url} returned non-JSON"
                        continue

                    # Map known fields to exporter metrics
                    dns_queries = data.get("dns_queries_today") or data.get("queries") or data.get("dns_queries_total")
                    ads_blocked = data.get("ads_blocked_today") or data.get("ads_blocked_total") or data.get("dns_blocked_total")
                    forwarded = data.get("queries_forwarded") or data.get("forwarded")
                    cached = data.get("queries_cached") or data.get("cached")
                    clients = data.get("unique_clients") or data.get("clients")

                    # If the response is nested (summary: {...}) try to pull out
                    if not any([dns_queries, ads_blocked, clients]):
                        # try nested dicts
                        for v in data.values():
                            if isinstance(v, dict):
                                dns_queries = dns_queries or v.get("dns_queries_today")
                                ads_blocked = ads_blocked or v.get("ads_blocked_today")
                                clients = clients or v.get("unique_clients")

                    if any([dns_queries, ads_blocked, clients]):
                        metrics_cache = {
                            "dns_queries_total": float(dns_queries or 0),
                            "dns_blocked_total": float(ads_blocked or 0),
                            "dns_forwarded_total": float(forwarded or 0),
                            "dns_cached_total": float(cached or 0),
                            "clients_total": float(clients or 0),
                            "devices_total": 0.0,  # Not available via API
                            "devices_active_24h": 0.0,  # Not available via API
                            "dns_queries_24h": float(dns_queries or 0),
                            "dns_blocked_24h": float(ads_blocked or 0),
                            "dns_forwarded_24h": float(forwarded or 0),
                            "dns_cached_24h": float(cached or 0),
                            "clients_24h": float(clients or 0),
                        }
                        success_api = True
                        break

                except Exception as api_error:
                    last_err = str(api_error)
                    continue

            if not success_api:
                print(f"API fallback failed (tried: {tried}, last error: {last_err})")
                # Use zeros if all methods fail
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
                }

        # Get per-client statistics (last 24 hours)
        client_query = """
        SELECT
            client,
            COUNT(*) as queries,
            SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as blocked,
            SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) as cached,
            SUM(CASE WHEN status = 3 THEN 1 ELSE 0 END) as forwarded
        FROM queries
        WHERE timestamp > strftime('%s', 'now', '-24 hours')
        GROUP BY client
        ORDER BY queries DESC
        LIMIT 50
        """

        client_results = query_ftl_database(client_query)
        per_client_metrics = {}
        for row in client_results:
            client = row.get("client", "unknown")
            per_client_metrics[client] = {
                "queries": float(row.get("queries", 0)),
                "blocked": float(row.get("blocked", 0)),
                "cached": float(row.get("cached", 0)),
                "forwarded": float(row.get("forwarded", 0)),
            }

        # Get top domains (last 24 hours)
        domain_query = """
        SELECT
            domain,
            COUNT(*) as queries,
            SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as blocked
        FROM queries
        WHERE timestamp > strftime('%s', 'now', '-24 hours')
          AND domain IS NOT NULL
          AND domain != ''
        GROUP BY domain
        ORDER BY queries DESC
        LIMIT 50
        """

        domain_results = query_ftl_database(domain_query)
        top_domains = []
        for row in domain_results:
            top_domains.append({
                "domain": row.get("domain", "unknown"),
                "queries": float(row.get("queries", 0)),
                "blocked": float(row.get("blocked", 0)),
            })

        # Get client info from network table
        # Network table has: id, hwaddr, interface, firstSeen, lastQuery, numQueries, macVendor, aliasclient_id
        network_query = """
        SELECT hwaddr, numQueries, macVendor
        FROM network
        WHERE hwaddr IS NOT NULL AND hwaddr != ''
        ORDER BY numQueries DESC
        LIMIT 50
        """

        network_results = query_ftl_database(network_query)
        top_clients = []
        for row in network_results:
            top_clients.append({
                "mac": row.get("hwaddr", ""),
                "name": row.get("macVendor", "unknown"),
                "ip": "",  # IP not in network table
                "queries": float(row.get("numQueries", 0)),
            })

        # Get query types breakdown (last 24 hours)
        query_type_query = """
        SELECT
            type,
            COUNT(*) as count
        FROM queries
        WHERE timestamp > strftime('%s', 'now', '-24 hours')
        GROUP BY type
        """

        query_type_results = query_ftl_database(query_type_query)
        query_types = {}
        # Map query type numbers to names
        # 1=A, 2=AAAA, 3=ANY, 4=SRV, 5=SOA, 6=PTR, 7=TXT, 8=NAPTR, 9=MX, 10=DS, 11=RRSIG, 12=DNSKEY, 13=NS, 14=OTHER, 15=SVCB, 16=HTTPS
        type_names = {
            1: "A", 2: "AAAA", 3: "ANY", 4: "SRV", 5: "SOA", 6: "PTR", 7: "TXT",
            8: "NAPTR", 9: "MX", 10: "DS", 11: "RRSIG", 12: "DNSKEY", 13: "NS",
            14: "OTHER", 15: "SVCB", 16: "HTTPS"
        }
        for row in query_type_results:
            qtype = row.get("type", 0)
            type_name = type_names.get(qtype, f"TYPE{qtype}")
            query_types[type_name] = float(row.get("count", 0))

        # Get upstream servers breakdown (last 24 hours)
        upstream_query = """
        SELECT
            forward,
            COUNT(*) as count
        FROM queries
        WHERE timestamp > strftime('%s', 'now', '-24 hours')
          AND forward IS NOT NULL
          AND forward != ''
          AND status = 3
        GROUP BY forward
        ORDER BY count DESC
        """

        upstream_results = query_ftl_database(upstream_query)
        upstream_servers = {}
        for row in upstream_results:
            server = row.get("forward", "unknown")
            upstream_servers[server] = float(row.get("count", 0))

        # Get top permitted domains (last 24 hours, status != 1)
        permitted_query = """
        SELECT
            domain,
            COUNT(*) as queries
        FROM queries
        WHERE timestamp > strftime('%s', 'now', '-24 hours')
          AND domain IS NOT NULL
          AND domain != ''
          AND status != 1
        GROUP BY domain
        ORDER BY queries DESC
        LIMIT 50
        """

        permitted_results = query_ftl_database(permitted_query)
        top_permitted_domains = []
        for row in permitted_results:
            top_permitted_domains.append({
                "domain": row.get("domain", "unknown"),
                "queries": float(row.get("queries", 0)),
            })

        # Get top blocked domains (last 24 hours, status = 1)
        blocked_query = """
        SELECT
            domain,
            COUNT(*) as queries
        FROM queries
        WHERE timestamp > strftime('%s', 'now', '-24 hours')
          AND domain IS NOT NULL
          AND domain != ''
          AND status = 1
        GROUP BY domain
        ORDER BY queries DESC
        LIMIT 50
        """

        blocked_results = query_ftl_database(blocked_query)
        top_blocked_domains = []
        for row in blocked_results:
            top_blocked_domains.append({
                "domain": row.get("domain", "unknown"),
                "queries": float(row.get("queries", 0)),
            })

        cache_time = time.time()
        print(f"Fetched stats: {len(per_client_metrics)} clients, {len(top_domains)} domains")
        print(f"Query types: {len(query_types)}, Upstream servers: {len(upstream_servers)}")
        print(f"Top permitted: {len(top_permitted_domains)}, Top blocked: {len(top_blocked_domains)}")
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
