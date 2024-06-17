import asyncio
import io
import logging
import shutil
from asyncio.subprocess import PIPE, Process

import aiofiles

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Audio settings (fixed)
SAMPLE_RATE = 44100
CHANNELS = 1


async def check_ffmpeg_installed():
    """Ensures FFmpeg is available."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is not installed or not found in your PATH.")


async def transcode_opus_to_pcm(input_bytes: io.BytesIO) -> io.BytesIO:
    """Transcode Opus audio_processing data from a BytesIO to PCM (16-bit, 44.1kHz, mono) BytesIO."""
    await check_ffmpeg_installed()

    output_bytes = io.BytesIO()

    ffmpeg_args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",  # Read from stdin (pipe)
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        str(CHANNELS),
        "-sample_fmt",
        "s16",
        "-f",
        "s16le",
        "pipe:1",  # Write to stdout (pipe)
    ]

    process: Process = await asyncio.create_subprocess_exec(*ffmpeg_args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate(input=input_bytes.getvalue())

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg process failed with error: {stderr.decode()}")

    output_bytes.write(stdout)
    output_bytes.seek(0)
    return output_bytes


async def transcode_pcm_to_opus(input_bytes: io.BytesIO) -> io.BytesIO:
    """Transcode PCM audio_processing data from a BytesIO to Opus (16-bit, 44.1kHz, mono) BytesIO."""
    await check_ffmpeg_installed()

    output_bytes = io.BytesIO()

    ffmpeg_args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "s16le",
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        str(CHANNELS),
        "-i",
        "pipe:0",  # Read from stdin
        "-f",
        "opus",
        "pipe:1",  # Write to stdout
    ]

    process: Process = await asyncio.create_subprocess_exec(*ffmpeg_args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate(input=input_bytes.getvalue())

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg process failed with error: {stderr.decode()}")

    output_bytes.write(stdout)
    output_bytes.seek(0)
    return output_bytes


async def load_audio_from_file(file_path: str) -> io.BytesIO:
    """Loads audio_processing data from a file into a BytesIO object."""
    async with aiofiles.open(file_path, "rb") as f:
        return io.BytesIO(await f.read())


async def save_audio_to_file(audio_bytes: io.BytesIO, file_path: str) -> None:
    """Saves audio_processing data from a BytesIO object to a file."""
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(audio_bytes.getvalue())


async def convert_and_save(
    input_bytes: io.BytesIO,
    output_path: str,
    source_format: str,
    target_format: str,
) -> None:
    """Converts audio_processing data in memory and saves the result to a file."""
    try:
        if source_format == "opus" and target_format == "pcm":
            converted_bytes = await transcode_opus_to_pcm(input_bytes)
        elif source_format == "pcm" and target_format == "opus":
            converted_bytes = await transcode_pcm_to_opus(input_bytes)
        else:
            raise ValueError(f"Unsupported conversion from {source_format} to {target_format}")

        await save_audio_to_file(converted_bytes, output_path)
        logging.info(f"Successfully converted to {output_path}")

    except Exception as e:
        logging.error(f"Conversion failed: {e}")
        raise  # Re-raise the exception after logging


async def main():
    input_opus_file = "Rihanna - Stay.opus"  # Replace with your actual file
    output_pcm_file = "Rihanna - Stay.pcm"
    output_opus_file = "Rihanna - Stay C.opus"

    # Load input audio_processing from file
    input_opus_bytes = await load_audio_from_file(input_opus_file)

    # Convert and save in memory
    await convert_and_save(input_opus_bytes, output_pcm_file, "opus", "pcm")

    # Load converted PCM data
    input_pcm_bytes = await load_audio_from_file(output_pcm_file)
    await convert_and_save(input_pcm_bytes, output_opus_file, "pcm", "opus")


if __name__ == "__main__":
    asyncio.run(main())
