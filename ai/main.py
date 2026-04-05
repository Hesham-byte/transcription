import os
import uuid
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
    """Background task to download video from URL and transcribe."""
    try:
        transcription_jobs[job_id]["status"] = "downloading"
        
        # Try yt-dlp first (for YouTube and other platforms)
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': file_path,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }] if False else [],  # Download video, extract audio later if needed
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                # Update file_path if yt-dlp changed extension
                if os.path.exists(downloaded_file):
                    file_path = downloaded_file
                elif os.path.exists(file_path):
                    pass
                else:
                    # Try to find the downloaded file
                    base_path = file_path.rsplit('.', 1)[0]
                    for ext in ['.mp4', '.webm', '.mkv', '.mp3', '.m4a']:
                        if os.path.exists(base_path + ext):
                            file_path = base_path + ext
                            break
        except Exception as ydl_error:
            # Fallback: try direct download with requests
            if not os.path.exists(file_path):
                response = requests.get(url, stream=True, timeout=60)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
        
        transcription_jobs[job_id]["status"] = "processing"
        
        # Transcribe
        result = model.transcribe(file_path)
        
        transcription_jobs[job_id]["status"] = "completed"
        transcription_jobs[job_id]["text"] = result["text"]
        transcription_jobs[job_id]["segments"] = result.get("segments", [])
        
        # Cleanup
        os.remove(file_path)
        
    except Exception as e:
        transcription_jobs[job_id]["status"] = "failed"
        transcription_jobs[job_id]["error"] = str(e)
        if os.path.exists(file_path):
            os.remove(file_path)
