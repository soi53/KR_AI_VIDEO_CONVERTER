# 베이스 이미지로 Python 3.11 사용
FROM python:3.11-slim

# 메타데이터 설정
LABEL maintainer="Company Video Translation Team"
LABEL description="동영상 번역 및 더빙 자동화 툴 - 주 애플리케이션 컨테이너"

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 시스템 패키지 설치 (ffmpeg 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    build-essential \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 의존성 파일 복사 및 설치
COPY ./app/requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY ./app /app/

# 데이터 디렉토리 볼륨 마운트 포인트 생성
RUN mkdir -p /data/uploads /data/processed /data/results
VOLUME ["/data"]

# Streamlit 실행 포트 노출
EXPOSE 8501

# 애플리케이션 실행 명령어
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"] 