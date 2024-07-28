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
        self.process_pool = concurrent.futures.ProcessPoolExecutor(max_workers=1)

    async def process_image(self, image_data: bytes) -> Image:
        loop = asyncio.get_running_loop()
        try:
            processed_image = await loop.run_in_executor(self.process_pool, self._process_image_sync, image_data)
            return processed_image
        except Exception as e:
            self.logger.error(f"Error processing image: {e}")
            raise

    @staticmethod
    def _process_image_sync(image_data: bytes) -> Image:
        # YOLO model can't be pickled, so it needs to be initialized within the process.
        model = YOLO("yolov8n-face.pt")

        image_array = np.frombuffer(image_data, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image data")

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = model(image_rgb)

        faces_detected = len(results[0].boxes) > 0

        if faces_detected:
            preprocessed = ImageProcessor.preprocess_image(image)
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy.tolist()[0])
                    cv2.rectangle(preprocessed, (x1, y1), (x2, y2), (0, 255, 0), 1)
            final_image = ImageProcessor.postprocess_image(preprocessed)
        else:
            final_image = image

        _, buffer = cv2.imencode(".jpg", final_image)
        processed_image = Image(image_data=buffer.tobytes(), faces_detected=faces_detected)
        return processed_image

    @staticmethod
    def apply_processing(image_data) -> bytes:
        image_array = np.frombuffer(image_data, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        preprocessed = ImageProcessor.preprocess_image(image)
        final_image = ImageProcessor.postprocess_image(preprocessed)

        _, buffer = cv2.imencode(".jpg", final_image)

        return buffer.tobytes()

    @staticmethod
    def preprocess_image(image, clahe_clip=2.0, clahe_grid=(6, 6), blur_kernel=(3, 3)):
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Apply CLAHE to L-channel
        clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=clahe_grid)
        cl = clahe.apply(l)

        # Merge the CLAHE enhanced L-channel back with A and B channels
        limg = cv2.merge((cl, a, b))

        # Convert back to BGR color space
        enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

        # Apply Gaussian blur for noise reduction
        denoised = cv2.GaussianBlur(enhanced, blur_kernel, 0)

        return denoised

    @staticmethod
    def postprocess_image(enhanced_image, sharpen_amount=0.5, saturation_factor=1.1):
        # Sharpen the image using an unsharp mask
        gaussian = cv2.GaussianBlur(enhanced_image, (0, 0), 2.0)
        sharpened = cv2.addWeighted(enhanced_image, 1 + sharpen_amount, gaussian, -sharpen_amount, 0)

        # Increase saturation
        hsv = cv2.cvtColor(sharpened, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = hsv[:, :, 1] * saturation_factor
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        final = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        return final
