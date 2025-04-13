"""
동영상 번역 및 더빙 자동화 웹 애플리케이션의 메인 모듈입니다.
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch  # Import PyTorch first
import streamlit as st  # Then Streamlit
from loguru import logger

# 모듈 경로 추가
app_dir = Path(__file__).resolve().parent
if str(app_dir) not in sys.path:
    sys.path.append(str(app_dir))

# 내부 모듈 임포트
from config.settings import (
    ALLOWED_VIDEO_FORMATS,
    DEFAULT_SOURCE_LANGUAGE,
    LANGUAGE_NAMES,
    MAX_UPLOAD_SIZE_MB,
    SUPPORTED_LANGUAGES,
    WHISPER_MODEL_OPTIONS,
    WHISPER_MODEL_SIZE,
)
from schemas import SubtitleFile, SubtitleSegment, VideoInfo
from utils.file_handler import clean_temporary_files, save_uploaded_file, validate_video_file
from utils.logger_config import logger
from utils.time_converter import validate_time_range
from backend.video_processor import get_video_duration, trim_video
from backend.subtitle_handler import extract_subtitles, parse_srt_file, parse_uploaded_subtitle, save_subtitles_to_file
from backend.translation_handler import translate_subtitles, save_translated_subtitles


# 세션 상태 초기화
def init_session_state():
    """세션 상태 변수를 초기화합니다."""
    if "video_info" not in st.session_state:
        st.session_state.video_info = None
    
    if "subtitles" not in st.session_state:
        st.session_state.subtitles = None
    
    if "current_step" not in st.session_state:
        st.session_state.current_step = "upload"
    
    if "processing" not in st.session_state:
        st.session_state.processing = False
    
    if "translated_subtitles" not in st.session_state:
        st.session_state.translated_subtitles = {}
    
    if "tts_audio_paths" not in st.session_state:
        st.session_state.tts_audio_paths = {}
    
    if "result_videos" not in st.session_state:
        st.session_state.result_videos = {}


# 애플리케이션 헤더 표시
def show_header():
    """애플리케이션 헤더를 표시합니다."""
    st.title("KR AI VIDEO CONVERTER")
    st.markdown(
        """
        회사 내 전략회의, 교육 등의 내부 동영상을 한국어에서 대상 언어로 번역하고, 
        해당 언어의 자막 및 음성(TTS)을 자동으로 삽입하여 전 세계 직원들이 언어 장벽 없이 시청할 수 있도록 지원합니다.
        """
    )
    st.divider()


# 진행 단계 표시
def show_progress_steps():
    """작업 진행 단계를 시각적으로 표시합니다."""
    steps = {
        "upload": "1. 동영상 업로드",
        "extract": "2. 자막 추출",
        "translate": "3. 자막 번역",
        "tts": "4. 음성삽입",
        "result": "5. 최종 동영상 생성"
    }
    
    current_step = st.session_state.current_step
    
    # 진행 단계 인덱스
    step_index = list(steps.keys()).index(current_step)
    
    # 진행 상황 표시
    progress_bar = st.progress(step_index / (len(steps) - 1))
    
    # 단계 목록 표시
    cols = st.columns(len(steps))
    for i, (step_key, step_name) in enumerate(steps.items()):
        with cols[i]:
            if step_key == current_step:
                st.markdown(f"**:blue[{step_name}]**")
            elif i < step_index:
                st.markdown(f"~~{step_name}~~")
            else:
                st.markdown(step_name)
    
    st.divider()


# 업로드 페이지 표시
def show_upload_page():
    """동영상 업로드 및 자르기 페이지를 표시합니다."""
    st.header("1. 동영상 업로드")
    
    # 기존 업로드된 동영상 정보가 있는 경우 표시
    if st.session_state.video_info:
        video_info = st.session_state.video_info
        st.success(f"동영상이 업로드되었습니다: {video_info.original_name}")
        
        # 동영상 파일 정보 표시
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 파일 정보")
            st.write(f"파일명: {video_info.original_name}")
            st.write(f"파일 크기: {video_info.size / (1024 * 1024):.2f} MB")
            
            # 동영상 길이가 있는 경우 표시
            if video_info.duration_ms:
                minutes, seconds = divmod(video_info.duration_ms // 1000, 60)
                st.write(f"재생 시간: {minutes}분 {seconds}초")
        
        # 동영상 자르기 옵션
        with col2:
            st.markdown("#### 동영상 자르기 (선택 사항)")
            
            # 이미 잘린 경우 정보 표시
            if video_info.trimmed:
                trim_start = video_info.trim_start_ms // 1000
                trim_end = video_info.trim_end_ms // 1000 if video_info.trim_end_ms else "끝까지"
                
                st.info(f"동영상이 잘렸습니다: {trim_start}초 ~ {trim_end}초")
                
                if st.button("자르기 취소", key="cancel_trim"):
                    # 자르기 정보 초기화
                    video_info.trimmed = False
                    video_info.trim_start_ms = None
                    video_info.trim_end_ms = None
                    video_info.trimmed_path = None
                    st.session_state.video_info = video_info
                    st.rerun()
            else:
                # 자르기 시작/종료 시간 입력
                col_start, col_end = st.columns(2)
                with col_start:
                    start_time = st.text_input("시작 시간 (MM:SS)", value="", placeholder="예: 00:30")
                
                with col_end:
                    end_time = st.text_input("종료 시간 (MM:SS)", value="", placeholder="예: 05:30")
                
                # 자르기 버튼
                if st.button("동영상 자르기", key="trim_video"):
                    # 시간 형식 검증
                    is_valid, error_message = validate_time_range(start_time, end_time)
                    
                    if not is_valid:
                        st.error(error_message)
                    else:
                        # 동영상 자르기 진행
                        st.session_state.processing = True
                        with st.spinner("동영상 자르기 중..."):
                            from utils.time_converter import time_to_ms
                            
                            # 시간을 밀리초로 변환
                            start_ms = time_to_ms(start_time) if start_time else 0
                            end_ms = time_to_ms(end_time) if end_time else None
                            
                            try:
                                # 동영상 자르기 실행
                                trimmed_path = trim_video(
                                    video_info.path,
                                    start_ms=start_ms,
                                    end_ms=end_ms
                                )
                                
                                # 비디오 정보 업데이트
                                video_info.trimmed = True
                                video_info.trimmed_path = trimmed_path
                                video_info.trim_start_ms = start_ms
                                video_info.trim_end_ms = end_ms
                                
                                st.session_state.video_info = video_info
                                st.session_state.processing = False
                                st.rerun()
                            except Exception as e:
                                st.session_state.processing = False
                                st.error(f"동영상 자르기 중 오류가 발생했습니다: {str(e)}")
        
        # 다음 단계 진행 버튼
        st.divider()
        if st.button("다음 단계: 자막 추출", type="primary"):
            st.session_state.current_step = "extract"
            st.rerun()
        
        # 새 동영상 업로드 옵션
        with st.expander("새 동영상 업로드"):
            upload_new_video()
    else:
        # 새 동영상 업로드
        upload_new_video()


def upload_new_video():
    """새 동영상을 업로드하는 폼을 표시합니다."""
    # 파일 업로드 필드
    uploaded_file = st.file_uploader(
        f"동영상 파일 선택 (.{', .'.join(ALLOWED_VIDEO_FORMATS)})", 
        type=ALLOWED_VIDEO_FORMATS
    )
    
    # 업로드된 파일이 있는 경우
    if uploaded_file is not None:
        # 파일 유효성 검사 - 파일 크기 제한 제거
        is_valid = True
        error_message = ""
        
        if not is_valid:
            st.error(error_message)
        else:
            # 업로드 버튼
            if st.button("업로드", key="upload_video"):
                st.session_state.processing = True
                
                with st.spinner("동영상 처리 중..."):
                    try:
                        # 파일 저장
                        file_info = save_uploaded_file(uploaded_file)
                        
                        # 동영상 길이 확인
                        duration_ms = get_video_duration(file_info["path"])
                        
                        # VideoInfo 객체 생성
                        video_info = VideoInfo(
                            id=file_info["id"],
                            original_name=file_info["original_name"],
                            saved_name=file_info["saved_name"],
                            path=file_info["path"],
                            size=file_info["size"],
                            type=file_info["type"],
                            duration_ms=duration_ms,
                            trimmed=False
                        )
                        
                        # 세션 상태에 저장
                        st.session_state.video_info = video_info
                        st.session_state.processing = False
                        st.rerun()
                    except Exception as e:
                        st.session_state.processing = False
                        st.error(f"동영상 처리 중 오류가 발생했습니다: {str(e)}")


# 자막 추출 페이지 표시
def show_extract_page():
    """자막 추출 페이지를 표시합니다."""
    st.header("2. 자막 추출")
    
    # 비디오 정보 가져오기
    video_info = st.session_state.video_info
    if not video_info:
        st.error("업로드된 동영상이 없습니다.")
        if st.button("동영상 업로드로 돌아가기"):
            st.session_state.current_step = "upload"
            st.rerun()
        return
    
    # 비디오 파일 경로 설정 (자르기된 경우 해당 경로 사용)
    video_path = video_info.trimmed_path if video_info.trimmed else video_info.path
    
    # 기존 자막 정보가 있는 경우 표시
    if st.session_state.subtitles:
        subtitles = st.session_state.subtitles
        
        st.success(f"자막이 추출되었습니다: {len(subtitles.segments)}개 세그먼트")
        
        # 자막 미리보기 표시
        st.subheader("자막 미리보기")
        
        # 표 형식으로 자막 세그먼트 표시
        preview_data = []
        for segment in subtitles.segments[:10]:  # 처음 10개만 표시
            start_time = segment.start_ms // 1000
            end_time = segment.end_ms // 1000
            preview_data.append({
                "ID": segment.id,
                "시작": f"{start_time // 60:02d}:{start_time % 60:02d}",
                "종료": f"{end_time // 60:02d}:{end_time % 60:02d}",
                "텍스트": segment.text[:50] + ("..." if len(segment.text) > 50 else "")
            })
        
        st.table(preview_data)
        
        if len(subtitles.segments) > 10:
            st.info(f"전체 {len(subtitles.segments)}개 중 10개만 표시됩니다.")
        
        # 자막 다운로드 버튼
        st.download_button(
            label="자막 파일 다운로드 (SRT)",
            data=open(subtitles.file_path, "rb").read(),
            file_name=f"subtitle_{video_info.id}.srt",
            mime="text/plain"
        )
        
        # 자막 업로드 옵션
        with st.expander("편집된 자막 업로드 (선택 사항)"):
            edit_subtitle_upload()
        
        # 다음 단계 진행 버튼
        st.divider()
        if st.button("다음 단계: 자막 번역", type="primary"):
            st.session_state.current_step = "translate"
            st.rerun()
        
        # 이전 단계로 돌아가기
        if st.button("이전 단계로 돌아가기"):
            st.session_state.current_step = "upload"
            st.rerun()
    else:
        # 자막 추출 옵션
        st.subheader("자막 추출 방법 선택")
        
        extract_option = st.radio(
            "자막 추출 방법",
            ["동영상에서 자동 추출", "자막 파일 직접 업로드"],
            horizontal=True
        )
        
        if extract_option == "동영상에서 자동 추출":
            extract_from_video(video_path, video_info)
        else:
            upload_subtitle_file(video_info)


def extract_from_video(video_path: str, video_info: VideoInfo):
    """동영상에서 자막을 자동으로 추출합니다."""
    st.info("OpenAI Whisper API를 사용하여 동영상에서 자막을 자동으로 추출합니다.")
    
    # 모델 설정 UI
    with st.expander("Whisper API 설정", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # 모델 크기 선택
            try:
                default_index = list(WHISPER_MODEL_OPTIONS.keys()).index(WHISPER_MODEL_SIZE)
            except ValueError:
                # WHISPER_MODEL_SIZE가 목록에 없는 경우 기본값(첫 번째 항목)을 사용
                if 'large-v3' in WHISPER_MODEL_OPTIONS:
                    default_index = list(WHISPER_MODEL_OPTIONS.keys()).index('large-v3')
                else:
                    default_index = 0
                st.warning(f"설정된 모델 '{WHISPER_MODEL_SIZE}'는 사용할 수 없습니다. 기본 모델을 사용합니다.")
                
            model_size = st.selectbox(
                "모델 크기",
                list(WHISPER_MODEL_OPTIONS.keys()),
                index=default_index,
                format_func=lambda x: f"{x} - {WHISPER_MODEL_OPTIONS[x]}"
            )
            
            # 언어 선택
            language = st.selectbox(
                "언어",
                ["자동 감지", "ko", "en", "ja", "zh", "de"],
                format_func=lambda x: "자동 감지" if x == "자동 감지" else f"{x} - {LANGUAGE_NAMES.get(x, x)}"
            )
            
            # 언어 값 변환
            if language == "자동 감지":
                language = None
        
        with col2:
            # 고급 설정
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.1,
                help="높을수록 다양한 결과, 낮을수록 결정적인 결과"
            )
            
            timestamp_granularity = st.radio(
                "타임스탬프 정밀도",
                ["segment", "word"],
                index=0,
                format_func=lambda x: "세그먼트 단위" if x == "segment" else "단어 단위",
                help="단어 단위는 더 정밀하지만 처리 시간이 더 길어집니다"
            )
        
        # 초기 프롬프트 설정
        initial_prompt = st.text_area(
            "초기 프롬프트 (선택 사항)",
            placeholder="특정 형식이나 도메인에 맞는 힌트를 제공할 수 있습니다",
            help="Whisper가 인식을 시작할 때 제공하는 컨텍스트입니다",
            max_chars=500
        )
    
    # 추출 버튼
    if st.button("자막 추출 시작", key="extract_button"):
        st.session_state.processing = True
        
        with st.spinner("자막 추출 중... (이 작업은 몇 분 정도 소요될 수 있습니다)"):
            try:
                # 자막 추출
                subtitle_path = extract_subtitles(
                    video_path=video_path,
                    model_size=model_size,
                    language=language,
                    temperature=temperature,
                    initial_prompt=initial_prompt if initial_prompt else None,
                    timestamp_granularity=timestamp_granularity
                )
                
                # 추출된 자막 파싱
                segments = parse_srt_file(subtitle_path)
                
                # SubtitleFile 객체 생성
                subtitle_file = SubtitleFile(
                    file_id=video_info.id,
                    segments=segments,
                    source_language=language or DEFAULT_SOURCE_LANGUAGE,
                    source_video_path=video_path,
                    file_path=subtitle_path
                )
                
                # 세션 상태에 저장
                st.session_state.subtitles = subtitle_file
                st.session_state.processing = False
                st.rerun()
            except Exception as e:
                st.session_state.processing = False
                st.error(f"자막 추출 중 오류가 발생했습니다: {str(e)}")


def upload_subtitle_file(video_info: VideoInfo):
    """자막 파일을 직접 업로드합니다."""
    st.info("SRT 또는 TXT 형식의 자막 파일을 직접 업로드합니다.")
    
    # 파일 업로드 필드
    uploaded_file = st.file_uploader(
        "자막 파일 선택 (.srt, .txt)",
        type=["srt", "txt"],
        help="SRT 또는 TXT(시작ms - 종료ms - 내용) 형식의 파일만 지원합니다."
    )
    
    # 업로드된 파일이 있는 경우
    if uploaded_file is not None:
        # 업로드 버튼
        if st.button("자막 파일 업로드", key="upload_subtitle"):
            st.session_state.processing = True
            
            with st.spinner("자막 파일 처리 중..."):
                try:
                    # 자막 파일 파싱
                    subtitle_path, segments = parse_uploaded_subtitle(uploaded_file)
                    
                    # SubtitleFile 객체 생성
                    subtitle_file = SubtitleFile(
                        file_id=video_info.id,
                        segments=segments,
                        source_language=DEFAULT_SOURCE_LANGUAGE,
                        source_video_path=video_info.path,
                        file_path=subtitle_path
                    )
                    
                    # 세션 상태에 저장
                    st.session_state.subtitles = subtitle_file
                    st.session_state.processing = False
                    st.rerun()
                except Exception as e:
                    st.session_state.processing = False
                    st.error(f"자막 파일 처리 중 오류가 발생했습니다: {str(e)}")


def edit_subtitle_upload():
    """편집된 자막 파일을 업로드합니다."""
    st.markdown("자막을 편집한 후 업로드하여 기존 자막을 대체할 수 있습니다.")
    
    # 파일 업로드 필드
    edited_file = st.file_uploader(
        "편집된 자막 파일 선택 (.srt, .txt)",
        type=["srt", "txt"],
        key="edited_subtitle",
        help="SRT 또는 TXT(시작ms - 종료ms - 내용) 형식의 파일만 지원합니다."
    )
    
    # 업로드된 파일이 있는 경우
    if edited_file is not None:
        # 업로드 버튼
        if st.button("편집된 자막 업로드", key="upload_edited_subtitle"):
            st.session_state.processing = True
            
            with st.spinner("자막 파일 처리 중..."):
                try:
                    video_info = st.session_state.video_info
                    
                    # 자막 파일 파싱
                    subtitle_path, segments = parse_uploaded_subtitle(edited_file)
                    
                    # SubtitleFile 객체 생성
                    subtitle_file = SubtitleFile(
                        file_id=video_info.id,
                        segments=segments,
                        source_language=DEFAULT_SOURCE_LANGUAGE,
                        source_video_path=video_info.path,
                        file_path=subtitle_path
                    )
                    
                    # 세션 상태에 저장
                    st.session_state.subtitles = subtitle_file
                    st.session_state.processing = False
                    st.success("편집된 자막이 업로드되었습니다.")
                    st.rerun()
                except Exception as e:
                    st.session_state.processing = False
                    st.error(f"자막 파일 처리 중 오류가 발생했습니다: {str(e)}")


# 자막 번역 페이지 표시
def show_translate_page():
    """자막 번역 페이지를 표시합니다."""
    st.header("3. 자막 번역")
    
    # 자막 정보 가져오기
    subtitles = st.session_state.subtitles
    if not subtitles:
        st.error("추출된 자막이 없습니다.")
        if st.button("자막 추출로 돌아가기"):
            st.session_state.current_step = "extract"
            st.rerun()
        return
    
    # 번역 설정
    st.subheader("번역 설정")
    
    # 원본 언어 표시
    st.write(f"원본 언어: {LANGUAGE_NAMES.get(subtitles.source_language, '한국어')}")
    
    # 대상 언어 선택
    target_language_options = {code: name for code, name in LANGUAGE_NAMES.items() 
                               if code in SUPPORTED_LANGUAGES and code != subtitles.source_language}
    
    target_language = st.selectbox(
        "대상 언어 선택",
        options=list(target_language_options.keys()),
        format_func=lambda x: target_language_options[x],
        help="번역할 대상 언어를 선택하세요."
    )
    
    # 이미 번역된 언어가 있는 경우 표시
    if st.session_state.translated_subtitles:
        st.success(f"번역된 언어: {', '.join([LANGUAGE_NAMES.get(lang, lang) for lang in st.session_state.translated_subtitles.keys()])}")
    
    # 번역 실행 버튼
    if st.button("번역 시작", key="translate_button"):
        # 이미 번역된 언어인 경우 확인
        if target_language in st.session_state.translated_subtitles:
            if not st.warning(f"{LANGUAGE_NAMES.get(target_language, target_language)}로 이미 번역되어 있습니다. 다시 번역하시겠습니까?"):
                return
        
        st.session_state.processing = True
        
        with st.spinner(f"{LANGUAGE_NAMES.get(target_language, target_language)}로 번역 중..."):
            try:
                # 자막 번역
                translated_segments = translate_subtitles(
                    subtitles.segments,
                    target_language=target_language,
                    source_language=subtitles.source_language
                )
                
                # 번역된 자막 파일 저장
                srt_path, txt_path = save_translated_subtitles(
                    translated_segments,
                    target_language=target_language,
                    file_id=subtitles.file_id
                )
                
                # 번역 결과 저장
                st.session_state.translated_subtitles[target_language] = {
                    "segments": translated_segments,
                    "srt_path": srt_path,
                    "txt_path": txt_path
                }
                
                st.session_state.processing = False
                st.success(f"{LANGUAGE_NAMES.get(target_language, target_language)}로 번역이 완료되었습니다.")
                st.rerun()
            except Exception as e:
                st.session_state.processing = False
                st.error(f"번역 중 오류가 발생했습니다: {str(e)}")
    
    # 번역 결과 표시
    if target_language in st.session_state.translated_subtitles:
        st.subheader("번역 결과")
        
        translated_data = st.session_state.translated_subtitles[target_language]
        segments = translated_data["segments"]
        
        # 표 형식으로 원본과 번역 결과 표시
        preview_data = []
        for segment in segments[:5]:  # 처음 5개만 표시
            preview_data.append({
                "ID": segment.id,
                "원본": segment.text[:40] + ("..." if len(segment.text) > 40 else ""),
                "번역": segment.translated_text[:40] + ("..." if len(segment.translated_text) > 40 else "")
            })
        
        st.table(preview_data)
        
        if len(segments) > 5:
            st.info(f"전체 {len(segments)}개 중 5개만 표시됩니다.")
        
        # 번역 결과 다운로드 버튼
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label=f"번역 자막 다운로드 (SRT - {LANGUAGE_NAMES.get(target_language, target_language)})",
                data=open(translated_data["srt_path"], "rb").read(),
                file_name=f"translated_{subtitles.file_id}_{target_language}.srt",
                mime="text/plain"
            )
        
        with col2:
            st.download_button(
                label=f"번역 자막 다운로드 (TXT - {LANGUAGE_NAMES.get(target_language, target_language)})",
                data=open(translated_data["txt_path"], "rb").read(),
                file_name=f"translated_{subtitles.file_id}_{target_language}.txt",
                mime="text/plain"
            )
    
    # 다음 단계 진행 버튼
    st.divider()
    
    # 번역된 언어가 있는 경우에만 다음 단계 활성화
    if st.session_state.translated_subtitles:
        if st.button("다음 단계: 음성삽입", type="primary"):
            st.session_state.current_step = "tts"
            st.rerun()
    else:
        st.warning("다음 단계로 진행하기 위해서는 최소 하나의 언어로 번역해야 합니다.")
    
    # 이전 단계로 돌아가기
    if st.button("이전 단계로 돌아가기"):
        st.session_state.current_step = "extract"
        st.rerun()


# TTS 생성 페이지 표시
def show_tts_page():
    """TTS 생성 페이지를 표시합니다."""
    st.header("4. 음성삽입")
    
    # 번역 결과 가져오기
    translated_subtitles = st.session_state.translated_subtitles
    if not translated_subtitles:
        st.error("번역된 자막이 없습니다.")
        if st.button("자막 번역으로 돌아가기"):
            st.session_state.current_step = "translate"
            st.rerun()
        return
    
    # TTS 설정
    st.subheader("TTS 설정")
    
    # 원본 비디오 정보 가져오기
    video_info = st.session_state.video_info
    subtitles = st.session_state.subtitles
    
    # 대상 언어 선택
    target_language_options = {code: LANGUAGE_NAMES.get(code, code) for code in translated_subtitles.keys()}
    
    target_language = st.selectbox(
        "TTS 생성 언어 선택",
        options=list(target_language_options.keys()),
        format_func=lambda x: target_language_options[x],
        help="TTS 음성을 생성할 언어를 선택하세요."
    )
    
    # 음성 성별 선택
    gender = st.radio(
        "음성 성별",
        options=["female", "male"],
        format_func=lambda x: "여성" if x == "female" else "남성",
        horizontal=True
    )
    
    # 이미 생성된 TTS가 있는 경우 표시
    tts_key = f"{target_language}_{gender}"
    if tts_key in st.session_state.tts_audio_paths:
        st.success(f"{target_language_options[target_language]} ({gender}) TTS가 이미 생성되었습니다.")
        
        # 오디오 미리 듣기
        audio_path = st.session_state.tts_audio_paths[tts_key]
        st.audio(audio_path, format="audio/wav")
    
    # TTS 생성 버튼
    if st.button("TTS 생성 시작", key="tts_button"):
        # 이미 생성된 TTS인 경우 확인
        if tts_key in st.session_state.tts_audio_paths:
            if not st.warning(f"{target_language_options[target_language]} ({gender}) TTS가 이미 생성되어 있습니다. 다시 생성하시겠습니까?"):
                return
        
        st.session_state.processing = True
        
        with st.spinner(f"{target_language_options[target_language]} TTS 생성 중... (이 작업은 몇 분 정도 소요될 수 있습니다)"):
            try:
                # TTS 모듈 임포트
                from backend.tts_handler import generate_tts_audio
                
                # 번역된 세그먼트 가져오기
                segments = translated_subtitles[target_language]["segments"]
                
                # TTS 생성
                audio_path = generate_tts_audio(
                    segments=segments,
                    target_language=target_language,
                    file_id=subtitles.file_id,
                    gender=gender
                )
                
                # TTS 결과 저장
                st.session_state.tts_audio_paths[tts_key] = audio_path
                
                st.session_state.processing = False
                st.success(f"{target_language_options[target_language]} ({gender}) TTS 생성이 완료되었습니다.")
                st.rerun()
            except Exception as e:
                st.session_state.processing = False
                st.error(f"TTS 생성 중 오류가 발생했습니다: {str(e)}")
    
    # 생성된 TTS 목록 표시
    if st.session_state.tts_audio_paths:
        st.subheader("생성된 TTS 목록")
        
        for tts_key, audio_path in st.session_state.tts_audio_paths.items():
            lang, gender = tts_key.split("_")
            lang_name = LANGUAGE_NAMES.get(lang, lang)
            gender_name = "여성" if gender == "female" else "남성"
            
            st.markdown(f"**{lang_name} ({gender_name})**")
            st.audio(audio_path, format="audio/wav")
    
    # 다음 단계 진행 버튼
    st.divider()
    
    # TTS가 생성된 경우에만 다음 단계 활성화
    if st.session_state.tts_audio_paths:
        if st.button("다음 단계: 최종 동영상 생성", type="primary"):
            st.session_state.current_step = "result"
            st.rerun()
    else:
        st.warning("다음 단계로 진행하기 위해서는 최소 하나의 TTS를 생성해야 합니다.")
    
    # 이전 단계로 돌아가기
    if st.button("이전 단계로 돌아가기"):
        st.session_state.current_step = "translate"
        st.rerun()


# 최종 동영상 생성 페이지 표시
def show_result_page():
    """최종 동영상 생성 페이지를 표시합니다."""
    st.header("5. 최종 동영상 생성")
    
    # 필요한 데이터 가져오기
    video_info = st.session_state.video_info
    subtitles = st.session_state.subtitles
    translated_subtitles = st.session_state.translated_subtitles
    tts_audio_paths = st.session_state.tts_audio_paths
    
    # 모든 필수 데이터가 있는지 확인
    if not (video_info and subtitles and translated_subtitles and tts_audio_paths):
        missing = []
        if not video_info:
            missing.append("동영상")
        if not subtitles:
            missing.append("자막")
        if not translated_subtitles:
            missing.append("번역된 자막")
        if not tts_audio_paths:
            missing.append("TTS 오디오")
        
        st.error(f"다음 데이터가 누락되었습니다: {', '.join(missing)}")
        if st.button("이전 단계로 돌아가기"):
            st.session_state.current_step = "tts"
            st.rerun()
        return
    
    # 동영상 생성 설정
    st.subheader("최종 동영상 생성 설정")
    
    # 비디오 파일 경로 설정 (자르기된 경우 해당 경로 사용)
    video_path = video_info.trimmed_path if video_info.trimmed else video_info.path
    
    # 대상 언어 및 TTS 선택
    tts_options = {}
    for tts_key in tts_audio_paths.keys():
        lang, gender = tts_key.split("_")
        lang_name = LANGUAGE_NAMES.get(lang, lang)
        gender_name = "여성" if gender == "female" else "남성"
        tts_options[tts_key] = f"{lang_name} ({gender_name})"
    
    selected_tts = st.selectbox(
        "생성할 동영상 언어 및 음성 선택",
        options=list(tts_options.keys()),
        format_func=lambda x: tts_options[x],
        help="최종 동영상을 생성할 언어와 음성을 선택하세요."
    )
    
    # 자막 포함 여부
    include_subtitles = st.checkbox("자막 포함", value=True, help="최종 동영상에 자막을 포함할지 여부")
    
    # 선택한 TTS 정보 분리
    target_language, gender = selected_tts.split("_")
    
    # 이미 생성된 결과 동영상이 있는 경우 표시
    if selected_tts in st.session_state.result_videos:
        result_path = st.session_state.result_videos[selected_tts]
        st.success(f"{tts_options[selected_tts]} 동영상이 이미 생성되었습니다.")
        
        # 다운로드 버튼
        video_filename = f"result_{video_info.id}_{target_language}_{gender}.mp4"
        with open(result_path, "rb") as file:
            st.download_button(
                label=f"결과 동영상 다운로드 ({tts_options[selected_tts]})",
                data=file,
                file_name=video_filename,
                mime="video/mp4"
            )
    
    # 동영상 생성 버튼
    if st.button("최종 동영상 생성", key="result_button"):
        # 이미 생성된 동영상인 경우 확인
        if selected_tts in st.session_state.result_videos:
            if not st.warning(f"{tts_options[selected_tts]} 동영상이 이미 생성되어 있습니다. 다시 생성하시겠습니까?"):
                return
        
        st.session_state.processing = True
        
        with st.spinner(f"{tts_options[selected_tts]} 동영상 생성 중... (이 작업은 몇 분 정도 소요될 수 있습니다)"):
            try:
                # 동영상 처리 모듈 임포트
                from backend.video_processor import combine_video
                
                # 필요한 파일 경로 가져오기
                audio_path = tts_audio_paths[selected_tts]
                
                # 자막 파일 경로 (옵션)
                subtitle_path = None
                if include_subtitles:
                    subtitle_path = translated_subtitles[target_language]["srt_path"]
                
                # 최종 동영상 생성
                result_path = combine_video(
                    video_path=video_path,
                    audio_path=audio_path,
                    subtitle_path=subtitle_path,
                    target_language=target_language
                )
                
                # 결과 저장
                st.session_state.result_videos[selected_tts] = result_path
                
                st.session_state.processing = False
                st.success(f"{tts_options[selected_tts]} 동영상 생성이 완료되었습니다.")
                st.rerun()
            except Exception as e:
                st.session_state.processing = False
                st.error(f"동영상 생성 중 오류가 발생했습니다: {str(e)}")
    
    # 생성된 동영상 목록 표시
    if st.session_state.result_videos:
        st.subheader("생성된 동영상 목록")
        
        for tts_key, result_path in st.session_state.result_videos.items():
            lang, gender = tts_key.split("_")
            lang_name = LANGUAGE_NAMES.get(lang, lang)
            gender_name = "여성" if gender == "female" else "남성"
            
            st.markdown(f"**{lang_name} ({gender_name})**")
            
            video_filename = f"result_{video_info.id}_{lang}_{gender}.mp4"
            with open(result_path, "rb") as file:
                st.download_button(
                    label=f"결과 동영상 다운로드 ({lang_name}, {gender_name})",
                    data=file,
                    file_name=video_filename,
                    mime="video/mp4",
                    key=f"download_{lang}_{gender}"
                )
    
    # 작업 초기화 버튼
    st.divider()
    if st.button("새 작업 시작", type="primary"):
        # 세션 상태 초기화
        for key in ["video_info", "subtitles", "translated_subtitles", "tts_audio_paths", "result_videos"]:
            if key in st.session_state:
                del st.session_state[key]
        
        st.session_state.current_step = "upload"
        st.rerun()
    
    # 이전 단계로 돌아가기
    if st.button("이전 단계로 돌아가기"):
        st.session_state.current_step = "tts"
        st.rerun()


# 메인 함수
def main():
    """애플리케이션 메인 함수입니다."""
    # 페이지 설정
    st.set_page_config(
        page_title="동영상 번역 및 더빙 자동화 툴",
        page_icon="🎬",
        layout="wide"
    )
    
    # 세션 상태 초기화
    init_session_state()
    
    # 헤더 표시
    show_header()
    
    # 진행 단계 표시
    show_progress_steps()
    
    # 현재 단계에 따른 UI 표시
    if st.session_state.current_step == "upload":
        show_upload_page()
    elif st.session_state.current_step == "extract":
        show_extract_page()
    elif st.session_state.current_step == "translate":
        show_translate_page()
    elif st.session_state.current_step == "tts":
        show_tts_page()
    elif st.session_state.current_step == "result":
        show_result_page()


# 애플리케이션 시작점
if __name__ == "__main__":
    main() 