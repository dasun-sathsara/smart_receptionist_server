import asyncio
import logging
import platform
import signal

import websockets
from sinric import SinricPro, SinricProConstants
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from components.app_state import AppState
from components.audio_processing.audio_processor import AudioProcessor
from components.audio_processing.audio_queue import AudioQueue
from components.config import Config
from components.events.event_handler import EventHandler
from components.events.event_listener import EventListener
from components.google_home import GoogleHome
from components.image_processing.image_processor import ImageProcessor
from components.image_processing.image_queue import ImageQueue
from components.telegram_bot import TelegramBot
from components.ws_server import WebSocketServer


async def initialize_telegram_app(telegram_bot: TelegramBot):
    bot_token = Config.BOT_TOKEN
    tg_app = ApplicationBuilder().token(bot_token).build()

    # Command handlers
    tg_app.add_handler(CommandHandler("start", telegram_bot.start))
    tg_app.add_handler(CommandHandler("menu", telegram_bot.send_main_menu))

    # Message handlers
    tg_app.add_handler(MessageHandler(filters.VOICE, telegram_bot.handle_voice_message))

    # Callback query handler
    tg_app.add_handler(CallbackQueryHandler(telegram_bot.handle_callback_query))

    # Custom keyboard handler
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_bot.handle_unrecognized_message))

    # Initialize the bot
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    return tg_app


async def initialize_ws_server(ws_server: WebSocketServer):
    # For local development
    ws_server_process = await websockets.serve(ws_server.handle_new_connection, "0.0.0.0", 8765)
    return ws_server_process


async def initialize_sinric_pro(set_mode, set_power_state):
    callbacks = {SinricProConstants.SET_MODE: set_mode, SinricProConstants.SET_POWER_STATE: set_power_state}
    sinric_pro_client = SinricPro(
        Config.SINRIC_APP_KEY,
        [Config.GATE_ID, Config.LIGHT_ID],
        callbacks,
        enable_log=False,
        restore_states=False,
        secret_key=Config.SINRIC_APP_SECRET,
    )

    # Default states
    sinric_pro_client.event_handler.raise_event(
        Config.GATE_ID,
        SinricProConstants.SET_MODE,
        data={SinricProConstants.MODE: SinricProConstants.CLOSE},
    )
    sinric_pro_client.event_handler.raise_event(
        Config.LIGHT_ID,
        SinricProConstants.SET_POWER_STATE,
        data={SinricProConstants.POWER_STATE: SinricProConstants.POWER_STATE_OFF},
    )

    sinric_pro_task = asyncio.create_task(sinric_pro_client.connect())
    return sinric_pro_client, sinric_pro_task


async def main():
    Config.validate()

    # Initialize components
    app_state = AppState()
    event_listener = EventListener()
    image_processor = ImageProcessor()
    image_queue = ImageQueue(image_processor=image_processor)
    telegram_bot = TelegramBot(
        admin_user_id=int(Config.ADMIN_USER_ID),
        event_listener=event_listener,
        app_state=app_state,
    )
    audio_queue = AudioQueue()
    audio_processor = AudioProcessor()
    ws_server = WebSocketServer(event_listener=event_listener, app_state=app_state)
    google_home = GoogleHome(event_listener)

    # Concurrent initialization of components
    init_tasks = [
        initialize_telegram_app(telegram_bot),
        initialize_ws_server(ws_server),
        initialize_sinric_pro(google_home.handle_set_mode, google_home.handle_power_state),
    ]

    tg_app, ws_server_process, (sinric_pro_client, sinric_pro_task) = await asyncio.gather(*init_tasks)

    event_handler = EventHandler(
        telegram_bot=telegram_bot,
        ws_server=ws_server,
        app_state=app_state,
        image_queue=image_queue,
        sinric_pro_client=sinric_pro_client,
        audio_queue=audio_queue,
        audio_processor=audio_processor,
    )

    # Start the event listener
    event_listener_task = asyncio.create_task(event_listener.listen(event_handler))

    # Create a shared event loop for signal handling and tasks
    loop = asyncio.get_event_loop()

    # Ctrl+C (SIGINT) signal stops the application
    stop_application = asyncio.Event()

    # Get the operating system name
    os_name = platform.system()

    if os_name == "Windows":
        signal.signal(signal.SIGINT, lambda _1, _2: stop_application.set())
        signal.signal(signal.SIGTERM, lambda _1, _2: stop_application.set())
    elif os_name == "Linux":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_application.set)

    try:
        # Wait for the stop signal
        await stop_application.wait()
    finally:
        # Cleanup tasks
        logging.info("Cleaning up...")

        # Cancel running tasks
        sinric_pro_task.cancel()
        event_listener_task.cancel()

        # Close WebSocket server
        ws_server_process.close()
        await ws_server_process.wait_closed()

        # Stop Telegram bot
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()

        # Wait for all tasks to complete
        await asyncio.gather(sinric_pro_task, event_listener_task, return_exceptions=True)

        logging.info("Cleanup completed. Exiting...")


if __name__ == "__main__":
    asyncio.run(main())
