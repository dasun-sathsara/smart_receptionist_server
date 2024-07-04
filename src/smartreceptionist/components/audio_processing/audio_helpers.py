import time
from pathlib import Path
from typing import Literal

import aiofiles

AudioOrigin = Literal["tg", "esp"]


async def save_audio_file(data: bytes, origin: AudioOrigin) -> Path:
    """Saves the received audio data to a file and returns the file path."""

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}.wav"
    base_dir = Path("media/audio")
    sub_dir = base_dir / f"{origin}_received"
    file_path = sub_dir / filename

    try:
        sub_dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "wb") as audio_file:
            await audio_file.write(data)
        return file_path
    except (FileNotFoundError, PermissionError, IOError) as e:
        raise SystemError(f"Error saving audio file: {e}")


async def get_latest_telegram_audio() -> Path:
    """Returns the path to the latest Telegram audio file."""
    audio_dir = Path("media/audio/tg_received")
    try:
        audio_files = sorted(audio_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        if not audio_files:
            raise FileNotFoundError("No Telegram audio files found")
        return audio_files[0]
    except (FileNotFoundError, IOError) as e:
        raise SystemError(f"Error retrieving latest Telegram audio: {e}") from e
