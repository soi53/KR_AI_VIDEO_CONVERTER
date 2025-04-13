"""
OpenAI Whisper STT API 서버
"""
import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

import uvicorn
import whisper
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel

# API 애플리케이션 초기화
app = FastAPI(
    title="OpenAI Whisper STT API",
    description="비디오 파일에서 자막을 추출하는 API",
    version="1.0.0"
)

# 로깅 설정
logger.remove()
logger.add(sys.stderr, format="{time} - {name} - {level} - {message}", level="INFO")
logger.add("whisper_api.log", rotation="10 MB", retention="3 days", level="DEBUG")

# 데이터 디렉토리 설정
UPLOADS_DIR = Path("/data/uploads")
PROCESSED_DIR = Path("/data/processed")

# 디렉토리 확인
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 모델 설정
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
WHISPER_TEMPERATURE = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
WHISPER_RESPONSE_FORMAT = os.getenv("WHISPER_RESPONSE_FORMAT", "json")

# 유효한 모델 크기 목록
VALID_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

# 응답 모델
class TranscriptionResponse(BaseModel):
    status: str
    message: str
    subtitle_path: Optional[str] = None
    error: Optional[str] = None
    processing_time: float

# 전역 변수로 모델 인스턴스 저장 (모델 재사용)
_model = None

def get_model():
    """Whisper 모델 인스턴스를 반환합니다."""
    global _model
    if _model is None:
        # 모델 크기 검증
        model_size = WHISPER_MODEL_SIZE
        if model_size not in VALID_MODELS:
            logger.warning(f"지원되지 않는 모델 크기: {model_size}, large-v3로 대체됩니다.")
            model_size = "large-v3"
            
        logger.info(f"OpenAI Whisper 모델 로드: {model_size}")
        try:
            _model = whisper.load_model(model_size)
            logger.info(f"OpenAI Whisper 모델 로드 완료: {model_size}")
        except Exception as e:
            logger.error(f"OpenAI Whisper 모델 로드 실패: {str(e)}")
            raise e
    return _model

def ms_to_srt_time(ms: int) -> str:
    """밀리초를 SRT 시간 형식(HH:MM:SS,mmm)으로 변환합니다."""
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

def extract_audio_from_video(video_path: Path) -> str:
    """
    비디오 파일에서 오디오 추출 (WAV 형식)
    
    Args:
        video_path: 비디오 파일 경로
        
    Returns:
        str: 추출된 오디오 파일 경로
    """
    try:
        # 임시 오디오 파일 경로 생성
        audio_file = PROCESSED_DIR / f"audio_{video_path.stem}.wav"
        
        # FFmpeg 명령어 실행 (오디오 추출)
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vn",                    # 비디오 스트림 제외
            "-map", "0:a?",           # 오디오 스트림 명시적 선택 (존재하는 경우)
            "-c:a", "pcm_s16le",      # PCM 16bit 인코더 사용
            "-ac", "1",               # 모노 채널
            "-ar", "16000",           # 16kHz 샘플링
            "-y",                     # 기존 파일 덮어쓰기
            str(audio_file)
        ]
        
        logger.debug(f"FFmpeg 명령어 실행: {' '.join(cmd)}")
        
        # FFmpeg 프로세스 실행
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 오류 확인
        if process.returncode != 0:
            logger.error(f"FFmpeg 오류: {process.stderr}")
            
            # 첫 번째 방법이 실패하면 대체 명령 시도
            logger.info("대체 FFmpeg 명령 시도...")
            cmd_alt = [
                "ffmpeg", "-i", str(video_path),
                "-f", "wav",          # 강제 WAV 형식
                "-vn",                # 비디오 스트림 제외
                "-acodec", "pcm_s16le", # PCM 16bit 인코더
                "-y",                 # 기존 파일 덮어쓰기
                str(audio_file)
            ]
            
            logger.debug(f"대체 FFmpeg 명령어: {' '.join(cmd_alt)}")
            
            process_alt = subprocess.run(
                cmd_alt,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process_alt.returncode != 0:
                logger.error(f"대체 FFmpeg 명령 오류: {process_alt.stderr}")
                raise ValueError(f"오디오 추출 실패: {process_alt.stderr}")
        
        logger.debug(f"오디오 추출 완료: {audio_file}")
        return str(audio_file)
        
    except Exception as e:
        logger.error(f"오디오 추출 중 오류: {str(e)}")
        raise ValueError(f"오디오 추출 중 오류: {str(e)}")

@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {"status": "ok", "message": "OpenAI Whisper STT API is running"}

@app.get("/health")
async def health_check():
    """API 헬스 체크 엔드포인트"""
    return {
        "status": "healthy", 
        "whisper_model": WHISPER_MODEL_SIZE,
        "beam_size": WHISPER_BEAM_SIZE,
        "temperature": WHISPER_TEMPERATURE
    }

@app.post("/api/extract_subtitles")
async def extract_subtitles(
    video_path: str = Form(...),
    language: str = Form("ko"),
    model_size: Optional[str] = Form(None),
    temperature: Optional[float] = Form(None),
    initial_prompt: Optional[str] = Form(None),
    timestamp_granularity: Optional[str] = Form("segment"),
):
    """
    비디오에서 자막을 추출하여 SRT 파일로 저장합니다.
    
    Args:
        video_path: Docker 볼륨 내 비디오 파일 경로 (상대 경로는 /data 기준)
        language: 자막 언어 코드 (기본값: ko)
        model_size: 사용할 Whisper 모델 크기 (기본값: 환경 변수)
        temperature: 샘플링 온도 (기본값: 환경 변수)
        initial_prompt: 초기 프롬프트 텍스트
        timestamp_granularity: 타임스탬프 정밀도 ("segment" 또는 "word")
        
    Returns:
        TranscriptionResponse: 처리 결과 및 자막 파일 경로
    """
    start_time = time.time()
    
    try:
        # 경로 정규화 (상대 경로는 /data 기준으로 처리)
        if not video_path.startswith('/'):
            video_path = f"/data/{video_path}"
        
        video_path_obj = Path(video_path)
        
        if not video_path_obj.exists():
            logger.error(f"비디오 파일이 존재하지 않습니다: {video_path}")
            return TranscriptionResponse(
                status="error",
                message="비디오 파일이 존재하지 않습니다",
                error=f"File not found: {video_path}",
                processing_time=time.time() - start_time
            )
        
        # 모델 선택 (API 호출에서 지정된 경우 우선)
        if model_size and model_size in VALID_MODELS:
            # 모델이 현재 로드된 모델과 다른 경우 재설정
            global _model
            if _model is not None and model_size != WHISPER_MODEL_SIZE:
                _model = None
                
            model = whisper.load_model(model_size)
            logger.info(f"선택된 모델 사용: {model_size}")
        else:
            # 기본 모델 사용
            model = get_model()
        
        # 파일 ID 추출
        file_id = video_path_obj.stem.split("_")[-1]
        
        # 출력 파일 경로 설정
        output_path = PROCESSED_DIR / f"subtitle_{file_id}.srt"
        
        logger.info(f"OpenAI Whisper 처리 시작: {video_path}")
        
        # 비디오에서 오디오 추출
        audio_path = extract_audio_from_video(video_path_obj)
        logger.info(f"오디오 추출 완료: {audio_path}")
        
        # 음성 인식 실행
        # language='ko'와 같이 언어 코드를 명시할 수 있음 (기본은 auto-detect)
        transcribe_options = {
            "beam_size": WHISPER_BEAM_SIZE,
            "language": language,
            "temperature": temperature if temperature is not None else WHISPER_TEMPERATURE,
            "word_timestamps": timestamp_granularity == "word",
        }
        
        # 초기 프롬프트가 제공된 경우 추가
        if initial_prompt:
            transcribe_options["initial_prompt"] = initial_prompt
            
        # 추출된 오디오로 트랜스크립션 실행
        result = model.transcribe(audio_path, **transcribe_options)
        
        # 결과를 SRT 형식으로 변환하여 파일로 저장
        with open(output_path, "w", encoding="utf-8") as f:
            i = 1
            
            if not result["segments"]:
                logger.warning("자막 추출 결과가 비어 있습니다.")
            
            for segment in result["segments"]:
                try:
                    start_time_ms = int(segment["start"] * 1000)
                    end_time_ms = int(segment["end"] * 1000)
                    text = segment["text"].strip()
                    
                    start_time_str = ms_to_srt_time(start_time_ms)
                    end_time_str = ms_to_srt_time(end_time_ms)
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_time_str} --> {end_time_str}\n")
                    f.write(f"{text}\n\n")
                    i += 1
                except Exception as e:
                    logger.error(f"세그먼트 {i} 처리 중 오류: {str(e)}")
                    continue
        
        processing_time = time.time() - start_time
        logger.info(f"자막 추출 완료: {output_path} (소요 시간: {processing_time:.2f}초)")
        
        # 볼륨 기준 상대 경로로 반환
        relative_path = str(output_path).replace("/data/", "", 1)
        
        return TranscriptionResponse(
            status="success",
            message="자막 추출이 완료되었습니다",
            subtitle_path=relative_path,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"자막 추출 중 예상치 못한 오류: {str(e)}")
        return TranscriptionResponse(
            status="error",
            message="자막 처리 중 오류가 발생했습니다",
            error=str(e),
            processing_time=time.time() - start_time
        )

# 직접 실행 시 API 서버 시작
if __name__ == "__main__":
    logger.info("OpenAI Whisper STT API 서버 시작")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="info") 