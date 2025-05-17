# Personal Accounting Telegram Bot

A Telegram bot that helps you track your personal finances by recording income and expenses.

## Features

- Record money coming in (income)
- Record money going out (expenses)
- Add descriptions to transactions
- View financial summary
- Edit transactions (admin only)
- Secure data storage using SQLite

## Setup

1. Create a new Telegram bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Use the `/newbot` command and follow the instructions
   - Copy the bot token provided by BotFather

2. Get your Telegram user ID:
   - Message [@userinfobot](https://t.me/userinfobot) on Telegram
   - Copy your user ID

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the bot:
   - Rename `.env.example` to `.env`
   - Add your bot token and user ID to the `.env` file:
     ```
     TELEGRAM_TOKEN=your_bot_token_here
     ADMIN_ID=your_telegram_user_id_here
     ```

5. Run the bot:
   ```bash
   python accounting_bot.py
   ```

## Usage

Start a chat with your bot on Telegram and use the following commands:

- `/start` - Display welcome message and available commands
- `/income` - Record money coming in
- `/expense` - Record money going out
- `/summary` - View your financial summary
- `/edit` - Edit a transaction (admin only)

## Data Storage

All transactions are stored in a local SQLite database (`accounting.db`). The database is automatically created when you first run the bot.

## Security

- Only the admin (specified by ADMIN_ID) can edit transactions
- All data is stored locally on your machine
- No sensitive financial data is transmitted to third parties 