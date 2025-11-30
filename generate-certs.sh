#!/bin/bash

# Generate self-signed certificate for pihole.home.arpa
DOMAIN="pihole.home.arpa"
CERT_DIR="./certs"
DAYS=3650

mkdir -p "$CERT_DIR"

# Generate private key
openssl genrsa -out "$CERT_DIR/pihole.key" 2048

# Generate certificate signing request
openssl req -new -key "$CERT_DIR/pihole.key" -out "$CERT_DIR/pihole.csr" \
  -subj "/C=US/ST=State/L=City/O=Home/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:pi.hole,DNS:*.home.arpa,DNS:localhost,IP:127.0.0.1"

# Generate self-signed certificate
openssl x509 -req -days $DAYS -in "$CERT_DIR/pihole.csr" \
  -signkey "$CERT_DIR/pihole.key" -out "$CERT_DIR/pihole.crt" \
  -extfile <(echo "subjectAltName=DNS:$DOMAIN,DNS:pi.hole,DNS:*.home.arpa,DNS:localhost,IP:127.0.0.1")

# Create combined certificate file for Traefik
cat "$CERT_DIR/pihole.crt" "$CERT_DIR/pihole.key" > "$CERT_DIR/pihole.pem"

# Create combined certificate file for Pi-hole (tls.pem format)
cat "$CERT_DIR/pihole.crt" "$CERT_DIR/pihole.key" > "$CERT_DIR/tls.pem"

# Set permissions
chmod 600 "$CERT_DIR"/*.key "$CERT_DIR"/*.pem "$CERT_DIR"/tls.pem
chmod 644 "$CERT_DIR"/*.crt "$CERT_DIR"/*.csr

echo " Self-signed certificate generated for $DOMAIN"
echo " Certificates are in: $CERT_DIR"
echo ""
echo "  Note: Browsers will show a security warning. You can safely accept it for local use."

