import os
import json
import subprocess
import tempfile
from typing import Any, List, Dict

import streamlit as st
import streamlit.components.v1 as components
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

# 방송 편집실(broadcast control-room) 컨셉 디자인 토큰
# - 타임코드/릴/EDL 등 이 도구가 실제로 다루는 소재에서 시각 언어를 그대로 가져옴
# - 색상은 모두 "명시적으로 밝은 배경을 가진 컨테이너 안"에서만 사용되어
#   .streamlit/config.toml의 라이트 테마 고정과 무관하게 대비가 항상 보장됨
st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
    <style>
    :root {
        --ink: #12151C;
        --ink-muted: #4B5563;
        --bg-page: #F4F5F7;
        --surface: #FFFFFF;
        --border: #E2E4EA;
        --accent: #BE123C;      /* 온에어 레드 - 실측 대비(백색 텍스트) 약 5.9:1 */
        --accent-soft: #FDE8ED;
        --signal: #0F766E;      /* 시그널 틸 - 보조 강조 */
        --tc-bg: #14151A;       /* 타임코드 LED 패널 배경 */
        --tc-fg: #FBBF24;       /* 타임코드 앰버 디지트 - 배경 대비 약 11.9:1 */
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    /* ---------- 상단 온에어 바 ---------- */
    .onair-bar {
        background-color: var(--ink);
        border-radius: 14px;
        padding: 22px 28px;
        margin-bottom: 1.4rem;
        position: relative;
        overflow: hidden;
        border-top: 4px solid var(--accent);
    }
    .onair-tally {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: rgba(190, 18, 60, 0.18);
        border: 1px solid rgba(190, 18, 60, 0.5);
        color: #FCA5B7;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        padding: 3px 10px;
        border-radius: 999px;
        margin-bottom: 12px;
    }
    .onair-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background-color: #FB7185;
        display: inline-block;
    }
    @media (prefers-reduced-motion: no-preference) {
        .onair-dot { animation: onair-pulse 1.8s ease-in-out infinite; }
    }
    @keyframes onair-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.35; }
    }
    .main-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        color: #FFFFFF; /* var(--ink) 배경 대비 약 17.6:1 */
        margin-bottom: 0.5rem;
        letter-spacing: -0.01em;
    }
    .sub-title {
        font-size: 1rem;
        color: #C7CBD6; /* var(--ink) 배경 대비 약 8.9:1 */
        margin-bottom: 0;
        line-height: 1.65;
        max-width: 62ch;
    }

    /* ---------- 섹션 헤더 (REEL 아이번로우) ---------- */
    .section-header {
        display: flex;
        align-items: baseline;
        gap: 12px;
        margin: 0.4rem 0 1rem 0;
        border-bottom: 1px solid var(--border);
        padding-bottom: 10px;
    }
    .section-eyebrow {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        color: var(--accent);
        background-color: var(--accent-soft);
        padding: 2px 8px;
        border-radius: 4px;
        white-space: nowrap;
    }
    .section-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--ink);
        margin: 0;
    }

    /* ---------- 하이라이트 카드 (클립 슬레이트) ---------- */
    .highlight-card {
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-left: 4px solid var(--signal);
        border-radius: 10px;
        padding: 22px 24px;
        margin-bottom: 18px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
    }
    .badge {
        background-color: var(--signal);
        color: #FFFFFF; /* var(--signal) 배경 대비 약 5.4:1 */
        padding: 3px 10px;
        border-radius: 5px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        display: inline-block;
        margin-bottom: 12px;
    }
    .card-title {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        color: var(--ink);
        font-size: 1.25rem;
        margin: 0 0 6px 0;
    }
    .card-subtitle {
        color: var(--ink-muted);
        font-weight: 500;
        margin: 0 0 14px 0;
    }
    .card-reason {
        color: var(--ink-muted);
        font-size: 0.92rem;
        margin: 12px 0 0 0;
        line-height: 1.55;
    }

    /* ---------- 타임코드 LED 패널 (시그니처 요소) ---------- */
    .tc-panel {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 4px 0 2px 0;
    }
    .tc-chip {
        background-color: var(--tc-bg);
        border-radius: 6px;
        padding: 8px 12px;
        display: flex;
        align-items: baseline;
        gap: 8px;
    }
    .tc-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        color: #8B8F9C;
        text-transform: uppercase;
    }
    .tc-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.98rem;
        font-weight: 600;
        color: var(--tc-fg); /* var(--tc-bg) 배경 대비 약 11.9:1 */
        letter-spacing: 0.02em;
    }
    .tc-duration {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        color: var(--ink-muted);
        align-self: center;
    }

    /* ---------- 접근 가능한 알림(alert) 박스 ---------- */
    .a11y-alert {
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 12px;
        font-size: 0.95rem;
        line-height: 1.5;
        border: 1px solid transparent;
    }
    .a11y-alert-info {
        background-color: #EFF6FF;
        border-color: #BFDBFE;
        color: #1E3A8A;
    }
    .a11y-alert-success {
        background-color: #F0FDF4;
        border-color: #BBF7D0;
        color: #14532D;
    }
    .a11y-alert-error {
        background-color: #FEF2F2;
        border-color: #FECACA;
        color: #7F1D1D;
    }
    .step-text {
        color: var(--ink);
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.88rem;
        margin: 4px 0;
    }

    /* ---------- Streamlit 네이티브 위젯 재스타일 ---------- */
    div[data-testid="stAppViewContainer"] {
        background-color: var(--bg-page);
    }
    button[kind="primary"], [data-testid="stBaseButton-primary"] {
        background-color: var(--accent) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
        background-color: #9F1239 !important;
    }
    [data-testid="stDownloadButton"] button {
        border-radius: 8px !important;
        border: 1.5px solid var(--signal) !important;
        color: var(--signal) !important;
        font-weight: 600 !important;
        background-color: transparent !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        background-color: #F0FDFA !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        border-radius: 10px !important;
        border: 1.5px dashed var(--border) !important;
    }
    [data-testid="stExpander"], [data-testid="stStatusWidget"] {
        border-radius: 10px !important;
        border-color: var(--border) !important;
    }

    /* 스크린 리더 전용 숨김 클래스 */
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
# 2. 접근성 유틸리티 (언어 설정 / 포커스 이동 / 접근 가능한 알림)
# ==============================================================================

def set_page_language(lang_code: str = "ko") -> None:
    """페이지 전체 언어를 명시적으로 지정하여 스크린리더가 올바른 발음 규칙을
    사용하도록 강제한다. Streamlit이 기본 lang 속성을 안정적으로 노출하지
    않으므로, 부모 문서(document)의 <html lang> 속성을 직접 설정한다."""
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
    """비동기로 렌더링되는 Streamlit 콘텐츠에 대해, 지정한 id의 요소로
    키보드 포커스를 이동시킨다. 결과가 새로 나타났음을 스크린리더/키보드
    사용자에게 알리기 위해 처리 완료 직후 호출한다."""
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
    """st.success / st.info / st.error 를 대체하는 접근성 준수 알림 박스.
    이모지에는 항상 aria-hidden 처리를 일관되게 적용한다."""
    css_class = {
        "info": "a11y-alert-info",
        "success": "a11y-alert-success",
        "error": "a11y-alert-error",
    }.get(kind, "a11y-alert-info")

    role = "alert" if kind == "error" else "status"
    icon_html = f'<span aria-hidden="true">{icon} </span>' if icon else ""

    st.markdown(
        f'<div class="a11y-alert {css_class}" role="{role}">{icon_html}{message}</div>',
        unsafe_allow_html=True,
    )


def accessible_step(message: str, icon: str = "") -> None:
    """st.status 내부의 단계별 안내 문구를 위한 접근성 준수 텍스트.
    이모지에는 aria-hidden을, 문구 갱신은 스크린리더가 인지할 수 있도록
    role=status 컨테이너로 감싼다."""
    icon_html = f'<span aria-hidden="true">{icon} </span>' if icon else ""
    st.markdown(
        f'<p class="step-text" role="status">{icon_html}{message}</p>',
        unsafe_allow_html=True,
    )


def section_header(reel_number: str, title: str) -> None:
    """실제 순차 워크플로우(업로드→분석→결과→다운로드)를 나타내는 섹션 헤딩.
    'REEL' 표기는 이 도구가 다루는 EDL/릴 용어와 일관성을 맞춘 것으로,
    장식이 아니라 진행 순서라는 정보를 담는다. 시맨틱 h2는 그대로 유지."""
    st.markdown(
        f'<div class="section-header">'
        f'<span class="section-eyebrow" aria-hidden="true">REEL {reel_number}</span>'
        f'<h2 class="section-title">{title}</h2>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ==============================================================================
# 3. 헤더 UI (접근성 태그 및 대체텍스트 적용)
# ==============================================================================

set_page_language("ko")

st.markdown(
    '<div class="onair-bar">'
    '<div class="onair-tally"><span class="onair-dot" aria-hidden="true"></span>ON AIR · AUTO EDIT</div>'
    '<h1 class="main-title"><span aria-hidden="true">🎬 </span>뉴스 숏폼 하이라이트 자동 추출기</h1>'
    '<p class="sub-title">'
    '뉴스 음성/영상 파일을 업로드하면 Groq Whisper로 자막과 타임코드를 추출하고, '
    'Gemini AI가 30~60초 숏폼 구간 및 자막 타이틀을 자동으로 선정합니다.'
    '</p>'
    '</div>',
    unsafe_allow_html=True,
)

accessible_alert(
    "처리 결과는 EDIUS 영상 편집 프로그램에서 즉시 사용할 수 있는 EDL 파일로 제공됩니다.",
    kind="info",
    icon="💡",
)
st.divider()


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
# 9. 메인 애플리케이션 (접근성 보완 구조)
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

    section_header("01", "뉴스 파일 업로드")
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

    file_size_mb = uploaded_file.size / (1024 * 1024)
    accessible_alert(
        f"파일 선택 완료: <strong>{uploaded_file.name}</strong> ({file_size_mb:.2f} MB)",
        kind="success",
        icon="📁",
    )

    if uploaded_file.size > (1024 * 1024 * 1024):
        accessible_alert("파일 크기가 1GB를 초과합니다. 1GB 이하의 파일을 업로드해 주세요.", kind="error")
        return

    section_header("02", "하이라이트 분석")
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

        # 스크린리더 사용자에게 결과 생성 완료를 알리는 시각적으로 숨겨진 알림.
        # role="status" + aria-live="polite" 조합으로 화면 변화를 능동적으로 공지한다.
        st.markdown(
            '<div class="sr-only" role="status" aria-live="polite">'
            '분석이 완료되었습니다. 추천 숏폼 하이라이트 3건이 아래에 표시됩니다.'
            '</div>',
            unsafe_allow_html=True,
        )

        # 결과 헤딩 - tabindex="-1"을 부여해 스크립트로 포커스를 이동시킬 수 있도록 함
        st.markdown(
            '<div class="section-header">'
            '<span class="section-eyebrow" aria-hidden="true">REEL 03</span>'
            '<h2 class="section-title" id="results-heading" tabindex="-1" style="outline:none;">'
            '추천 숏폼 하이라이트 (3선)</h2>'
            '</div>',
            unsafe_allow_html=True,
        )
        # 결과가 방금 나타났음을 키보드/스크린리더 사용자에게 알리기 위해 포커스 이동
        focus_element_by_id("results-heading")

        for index, highlight in enumerate(highlights, 1):
            start_sec = float(highlight.get("start_time", 0.0))
            end_sec = float(highlight.get("end_time", 0.0))
            duration = round(end_sec - start_sec, 1)

            title = str(highlight.get("main_title", f"하이라이트 {index}"))
            subtitle = str(highlight.get("sub_title", "-"))
            reason = str(highlight.get("reason", "-"))

            # 접근성이 준수된 커스텀 카드 HTML - 타임코드는 실제 방송 화면의
            # LED 번인(burn-in) 오버레이를 본뜬 시그니처 요소로 표현
            st.markdown(
                f"""
                <article class="highlight-card" aria-labelledby="card-title-{index}">
                    <span class="badge">CLIP {index:02d} / 03</span>
                    <h3 id="card-title-{index}" class="card-title">{title}</h3>
                    <p class="card-subtitle">{subtitle}</p>
                    <div class="tc-panel" role="region" aria-label="시간 정보">
                        <div class="tc-chip">
                            <span class="tc-label" aria-hidden="true">TC IN/OUT</span>
                            <span class="tc-value">{seconds_to_df_timecode(start_sec)} — {seconds_to_df_timecode(end_sec)}</span>
                        </div>
                        <span class="tc-duration">{seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)} · {duration}초</span>
                    </div>
                    <p class="card-reason">
                        <strong><span aria-hidden="true">💡 </span>선정 이유:</strong> {reason}
                    </p>
                </article>
                """,
                unsafe_allow_html=True,
            )

        st.divider()
        section_header("04", "EDIUS 연동 파일 다운로드")

        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"

        st.download_button(
            label="💾 EDIUS용 EDL 파일 다운로드",
            data=edl_content,
            file_name=edl_filename,
            mime="text/plain",
            use_container_width=True,
        )

    except Exception as error:
        accessible_alert("처리 중 오류가 발생했습니다.", kind="error", icon="❌")
        st.markdown(
            '<ul style="color:#4B5563; font-size:0.95rem;">'
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
