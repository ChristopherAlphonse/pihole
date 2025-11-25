# Pi-hole Docker Setup with Monitoring

A comprehensive Docker-based Pi-hole deployment with Traefik reverse proxy, Prometheus metrics collection, and Grafana dashboards for network-wide ad-blocking and DNS management.

## Features

- **Pi-hole DNS Server**: Network-wide ad and tracker blocking
- **Traefik Reverse Proxy**: Automatic HTTPS with Let's Encrypt (Cloudflare DNS challenge)
- **Prometheus Monitoring**: Metrics collection from Pi-hole
- **Grafana Dashboards**: Visual analytics for DNS queries, blocked ads, and client activity
- **Custom Exporter**: Python-based exporter that queries Pi-hole's FTL database directly
- **Management Scripts**: Device mapping, DHCP reservations, and blocklist management

## Prerequisites

- Docker and Docker Compose installed
- Cloudflare account (for DNS challenge) or modify for other ACME providers
- Network access to configure router DNS settings
- Ports available: 53 (DNS), 80 (HTTP), 443 (HTTPS), 8443 (Pi-hole admin)

## Quick Start

### 1. Clone and Configure

```bash
git clone <repository-url>
cd pihole
```

### 2. Environment Setup

Create `.env.pihole` file with your Pi-hole configuration:

```bash
# Pi-hole Configuration
WEBPASSWORD=your-secure-password-here
TZ=America/New_York
FTLCONF_LOCAL_IPV4=192.168.1.100
FTLCONF_LOCAL_IPV6=
VIRTUAL_HOST=pihole.home.arpa
```

### 3. Generate TLS Certificate

```bash
./generate-certs.sh
```

Or manually create `certs/tls.pem` for Pi-hole admin interface HTTPS.

### 4. Start Services

```bash
docker compose up -d
```

### 5. Configure Your Router

Point your router's DNS settings to your Pi-hole server IP address (port 53).

## Project Structure

```
pihole/
├── compose.yaml              # Main Pi-hole Docker Compose configuration
├── traefik-compose.yaml      # Traefik reverse proxy setup
├── compose.grafana.yaml      # Grafana monitoring stack (excluded from git)
├── traefik.yml               # Traefik configuration
├── traefik-config/           # Traefik TLS and routing configs
├── prometheus/               # Prometheus configuration
│   └── prometheus.yml
├── grafana/                  # Grafana dashboards and provisioning
│   ├── dashboards/
│   └── provisioning/
├── certs/                    # TLS certificates (excluded from git)
├── pihole-exporter.py        # Custom Prometheus exporter
├── Dockerfile.exporter       # Exporter container image
├── apply-device-mappings.sh  # Device name mapping script
├── manage-dhcp-reservations.sh # DHCP reservation management
├── identify-devices.sh       # Network device identification
├── whitelist-essential-sites.sh # Essential site whitelisting
└── SECURITY-NOTES.md         # Security best practices
```

## Configuration

### Pi-hole Configuration

The main Pi-hole service is configured in `compose.yaml`:

- **Image**: `docker.io/pihole/pihole:2025.11.0`
- **Ports**:
  - `53/tcp` and `53/udp` - DNS queries
  - `8443/tcp` - HTTPS admin interface
  - `123/udp` - NTP (optional)
- **Volumes**: Persistent storage for configuration and dnsmasq settings
- **Networks**: Connected to Traefik and internal Pi-hole network

### Traefik Configuration

Traefik provides:

- Automatic HTTPS with Let's Encrypt
- HTTP to HTTPS redirects
- Service discovery via Docker labels
- Cloudflare DNS challenge for ACME

Configure Cloudflare credentials in your environment:

```bash
CF_EMAIL=your-email@example.com
CF_DNS_API_TOKEN=your-cloudflare-api-token
```

### Monitoring Stack

#### Prometheus Exporter

The custom `pihole-exporter.py` provides comprehensive metrics by:

- Querying Pi-hole's FTL SQLite database directly
- Falling back to HTTP API if database access unavailable
- Exposing metrics on port `9617` at `/metrics`

**Metrics Provided:**

- Total DNS queries (all-time and 24h)
- Blocked queries count
- Cached vs forwarded queries
- Per-client statistics
- Top domains and blocked domains
- Query type breakdown (A, AAAA, MX, etc.)
- Upstream server distribution

#### Grafana

Pre-configured dashboards show:

- DNS query trends
- Block rate percentages
- Top clients and domains
- Query type distribution
- Historical blocking statistics

Access Grafana at `http://localhost:3000` (default credentials in `compose.grafana.yaml`).

## Management Scripts

### Device Mapping

Map MAC addresses to friendly device names:

```bash
./apply-device-mappings.sh
```

### DHCP Reservations

Manage static IP assignments:

```bash
./manage-dhcp-reservations.sh
```

### Identify Devices

Discover devices on your network:

```bash
./identify-devices.sh
```

### Whitelist Essential Sites

Add sites that should never be blocked:

```bash
./whitelist-essential-sites.sh
```

## Security

### Important Security Notes

**Never commit sensitive files to git!**

The following files are excluded via `.gitignore`:

- `.env*` files (contain passwords and secrets)
- `compose.grafana.yaml` (contains hardcoded passwords)
- Certificate files (`.pem`, `.key`, `.crt`, `.csr`)
- `certs/` directory
- Device-specific files (`pihole_address.txt`, `device-mappings.txt`)

### Best Practices

1. **Use Environment Files**: Store all secrets in `.env` files, not in compose files
2. **Strong Passwords**: Use complex passwords for Pi-hole admin interface
3. **Certificate Management**: Keep TLS certificates secure and rotate regularly
4. **Network Isolation**: Consider placing Pi-hole on a separate VLAN
5. **Regular Updates**: Keep Docker images updated for security patches

See `SECURITY-NOTES.md` for detailed security guidelines.

## Monitoring

### Accessing Metrics

- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`
- **Exporter**: `http://localhost:9617/metrics`
- **Pi-hole Admin**: `https://pihole.home.arpa:8443` or via Traefik

### Key Metrics to Monitor

- `pihole_dns_queries_total` - Total DNS queries processed
- `pihole_dns_blocked_total` - Total ads/trackers blocked
- `pihole_dns_blocked_24h` - Blocked in last 24 hours
- `pihole_clients_24h` - Active clients
- `pihole_client_queries_total{client="..."}` - Per-client query counts

## Maintenance

### Update Pi-hole

```bash
docker compose pull
docker compose up -d
```

### Backup Configuration

```bash
docker compose exec pihole pihole -a -t
```

### View Logs

```bash
docker compose logs -f pihole
docker compose logs -f pihole-exporter
```

### Restart Services

```bash
docker compose restart pihole
```

## Troubleshooting

### DNS Not Working

1. Verify Pi-hole container is running: `docker compose ps`
2. Check DNS port binding: `netstat -tuln | grep 53`
3. Verify router DNS settings point to Pi-hole IP
4. Check Pi-hole logs: `docker compose logs pihole`

### Exporter Not Collecting Metrics

1. Verify exporter can access Pi-hole container
2. Check `USE_VOLUME_MOUNT` environment variable
3. Ensure Pi-hole FTL database is accessible
4. Review exporter logs: `docker compose logs pihole-exporter`

### Traefik Not Routing

1. Verify Traefik network exists: `docker network ls | grep traefik`
2. Check Traefik labels in `compose.yaml`
3. Review Traefik logs: `docker compose logs traefik`

## License

This project is provided as-is for personal use. Pi-hole is licensed under the EUPL-1.2.

## Contributing

Contributions welcome! Please ensure:

- No sensitive data in commits
- Scripts are tested before submitting
- Documentation is updated for new features

## Additional Resources

- [Pi-hole Documentation](https://docs.pi-hole.net/)
- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

## Disclaimer

This setup is for personal/home use. Ensure compliance with your network policies and applicable laws when blocking ads and tracking.
