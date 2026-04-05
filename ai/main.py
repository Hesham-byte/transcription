import os
import uuid
import subprocess
import whisper
import yt_dlp
import requests
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


class URLInput(BaseModel):
    url: str
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


@app.post("/transcribe/url", response_model=TranscriptionResponse)
async def transcribe_from_url(
    background_tasks: BackgroundTasks,
    url_input: URLInput
):
    """
    Transcribe a video from a URL (YouTube, direct video link, etc.).
    Returns immediately with a job_id to poll for results.
    """
    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}.mp4")
    
    # Initialize job status
    transcription_jobs[job_id] = {
        "status": "pending",
        "filename": url_input.filename or "video_from_url",
        "text": None,
        "error": None
    }
    
    # Start background download and transcription
    background_tasks.add_task(process_url_transcription, job_id, url_input.url, file_path)
    
    return TranscriptionResponse(job_id=job_id, status="pending")


def process_url_transcription(job_id: str, url: str, file_path: str):
    """Background task to stream video from URL using ffmpeg and transcribe."""
    audio_path = file_path.rsplit('.', 1)[0] + '.mp3'
    
    try:
        transcription_jobs[job_id]["status"] = "downloading"
        
        # Use ffmpeg to stream from URL and extract audio directly
        # This avoids downloading the full video file
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', url,           # Input from URL (stream)
            '-vn',               # No video
            '-acodec', 'libmp3lame',
            '-ar', '16000',      # Sample rate that whisper prefers
            '-ac', '1',          # Mono audio
            '-q:a', '2',         # Quality
            '-y',                # Overwrite output
            audio_path
        ]
        
        try:
            # Run ffmpeg to extract audio from stream
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                # If ffmpeg fails (e.g., unsupported URL), try yt-dlp as fallback
                raise Exception(f"ffmpeg failed: {result.stderr}")
                
        except Exception as ffmpeg_error:
            # Fallback: try yt-dlp for YouTube/other platforms
            transcription_jobs[job_id]["status"] = "downloading"
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_path,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        # Check if audio file was created
        if not os.path.exists(audio_path):
            raise Exception("Failed to extract audio from URL")
        
        transcription_jobs[job_id]["status"] = "processing"
        
        # Transcribe the audio
        result = model.transcribe(audio_path)
        
        transcription_jobs[job_id]["status"] = "completed"
        transcription_jobs[job_id]["text"] = result["text"]
        transcription_jobs[job_id]["segments"] = result.get("segments", [])
        
        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
    except Exception as e:
        transcription_jobs[job_id]["status"] = "failed"
        transcription_jobs[job_id]["error"] = str(e)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(file_path):
            os.remove(file_path)
