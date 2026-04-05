import os
import uuid
import whisper
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict
import aiofiles

app = FastAPI(
    title="Video Transcription API",
    description="API for transcribing video files using Whisper",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Whisper model once at startup
model = whisper.load_model("base")

# In-memory storage for job status (use Redis/DB in production)
transcription_jobs: Dict[str, Dict] = {}

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class TranscriptionResponse(BaseModel):
    job_id: str
    status: str
    text: Optional[str] = None
    error: Optional[str] = None


class TranscriptionStatus(BaseModel):
    job_id: str
    status: str
    text: Optional[str] = None
    error: Optional[str] = None
    filename: Optional[str] = None


def process_transcription(job_id: str, file_path: str, filename: str):
    """Background task to transcribe video/audio."""
    try:
        transcription_jobs[job_id]["status"] = "processing"
        
        result = model.transcribe(file_path)
        
        transcription_jobs[job_id]["status"] = "completed"
        transcription_jobs[job_id]["text"] = result["text"]
        transcription_jobs[job_id]["segments"] = result.get("segments", [])
        
        # Cleanup uploaded file
        os.remove(file_path)
        
    except Exception as e:
        transcription_jobs[job_id]["status"] = "failed"
        transcription_jobs[job_id]["error"] = str(e)
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/")
async def root():
    return {"message": "Video Transcription API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": "whisper-base"}


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a video or audio file for transcription.
    Returns immediately with a job_id to poll for results.
    """
    # Validate file type
    allowed_extensions = {'.mp4', '.mp3', '.wav', '.m4a', '.webm', '.mov', '.mkv', '.avi', '.flac', '.ogg'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded file
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}{file_ext}")
    
    try:
        async with aiofiles.open(file_path, 'wb') as buffer:
            content = await file.read()
            await buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Initialize job status
    transcription_jobs[job_id] = {
        "status": "pending",
        "filename": file.filename,
        "text": None,
        "error": None
    }
    
    # Start background transcription
    background_tasks.add_task(process_transcription, job_id, file_path, file.filename)
    
    return TranscriptionResponse(job_id=job_id, status="pending")


@app.get("/transcribe/{job_id}", response_model=TranscriptionStatus)
async def get_transcription_status(job_id: str):
    """Check the status of a transcription job."""
    if job_id not in transcription_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = transcription_jobs[job_id]
    return TranscriptionStatus(
        job_id=job_id,
        status=job["status"],
        text=job.get("text"),
        error=job.get("error"),
        filename=job.get("filename")
    )


@app.post("/transcribe/sync")
async def transcribe_video_sync(file: UploadFile = File(...)):
    """
    Synchronous transcription - waits for transcription to complete.
    For small files only (< 10MB recommended).
    """
    allowed_extensions = {'.mp4', '.mp3', '.wav', '.m4a', '.webm', '.mov', '.mkv', '.avi', '.flac', '.ogg'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}{file_ext}")
    
    try:
        async with aiofiles.open(file_path, 'wb') as buffer:
            content = await file.read()
            await buffer.write(content)
        
        # Transcribe immediately
        result = model.transcribe(file_path)
        
        os.remove(file_path)
        
        return {
            "job_id": job_id,
            "status": "completed",
            "text": result["text"],
            "language": result.get("language"),
            "segments": result.get("segments", [])
        }
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
