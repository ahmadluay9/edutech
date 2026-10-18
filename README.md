# EduTech Interactive Video Roleplay Prototype

Prototipe aplikasi pembelajaran percakapan bahasa Inggris interaktif (*Self-Study Lesson View* bergaya EF English Live) menggunakan:
- **Veo 3.1 Lite (`veo-3.1-lite-generate-001`)** via `google-genai` SDK (`project="eikon-dev-ai-team"`, `location="global"`) untuk men-generate video karakter berbicara.
- **Interactive Video Player (HTML5 Custom Timeline)** dengan titik *checkpoint* otomatis (*auto-pause* di detik `2.25s` dan `7.75s`, transisi dari *skeleton loader* ke pilihan ganda `A / B / C` + tombol mikrofon, serta tombol *Replay* di tengah video).
- **Open-Source Speech Recognition & Pronunciation Evaluation** menggunakan *Web Speech API* + `MediaRecorder` dan algoritma pencocokan teks/kata berbasis Levenshtein (`rapidfuzz`) di backend **FastAPI**.

---

## Struktur Proyek

- [`src/edutech/generate_video.py`](file:///root/edutech/src/edutech/generate_video.py) — Script generator video menggunakan `veo-3.1-lite-generate-001` (`location="global"`), menyimpan 4 variasi video ke `static/videos/lesson_video_1..4.mp4`.
- [`src/edutech/speech_eval.py`](file:///root/edutech/src/edutech/speech_eval.py) — Modul evaluasi ucapan & skor pelafalan tingkat kata (*word-level alignment*) berbasis `rapidfuzz`.
- [`src/edutech/main.py`](file:///root/edutech/src/edutech/main.py) — Server backend FastAPI (`/api/lesson`, `/api/evaluate-speech`, `/api/transcribe-audio`, `/api/generate-video`).
- [`static/index.html`](file:///root/edutech/static/index.html) — Antarmuka pengguna interaktif (*split-screen*, *skeleton placeholders*, *checkpoint markers*, input mikrofon, dan simulator suara).
- [`tests/test_app.py`](file:///root/edutech/tests/test_app.py) — Pengujian otomatis logika evaluasi suara dan endpoint server.

---

## Cara Menjalankan

### 1. Menjalankan Server Web Prototype
```bash
uv run edutech
# atau
.venv/bin/uvicorn edutech.main:app --host 0.0.0.0 --port 8085
```
Buka **`http://localhost:8085`** di browser.

### 2. Men-generate Video Baru dengan Veo 3.1 Lite
```bash
.venv/bin/python src/edutech/generate_video.py
```
Atau klik tombol **`+ Veo 3.1 Video`** langsung dari header aplikasi web.

### 3. Menjalankan Pengujian
```bash
.venv/bin/python tests/test_app.py
```
