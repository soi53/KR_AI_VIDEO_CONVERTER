"""
비디오 처리를 위한 백엔드 모듈입니다.
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import ffmpeg
from loguru import logger

from config.settings import PROCESSED_DIR, RESULTS_DIR
from utils.file_handler import generate_unique_id


def get_video_duration(video_path: Union[str, Path]) -> int:
    """
    비디오 파일의 재생 시간을 밀리초 단위로 반환합니다.
    
    Args:
        video_path: 비디오 파일 경로
        
    Returns:
        int: 재생 시간 (밀리초)
        
    Raises:
        ValueError: 비디오 파일 정보를 읽을 수 없는 경우
    """
    try:
        probe = ffmpeg.probe(str(video_path))
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        duration_seconds = float(probe['format']['duration'])
        return int(duration_seconds * 1000)
    except ffmpeg.Error as e:
        logger.error(f"비디오 정보 읽기 실패: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}")
        raise ValueError("비디오 파일 정보를 읽을 수 없습니다.")
    except (KeyError, StopIteration) as e:
        logger.error(f"비디오 형식 오류: {str(e)}")
        raise ValueError("비디오 형식이 유효하지 않습니다.")


def trim_video(
    video_path: Union[str, Path],
    start_ms: int = 0,
    end_ms: Optional[int] = None,
    output_dir: Path = PROCESSED_DIR
) -> str:
    """
    지정된 시간 범위로 비디오를 자릅니다.
    
    Args:
        video_path: 입력 비디오 파일 경로
        start_ms: 시작 시간 (밀리초)
        end_ms: 종료 시간 (밀리초), None인 경우 끝까지
        output_dir: 출력 디렉토리 경로
        
    Returns:
        str: 잘린 비디오 파일 경로
        
    Raises:
        ValueError: 비디오 자르기 실패 시
    """
    try:
        if isinstance(video_path, str):
            video_path = Path(video_path)
        
        # 출력 디렉토리 확인
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 원본 파일 ID 추출
        file_id = video_path.stem.split("_")[-1]
        
        # 출력 파일 경로 설정
        output_path = output_dir / f"trimmed_{file_id}{video_path.suffix}"
        
        # 시작 시간이 0이고 종료 시간이 없는 경우 자르기를 수행할 필요가 없음
        if start_ms == 0 and end_ms is None:
            logger.debug(f"자르기 범위가 전체 동영상이므로 자르기를 수행하지 않습니다: {video_path}")
            return str(video_path)
        
        # FFmpeg 명령어 구성
        input_stream = ffmpeg.input(str(video_path))
        
        # 시작 시간과 종료 시간 설정
        start_seconds = start_ms / 1000
        
        if end_ms is not None:
            # 종료 시간이 지정된 경우 재생 시간을 계산
            duration_seconds = (end_ms - start_ms) / 1000
            output_stream = input_stream.trim(start=start_seconds, duration=duration_seconds)
        else:
            # 종료 시간이 지정되지 않은 경우 시작 시간만 설정
            output_stream = input_stream.trim(start=start_seconds)
        
        # 비디오 스트림 설정
        output_stream = output_stream.setpts('PTS-STARTPTS')
        
        # 출력 파일로 저장
        output_stream = ffmpeg.output(output_stream, str(output_path), c='copy')
        
        # 실행 (덮어쓰기 허용)
        ffmpeg.run(output_stream, overwrite_output=True, quiet=True)
        
        logger.debug(f"비디오 자르기 완료: {output_path} (시작: {start_ms}ms, 종료: {end_ms if end_ms is not None else '끝까지'}ms)")
        return str(output_path)
    
    except ffmpeg.Error as e:
        error_message = e.stderr.decode() if hasattr(e, 'stderr') else str(e)
        logger.error(f"비디오 자르기 실패: {error_message}")
        raise ValueError(f"비디오 자르기 실패: {error_message}")
    except Exception as e:
        logger.error(f"비디오 자르기 중 예상치 못한 오류: {str(e)}")
        raise ValueError(f"비디오 처리 중 오류가 발생했습니다: {str(e)}")


def combine_video(
    video_path: Union[str, Path],
    audio_path: Union[str, Path],
    subtitle_path: Optional[Union[str, Path]] = None,
    output_dir: Path = RESULTS_DIR,
    target_language: str = "en"
) -> str:
    """
    비디오, TTS 오디오, 번역된 자막을 결합하여 최종 비디오를 생성합니다.
    
    Args:
        video_path: 입력 비디오 파일 경로
        audio_path: TTS 오디오 파일 경로
        subtitle_path: 자막 파일 경로 (선택 사항)
        output_dir: 출력 디렉토리 경로
        target_language: 대상 언어 코드
        
    Returns:
        str: 생성된 최종 비디오 파일 경로
        
    Raises:
        ValueError: 비디오 합성 실패 시
    """
    try:
        if isinstance(video_path, str):
            video_path = Path(video_path)
        if isinstance(audio_path, str):
            audio_path = Path(audio_path)
        if subtitle_path and isinstance(subtitle_path, str):
            subtitle_path = Path(subtitle_path)
        
        # 출력 디렉토리 확인
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 원본 파일 ID 추출
        file_id = video_path.stem.split("_")[-1]
        
        # 출력 파일 경로 설정
        output_path = output_dir / f"result_{file_id}_{target_language}{video_path.suffix}"
        
        # 임시 파일 경로 (자막 포함 경우를 위해)
        temp_path = PROCESSED_DIR / f"temp_{file_id}_{target_language}{video_path.suffix}"
        
        # 비디오와 오디오 결합
        input_video = ffmpeg.input(str(video_path))
        input_audio = ffmpeg.input(str(audio_path))
        
        # 비디오와 오디오 스트림 설정
        video_stream = input_video.video
        
        # 오디오 결합 (원본 오디오 대체)
        output = ffmpeg.output(
            video_stream,
            input_audio,
            str(temp_path if subtitle_path else output_path),
            c='copy',
            map_metadata=0
        )
        
        # 실행 (덮어쓰기 허용)
        ffmpeg.run(output, overwrite_output=True, quiet=True)
        
        # 자막이 제공된 경우 하드섭타이틀 추가
        if subtitle_path:
            input_with_audio = ffmpeg.input(str(temp_path))
            
            # 자막 포맷에 따라 인코딩 설정
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Ubuntu 기본 폰트 경로
            
            # 자막을 비디오에 하드코딩
            output_with_subtitle = ffmpeg.output(
                input_with_audio,
                str(output_path),
                vf=f"subtitles={subtitle_path}:force_style='FontName={font_path},FontSize=24'",
                c='copy',
                map_metadata=0
            )
            
            # 실행 (덮어쓰기 허용)
            ffmpeg.run(output_with_subtitle, overwrite_output=True, quiet=True)
            
            # 임시 파일 삭제
            if temp_path.exists():
                temp_path.unlink()
        
        logger.debug(f"비디오 합성 완료: {output_path}")
        return str(output_path)
    
    except ffmpeg.Error as e:
        error_message = e.stderr.decode() if hasattr(e, 'stderr') else str(e)
        logger.error(f"비디오 합성 실패: {error_message}")
        raise ValueError(f"비디오 합성 실패: {error_message}")
    except Exception as e:
        logger.error(f"비디오 합성 중 예상치 못한 오류: {str(e)}")
        raise ValueError(f"비디오 처리 중 오류가 발생했습니다: {str(e)}") 