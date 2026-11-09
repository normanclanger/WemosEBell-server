#!/bin/bash

set -e

# ==================================================
# eBells Server Wi-Fi Hotspot Setup
# ==================================================

INTERFACE="wlan0"
CONNECTION_NAME="eBells Server"

SERVER_IP="10.42.0.1/24"
SERVER_IP_ONLY="10.42.0.1"

HOTSPOT_PASSWORD="eBellServer123"

# ==================================================
# Check that the Wi-Fi interface exists
# ==================================================

if [ ! -e "/sys/class/net/$INTERFACE" ]; then
    echo "ERROR: Wi-Fi interface $INTERFACE not found."
    exit 1
fi

# ==================================================
# Get Wi-Fi MAC address
# ==================================================

MAC=$(cat /sys/class/net/$INTERFACE/address)

# Remove colons and take the final six characters
MAC_SUFFIX=$(echo "$MAC" | tr -d ':' | tail -c 7)

SSID="eBell-server-$MAC_SUFFIX"

# ==================================================
# Display configuration
# ==================================================

echo
echo "=========================================="
echo "        eBells Server Hotspot Setup"
echo "=========================================="
echo
echo "Wi-Fi interface : $INTERFACE"
echo "Wi-Fi MAC       : $MAC"
echo "SSID            : $SSID"
echo "Password        : $HOTSPOT_PASSWORD"
echo "Server IP       : $SERVER_IP_ONLY"
echo "Subnet          : 10.42.0.0/24"
echo "UDP port        : 5005"
echo

# ==================================================
# Remove an existing eBells Server connection
# ==================================================

if nmcli connection show "$CONNECTION_NAME" >/dev/null 2>&1; then
    echo "Removing existing '$CONNECTION_NAME' connection..."
    sudo nmcli connection delete "$CONNECTION_NAME"
fi

# ==================================================
# Create the Wi-Fi access point
# ==================================================

echo "Creating NetworkManager connection..."

sudo nmcli connection add \
    type wifi \
    ifname "$INTERFACE" \
    con-name "$CONNECTION_NAME" \
    autoconnect yes \
    ssid "$SSID"

# ==================================================
# Configure access point
# ==================================================

sudo nmcli connection modify "$CONNECTION_NAME" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg

# ==================================================
# Configure WPA2 password
# ==================================================

sudo nmcli connection modify "$CONNECTION_NAME" \
    802-11-wireless-security.key-mgmt wpa-psk \
    802-11-wireless-security.psk "$HOTSPOT_PASSWORD"

# ==================================================
# Configure IPv4 network
# ==================================================

sudo nmcli connection modify "$CONNECTION_NAME" \
    ipv4.method shared \
    ipv4.addresses "$SERVER_IP" \
    ipv4.never-default yes

# ==================================================
# We don't need IPv6 for the eBells network
# ==================================================

sudo nmcli connection modify "$CONNECTION_NAME" \
    ipv6.method disabled

# ==================================================
# Start the hotspot
# ==================================================

echo
echo "Starting hotspot..."

sudo nmcli connection up "$CONNECTION_NAME"

# ==================================================
# Display result
# ==================================================

echo
echo "=========================================="
echo "        eBells Server Ready"
echo "=========================================="
echo
echo "SSID:       $SSID"
echo "Password:   $HOTSPOT_PASSWORD"
echo "Server IP:  $SERVER_IP_ONLY"
echo "Subnet:     10.42.0.0/24"
echo
