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
    "chevron-right": '<polyline points="9 18 15 12 9 6"/>',
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
        padding-top: 2rem !important;
    }}

    div[data-testid="stVerticalBlock"] {{ gap: 0.75rem !important; }}

    .app-header {{ display:flex; align-items:center; gap:16px; margin-bottom: 8px; }}
    .app-title-group {{ display:flex; flex-direction:column; gap:4px; }}
    .app-title {{
        font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:1.75rem;
        margin:0; color:var(--text-primary); letter-spacing:-0.5px; line-height:1.2;
    }}
    .app-sub {{ color:var(--text-secondary); font-size:0.95rem; line-height:1.4; margin:0; }}

    .a11y-alert {{
        display:flex; align-items:center; gap:10px;
        border-radius:10px; padding:14px 18px; margin: 16px 0;
        font-size:0.92rem; line-height:1.5; font-weight: 500;
    }}
    .a11y-alert-info {{ background:var(--brand-tint); color:var(--brand-dark); }}
    .a11y-alert-error {{ background:#FEF2F2; border-color:#FECACA; color:#991B1B; border:1px solid; }}

    [data-testid="stFileUploader"] {{
        background-color: var(--surface);
        border: 2px dashed #CBD5E1 !important;
        border-radius: 16px !important;
        padding: 16px !important;
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

    /* 테이블 스타일링 및 패널 컨테이너 */
    .panel-container {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 20px;
        box-shadow: var(--shadow-md);
        height: 100%;
    }}
    
    .panel-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        border-bottom: 1px solid var(--border);
        padding-bottom: 12px;
    }}
    
    .panel-title {{
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
    }}

    /* 커스텀 버튼 디자인 (이미지 하단 주황색 버튼 스타일 매칭) */
    .custom-edl-btn {{
        background-color: #FF5722 !important;
        color: white !important;
        font-weight: 600 !important;
        width: 100%;
        padding: 0.75rem;
        border-radius: 8px;
        text-align: center;
        display: block;
        text-decoration: none !important;
        box-shadow: 0 4px 6px rgba(255, 87, 34, 0.2);
        transition: background 0.2s;
        border: none;
        cursor: pointer;
        font-size: 1rem;
    }}
    .custom-edl-btn:hover {{
        background-color: #E64A19 !important;
    }}

    button[kind="primary"] {{
        background-color: var(--brand) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.6rem 1.5rem !important;
        border-radius: 12px !important;
        border: 1px solid var(--brand) !important;
        transition: all 0.2s ease !important;
        min-height: 48px;
    }}
    button[kind="primary"]:hover {{
        background-color: var(--brand-dark) !important;
        border-color: var(--brand-dark) !important;
        transform: translateY(-1px) !important;
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

    for item in raw_topics:
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
            fixed_list.append(item)
        except (TypeError, ValueError):
            continue

    fixed_list.sort(key=lambda x: x["start_time"])
    return fixed_list


def run_gemini_topic_splitting(api_key: str, transcript_segments: list, media_duration: float = 0.0) -> list:
    # 💥 에러 방지 핵심 수정: API 스펙 에러가 나지 않는 최신 안정 모델("gemini-2.5-flash") 사용
    client = genai.Client(api_key=api_key)
    preferred_models = ["gemini-2.5-flash", "gemini-1.5-flash"]

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
4. 각 주제별로 명확한 제목, 요약 설명, 그리고 임팩트 점수(70~95 사이 정수)를 부여한다.

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
                    "main_title": {"type": "STRING", "description": "주제/리포트 제목 (20자 이내)"},
                    "sub_title": {"type": "STRING", "description": "카테고리/핵심 요약 (30자 이내)"},
                    "start_time": {"type": "NUMBER", "description": "구간 시작 시간(초)"},
                    "end_time": {"type": "NUMBER", "description": "구간 종료 시간(초)"},
                    "impact_score": {"type": "INTEGER", "description": "임팩트 점수 (70~95)"},
                    "reason": {"type": "STRING", "description": "해당 주제 요약 및 설명"},
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

    st.markdown('<p style="font-size:1rem; font-weight:700; margin: 12px 0 8px; color:var(--text-primary);">미디어 소스 업로드</p>', unsafe_allow_html=True)
    
    col_up, col_btn = st.columns([0.8, 0.2], vertical_alignment="bottom")
    with col_up:
        uploaded_file = st.file_uploader("파일 업로드", type=["mp4", "mp3", "mov"], label_visibility="collapsed")
    with col_btn:
        start_button = st.button("분할 및 구간 분석 시작", type="primary", use_container_width=True, disabled=(uploaded_file is None))
    
    pipe_placeholder = st.empty()
    render_pipeline(pipe_placeholder, active_index=-1)

    if start_button and uploaded_file:
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
            
            # 초기 선택 상태 세팅 (전부 선택)
            for i in range(len(topics)):
                st.session_state[f"chk_{i}"] = True

        except Exception as e:
            accessible_alert(f"처리 중 문제가 발생했습니다: {str(e)}", kind="error", icon_name="x-circle")
            return
        finally:
            if raw_input_path and os.path.exists(raw_input_path):
                try:
                    os.remove(raw_input_path)
                except OSError:
                    pass

    # 분석 결과가 있는 경우 가로 2분할(7:3 또는 8:4 비율 구현) 레이아웃 렌더링
    if "topics" in st.session_state and st.session_state["topics"]:
        render_pipeline(pipe_placeholder, active_index=3, done=True)
        topics = st.session_state["topics"]
        video_fps = st.session_state.get("video_fps", 29.97)
        source_filename = st.session_state.get("source_filename", "source.mp4")

        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        
        # 화면 가로 2분할 (좌측 토픽 리스트: 8, 우측 EDL 패널: 4 비율)
        left_col, right_col = st.columns([8, 4], gap="medium")

        # 콜백: 선택 해제 버튼 동작용
        def deselect_all():
            for i in range(len(topics)):
                st.session_state[f"chk_{i}"] = False

        with left_col:
            st.markdown('<div class="panel-container">', unsafe_allow_html=True)
            
            # 좌측 헤더 영역
            selected_count = sum(1 for i in range(len(topics)) if st.session_state.get(f"chk_{i}", True))
            
            hc1, hc2 = st.columns([0.6, 0.4])
            with hc1:
                st.markdown(f'<h3 class="panel-title" style="padding-top:6px;">토픽 리스트</h3>', unsafe_allow_html=True)
            with hc2:
                col_cnt, col_btn_clear = st.columns([0.55, 0.45], vertical_alignment="center")
                with col_cnt:
                    st.markdown(f'<span style="font-size:0.85rem; color:var(--text-secondary); white-space:nowrap;"><b>{selected_count}</b>개 선택됨</span>', unsafe_allow_html=True)
                with col_btn_clear:
                    st.button("선택 해제", on_click=deselect_all, use_container_width=True)

            st.markdown('<hr style="margin: 12px 0; border: none; border-top: 1px solid var(--border);">', unsafe_allow_html=True)

            # 테이블 헤더 모방 행
            th_cols = st.columns([0.6, 0.6, 2.2, 1.0, 1.2, 2.5, 3.0])
            headers = ["", "#", "구간 (IN-OUT)", "길이", "임팩트 점수", "추천 제목", "자막 미리보기"]
            for col, h_text in zip(th_cols, headers):
                with col:
                    st.markdown(f'<span style="font-size:0.8rem; font-weight:700; color:var(--text-secondary);">{h_text}</span>', unsafe_allow_html=True)

            st.markdown('<div style="border-bottom: 1px solid var(--border); margin: 8px 0 4px 0;"></div>', unsafe_allow_html=True)

            # 각 행 데이터 렌더링
            for index, topic in enumerate(topics):
                start_sec = float(topic.get("start_time", 0.0))
                end_sec = float(topic.get("end_time", 0.0))
                duration = round(end_sec - start_sec, 1)
                title = html.escape(str(topic.get("main_title", f"주제 {index + 1}")))
                reason = html.escape(str(topic.get("reason", "-")))
                impact = topic.get("impact_score", 85)
                
                in_tc = seconds_to_timecode(start_sec, video_fps)
                out_tc = seconds_to_timecode(end_sec, video_fps)
                tc_str = f"{in_tc} - {out_tc}"
                dur_str = f"00:{int(duration):02d}" if duration < 60 else f"{int(duration)//60:02d}:{int(duration)%60:02d}"

                row_cols = st.columns([0.6, 0.6, 2.2, 1.0, 1.2, 2.5, 3.0], vertical_alignment="center")
                
                with row_cols[0]:
                    st.checkbox("선택", value=True, key=f"chk_{index}", label_visibility="collapsed")
                with row_cols[1]:
                    st.markdown(f'<span style="font-size:0.85rem; font-weight:600; color:var(--text-primary);">{index + 1}</span>', unsafe_allow_html=True)
                with row_cols[2]:
                    st.markdown(f'<span style="font-size:0.75rem; font-family:\'IBM Plex Mono\', monospace; color:var(--text-secondary);">{tc_str}</span>', unsafe_allow_html=True)
                with row_cols[3]:
                    st.markdown(f'<span style="font-size:0.8rem; font-family:\'IBM Plex Mono\', monospace; color:var(--text-secondary);">{dur_str}</span>', unsafe_allow_html=True)
                with row_cols[4]:
                    st.markdown(f'<span style="font-size:0.85rem; font-weight:700; color:#EF4444;">{impact}</span>', unsafe_allow_html=True)
                with row_cols[5]:
                    st.markdown(f'<span style="font-size:0.85rem; font-weight:600; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:block;" title="{title}">{title}</span>', unsafe_allow_html=True)
                with row_cols[6]:
                    st.markdown(f'<span style="font-size:0.78rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:block;" title="{reason}">{reason}</span>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        with right_col:
            st.markdown('<div class="panel-container">', unsafe_allow_html=True)
            st.markdown('<h3 class="panel-title" style="margin-bottom:16px;">EDL 파일 생성</h3>', unsafe_allow_html=True)

            # 선택된 항목 수 및 총 러닝타임 계산
            selected_indices = [i for i in range(len(topics)) if st.session_state.get(f"chk_{i}", True)]
            filtered_topics = [topics[i] for i in selected_indices]
            
            total_duration_sec = sum(float(t.get("end_time", 0)) - float(t.get("start_time", 0)) for t in filtered_topics)
            tot_min = int(total_duration_sec) // 60
            tot_sec = int(total_duration_sec) % 60
            tot_time_str = f"{tot_min:02d}:{tot_sec:02d}"

            # 정보성 텍스트 키-값 형태 정렬
            info_items = [
                ("내보낼 항목", f"{len(selected_indices)}개 클립"),
                ("총 러닝타임(선택분)", tot_time_str),
                ("타임코드 형식", f"00:00:00:00 ({int(round(video_fps))}fps)"),
                ("트랙 매핑", "V1 / A1")
            ]

            for k, v in info_items:
                ik_col, iv_col = st.columns([0.45, 0.55])
                with ik_col:
                    st.markdown(f'<span style="font-size:0.85rem; color:var(--text-secondary);">{k}</span>', unsafe_allow_html=True)
                with iv_col:
                    st.markdown(f'<span style="font-size:0.85rem; font-weight:600; color:var(--text-primary); text-align:right; display:block; font-family:\'IBM Plex Mono\', monospace;">{v}</span>', unsafe_allow_html=True)
                st.markdown('<div style="margin: 4px 0; border-bottom: 1px dashed var(--border);"></div>', unsafe_allow_html=True)

            st.markdown('<div style="margin-top: 12px;"></div>', unsafe_allow_html=True)
            st.markdown('<span style="font-size:0.85rem; color:var(--text-secondary); font-weight:600;">파일명</span>', unsafe_allow_html=True)
            
            default_edl_name = f"{os.path.splitext(source_filename)[0]}_highlights.edl"
            edl_filename_input = st.text_input("파일명 입력", value=default_edl_name, label_visibility="collapsed")

            st.markdown('<div style="margin-top: 8px;"></div>', unsafe_allow_html=True)
            st.info("EDIUS 호환 EDL (CMX 3600) 형식으로 생성됩니다.")
            st.markdown('<div style="margin-top: 8px;"></div>', unsafe_allow_html=True)

            if not selected_indices:
                st.markdown('<button class="custom-edl-btn" style="opacity: 0.6; cursor: not-allowed;" disabled>EDL 파일 생성</button>', unsafe_allow_html=True)
            else:
                edl_content = generate_edl(filtered_topics, source_filename=source_filename, fps=video_fps)
                b64_content = base64.b64encode(edl_content.encode('utf-8')).decode('utf-8')
                download_filename = edl_filename_input.strip() or default_edl_name
                href = f"data:text/plain;charset=utf-8;base64,{b64_content}"

                st.markdown(
                    f'<a href="{href}" download="{html.escape(download_filename)}" class="custom-edl-btn">'
                    f'{icon("download", 18, "#FFFFFF", 2.5)} EDL 파일 생성'
                    f'</a>',
                    unsafe_allow_html=True
                )

            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
