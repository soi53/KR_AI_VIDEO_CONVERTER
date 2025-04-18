"""
환경 변수를 로드하고 애플리케이션 설정을 관리하는 모듈입니다.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from dotenv import load_dotenv
from loguru import logger

# .env 파일 로드
load_dotenv()

# 기본 경로
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path("/data")

# OpenAI API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# 언어 설정
DEFAULT_SOURCE_LANGUAGE = os.getenv("DEFAULT_SOURCE_LANGUAGE", "ko")
SUPPORTED_LANGUAGES = os.getenv("SUPPORTED_LANGUAGES", "en,ja,zh,de,id").split(",")

# 언어 코드와 이름 매핑
LANGUAGE_NAMES = {
    "ko": "한국어",
    "en": "영어 (English)",
    "ja": "일본어 (日本語)",
    "zh": "중국어 (中文)",
    "de": "독일어 (Deutsch)",
    "id": "인도네시아어 (Bahasa Indonesia)"
}

# 파일 설정
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
ALLOWED_VIDEO_FORMATS = os.getenv("ALLOWED_VIDEO_FORMATS", "mp4,avi").split(",")

# 파일 저장 경로
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "/data/processed"))
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "/data/results"))

# Whisper 설정
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
WHISPER_TEMPERATURE = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
WHISPER_TIMESTAMP_GRANULARITY = os.getenv("WHISPER_TIMESTAMP_GRANULARITY", "segment")

# Whisper 모델 옵션
WHISPER_MODEL_OPTIONS = {
    "tiny": "초소형 (가장 빠름, 낮은 정확도)",
    "base": "기본형 (빠름, 기본 정확도)",
    "small": "소형 (중간 속도, 좋은 정확도)",
    "medium": "중형 (느림, 높은 정확도)",
    "large-v3": "대형 (가장 느림, 최고 정확도)"
}

# Whisper API 설정
WHISPER_API_URL = os.getenv("WHISPER_API_URL", "http://whisper:8000")

# TTS 모델 설정
TTS_MODEL = os.getenv("TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
TTS_SPEAKERS_FILE = os.getenv("TTS_SPEAKERS_FILE", "/app/config/tts_speakers.json")

# 디버그 모드
DEBUG = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]

# 모든 디렉토리가 존재하는지 확인하고 필요한 경우 생성
for directory in [UPLOAD_DIR, PROCESSED_DIR, RESULTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# 환경 변수 검증
if not OPENAI_API_KEY and not DEBUG:
    logger.warning("OPENAI_API_KEY가 설정되지 않았습니다. 번역 기능이 작동하지 않을 수 있습니다.")

# API 키와 같은 민감한 정보는 로깅하지 않도록 주의
logger.debug(f"애플리케이션 설정이 로드되었습니다. 디버그 모드: {DEBUG}")
logger.debug(f"지원 언어: {', '.join(SUPPORTED_LANGUAGES)}")
logger.debug(f"Whisper 모델: {WHISPER_MODEL_SIZE}")
logger.debug(f"TTS 모델: {TTS_MODEL}") 