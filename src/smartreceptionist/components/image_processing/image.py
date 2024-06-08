import asyncio
import logging
import time
from base64 import b64decode
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Image:
    image_data: str  # Base64 encoded image data
    faces_detected: bool = False
    image_name: str = field(default=None)
    logger: logging.Logger = field(init=False)

    def __post_init__(self):
        self.logger = logging.getLogger(__name__)
        self.image_name = str(time.strftime('%Y%m%d-%H%M%S'))

    async def save_to_disk(self) -> None:
        try:
            file_path = Path("media/images") / f"{self.image_name}.jpg"
            img_bytes = b64decode(self.image_data)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: file_path.write_bytes(img_bytes))

            self.logger.info(f"Image saved to {file_path}")
        except Exception as e:
            self.logger.error(f"Error saving image: {e}")
