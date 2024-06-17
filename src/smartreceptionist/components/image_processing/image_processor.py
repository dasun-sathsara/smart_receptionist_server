import asyncio
import concurrent.futures
import logging

import cv2
import numpy as np
from ultralytics import YOLO

from .image import Image


class ImageProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.model = YOLO("yolov8n-face.pt")

    async def process_image(self, image_data: bytes) -> Image:
        with concurrent.futures.ProcessPoolExecutor() as pool:  # Use ProcessPoolExecutor
            processed_image = await asyncio.get_running_loop().run_in_executor(
                pool, self._process_image_sync, image_data
            )
        return processed_image

    def _process_image_sync(self, image_data: bytes) -> Image:
        image_array = np.frombuffer(image_data, dtype=np.uint8)  # Convert to NumPy array
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)  # Decode image

        if image is None:
            self.logger.error("Failed to decode image from raw data.")
            raise ValueError("Invalid image data")

        results = self.model.predict(source=image, save=False, max_det=5)

        faces_detected = False

        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy.tolist()[0])
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 1)
                faces_detected = True

        # Re-encode the processed image to base64
        _, buffer = cv2.imencode(".jpg", image)
        processed_image = Image(image_data=buffer.tobytes(), faces_detected=faces_detected)
        return processed_image
