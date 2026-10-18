from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel
import uvicorn

from edutech.generate_video import DEFAULT_PROMPT, generate_lesson_videos
from edutech.speech_eval import (
    DialogOption,
    SpeechEvaluationResult,
    evaluate_spoken_response,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
VIDEOS_DIR = STATIC_DIR / "videos"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="EduTech Interactive Video Roleplay Prototype",
    description="EF English Live style interactive speaking & roleplay lesson with Veo 3.1 Lite & Open-Source Speech Evaluation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckpointConfig(BaseModel):
    id: int
    title: str
    speaker_prompt: str
    pause_at_sec: float
    replay_start_sec: float
    resume_from_sec: float
    options: list[DialogOption]


class LessonConfig(BaseModel):
    lesson_id: str
    title: str
    subtitle: str
    default_video_url: str
    available_videos: list[dict[str, str]]
    checkpoints: list[CheckpointConfig]


DEFAULT_CHECKPOINTS: list[CheckpointConfig] = [
    CheckpointConfig(
        id=1,
        title="Checkpoint 1: Greeting & Current Activity",
        speaker_prompt="Hi, and what are you reading?",
        pause_at_sec=2.25,
        replay_start_sec=0.0,
        resume_from_sec=4.65,
        options=[
            DialogOption(
                id="A",
                text="I'm reading a business news summary.",
                is_correct=True,
                explanation="Tepat! Menjawab langsung pertanyaan 'What are you reading?' dengan objek bacaan yang sedang dibaca.",
            ),
            DialogOption(
                id="B",
                text="Yes, the stock price has increased a lot.",
                is_correct=False,
                explanation="Kurang tepat. Pertanyaan 'What are you reading?' adalah WH-question, bukan Yes/No question.",
            ),
            DialogOption(
                id="C",
                text="I agree with you that it's disgusting.",
                is_correct=False,
                explanation="Kurang tepat. Lawan bicara belum menyampaikan opini apa pun untuk disetujui.",
            ),
        ],
    ),
    CheckpointConfig(
        id=2,
        title="Checkpoint 2: Market Discussion",
        speaker_prompt="Oh, interesting! How is the stock market doing today?",
        pause_at_sec=7.75,
        replay_start_sec=4.65,
        resume_from_sec=7.95,
        options=[
            DialogOption(
                id="A",
                text="I'm reading a business news summary.",
                is_correct=False,
                explanation="Kurang tepat. Anda sudah menyebutkan ini sebelumnya; sekarang lawan bicara menanyakan kondisi pasar saham hari ini.",
            ),
            DialogOption(
                id="B",
                text="Yes, the stock price has increased a lot.",
                is_correct=True,
                explanation="Tepat! Respons ini menjelaskan perkembangan positif harga saham di pasar hari ini.",
            ),
            DialogOption(
                id="C",
                text="I agree with you that it's disgusting.",
                is_correct=False,
                explanation="Kurang tepat dan tidak sesuai dengan konteks pertanyaan tentang kondisi pasar saham.",
            ),
        ],
    ),
]


def get_available_videos() -> list[dict[str, str]]:
    videos: list[dict[str, str]] = []
    # Prioritize lesson_video_2.mp4 as the cleanest take, then list all generated videos
    ordered_names = [
        ("lesson_video_2.mp4", "Veo 3.1 Lite - Take 2 (Recommended)"),
        ("lesson_video_1.mp4", "Veo 3.1 Lite - Take 1"),
        ("lesson_video_3.mp4", "Veo 3.1 Lite - Take 3"),
        ("lesson_video_4.mp4", "Veo 3.1 Lite - Take 4"),
    ]
    seen: set[str] = set()
    for fname, label in ordered_names:
        fpath = VIDEOS_DIR / fname
        if fpath.exists():
            videos.append({"name": fname, "label": label, "url": f"/static/videos/{fname}"})
            seen.add(fname)

    for fpath in sorted(VIDEOS_DIR.glob("*.mp4")):
        if fpath.name not in seen:
            videos.append(
                {
                    "name": fpath.name,
                    "label": fpath.stem.replace("_", " ").title(),
                    "url": f"/static/videos/{fpath.name}",
                }
            )
    return videos


class EvaluateSpeechRequest(BaseModel):
    transcript: str
    checkpoint_id: int = 1
    pass_threshold: float = 65.0


class GenerateVideoRequest(BaseModel):
    prompt: str = DEFAULT_PROMPT
    number_of_videos: int = 1
    duration_seconds: int = 8


@app.get("/api/lesson", response_model=LessonConfig)
async def get_lesson() -> LessonConfig:
    videos = get_available_videos()
    default_url = videos[0]["url"] if videos else "/static/videos/lesson_video_2.mp4"
    return LessonConfig(
        lesson_id="business-news-roleplay-01",
        title="Self-Study Lesson: Talking About Business News",
        subtitle="Listen to your colleague, choose the best response, and speak it aloud.",
        default_video_url=default_url,
        available_videos=videos,
        checkpoints=DEFAULT_CHECKPOINTS,
    )


@app.post("/api/evaluate-speech", response_model=SpeechEvaluationResult)
async def evaluate_speech_endpoint(req: EvaluateSpeechRequest) -> SpeechEvaluationResult:
    checkpoint = next(
        (cp for cp in DEFAULT_CHECKPOINTS if cp.id == req.checkpoint_id),
        DEFAULT_CHECKPOINTS[0],
    )
    return evaluate_spoken_response(
        transcript=req.transcript,
        options=checkpoint.options,
        pass_threshold=req.pass_threshold,
    )


@app.post("/api/transcribe-audio", response_model=SpeechEvaluationResult)
async def transcribe_and_evaluate_audio(
    audio: UploadFile = File(...),
    checkpoint_id: int = Form(1),
    client_transcript: str = Form(""),
) -> SpeechEvaluationResult:
    checkpoint = next(
        (cp for cp in DEFAULT_CHECKPOINTS if cp.id == checkpoint_id),
        DEFAULT_CHECKPOINTS[0],
    )

    # If the browser Web Speech API already produced a clear transcript, evaluate immediately
    transcript_text = client_transcript.strip()

    # Otherwise, transcribe the recorded audio bytes using Gemini on Vertex AI (global)
    if not transcript_text:
        audio_bytes = await audio.read()
        if audio_bytes:
            try:
                client = genai.Client(
                    vertexai=True,
                    project="eikon-dev-ai-team",
                    location="global",
                )
                mime_type = audio.content_type or "audio/webm"
                if ";" in mime_type:
                    mime_type = mime_type.split(";")[0].strip()
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        (
                            "Transcribe the exact English words spoken in this audio clip. "
                            "Return ONLY the raw spoken English transcript without quotes or explanation. "
                            "If no speech is audible, return an empty string."
                        ),
                    ],
                )
                transcript_text = (response.text or "").strip()
            except Exception as exc:
                print(f"Audio transcription fallback error: {exc}")

    return evaluate_spoken_response(
        transcript=transcript_text,
        options=checkpoint.options,
        pass_threshold=65.0,
    )


@app.post("/api/generate-video")
async def generate_video_endpoint(req: GenerateVideoRequest) -> dict[str, object]:
    try:
        saved = generate_lesson_videos(
            prompt=req.prompt,
            output_dir=VIDEOS_DIR,
            number_of_videos=req.number_of_videos,
            duration_seconds=req.duration_seconds,
        )
        return {
            "status": "ok",
            "generated_count": len(saved),
            "videos": get_available_videos(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def run() -> None:
    uvicorn.run("edutech.main:app", host="0.0.0.0", port=8085, reload=False)



if __name__ == "__main__":
    run()
