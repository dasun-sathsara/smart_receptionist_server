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
        with concurrent.futures.ProcessPoolExecutor() as pool:
            processed_image = await asyncio.get_running_loop().run_in_executor(pool, self._process_image_sync, image_data)
        return processed_image

    def _process_image_sync(self, image_data: bytes) -> Image:
        image_array = np.frombuffer(image_data, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None:
            self.logger.error("Failed to decode image from raw data.")
            raise ValueError("Invalid image data")

        results = self.model.predict(source=image, save=False, max_det=5)

        faces_detected = False
        for result in results:
            boxes = result.boxes
            if len(boxes) > 0:
                faces_detected = True
                break

        if faces_detected:
            # Apply pre-processing
            preprocessed = self.preprocess_image(image)

            # Draw bounding boxes on the preprocessed image
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy.tolist()[0])
                    cv2.rectangle(preprocessed, (x1, y1), (x2, y2), (0, 255, 0), 1)

            # Apply post-processing
            final_image = self.postprocess_image(preprocessed)
        else:
            final_image = image

        # Re-encode the processed image to bytes
        _, buffer = cv2.imencode(".jpg", final_image)
        processed_image = Image(image_data=buffer.tobytes(), faces_detected=faces_detected)
        return processed_image

    @staticmethod
    def preprocess_image(image, clahe_clip=2.0, clahe_grid=(8, 8), blur_kernel=(3, 3)):
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
    def postprocess_image(enhanced_image, sharpen_amount=0.5, saturation_factor=1.2):
        # Sharpen the image using an unsharp mask
        gaussian = cv2.GaussianBlur(enhanced_image, (0, 0), 2.0)
        sharpened = cv2.addWeighted(enhanced_image, 1 + sharpen_amount, gaussian, -sharpen_amount, 0)

        # Increase saturation
        hsv = cv2.cvtColor(sharpened, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = hsv[:, :, 1] * saturation_factor
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        final = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        return final
