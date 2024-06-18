import asyncio
import io
import logging
from shutil import which

import numpy as np
import soundfile as sf
from pydub import AudioSegment

TARGET_VOLUME = -16
NOISE_FLOOR = -30
SAMPLE_RATE = 48000
BIT_DEPTH = 16


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
        await self.check_ffmpeg_installed()  # Asynchronous check

        command = [
            "ffmpeg",
            "-f",
            "s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-c:a",
            "libopus",
            "-f",
            "opus",
            "pipe:1",
        ]  # More readable formatting

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
            # Input Format Handling
            audio_segment = (
                AudioSegment.from_file(io.BytesIO(input_bytes))
                if input_format == "opus"
                else AudioSegment.from_file(
                    io.BytesIO(input_bytes), format="raw", frame_rate=SAMPLE_RATE, channels=1, sample_width=BIT_DEPTH // 8
                )
                if input_format == "pcm"
                else None
            )
            if audio_segment is None:
                raise ValueError(f"Unsupported input format: {input_format}")

            # Process Audio Data
            audio_data = np.array(audio_segment.get_array_of_samples(), dtype=np.float32) / (2 ** (BIT_DEPTH - 1))
            audio_data = self.process_audio_data(audio_data)

            bytes_object = io.BytesIO()

            sf.write(bytes_object, audio_data, SAMPLE_RATE, subtype="PCM_16", format="RAW")
            bytes_data = bytes_object.getvalue()

            if output_format == "opus":
                bytes_data = await self._transcode(bytes_data)

            return bytes_data

        except Exception as e:  # Log detailed error information
            self.logger.exception(f"Error processing audio: {e}")
            raise  # Re-raise the exception after logging

    def process_audio_data(self, audio_data: np.ndarray) -> np.ndarray:
        """Applies audio processing steps in a clear sequence."""
        audio_data = self.increase_volume(audio_data, TARGET_VOLUME)
        audio_data = self.normalize_audio(audio_data)
        audio_data = self.reduce_noise(audio_data, NOISE_FLOOR)
        return audio_data

    @staticmethod
    def increase_volume(audio_data: np.ndarray, target_volume: float) -> np.ndarray:
        """Increase the volume of the audio data to the target volume."""
        rms = np.sqrt(np.mean(audio_data**2))
        target_rms = 10 ** (target_volume / 20)
        gain = target_rms / (rms + 1e-10)  # Avoid division by zero
        return audio_data * gain

    @staticmethod
    def normalize_audio(audio_data: np.ndarray) -> np.ndarray:
        """Normalize the audio data to the range [-1, 1]."""
        peak = np.max(np.abs(audio_data))
        return audio_data / (peak + 1e-10)  # Avoid division by zero

    @staticmethod
    def reduce_noise(audio_data: np.ndarray, noise_floor: float) -> np.ndarray:
        """Reduce noise in the audio data based on the noise floor."""
        noise_threshold = np.percentile(np.abs(audio_data), 1) * 10 ** (noise_floor / 20)
        audio_data[np.abs(audio_data) < noise_threshold] = 0
        return audio_data


logger = logging.getLogger(__name__)


async def main():
    processor = AudioProcessor()

    test_cases = [
        ("test_input.opus", "opus", "opus_output.opus"),  # opus to opus
        ("test_input.pcm", "pcm", "pcm_output.pcm"),  # pcm to pcm
        ("test_input.opus", "opus", "pcm_output2.pcm"),  # opus to pcm
        ("test_input.pcm", "pcm", "opus_output2.opus"),  # pcm to opus
        (b"invalid_data", "invalid_format", "error_output.opus"),  # Invalid format (should raise error)
    ]

    for input_file, input_format, output_file in test_cases:
        try:
            if isinstance(input_file, bytes):
                input_bytes = input_file
            else:
                with open(input_file, "rb") as f:
                    input_bytes = f.read()

            output_bytes = await processor.process_audio(input_bytes, input_format, output_file.split(".")[-1])
            if output_bytes:  # Skip saving for invalid format cases
                with open(output_file, "wb") as f:
                    f.write(output_bytes)
                logger.info(f"Processed audio saved to {output_file}")

        except Exception as e:  # Log detailed error information
            logger.exception(f"Error processing file {input_file}: {e}")


if __name__ == "__main__":
    # Create dummy input files (1 second of random audio)
    asyncio.run(main())