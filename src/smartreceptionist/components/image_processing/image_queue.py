import asyncio
import logging

from .image import Image
from .image_processor import ImageProcessor


class ImageQueue:
    def __init__(self, image_processor: ImageProcessor, max_unprocessed_queue_size: int = 20, max_processed_queue_size: int = 10):
        self.image_processor = image_processor
        self.unprocessed_image_queue = asyncio.Queue(maxsize=max_unprocessed_queue_size)
        self.processed_image_queue = asyncio.Queue(maxsize=max_processed_queue_size)
        self._faces_detected_images = asyncio.Queue(maxsize=max_processed_queue_size)
        self.num_of_face_detected_images = 0
        self.logger = logging.getLogger(__name__)
        self._consumer_task = None

    async def enqueue_image(self, image_data: str):
        try:
            await self.unprocessed_image_queue.put(image_data)
        except asyncio.QueueFull:
            self.logger.error("Unprocessed image queue is full. Image dropped.")

        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self._process_images())

    async def _process_images(self) -> None:
        while True:
            try:
                image_data = await self.unprocessed_image_queue.get()
                self.unprocessed_image_queue.task_done()  # Mark the task as done in the unprocessed queue
            except asyncio.CancelledError:
                self.logger.info("Image processing task cancelled.")
                break

            try:
                image = await self.image_processor.process_image(image_data)
                await self.processed_image_queue.put(image)

                if image.faces_detected:
                    await self._faces_detected_images.put(image)
                    self.num_of_face_detected_images += 1
                    self.logger.info(f"Face detected in image: {image.image_name}")
                else:
                    self.logger.info(f"No face detected in image: {image.image_name}")
            except Exception as e:
                self.logger.error(f"Error processing image: {e}")

    async def dequeue_processed_image(self) -> Image:
        processed_image = await self.processed_image_queue.get()
        self.processed_image_queue.task_done()
        return processed_image

    async def get_face_detected_images(self):
        faces_detected_images = []
        while True:
            try:
                image = self._faces_detected_images.get_nowait()
                faces_detected_images.append(image)
            except asyncio.QueueEmpty:
                break
        return faces_detected_images

    async def cleanup(self):
        self.unprocessed_image_queue = asyncio.Queue()
        self.processed_image_queue = asyncio.Queue()
        self._faces_detected_images = asyncio.Queue()
        self.num_of_face_detected_images = 0
