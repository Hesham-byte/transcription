# Video Transcription API - Project Structure

## Overview
FastAPI-based service for transcribing video/audio files using OpenAI Whisper.

## Project Structure

```
ai/
├── .venv/                  # Virtual environment
├── .md/                    # Documentation
│   └── structure.md        # This file
├── uploads/                # Temporary upload storage
├── main.py                 # Main FastAPI application
├── requirements.txt        # Python dependencies
└── README.md              # Project documentation (optional)
```

## Architecture

### Core Components

| Component | Description |
|-----------|-------------|
| `FastAPI` | Web framework for API endpoints |
| `Whisper` | OpenAI's speech recognition model |
| `BackgroundTasks` | Async processing for transcription |
| `In-Memory Store` | Job status tracking (Redis/DB for production) |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API info |
| `GET` | `/health` | Health check |
| `POST` | `/transcribe` | Async transcription - returns job_id |
| `GET` | `/transcribe/{job_id}` | Poll transcription status |
| `POST` | `/transcribe/sync` | Sync transcription - waits for result |

### Data Models

#### TranscriptionResponse
- `job_id`: str - Unique identifier
- `status`: str - pending/processing/completed/failed
- `text`: Optional[str] - Transcription result
- `error`: Optional[str] - Error message if failed

#### TranscriptionStatus
- `job_id`: str
- `status`: str
- `text`: Optional[str]
- `error`: Optional[str]
- `filename`: Optional[str]

## Supported Formats

- Video: `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`
- Audio: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`

## Workflow

### Async Transcription
```
Client → POST /transcribe (upload file)
       ← {job_id, status: "pending"}
       
Client → GET /transcribe/{job_id} (poll)
       ← {status: "processing"} → wait
       ← {status: "completed", text: "..."}
```

### Sync Transcription
```
Client → POST /transcribe/sync (upload file)
       ← wait for processing
       ← {status: "completed", text: "...", segments: [...]}
```

## Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `openai-whisper` - Speech recognition
- `python-multipart` - File upload handling
- `aiofiles` - Async file operations

## Environment

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn main:app --reload
```

## Production Considerations

1. **Storage**: Replace in-memory job store with Redis/PostgreSQL
2. **File Storage**: Use S3/Cloud storage instead of local filesystem
3. **Queue**: Use Celery/RQ for distributed task processing
4. **Monitoring**: Add logging and metrics collection
5. **Auth**: Add API key authentication
6. **Rate Limiting**: Prevent abuse with request throttling
