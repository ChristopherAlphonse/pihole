#!/bin/bash


set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Pi-hole DHCP Reservation & Hostname Manager${NC}"
echo "=============================================="
echo ""



DEVICES=(

    "46:c6:41:28:b1:06|192.168.1.100|device-1"
    "7a:ac:e7:8d:a2:17|192.168.1.101|device-2"
    "22:5e:ac:65:fb:5d|192.168.1.102|device-3"
    "ca:4f:b3:27:f1:83|192.168.1.103|device-4"
    "66:f0:2d:7a:90:52|192.168.1.104|device-5"
    "c2:d6:38:6d:7a:a9|192.168.1.105|device-6"
    "ba:fc:20:3c:5f:c7:9|192.168.1.106|device-7"
)

echo -e "${YELLOW}Step 1: Adding DHCP Reservations${NC}"
echo "-----------------------------------"


for device in "${DEVICES[@]}"; do
    IFS='|' read -r mac ip hostname <<< "$device"

    if [[ -z "$mac" || -z "$ip" || -z "$hostname" ]]; then
        echo -e "${RED}Skipping invalid entry: $device${NC}"
        continue
    fi

    echo -e "Adding: ${GREEN}$hostname${NC} (MAC: $mac, IP: $ip)"


    docker exec pihole bash -c "cat >> /etc/dnsmasq.d/04-pihole-static-dhcp.conf << EOF
# $hostname
dhcp-host=$mac,$ip,$hostname,infinite
EOF"
done

echo ""
echo -e "${YELLOW}Step 2: Adding Local DNS Records${NC}"
echo "-----------------------------------"


for device in "${DEVICES[@]}"; do
    IFS='|' read -r mac ip hostname <<< "$device"

    if [[ -z "$mac" || -z "$ip" || -z "$hostname" ]]; then
        continue
    fi

    echo -e "Adding DNS record: ${GREEN}$hostname.home.arpa${NC} → $ip"


    docker exec pihole bash -c "echo '$ip $hostname.home.arpa $hostname' >> /etc/pihole/custom.list"
done

echo ""
echo -e "${YELLOW}Step 3: Restarting Pi-hole DNS${NC}"
echo "-----------------------------------"

# Restart DNS to apply changes
docker exec pihole pihole restartdns

echo ""
echo -e "${GREEN}✓ DHCP reservations and DNS records added successfully!${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Edit this script and replace the example MAC addresses with your actual devices"
echo "2. Customize the hostnames to something meaningful (e.g., 'johns-laptop', 'living-room-tv')"
echo "3. Renew DHCP leases on your devices:"
echo "   - Windows: ipconfig /release && ipconfig /renew"
echo "   - Mac/Linux: sudo dhclient -r && sudo dhclient"
echo "   - Phone/Tablet: Toggle WiFi off and on"
echo "4. Check Pi-hole Network page to see the new hostnames"
echo ""
echo -e "${YELLOW}To find your device MAC addresses:${NC}"
echo "  Windows:       ipconfig /all          (look for 'Physical Address')"
echo "  Mac:           ifconfig | grep ether  (look for 'ether')"
echo "  Linux:         ip link show           (look for 'link/ether')"
echo "  iPhone:        Settings → WiFi → (i) → MAC Address"
echo "  Android:       Settings → WiFi → Advanced → MAC Address"
echo ""
