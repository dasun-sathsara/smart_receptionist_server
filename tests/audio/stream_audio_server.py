import argparse
import asyncio
import logging
from pathlib import Path

import websockets

# Constants
SAMPLE_RATE = 44100
BYTES_PER_SAMPLE = 2
DEFAULT_CHUNK_SIZE = 1024

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def stream_audio(websocket, path, filename, chunk_size):
    try:
        file_size = Path(filename).stat().st_size
        with open(filename, 'rb') as audio_file:
            logging.info(f"New connection from {websocket.remote_address}. Streaming file: {filename}")

            while True:
                chunk = audio_file.read(chunk_size)
                if not chunk:
                    break

                await websocket.send(chunk)

                # Delay to match real-time playback
                await asyncio.sleep(chunk_size / (SAMPLE_RATE * BYTES_PER_SAMPLE))

            logging.info(f"Finished streaming file to {websocket.remote_address}")

    except websockets.exceptions.ConnectionClosed:
        logging.info(f"Connection closed by {websocket.remote_address}")
    except Exception as e:
        logging.error(f"Error occurred while streaming to {websocket.remote_address}: {e}")


async def main(args):
    server = await websockets.serve(
        lambda ws, path: stream_audio(ws, path, args.filename, args.chunk_size),
        args.host,
        args.port,
        ping_interval=None
    )

    logging.info(f"Server started on {args.host}:{args.port}. Press Ctrl+C to stop.")

    try:
        await server.wait_closed()
    except KeyboardInterrupt:
        logging.info("Server stopping...")
    finally:
        await server.close()
        logging.info("Server stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebSocket Audio Streaming Server")
    parser.add_argument("filename", help="Path to the PCM audio file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind the server to")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Chunk size in bytes")

    args = parser.parse_args()

    if not Path(args.filename).is_file():
        logging.error(f"File not found: {args.filename}")
    else:
        asyncio.run(main(args))
