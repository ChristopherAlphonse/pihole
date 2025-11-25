# Pi-hole Device Mapping Application Script (PowerShell)
# This script applies device name mappings to Pi-hole using the device-mappings.txt file

param(
    [string]$MappingsFile = "device-mappings.txt"
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-ColorOutput Cyan "╔════════════════════════════════════════════════════════════╗"
Write-ColorOutput Cyan "║   Pi-hole Device Name to MAC Address Mapping Tool        ║"
Write-ColorOutput Cyan "╚════════════════════════════════════════════════════════════╝"
Write-Output ""

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$MappingsPath = Join-Path $ScriptDir $MappingsFile

# Check if mappings file exists
if (-not (Test-Path $MappingsPath)) {
    Write-ColorOutput Red "Error: Mappings file not found: $MappingsPath"
    exit 1
}

# Check if Pi-hole container is running
$piholeRunning = docker ps --filter "name=pihole" --format "{{.Names}}" | Select-String -Pattern "pihole"
if (-not $piholeRunning) {
    Write-ColorOutput Red "Error: Pi-hole container is not running"
    Write-Output "Please start Pi-hole first: docker-compose up -d"
    exit 1
}

Write-ColorOutput Yellow "Step 1: Reading device mappings"
Write-Output "-----------------------------------"

# Read mappings file
$devices = @()
Get-Content $MappingsPath | ForEach-Object {
    $line = $_.Trim()

    # Skip comments and empty lines
    if ($line -match "^#" -or [string]::IsNullOrWhiteSpace($line)) {
        return
    }

    # Parse line: MAC|HOSTNAME|DESCRIPTION|CONNECTION
    $parts = $line -split '\|'
    if ($parts.Length -ge 2) {
        $mac = $parts[0].Trim().ToLower()
        $hostname = $parts[1].Trim()
        $description = if ($parts.Length -ge 3) { $parts[2].Trim() } else { "" }
        $connection = if ($parts.Length -ge 4) { $parts[3].Trim() } else { "" }

        # Validate MAC address format
        if ($mac -match "^([0-9a-f]{2}:){5}[0-9a-f]{2}$") {
            $devices += @{
                MAC = $mac
                Hostname = $hostname
                Description = $description
                Connection = $connection
            }
            Write-ColorOutput Green "  ✓ $hostname ($mac)"
        } else {
            Write-ColorOutput Red "  Warning: Invalid MAC address format: $mac"
        }
    }
}

Write-Output ""
Write-ColorOutput Yellow "Step 2: Updating Pi-hole FTL Database"
Write-Output "-----------------------------------"

# Update the network table in Pi-hole's FTL database
foreach ($device in $devices) {
    $mac = $device.MAC
    $hostname = $device.Hostname

    # Escape single quotes in hostname for SQL
    $hostnameEscaped = $hostname -replace "'", "''"

    # Update the network table with the hostname
    $sqlUpdate = @"
UPDATE network
SET name = '$hostnameEscaped'
WHERE LOWER(hwaddr) = '$mac';

INSERT OR IGNORE INTO network (hwaddr, name, lastQuery, numQueries)
VALUES ('$mac', '$hostnameEscaped', strftime('%s', 'now'), 0);
"@

    docker exec pihole bash -c "sqlite3 /etc/pihole/pihole-FTL.db `"$sqlUpdate`"" 2>$null

    Write-ColorOutput Green "  ✓ Updated: $hostname → $mac"
}

Write-Output ""
Write-ColorOutput Yellow "Step 3: Restarting Pi-hole FTL"
Write-Output "-----------------------------------"

# Restart FTL to apply changes
docker exec pihole pihole restartdns

Write-Output ""
Write-ColorOutput Green "╔════════════════════════════════════════════════════════════╗"
Write-ColorOutput Green "║   ✓ Device mappings applied successfully!                 ║"
Write-ColorOutput Green "╚════════════════════════════════════════════════════════════╝"
Write-Output ""
Write-ColorOutput Yellow "Next Steps:"
Write-Output "1. Open Pi-hole web interface and check the Network page"
Write-Output "2. Devices should now show with their proper names"
Write-Output "3. If some devices still show as 'unknown', they may need to make a DNS query first"
Write-Output "4. You can run this script again anytime to update mappings"
Write-Output ""
Write-ColorOutput Yellow "To view current devices:"
Write-Output "  Run: ./identify-devices.sh"
Write-Output ""





