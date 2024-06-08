import asyncio
import concurrent.futures
import logging
from base64 import b64decode, b64encode

import cv2
import numpy as np
from ultralytics import YOLO

from .image import Image


class ImageProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def process_image(self, image_data: str) -> Image:
        with concurrent.futures.ProcessPoolExecutor() as pool:  # Use ProcessPoolExecutor
            processed_image = await asyncio.get_running_loop().run_in_executor(pool, self._process_image_sync, image_data)
        return processed_image

    def _process_image_sync(self, image_data: str) -> Image:
        model = YOLO("yolov8n-face.pt")

        # Decode the base64 image data
        image_bytes = b64decode(image_data)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)  # Convert to NumPy array
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)  # Decode image

        if image is None:
            self.logger.error("Failed to decode image from base64 data.")
            raise ValueError("Invalid image data")

        results = model.predict(source=image, save=False, max_det=5)

        faces_detected = False

        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy.tolist()[0])
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 1)
                faces_detected = True

        # Re-encode the processed image to base64
        _, buffer = cv2.imencode('.jpg', image)
        processed_image_data = b64encode(buffer).decode("utf-8")
        processed_image = Image(image_data=processed_image_data, faces_detected=faces_detected)
        return processed_image
