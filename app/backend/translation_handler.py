"""
번역 처리를 위한 백엔드 모듈입니다.
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import openai
from loguru import logger

from config.settings import OPENAI_API_KEY, OPENAI_MODEL, PROCESSED_DIR
from schemas import SubtitleSegment, SubtitleFile
from utils.file_handler import generate_unique_id


# OpenAI API 키 설정
openai.api_key = OPENAI_API_KEY


def translate_subtitles(
    segments: List[SubtitleSegment],
    target_language: str,
    source_language: str = "ko"
) -> List[SubtitleSegment]:
    """
    OpenAI GPT API를 사용하여 자막 세그먼트를 번역합니다.
    
    Args:
        segments: 자막 세그먼트 목록
        target_language: 대상 언어 코드
        source_language: 원본 언어 코드
        
    Returns:
        List[SubtitleSegment]: 번역된 자막 세그먼트 목록
        
    Raises:
        ValueError: 번역 실패 시
    """
    try:
        if not segments:
            logger.warning("번역할 자막 세그먼트가 없습니다.")
            return []
        
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
        
        # 언어 코드를 언어명으로 변환 (API 요청에 사용)
        lang_map = {
            "ko": "한국어",
            "en": "영어",
            "ja": "일본어",
            "zh": "중국어",
            "de": "독일어",
            "id": "인도네시아어"
        }
        
        source_lang = lang_map.get(source_language, "한국어")
        target_lang = lang_map.get(target_language, "영어")
        
        # 가독성을 위해 세그먼트를 청크로 분할
        chunk_size = 10  # 한 번에 10개씩 번역
        chunks = [segments[i:i + chunk_size] for i in range(0, len(segments), chunk_size)]
        
        translated_segments = []
        
        for i, chunk in enumerate(chunks):
            # 번역 요청을 위한 문장 목록 생성
            texts = []
            for segment in chunk:
                texts.append(f"{segment.id}. {segment.text}")
            
            texts_str = "\n".join(texts)
            
            # API 요청 시스템 메시지 설정
            system_message = (
                f"당신은 전문 번역가입니다. {source_lang}에서 {target_lang}로 자막 텍스트를 번역해주세요. "
                f"각 줄의 번호를 유지하고, 자연스러운 {target_lang}로 번역하되 원래 의미를 정확히 전달하세요. "
                f"번역만 제공하고 다른 설명은 추가하지 마세요. "
                f"번역 시 공식적이고 전문적인 어투를 유지하세요."
            )
            
            # API 요청 사용자 메시지 설정
            user_message = (
                f"다음 {source_lang} 자막 텍스트를 {target_lang}로 번역해주세요. "
                f"각 줄은 '줄번호. 내용' 형식입니다. 번역 결과도 동일한 형식으로 제공해주세요.\n\n"
                f"{texts_str}"
            )
            
            # OpenAI API 호출 (오류 발생 시 재시도 로직 포함)
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    response = openai.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=0.3,  # 번역은 창의성보다 정확성 중요
                    )
                    
                    # 응답에서 번역된 텍스트 추출
                    translated_text = response.choices[0].message.content.strip()
                    
                    # 번역된 텍스트 파싱
                    lines = translated_text.split("\n")
                    
                    # 번역 결과를 세그먼트에 할당
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # "번호. 내용" 형식 파싱
                        try:
                            parts = line.split(". ", 1)
                            if len(parts) != 2:
                                logger.warning(f"번역 응답에서 잘못된 형식의 줄: {line}")
                                continue
                            
                            segment_id = int(parts[0])
                            translated_content = parts[1]
                            
                            # 해당 ID를 가진 세그먼트 찾기
                            for segment in chunk:
                                if segment.id == segment_id:
                                    segment.translated_text = translated_content
                                    break
                        except ValueError:
                            logger.warning(f"번역 응답에서 세그먼트 ID 파싱 실패: {line}")
                    
                    # 처리된 세그먼트 추가
                    translated_segments.extend(chunk)
                    
                    # API 호출 간 짧은 지연
                    if i < len(chunks) - 1:
                        time.sleep(1)
                    
                    # 성공적으로 처리됨
                    break
                
                except openai.APIError as e:
                    logger.error(f"OpenAI API 오류: {str(e)}")
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # 지수 백오프
                        logger.debug(f"재시도 {retry_count}/{max_retries} - {wait_time}초 후 재시도")
                        time.sleep(wait_time)
                    else:
                        raise ValueError(f"API 호출 재시도 한도 초과: {str(e)}")
        
        logger.debug(f"{len(segments)}개 세그먼트 번역 완료 ({source_language} -> {target_language})")
        return translated_segments
    
    except openai.APIError as e:
        logger.error(f"OpenAI API 오류: {str(e)}")
        raise ValueError(f"OpenAI API 통신 중 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        logger.error(f"번역 중 예상치 못한 오류: {str(e)}")
        raise ValueError(f"번역 중 오류가 발생했습니다: {str(e)}")


def save_translated_subtitles(
    segments: List[SubtitleSegment],
    target_language: str,
    file_id: str,
    output_dir: Path = PROCESSED_DIR
) -> Tuple[str, str]:
    """
    번역된 자막을 SRT 파일과 TXT 파일로 저장합니다.
    
    Args:
        segments: 번역된 자막 세그먼트 목록
        target_language: 대상 언어 코드
        file_id: 파일 ID
        output_dir: 출력 디렉토리 경로
        
    Returns:
        Tuple[str, str]: 저장된 SRT 파일 경로와 TXT 파일 경로
        
    Raises:
        ValueError: 파일 저장 실패 시
    """
    try:
        # 출력 디렉토리 확인
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # SRT 파일 경로 설정
        srt_path = output_dir / f"translated_{file_id}_{target_language}.srt"
        
        # TXT 파일 경로 설정
        txt_path = output_dir / f"translated_{file_id}_{target_language}.txt"
        
        # SRT 형식으로 저장
        with open(srt_path, "w", encoding="utf-8") as f:
            for segment in segments:
                text = segment.translated_text if segment.translated_text else segment.text
                
                # 시간 형식 변환 (밀리초 -> 00:00:00,000 형식)
                start_time = format_srt_time(segment.start_ms)
                end_time = format_srt_time(segment.end_ms)
                
                # SRT 형식으로 작성
                f.write(f"{segment.id}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        
        # TXT 형식으로 저장 (시작ms - 종료ms - 내용)
        with open(txt_path, "w", encoding="utf-8") as f:
            for segment in segments:
                text = segment.translated_text if segment.translated_text else segment.text
                f.write(f"{segment.start_ms} - {segment.end_ms} - {text}\n")
        
        logger.debug(f"번역된 자막 파일 저장 완료: SRT({srt_path}), TXT({txt_path})")
        return str(srt_path), str(txt_path)
    
    except Exception as e:
        logger.error(f"번역된 자막 파일 저장 중 오류: {str(e)}")
        raise ValueError(f"번역된 자막 파일 저장 중 오류가 발생했습니다: {str(e)}")


def format_srt_time(ms: int) -> str:
    """
    밀리초를 SRT 시간 형식(00:00:00,000)으로 변환합니다.
    
    Args:
        ms: 밀리초
        
    Returns:
        str: SRT 형식의 시간 문자열
    """
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}" 