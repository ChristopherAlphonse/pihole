# Pi-hole Docker Setup with Monitoring

A complete, one-command deployment of Pi-hole with Grafana monitoring, Prometheus metrics, and optional WireGuard VPN for remote access.

<details>
  <summary><strong>Pi-hole AI Deployment Instructions (click to expand)</strong></summary>

  ```bash
  You are a senior DevOps automation assistant. Your task is to guide the user through a fully automated, end-to-end deployment of the Pi-hole stack located at:
  https://github.com/ChristopherAlphonse/pihole

  Your process must always be interactive, safe, and OS-aware.

  ────────────────────────────────────────
  ENVIRONMENT & OS DETECTION
  ────────────────────────────────────────
  1. Detect the user's operating system (Linux, macOS, Windows).

  2. If the user is on Windows:
     - Ask if they prefer to run the setup using:
          A) WSL2  
          B) Docker Desktop (native)
     - If WSL2:
          • Check if WSL2 is installed; if not, give installation commands.
          • Check if a Linux distro is installed; if not, ask which distro they want.
          • Once confirmed, continue deployment inside WSL2.
     - If Docker Desktop:
          • Check if Docker Desktop is installed and running; if not, provide installation instructions.

  3. If the user is on Linux or macOS:
     - Check if Docker is installed.
     - If missing:
          • Ask user for permission to install Docker.
          • If granted, provide validated installation commands for their OS.

  4. Check for Docker Compose v2.
     - If missing, guide user to install it.

  ────────────────────────────────────────
  REPO SETUP & CONFIGURATION
  ────────────────────────────────────────
  5. Clone the GitHub repo: ChristopherAlphonse/pihole  
  6. Ensure required directory structure exists.

  7. Help the user generate or edit `.env.pihole` including:
     - TZ=America/New_York
     - DNSMASQ_LISTENING=all
     - WEBPASSWORD=<ask user if they want to set one, or auto-generate a secure 32-char password>

  8. If the stack requires certificates:
     - Generate TLS certificates automatically (self-signed unless user provides custom certs).

  9. Validate docker-compose.yml and ensure all volumes exist.

  ────────────────────────────────────────
  DEPLOYMENT
  ────────────────────────────────────────
  10. Bring the entire stack up using Docker Compose.

  11. After deployment, verify each required component:
      - Pi-hole container is running
      - DNS is listening on port 53 (UDP & TCP)
      - DHCP (if enabled) is on port 67
      - Web UI reachable on port 80/443
      - Prometheus & Grafana containers running
      - Metrics exporter running

  12. Detect and output the machine’s LAN IP address.
      - This MUST be printed clearly as:
           "Use **THIS IP** for DNS: <IP>"
           "Use **THIS IP** for DHCP: <IP> (if DHCP enabled)"

  13. Output all login URLs and credentials in a clear summary:
      - Pi-hole Admin URL
      - Username (always 'admin' unless repo uses different)
      - The WEBPASSWORD value (print it clearly)
      - Grafana URL + default Grafana username & password
      - Prometheus UI URL
      - Exporter URL(s)

  ────────────────────────────────────────
  POST-INSTALL CONFIGURATION
  ────────────────────────────────────────
  14. Provide instructions for configuring client DNS:
      • Routers (common brands)
      • Windows
      • macOS
      • Linux
      • iOS / Android

  15. Provide instructions to disable DNS-over-HTTPS (DOH) in major browsers (Chrome, Firefox, Edge, Brave, Safari).

  16. Provide health checks:
      - `dig` or `nslookup` test commands
      - How to validate blocking is working
      - How to restart or update the stack

  ────────────────────────────────────────
  OUTPUT FORMAT
  ────────────────────────────────────────
  Your final output must be structured in this order:

  A. System detection summary  
  B. Missing dependencies & installation steps  
  C. Repository setup & .env generation  
  D. Deployment steps  
  E. Final connection information including:  
       - Pi-hole Admin URL  
       - Username  
       - Password  
       - LAN IP address for DNS  
       - LAN IP address for DHCP  
       - Grafana URL & credentials  
       - Prometheus URL  
  F. Health-check & troubleshooting guide  

  Begin now.
``` 
</details>


## Features

- **Pi-hole DNS Server** - Network-wide ad and tracker blocking (~500k domains)
- **Grafana Dashboard** - Beautiful real-time monitoring
- **Prometheus Metrics** - Detailed statistics collection  
- **Custom Exporter** - Pi-hole v6 API compatible metrics exporter
- **WireGuard VPN** - Optional secure remote access from your phone
- **Auto-configured Blocklists** - Top blocklists automatically added

## Quick Start

### One-Command Setup

```bash
git clone https://github.com/ChristopherAlphonse/pihole.git
cd pihole
chmod +x setup.sh
./setup.sh
```

The setup script will:
1. Check prerequisites (Docker)
2. Detect your local IP
3. Generate TLS certificates
4. Start all services
5. Download and configure ~500k blocked domains
6. Display access URLs


### Manual 

<img width="1665" height="976" alt="198c3b80-73e0-11e9-8308-5fc92b936f98" src="https://github.com/user-attachments/assets/4361c84b-0585-4ec6-85ef-c11d16e81279" />

Setup

If you prefer manual setup:

```bash
# 1. Clone the repository
git clone https://github.com/ChristopherAlphonse/pihole.git
cd pihole

# 2. Create environment file
cat > .env.pihole << 'EOF'
TZ=America/New_York
FTLCONF_webserver_api_password=
FTLCONF_dns_listeningMode=all
EOF

# 3. Generate certificates
chmod +x generate-certs.sh
./generate-certs.sh

# 4. Start services
docker compose -f compose.monitoring.yaml up -d

# 5. Update gravity (blocklists)
docker exec pihole pihole -g
```

## Services & Ports

| Service | Port | URL |
|---------|------|-----|
| Pi-hole DNS | 53 | - |
| Pi-hole Admin | 80 | http://YOUR_IP/admin |
| Pi-hole HTTPS | 8443 | https://YOUR_IP:8443/admin |
| Grafana | 3000 | http://YOUR_IP:3000 |
| Prometheus | 9090 | http://YOUR_IP:9090 |
| Metrics Exporter | 9617 | http://YOUR_IP:9617/metrics |
| WireGuard VPN | 51820/udp | - |

## Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| Pi-hole | - | No password (disabled) |
| Grafana | admin | admin123 |

## Configure Your Devices

### Option 1: Configure Router (Recommended)
Set your router's DNS server to your Pi-hole IP. All devices on your network will automatically use Pi-hole.

### Option 2: Configure Individual Device

**Linux:**
```bash
sudo bash -c 'chattr -i /etc/resolv.conf 2>/dev/null; echo "nameserver YOUR_PIHOLE_IP" > /etc/resolv.conf; chattr +i /etc/resolv.conf'
```

**Windows:**
1. Control Panel → Network and Sharing Center
2. Change adapter settings → Right-click your adapter → Properties
3. IPv4 → Properties → Use the following DNS server
4. Enter your Pi-hole IP

**macOS:**
1. System Preferences → Network
2. Select your connection → Advanced → DNS
3. Add your Pi-hole IP

**Important:** Disable DNS-over-HTTPS in your browser:
- Firefox: Settings → Privacy & Security → DNS over HTTPS → Off
- Chrome: Settings → Privacy → Security → Use secure DNS → Off

## Remote Access (WireGuard VPN)

To access Pi-hole from your phone when away from home:

```bash
sudo bash setup-wireguard.sh
```

This will:
1. Install WireGuard
2. Generate server and client keys
3. Display a QR code to scan with the WireGuard app
4. Start the VPN server

**Router Configuration Required:**
- Forward port 51820 UDP to your Pi-hole server

## Included Blocklists

The setup automatically adds these top blocklists (~500k domains):

| List | Domains | Description |
|------|---------|-------------|
| StevenBlack Unified | ~88k | Comprehensive hosts file |
| Hagezi Pro | ~332k | Professional-grade blocking |
| OISD Big | ~217k | Curated wildcard list |
| AdGuard DNS | ~120k | AdGuard's DNS filter |
| 1Hosts Lite | ~128k | Lightweight but effective |
| Peter Lowe's List | ~3.5k | Classic ad server list |
| Firebog Suspicious | ~355 | Suspicious domains |
| d3Host List | ~131 | Adblock test domains |

## Useful Commands

```bash
# View all logs
docker compose -f compose.monitoring.yaml logs -f

# View Pi-hole logs only
docker logs pihole -f

# Restart all services
docker compose -f compose.monitoring.yaml restart

# Update blocklists
docker exec pihole pihole -g

# Check blocking status
docker exec pihole pihole status

# Query if a domain is blocked
docker exec pihole pihole -q example.com

# Stop all services
docker compose -f compose.monitoring.yaml down

# Update Pi-hole image
docker compose -f compose.monitoring.yaml pull
docker compose -f compose.monitoring.yaml up -d
```

## Test Your Ad Blocking

After configuring DNS, test with these sites:
- https://canyoublockit.com/extreme-test/
- https://fuzzthepiguy.tech/adtest/
- https://adblock.turtlecute.org/

## File Structure

```
pihole/
├── compose.monitoring.yaml    # Main Docker Compose file
├── setup.sh                   # One-command setup script
├── setup-wireguard.sh         # WireGuard VPN setup
├── generate-certs.sh          # TLS certificate generator
├── pihole-exporter.py         # Custom Prometheus exporter
├── Dockerfile.exporter        # Exporter container image
├── prometheus/
│   └── prometheus.yml         # Prometheus configuration
├── grafana/
│   ├── dashboards/
│   │   └── pihole-dashboard.json
│   └── provisioning/
│       ├── dashboards/
│       │   └── dashboard.yml
│       └── datasources/
│           └── datasource.yml
└── certs/                     # Generated TLS certificates (gitignored)
```

## Troubleshooting

### DNS Not Working
1. Check Pi-hole is running: `docker ps | grep pihole`
2. Check Pi-hole health: `docker exec pihole pihole status`
3. Verify DNS port: `netstat -tuln | grep :53`
4. Check your device's DNS settings

### Grafana Shows "No Data"
1. Check exporter: `curl http://localhost:9617/metrics`
2. Check Prometheus targets: http://YOUR_IP:9090/targets
3. Restart exporter: `docker restart pihole-exporter`

### Ads Still Showing
1. Ensure DNS-over-HTTPS is disabled in your browser
2. Clear browser cache
3. Check if domain is blocked: `docker exec pihole pihole -q domain.com`

### Container Keeps Restarting
1. Check logs: `docker logs pihole`
2. Ensure port 53 isn't in use: `sudo lsof -i :53`
3. On Linux, disable systemd-resolved: `sudo systemctl disable systemd-resolved`

## Contributing

Contributions welcome! Please ensure:
- No sensitive data in commits
- Test changes before submitting
- Update documentation for new features

## License

This project is provided as-is for personal use. Pi-hole is licensed under EUPL-1.2.

## Credits

- [Pi-hole](https://pi-hole.net/) - Network-wide ad blocking
- [Grafana](https://grafana.com/) - Monitoring dashboards
- [Prometheus](https://prometheus.io/) - Metrics collection
- Blocklist maintainers: StevenBlack, Hagezi, OISD, AdGuard, and others
