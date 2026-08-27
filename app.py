import os
import json
import math
import subprocess
import tempfile
from typing import Any, Dict, List, Union

import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types


# ==============================================================================
# 1. 환경 설정 및 페이지 구성
# ==============================================================================

load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기 | Studio Edition",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 방송실/편집실 테마 Custom CSS
st.markdown("""
<style>
    /* 전체 배경 및 폰트 톤앤매너 */
    .stApp {
        background-color: #0f1117;
        color: #e0e6ed;
    }
    
    /* 카드 스타일링 */
    .highlight-card {
        background-color: #1a1d26;
        border: 1px solid #2e3440;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    /* 하이라이트 번호 배지 */
    .badge-index {
        background-color: #2563eb;
        color: #ffffff;
        font-weight: 700;
        font-size: 0.85rem;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
        margin-bottom: 8px;
    }
    
    .badge-time {
        background-color: #059669;
        color: #ffffff;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
        margin-left: 8px;
    }
    
    /* 타이틀 강조 */
    .card-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f3f4f6;
        margin-top: 6px;
        margin-bottom: 4px;
    }
    
    .card-subtitle {
        font-size: 0.95rem;
        color: #9ca3af;
        margin-bottom: 12px;
    }
    
    .card-reason {
        font-size: 0.9rem;
        color: #d1d5db;
        background-color: #262b36;
        padding: 10px 14px;
        border-left: 3px solid #2563eb;
        border-radius: 4px;
    }
</style>
""", unsafe_text_html=True)


# ==============================================================================
# 2. 메인 헤더 UI
# ==============================================================================

st.title("🎬 뉴스 숏폼 하이라이트 자동 추출기")
st.caption("Broadcast News Short-form Automation & EDIUS EDL Generator")

st.markdown(
    """
    뉴스 파일(음성/영상)을 업로드하면 **Groq Whisper**를 통해 자막과 타임코드를 추출하고, 
    **Gemini AI**가 숏폼(YouTube Shorts, Reels, TikTok)에 최적화된 30~60초 주요 구간 3곳을 자동으로 선정합니다.
    """
)

st.info("💡 모든 타임코드는 NTSC Drop Frame(29.97fps) 기반으로 계산되며, EDIUS 호환 CMX 3600 EDL로 내보낼 수 있습니다.")
st.divider()


# ==============================================================================
# 3. 유틸리티 함수
# ==============================================================================

def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Dict 및 SDK Response 객체 양쪽에서 안전하게 값을 추출하는 헬퍼 함수"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def prepare_audio_for_groq(input_file_path: str) -> str:
    """
    대용량 영상/음성 파일을 Groq API 전송 기준(25MB 이하)에 맞춰
    16kHz / mono / 32kbps MP3로 변환한다.
    """
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()

    cmd = [
        "ffmpeg", "-y", "-i", input_file_path,
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
        "-f", "mp3", output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        error_message = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"오디오 최적화 변환에 실패했습니다.\n{error_message}")


def seconds_to_df_timecode(seconds: float) -> str:
    """초 단위 시간을 NTSC Drop Frame Timecode (29.97fps / HH:MM:SS;FF) 형식으로 변환"""
    seconds = max(0.0, float(seconds))
    total_frames = int(round(seconds * 29.97))

    D = total_frames // 17982
    M = total_frames % 17982

    if M >= 2:
        total_frames += 18 * D + 2 * ((M - 2) // 1798)
    else:
        total_frames += 18 * D

    frames = total_frames % 30
    total_seconds = total_frames // 30
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60

    return f"{hh:02d}:{mm:02d}:{ss:02d};{frames:02d}"


def seconds_to_min_sec(seconds: float) -> str:
    """UI 표시용 mm:ss 변환"""
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def get_media_duration(file_path: str) -> float:
    """FFprobe를 이용해 원본 미디어의 전체 재생 시간을 측정"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def generate_edl(highlights: list, reel_name: str = "AX0101") -> str:
    """EDIUS 연동 CMX 3600 EDL 생성"""
    edl_lines = [
        "TITLE: NEWS_SHORTFORM_HIGHLIGHTS",
        "FMT: NTSC DF",
        "",
    ]

    for idx, item in enumerate(highlights, 1):
        start_time = float(_get_val(item, "start_time", 0.0))
        end_time = float(_get_val(item, "end_time", 0.0))

        src_in = seconds_to_df_timecode(start_time)
        src_out = seconds_to_df_timecode(end_time)

        main_title = str(_get_val(item, "main_title", "Highlight"))
        sub_title = str(_get_val(item, "sub_title", ""))

        edl_lines.append(
            f"{idx:03d}  {reel_name:<8} AA/V  C        {src_in} {src_out} {src_in} {src_out}"
        )
        edl_lines.append(f"* FROM CLIP: {main_title}")
        edl_lines.append(f"* COMMENTS: {sub_title}")
        edl_lines.append("")

    return "\n".join(edl_lines)


# ==============================================================================
# 4. Groq Whisper STT API
# ==============================================================================

def run_whisper_stt(client: Groq, audio_path: str) -> List[Any]:
    """Groq Whisper API를 호출하여 타임코드가 포함된 segments 반환"""
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    
    # Groq API의 25MB 용량 제한 검증
    if file_size_mb > 24.5:
        raise RuntimeError("최적화된 오디오 파일 크기가 25MB를 초과하여 Groq API로 전송할 수 없습니다.")

    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="ko",
        )

    return _get_val(transcription, "segments", [])


# ==============================================================================
# 5. 하이라이트 데이터 검증 (Python Validation)
# ==============================================================================

def sanitize_and_fix_highlights(raw_highlights: list, media_duration: float = 0.0) -> list:
    """Gemini 반환 데이터에 대한 엄격한 30~60초 무결성 검증 및 교정"""
    fixed_list = []
    if not isinstance(raw_highlights, list):
        return fixed_list

    for item in raw_highlights:
        try:
            start_time = float(_get_val(item, "start_time", 0.0))
            end_time = float(_get_val(item, "end_time", 0.0))

            start_time = max(0.0, start_time)
            end_time = max(0.0, end_time)

            if start_time > end_time:
                start_time, end_time = end_time, start_time

            if media_duration > 0:
                start_time = min(start_time, media_duration)
                end_time = min(end_time, media_duration)

            duration = end_time - start_time

            # 최소 30초 보장
            if duration < 30.0:
                candidate_end = start_time + 30.0
                if media_duration > 0 and candidate_end > media_duration:
                    continue
                end_time = candidate_end

            # 최대 60초 제한
            duration = end_time - start_time
            if duration > 60.0:
                end_time = start_time + 60.0

            duration = end_time - start_time
            if not (start_time < end_time and 30.0 <= duration <= 60.0):
                continue

            fixed_item = {
                "main_title": str(_get_val(item, "main_title", "하이라이트")),
                "sub_title": str(_get_val(item, "sub_title", "")),
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "reason": str(_get_val(item, "reason", ""))
            }
            fixed_list.append(fixed_item)

        except (TypeError, ValueError):
            continue

    return fixed_list


# ==============================================================================
# 6. Gemini 하이라이트 추출 (2026 최신 Gemini SDK 호환)
# ==============================================================================

def run_gemini_highlight_extraction(
    gemini_api_key: str,
    segments: list,
    media_duration: float = 0.0,
) -> list:

    client = genai.Client(api_key=gemini_api_key)

    # 2026년 기준 사용 가능한 추천 모델 라인업 (gemini-2.0-flash 제외)
    preferred_models = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-2.5-flash",
    ]

    # Transcript 텍스트 생성 (Dict/Object 호환)
    formatted_transcript = []
    for segment in segments:
        start = round(float(_get_val(segment, "start", 0)), 2)
        end = round(float(_get_val(segment, "end", 0)), 2)
        text = str(_get_val(segment, "text", "")).strip()

        if text:
            formatted_transcript.append(f"[{start:.2f}s ~ {end:.2f}s] {text}")

    transcript_text = "\n".join(formatted_transcript)

    prompt = f"""
너는 뉴스 방송 수석 에디터이자 YouTube Shorts, TikTok 전문 콘텐츠 크리에이터이다.
아래 뉴스 자막 데이터의 타임코드를 정확하게 분석하여 숏폼으로 제작하기 가장 적합한 구간 3곳을 선정하라.

[필수 규칙]
1. 정확히 3개의 하이라이트를 반환한다.
2. start_time은 반드시 end_time보다 작아야 한다.
3. 각 구간의 길이는 반드시 30초 이상 60초 이하여야 한다.
4. start_time은 선택한 첫 번째 자막의 시작 시간이다.
5. end_time은 선택한 마지막 자막의 종료 시간이다.
6. 문장이 중간에서 잘리지 않고 완결된 의미를 전달해야 한다.
7. 서로 지나치게 겹치는 구간은 피한다.
8. 영상 전체 길이는 약 {media_duration:.2f}초이다.

[뉴스 자막 데이터]
{transcript_text}
"""

    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "main_title": {"type": "STRING", "description": "메인 타이틀. 15자 이내."},
                    "sub_title": {"type": "STRING", "description": "핵심 요약. 25자 이내."},
                    "start_time": {"type": "NUMBER", "description": "구간 시작 시간 (초)"},
                    "end_time": {"type": "NUMBER", "description": "구간 종료 시간 (초)"},
                    "reason": {"type": "STRING", "description": "해당 구간 선정 이유"},
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "reason"],
            },
        },
        temperature=0.1,
    )

    last_exception = None

    for model_name in preferred_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gen_config,
            )

            raw_data = json.loads(response.text)
            sanitized_data = sanitize_and_fix_highlights(raw_data, media_duration)

            if len(sanitized_data) == 3:
                return sanitized_data

            last_exception = RuntimeError(f"모델 {model_name}이 유효한 3개 하이라이트 조건을 만족하지 못했습니다.")

        except Exception as error:
            last_exception = error
            continue

    raise RuntimeError("모든 Gemini 모델 시도 후에도 하이라이트 추출에 실패했습니다.") from last_exception


# ==============================================================================
# 7. API 키 검증
# ==============================================================================

def get_api_keys():
    groq_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    gemini_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    return groq_key, gemini_key


# ==============================================================================
# 8. 메인 애플리케이션
# ==============================================================================

def main():
    groq_api_key, gemini_api_key = get_api_keys()

    if not groq_api_key or not gemini_api_key:
        st.error("🔑 API 키가 설정되지 않았증니다. Secrets 또는 .env 파일을 확인해주세요.")
        st.stop()

    groq_client = Groq(api_key=groq_api_key)

    # ------------------------------------------------------------------
    # 1. 파일 업로드 영역
    # ------------------------------------------------------------------
    st.subheader("1. 뉴스 미디어 파일 업로드")
    
    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 선택하세요 (최대 1GB)",
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"],
        help="MP4, TS, MOV 등의 영상 파일이나 MP3, WAV 등의 오디오 파일을 업로드할 수 있습니다."
    )

    if uploaded_file is None:
        st.info("📌 분석을 진행할 미디어 파일을 상단에 업로드해주세요.")
        return

    file_size_mb = uploaded_file.size / (1024 * 1024)
    st.success(f"📁 선택된 파일: `{uploaded_file.name}` ({file_size_mb:.2f} MB)")

    if uploaded_file.size > (1024 * 1024 * 1024):
        st.error("⚠️ 파일 크기가 1GB를 초과합니다. 1GB 이하의 파일을 업로드해주세요.")
        return

    # ------------------------------------------------------------------
    # 2. 실행 컨트롤
    # ------------------------------------------------------------------
    st.subheader("2. AI 분석 실행")
    start_button = st.button(
        "⚡ 하이라이트 추출 및 EDL 생성 시작",
        type="primary",
        use_container_width=True
    )

    if not start_button:
        return

    raw_input_path = None
    processed_audio_path = None

    try:
        with st.status("🎬 뉴스 미디어 분석 프로세스 진행 중...", expanded=True) as status:
            
            # Step 1: 임시 저장 & FFmpeg 최적화
            st.write("🔄 **1단계:** 미디어 파일 수신 및 Groq 전달용 오디오 변환 중 (16kHz / Mono / MP3)...")
            suffix = "." + uploaded_file.name.split(".")[-1]
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                chunk_size = 8 * 1024 * 1024
                while True:
                    chunk = uploaded_file.read(chunk_size)
                    if not chunk:
                        break
                    tmp.write(chunk)
                raw_input_path = tmp.name

            media_duration = get_media_duration(raw_input_path)
            processed_audio_path = prepare_audio_for_groq(raw_input_path)
            st.write(f"✅ 오디오 최적화 완료 (전체 재생 시간: {seconds_to_min_sec(media_duration)})")

            # Step 2: Groq Whisper STT
            st.write("🎙️ **2단계:** Groq Whisper-large-v3를 사용해 자막 및 타임코드 추출 중...")
            segments = run_whisper_stt(groq_client, processed_audio_path)
            
            if not segments:
                raise RuntimeError("음성 인식 결과 자막 데이터를 추출하지 못했습니다.")
            st.write(f"✅ 자막 추출 완료 (총 {len(segments)}개 구문 타임코드 확보)")

            # Step 3: Gemini 하이라이트 분석
            st.write("🧠 **3단계:** Gemini AI가 숏폼 맥락을 고려하여 30~60초 하이라이트 3곳 선정 중...")
            highlights = run_gemini_highlight_extraction(gemini_api_key, segments, media_duration)
            st.write("✅ 하이라이트 구간 검증 완료 (3개 구간 30~60초 조건 충족)")

            # Step 4: EDL 생성
            st.write("📼 **4단계:** EDIUS NLE 연동용 CMX 3600 EDL 타임코드 바인딩 중...")
            edl_content = generate_edl(highlights)
            st.write("✅ EDL 데이터 바인딩 완료")

            status.update(
                label="🎉 모든 하이라이트 분석 및 EDL 생성이 완료되었습니다!",
                state="complete",
                expanded=False
            )

        # ------------------------------------------------------------------
        # 3. 결과 리포트 (Dashboard Card Layout)
        # ------------------------------------------------------------------
        st.subheader("3. 추천 숏폼 하이라이트 분석 결과")

        for index, item in enumerate(highlights, 1):
            start_sec = float(item["start_time"])
            end_sec = float(item["end_time"])
            duration = round(end_sec - start_sec, 1)

            st.markdown(f"""
            <div class="highlight-card">
                <div>
                    <span class="badge-index">구간 {index}</span>
                    <span class="badge-time">⏱️ {duration}초 ({seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)})</span>
                </div>
                <div class="card-title">{item['main_title']}</div>
                <div class="card-subtitle">{item['sub_title']}</div>
                <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 8px;">
                    🎯 NTSC DF Timecode: <code>{seconds_to_df_timecode(start_sec)}</code> ~ <code>{seconds_to_df_timecode(end_sec)}</code>
                </div>
                <div class="card-reason">
                    <strong>💡 AI 선정 이유:</strong> {item['reason']}
                </div>
            </div>
            """, unsafe_text_html=True)

        # ------------------------------------------------------------------
        # 4. EDL 다운로드
        # ------------------------------------------------------------------
        st.divider()
        st.subheader("4. NLE 내보내기 (EDIUS EDL)")
        
        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"

        col1, col2 = st.columns([2, 1])
        with col1:
            st.write("생성된 EDL 파일을 다운로드하여 EDIUS 시퀀스 타임라인으로 직접 컷 편집본을 가져올 수 있습니다.")
        with col2:
            st.download_button(
                label="📥 EDIUS EDL 파일 다운로드",
                data=edl_content,
                file_name=edl_filename,
                mime="text/plain",
                use_container_width=True
            )

    except Exception as error:
        st.error("🚨 분석 중 오류가 발생했습니다.")
        st.warning("• 업로드한 미디어 파일에 오디오 트랙이 정상 포함되어 있는지 확인해주세요.\n• 네트워크 상태 및 API Quota를 점검해 주세요.")

        # 개발 환경 디버깅
        if os.getenv("APP_DEBUG", "false").lower() == "true":
            st.exception(error)

    finally:
        # 파일 정리
        for path in [raw_input_path, processed_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
