import html
import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List

from google import genai
from google.genai import types
from groq import Groq
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

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

# 고급 프로페셔널 라이트 테마 스타일링 (WCAG AA 준수, 모던 스튜디오 UI)
st.markdown(
    """
    <style>
    /* 메인 배경 및 기본 폰트 설정 */
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
    }
    
    /* 헤더 카드 스타일링 */
    .hero-container {
        background: linear-gradient(135deg, #FFFFFF 0%, #EFF6FF 100%);
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.02em;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .hero-subtitle {
        font-size: 1.05rem;
        color: #475569;
        line-height: 1.6;
        margin-bottom: 0;
    }
    
    /* 하이라이트 카드 스타일링 */
    .highlight-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03);
        transition: all 0.2s ease-in-out;
    }
    .highlight-card:hover {
        border-color: #2563EB;
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
    }
    .badge {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: #FFFFFF;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        display: inline-block;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
    }
    .time-info {
        background-color: #F1F5F9;
        border-left: 4px solid #2563EB;
        padding: 12px 16px;
        font-family: 'JetBrains Mono', 'Courier New', monospace;
        font-size: 0.92rem;
        color: #0F172A;
        margin: 14px 0;
        border-radius: 0 8px 8px 0;
    }
    
    /* 통계 메트릭 박스 */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #2563EB;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        margin-top: 4px;
    }

    /* 포커스 및 접근성 요소 */
    .focusable-heading {
        margin-top: 1rem;
        margin-bottom: 1rem;
        padding: 6px 10px;
        border-radius: 8px;
        color: #0F172A;
        font-size: 1.5rem;
        font-weight: 700;
    }
    .focusable-heading:focus, .focusable-heading:focus-visible {
        outline: 3px solid #2563EB !important;
        outline-offset: 3px !important;
    }

    /* 알림 박스 */
    .a11y-alert {
        border-radius: 10px;
        padding: 16px 18px;
        margin-bottom: 16px;
        font-size: 0.95rem;
        line-height: 1.5;
        border: 1px solid transparent;
    }
    .a11y-alert-info {
        background-color: #EFF6FF;
        border-color: #BFDBFE;
        color: #1E40AF;
    }
    .a11y-alert-success {
        background-color: #F0FDF4;
        border-color: #BBF7D0;
        color: #166534;
    }
    .a11y-alert-error {
        background-color: #FEF2F2;
        border-color: #FECACA;
        color: #991B1B;
    }
    .step-text {
        color: #0F172A;
        font-size: 0.95rem;
        margin: 6px 0;
        font-weight: 500;
    }
    .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. 접근성 유틸리티
# ==============================================================================
def set_page_language(lang_code: str = "ko") -> None:
    """페이지 전체 언어를 명시적으로 지정하여 스크린리더가 올바른 발음 규칙을
    사용하도록 강제한다."""
    components.html(
        f"""
        <script>
        try {{
            window.parent.document.documentElement.lang = "{lang_code}";
        }} catch (e) {{}}
        </script>
        """,
        height=0,
        width=0,
    )


def focus_element_by_id(element_id: str) -> None:
    """지정한 id의 요소로 키보드 포커스를 이동시킨다."""
    components.html(
        f"""
        <script>
        function tryFocus(retries) {{
            try {{
                const el = window.parent.document.getElementById("{element_id}");
                if (el) {{
                    el.focus();
                }} else if (retries > 0) {{
                    setTimeout(() => tryFocus(retries - 1), 150);
                }}
            }} catch (e) {{}}
        }}
        tryFocus(10);
        </script>
        """,
        height=0,
        width=0,
    )


def accessible_alert(message: str, kind: str = "info", icon: str = "") -> None:
    """접근성 준수 알림 박스 (aria-live 명시)"""
    css_class = {
        "info": "a11y-alert-info",
        "success": "a11y-alert-success",
        "error": "a11y-alert-error",
    }.get(kind, "a11y-alert-info")

    if kind == "error":
        role = "alert"
        aria_live = "assertive"
    else:
        role = "status"
        aria_live = "polite"

    icon_html = f'<span aria-hidden="true">{icon} </span>' if icon else ""

    st.markdown(
        f'<div class="a11y-alert {css_class}" role="{role}" aria-live="{aria_live}">{icon_html}{message}</div>',
        unsafe_allow_html=True,
    )


def accessible_step(message: str, icon: str = "") -> None:
    """st.status 내부 단계별 안내 문구"""
    icon_html = f'<span aria-hidden="true">{icon} </span>' if icon else ""
    st.markdown(
        f'<p class="step-text" role="status" aria-live="polite">{icon_html}{message}</p>',
        unsafe_allow_html=True,
    )


# ==============================================================================
# 3. 헤더 UI (시맨틱 <header> 랜드마크 적용)
# ==============================================================================
set_page_language("ko")
st.markdown(
    '<header class="hero-container" role="banner">'
    '<h1 class="hero-title"><span aria-hidden="true">🎬</span> 뉴스 숏폼 하이라이트 자동 추출기</h1>'
    '<p class="hero-subtitle">'
    '뉴스 음성/영상 파일을 업로드하면 <strong>Groq Whisper AI</strong>가 자막과 타임코드를 추출하고, '
    '<strong>Gemini AI</strong>가 30~60초 숏폼 구간 및 핵심 타이틀을 자동으로 선정합니다.'
    '</p>'
    '</header>',
    unsafe_allow_html=True,
)
accessible_alert(
    "추출 결과는 EDIUS 등 주요 넷라인 NLE에서 즉시 타임라인 복원이 가능한 CMX3600 EDL 포맷으로 제공됩니다.",
    kind="info",
    icon="💡",
)

# ==============================================================================
# 4. 유틸리티 함수
# ==============================================================================
def prepare_audio_for_groq(input_file_path: str) -> str:
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()

    cmd = [
        "ffmpeg", "-y", "-i", input_file_path,
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
        "-f", "mp3", output_path,
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        error_message = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"오디오 변환(ffmpeg) 실패:\n{error_message}")


def seconds_to_df_timecode(seconds: float) -> str:
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
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def get_media_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def generate_edl(highlights: list, reel_name: str = "AX0101") -> str:
    edl_lines = ["TITLE: NEWS_SHORTFORM_HIGHLIGHTS", "FMT: NTSC DF", ""]
    for idx, item in enumerate(highlights, 1):
        start_time = float(item.get("start_time", 0.0))
        end_time = float(item.get("end_time", 0.0))
        src_in = seconds_to_df_timecode(start_time)
        src_out = seconds_to_df_timecode(end_time)
        main_title = str(item.get("main_title", "Highlight"))
        sub_title = str(item.get("sub_title", ""))

        edl_lines.append(f"{idx:03d}  {reel_name:<8} AA/V  C        {src_in} {src_out} {src_in} {src_out}")
        edl_lines.append(f"* FROM CLIP: {main_title}")
        edl_lines.append(f"* COMMENTS: {sub_title}")
        edl_lines.append("")
    return "\n".join(edl_lines)


# ==============================================================================
# 5. Whisper STT
# ==============================================================================
def extract_segment_data(segment: Any) -> Dict[str, Any]:
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
    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="ko",
        )
    raw_segments = getattr(transcription, "segments", []) or []
    return [extract_segment_data(seg) for seg in raw_segments]


# ==============================================================================
# 6. 데이터 보정
# ==============================================================================
def sanitize_and_fix_highlights(raw_highlights: list, media_duration: float = 0.0) -> list:
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
            if duration < 30.0:
                candidate_end = start_time + 30.0
                if media_duration > 0 and candidate_end > media_duration:
                    start_time = max(0.0, media_duration - 30.0)
                    end_time = media_duration
                else:
                    end_time = candidate_end

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
def run_gemini_highlight_extraction(gemini_api_key: str, segments: list, media_duration: float = 0.0) -> list:
    client = genai.Client(api_key=gemini_api_key)
    preferred_models = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.5-flash"]

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
                    "main_title": {"type": "STRING", "description": "메인 타이틀 (15자 이내)"},
                    "sub_title": {"type": "STRING", "description": "핵심 요약 (25자 이내)"},
                    "start_time": {"type": "NUMBER", "description": "시작 시간(초)"},
                    "end_time": {"type": "NUMBER", "description": "종료 시간(초)"},
                    "reason": {"type": "STRING", "description": "선정 이유"},
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "reason"],
            },
        },
        temperature=0.1,
    )

    last_exception = None
    for model_name in preferred_models:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=gen_config)
            raw_data = json.loads(response.text)
            sanitized_data = sanitize_and_fix_highlights(raw_data, media_duration)
            if len(sanitized_data) == 3:
                return sanitized_data
            else:
                last_exception = RuntimeError(f"모델 {model_name}이 유효한 3개 구간을 반환하지 않았습니다.")
        except Exception as error:
            last_exception = error
            continue

    raise RuntimeError("하이라이트 추출에 실패했습니다. 잠시 후 다시 시도해주세요.") from last_exception


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
        accessible_alert("API 키가 설정되지 않았습니다.", kind="error", icon="⚠️")
        accessible_alert(
            "환경 변수 또는 Streamlit Secrets에 GROQ_API_KEY와 GEMINI_API_KEY를 설정해 주세요.",
            kind="info",
        )
        st.stop()

    groq_client = Groq(api_key=groq_api_key)

    # 섹션 1: 파일 업로드
    st.markdown('<h2 class="focusable-heading">1. 뉴스 미디어 파일 업로드</h2>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 선택하세요.",
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"],
        help="MP3, MP4, TS, MOV 등 다양한 방송 미디어 포맷을 지원합니다.",
    )

    if uploaded_file is None:
        accessible_alert(
            "파일을 업로드하시면 하이라이트 분석 및 EDL 생성을 시작할 수 있습니다.",
            kind="info",
            icon="📌",
        )
        return

    safe_filename = html.escape(uploaded_file.name)
    file_size_mb = uploaded_file.size / (1024 * 1024)
    
    accessible_alert(
        f"파일 선택 완료: <strong>{safe_filename}</strong> ({file_size_mb:.2f} MB)",
        kind="success",
        icon="📁",
    )

    if uploaded_file.size > (1024 * 1024 * 1024):
        accessible_alert("파일 크기가 1GB를 초과합니다. 1GB 이하의 파일을 업로드해 주세요.", kind="error")
        return

    # 섹션 2: 분석 실행
    st.markdown('<h2 class="focusable-heading">2. 하이라이트 분석 및 EDL 생성</h2>', unsafe_allow_html=True)
    start_button = st.button("🚀 하이라이트 추출 및 EDL 생성 시작", type="primary", use_container_width=True)

    if not start_button:
        return

    raw_input_path = None
    processed_audio_path = None

    try:
        with st.status("🎬 뉴스 미디어를 분석하는 중입니다...", expanded=True) as status:
            accessible_step("임시 파일 저장 및 오디오 변환(16kHz Mono) 중...", icon="1️⃣")
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

            accessible_step("Groq Whisper AI를 활용한 자막 및 타임코드 추출 중...", icon="2️⃣")
            segments = run_whisper_stt(groq_client, processed_audio_path)

            if not segments:
                raise RuntimeError("음성에서 자막을 추출하지 못했습니다. 오디오 트랙을 확인해주세요.")

            accessible_step(f"자막 구간 {len(segments)}개 추출 완료", icon="✓")

            accessible_step("Gemini AI 기반 숏폼(30~60초) 하이라이트 구간 탐색 중...", icon="3️⃣")
            highlights = run_gemini_highlight_extraction(gemini_api_key, segments, media_duration)

            accessible_step("EDIUS 연동 EDL (CMX 3600) 파일 생성 중...", icon="4️⃣")
            edl_content = generate_edl(highlights)

            status.update(label="✅ 분석 및 EDL 파일 생성이 완료되었습니다!", state="complete", expanded=False)

        st.markdown(
            '<div class="sr-only" role="status" aria-live="polite">'
            '분석이 완료되었습니다. 추천 숏폼 하이라이트 3건이 아래에 표시됩니다.'
            '</div>',
            unsafe_allow_html=True,
        )

        # 요약 메트릭 카드 대시보드
        st.markdown("<br>", unsafe_allow_html=True)
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{seconds_to_min_sec(media_duration)}</div><div class="metric-label">전체 영상 길이</div></div>',
                unsafe_allow_html=True,
            )
        with col_m2:
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{len(highlights)}개</div><div class="metric-label">추출 숏폼 구간</div></div>',
                unsafe_allow_html=True,
            )
        with col_m3:
            st.markdown(
                '<div class="metric-card"><div class="metric-value">29.97 DF</div><div class="metric-label">타임코드 규격</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<h2 id="results-heading" class="focusable-heading" tabindex="-1">3. 추천 숏폼 하이라이트 (3선)</h2>',
            unsafe_allow_html=True,
        )
        focus_element_by_id("results-heading")

        for index, highlight in enumerate(highlights, 1):
            start_sec = float(highlight.get("start_time", 0.0))
            end_sec = float(highlight.get("end_time", 0.0))
            duration = round(end_sec - start_sec, 1)

            title = html.escape(str(highlight.get("main_title", f"하이라이트 {index}")))
            subtitle = html.escape(str(highlight.get("sub_title", "-")))
            reason = html.escape(str(highlight.get("reason", "-")))

            region_aria_label = html.escape(f"{title} 타임코드 및 재생시간 정보")

            st.markdown(
                f"""
                <article class="highlight-card" aria-labelledby="card-title-{index}">
                    <span class="badge">SHORTFORM CLIP #{index}</span>
                    <h3 id="card-title-{index}" style="margin: 0 0 8px 0; color: #0F172A; font-size: 1.35rem; font-weight: 700;">{title}</h3>
                    <p style="margin: 0 0 12px 0; color: #2563EB; font-weight: 600; font-size: 1.05rem;">{subtitle}</p>
                    <div class="time-info" role="region" aria-label="{region_aria_label}">
                        <span aria-hidden="true">⏱️ </span><strong>DF 타임코드:</strong> {seconds_to_df_timecode(start_sec)} ~ {seconds_to_df_timecode(end_sec)}<br>
                        <span aria-hidden="true">⏳ </span><strong>구간 위치:</strong> {seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)} ({duration}초)
                    </div>
                    <p style="margin: 10px 0 0 0; font-size: 0.95rem; color: #334155; line-height: 1.6;">
                        <strong><span aria-hidden="true">💡 </span>추천 사유:</strong> {reason}
                    </p>
                </article>
                """,
                unsafe_allow_html=True,
            )

        st.markdown('<h2 class="focusable-heading">4. EDIUS 연동 파일 다운로드</h2>', unsafe_allow_html=True)

        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"

        st.download_button(
            label="💾 EDIUS용 EDL 파일 다운로드 (.edl)",
            data=edl_content,
            file_name=edl_filename,
            mime="text/plain",
            use_container_width=True,
        )

    except Exception as error:
        accessible_alert("처리 중 오류가 발생했습니다.", kind="error", icon="❌")
        st.markdown(
            '<ul style="color:#334155; font-size:0.95rem;">'
            '<li>오디오 트랙이 정상 포함된 미디어 파일인지 확인해 보세요.</li>'
            '<li>지속적인 실패 발생 시 관리자에게 문의바랍니다.</li>'
            '</ul>',
            unsafe_allow_html=True,
        )

        if os.getenv("APP_DEBUG", "false").lower() == "true":
            st.exception(error)

    finally:
        for path in [raw_input_path, processed_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
