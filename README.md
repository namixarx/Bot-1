# Telegram Bot Panel

A web-based panel for creating and managing Telegram bots with a green and black theme.

## Features

- **User Authentication**: Registration and login system
- **Bot Management**: Create, edit, enable/disable, and delete Telegram bots
- **Message Management**: Configure auto-reply messages with trigger text
- **Button Management**: Create menu buttons with responses
- **Real-time Bot Handling**: Active bots poll Telegram API and respond to messages
- **Token Validation**: Validates Telegram bot tokens on creation/update

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Set up the database (automatically created on first run):
```bash
python app.py
```

3. Access the application at `http://localhost:5000`

## Usage

1. **Register**: Create a new account with your Telegram bot token (get it from @BotFather)
2. **Create Bots**: Add multiple Telegram bots to your account
3. **Configure Messages**: Set up auto-reply messages with trigger text
4. **Add Buttons**: Create menu buttons with responses
5. **Test**: Use the test interface to verify bot responses
6. **Manage**: Enable/disable bots as needed

## Project Structure

- `app.py` - Main Flask application with routes
- `models.py` - Database models (User, Bot, Message, Button)
- `bot_handler.py` - Telegram bot polling and message handling
- `config.py` - Configuration settings
- `templates/` - HTML templates
- `static/` - CSS and JavaScript files
- `instance/` - SQLite database (created automatically)

## Security Notes

- Change the `SECRET_KEY` in `config.py` for production
- Consider encrypting bot tokens in production
- Use environment variables for sensitive configuration

## Requirements

- Python 3.7+
- Flask
- SQLite (included with Python)
- python-telegram-bot library

