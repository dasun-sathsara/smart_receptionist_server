import asyncio
import logging
from pathlib import Path

import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AudioServer:
    def __init__(self, save_path='output.pcm'):
        self.save_path = Path(save_path)
        self.audio_queue = asyncio.Queue()
        self.clients = set()
        self.recording = False

    async def register(self, websocket):
        self.clients.add(websocket)
        logging.info(f"New client connected. Total clients: {len(self.clients)}")

    async def unregister(self, websocket):
        self.clients.remove(websocket)
        logging.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def distribute_message(self, message):
        if self.clients:
            coroutines = [client.send(message) for client in self.clients]
            results = await asyncio.gather(*coroutines, return_exceptions=True)
            for client, result in zip(self.clients.copy(), results):
                if isinstance(result, Exception):
                    logging.warning(f"Failed to send message to a client: {result}")
                    await self.unregister(client)

    async def consumer_handler(self, websocket, path):
        try:
            async for message in websocket:
                if message == 'start_recording':
                    self.recording = True
                    logging.info("Recording started")
                    await self.distribute_message('start_recording')
                elif message == 'stop_recording':
                    self.recording = False
                    logging.info("Recording stopped")
                    await self.distribute_message('stop_recording')
                    await self.save_audio()
                else:
                    if self.recording:
                        await self.audio_queue.put(message)
        finally:
            await self.unregister(websocket)

    async def handler(self, websocket, path):
        await self.register(websocket)
        consumer_task = asyncio.create_task(self.consumer_handler(websocket, path))
        done, pending = await asyncio.wait(
            [consumer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    async def save_audio(self):
        logging.info(f"Saving audio to {self.save_path}")
        with open(self.save_path, 'wb') as f:
            while not self.audio_queue.empty():
                chunk = await self.audio_queue.get()
                f.write(chunk)
        logging.info("Audio saved successfully")


async def main(host='0.0.0.0', port=8080):
    audio_server = AudioServer()
    server = await websockets.serve(audio_server.handler, host, port)
    logging.info(f"Server listening on {host}:{port}")
    await server.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
