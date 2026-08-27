import os
import json
import subprocess
import tempfile
from html import escape
from typing import Any, List, Dict

import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types


# ==============================================================================
# 1. 환경 및 페이지 설정
# ==============================================================================

load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==============================================================================
# 2. WCAG 2.2 AA 고려 커스텀 CSS
# ==============================================================================

st.markdown(
    """
    <style>
    /* 기본 접근성 */
    html {
        font-size: 16px;
    }

    body {
        line-height: 1.5;
    }

    button:focus-visible,
    input:focus-visible,
    textarea:focus-visible,
    select:focus-visible,
    a:focus-visible,
    [role="button"]:focus-visible {
        outline: 3px solid #0F62FE !important;
        outline-offset: 3px !important;
        box-shadow: 0 0 0 2px #FFFFFF !important;
    }

    /* 페이지 헤더 */
    .main-title {
        font-size: clamp(1.75rem, 4vw, 2.4rem);
        line-height: 1.2;
        font-weight: 700;
        color: #0F172A;
        margin: 0 0 0.75rem 0;
        overflow-wrap: anywhere;
    }

    .sub-title {
        font-size: 1.05rem;
        line-height: 1.65;
        color: #334155;
        margin: 0 0 1.5rem 0;
        max-width: 900px;
        overflow-wrap: anywhere;
    }

    /* 하이라이트 카드 */
    .highlight-card {
        background-color: #FFFFFF;
        border: 2px solid #CBD5E1;
        border-radius: 12px;
        padding: 20px;
        margin: 0 0 20px 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        overflow-wrap: anywhere;
        word-break: keep-all;
    }

    .highlight-card h3 {
        margin: 0 0 10px 0;
        color: #0F172A;
        font-size: clamp(1.15rem, 2vw, 1.35rem);
        line-height: 1.4;
        overflow-wrap: anywhere;
        word-break: keep-all;
    }

    .highlight-card p {
        line-height: 1.6;
        overflow-wrap: anywhere;
        word-break: keep-all;
    }

    /* SHORTFORM 배지 */
    .badge {
        background-color: #1D4ED8;
        color: #FFFFFF;
        padding: 5px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        line-height: 1.3;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 12px;
    }

    /* 타임코드 정보 */
    .time-info {
        background-color: #F8FAFC;
        border-left: 5px solid #1D4ED8;
        padding: 12px 14px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco,
                     Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 0.95rem;
        line-height: 1.7;
        color: #0F172A;
        margin: 14px 0;
        border-radius: 0 6px 6px 0;
        overflow-wrap: anywhere;
    }

    .section-description {
        color: #334155;
        font-size: 0.95rem;
        line-height: 1.6;
        margin: -0.5rem 0 1rem 0;
    }

    @media (max-width: 768px) {
        .main-title { font-size: 1.8rem; }
        .sub-title { font-size: 1rem; }
        .highlight-card { padding: 16px; border-radius: 10px; }
        .time-info { font-size: 0.88rem; padding: 10px 12px; }
        .badge { font-size: 0.8rem; }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            scroll-behavior: auto !important;
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 3. 헤더 UI
# ==============================================================================

st.markdown(
    """
    <h1 class="main-title">
        <span aria-hidden="true">🎬 </span>
        뉴스 숏폼 하이라이트 자동 추출기
    </h1>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class="sub-title">
        뉴스 음성/영상 파일을 업로드하면 Groq Whisper로 자막과 타임코드를 추출하고,
        Gemini AI가 30~60초 숏폼 구간 및 자막 타이틀을 자동으로 선정합니다.
    </p>
    """,
    unsafe_allow_html=True,
)

st.info(
    "💡 처리 결과는 EDIUS 영상 편집 프로그램에서 즉시 사용할 수 있는 "
    "EDL 파일로 제공됩니다."
)

st.divider()


# ==============================================================================
# 4. 유틸리티 함수
# ==============================================================================

def prepare_audio_for_groq(input_file_path: str) -> str:
    """
    대용량 영상/음성 파일을 Groq API 용량 제한(25MB)에 맞추어
    16kHz / mono / 32kbps MP3로 최적화 변환한다.
    """
    output_temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3",
    )
    output_path = output_temp_file.name
    output_temp_file.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_file_path,
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "32k",
        "-f",
        "mp3",
        output_path,
    ]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return output_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        error_message = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"오디오 변환(ffmpeg) 실패:\n{error_message}")


def seconds_to_df_timecode(seconds: float) -> str:
    """
    초 단위 시간을 NTSC Drop Frame Timecode
    (29.97fps / HH:MM:SS;FF) 형식으로 변환한다.
    """
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
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def get_media_duration(file_path: str) -> float:
    """FFprobe를 이용하여 미디어의 전체 재생 시간(초)을 구한다."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
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
        start_time = float(item.get("start_time", 0.0))
        end_time = float(item.get("end_time", 0.0))

        src_in = seconds_to_df_timecode(start_time)
        src_out = seconds_to_df_timecode(end_time)

        main_title = str(item.get("main_title", "Highlight"))
        sub_title = str(item.get("sub_title", ""))

        edl_lines.append(
            f"{idx:03d}  {reel_name:<8} AA/V  C        "
            f"{src_in} {src_out} {src_in} {src_out}"
        )
        edl_lines.append(f"* FROM CLIP: {main_title}")
        edl_lines.append(f"* COMMENTS: {sub_title}")
        edl_lines.append("")

    return "\n".join(edl_lines)


# ==============================================================================
# 5. Whisper STT
# ==============================================================================

def extract_segment_data(segment: Any) -> Dict[str, Any]:
    """Groq Whisper API 반환 객체/Dict 단위 파싱"""
    if isinstance(segment, dict):
        return {
            "start": segment.get("start", 0.0),
            "end": segment.get("end", 0.0),
            "text": segment.get("text", ""),
        }

    return {
        "start": getattr(segment, "start", 0.0),
        "end": getattr(segment, "end", 0.0),
        "text": getattr(segment, "text", ""),
    }


def run_whisper_stt(client: Groq, audio_path: str) -> List[Dict[str, Any]]:
    """Groq Whisper API를 호출하여 타임코드가 포함된 자막 세그먼트를 추출한다."""
    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="ko",
        )

    raw_segments = getattr(transcription, "segments", []) or []
    return [extract_segment_data(seg) for seg in raw_segments]


# ==============================================================================
# 6. 하이라이트 데이터 Python 단 검증 및 보정
# ==============================================================================

def sanitize_and_fix_highlights(raw_highlights: list, media_duration: float = 0.0) -> list:
    """Gemini가 생성한 구간 데이터의 타임코드 무결성 및 30~60초 조건을 엄격히 검증한다."""
    fixed_list = []

    if not isinstance(raw_highlights, list):
        return fixed_list

    for item in raw_highlights:
        if not isinstance(item, dict):
            continue

        try:
            start_time = max(0.0, float(item.get("start_time", 0.0)))
            end_time = max(0.0, float(item.get("end_time", 0.0)))

            if start_time > end_time:
                start_time, end_time = end_time, start_time

            if media_duration > 0:
                start_time = min(start_time, media_duration)
                end_time = min(end_time, media_duration)

            duration = end_time - start_time

            # 30초 미만 보정
            if duration < 30.0:
                candidate_end = start_time + 30.0
                if media_duration > 0 and candidate_end > media_duration:
                    start_time = max(0.0, media_duration - 30.0)
                    end_time = media_duration
                else:
                    end_time = candidate_end

            # 60초 초과 보정
            duration = end_time - start_time
            if duration > 60.0:
                end_time = start_time + 60.0

            duration = end_time - start_time
            if start_time >= end_time or not (29.0 <= duration <= 61.0):
                continue

            item["start_time"] = round(start_time, 2)
            item["end_time"] = round(end_time, 2)
            fixed_list.append(item)

        except (TypeError, ValueError):
            continue

    return fixed_list


# ==============================================================================
# 7. Gemini 하이라이트 추출
# ==============================================================================

def run_gemini_highlight_extraction(
    gemini_api_key: str,
    segments: list,
    media_duration: float = 0.0,
) -> list:
    client = genai.Client(api_key=gemini_api_key)

    preferred_models = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    ]

    formatted_transcript = []
    for segment in segments:
        seg_data = extract_segment_data(segment)
        start = round(float(seg_data["start"]), 2)
        end = round(float(seg_data["end"]), 2)
        text = str(seg_data["text"]).strip()

        if text:
            formatted_transcript.append(f"[{start:.2f}s ~ {end:.2f}s] {text}")

    transcript_text = "\n".join(formatted_transcript)

    prompt = f"""
너는 뉴스 방송 수석 에디터이자 YouTube Shorts/TikTok 전문 숏폼 에디터이다.
아래 뉴스 자막 데이터의 타임코드를 분석하여 숏폼으로 제작하기 가장 좋은 핵심 구간 3곳을 선정하라.

[필수 규칙]
1. 정확히 3개의 하이라이트를 반환한다.
2. 각 구간의 길이는 반드시 30초 이상 60초 이하여야 한다.
3. start_time은 선택한 첫 번째 자막의 시작 시간, end_time은 마지막 자막의 종료 시간이어야 한다.
4. 문장이 중간에 잘리지 않는 완전한 뉴스 맥락을 선택하라.
5. 영상 전체 길이는 약 {media_duration:.2f}초이다.

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
                    "main_title": {
                        "type": "STRING",
                        "description": "메인 타이틀 (15자 이내)",
                    },
                    "sub_title": {
                        "type": "STRING",
                        "description": "핵심 요약 (25자 이내)",
                    },
                    "start_time": {
                        "type": "NUMBER",
                        "description": "시작 시간(초)",
                    },
                    "end_time": {
                        "type": "NUMBER",
                        "description": "종료 시간(초)",
                    },
                    "reason": {
                        "type": "STRING",
                        "description": "선정 이유",
                    },
                },
                "required": [
                    "main_title",
                    "sub_title",
                    "start_time",
                    "end_time",
                    "reason",
                ],
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
            sanitized_data = sanitize_and_fix_highlights(
                raw_data,
                media_duration,
            )

            if len(sanitized_data) == 3:
                return sanitized_data

            last_exception = RuntimeError(
                f"모델 {model_name}이 유효한 3개 구간을 반환하지 않았습니다."
            )

        except Exception as error:
            last_exception = error
            continue

    raise RuntimeError(
        "하이라이트 추출에 실패했습니다. 잠시 후 다시 시도해주세요."
    ) from last_exception


# ==============================================================================
# 8. API 키 가져오기
# ==============================================================================

def get_api_keys():
    groq_api_key = st.secrets.get("GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
    gemini_api_key = st.secrets.get("GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    return groq_api_key, gemini_api_key


# ==============================================================================
# 9. 메인 애플리케이션
# ==============================================================================

def main():
    groq_api_key, gemini_api_key = get_api_keys()

    if not groq_api_key or not gemini_api_key:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        st.info("환경 변수 또는 Streamlit Secrets에 GROQ_API_KEY와 GEMINI_API_KEY를 설정해 주세요.")
        st.stop()

    groq_client = Groq(api_key=groq_api_key)

    # 1. 파일 업로드
    st.header("1. 뉴스 파일 업로드")
    st.markdown(
        """
        <p class="section-description">
            분석할 뉴스 음성 또는 영상 파일을 선택하세요.
        </p>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 선택하세요.",
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"],
        help="MP3, MP4, TS, MOV, M4A, WAV 형식을 지원합니다. 최대 1GB까지 업로드할 수 있습니다.",
    )

    if uploaded_file is None:
        st.info("📌 파일을 업로드하시면 하이라이트 분석 및 EDL 생성을 시작할 수 있습니다.")
        return

    file_size_mb = uploaded_file.size / (1024 * 1024)
    safe_filename = escape(str(uploaded_file.name))

    st.success(f"📁 파일 선택 완료: **{safe_filename}** ({file_size_mb:.2f} MB)")

    if uploaded_file.size > (1024 * 1024 * 1024):
        st.error("파일 크기가 1GB를 초과합니다. 1GB 이하의 파일을 업로드해 주세요.")
        return

    # 2. 하이라이트 분석
    st.header("2. 하이라이트 분석")
    st.markdown(
        """
        <p class="section-description">
            업로드한 미디어의 음성을 분석하여 숏폼 하이라이트 3개 구간을 자동으로 선정합니다.
        </p>
        """,
        unsafe_allow_html=True,
    )

    start_button = st.button(
        "🚀 하이라이트 추출 및 EDL 생성 시작",
        type="primary",
        use_container_width=True,
    )

    if not start_button:
        return

    raw_input_path = None
    processed_audio_path = None

    try:
        with st.status("🎬 뉴스 미디어를 분석하는 중입니다...", expanded=True) as status:
            # 1단계: 임시 파일 처리
            st.write("1️⃣ 임시 파일 저장 및 오디오 변환(16kHz Mono) 중...")
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

            # 2단계: Whisper STT
            st.write("2️⃣ Groq Whisper AI를 활용한 자막 및 타임코드 추출 중...")
            segments = run_whisper_stt(groq_client, processed_audio_path)

            if not segments:
                raise RuntimeError("음성에서 자막을 추출하지 못했습니다. 오디오 트랙을 확인해주세요.")

            st.write(f"✓ 자막 구간 {len(segments)}개 추출 완료")

            # 3단계: Gemini 추출
            st.write("3️⃣ Gemini AI 기반 숏폼(30~60초) 하이라이트 구간 탐색 중...")
            highlights = run_gemini_highlight_extraction(
                gemini_api_key,
                segments,
                media_duration,
            )

            # 4단계: EDL 생성
            st.write("4️⃣ EDIUS 연동 EDL (CMX 3600) 파일 생성 중...")
            edl_content = generate_edl(highlights)

            status.update(
                label="✅ 분석 및 EDL 파일 생성이 완료되었습니다!",
                state="complete",
                expanded=False,
            )

        # 3. 결과 출력 및 카드 UI
        st.header("3. 추천 숏폼 하이라이트 (3선)")
        st.markdown(
            """
            <p class="section-description">
                Gemini AI가 선정한 30~60초 길이의 숏폼 후보 3개입니다.
            </p>
            """,
            unsafe_allow_html=True,
        )

        for index, highlight in enumerate(highlights, 1):
            start_sec = float(highlight.get("start_time", 0.0))
            end_sec = float(highlight.get("end_time", 0.0))
            duration = round(end_sec - start_sec, 1)

            title = escape(str(highlight.get("main_title", f"하이라이트 {index}")))
            subtitle = escape(str(highlight.get("sub_title", "-")))
            reason = escape(str(highlight.get("reason", "-")))

            start_tc = seconds_to_df_timecode(start_sec)
            end_tc = seconds_to_df_timecode(end_sec)
            start_ms = seconds_to_min_sec(start_sec)
            end_ms = seconds_to_min_sec(end_sec)

            st.markdown(
                f"""
                <article class="highlight-card" aria-labelledby="card-title-{index}">
                    <span class="badge">SHORTFORM #{index}</span>
                    <h3 id="card-title-{index}">{title}</h3>
                    <p style="margin: 0 0 12px 0; color: #334155; font-weight: 600;">{subtitle}</p>
                    <div class="time-info">
                        <span aria-hidden="true">⏱️</span>
                        <strong>타임코드:</strong> {start_tc} ~ {end_tc}<br>
                        <span aria-hidden="true">⏳</span>
                        <strong>재생시간:</strong> {start_ms} ~ {end_ms} ({duration}초)
                    </div>
                    <p style="margin: 8px 0 0 0; font-size: 0.95rem; color: #334155;">
                        <strong>선정 이유:</strong> {reason}
                    </p>
                </article>
                """,
                unsafe_allow_html=True,
            )

        # 4. EDL 다운로드 섹션
        st.divider()
        st.header("4. EDIUS EDL 파일 다운로드")
        st.download_button(
            label="📥 EDL 파일 다운로드 (.edl)",
            data=edl_content,
            file_name="news_highlights.edl",
            mime="text/plain",
            use_container_width=True,
        )

    except Exception as e:
        st.error(f"❌ 처리 중 오류가 발생했습니다: {e}")

    finally:
        # 임시 파일 세척
        if raw_input_path and os.path.exists(raw_input_path):
            os.remove(raw_input_path)
        if processed_audio_path and os.path.exists(processed_audio_path):
            os.remove(processed_audio_path)


if __name__ == "__main__":
    main()
