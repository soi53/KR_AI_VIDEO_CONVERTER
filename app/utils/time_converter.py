"""
시간 형식 변환을 위한 유틸리티 모듈입니다.
"""
import re
from typing import Tuple, Union


def time_to_ms(time_str: str) -> int:
    """
    MM:SS 형식의 시간 문자열을 밀리초로 변환합니다.
    
    Args:
        time_str: 'MM:SS' 형식의 시간 문자열
        
    Returns:
        int: 밀리초 단위의 시간
        
    Raises:
        ValueError: 시간 형식이 올바르지 않은 경우
    """
    if not time_str or time_str.strip() == "":
        return 0
    
    time_pattern = re.compile(r"^(\d+):([0-5]?\d)$")
    match = time_pattern.match(time_str.strip())
    
    if not match:
        raise ValueError("시간 형식이 올바르지 않습니다. 'MM:SS' 형식을 사용하세요.")
    
    minutes, seconds = map(int, match.groups())
    return (minutes * 60 + seconds) * 1000


def ms_to_time(ms: int) -> str:
    """
    밀리초를 MM:SS 형식의 시간 문자열로 변환합니다.
    
    Args:
        ms: 밀리초 단위의 시간
        
    Returns:
        str: 'MM:SS' 형식의 시간 문자열
    """
    if ms < 0:
        ms = 0
    
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    
    return f"{minutes:02d}:{seconds:02d}"


def srt_time_to_ms(srt_time: str) -> int:
    """
    SRT 형식의 시간 문자열(HH:MM:SS,mmm)을 밀리초로 변환합니다.
    
    Args:
        srt_time: 'HH:MM:SS,mmm' 형식의 시간 문자열
        
    Returns:
        int: 밀리초 단위의 시간
        
    Raises:
        ValueError: SRT 시간 형식이 올바르지 않은 경우
    """
    time_pattern = re.compile(r"^(\d{2}):(\d{2}):(\d{2})[,.](\d{3})$")
    match = time_pattern.match(srt_time.strip())
    
    if not match:
        raise ValueError("SRT 시간 형식이 올바르지 않습니다. 'HH:MM:SS,mmm' 형식을 사용하세요.")
    
    hours, minutes, seconds, ms = map(int, match.groups())
    return hours * 3600 * 1000 + minutes * 60 * 1000 + seconds * 1000 + ms


def ms_to_srt_time(ms: int) -> str:
    """
    밀리초를 SRT 형식의 시간 문자열(HH:MM:SS,mmm)로 변환합니다.
    
    Args:
        ms: 밀리초 단위의 시간
        
    Returns:
        str: 'HH:MM:SS,mmm' 형식의 시간 문자열
    """
    if ms < 0:
        ms = 0
    
    hours = ms // (3600 * 1000)
    ms %= 3600 * 1000
    minutes = ms // (60 * 1000)
    ms %= 60 * 1000
    seconds = ms // 1000
    ms %= 1000
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def validate_time_range(start_time: str, end_time: str) -> Tuple[bool, str]:
    """
    시작 시간과 종료 시간이 유효한지 검사합니다.
    
    Args:
        start_time: 'MM:SS' 형식의 시작 시간 문자열
        end_time: 'MM:SS' 형식의 종료 시간 문자열
        
    Returns:
        Tuple[bool, str]: 유효성 여부와 오류 메시지(있는 경우)
    """
    # 둘 다 비어있으면 자르기를 원하지 않는 것으로 간주
    if (not start_time or start_time.strip() == "") and (not end_time or end_time.strip() == ""):
        return True, ""
    
    try:
        start_ms = time_to_ms(start_time) if start_time and start_time.strip() != "" else 0
        end_ms = time_to_ms(end_time) if end_time and end_time.strip() != "" else float("inf")
        
        if start_ms >= end_ms:
            return False, "종료 시간은 시작 시간보다 커야 합니다."
        
        return True, ""
    except ValueError as e:
        return False, str(e) 