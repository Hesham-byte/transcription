"use client";

import { useState, useCallback, useRef } from "react";

interface TranscriptionJob {
  jobId: string;
  status: "pending" | "processing" | "completed" | "failed";
  text: string | null;
  error: string | null;
  filename: string;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<TranscriptionJob | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && isValidFile(droppedFile)) {
      setFile(droppedFile);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && isValidFile(selectedFile)) {
      setFile(selectedFile);
    }
  };

  const isValidFile = (file: File): boolean => {
    const allowedTypes = [
      "video/mp4",
      "video/webm",
      "video/quicktime",
      "audio/mpeg",
      "audio/wav",
      "audio/mp4",
    ];
    const allowedExtensions = [".mp4", ".mp3", ".wav", ".m4a", ".webm", ".mov", ".mkv", ".avi", ".flac", ".ogg"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    return allowedTypes.includes(file.type) || allowedExtensions.includes(ext);
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://localhost:8000/transcribe", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();
      setJob({
        jobId: data.job_id,
        status: "pending",
        text: null,
        error: null,
        filename: file.name,
      });

      pollStatus(data.job_id);
    } catch (error) {
      console.error("Upload error:", error);
      setJob({
        jobId: "",
        status: "failed",
        text: null,
        error: "Failed to upload file. Please try again.",
        filename: file.name,
      });
    } finally {
      setIsUploading(false);
    }
  };

  const pollStatus = async (jobId: string) => {
    const checkStatus = async () => {
      try {
        const response = await fetch(`http://localhost:8000/transcribe/${jobId}`);
        if (!response.ok) throw new Error("Failed to check status");

        const data = await response.json();
        setJob({
          jobId: data.job_id,
          status: data.status,
          text: data.text,
          error: data.error,
          filename: data.filename,
        });

        if (data.status === "pending" || data.status === "processing") {
          setTimeout(checkStatus, 2000);
        }
      } catch (error) {
        console.error("Polling error:", error);
      }
    };

    checkStatus();
  };

  const clearAll = () => {
    setFile(null);
    setJob(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <main className="min-h-screen bg-linear-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="mb-12 text-center">
          <h1 className="mb-4 text-5xl font-bold tracking-tight">
            Video <span className="text-blue-400">Transcription</span>
          </h1>
          <p className="text-lg text-slate-400">
            Upload your video or audio file and get AI-powered transcription in seconds
          </p>
        </div>

        {!job && (
          <div className="mb-8">
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-200 ${
                isDragging
                  ? "border-blue-400 bg-blue-400/10"
                  : file
                  ? "border-green-400 bg-green-400/10"
                  : "border-slate-600 bg-slate-800/50 hover:border-slate-500 hover:bg-slate-800"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".mp4,.mp3,.wav,.m4a,.webm,.mov,.mkv,.avi,.flac,.ogg,video/*,audio/*"
                onChange={handleFileSelect}
                className="hidden"
              />

              {!file ? (
                <div className="space-y-4">
                  <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-slate-700">
                    <svg className="h-10 w-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-lg font-medium text-white">
                      Drop your file here, or click to browse
                    </p>
                    <p className="mt-2 text-sm text-slate-400">
                      Supports MP4, MP3, WAV, M4A, WebM, MOV, MKV, AVI, FLAC, OGG
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20">
                    <svg className="h-10 w-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-lg font-medium text-white">{file.name}</p>
                    <p className="text-sm text-slate-400">{formatFileSize(file.size)}</p>
                  </div>
                </div>
              )}
            </div>

            {file && (
              <div className="mt-6 flex gap-4">
                <button
                  onClick={handleUpload}
                  disabled={isUploading}
                  className="flex-1 rounded-xl bg-blue-500 px-6 py-4 font-semibold text-white transition-all hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isUploading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Uploading...
                    </span>
                  ) : (
                    "Start Transcription"
                  )}
                </button>
                <button
                  onClick={clearAll}
                  disabled={isUploading}
                  className="rounded-xl border-2 border-slate-600 px-6 py-4 font-semibold text-slate-300 transition-all hover:border-slate-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}

        {job && (
          <div className="rounded-2xl border border-slate-700 bg-slate-800/50 p-8">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">{job.filename}</h2>
                <p className="text-sm text-slate-400">
                  Job ID: {job.jobId.slice(0, 8)}...
                </p>
              </div>
              <div className="flex items-center gap-2">
                {job.status === "pending" && (
                  <span className="flex items-center gap-2 rounded-full bg-yellow-500/20 px-4 py-2 text-sm font-medium text-yellow-400">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-yellow-400" />
                    Pending
                  </span>
                )}
                {job.status === "processing" && (
                  <span className="flex items-center gap-2 rounded-full bg-blue-500/20 px-4 py-2 text-sm font-medium text-blue-400">
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Processing
                  </span>
                )}
                {job.status === "completed" && (
                  <span className="flex items-center gap-2 rounded-full bg-green-500/20 px-4 py-2 text-sm font-medium text-green-400">
                    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Completed
                  </span>
                )}
                {job.status === "failed" && (
                  <span className="flex items-center gap-2 rounded-full bg-red-500/20 px-4 py-2 text-sm font-medium text-red-400">
                    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    Failed
                  </span>
                )}
              </div>
            </div>

            {(job.status === "pending" || job.status === "processing") && (
              <div className="mb-6 py-4">
                {/* Animated Loader */}
                <div className="mb-6 flex justify-center">
                  {job.status === "processing" ? (
                    <div className="flex items-end gap-1">
                      {[1, 2, 3, 4, 5].map((bar) => (
                        <div
                          key={bar}
                          className="w-2 animate-pulse rounded-t bg-blue-400"
                          style={{
                            height: "40px",
                            animationDelay: `${bar * 0.1}s`,
                            animationDuration: "0.6s",
                          }}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="relative flex h-20 w-20 items-center justify-center">
                      <div className="absolute h-20 w-20 animate-ping rounded-full bg-blue-500/30"></div>
                      <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-slate-800">
                        <svg className="h-8 w-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                    </div>
                  )}
                </div>

                {/* Progress Bar */}
                <div className="mb-4 h-3 overflow-hidden rounded-full bg-slate-700">
                  <div 
                    className={`h-full rounded-full bg-linear-to-r from-blue-500 to-blue-400 transition-all duration-1000 ${
                      job.status === "processing" ? "animate-pulse" : ""
                    }`}
                    style={{ 
                      width: job.status === "processing" ? "80%" : "30%",
                    }} 
                  />
                </div>

                {/* Status Text */}
                <div className="text-center">
                  <p className="text-lg font-medium text-white">
                    {job.status === "processing" && "AI is transcribing your audio..."}
                    {job.status === "pending" && "Waiting in queue..."}
                  </p>
                  <p className="mt-1 text-sm text-slate-400">
                    {job.status === "processing" && "This may take a few minutes depending on video length"}
                    {job.status === "pending" && "Your job is queued and will start soon"}
                  </p>
                </div>
              </div>
            )}

            {job.error && (
              <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
                <p className="text-red-400">{job.error}</p>
              </div>
            )}

            {job.text && (
              <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-6">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="font-semibold text-slate-300">Transcription</h3>
                  <button
                    onClick={() => navigator.clipboard.writeText(job.text || "")}
                    className="flex items-center gap-2 rounded-lg bg-slate-700 px-3 py-2 text-sm transition-colors hover:bg-slate-600"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy
                  </button>
                </div>
                <p className="whitespace-pre-wrap text-lg leading-relaxed text-slate-200">
                  {job.text}
                </p>
              </div>
            )}

            <div className="mt-6 flex justify-center">
              <button
                onClick={clearAll}
                className="flex items-center gap-2 rounded-xl bg-slate-700 px-6 py-3 font-semibold text-white transition-colors hover:bg-slate-600"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Transcribe Another File
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
