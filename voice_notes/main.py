import json
import os
from typing import Annotated
from typing import TypedDict, List

import assemblyai as aai
import typer
from assemblyai import Transcript


aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")
transcriber = aai.Transcriber()


class SpeakerLabel(TypedDict):
    speaker_label: str | None
    text: str
    start: int
    end: int


def get_speaker_labels(audio_transcript: Transcript) -> List[SpeakerLabel]:
    return [
        SpeakerLabel(
            speaker_label=utterance.speaker,
            text=utterance.text,
            start=utterance.start,
            end=utterance.end,
        )
        for utterance in (audio_transcript.utterances or [])
    ]


def transcribe_file(path_to_transcribe: str) -> Transcript:
    config = aai.TranscriptionConfig(speaker_labels=True, language_code="en")
    return aai.Transcriber().transcribe(data=path_to_transcribe, config=config)


def format_transcription(transcription: list[SpeakerLabel], output_format: str):
    if output_format == "txt":
        return "\n".join(
            [
                f"[{el['start']}:{el['end']}] {el['speaker_label']}: {el['text']}"
                for el in transcription
            ]
        )
    elif output_format == "json":
        return json.dumps([
            dict(
                speaker=el["speaker_label"],
                text = el["text"],
                start = el["start"],
                end = el["end"]
            ) for el in transcription
        ])
    else:
        raise ValueError("Invalid format")


app = typer.Typer()


@app.command()
def t(
    file_path: Annotated[str, typer.Argument(help="path to the audio file")],
    output_format: Annotated[
        str,
        typer.Option(
            help="format of the transcription. defaults to json. possible values:json|txt"
        ),
    ] = "json",
):
    """
    requires an API key from assembly AI. please set it up as an environment variable at ASSEMBLYAI_API_KEY
    """
    # TODO: trim silence from audio file to optimize transcription cost
    transcript: Transcript = transcribe_file(os.path.expanduser(file_path))
    transcription = get_speaker_labels(transcript)
    print(format_transcription(transcription, output_format.lower()))


if __name__ == "__main__":
    app()
