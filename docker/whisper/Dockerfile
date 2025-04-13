FROM python:3.9-slim

# 메타데이터 설정
LABEL maintainer="Company Video Translation Team"
LABEL description="OpenAI Whisper STT 서비스 컨테이너"

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    build-essential \
    git \
    cmake \
    libopenblas-dev \
    rustc \
    cargo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Rust 환경 설정 (tiktoken 의존성)
ENV PATH="/root/.cargo/bin:${PATH}"

# 필요한 Python 패키지 설치
COPY ./docker/whisper/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir setuptools-rust && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY ./docker/whisper/app.py /app/app.py

# 데이터 디렉토리 볼륨 마운트 포인트 생성
RUN mkdir -p /data/uploads /data/processed

# API 서버 실행 포트 노출
EXPOSE 8000

# 애플리케이션 실행 명령어
CMD ["python", "app.py"] 