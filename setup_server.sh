#!/bin/bash
# 🚀 proglem - Debian Server Initialization Script
# Installs Nginx, Python 3.11+, .NET Runtime, cloudflared, and playit.gg

echo "Starting server initialization..."

# 1. Update system and install core dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget gnupg software-properties-common nginx python3.11 python3.11-venv python3-pip

# 2. Install .NET Runtime (for RimWorld Together C# Server)
# Fetch Microsoft signing key and repository
wget https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb
sudo apt update
sudo apt install -y aspnetcore-runtime-8.0

# 3. Install Cloudflared (For HTTP/HTTPS CGNAT Bypass)
# Fetches the latest stable deb package directly from Cloudflare
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
rm cloudflared-linux-amd64.deb

# 4. Install Playit.gg (For TCP/UDP Game Tunnel)
curl -SsL https://playit-cloud.github.io/ppa/key.gpg | sudo apt-key add -
sudo curl -SsL -o /etc/apt/sources.list.d/playit-cloud.list https://playit-cloud.github.io/ppa/playit-cloud.list
sudo apt update
sudo apt install -y playit

echo "✅ Core dependencies installed successfully!"
echo "Next steps:"
echo "1. Run 'cloudflared tunnel login' to authenticate your domain."
echo "2. Run 'playit' to claim your game tunnel."