# Security Notes

## ⚠️ Important Security Reminders

### Files with Passwords

**`compose.grafana.yaml`** contains a hardcoded password:
- `PIHOLE_PASSWORD: eA5u1lWWEB6d2N82sGjj0smfbdD8RigH`

This file is now in `.gitignore` to prevent committing the password to git.

**Recommended:** Move the password to a `.env.grafana` file:

1. Create `.env.grafana`:
   ```
   PIHOLE_PASSWORD=eA5u1lWWEB6d2N82sGjj0smfbdD8RigH
   ```

2. Update `compose.grafana.yaml`:
   ```yaml
   env_file:
     - .env.grafana
   ```

3. Add `.env.grafana` to `.gitignore` (already included)

### Files in .gitignore

The following files are excluded from git:

- **Sensitive files:**
  - `compose.grafana.yaml` (contains password)
  - `pihole_address.txt` (device-specific IP)
  - `device-mappings.txt` (device-specific MAC addresses)
  - `custom-blocklist.txt` (may contain custom rules)
  - All `.env*` files
  - All certificate files (`.pem`, `.key`, `.crt`, `.csr`)
  - `certs/` directory

- **Temporary scripts:**
  - `check-*.ps1`, `check-*.sh`
  - `whitelist-*.ps1`, `whitelist-*.sh`
  - `cleanup-*.ps1`, `cleanup-*.sh`

- **Cache and IDE files:**
  - `__pycache__/`
  - `.vscode/`, `.idea/`
  - Log files

### Safe to Commit

These files are safe to commit (no sensitive data):
- `compose.yaml` (uses `.env.pihole` for secrets)
- `pihole-exporter.py`
- `Dockerfile.exporter`
- `grafana/` configs (no passwords)
- `prometheus/` configs
- Scripts like `apply-device-mappings.sh`, `manage-dhcp-reservations.sh` (templates)
- `traefik.yml`, `traefik-config/` (if no secrets)

