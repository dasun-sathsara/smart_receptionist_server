import io
import logging
from asyncio.subprocess import PIPE, create_subprocess_exec
from shutil import which


class AudioProcessor:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    @staticmethod
    async def _check_ffmpeg_installed():
        """Ensures FFmpeg is available."""
        if not which("ffmpeg"):
            raise RuntimeError("FFmpeg is not installed or not found in your PATH.")

    async def _transcode(self, input_bytes: io.BytesIO, input_format: str, output_format: str) -> io.BytesIO:
        """Transcode audio using FFmpeg with PCM/Opus commands (no parameters)."""
        await self._check_ffmpeg_installed()

        output_bytes = io.BytesIO()

        if input_format == "pcm" and output_format == "opus":
            command = [
                "ffmpeg",
                "-f",
                "s16le",
                "-ar",
                "44100",
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
        elif input_format == "opus" and output_format == "pcm":
            command = [
                "ffmpeg",
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-ar",
                "44100",
                "-ac",
                "1",
                "pipe:1",
            ]
        else:
            raise ValueError(f"Unsupported conversion: {input_format} to {output_format}")

        process = await create_subprocess_exec(*command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = await process.communicate(input=input_bytes.getvalue())

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            raise RuntimeError(f"FFmpeg process failed: {error_message}")

        output_bytes.write(stdout)
        output_bytes.seek(0)
        self._logger.info(f"Transcoded from {input_format} to {output_format}.")
        return output_bytes

    async def transcode_opus_to_pcm(self, input_bytes: io.BytesIO) -> io.BytesIO:
        """Transcode Opus to PCM (16-bit, 44.1kHz, mono)."""
        return await self._transcode(input_bytes, "opus", "pcm")

    async def transcode_pcm_to_opus(self, input_bytes: io.BytesIO) -> io.BytesIO:
        """Transcode PCM to Opus (16-bit, 44.1kHz, mono)."""
        return await self._transcode(input_bytes, "pcm", "opus")
