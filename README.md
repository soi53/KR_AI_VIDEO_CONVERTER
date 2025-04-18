# 동영상 번역 및 더빙 자동화 도구

이 프로젝트는 동영상의 음성을 텍스트로 변환(STT), 번역, 자연스러운 목소리로 새로운 언어로 더빙(TTS)하는 과정을 자동화하는 도구입니다.

## 주요 기능

- OpenAI Whisper를 이용한 음성 인식 및 자막 추출
- OpenAI GPT를 이용한 고품질 번역
- TTS(Text-to-Speech)를 통한 자연스러운 음성 합성
- 최종 비디오에 번역된 음성을 합성

## 시스템 요구사항

- Docker & Docker Compose
- 최소 8GB RAM
- NVIDIA GPU (선택 사항, CPU에서도 작동)
- OpenAI API 키

## 설치 및 실행

1. 저장소 클론:

```bash
git clone https://github.com/your-username/video-translator.git
cd video-translator
```

2. `.env` 파일 설정:

```bash
cp .env.example .env
# .env 파일 편집 및 API 키 추가
```

3. Docker 컨테이너 빌드 및 실행:

```bash
docker-compose up -d
```

4. 웹 인터페이스 접속:

```
http://localhost:8501
```

## 기술 스택

- OpenAI Whisper: 음성 인식
- OpenAI GPT: 번역
- XTTS-v2: 음성 합성
- FFmpeg: 비디오 처리
- Streamlit: 웹 인터페이스
- FastAPI: 백엔드 API
- Docker: 컨테이너화
