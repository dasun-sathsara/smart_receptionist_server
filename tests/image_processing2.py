import cv2
import numpy as np
import tensorflow as tf
from skimage.restoration import denoise_nl_means, estimate_sigma
from tensorflow.keras.applications.vgg16 import VGG16
from tensorflow.keras.applications.vgg16 import preprocess_input
from tensorflow.keras.models import Model


def load_image(image_path):
    return cv2.imread(image_path)


def resize_image(image, target_size=(640, 480)):
    return cv2.resize(image, target_size, interpolation=cv2.INTER_LANCZOS4)


def denoise_image(image):
    sigma_est = np.mean(estimate_sigma(image, multichannel=True))
    return denoise_nl_means(image, h=1.15 * sigma_est, fast_mode=True, patch_size=5, patch_distance=3, multichannel=True)


def adjust_brightness_contrast(image, brightness=0, contrast=0):
    if brightness != 0:
        if brightness > 0:
            shadow = brightness
            highlight = 255
        else:
            shadow = 0
            highlight = 255 + brightness
        alpha_b = (highlight - shadow) / 255
        gamma_b = shadow
        image = cv2.addWeighted(image, alpha_b, image, 0, gamma_b)

    if contrast != 0:
        f = 131 * (contrast + 127) / (127 * (131 - contrast))
        alpha_c = f
        gamma_c = 127 * (1 - f)
        image = cv2.addWeighted(image, alpha_c, image, 0, gamma_c)

    return image


def sharpen_image(image):
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    return cv2.filter2D(image, -1, kernel)


def enhance_details(image):
    vgg = VGG16(weights="imagenet", include_top=False)
    content_layers = ["block1_conv2", "block2_conv2", "block3_conv3", "block4_conv3"]
    content_model = Model(inputs=vgg.input, outputs=[vgg.get_layer(layer).output for layer in content_layers])

    img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    img = np.expand_dims(img, axis=0)
    img = preprocess_input(img)

    content_features = content_model.predict(img)

    # Use content features to create an enhancement mask
    enhancement_mask = np.zeros_like(image, dtype=np.float32)
    for feature in content_features:
        resized_feature = cv2.resize(feature[0], (image.shape[1], image.shape[0]))
        enhancement_mask += resized_feature.mean(axis=-1)

    enhancement_mask = (enhancement_mask - enhancement_mask.min()) / (enhancement_mask.max() - enhancement_mask.min())
    enhancement_mask = enhancement_mask[..., np.newaxis]

    # Apply the enhancement mask
    enhanced = image.astype(np.float32) * (1 + enhancement_mask)
    enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)

    # Further enhance contrast and saturation
    enhanced = tf.image.adjust_contrast(tf.convert_to_tensor(enhanced), 1.5)
    enhanced = tf.image.adjust_saturation(enhanced, 1.2)

    return np.array(enhanced)


def enhance_image(image_path):
    # Load and resize image
    image = load_image(image_path)
    image = resize_image(image)

    # Denoise
    denoised = denoise_image(image)

    # Adjust brightness and contrast
    adjusted = adjust_brightness_contrast(denoised, brightness=10, contrast=20)

    # Enhance details using VGG16 features
    enhanced = enhance_details(adjusted)

    # Final sharpening
    sharpened = sharpen_image(enhanced)

    # Equalize histogram for better distribution of intensities
    ycrcb = cv2.cvtColor(sharpened, cv2.COLOR_BGR2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    final = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

    return final


# Example usage
input_image_path = "path_to_your_esp32_image.jpg"
enhanced_image = enhance_image(input_image_path)
cv2.imwrite("enhanced_esp32_image.jpg", enhanced_image)
