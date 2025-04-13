### **구현 계획 (Implementation Plan) \- 동영상 번역 및 더빙 자동화 툴 V1**

**목표:** 이 구현 계획은 동영상 번역 및 더빙 자동화 툴 V1 개발을 위한 단계별 작업 지침을 제공합니다. AI는 각 단계를 순서대로 수행하고, 완료 시 해당 단계에 Done 표시와 함께 2줄 요약을 추가해야 합니다 (규칙 3). 모든 작업은 Docker 환경 내에서 수행되는 것을 전제로 합니다.

**Phase 1: 프로젝트 설정 및 Docker 환경 구성**

1. 프로젝트 루트 디렉토리 생성 (video\_translator\_app)  
2. Git 저장소 초기화 (git init) 및 기본 .gitignore 파일 생성 (Python, Docker, .env 관련)  
3. 기본 폴더 구조 생성 (app, docker, data/uploads, data/processed, data/results, config)  
4. 주 애플리케이션 Dockerfile 생성 (docker/app/Dockerfile) \- Python 3.11 베이스 이미지 사용  
5. Dockerfile: 기본 작업 디렉토리 설정 및 필요 시스템 패키지 설치 (ffmpeg 등)  
6. 애플리케이션 의존성 파일 생성 (app/requirements.txt) \- streamlit==1.32.2, python-dotenv 명시  
7. Dockerfile: requirements.txt 복사 및 pip install 실행 단계 추가 (ffmpeg-python, openai, faster-whisper, coqui-tts 등 추가 필요)  
8. Dockerfile: 애플리케이션 코드 복사 (COPY ./app /app) 및 기본 실행 명령어 설정 (CMD \["streamlit", "run", "app.py"\])  
9. 환경 변수 관리 파일 생성 (.env.example) \- OPENAI\_API\_KEY 등 필요한 키 목록 정의  
10. 구성 로딩 모듈 생성 (app/config/settings.py) \- python-dotenv 사용하여 .env 파일 로드 로직 구현  
11. docker-compose.yml 파일 생성 (루트 디렉토리)  
12. docker-compose.yml: 주 애플리케이션 서비스('app') 정의 (build 컨텍스트, ports, volumes 설정 \- /data 폴더 마운트, env\_file 설정 \- .env 파일 참조)  
13. docker-compose.yml: GPU 사용을 위한 설정(선택 사항) 추가  
14. Docker 이미지 빌드 테스트 (docker-compose build app)  
15. 기본 Streamlit 앱 파일 생성 (app/app.py) \- 페이지 타이틀 및 설정 로드 로직 포함  
16. Docker 컨테이너 실행 테스트 (docker-compose up app) 및 브라우저에서 기본 앱 접속, 설정 로드 확인

**Phase 2: Frontend UI \- 초기 화면 및 업로드 기능**

17. app.py: Streamlit 페이지 설정 (st.set\_page\_config) \- 타이틀, 레이아웃 등  
18. app.py: 파일 업로드 UI 구현 (st.file\_uploader 사용, 허용 파일 타입 지정 \- AVI, MP4)  
19. app/utils/file\_handler.py 모듈 생성 및 파일 저장 함수 정의 (save\_uploaded\_file) \- 고유 ID 생성 및 /data/uploads에 저장  
20. app.py: 파일 업로드 시 save\_uploaded\_file함수 호출 및 업로드된 파일 정보(ID, 이름, 경로)st.session\_state에 저장 로직 구현  
21. app.py: 파일 업로드 성공 시 사용자에게 파일명과 함께 성공 메시지(st.success) 표시

**Phase 3: Frontend UI & Backend Logic \- 동영상 자르기**

22. app.py: 동영상 자르기 UI 구현 (MM:SS 형식 입력 필드 2개 또는 st.time\_input 활용, 안내 문구 포함)  
23. app/utils/time\_converter.py 모듈 생성 및 MM:SS \-\> ms 변환 함수, ms \-\> MM:SS 변환 함수 정의  
24. app/backend/video\_processor.py 모듈 생성  
25. video\_processor.py: trim\_video 함수 정의 (입력: 원본 비디오 경로, 시작/종료 ms. 출력: 잘린 비디오 경로)  
26. video\_processor.py: trim\_video함수 내부에ffmpeg-python 라이브러리를 사용하여 실제 자르기 로직 구현 (오류 처리 포함)  
27. app.py: 자르기 시간 입력값 유효성 검사 및 ms 변환 로직 추가  
28. app.py: (선택적) '자르기 미리보기' 또는 '자르기 적용' 버튼 및 관련 로직 추가 (V1에서는 자막 추출 시 함께 처리)

**Phase 4: 데이터 구조 정의 및 자막 추출 준비**

29. app/schemas.py 모듈 생성 (또는 적절한 위치)  
30. schemas.py: 자막 세그먼트 데이터 구조 정의 (예: Pydantic 모델 또는 단순 dict \- start\_ms, end\_ms, text 필드 포함)  
31. app/backend/subtitle\_handler.py 모듈 생성  
32. subtitle\_handler.py: extract\_subtitles 함수 정의 (입력: 비디오 경로. 출력: List\[SubtitleSegment\] 또는 자막 파일 경로)

**Phase 5: Backend Logic & Frontend \- 자막 추출 (Faster Whisper 연동)**

33. subtitle\_handler.py: extract\_subtitles 함수 내부에 Faster Whisper 라이브러리를 사용하여 음성 인식 로직 구현  
34. subtitle\_handler.py: Faster Whisper 모델 초기화 (model_size, device, compute_type) 및 음성 인식 실행 로직 구현  
35. subtitle\_handler.py: 인식 결과를 SRT 형식으로 변환하고 파일(/data/processed)로 저장하는 로직 구현 (경로 관리 주의)  
36. app.py: "자막 추출 시작" 버튼 구현 및 클릭 시 extract\_subtitles함수 호출 로직 추가 (진행 중st.spinner 표시)  
37. app.py: 자막 추출 성공 시 결과 데이터(List\[SubtitleSegment\]) 또는 파일 경로 st.session\_state에 저장 및 성공 메시지 표시  
38. app.py: 추출된 자막 다운로드 버튼 구현 (st.download\_button 사용, SRT/TXT 형식 지원 \- 필요시 데이터 구조를 파일로 변환)

**Phase 6: 수정된 자막 업로드 UI 및 처리 로직 구현**

39. app.py: "수정 완료된 자막 업로드" UI 구현 (st.file\_uploader 사용, SRT/TXT 허용)  
40. subtitle\_handler.py: parse\_uploaded\_subtitle 함수 정의 (입력: 업로드된 파일 객체. 출력: List\[SubtitleSegment\] 또는 오류)  
41. subtitle\_handler.py: parse\_uploaded\_subtitle 함수 내부에 SRT/TXT 파일 형식 검증 및 내용 파싱 로직 구현 (schemas.py의 데이터 구조 사용)  
42. app.py: 자막 파일 업로드 시 parse\_uploaded\_subtitle 호출 및 유효성 검사 로직 구현  
43. app.py: 유효한 자막 업로드 시 파싱된 데이터(List\[SubtitleSegment\])를 st.session\_state에 저장 및 성공 메시지 표시

**Phase 7: 번역 언어 선택 UI 및 번역 API 연동 로직 구현**

44. app.py: 번역 대상 언어 선택 UI 구현 (st.selectbox 사용 \- 영어, 일본어, 중국어, 독일어, 인도네시아어)  
45. app/backend/translation\_handler.py 모듈 생성  
46. translation\_handler.py: translate\_subtitles 함수 정의 (입력: List\[SubtitleSegment\], 대상 언어 코드. 출력: List\[SubtitleSegment\] \- 번역된 텍스트 포함)  
47. translation\_handler.py: translate\_subtitles 함수 내부에 OpenAI GPT-4 API 호출 로직 구현 (자막 청크 분할, 프롬프트 구성, API Key 사용 \- config/settings.py 참조)  
48. translation\_handler.py: OpenAI API 응답 파싱 및 번역된 텍스트를 자막 데이터 구조에 업데이트하는 로직 구현  
49. translation\_handler.py: OpenAI API 관련 오류(인증, Rate Limit, 응답 오류 등) 처리 로직 추가  
50. app.py: "번역 및 TTS 생성 시작" 버튼 구현  
51. app.py: 버튼 클릭 시 st.session\_state에서 필요한 정보(자막 데이터, 언어) 가져와 translate\_subtitles함수 호출 로직 추가 (진행 중st.spinner 표시)  
52. app.py: 번역 성공 시 번역된 자막 데이터(List\[SubtitleSegment\]) st.session\_state에 저장 및 중간 성공 메시지 표시

**Phase 8: TTS 모델 준비 및 생성 로직 구현 (Coqui TTS 연동)**

53. (사전 작업) Coqui TTS 다국어 지원 모델 조사 및 초기 모델 선택 (예: tts\_models/multilingual/multi-dataset/xtts\_v2) \- Tech Stack 문서 업데이트 가능  
54. Dockerfile: 선택된 Coqui TTS 모델 다운로드 및 설치/설정 단계 추가 (빌드 시 또는 초기 실행 시)  
55. app/backend/tts\_handler.py 모듈 생성  
56. tts\_handler.py: generate\_tts\_audio 함수 정의 (입력: List\[SubtitleSegment\] \- 번역됨, 언어 코드. 출력: 생성된 오디오 파일 경로)  
57. tts\_handler.py: Coqui TTS 라이브러리 초기화 및 선택된 모델 로딩 로직 구현 (캐싱 고려)  
58. tts\_handler.py: 번역된 텍스트를 입력받아 TTS 실행 및 오디오 파일(/data/processed) 저장 로직 구현 (자막 시간 정보 활용 가능성 고려)  
59. tts\_handler.py: Coqui TTS 관련 오류(모델 로딩 실패, 음성 생성 실패 등) 처리 로직 추가  
60. app.py: 번역 성공 후 generate\_tts\_audio함수 자동 호출 로직 추가 (진행 중st.spinner 업데이트)  
61. app.py: TTS 생성 성공 시 생성된 오디오 파일 경로 st.session\_state에 저장 및 중간 성공 메시지 표시

**Phase 9: 최종 동영상 합성 로직 구현**

62. video\_processor.py: combine\_video 함수 정의 (입력: 원본/잘린 비디오 경로, 번역된 자막 데이터/경로(선택), TTS 오디오 경로. 출력: 최종 비디오 경로)  
63. video\_processor.py: combine\_video 함수 내부에 FFmpeg를 사용하여 비디오, 자막(하드섭 또는 소프트섭 \- 초기엔 하드섭 가정), 오디오를 합성하는 로직 구현  
64. video\_processor.py: FFmpeg 실행 관련 오류 처리 로직 추가  
65. app.py: TTS 생성 성공 후 combine\_video함수 자동 호출 로직 추가 (진행 중st.spinner 업데이트)  
66. app.py: 최종 동영상 생성 성공 시 최종 파일 경로 st.session\_state에 저장 및 "최종 동영상 생성 완료\!" 메시지(st.success) 표시

**Phase 10: 최종 동영상 다운로드 기능 구현**

67. app.py: 최종 동영상 정보(파일명, 크기 등) 표시 로직 구현  
68. app.py: 최종 동영상 다운로드 버튼 구현 (st.download\_button사용,st.session\_state의 최종 파일 경로 참조)

**Phase 11: 전체 흐름 연결 및 상태 관리 고도화**

69. app.py: 각 단계 완료 여부를 st.session\_state를 통해 명확히 추적하고, 이전 단계 미완료 시 다음 단계 UI 비활성화/숨김 처리 로직 구현  
70. app.py: 전체 프로세스 초기화(재시작) 버튼 및 관련 상태 초기화 로직 구현

**Phase 12: 각 단계별 오류 처리 로직 상세 구현 및 테스트**

71. 각 백엔드 함수(trim\_video, extract\_subtitles등) 내try...except 블록 상세화 및 구체적인 예외 처리 추가  
72. app.py: 백엔드 함수 호출 결과(성공/실패)에 따른 분기 처리 및 사용자 친화적 오류 메시지(st.error) 표시 강화  
73. 주요 오류 시나리오(파일 형식 오류, API 키 오류, 타임아웃, Faster Whisper 오류 등)에 대한 테스트 수행 및 오류 메시지 확인

**Phase 13: 단위 테스트 및 통합 테스트 코드 작성 (필요시)**

74. app/utils/time\_converter.py 등 순수 함수에 대한 단위 테스트 작성 (pytest 사용)  
75. (선택) 주요 백엔드 함수에 대한 통합 테스트 케이스 설계 (Mock 객체 활용)

**Phase 14: 로깅 및 최적화**

76. app/utils/logger\_config.py 모듈 생성 및 Python logging 설정 (파일 핸들러, 포맷터 등)  
77. app.py 및 각 백엔드 모듈에 로거 인스턴스 생성 및 주요 이벤트/오류 로깅 코드 추가 (logger.info, logger.error)  
78. (추후 고려) FFmpeg 명령어 옵션 검토 및 성능/품질 최적화 (예: 비디오/오디오 코덱, 비트레이트 설정, 자막 스타일링)

**(추가 고려 사항)**

* 비동기 처리 도입 (Streamlit 스레딩 또는 외부 Task Queue 고려) \- V2  
* 사용자 인증 및 작업 이력 관리 \- V2  
* ...