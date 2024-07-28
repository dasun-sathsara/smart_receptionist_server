import io

from google.cloud import speech, texttospeech
from pydub import AudioSegment


def voice_to_text(file_path):
    client = speech.SpeechClient()

    with io.open(file_path, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio({"content": content})

    config = speech.RecognitionConfig(
        {
            "encoding": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "sample_rate_hertz": 48000,
            "language_code": "en-US",
        }
    )

    response = client.recognize(config=config, audio=audio)

    transcription = ""
    for result in response.results:
        transcription += result.alternatives[0].transcript

    return transcription


def text_to_voice(text, output_file):
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        {
            "language_code": "en-US",
            "name": "en-US-Wavenet-D",
            "ssml_gender": texttospeech.SsmlVoiceGender.NEUTRAL,
        }
    )

    audio_config = texttospeech.AudioConfig({"audio_encoding": texttospeech.AudioEncoding.LINEAR16, "sample_rate_hertz": 48000})

    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

    with open("temp.wav", "wb") as out:
        out.write(response.audio_content)

    audio = AudioSegment.from_wav("temp.wav")
    audio.export(output_file, format="opus", bitrate="64k")


# Example usage
input_opus = "20240629-211211.opus"
output_text = voice_to_text(input_opus)
print(f"Transcription: {output_text}")

input_text = "Hello, this is a test of text-to-speech conversion. I hope it works! Fingers crossed!"
output_opus = "output.opus"
text_to_voice(input_text, output_opus)
print(f"Audio saved to {output_opus}")
