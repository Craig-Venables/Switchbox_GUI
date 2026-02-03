# Notifications Package

This package contains notification services for the measurement system. Currently includes Telegram bot integration for sending notifications and receiving interactive responses.

## Overview

The Notifications package provides a unified interface for sending alerts, notifications, and receiving user feedback during long-running measurements. The services are designed to be non-blocking and thread-safe.

## Package Structure

```
Notifications/
├── README.md              # This file
├── __init__.py            # Package exports
└── telegram_bot.py        # TelegramBot class
```

## Components

### TelegramBot (`telegram_bot.py`)

Simplified Telegram bot interface for sending notifications, images, and interactive messages.

**Key Features**:
- Thread-safe: runs in separate daemon thread with own event loop
- Non-blocking: all operations use async internally
- Automatic webhook cleanup: ensures long polling works properly
- Error resilient: failures don't crash the application
- Interactive Q&A: send questions and wait for replies

## Usage

### Basic Usage

```python
from Notifications import TelegramBot

# Initialize bot with token and chat ID
bot = TelegramBot(token="YOUR_BOT_TOKEN", chat_id="YOUR_CHAT_ID")

# Send simple messages
bot.send_message("Measurement complete!")

# Send images
bot.send_image("path/to/plot.png", caption="IV Curve Results")

# Ask interactive questions
response = bot.ask_and_wait(
    question="Continue test?",
    choices={"1": "Yes", "2": "No", "3": "Skip"},
    timeout_s=60
)

# Graceful shutdown
bot.shutdown()
```

### Integration Example

```python
from Notifications import TelegramBot

class MeasurementService:
    def __init__(self):
        # Initialize Telegram bot if configured
        try:
            token = self.config.get("telegram_token")
            chat_id = self.config.get("telegram_chat_id")
            if token and chat_id:
                self.telegram_bot = TelegramBot(token, chat_id)
            else:
                self.telegram_bot = None
        except Exception as e:
            print(f"Telegram bot initialization failed: {e}")
            self.telegram_bot = None
    
    def notify_measurement_complete(self, data_path: str):
        """Send notification when measurement completes."""
        if self.telegram_bot:
            self.telegram_bot.send_message(
                f"✅ Measurement complete!\n\n"
                f"Data saved to: {data_path}"
            )
            # Send summary plot if available
            plot_path = f"{data_path}_summary.png"
            if Path(plot_path).exists():
                self.telegram_bot.send_image(
                    plot_path,
                    caption="Measurement Summary"
                )
```

## Dependencies

### Core Dependencies
- `python-telegram-bot`: Official Telegram Bot API library
- `asyncio`: Asynchronous operations
- `threading`: Thread management

### Python Version
- Python 3.8+

## Configuration

The Telegram bot requires:
- **Bot Token**: Obtained from [@BotFather](https://t.me/BotFather) on Telegram
- **Chat ID**: Your Telegram chat ID where messages should be sent

Configuration can be provided:
- Via constructor parameters
- From JSON configuration files
- From GUI settings

## API Reference

### `TelegramBot`

Main class for Telegram bot functionality.

**Parameters**:
- `token` (str): Telegram Bot API token
- `chat_id` (str): Telegram Chat ID for sending messages

**Methods**:
- `send_message(text: str) -> None`: Send a text message (non-blocking)
- `send_image(image_path: str, caption: str = "") -> None`: Send an image (non-blocking)
- `ask_question(question: str, choices: Dict[str, str]) -> None`: Send a question (non-blocking)
- `wait_for_text_reply(timeout_s: int = 300) -> Optional[str]`: Wait for a text reply (blocking)
- `ask_and_wait(question: str, choices: Dict[str, str], timeout_s: int = 300) -> Optional[str]`: Send question and wait for reply (blocking)
- `shutdown(timeout: float = 5.0) -> None`: Gracefully shutdown the bot

## Architecture

### Thread Model
- The bot runs in a separate daemon thread
- All operations are scheduled on an async event loop
- Main application remains non-blocking

### Error Handling
- Network errors use exponential backoff retry
- Failures are logged but don't crash the application
- Graceful degradation if bot is unavailable

### Message Polling
- Uses Telegram's getUpdates API with long polling
- Efficiently waits for replies without high API usage
- Filters messages by chat_id for security

## Examples

### Measurement Notification

```python
from Notifications import TelegramBot

bot = TelegramBot(token, chat_id)

# Send start notification
bot.send_message("🔬 Starting measurement sequence...")

# Send progress updates
bot.send_message(f"📊 Completed {completed}/{total} devices")

# Send completion notification with plot
bot.send_image("summary_plot.png", caption="Measurement Complete")
```

### Interactive Workflow

```python
from Notifications import TelegramBot

bot = TelegramBot(token, chat_id)

# Ask user if measurement should continue
response = bot.ask_and_wait(
    question="Measurement complete. Continue with next device?",
    choices={
        "1": "Yes, continue",
        "2": "No, stop here",
        "3": "Skip this device"
    },
    timeout_s=300  # Wait up to 5 minutes
)

if response == "1":
    # Continue measurement
    pass
elif response == "2":
    # Stop measurement
    pass
elif response == "3":
    # Skip device
    pass
```

## Integration Points

The Telegram bot is integrated into:

1. **Sample GUI** (`gui/sample_gui/main.py`):
   - Loads bot configuration from JSON
   - Sends device status updates

2. **Measurement GUI** (via `TelegramCoordinator`):
   - Sends measurement completion notifications
   - Sends data summary plots
   - Interactive measurement control

3. **Telegram Coordinator** (`Measurements/telegram_coordinator.py`):
   - Wraps Telegram bot for measurement services
   - Provides convenient notification methods

## Future Enhancements

Potential additions to the Notifications package:
- Email notifications
- Slack integration
- Discord integration
- SMS notifications (via Twilio)
- Push notifications
- Unified notification interface for multiple services

## Notes

- The bot uses a daemon thread, so it will automatically terminate when the main application exits
- Always call `shutdown()` when done to ensure clean resource cleanup
- The bot is designed to be optional - applications should handle the case when it's not configured
- Long polling timeouts are configurable to balance responsiveness and API usage

## Backward Compatibility

The root-level `TelegramBot.py` file provides backward compatibility:

```python
# Old import (still works)
from TelegramBot import TelegramBot

# New import (recommended)
from Notifications import TelegramBot
```

Both import paths work, but new code should use the `Notifications` package import.

