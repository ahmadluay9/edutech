import base64
from pathlib import Path
import sys
import time
from google import genai
from google.genai import types


def b64decode(b64_encoded_string: str) -> bytes:
    return base64.b64decode(b64_encoded_string.encode("utf-8"))


DEFAULT_PROMPT = (
    "Medium close-up shot of a friendly professional businesswoman in a modern softly "
    "blurred office, looking directly at the camera. At the beginning she smiles warmly "
    'and asks clearly in English: "Hi, and what are you reading?" She then pauses and '
    "nods attentively for two seconds, and then smiles and asks: "
    '"Oh interesting, how is the stock market doing today?"'
)


def generate_lesson_videos(
    prompt: str = DEFAULT_PROMPT,
    output_dir: str | Path = "static/videos",
    number_of_videos: int = 4,
    duration_seconds: int = 8,
) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    client = genai.Client(
        vertexai=True,
        project="eikon-dev-ai-team",
        location="global",
    )

    source = types.GenerateVideosSource(
        prompt=prompt,
    )

    config = types.GenerateVideosConfig(
        aspect_ratio="16:9",
        number_of_videos=number_of_videos,
        duration_seconds=duration_seconds,
        person_generation="allow_all",
        generate_audio=True,
        resolution="720p",
        seed=0,
    )

    print(f"Starting video generation with model='veo-3.1-lite-generate-001' (location='global')...")
    operation = client.models.generate_videos(
        model="veo-3.1-lite-generate-001", source=source, config=config
    )

    while not operation.done:
        print("Video has not been generated yet. Check again in 10 seconds...")
        time.sleep(10)
        operation = client.operations.get(operation)

    response = operation.result
    if not response:
        print("Error occurred while generating video.")
        sys.exit(1)

    generated_videos = response.generated_videos
    if not generated_videos:
        print("No videos were generated.")
        sys.exit(1)

    print(f"Generated {len(generated_videos)} video(s).")
    saved_files: list[Path] = []
    for idx, generated_video in enumerate(generated_videos):
        if generated_video.video:
            file_path = output_path / f"lesson_video_{idx + 1}.mp4"
            if generated_video.video.video_bytes:
                file_path.write_bytes(generated_video.video.video_bytes)
                print(f"Saved video {idx + 1} to {file_path} ({len(generated_video.video.video_bytes)} bytes)")
                saved_files.append(file_path)
            elif generated_video.video.uri:
                print(f"Video {idx + 1} URI: {generated_video.video.uri}")
            try:
                generated_video.video.show()
            except Exception:
                # .show() is for IPython/Jupyter notebooks; ignore outside notebook environment
                pass

    return saved_files


if __name__ == "__main__":
    custom_prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_PROMPT
    generate_lesson_videos(prompt=custom_prompt)
