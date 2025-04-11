"""
애플리케이션 로깅 설정을 위한 모듈입니다.
"""
import os
import sys
from pathlib import Path

from loguru import logger

from config.settings import DEBUG


def setup_logger():
    """
    loguru 로거를 구성하고 설정합니다.
    """
    # 기존 로거 설정 제거
    logger.remove()

    # 로그 파일 경로 설정
    log_dir = Path("/data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # 로그 포맷 설정
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 콘솔 로거 추가
    logger.add(
        sys.stderr,
        format=log_format,
        level="DEBUG" if DEBUG else "INFO",
        colorize=True,
    )

    # 파일 로거 추가 (로테이션 설정)
    logger.add(
        log_file,
        format=log_format,
        level="DEBUG" if DEBUG else "INFO",
        rotation="10 MB",
        compression="zip",
        retention="1 week",
    )

    logger.debug("로거가 설정되었습니다.")
    return logger


# 로거 설정 초기화
logger = setup_logger() 