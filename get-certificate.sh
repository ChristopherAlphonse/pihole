#!/bin/bash

# Generate proper certificate for pihole.home.arpa
DOMAIN="pihole.home.arpa"
CERT_DIR="./certs"
DAYS=365

mkdir -p "$CERT_DIR"

# Check if mkcert is available (best option for local trust)
if command -v mkcert &> /dev/null; then
    echo "✅ Using mkcert for locally trusted certificates"
    mkcert -install 2>&1 | head -5
    mkcert "$DOMAIN" pi.hole localhost 127.0.0.1 ::1 2>&1
    mv "${DOMAIN}+3.pem" "$CERT_DIR/pihole.pem"
    mv "${DOMAIN}+3-key.pem" "$CERT_DIR/pihole.key"
    openssl x509 -in "$CERT_DIR/pihole.pem" -out "$CERT_DIR/pihole.crt"
    # Create combined certificate file for Pi-hole (tls.pem format)
    cat "$CERT_DIR/pihole.crt" "$CERT_DIR/pihole.key" > "$CERT_DIR/tls.pem"
    chmod 600 "$CERT_DIR/tls.pem"
    echo "✅ mkcert certificate generated and installed"
else
    echo "⚠️  mkcert not found. Generating self-signed certificate..."
    echo "   Install mkcert for locally trusted certs: https://github.com/FiloSottile/mkcert"

    # Generate self-signed with proper SAN
    openssl genrsa -out "$CERT_DIR/pihole.key" 2048

    # Create certificate with Subject Alternative Names
    openssl req -new -x509 -key "$CERT_DIR/pihole.key" -out "$CERT_DIR/pihole.crt" \
        -days $DAYS \
        -subj "/C=US/ST=State/L=City/O=Home/CN=$DOMAIN" \
        -addext "subjectAltName=DNS:$DOMAIN,DNS:pi.hole,DNS:localhost,IP:127.0.0.1,IP:::1"

    # Create combined PEM
    cat "$CERT_DIR/pihole.crt" "$CERT_DIR/pihole.key" > "$CERT_DIR/pihole.pem"

    # Create combined certificate file for Pi-hole (tls.pem format)
    cat "$CERT_DIR/pihole.crt" "$CERT_DIR/pihole.key" > "$CERT_DIR/tls.pem"

    chmod 600 "$CERT_DIR"/*.key "$CERT_DIR"/*.pem "$CERT_DIR"/tls.pem
    chmod 644 "$CERT_DIR"/*.crt

    echo "✅ Self-signed certificate generated"
    echo "⚠️  Browser will still show warning (normal for self-signed)"
fi

echo ""
echo "📁 Certificates in: $CERT_DIR"
ls -lh "$CERT_DIR"/*.{crt,key,pem} 2>/dev/null



