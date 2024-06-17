import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Image:
    image_data: bytes  # Raw image data
    faces_detected: bool = False
    image_name: str = field(default=None)
    logger: logging.Logger = field(init=False)
    path: Path = field(init=False)

    def __post_init__(self):
        self.logger = logging.getLogger(__name__)
        self.image_name = str(time.strftime("%Y%m%d-%H%M%S"))
        self.path = Path("media/images") / f"{self.image_name}.jpg"

    async def save_to_disk(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: self.path.write_bytes(self.image_data))

            self.logger.info(f"Image saved to {self.path}")
        except FileNotFoundError as e:
            self.logger.error(f"Error saving image: {e}")
