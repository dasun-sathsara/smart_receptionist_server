import time
from pathlib import Path
from typing import Literal

import aiofiles

AudioOrigin = Literal["tg", "esp"]


async def save_audio_file(data: bytes, origin: AudioOrigin) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    file_extension = "pcm" if origin == "tg" else "opus"
    filename = f"{timestamp}.{file_extension}"

    base_dir = Path("media/audio")
    sub_dir = base_dir / f"{origin}_received"
    file_path = sub_dir / filename

    try:
        sub_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
        async with aiofiles.open(file_path, "wb") as audio_file:
            await audio_file.write(data)
        return file_path
    except (FileNotFoundError, PermissionError, IOError) as e:
        raise SystemError(f"Error saving audio file: {e}") from e  # Chain exceptions for better debugging


async def get_latest_telegram_audio() -> bytes:
    audio_dir = Path("media/audio/telegram_received")
    try:
        audio_files = sorted(audio_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        if not audio_files:  # Check if any files exist
            raise FileNotFoundError("No Telegram audio files found")

        latest_file = audio_files[0]
        async with aiofiles.open(latest_file, "rb") as audio_file:
            return await audio_file.read()
    except (FileNotFoundError, IOError) as e:
        raise SystemError(f"Error retrieving latest Telegram audio: {e}") from e
