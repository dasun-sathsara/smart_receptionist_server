import asyncio
import logging
import signal

import websockets
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
)

from components.app_state import AppState
from components.event_handler import EventHandler
from components.telegram_bot import TelegramBot
from components.ws_server import WebSocketServer
from config import Config


async def initialize_telegram_app(telegram_bot: TelegramBot):
    bot_token = Config.BOT_TOKEN
    tg_app = ApplicationBuilder().token(bot_token).build()

    # /start command handler
    start_handler = CommandHandler("start", telegram_bot.start)

    tg_app.add_handler(start_handler)

    # Initialize the bot
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    return tg_app


async def initialize_ws_server(ws_server: WebSocketServer):
    # for production

    # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # ssl_context.load_cert_chain(
    #     certfile="/etc/letsencrypt/live/x.dasunsathsara.com/fullchain.pem",
    #     keyfile="/etc/letsencrypt/live/x.dasunsathsara.com/privkey.pem",
    # )
    # ws_server_process = await websockets.serve(ws_server.register, "x.dasunsathsara.com", 443, ssl=ssl_context)

    # for local development
    ws_server_process = await websockets.serve(ws_server.handle_new_connection, "localhost", 8765)

    return ws_server_process


async def main():
    Config.validate()

    app_state = AppState()
    event_handler = EventHandler()
    telegram_bot = TelegramBot(admin=int(Config.ADMIN_USER_ID), event_listener=event_handler, app_state=app_state)
    ws_server = WebSocketServer(event_listener=event_handler, app_state=app_state)

    tg_app = await initialize_telegram_app(telegram_bot)
    ws_server_process = await initialize_ws_server(ws_server)

    # Start the event listener
    event_listener_task = asyncio.create_task(event_handler.process_events(telegram_bot, app_state, ws_server))

    # Create a shared event loop for signal handling and tasks
    loop = asyncio.get_event_loop()

    # Ctrl+C (SIGINT) signal stops the application
    stop_application = loop.create_future()

    def signal_handler(sig, frame):
        stop_application.set_result(None)
        logging.info("Received signal %s, stopping application", sig)

    signal.signal(signal.SIGINT, signal_handler)

    # Wait for the stop signal
    await stop_application

    # Cancel the event listener task
    event_listener_task.cancel()
    try:
        await event_listener_task
    except asyncio.CancelledError:
        pass

    # Close the websocket server
    ws_server_process.close()
    await ws_server_process.wait_closed()

    # Stop the telegram bot
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
