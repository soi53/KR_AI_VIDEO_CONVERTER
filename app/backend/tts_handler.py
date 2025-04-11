"""
TTS(Text-to-Speech) 처리를 위한 백엔드 모듈입니다.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from loguru import logger
from TTS.api import TTS

from config.settings import (
    PROCESSED_DIR,
    TTS_MODEL,
    TTS_SPEAKERS_FILE
)
from schemas import SubtitleSegment


# TTS 모델 인스턴스 및 초기화 상태
_tts_instance = None
_is_initialized = False


def get_tts_instance() -> TTS:
    """
    TTS 모델 인스턴스를 반환합니다. 필요한 경우 모델을 초기화합니다.
    
    Returns:
        TTS: TTS 모델 인스턴스
    """
    global _tts_instance, _is_initialized
    
    if not _is_initialized:
        try:
            # GPU 사용 가능한 경우 사용
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.debug(f"TTS 모델 초기화 중... (device: {device})")
            
            # 모델 로드
            _tts_instance = TTS(model_name=TTS_MODEL, gpu=(device == "cuda"))
            
            _is_initialized = True
            logger.debug(f"TTS 모델 초기화 완료: {TTS_MODEL}")
        except Exception as e:
            logger.error(f"TTS 모델 초기화 오류: {str(e)}")
            raise ValueError(f"TTS 모델을 초기화할 수 없습니다: {str(e)}")
    
    return _tts_instance


def load_tts_speakers() -> Dict:
    """
    TTS 스피커 설정 파일을 로드합니다.
    
    Returns:
        Dict: 언어별 스피커 설정
    """
    try:
        speakers_file = Path(TTS_SPEAKERS_FILE)
        
        if not speakers_file.exists():
            logger.warning(f"TTS 스피커 설정 파일을 찾을 수 없습니다: {speakers_file}")
            return {}
        
        with open(speakers_file, "r", encoding="utf-8") as f:
            speakers = json.load(f)
        
        return speakers
    except Exception as e:
        logger.error(f"TTS 스피커 설정 로드 오류: {str(e)}")
        return {}


def get_speaker_for_language(language: str, gender: str = "female") -> Optional[str]:
    """
    지정된 언어 및 성별에 맞는 TTS 스피커를 반환합니다.
    
    Args:
        language: 언어 코드
        gender: 성별 ("male" 또는 "female")
        
    Returns:
        Optional[str]: 스피커 이름, 찾을 수 없는 경우 None
    """
    try:
        speakers = load_tts_speakers()
        
        if language not in speakers:
            logger.warning(f"언어 코드에 해당하는 스피커를 찾을 수 없습니다: {language}")
            return None
        
        # 성별에 맞는 스피커 찾기
        for speaker in speakers[language]:
            if speaker.get("gender") == gender:
                return speaker.get("name")
        
        # 성별에 맞는 스피커가 없으면 첫 번째 스피커 반환
        if speakers[language]:
            logger.warning(f"{language}의 {gender} 스피커를 찾을 수 없어 첫 번째 스피커를 사용합니다.")
            return speakers[language][0].get("name")
        
        return None
    except Exception as e:
        logger.error(f"스피커 선택 오류: {str(e)}")
        return None


def generate_tts_audio(
    segments: List[SubtitleSegment],
    target_language: str,
    file_id: str,
    gender: str = "female",
    output_dir: Path = PROCESSED_DIR
) -> str:
    """
    번역된 자막 세그먼트를 TTS로 음성 파일로 변환합니다.
    
    Args:
        segments: 번역된 자막 세그먼트 목록
        target_language: 대상 언어 코드
        file_id: 파일 ID
        gender: 성별 ("male" 또는 "female")
        output_dir: 출력 디렉토리 경로
        
    Returns:
        str: 생성된 오디오 파일 경로
        
    Raises:
        ValueError: TTS 생성 실패 시
    """
    try:
        # 출력 디렉토리 확인
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 출력 파일 경로 설정
        output_path = output_dir / f"tts_{file_id}_{target_language}.wav"
        
        # TTS 모델 인스턴스 가져오기
        tts = get_tts_instance()
        
        # 스피커 선택
        speaker = get_speaker_for_language(target_language, gender)
        
        # 번역된 텍스트 결합 (각 세그먼트 사이에 짧은 휴식 포함)
        texts = []
        for segment in segments:
            if segment.translated_text:
                texts.append(segment.translated_text)
            else:
                # 번역된 텍스트가 없으면 원본 텍스트 사용
                logger.warning(f"세그먼트 {segment.id}에 번역된 텍스트가 없어 원본 텍스트를 사용합니다.")
                texts.append(segment.text)
        
        # 텍스트를 문단으로 결합
        full_text = " ".join(texts)
        
        # TTS 실행 (스피커 지정)
        tts_kwargs = {}
        if speaker:
            tts_kwargs["speaker"] = speaker
        
        # 언어 코드 지정
        language_mapping = {
            "en": "en",
            "zh": "zh-cn",
            "ja": "ja",
            "de": "de",
            "id": "id"
        }
        
        tts_language = language_mapping.get(target_language, "en")
        tts_kwargs["language"] = tts_language
        
        # TTS 실행
        logger.debug(f"TTS 생성 시작: 언어={tts_language}, 스피커={speaker if speaker else '기본'}")
        tts.tts_to_file(
            text=full_text,
            file_path=str(output_path),
            **tts_kwargs
        )
        
        logger.debug(f"TTS 생성 완료: {output_path}")
        return str(output_path)
    
    except Exception as e:
        logger.error(f"TTS 생성 중 오류: {str(e)}")
        raise ValueError(f"TTS 음성 생성 중 오류가 발생했습니다: {str(e)}")


def generate_segmented_tts_audio(
    segments: List[SubtitleSegment],
    target_language: str,
    file_id: str,
    gender: str = "female",
    output_dir: Path = PROCESSED_DIR
) -> Tuple[str, Dict[int, str]]:
    """
    각 자막 세그먼트별로 개별 TTS 오디오 파일을 생성하고 최종적으로 하나의 파일로 합칩니다.
    
    Args:
        segments: 번역된 자막 세그먼트 목록
        target_language: 대상 언어 코드
        file_id: 파일 ID
        gender: 성별 ("male" 또는 "female")
        output_dir: 출력 디렉토리 경로
        
    Returns:
        Tuple[str, Dict[int, str]]: 합쳐진 오디오 파일 경로와 세그먼트별 오디오 파일 경로 맵
        
    Raises:
        ValueError: TTS 생성 실패 시
    """
    # 이 기능은 고급 기능으로 V1 범위에서는 단순화를 위해 구현하지 않습니다.
    # 필요시 나중에 구현할 수 있습니다.
    raise NotImplementedError("세그먼트별 TTS 생성 기능은 현재 지원되지 않습니다.") 