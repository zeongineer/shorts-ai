import html
import os
import re
import subprocess
import tempfile
import base64
from typing import Any, Dict, List
import json

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq

# ==============================================================================
# 1. 환경 및 페이지 설정
# ==============================================================================
load_dotenv()
st.set_page_config(
    page_title="뉴스 주제별 구간 자동 분할기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BRAND = "#1E3A8A" 
BRAND_DARK = "#1E40AF"
BRAND_TINT = "#EFF6FF"


def _get_secret_or_env(key: str) -> str:
    """GitHub에 커밋되는 .env 대신, 배포 환경(Streamlit Community Cloud)에서는
    st.secrets(Settings > Secrets)를 우선 사용합니다. 로컬 개발 시에만 .env로 폴백합니다."""
    try:
        secret_value = st.secrets.get(key, None)
    except Exception:
        secret_value = None
    return secret_value or os.getenv(key)


def get_gemini_api_key() -> str:
    return _get_secret_or_env("GEMINI_API_KEY")


def get_groq_api_key() -> str:
    return _get_secret_or_env("GROQ_API_KEY")

# ==============================================================================
# 2. 아이콘 (SVG, Lucide 스타일)
# ==============================================================================
_ICON_PATHS = {
    "film": '<rect x="2" y="2" width="20" height="20" rx="2.5"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/>',
    "bulb": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/>',
    "alert-triangle": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "x-circle": '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "circle": '<circle cx="12" cy="12" r="10"/>',
    "dot": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/>',
    "doc": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "mic": '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>',
    "chart": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "timer": '<line x1="10" y1="2" x2="14" y2="2"/><line x1="12" y1="14" x2="15" y2="11"/><circle cx="12" cy="14" r="8"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
}

def icon(name: str, size: int = 16, color: str = "currentColor", stroke_width: float = 2) -> str:
    path = _ICON_PATHS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;flex-shrink:0;">{path}</svg>'
    )

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Noto+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root{{
        --brand:{BRAND};
        --brand-dark:{BRAND_DARK};
        --brand-tint:{BRAND_TINT};
        --bg-base:#F8FAFC;
        --surface:#FFFFFF;
        --border:#E2E8F0;
        --text-primary:#0F172A;
        --text-secondary:#64748B;
        --green:#10B981;
        --gray-light:#F1F5F9;
        --shadow-md: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
    }}

    .stApp {{ background-color: var(--bg-base); }}
    body, .stApp, p, span, div {{ font-family: 'Noto Sans KR', sans-serif; }}

    .block-container {{
        max-width: 1400px !important;
        margin: 0 auto;
        padding-top: 2.5rem !important;
    }}

    div[data-testid="stVerticalBlock"] {{ gap: 0.5rem !important; }}

    .app-header {{ display:flex; align-items:center; gap:16px; margin-bottom: 8px; }}
    .app-title-group {{ display:flex; flex-direction:column; gap:4px; }}
    .app-title {{
        font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:1.75rem;
        margin:0; color:var(--text-primary); letter-spacing:-0.5px; line-height:1.2;
    }}
    .app-sub {{ color:var(--text-secondary); font-size:0.95rem; line-height:1.4; margin:0; }}

    .a11y-alert {{
        display:flex; align-items:center; gap:10px;
        border-radius:10px; padding:12px 16px; margin: 16px 0;
        font-size:0.9rem; line-height:1.5; font-weight: 500;
    }}
    .a11y-alert-info {{ background:var(--brand-tint); color:var(--brand-dark); }}
    .a11y-alert-error {{ background:#FEF2F2; border-color:#FECACA; color:#991B1B; border:1px solid; }}

    [data-testid="stFileUploader"] {{
        background-color: var(--bg-base);
        border: 2px dashed #CBD5E1 !important;
        border-radius: 16px !important;
        padding: 20px !important;
        transition: all 0.2s ease;
    }}
    [data-testid="stFileUploader"]:hover {{ border-color: var(--brand) !important; background-color: var(--brand-tint); }}

    .stepper-container {{
        display: flex; justify-content: space-between; position: relative; 
        margin: 16px 0 24px; padding: 0 20px;
    }}
    .stepper-container::before {{
        content: ""; position: absolute; top: 15px; left: 50px; right: 50px; height: 2px;
        background: var(--border); z-index: 1;
    }}
    .step-node {{
        position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; gap: 8px;
        width: 120px;
    }}
    .step-circle {{
        width: 32px; height: 32px; border-radius: 50%; background: var(--surface); border: 2px solid var(--border);
        display: flex; align-items: center; justify-content: center; font-weight: 700; color: var(--text-secondary);
        font-size: 0.9rem; transition: all 0.3s;
    }}
    .step-label {{ font-size: 0.85rem; font-weight: 600; color: var(--text-secondary); text-align: center; }}
    
    .step-node.done .step-circle {{ background: var(--brand); border-color: var(--brand); color: #FFF; }}
    .step-node.done .step-label {{ color: var(--text-primary); }}
    .step-node.active .step-circle {{ border-color: var(--brand); color: var(--brand); box-shadow: 0 0 0 4px var(--brand-tint); }}
    .step-node.active .step-label {{ color: var(--brand); }}

    /* 패널 및 테이블 스타일 */
    .panel-container {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 20px;
        box-shadow: var(--shadow-md);
        height: 100%;
    }}
    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--border);
    }
    .panel-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
    }
    
    /* 커스텀 테이블 스타일 */
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.88rem;
    }
    .custom-table th {
        background-color: var(--gray-light);
        color: var(--text-secondary);
        font-weight: 600;
        text-align: left;
        padding: 10px 8px;
        border-bottom: 1px solid var(--border);
    }
    .custom-table td {
        padding: 10px 8px;
        border-bottom: 1px solid var(--border);
        color: var(--text-primary);
        vertical-align: middle;
    }
    .custom-table tr:hover {
        background-color: #F8FAFC;
    }
    
    .score-badge {
        font-weight: 700;
        font-family: 'IBM Plex Mono', monospace;
        color: #DC2626;
    }
    .tc-text {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.82rem;
        color: var(--text-secondary);
    }

    /* 우측 패널 키-값 스타일 */
    .kv-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid var(--border);
        font-size: 0.92rem;
    }
    .kv-key { color: var(--text-secondary); }
    .kv-val { font-weight: 600; color: var(--text-primary); font-family: 'IBM Plex Mono', monospace; }

    button[kind="primary"] {{
        background-color: #FF5722 !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 12px !important;
        border: 1px solid #FF5722 !important;
        transition: all 0.2s ease !important;
        min-height: 50px;
        width: 100%;
        margin-top: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }}
    button[kind="primary"]:hover {{
        background-color: #E64A19 !important;
        border-color: #E64A19 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 6px -1px rgba(255, 87, 34, 0.2) !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 3. 공통 유틸리티
# ==============================================================================
def accessible_alert(message: str, kind: str = "info", icon_name: str = "") -> None:
    css_class = {"info": "a11y-alert-info", "error": "a11y-alert-error"}.get(kind, "a11y-alert-info")
    color_map = {"info": BRAND_DARK, "error": "#991B1B"}
    role = "alert" if kind == "error" else "status"
    aria_live = "assertive" if kind == "error" else "polite"
    icon_html = icon(icon_name, size=18, color=color_map.get(kind, BRAND_DARK)) if icon_name else ""

    st.markdown(
        f'<div class="a11y-alert {css_class}" role="{role}" aria-live="{aria_live}">{icon_html}<span>{message}</span></div>',
        unsafe_allow_html=True,
    )

def render_header() -> None:
    components.html('<script>try { window.parent.document.documentElement.lang = "ko"; } catch (e) {}</script>', height=0, width=0)
    st.markdown(
        '<header class="app-header">'
        '<div class="app-title-group">'
        '<h1 class="app-title">뉴스 주제별 구간 자동 분할기</h1>'
        '<p class="app-sub">뉴스 미디어 파일을 업로드하면 전체 주제별로 구간을 분할하고, 원하는 구간만 선택하여 EDL 파일로 생성할 수 있습니다.</p>'
        '</div>'
        '</header>',
        unsafe_allow_html=True,
    )

# ==============================================================================
# 4. 파이프라인 및 방송 데이터 포맷팅
# ==============================================================================
PIPELINE_STEPS = [
    {"title": "미디어 전처리"},
    {"title": "음성 인식 (STT)"},
    {"title": "AI 주제별 구간 분석"},
    {"title": "EDL 패키징"},
]

def render_pipeline(placeholder, active_index: int, done: bool = False) -> None:
    html_str = '<div class="stepper-container">'
    for i, step in enumerate(PIPELINE_STEPS):
        if done or i < active_index:
            state = "done"
            icon_html = icon("check", 16, "currentColor", 3)
        elif i == active_index:
            state = "active"
            icon_html = f"{i+1}"
        else:
            state = "pending"
            icon_html = f"{i+1}"

        html_str += (
            f'<div class="step-node {state}">'
            f'<div class="step-circle">{icon_html}</div>'
            f'<div class="step-label">{step["title"]}</div>'
            f'</div>'
        )
    html_str += '</div>'
    placeholder.markdown(html_str, unsafe_allow_html=True)

def _is_ntsc_rate(fps: float) -> bool:
    return any(abs(fps - r) < 0.05 for r in (23.976, 29.97, 59.94))

def _seconds_to_drop_frame_tc(seconds: float, nominal_fps: int) -> str:
    seconds = max(0.0, float(seconds))
    drop_frames = 2 if nominal_fps == 30 else 4
    frames_per_min = nominal_fps * 60
    frames_per_10min = frames_per_min * 10

    total_frames = int(round(seconds * (nominal_fps * 1000 / 1001)))
    d, m = divmod(total_frames, frames_per_10min)
    if m >= drop_frames:
        total_frames += drop_frames * 9 * d + drop_frames * ((m - drop_frames) // (frames_per_min - drop_frames))
    else:
        total_frames += drop_frames * 9 * d

    ff = total_frames % nominal_fps
    total_seconds = total_frames // nominal_fps
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d};{ff:02d}"

def seconds_to_timecode(seconds: float, fps: float = 29.97) -> str:
    seconds = max(0.0, float(seconds))
    if _is_ntsc_rate(fps):
        nominal = 60 if abs(fps - 59.94) < 0.05 else 30
        return _seconds_to_drop_frame_tc(seconds, nominal)

    nominal = int(round(fps)) or 30
    total_frames = int(round(seconds * nominal))
    hh = total_frames // (3600 * nominal)
    mm = (total_frames % (3600 * nominal)) // (60 * nominal)
    ss = (total_frames % (60 * nominal)) // nominal
    ff = total_frames % nominal
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

def _derive_reel_name(filename: str) -> str:
    base = os.path.splitext(filename)[0]
    base = re.sub(r"[^A-Za-z0-9]", "", base).upper()
    return base[:8] if base else "REEL001"

def generate_edl(highlights: list, source_filename: str = "source.mp4", fps: float = 29.97) -> str:
    is_df = _is_ntsc_rate(fps)
    fcm = "DROP FRAME" if is_df else "NON-DROP FRAME"
    reel_name = _derive_reel_name(source_filename)

    edl_lines = ["TITLE: AI_TOPIC_SPLIT_EDL", f"FCM: {fcm}", ""]
    rec_cursor = 0.0

    for i, hl in enumerate(highlights, 1):
        src_start = float(hl.get("start_time", 0.0))
        src_end = float(hl.get("end_time", 0.0))
        clip_duration = max(0.0, src_end - src_start)

        src_in_tc = seconds_to_timecode(src_start, fps)
        src_out_tc = seconds_to_timecode(src_end, fps)
        rec_in_tc = seconds_to_timecode(rec_cursor, fps)
        rec_out_tc = seconds_to_timecode(rec_cursor + clip_duration, fps)
        rec_cursor += clip_duration

        event_num = f"{i:03d}"
        edl_lines.append(f"{event_num}  {reel_name:<8} AA/V  C        {src_in_tc} {src_out_tc} {rec_in_tc} {rec_out_tc}")
        edl_lines.append(f"* FROM CLIP NAME: {hl.get('main_title', 'Unknown')}")
        edl_lines.append(f"* SOURCE FILE: {source_filename}")
        edl_lines.append("")

    return "\n".join(edl_lines)

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

def get_video_fps(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        raw = result.stdout.strip()
        if not raw:
            return 29.97
        if "/" in raw:
            num, den = raw.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 29.97
        else:
            fps = float(raw)
        return fps if fps > 0 else 29.97
    except (subprocess.CalledProcessError, ValueError, ZeroDivisionError):
        return 29.97

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

def extract_transcript(groq_client: Groq, file_bytes: bytes, file_name: str) -> list:
    suffix = os.path.splitext(file_name)[1] or ".mp4"
    raw_path = None
    audio_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            raw_path = tmp.name

        audio_path = prepare_audio_for_groq(raw_path)

        with open(audio_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="ko",
            )

        raw_segments = getattr(transcription, "segments", []) or []
        segments = []
        for seg in raw_segments:
            if isinstance(seg, dict):
                start, end, text = seg.get("start", 0.0), seg.get("end", 0.0), seg.get("text", "")
            else:
                start = getattr(seg, "start", 0.0)
                end = getattr(seg, "end", 0.0)
                text = getattr(seg, "text", "")
            text = str(text).strip()
            if text:
                segments.append({"start": round(float(start), 2), "end": round(float(end), 2), "text": text})
        return segments
    finally:
        for path in (raw_path, audio_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

def sanitize_and_fix_topics(raw_topics: list, media_duration: float = 0.0) -> list:
    fixed_list = []
    if not isinstance(raw_topics, list):
        return fixed_list

    for i, item in enumerate(raw_topics):
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

            if start_time >= end_time:
                continue

            item["start_time"] = round(start_time, 2)
            item["end_time"] = round(end_time, 2)
            
            # 임팩트 점수가 없거나 잘못된 경우 기본값 부여 (정렬 화면과 맞춤)
            if "impact_score" not in item:
                item["impact_score"] = max(70, 95 - (i * 3))
            
            fixed_list.append(item)
        except (TypeError, ValueError):
            continue

    fixed_list.sort(key=lambda x: x["start_time"])
    return fixed_list

def run_gemini_topic_splitting(api_key: str, transcript_segments: list, media_duration: float = 0.0) -> list:
    client = genai.Client(api_key=api_key)
    # 404 에러 방지를 위해 최신 권장 모델명을 사용합니다[cite: 10]
    preferred_models = ["gemini-2.5-flash", "gemini-2.5-pro"]

    formatted_transcript = "\n".join(
        f"[{seg['start']:.2f}s ~ {seg['end']:.2f}s] {seg['text']}" for seg in transcript_segments
    )

    prompt = f"""
너는 전문 방송 뉴스 에디터이다.
아래 제공된 뉴스 자막 전체의 타임코드를 분석하여, 뉴스 영상 내에 등장하는 **모든 독립된 주제(아이템, 리포트, 오프닝, 클로징 등)별로 빠짐없이 구간을 나누어라.**

[필수 규칙]
1. 영상의 처음부터 끝까지 전체 흐름이 누락되는 구간 없이 연속적인 주제별 구간들로 나눈다.
2. 각 구간은 의미가 통하는 하나의 주제 단위여야 하며, 시작 시간과 종료 시간을 정확히 명시한다.
3. 영상 총 길이는 약 {media_duration:.2f}초이다.
4. 각 주제별로 명확한 추천 제목(main_title), 자막 미리보기 요약(reason) 및 임팩트 점수(impact_score, 70~99 사이 정수)를 작성한다.

[뉴스 자막 데이터]
{formatted_transcript}
"""

    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "main_title": {"type": "STRING", "description": "추천 제목 (20자 이내)"},
                    "sub_title": {"type": "STRING", "description": "카테고리/핵심 요약 (30자 이내)"},
                    "start_time": {"type": "NUMBER", "description": "구간 시작 시간(초)"},
                    "end_time": {"type": "NUMBER", "description": "구간 종료 시간(초)"},
                    "impact_score": {"type": "INTEGER", "description": "임팩트 점수 (70~99)"},
                    "reason": {"type": "STRING", "description": "자막 미리보기 및 요약 내용"},
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "impact_score", "reason"],
            },
        },
        temperature=0.2,
    )

    failures = []
    for model_name in preferred_models:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=gen_config)
            raw_data = json.loads(response.text)
            fixed = sanitize_and_fix_topics(raw_data, media_duration)
            if len(fixed) >= 1:
                return fixed
            failures.append(f"{model_name}: 유효한 구간을 반환하지 않음")
        except Exception as error:
            failures.append(f"{model_name}: {error}")
            continue

    detail = " / ".join(failures) if failures else "알 수 없는 오류"
    raise RuntimeError(f"주제별 구간 분할에 실패했습니다 → {detail}")

# ==============================================================================
# 5. 메인 애플리케이션
# ==============================================================================
def main():
    render_header()

    gemini_api_key = get_gemini_api_key()
    groq_api_key = get_groq_api_key()
    missing = [name for name, key in [("GEMINI_API_KEY", gemini_api_key), ("GROQ_API_KEY", groq_api_key)] if not key]
    if missing:
        accessible_alert(
            f"{', '.join(missing)}가 설정되지 않았습니다. Streamlit Cloud에서는 "
            "Settings → Secrets에, 로컬에서는 .env 파일에 설정해주세요.",
            kind="error",
            icon_name="alert-triangle",
        )
        return

    groq_client = Groq(api_key=groq_api_key)

    st.markdown('<p style="font-size:1.05rem; font-weight:700; margin: 16px 0 8px; color:var(--text-primary);">미디어 소스 업로드</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("파일 업로드", type=["mp4", "mp3", "mov"], label_visibility="collapsed")
    
    if uploaded_file:
        start_button = st.button("분할 및 구간 분석 시작", type="primary", use_container_width=True)
    else:
        start_button = False
        if "topics" in st.session_state:
            del st.session_state["topics"]
        return
    
    st.markdown('<hr style="margin: 20px 0; border: none; border-top: 1px solid var(--border);">', unsafe_allow_html=True)
    
    pipe_placeholder = st.empty()
    render_pipeline(pipe_placeholder, active_index=-1)

    if start_button:
        raw_input_path = None
        try:
            render_pipeline(pipe_placeholder, active_index=0)
            file_bytes = uploaded_file.read()

            suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                raw_input_path = tmp.name
            media_duration = get_media_duration(raw_input_path)
            video_fps = get_video_fps(raw_input_path)

            render_pipeline(pipe_placeholder, active_index=1)
            segments = extract_transcript(groq_client, file_bytes, uploaded_file.name)

            if not segments:
                raise RuntimeError("음성에서 자막을 추출하지 못했습니다. 오디오 트랙을 확인해주세요.")

            render_pipeline(pipe_placeholder, active_index=2)
            topics = run_gemini_topic_splitting(gemini_api_key, segments, media_duration)
            
            render_pipeline(pipe_placeholder, active_index=3, done=True)

            st.session_state["topics"] = topics
            st.session_state["video_fps"] = video_fps
            st.session_state["source_filename"] = uploaded_file.name
            # 전체 선택 상태 초기화
            for idx in range(len(topics)):
                st.session_state[f"chk_{idx}"] = True

        except Exception as e:
            accessible_alert(f"처리 중 문제가 발생했습니다: {str(e)}", kind="error", icon_name="x-circle")
            return
        finally:
            if raw_input_path and os.path.exists(raw_input_path):
                try:
                    os.remove(raw_input_path)
                except OSError:
                    pass

    # 분석 결과가 있는 경우 2분할 레이아웃 적용 (비율 약 7:3)
    if "topics" in st.session_state and st.session_state["topics"]:
        render_pipeline(pipe_placeholder, active_index=3, done=True)
        topics = st.session_state["topics"]
        video_fps = st.session_state.get("video_fps", 29.97)
        source_filename = st.session_state.get("source_filename", "source.mp4")

        # 전체 선택/해제 상태 관리용 콜백 함수
        if "select_all_state" not in st.session_state:
            st.session_state["select_all_state"] = True

        col_left, col_right = st.columns([7, 3], gap="medium")

        # ----------------------------------------------------
        # 좌측 영역: 토픽 리스트 패널
        # ----------------------------------------------------
        with col_left:
            st.markdown('<div class="panel-container">', unsafe_allow_html=True)
            
            # 헤더 영역
            selected_count = sum(1 for i in range(len(topics)) if st.session_state.get(f"chk_{i}", True))
            
            col_h1, col_h2 = st.columns([6, 4])
            with col_h1:
                st.markdown(f'<h3 class="panel-title" style="margin-top:4px;">토픽 리스트</h3>', unsafe_allow_html=True)
            with col_h2:
                sub_col1, sub_col2 = st.columns([7, 5])
                with sub_col1:
                    st.markdown(f'<div style="text-align:right; font-size:0.85rem; color:var(--text-secondary); padding-top:6px;"><b>{selected_count}개</b> 선택됨</div>', unsafe_allow_html=True)
                with sub_col2:
                    if st.button("선택 해제", use_container_width=True, key="deselect_all_btn"):
                        for i in range(len(topics)):
                            st.session_state[f"chk_{i}"] = False
                        st.rerun()

            st.markdown('<hr style="margin: 12px 0; border: none; border-top: 1px solid var(--border);">', unsafe_allow_html=True)

            # 테이블 헤더
            st.markdown(
                '<table class="custom-table">'
                '<thead><tr>'
                '<th style="width: 40px; text-align:center;">#</th>'
                '<th style="width: 140px;">구간 (IN - OUT)</th>'
                '<th style="width: 60px;">길이</th>'
                '<th style="width: 70px; text-align:center;">임팩트</th>'
                '<th>추천 제목</th>'
                '<th>자막 미리보기</th>'
                '</tr></thead>'
                '<tbody>',
                unsafe_allow_html=True
            )

            selected_indices = []
            total_selected_duration = 0.0

            for index, topic in enumerate(topics):
                start_sec = float(topic.get("start_time", 0.0))
                end_sec = float(topic.get("end_time", 0.0))
                duration = round(end_sec - start_sec, 1)
                title = html.escape(str(topic.get("main_title", f"주제 {index + 1}")))
                reason = html.escape(str(topic.get("reason", "-")))
                impact = int(topic.get("impact_score", 80))
                
                in_tc = seconds_to_timecode(start_sec, video_fps)
                out_tc = seconds_to_timecode(end_sec, video_fps)
                tc_str = f"{in_tc} - {out_tc}"
                dur_str = f"00:{int(duration):02d}" if duration < 60 else f"{int(duration)//60:02d}:{int(duration)%60:02d}"

                # 행 단위 체크박스 (Streamlit native checkbox 활용)
                is_chk = st.checkbox("선택", value=st.session_state.get(f"chk_{index}", True), key=f"chk_{index}", label_visibility="collapsed")
                
                if is_chk:
                    selected_indices.append(index)
                    total_selected_duration += duration

                st.markdown(
                    f'<tr>'
                    f'<td style="text-align:center; font-weight:600; color:var(--text-secondary);">{index + 1}</td>'
                    f'<td><span class="tc-text">{tc_str}</span></td>'
                    f'<td><span class="tc-text">{dur_str}</span></td>'
                    f'<td style="text-align:center;"><span class="score-badge">{impact}</span></td>'
                    f'<td style="font-weight:600;">{title}</td>'
                    f'<td style="color:var(--text-secondary); font-size:0.82rem;">{reason}</td>'
                    f'</tr>',
                    unsafe_allow_html=True
                )

            st.markdown('</tbody></table>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ----------------------------------------------------
        # 우측 영역: EDL 파일 생성 패널
        # ----------------------------------------------------
        with col_right:
            st.markdown('<div class="panel-container">', unsafe_allow_html=True)
            st.markdown('<h3 class="panel-title" style="margin-bottom:16px;">EDL 파일 생성</h3>', unsafe_allow_html=True)

            # 정보성 텍스트 키-값 정렬
            total_dur_str = f"{int(total_selected_duration)//60:02d}:{int(total_selected_duration)%60:02d}"
            
            st.markdown(
                f'<div class="kv-row"><span class="kv-key">내보낼 항목</span><span class="kv-val">{len(selected_indices)}개 클립</span></div>'
                f'<div class="kv-row"><span class="kv-key">총 러닝타임(선택분)</span><span class="kv-val">{total_dur_str}</span></div>'
                f'<div class="kv-row"><span class="kv-key">타임코드 형식</span><span class="kv-val">00:00:00:00 ({int(video_fps)}fps)</span></div>'
                f'<div class="kv-row" style="border-bottom: none; margin-bottom: 8px;"><span class="kv-key">트랙 매핑</span><span class="kv-val">V1 / A1</span></div>',
                unsafe_allow_html=True
            )

            st.markdown('<p style="font-size:0.88rem; font-weight:600; color:var(--text-primary); margin: 12px 0 6px;">파일명</p>', unsafe_allow_html=True)
            default_edl_name = f"{os.path.splitext(source_filename)[0]}_highlights.edl"
            file_name_input = st.text_input("파일명 입력", value=default_edl_name, label_visibility="collapsed")

            st.markdown('<div style="margin-top: 16px;"></div>', unsafe_allow_html=True)
            st.info("EDIUS 호환 EDL (CMX 3600) 형식으로 생성됩니다.")

            if not selected_indices:
                st.warning("최소 1개 이상의 토픽을 선택해주세요.")
                st.button("EDL 파일 생성", type="primary", disabled=True, use_container_width=True)
            else:
                filtered_topics = [topics[i] for i in selected_indices]
                edl_content = generate_edl(filtered_topics, source_filename=source_filename, fps=video_fps)
                
                b64_content = base64.b64encode(edl_content.encode('utf-8')).decode('utf-8')
                href = f"data:text/plain;charset=utf-8;base64,{b64_content}"
                safe_filename = html.escape(file_name_input)

                # 커스텀 다운로드 버튼 형태의 링크 마크다운
                st.markdown(
                    f'<a href="{href}" download="{safe_filename}" style="text-decoration:none;">'
                    f'<button kind="primary" style="width:100%; cursor:pointer;">'
                    f'{icon("download", 18, "#FFFFFF")} EDL 파일 생성'
                    f'</button></a>',
                    unsafe_allow_html=True,
                )

            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
