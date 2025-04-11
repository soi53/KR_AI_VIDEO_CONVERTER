"""
파일 업로드, 저장 및 관리를 위한 유틸리티 모듈입니다.
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from loguru import logger

from config.settings import (
    ALLOWED_VIDEO_FORMATS,
    MAX_UPLOAD_SIZE_MB,
    PROCESSED_DIR,
    RESULTS_DIR,
    UPLOAD_DIR,
)


def generate_unique_id() -> str:
    """
    고유한 ID를 생성합니다.
    
    Returns:
        str: 하이픈이 없는 UUID 문자열
    """
    return str(uuid.uuid4()).replace("-", "")


def validate_video_file(file) -> Tuple[bool, str]:
    """
    업로드된 비디오 파일의 유효성을 검사합니다.
    
    Args:
        file: 업로드된 파일 객체
        
    Returns:
        유효성 여부(bool)와 오류 메시지(str) 튜플
    """
    # 파일이 있는지 확인
    if file is None:
        return False, "파일이 선택되지 않았습니다."
    
    # 파일 형식 확인
    filename = file.name
    file_ext = filename.split(".")[-1].lower()
    
    if file_ext not in ALLOWED_VIDEO_FORMATS:
        return False, f"지원되지 않는 파일 형식입니다. 지원되는 형식: {', '.join(ALLOWED_VIDEO_FORMATS)}"
    
    # 파일 크기 제한 검사 제거 - 모든 크기의 파일 허용
    
    return True, ""


def save_uploaded_file(file, directory: Path = UPLOAD_DIR) -> Dict[str, str]:
    """
    업로드된 파일을 저장하고 관련 정보를 반환합니다.
    
    Args:
        file: Streamlit 파일 업로더에서 제공한 파일 객체
        directory: 파일을 저장할 디렉토리 경로
        
    Returns:
        Dict[str, str]: 저장된 파일 정보 (ID, 이름, 경로 등)
    """
    # 디렉토리가 존재하는지 확인
    directory.mkdir(parents=True, exist_ok=True)
    
    # 고유한 ID 생성
    file_id = generate_unique_id()
    
    # 파일 확장자 추출
    file_ext = file.name.split(".")[-1]
    
    # 저장할 파일명 생성 (original_{file_id}.{file_ext})
    filename = f"original_{file_id}.{file_ext}"
    file_path = directory / filename
    
    # 파일 저장
    with open(file_path, "wb") as f:
        f.write(file.getbuffer())
    
    logger.debug(f"파일이 저장되었습니다: {file_path}")
    
    # 파일 정보 반환
    return {
        "id": file_id,
        "original_name": file.name,
        "saved_name": filename,
        "path": str(file_path),
        "size": file.size,
        "type": file_ext,
    }


def delete_file(file_path: Union[str, Path]) -> bool:
    """
    지정된 경로의 파일을 삭제합니다.
    
    Args:
        file_path: 삭제할 파일 경로
        
    Returns:
        bool: 삭제 성공 여부
    """
    try:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        if file_path.exists():
            file_path.unlink()
            logger.debug(f"파일이 삭제되었습니다: {file_path}")
            return True
        else:
            logger.warning(f"삭제할 파일이 존재하지 않습니다: {file_path}")
            return False
    except Exception as e:
        logger.error(f"파일 삭제 중 오류가 발생했습니다: {e}")
        return False


def get_file_size(file_path: Union[str, Path]) -> int:
    """
    지정된 경로의 파일 크기를 바이트 단위로 반환합니다.
    
    Args:
        file_path: 파일 경로
        
    Returns:
        int: 파일 크기(바이트)
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    if file_path.exists():
        return file_path.stat().st_size
    return 0


def clean_temporary_files(file_id: str) -> None:
    """
    특정 작업과 관련된 임시 파일들을 정리합니다.
    
    Args:
        file_id: 작업 관련 파일 ID
    """
    try:
        # 각 디렉토리에서 해당 ID를 포함하는 임시 파일 찾기
        for directory in [UPLOAD_DIR, PROCESSED_DIR]:
            for file_path in directory.glob(f"*{file_id}*"):
                # 결과물이 아닌 경우에만 삭제
                if "result" not in file_path.name and file_path.is_file():
                    delete_file(file_path)
        
        logger.debug(f"ID: {file_id}와 관련된 임시 파일들이 정리되었습니다.")
    except Exception as e:
        logger.error(f"임시 파일 정리 중 오류가 발생했습니다: {e}") 