from client_integration.main import telegram_worker

# Starting the Telegram bot
telegram_bot = telegram_worker()
if __name__ == "__main__":
    telegram_bot.start()
