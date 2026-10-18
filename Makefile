.PHONY: help install sync run dev generate-video test clean

PYTHON := .venv/bin/python
UVICORN := .venv/bin/uvicorn
HOST ?= 0.0.0.0
PORT ?= 8085
PROMPT ?=

help: ## Tampilkan daftar perintah Makefile yang tersedia
	@echo "EduTech Interactive Video Roleplay - Makefile Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install / sinkronisasi dependencies menggunakan uv
	uv sync

sync: install ## Alias untuk make install

run: ## Jalankan server aplikasi FastAPI (default port: 8085)
	$(UVICORN) edutech.main:app --host $(HOST) --port $(PORT)

dev: ## Jalankan server FastAPI dalam mode auto-reload untuk development
	$(UVICORN) edutech.main:app --host $(HOST) --port $(PORT) --reload

generate-video: ## Generate video pembelajaran baru menggunakan Veo 3.1 Lite (opsional: PROMPT="...")
	@if [ -n "$(PROMPT)" ]; then \
		$(PYTHON) src/edutech/generate_video.py "$(PROMPT)"; \
	else \
		$(PYTHON) src/edutech/generate_video.py; \
	fi

test: ## Jalankan unit & integration tests (pastikan server berjalan untuk live test)
	$(PYTHON) -c "from tests.test_app import test_speech_evaluation_logic; test_speech_evaluation_logic(); print('Unit tests passed!')"

test-all: ## Jalankan seluruh pengujian termasuk live endpoint server
	$(PYTHON) tests/test_app.py

clean: ## Bersihkan file cache Python
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
