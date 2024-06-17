import asyncio
import logging
from typing import Optional


class AudioQueue:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._audio_chunk_queue = asyncio.Queue()

    async def add_audio_chunk(self, audio_chunk: bytes) -> None:
        if not isinstance(audio_chunk, bytes):
            raise TypeError("Audio chunk must be of type bytes")

        try:
            await self._audio_chunk_queue.put(audio_chunk)
            self.logger.debug("Added audio chunk to queue.")
        except asyncio.QueueFull:
            self.logger.warning("Audio chunk queue is full. Dropping chunk.")

    async def get_audio_data(self, timeout: Optional[float] = None) -> bytes:
        # Wait for one second
        await asyncio.sleep(1)

        audio_data = b""

        while True:
            try:
                audio_chunk = await asyncio.wait_for(self._audio_chunk_queue.get(), timeout)
                audio_data += audio_chunk
                self._audio_chunk_queue.task_done()
            except asyncio.TimeoutError:
                break

        self.logger.debug(f"Retrieved {len(audio_data)} bytes of audio data.")
        return audio_data
