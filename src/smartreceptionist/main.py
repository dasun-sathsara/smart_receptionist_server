import asyncio
import logging
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

    # /start command handler
    start_handler = CommandHandler("start", telegram_bot.start)

    # /ap command handler
    ap_command_handler = CommandHandler("ap", telegram_bot.handle_action_prompt)

    # 'ap' message handler
    ap_message_handler = MessageHandler(
        filters=filters.TEXT & filters.Regex(r"^ap$"), callback=telegram_bot.handle_action_prompt
    )

    # Voice message handler
    voice_message_handler = MessageHandler(filters=filters.VOICE, callback=telegram_bot.handle_voice_message)

    # Handle messages that starts with cmd
    cmd_message_handler = MessageHandler(
        filters=filters.TEXT & filters.Regex(r"^cmd"), callback=telegram_bot.handle_cmd_message
    )

    # Callback query handler
    action_prompt_handler = CallbackQueryHandler(telegram_bot.handle_callback_query)

    tg_app.add_handler(start_handler)
    tg_app.add_handler(action_prompt_handler)
    tg_app.add_handler(ap_command_handler)
    tg_app.add_handler(ap_message_handler)
    tg_app.add_handler(cmd_message_handler)
    tg_app.add_handler(voice_message_handler)

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
        data={
            SinricProConstants.MODE: SinricProConstants.CLOSE,
        },
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
    sinric_pro_client, sinric_pro_task = await initialize_sinric_pro(
        google_home.handle_set_mode, google_home.handle_power_state
    )

    event_handler = EventHandler(
        telegram_bot=telegram_bot,
        ws_server=ws_server,
        app_state=app_state,
        image_queue=image_queue,
        sinric_pro_client=sinric_pro_client,
        audio_queue=audio_queue,
        audio_processor=audio_processor,
    )

    tg_app = await initialize_telegram_app(telegram_bot)
    ws_server_process = await initialize_ws_server(ws_server)

    # Start the event listener
    event_listener_task = asyncio.create_task(event_listener.listen(event_handler))

    # Create a shared event loop for signal handling and tasks
    loop = asyncio.get_event_loop()

    # Ctrl+C (SIGINT) signal stops the application
    stop_application = loop.create_future()

    def signal_handler(sig, _):
        stop_application.set_result(None)
        logging.info("Received signal %s, stopping application", sig)

    signal.signal(signal.SIGINT, signal_handler)

    # Wait for the stop signal
    await stop_application

    # Cancel the Sinric Pro task
    sinric_pro_task.cancel()

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
    import os

    print(os.getcwd())
    # asyncio.run(main(), debug=True)
    asyncio.run(main())
