import io
import logging

import noisereduce as nr
import numpy as np
import soundfile as sf
from pydub import AudioSegment
from scipy import signal

from ..config import Config


class AudioProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def process_audio(self, input_bytes: bytes, input_format: str) -> bytes:
        try:
            if input_format == "opus":
                # Convert Opus (Telegram) audio to 16kHz, mono
                audio = AudioSegment.from_file(io.BytesIO(input_bytes), format="ogg", codec="opus")
                audio = audio.set_frame_rate(Config.SAMPLE_RATE).set_channels(1)
                audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
            elif input_format == "wav":
                audio_data, _ = sf.read(io.BytesIO(input_bytes))
            elif input_format == "pcm":
                audio_data = AudioSegment.from_file(
                    io.BytesIO(input_bytes),
                    format="raw",
                    frame_rate=Config.SAMPLE_RATE,
                    channels=1,
                    sample_width=Config.BIT_DEPTH // 8,
                )
                audio_data = np.array(audio_data.get_array_of_samples(), dtype=np.float32) / 32768.0
            else:
                raise ValueError(f"Unsupported input format: {input_format}")

            processed_data = self.process_audio_data(audio_data)

            output_buffer = io.BytesIO()
            sf.write(output_buffer, processed_data, Config.SAMPLE_RATE, format="WAV", subtype="PCM_16")
            return output_buffer.getvalue()

        except Exception as e:
            self.logger.exception(f"Error processing audio: {e}")

    def process_audio_data(self, audio_data: np.ndarray) -> np.ndarray:
        # Apply high-pass filter
        sos = signal.butter(5, 50, "hp", fs=Config.SAMPLE_RATE, output="sos")
        audio_data = signal.sosfilt(sos, audio_data)

        # Apply low-pass filter
        sos = signal.butter(5, 7000, "lp", fs=Config.SAMPLE_RATE, output="sos")
        audio_data = signal.sosfilt(sos, audio_data)

        # Noise reduction
        audio_data = nr.reduce_noise(
            y=audio_data,
            sr=Config.SAMPLE_RATE,
            prop_decrease=0.7,
            time_constant_s=2.0,
            freq_mask_smooth_hz=100,
            n_std_thresh_stationary=1.5,
        )

        # Auto gain
        audio_data = self.auto_gain(audio_data, target_level=Config.TARGET_VOLUME)

        return audio_data

    @staticmethod
    def auto_gain(audio_data: np.ndarray, target_level=-5.0) -> np.ndarray:
        current_level = 20 * np.log10(np.max(np.abs(audio_data)))
        gain_factor = 10 ** ((target_level - current_level) / 20)
        return audio_data * gain_factor
