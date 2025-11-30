#!/bin/bash
# WireGuard VPN Setup Script for Pi-hole Remote Access
# Run this script with: sudo bash setup-wireguard.sh

set -e

# Configuration
SERVER_IP="192.168.1.177"
WG_PORT="51820"
WG_INTERFACE="wg0"
WG_NETWORK="10.66.66.0/24"
SERVER_WG_IP="10.66.66.1"
CLIENT_WG_IP="10.66.66.2"
WG_DIR="/etc/wireguard"

echo "=========================================="
echo "  WireGuard VPN Setup for Pi-hole"
echo "=========================================="

# Install WireGuard
echo "[1/7] Installing WireGuard..."
pacman -S --noconfirm wireguard-tools qrencode

# Create WireGuard directory
echo "[2/7] Creating WireGuard directory..."
mkdir -p "$WG_DIR"
chmod 700 "$WG_DIR"

# Generate server keys
echo "[3/7] Generating server keys..."
wg genkey | tee "$WG_DIR/server_private.key" | wg pubkey > "$WG_DIR/server_public.key"
chmod 600 "$WG_DIR/server_private.key"

# Generate client keys (for phone)
echo "[4/7] Generating client keys..."
wg genkey | tee "$WG_DIR/phone_private.key" | wg pubkey > "$WG_DIR/phone_public.key"
chmod 600 "$WG_DIR/phone_private.key"

# Read keys
SERVER_PRIVATE=$(cat "$WG_DIR/server_private.key")
SERVER_PUBLIC=$(cat "$WG_DIR/server_public.key")
PHONE_PRIVATE=$(cat "$WG_DIR/phone_private.key")
PHONE_PUBLIC=$(cat "$WG_DIR/phone_public.key")

# Detect primary network interface
PRIMARY_IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
echo "Detected primary interface: $PRIMARY_IFACE"

# Create server config
echo "[5/7] Creating server configuration..."
cat > "$WG_DIR/$WG_INTERFACE.conf" << EOF
[Interface]
Address = $SERVER_WG_IP/24
ListenPort = $WG_PORT
PrivateKey = $SERVER_PRIVATE
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o $PRIMARY_IFACE -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o $PRIMARY_IFACE -j MASQUERADE

# Phone Client
[Peer]
PublicKey = $PHONE_PUBLIC
AllowedIPs = $CLIENT_WG_IP/32
EOF

chmod 600 "$WG_DIR/$WG_INTERFACE.conf"

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_PUBLIC_IP")

# Create phone client config
echo "[6/7] Creating phone client configuration..."
PHONE_CONFIG="$WG_DIR/phone.conf"
cat > "$PHONE_CONFIG" << EOF
[Interface]
PrivateKey = $PHONE_PRIVATE
Address = $CLIENT_WG_IP/24
DNS = $SERVER_WG_IP

[Peer]
PublicKey = $SERVER_PUBLIC
Endpoint = $PUBLIC_IP:$WG_PORT
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

# Also save a copy to the pihole directory for easy access
cp "$PHONE_CONFIG" /home/surface/pihole/phone-wireguard.conf 2>/dev/null || true

# Enable IP forwarding
echo "[7/7] Enabling IP forwarding..."
echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-wireguard.conf
sysctl -p /etc/sysctl.d/99-wireguard.conf

# Start WireGuard
systemctl enable wg-quick@$WG_INTERFACE
systemctl start wg-quick@$WG_INTERFACE

echo ""
echo "=========================================="
echo "  WireGuard Setup Complete!"
echo "=========================================="
echo ""
echo "Server is running on: $SERVER_IP:$WG_PORT"
echo "Public IP detected: $PUBLIC_IP"
echo ""
echo "Phone QR Code (scan with WireGuard app):"
echo "------------------------------------------"
qrencode -t ansiutf8 < "$PHONE_CONFIG"
echo ""
echo "Phone config saved to: $PHONE_CONFIG"
echo "Phone config also at: /home/surface/pihole/phone-wireguard.conf"
echo ""
echo "To check status: sudo wg show"
echo ""
