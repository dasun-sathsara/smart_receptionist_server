import asyncio
import io
import logging
from shutil import which

import noisereduce as nr
import numpy as np
import soundfile as sf
from pydub import AudioSegment
from scipy import signal

from ..config import Config


class AudioProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    async def check_ffmpeg_installed():
        """Asynchronous check if FFmpeg is available."""
        if not which("ffmpeg"):
            raise RuntimeError("FFmpeg is not installed or not found in your PATH.")

    async def _transcode(self, input_bytes: bytes) -> bytes:
        """Transcode audio using FFmpeg (opus to/from pcm)."""

        await self.check_ffmpeg_installed()

        command = [
            "ffmpeg",
            "-f",
            "s16le",
            "-ar",
            str(Config.SAMPLE_RATE),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-c:a",
            "libopus",
            "-f",
            "opus",
            "pipe:1",
        ]

        process = await asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate(input=input_bytes)

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            raise RuntimeError(f"FFmpeg error: {error_message}")

        return stdout

    async def process_audio(self, input_bytes: bytes, input_format: str, output_format: str) -> bytes:
        """Main audio processing pipeline."""
        try:
            audio_segment = (
                AudioSegment.from_file(io.BytesIO(input_bytes))
                if input_format == "opus"
                else AudioSegment.from_file(
                    io.BytesIO(input_bytes),
                    format="raw",
                    frame_rate=Config.SAMPLE_RATE,
                    channels=1,
                    sample_width=Config.BIT_DEPTH // 8,
                )
                if input_format == "pcm"
                else None
            )
            if audio_segment is None:
                raise ValueError(f"Unsupported input format: {input_format}")

            # Process Audio Data
            audio_data = np.array(audio_segment.get_array_of_samples(), dtype=np.float32) / (2 ** (Config.BIT_DEPTH - 1))
            audio_data = self.process_audio_data(audio_data)

            bytes_object = io.BytesIO()

            sf.write(bytes_object, audio_data, Config.SAMPLE_RATE, subtype="PCM_16", format="RAW")
            bytes_data = bytes_object.getvalue()

            if output_format == "opus":
                bytes_data = await self._transcode(bytes_data)

            return bytes_data

        except Exception as e:
            self.logger.exception(f"Error processing audio: {e}")

    def process_audio_data(self, audio_data: np.ndarray) -> np.ndarray:
        """Applies audio processing steps in a clear sequence."""

        # Apply high-pass filter with a lower cutoff frequency
        sos = signal.butter(5, 50, "hp", fs=Config.SAMPLE_RATE, output="sos")
        audio_data = signal.sosfilt(sos, audio_data)

        # Apply low-pass filter with a higher cutoff frequency
        sos = signal.butter(5, 8000, "lp", fs=Config.SAMPLE_RATE, output="sos")
        audio_data = signal.sosfilt(sos, audio_data)

        # Noise reduction with different parameters
        audio_data = nr.reduce_noise(
            y=audio_data,
            sr=Config.SAMPLE_RATE,
            prop_decrease=0.7,
            time_constant_s=2.0,
            freq_mask_smooth_hz=100,
            n_std_thresh_stationary=1.5,
        )

        # Auto gain with a conservative target level
        audio_data = self.auto_gain(audio_data, target_level=Config.TARGET_VOLUME)  # Increased target level

        return audio_data

    @staticmethod
    def auto_gain(audio_data: np.ndarray, target_level=-5.0) -> np.ndarray:
        """Apply automatic gain control to normalize audio levels."""
        current_level = 20 * np.log10(np.max(np.abs(audio_data)))
        gain_factor = 10 ** ((target_level - current_level) / 20)
        return audio_data * gain_factor
