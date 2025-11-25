#!/bin/bash

# Pi-hole Device Mapping Application Script
# This script applies device name mappings to Pi-hole using the device-mappings.txt file

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAPPINGS_FILE="${SCRIPT_DIR}/device-mappings.txt"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Pi-hole Device Name to MAC Address Mapping Tool        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if mappings file exists
if [[ ! -f "$MAPPINGS_FILE" ]]; then
    echo -e "${RED}Error: Mappings file not found: $MAPPINGS_FILE${NC}"
    exit 1
fi

# Check if Pi-hole container is running
if ! docker ps | grep -q "pihole"; then
    echo -e "${RED}Error: Pi-hole container is not running${NC}"
    echo "Please start Pi-hole first: docker-compose up -d"
    exit 1
fi

echo -e "${YELLOW}Step 1: Reading device mappings${NC}"
echo "-----------------------------------"

# Read mappings file (skip comments and empty lines)
declare -a DEVICES
while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip comments and empty lines
    [[ "$line" =~ ^#.*$ ]] && continue
    [[ -z "$line" ]] && continue

    # Parse line: MAC|HOSTNAME|DESCRIPTION|CONNECTION
    IFS='|' read -r mac hostname description connection <<< "$line"

    # Validate MAC address format (basic check)
    if [[ ! "$mac" =~ ^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$ ]]; then
        echo -e "${RED}Warning: Invalid MAC address format: $mac${NC}"
        continue
    fi

    # Normalize MAC address to lowercase
    mac=$(echo "$mac" | tr '[:upper:]' '[:lower:]')

    DEVICES+=("$mac|$hostname|$description|$connection")
    echo -e "  ${GREEN}✓${NC} $hostname ($mac)"
done < "$MAPPINGS_FILE"

echo ""
echo -e "${YELLOW}Step 2: Updating Pi-hole FTL Database${NC}"
echo "-----------------------------------"

# Update the network table in Pi-hole's FTL database
for device in "${DEVICES[@]}"; do
    IFS='|' read -r mac hostname description connection <<< "$device"

    # Update the network table with the hostname
    # Pi-hole stores MAC addresses in lowercase in the database
    docker exec pihole bash -c "
        sqlite3 /etc/pihole/pihole-FTL.db \"
        UPDATE network
        SET name = '$hostname'
        WHERE LOWER(hwaddr) = '$mac';

        -- If no row exists, insert a new one (though this is less common)
        INSERT OR IGNORE INTO network (hwaddr, name, lastQuery, numQueries)
        VALUES ('$mac', '$hostname', strftime('%s', 'now'), 0);
        \" 2>/dev/null || true
    "

    echo -e "  ${GREEN}✓${NC} Updated: $hostname → $mac"
done

echo ""
echo -e "${YELLOW}Step 3: Restarting Pi-hole FTL${NC}"
echo "-----------------------------------"

# Restart FTL to apply changes
docker exec pihole pihole restartdns

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓ Device mappings applied successfully!                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Open Pi-hole web interface and check the Network page"
echo "2. Devices should now show with their proper names"
echo "3. If some devices still show as 'unknown', they may need to make a DNS query first"
echo "4. You can run this script again anytime to update mappings"
echo ""
echo -e "${YELLOW}To view current devices:${NC}"
echo "  Run: ./identify-devices.sh"
echo ""





