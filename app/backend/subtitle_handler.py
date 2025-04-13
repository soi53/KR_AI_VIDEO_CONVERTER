"""
자막 처리를 위한 백엔드 모듈입니다.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import requests
from loguru import logger

from config.settings import (
    PROCESSED_DIR,
    UPLOAD_DIR,
    WHISPER_API_URL,
    WHISPER_MODEL_SIZE,
    WHISPER_TEMPERATURE,
)
from schemas import SubtitleFile, SubtitleSegment
from utils.file_handler import generate_unique_id
from utils.time_converter import ms_to_srt_time, srt_time_to_ms


def extract_subtitles(
    video_path: Union[str, Path],
    output_dir: Path = PROCESSED_DIR,
    model_size: Optional[str] = None,
    language: str = "ko",
    temperature: Optional[float] = None,
    initial_prompt: Optional[str] = None,
    timestamp_granularity: str = "segment"
) -> str:
    """
    OpenAI Whisper API를 호출하여 비디오에서 자막을 추출합니다.
    
    Args:
        video_path: 입력 비디오 파일 경로
        output_dir: 출력 디렉토리 경로
        model_size: Whisper 모델 크기 (tiny, base, small, medium, large-v3)
        language: 자막 언어 코드 (기본값: ko)
        temperature: 샘플링 온도 (0.0 ~ 1.0, 낮을수록 결정적)
        initial_prompt: 초기 프롬프트 텍스트
        timestamp_granularity: 타임스탬프 정밀도 ("segment" 또는 "word")
        
    Returns:
        str: 생성된 자막 파일 경로 (SRT 형식)
        
    Raises:
        ValueError: 자막 추출 실패 시
    """
    try:
        if isinstance(video_path, str):
            video_path = Path(video_path)
        
        # 출력 디렉토리 확인
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # /data 볼륨 기준 상대 경로
        # 도커 볼륨 마운트 구조: ./data:/data
        relative_video_path = str(video_path)
        if relative_video_path.startswith('/data/'):
            relative_video_path = relative_video_path[6:]  # '/data/' 제거
        
        logger.debug(f"OpenAI Whisper API 호출 준비: 비디오 경로={relative_video_path}")
        
        # API 엔드포인트 호출
        api_url = f"{WHISPER_API_URL}/api/extract_subtitles"
        
        # 폼 데이터 구성
        payload = {
            'video_path': relative_video_path,
            'language': language
        }
        
        # 선택적 매개변수 추가
        if model_size:
            payload['model_size'] = model_size
        
        if temperature is not None:
            payload['temperature'] = str(temperature)
        elif WHISPER_TEMPERATURE is not None:
            payload['temperature'] = str(WHISPER_TEMPERATURE)
            
        if initial_prompt:
            payload['initial_prompt'] = initial_prompt
            
        if timestamp_granularity:
            payload['timestamp_granularity'] = timestamp_granularity
        
        logger.debug(f"OpenAI Whisper API 호출: {api_url}, 매개변수: {payload}")
        response = requests.post(api_url, data=payload)
        
        # API 응답 처리
        if response.status_code != 200:
            error_msg = f"OpenAI Whisper API 호출 실패 (상태 코드: {response.status_code}): {response.text}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # JSON 응답 파싱
        result = response.json()
        
        if result["status"] != "success":
            error_msg = f"OpenAI Whisper API 처리 오류: {result.get('error', '알 수 없는 오류')}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # API가 반환한 자막 파일 경로 (상대 경로)
        subtitle_path = result.get("subtitle_path")
        if not subtitle_path:
            raise ValueError("API 응답에 자막 파일 경로가 포함되지 않았습니다")
        
        # 전체 경로로 변환
        full_subtitle_path = Path("/data") / subtitle_path
        
        logger.debug(f"자막 추출 완료: {full_subtitle_path}")
        return str(full_subtitle_path)
    
    except Exception as e:
        logger.error(f"자막 추출 중 예상치 못한 오류: {str(e)}")
        raise ValueError(f"자막 처리 중 오류가 발생했습니다: {str(e)}")


def parse_srt_file(srt_path: Union[str, Path]) -> List[SubtitleSegment]:
    """
    SRT 파일을 파싱하여 자막 세그먼트 목록을 반환합니다.
    
    Args:
        srt_path: SRT 파일 경로
        
    Returns:
        List[SubtitleSegment]: 자막 세그먼트 목록
        
    Raises:
        ValueError: SRT 파일 파싱 실패 시
    """
    try:
        if isinstance(srt_path, str):
            srt_path = Path(srt_path)
        
        # SRT 파일 내용 읽기
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # SRT 파일 파싱을 위한 정규식
        pattern = re.compile(
            r"(\d+)\s*\n"                      # 세그먼트 번호
            r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"  # 시작 시간
            r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n"       # 종료 시간
            r"([\s\S]*?)(?=\n\s*\n\s*\d+\s*\n|$)",    # 자막 텍스트
            re.DOTALL
        )
        
        # 정규식으로 파싱
        segments = []
        for match in pattern.finditer(content):
            segment_id = int(match.group(1))
            start_time = match.group(2)
            end_time = match.group(3)
            text = match.group(4).strip()
            
            # 시간 형식을 밀리초로 변환
            start_ms = srt_time_to_ms(start_time)
            end_ms = srt_time_to_ms(end_time)
            
            # 세그먼트 객체 생성
            segment = SubtitleSegment(
                id=segment_id,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text
            )
            segments.append(segment)
        
        logger.debug(f"SRT 파일 파싱 완료: {len(segments)}개 세그먼트")
        return segments
    
    except Exception as e:
        logger.error(f"SRT 파일 파싱 중 오류: {str(e)}")
        raise ValueError(f"SRT 파일 파싱 중 오류가 발생했습니다: {str(e)}")


def parse_uploaded_subtitle(
    file,
    output_dir: Path = PROCESSED_DIR
) -> Tuple[str, List[SubtitleSegment]]:
    """
    업로드된 자막 파일을 파싱합니다.
    
    Args:
        file: Streamlit 파일 업로더에서 제공한 파일 객체
        output_dir: 출력 디렉토리 경로
        
    Returns:
        Tuple[str, List[SubtitleSegment]]: 저장된 파일 경로와 자막 세그먼트 목록
        
    Raises:
        ValueError: 자막 파일 파싱 실패 시
    """
    try:
        # 출력 디렉토리 확인
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 고유한 ID 생성
        file_id = generate_unique_id()
        
        # 파일 확장자 추출
        file_ext = file.name.split(".")[-1].lower()
        
        if file_ext not in ["srt", "txt"]:
            raise ValueError("지원되지 않는 자막 파일 형식입니다. 지원 형식: SRT, TXT")
        
        # 저장할 파일명 생성
        filename = f"edited_subtitle_{file_id}.{file_ext}"
        file_path = output_dir / filename
        
        # 파일 저장
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        
        # 파일 형식에 따른 파싱
        if file_ext == "srt":
            segments = parse_srt_file(file_path)
        else:  # txt 형식 - "ms - 내용" 형식 가정
            segments = parse_txt_file(file_path)
        
        logger.debug(f"업로드된 자막 파일 파싱 완료: {file_path}")
        return str(file_path), segments
    
    except Exception as e:
        logger.error(f"자막 파일 파싱 중 오류: {str(e)}")
        raise ValueError(f"자막 파일 파싱 중 오류가 발생했습니다: {str(e)}")


def parse_txt_file(txt_path: Union[str, Path]) -> List[SubtitleSegment]:
    """
    TXT 파일을 파싱하여 자막 세그먼트 목록을 반환합니다.
    TXT 파일은 "시작ms - 종료ms - 내용" 형식이어야 합니다.
    
    Args:
        txt_path: TXT 파일 경로
        
    Returns:
        List[SubtitleSegment]: 자막 세그먼트 목록
        
    Raises:
        ValueError: TXT 파일 파싱 실패 시
    """
    try:
        if isinstance(txt_path, str):
            txt_path = Path(txt_path)
        
        # TXT 파일 내용 읽기
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # 각 줄 파싱
        segments = []
        segment_id = 1
        
        for line in lines:
            line = line.strip()
            if not line:  # 빈 줄 건너뛰기
                continue
            
            # "시작ms - 종료ms - 내용" 형식 파싱
            parts = line.split(" - ", 2)
            if len(parts) < 3:
                logger.warning(f"잘못된 형식의 줄: {line}")
                continue
            
            try:
                start_ms = int(parts[0])
                end_ms = int(parts[1])
                text = parts[2]
                
                # 세그먼트 객체 생성
                segment = SubtitleSegment(
                    id=segment_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=text
                )
                segments.append(segment)
                segment_id += 1
            except ValueError:
                logger.warning(f"시간 형식 오류 (ms 정수 필요): {line}")
        
        logger.debug(f"TXT 파일 파싱 완료: {len(segments)}개 세그먼트")
        return segments
    
    except Exception as e:
        logger.error(f"TXT 파일 파싱 중 오류: {str(e)}")
        raise ValueError(f"TXT 파일 파싱 중 오류가 발생했습니다: {str(e)}")


def save_subtitles_to_file(
    segments: List[SubtitleSegment],
    output_path: Union[str, Path],
    file_format: str = "srt",
    translated: bool = False
) -> str:
    """
    자막 세그먼트 목록을 파일로 저장합니다.
    
    Args:
        segments: 자막 세그먼트 목록
        output_path: 출력 파일 경로
        file_format: 출력 파일 형식 ("srt" 또는 "txt")
        translated: 번역된 텍스트 사용 여부
        
    Returns:
        str: 저장된 파일 경로
        
    Raises:
        ValueError: 파일 저장 실패 시
    """
    try:
        if isinstance(output_path, str):
            output_path = Path(output_path)
        
        # 출력 디렉토리 확인
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 파일 형식에 따른 저장
        if file_format.lower() == "srt":
            content = ""
            for segment in segments:
                text = segment.translated_text if translated and segment.translated_text else segment.text
                
                # SRT 형식 문자열 생성
                content += f"{segment.id}\n"
                content += f"{ms_to_srt_time(segment.start_ms)} --> {ms_to_srt_time(segment.end_ms)}\n"
                content += f"{text}\n\n"
        
        else:  # txt 형식 - "시작ms - 종료ms - 내용" 형식
            lines = []
            for segment in segments:
                text = segment.translated_text if translated and segment.translated_text else segment.text
                lines.append(f"{segment.start_ms} - {segment.end_ms} - {text}")
            
            content = "\n".join(lines)
        
        # 파일 저장
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.debug(f"자막 파일 저장 완료: {output_path} ({file_format} 형식)")
        return str(output_path)
    
    except Exception as e:
        logger.error(f"자막 파일 저장 중 오류: {str(e)}")
        raise ValueError(f"자막 파일 저장 중 오류가 발생했습니다: {str(e)}") 