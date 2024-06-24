# File path: image_processing.py

import cv2
import numpy as np


def read_image(file_path: str) -> np.ndarray:
    """
    Read an image from a file path.

    :param file_path: Path to the input image.
    :return: Image as a numpy array.
    """
    image = cv2.imread(file_path)
    if image is None:
        raise FileNotFoundError(f"Image at {file_path} not found.")
    return image


def remove_noise(image: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """
    Remove noise from an image using Gaussian Blur.

    :param image: Input image.
    :param kernel_size: Size of the kernel for Gaussian Blur.
    :return: Denoised image.
    """
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)


def adjust_brightness(image: np.ndarray, beta: int = 50) -> np.ndarray:
    """
    Adjust the brightness of an image.

    :param image: Input image.
    :param beta: Brightness increment (positive to increase brightness).
    :return: Brightened image.
    """
    return cv2.convertScaleAbs(image, alpha=1, beta=beta)


def adjust_saturation(image: np.ndarray, scale: float = 1.2) -> np.ndarray:
    """
    Adjust the saturation of an image.

    :param image: Input image.
    :param scale: Scale factor for saturation.
    :return: Saturated image.
    """
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hsv_image[:, :, 1] = cv2.multiply(hsv_image[:, :, 1], scale)
    return cv2.cvtColor(hsv_image, cv2.COLOR_HSV2BGR)


def process_image(input_path: str, output_path: str) -> None:
    """
    Process an image by removing noise, brightening, and adjusting saturation.

    :param input_path: Path to the input image.
    :param output_path: Path to save the processed image.
    """
    # Read the image
    image = read_image(input_path)

    # Remove noise
    image = remove_noise(image)

    # Adjust brightness
    image = adjust_brightness(image)

    # Adjust saturation
    image = adjust_saturation(image)

    # Save the processed image
    cv2.imwrite(output_path, image)
    print(f"Processed image saved at {output_path}")


if __name__ == "__main__":
    input_image_path = "20240620-132917.jpg"  # Replace with your input image path
    output_image_path = "output.jpg"  # Replace with your desired output image path

    process_image(input_image_path, output_image_path)
