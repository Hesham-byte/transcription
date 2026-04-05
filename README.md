# Video Transcription App

![Demo](demo.gif)

A full-stack application for transcribing video and audio files using OpenAI's Whisper AI model.

## Architecture

```
trans/
├── ai/                 # FastAPI backend
│   ├── main.py        # API endpoints & transcription logic
│   ├── requirements.txt
│   └── .venv/         # Python virtual environment
│
├── transcript/        # Next.js frontend
│   ├── src/app/
│   │   └── page.tsx   # Main transcription UI
│   └── package.json
│
├── .gitignore
└── README.md
```

## Features

- **File Upload**: Drag & drop or click to upload video/audio files
- **AI Transcription**: Powered by OpenAI Whisper (base model)
- **Real-time Status**: Polling-based progress updates with animated loaders
- **Copy Results**: One-click copy of transcription text
- **Supported Formats**: MP4, MP3, WAV, M4A, WebM, MOV, MKV, AVI, FLAC, OGG

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- ffmpeg (for audio processing)

### Install ffmpeg (macOS)

```bash
brew install ffmpeg
```

### Backend Setup

```bash
cd ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend runs at http://localhost:8000

### Frontend Setup

```bash
cd transcript
npm install
npm run dev
```

Frontend runs at http://localhost:3000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/transcribe` | Upload file for async transcription |
| `GET` | `/transcribe/{job_id}` | Check transcription status |
| `POST` | `/transcribe/sync` | Synchronous transcription |
| `GET` | `/health` | Health check |

## Usage

1. Open http://localhost:3000
2. Drag & drop or click to select a video/audio file
3. Click "Start Transcription"
4. Wait for processing (animated loader shows progress)
5. Copy the transcription result

## Tech Stack

**Backend:**
- FastAPI
- OpenAI Whisper
- Python-multipart (file uploads)

**Frontend:**
- Next.js 16
- React 19
- Tailwind CSS v4
- TypeScript

## Project Structure

### Backend (`ai/`)

- **Async Processing**: File uploads return immediately with `job_id`
- **Background Tasks**: Whisper runs in background using FastAPI's `BackgroundTasks`
- **In-Memory Storage**: Job status stored in dict (use Redis/DB for production)

### Frontend (`transcript/`)

- **Drag & Drop**: Native HTML5 drag and drop with visual feedback
- **Status Polling**: Polls every 2 seconds for job status updates
- **Animated UI**: Audio wave animation during processing
- **Dark Theme**: Slate gradient background with blue accents

## Development

### Backend Hot Reload

FastAPI's `--reload` flag watches for code changes automatically.

### Frontend Hot Reload

Next.js dev server auto-reloads on file changes.

## Production Considerations

1. **Database**: Replace in-memory job store with Redis/PostgreSQL
2. **File Storage**: Use S3/Cloud storage instead of local filesystem
3. **Queue**: Implement Celery/RQ for distributed processing
4. **Authentication**: Add API key or OAuth authentication
5. **Rate Limiting**: Prevent abuse with request throttling
6. **Monitoring**: Add logging and metrics (Prometheus/Grafana)

## License

MIT
