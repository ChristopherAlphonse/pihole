#!/bin/bash

# Device Identification Helper Script
# Run this to see current devices connected to Pi-hole

echo "Current Devices Connected to Pi-hole"
echo "====================================="
echo ""


echo "Fetching device list from Pi-hole..."
echo ""


docker exec pihole bash -c "
echo 'IP Address          | MAC Address       | Hostname          | Last Seen           | Queries'
echo '--------------------------------------------------------------------------------------------'
sqlite3 /etc/pihole/pihole-FTL.db \"
SELECT
    ip,
    hwaddr,
    COALESCE(name, '(unknown)') as hostname,
    datetime(lastQuery, 'unixepoch', 'localtime') as last_seen,
    numQueries
FROM network
WHERE ip != ''
ORDER BY numQueries DESC;
\" | column -t -s '|'
"

echo ""
echo "--------------------------------------------------------------------------------------------"
echo ""
echo "To identify your devices:"
echo ""
echo "1. On each device, find its current IP address:"
echo "   - Windows PC:     Open Command Prompt → run 'ipconfig'"
echo "   - Mac:            System Settings → Network → Details"
echo "   - iPhone/iPad:    Settings → WiFi → tap (i) next to network name"
echo "   - Android:        Settings → WiFi → tap network name → Advanced"
echo "   - Smart TV:       Settings → Network → Network Status"
echo ""
echo "2. Match the IP address from your device to the table above"
echo ""
echo "3. Note the MAC address for that device"
echo ""
echo "4. Edit manage-dhcp-reservations.sh and update the DEVICES array with:"
echo "   - The MAC address you found"
echo "   - A static IP you want to assign (e.g., 192.168.1.100)"
echo "   - A friendly hostname (e.g., 'johns-laptop', 'living-room-tv')"
echo ""
