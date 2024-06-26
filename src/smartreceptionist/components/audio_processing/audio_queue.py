import asyncio
import logging


class AudioQueue:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._audio_chunk_queue = asyncio.Queue()

    async def add_audio_chunk(self, audio_chunk: bytes) -> None:
        if not isinstance(audio_chunk, bytes):
            raise TypeError("Audio chunk must be of type bytes")

        try:
            await self._audio_chunk_queue.put(audio_chunk)
        except asyncio.QueueFull:
            self.logger.warning("Audio chunk queue is full. Dropping chunk.")

    async def get_audio_data(self) -> bytes:
        # Wait for one second to queue up any incoming data
        await asyncio.sleep(1)

        audio_data = b""

        while not self._audio_chunk_queue.empty():
            chunk = await self._audio_chunk_queue.get()
            audio_data += chunk

        self.logger.debug(f"Retrieved {len(audio_data)} bytes of audio data.")
        return audio_data
