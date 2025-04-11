"""
데이터 구조를 정의하는 스키마 모듈입니다.
"""
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class SubtitleSegment(BaseModel):
    """자막 세그먼트(한 문장 단위)의 데이터 구조"""
    
    id: int = Field(..., description="세그먼트 고유 ID (일반적으로 순차적 번호)")
    start_ms: int = Field(..., description="시작 시간 (밀리초)")
    end_ms: int = Field(..., description="종료 시간 (밀리초)")
    text: str = Field(..., description="원본 텍스트")
    translated_text: Optional[str] = Field(None, description="번역된 텍스트")
    
    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "start_ms": 0,
                "end_ms": 3000,
                "text": "안녕하세요, 반갑습니다.",
                "translated_text": "Hello, nice to meet you."
            }
        }


class SubtitleFile(BaseModel):
    """자막 파일의 데이터 구조"""
    
    file_id: str = Field(..., description="파일 고유 ID")
    segments: List[SubtitleSegment] = Field(default_factory=list, description="자막 세그먼트 목록")
    source_language: str = Field("ko", description="원본 언어 코드")
    target_language: Optional[str] = Field(None, description="대상 언어 코드 (번역 시)")
    source_video_path: Optional[str] = Field(None, description="원본 비디오 파일 경로")
    
    class Config:
        schema_extra = {
            "example": {
                "file_id": "1a2b3c4d5e6f",
                "segments": [
                    {
                        "id": 1,
                        "start_ms": 0,
                        "end_ms": 3000,
                        "text": "안녕하세요, 반갑습니다.",
                        "translated_text": "Hello, nice to meet you."
                    }
                ],
                "source_language": "ko",
                "target_language": "en",
                "source_video_path": "/data/uploads/original_1a2b3c4d5e6f.mp4"
            }
        }


class VideoInfo(BaseModel):
    """비디오 파일 정보의 데이터 구조"""
    
    id: str = Field(..., description="비디오 고유 ID")
    original_name: str = Field(..., description="원본 파일명")
    saved_name: str = Field(..., description="저장된 파일명")
    path: str = Field(..., description="파일 경로")
    size: int = Field(..., description="파일 크기 (바이트)")
    type: str = Field(..., description="파일 타입 (확장자)")
    duration_ms: Optional[int] = Field(None, description="비디오 길이 (밀리초)")
    trimmed: bool = Field(False, description="자르기 여부")
    trimmed_path: Optional[str] = Field(None, description="잘린 비디오 파일 경로")
    trim_start_ms: Optional[int] = Field(None, description="자르기 시작 시간 (밀리초)")
    trim_end_ms: Optional[int] = Field(None, description="자르기 종료 시간 (밀리초)")
    subtitle_file_id: Optional[str] = Field(None, description="연결된 자막 파일 ID")
    result_path: Optional[str] = Field(None, description="최종 결과 파일 경로")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "1a2b3c4d5e6f",
                "original_name": "meeting.mp4",
                "saved_name": "original_1a2b3c4d5e6f.mp4",
                "path": "/data/uploads/original_1a2b3c4d5e6f.mp4",
                "size": 15000000,
                "type": "mp4",
                "duration_ms": 180000,
                "trimmed": True,
                "trimmed_path": "/data/processed/trimmed_1a2b3c4d5e6f.mp4",
                "trim_start_ms": 5000,
                "trim_end_ms": 120000,
                "subtitle_file_id": "abcdef123456",
                "result_path": "/data/results/result_1a2b3c4d5e6f_en.mp4"
            }
        }


class TranslationTask(BaseModel):
    """번역 작업의 데이터 구조"""
    
    video_id: str = Field(..., description="비디오 고유 ID")
    subtitle_file_id: str = Field(..., description="자막 파일 ID")
    target_language: str = Field(..., description="대상 언어 코드")
    status: str = Field("pending", description="작업 상태")
    created_at: Optional[str] = Field(None, description="작업 생성 시간")
    completed_at: Optional[str] = Field(None, description="작업 완료 시간")
    result_path: Optional[str] = Field(None, description="결과 파일 경로")
    error_message: Optional[str] = Field(None, description="오류 메시지 (있는 경우)") 