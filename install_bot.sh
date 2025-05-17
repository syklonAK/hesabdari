#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status messages
print_status() {
    echo -e "${YELLOW}[*] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[+] $1${NC}"
}

print_error() {
    echo -e "${RED}[-] $1${NC}"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

print_status "Starting Accounting Bot Installation..."

# Update system packages
print_status "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install system dependencies
print_status "Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev

# Create bot directory
BOT_DIR="/opt/accounting-bot"
print_status "Creating bot directory at $BOT_DIR..."
mkdir -p $BOT_DIR
cd $BOT_DIR

# Create virtual environment
print_status "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
print_status "Installing Python packages..."
pip install --upgrade pip
pip install \
    python-telegram-bot \
    sqlalchemy \
    jdatetime \
    hijri-converter \
    python-dotenv

# Create bot user
print_status "Creating bot user..."
if ! id "botuser" &>/dev/null; then
    useradd -m -s /bin/bash botuser
    chown -R botuser:botuser $BOT_DIR
fi

# Download bot source code
print_status "Downloading bot source code..."
# Note: Replace this URL with your actual bot source code URL
wget https://raw.githubusercontent.com/yourusername/accounting-bot/main/accounting_bot.py -O $BOT_DIR/accounting_bot.py

# Create .env file
print_status "Setting up environment variables..."
echo "Please enter your Telegram Bot Token (from @BotFather):"
read bot_token
echo "Please enter your Telegram User ID (from @userinfobot):"
read admin_id

cat > $BOT_DIR/.env << EOF
TELEGRAM_TOKEN=$bot_token
ADMIN_ID=$admin_id
EOF

# Set proper permissions
chown -R botuser:botuser $BOT_DIR
chmod 600 $BOT_DIR/.env

# Create systemd service
print_status "Creating systemd service..."
cat > /etc/systemd/system/accounting-bot.service << EOF
[Unit]
Description=Accounting Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=$BOT_DIR
Environment=PATH=$BOT_DIR/venv/bin
ExecStart=$BOT_DIR/venv/bin/python $BOT_DIR/accounting_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
print_status "Starting bot service..."
systemctl daemon-reload
systemctl enable accounting-bot
systemctl start accounting-bot

# Check service status
print_status "Checking service status..."
systemctl status accounting-bot

print_success "Installation completed!"
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  ${GREEN}sudo systemctl start accounting-bot${NC}   - Start the bot"
echo -e "  ${GREEN}sudo systemctl stop accounting-bot${NC}    - Stop the bot"
echo -e "  ${GREEN}sudo systemctl restart accounting-bot${NC} - Restart the bot"
echo -e "  ${GREEN}sudo systemctl status accounting-bot${NC}  - Check bot status"
echo -e "  ${GREEN}sudo journalctl -u accounting-bot -f${NC}  - View bot logs"
echo -e "\n${YELLOW}Bot files are located at:${NC} $BOT_DIR"
echo -e "${YELLOW}Logs can be found at:${NC} /var/log/syslog" 