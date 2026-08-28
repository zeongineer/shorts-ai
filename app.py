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
    page_title="뉴스 숏폼 하이라이트 추출기",
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
    "play": '<polygon points="5 3 19 12 5 21 5 3"/>',
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
        max-width: 1200px !important;
        margin: 0 auto;
        padding-top: 3rem !important;
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
        border-radius:10px; padding:14px 18px; margin: 24px 0 16px;
        font-size:0.92rem; line-height:1.5; font-weight: 500;
    }}
    .a11y-alert-info {{ background:var(--brand-tint); color:var(--brand-dark); }}
    .a11y-alert-error {{ background:#FEF2F2; border-color:#FECACA; color:#991B1B; border:1px solid; }}

    [data-testid="stFileUploader"] {{
        background-color: var(--bg-base);
        border: 2px dashed #CBD5E1 !important;
        border-radius: 16px !important;
        padding: 24px !important;
        transition: all 0.2s ease;
    }}
    [data-testid="stFileUploader"]:hover {{ border-color: var(--brand) !important; background-color: var(--brand-tint); }}

    .stepper-container {{
        display: flex; justify-content: space-between; position: relative; 
        margin: 24px 0 36px; padding: 0 20px;
    }}
    .stepper-container::before {{
        content: ""; position: absolute; top: 15px; left: 50px; right: 50px; height: 2px;
        background: var(--border); z-index: 1;
    }}
    .step-node {{
        position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; gap: 10px;
        width: 120px;
    }}
    .step-circle {{
        width: 32px; height: 32px; border-radius: 50%; background: var(--surface); border: 2px solid var(--border);
        display: flex; align-items: center; justify-content: center; font-weight: 700; color: var(--text-secondary);
        font-size: 0.9rem; transition: all 0.3s;
    }}
    .step-label {{ font-size: 0.9rem; font-weight: 600; color: var(--text-secondary); text-align: center; }}
    
    .step-node.done .step-circle {{ background: var(--brand); border-color: var(--brand); color: #FFF; }}
    .step-node.done .step-label {{ color: var(--text-primary); }}
    .step-node.active .step-circle {{ border-color: var(--brand); color: var(--brand); box-shadow: 0 0 0 4px var(--brand-tint); }}
    .step-node.active .step-label {{ color: var(--brand); }}

    .h-card {{
        background:var(--surface); border:1px solid var(--border); border-radius:16px;
        padding:24px; box-shadow: var(--shadow-md);
        display:flex; flex-direction:column; gap:12px;
    }}
    .h-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px; }}
    .h-card h3 {{ font-size:1.1rem; margin:0; line-height:1.4; color:var(--text-primary); font-weight:700; }}
    
    .step-num {{ 
        display: inline-flex; align-items: center; justify-content: center;
        width: 26px; height: 26px; border-radius: 50%;
        background: var(--brand); color: #FFF; font-weight: 700; font-size: 0.85rem;
    }}

    .h-row {{
        display:flex; align-items:center; gap:12px; font-family:'IBM Plex Mono', monospace;
        font-size:0.85rem; color:var(--text-secondary); margin-bottom: 4px;
    }}
    .tc-block {{ display: flex; align-items: center; gap: 6px; }}
    
    .h-reason {{
        margin-top: 4px; background:var(--brand-tint); border-radius:8px; border: none;
        padding:14px; font-size:0.85rem; color:var(--text-secondary); line-height:1.6;
    }}
    .h-reason b {{ color:var(--brand-dark); display:block; margin-bottom:4px; font-weight: 600; }}

    .dl-wrapper {{ 
        flex-direction: row; align-items: center; justify-content: space-between; 
        background-color: var(--brand-tint); border-color: #DBEAFE;
    }}
    .download-icon-box {{
        width:48px; height:48px; border-radius:10px; background:var(--surface); color:var(--brand);
        display:flex; align-items:center; justify-content:center; flex-shrink:0;
        box-shadow: var(--shadow-sm);
    }}
    .file-name {{ font-weight:700; font-size:1rem; color:var(--text-primary); margin-bottom:2px; }}
    .file-meta {{ color:var(--text-secondary); font-size:0.85rem; }}
    
    .dl-btn {{
        background-color: var(--brand); color: #FFFFFF !important;
        font-weight: 600; font-size: 0.95rem; padding: 0.6rem 1.5rem;
        border-radius: 8px; text-decoration: none !important;
        display: inline-block; transition: all 0.2s ease;
        border: 1px solid var(--brand);
    }}
    .dl-btn:hover {{ background-color: var(--brand-dark); border-color: var(--brand-dark); transform: translateY(-1px); }}
    
    button[kind="primary"] {{
        background-color: var(--brand) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 12px !important;
        border: 1px solid var(--brand) !important;
        transition: all 0.2s ease !important;
        min-height: 52px;
        margin-top: 8px;
    }}
    button[kind="primary"]:hover {{
        background-color: var(--brand-dark) !important;
        border-color: var(--brand-dark) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 6px -1px rgba(30, 58, 138, 0.2) !important;
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
        '<h1 class="app-title">뉴스 숏폼 하이라이트 자동 추출기</h1>'
        '<p class="app-sub">뉴스 미디어 파일을 업로드하면 자막을 분석하고, Gemini가 가장 임팩트 있는 숏폼 구간을 자동 선정합니다.</p>'
        '</div>'
        '</header>',
        unsafe_allow_html=True,
    )
    accessible_alert("처리 완료 시 편집기(EDIUS 등)에 즉시 임포트 가능한 타임코드 EDL 파일이 제공됩니다.", kind="info", icon_name="bulb")

# ==============================================================================
# 4. 파이프라인 및 방송 데이터 포맷팅
# ==============================================================================
PIPELINE_STEPS = [
    {"title": "미디어 전처리"},
    {"title": "음성 인식 (STT)"},
    {"title": "AI 숏폼 분석"},
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

    edl_lines = ["TITLE: AI_SHORTFORM_EDL", f"FCM: {fcm}", ""]
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
        raise RuntimeError(f"오디오 변환(ffmpeg) 실패:\n{e.stderr.decode('utf-8', errors='ignore')}")

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

def generate_preview_clip(input_file_path: str, start_time: float, end_time: float) -> str:
    """미리보기용으로 원본 전체 대신 해당 하이라이트 구간만 H.264/AAC MP4로 잘라내어 인코딩합니다."""
    output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_path = output_temp.name
    output_temp.close()

    duration = max(1.0, end_time - start_time)
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_time), "-i", input_file_path,
        "-t", str(duration), "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "28", "-c:a", "aac", "-b:a", "96k", "-pix_fmt", "yuv420p",
        output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except subprocess.CalledProcessError:
        if os.path.exists(output_path):
            os.remove(output_path)
        return ""

def generate_vtt_subtitles(segments: list, clip_start: float, clip_end: float) -> str:
    """해당 하이라이트 구간에 포함되는 자막만 추출하여 WebVTT(.vtt) 형식으로 변환합니다."""
    vtt_lines = ["WEBVTT", ""]
    idx = 1
    for seg in segments:
        s = seg.get("start", 0.0)
        e = seg.get("end", 0.0)
        text = seg.get("text", "")

        # 클립 범위와 겹치는 자막만 포함하되, 시간축은 클립 시작점 기준(0초부터)으로 조정
        if e >= clip_start and s <= clip_end:
            rel_s = max(0.0, s - clip_start)
            rel_e = max(rel_s + 0.5, e - clip_start)
            
            def fmt_time(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s_ = int(sec % 60)
                ms = int(round((sec - int(sec)) * 1000))
                return f"{h:02d}:{m:02d}:{s_:02d}.{ms:03d}"

            vtt_lines.append(f"{idx}")
            vtt_lines.append(f"{fmt_time(rel_s)} --> {fmt_time(rel_e)}")
            vtt_lines.append(text)
            vtt_lines.append("")
            idx += 1
    return "\n".join(vtt_lines)

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

def run_gemini_highlight_extraction(api_key: str, transcript_segments: list, media_duration: float = 0.0) -> list:
    client = genai.Client(api_key=api_key)
    preferred_models = ["gemini-3.6-flash", "gemini-3.7-flash"]

    formatted_transcript = "\n".join(
        f"[{seg['start']:.2f}s ~ {seg['end']:.2f}s] {seg['text']}" for seg in transcript_segments
    )

    prompt = f"""
너는 뉴스 방송 수석 에디터이자 YouTube Shorts/TikTok 전문 숏폼 에디터이다.
아래 뉴스 자막 데이터의 타임코드를 분석하여 숏폼으로 제작하기 가장 임팩트 있고
흥미로운 핵심 구간 3곳을 선정하라.

[필수 규칙]
1. 정확히 3개의 하이라이트를 반환한다.
2. 각 구간의 길이는 반드시 30초 이상 60초 이하여야 한다.
3. start_time은 선택한 첫 번째 자막의 시작 시간, end_time은 마지막 자막의 종료 시간이어야 한다.
4. 문장이 중간에 잘리지 않는 완전한 뉴스 맥락을 선택하라.
5. 영상 전체 길이는 약 {media_duration:.2f}초이다.

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
                    "main_title": {"type": "STRING", "description": "주제 제목 (15자 이내)"},
                    "sub_title": {"type": "STRING", "description": "카테고리/핵심 요약 (25자 이내)"},
                    "start_time": {"type": "NUMBER", "description": "시작 시간(초)"},
                    "end_time": {"type": "NUMBER", "description": "종료 시간(초)"},
                    "reason": {"type": "STRING", "description": "선정 이유"},
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "reason"],
            },
        },
        temperature=0.2,
    )

    failures = []
    for model_name in preferred_models:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=gen_config)
            raw_data = json.loads(response.text)
            fixed = sanitize_and_fix_highlights(raw_data, media_duration)
            if len(fixed) >= 1:
                return fixed[:3]
            failures.append(f"{model_name}: 유효한 구간을 반환하지 않음")
        except Exception as error:
            failures.append(f"{model_name}: {error}")
            continue

    detail = " / ".join(failures) if failures else "알 수 없는 오류"
    raise RuntimeError(f"하이라이트 추출에 실패했습니다 → {detail}")

# ==============================================================================
# 5. 하이라이트 카드 렌더링 및 미리보기
# ==============================================================================
def render_highlight_card(index: int, highlight: dict, segments: list, source_path: str, fps: float = 29.97) -> None:
    start_sec = float(highlight.get("start_time", 0.0))
    end_sec = float(highlight.get("end_time", 0.0))
    duration = round(end_sec - start_sec, 1)
    title = html.escape(str(highlight.get("main_title", f"하이라이트 {index + 1}")))
    reason = html.escape(str(highlight.get("reason", "-")))

    st.markdown(
        f'<article class="h-card">'
        f'<div class="h-top"><span class="step-num">{index + 1}</span></div>'
        f'<h3>{title}</h3>'
        f'<div class="h-row">'
        f'<div class="tc-block">{icon("clock", 14, "currentColor")} {seconds_to_timecode(start_sec, fps)} ~ {seconds_to_timecode(end_sec, fps)}</div>'
        f'<div class="tc-block" style="color:var(--brand); font-weight:500;">{icon("timer", 14, "currentColor")} {duration}초</div>'
        f'</div>'
        f'<div class="h-reason"><b>선정 이유</b>{reason}</div>'
        f'</article>',
        unsafe_allow_html=True,
    )

    preview_key = f"preview_{index}"
    is_preview_open = st.session_state.get(preview_key, False)

    if not is_preview_open:
        if st.button(f"▶ 재생 및 자막 미리보기 #{index + 1}", key=f"btn_{index}", use_container_width=True):
            st.session_state[preview_key] = True
            st.rerun()
    else:
        if st.button(f"▲ 미리보기 닫기 #{index + 1}", key=f"close_{index}", use_container_width=True):
            st.session_state[preview_key] = False
            st.rerun()
        
        with st.spinner("미리보기 클립 및 자막 생성 중..."):
            clip_path = generate_preview_clip(source_path, start_sec, end_sec)
            vtt_content = generate_vtt_subtitles(segments, start_sec, end_sec)

        if clip_path and os.path.exists(clip_path):
            try:
                st.video(clip_path, subtitles=vtt_content if vtt_content.count("-->") > 0 else None)
            except TypeError:
                # 구버전 Streamlit 호환용 폴백
                st.video(clip_path)
                accessible_alert("현재 사용 중인 Streamlit 버전은 자막 오버레이(subtitles 파라미터)를 직접 지원하지 않아 영상만 재생됩니다.", kind="info")
            finally:
                try:
                    os.remove(clip_path)
                except OSError:
                    pass
        else:
            accessible_alert("미리보기 클립을 생성하지 못했습니다.", kind="error")

# ==============================================================================
# 6. 메인 애플리케이션
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

    st.markdown('<p style="font-size:1.1rem; font-weight:700; margin: 24px 0 12px; color:var(--text-primary);">미디어 소스 업로드</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("파일 업로드", type=["mp4", "mp3", "mov"], label_visibility="collapsed")
    
    if uploaded_file:
        file_bytes = uploaded_file.read()
        
        # 파일이 변경되면 기존 결과 초기화
        if st.session_state.get("last_uploaded_name") != uploaded_file.name:
            st.session_state["last_uploaded_name"] = uploaded_file.name
            st.session_state["highlights"] = None
            st.session_state["segments"] = None
            st.session_state["video_fps"] = 29.97
            st.session_state["edl_content"] = None

        start_button = st.button("추출 및 EDL 생성 시작", type="primary", use_container_width=True)
    else:
        start_button = False
        st.session_state.clear()
        return
    
    st.markdown('<hr style="margin: 32px 0; border: none; border-top: 1px solid var(--border);">', unsafe_allow_html=True)
    
    pipe_placeholder = st.empty()

    if start_button:
        raw_input_path = None
        try:
            render_pipeline(pipe_placeholder, active_index=0)
            
            suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                raw_input_path = tmp.name
            
            # 임시 파일 경로를 세션에 저장해 미리보기 재생 시 사용
            st.session_state["source_path"] = raw_input_path
            media_duration = get_media_duration(raw_input_path)
            video_fps = get_video_fps(raw_input_path)
            st.session_state["video_fps"] = video_fps

            render_pipeline(pipe_placeholder, active_index=1)
            segments = extract_transcript(groq_client, file_bytes, uploaded_file.name)
            st.session_state["segments"] = segments

            if not segments:
                raise RuntimeError("음성에서 자막을 추출하지 못했습니다. 오디오 트랙을 확인해주세요.")

            render_pipeline(pipe_placeholder, active_index=2)
            highlights = run_gemini_highlight_extraction(gemini_api_key, segments, media_duration)
            st.session_state["highlights"] = highlights
            
            render_pipeline(pipe_placeholder, active_index=3)
            edl_content = generate_edl(highlights, source_filename=uploaded_file.name, fps=video_fps)
            st.session_state["edl_content"] = edl_content
            render_pipeline(pipe_placeholder, active_index=3, done=True)

        except Exception as e:
            accessible_alert(f"처리 중 문제가 발생했습니다: {str(e)}", kind="error", icon_name="x-circle")
            return

    # st.session_state에 데이터가 있으면 화면에 결과 렌더링 (재실행되어도 유지됨)
    if st.session_state.get("highlights"):
        render_pipeline(pipe_placeholder, active_index=3, done=True)
        st.markdown('<hr style="margin: 32px 0; border: none; border-top: 1px solid var(--border);">', unsafe_allow_html=True)

        highlights = st.session_state["highlights"]
        segments = st.session_state.get("segments", [])
        source_path = st.session_state.get("source_path", "")
        video_fps = st.session_state.get("video_fps", 29.97)

        h_cols = st.columns(3)
        for index, highlight in enumerate(highlights):
            with h_cols[index % 3]:
                render_highlight_card(index, highlight, segments, source_path, fps=video_fps)

        st.markdown('<hr style="margin: 32px 0; border: none; border-top: 1px solid var(--border);">', unsafe_allow_html=True)
        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"
        edl_content = st.session_state["edl_content"]

        b64_content = base64.b64encode(edl_content.encode('utf-8')).decode('utf-8')
        href = f"data:text/plain;charset=utf-8;base64,{b64_content}"

        st.markdown(
            f'<div class="h-card dl-wrapper">'
            f'<div style="display: flex; align-items: center; gap: 16px;">'
            f'<div class="download-icon-box">{icon("doc", 24, BRAND)}</div>'
            f'<div>'
            f'<div class="file-name">{html.escape(edl_filename)}</div>'
            f'<div class="file-meta">CMX 3600 Format 타임코드 데이터</div>'
            f'</div>'
            f'</div>'
            f'<a href="{href}" download="{html.escape(edl_filename)}" class="dl-btn">EDL 파일 다운로드</a>'
            f'</div>', 
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
