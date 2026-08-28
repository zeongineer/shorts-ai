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

BRAND = "#1C9DE9"
BRAND_DARK = "#0E7FC4"
BRAND_TINT = "#EAF6FE"

# ==============================================================================
# 2. 아이콘 (SVG, Lucide 스타일) - OS 이모지 대신 사용해 플랫폼 간 일관성 확보
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
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "doc": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "mic": '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>',
    "chart": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "video": '<path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "timer": '<line x1="10" y1="2" x2="14" y2="2"/><line x1="12" y1="14" x2="15" y2="11"/><circle cx="12" cy="14" r="8"/>',
}


def icon(name: str, size: int = 16, color: str = "currentColor", stroke_width: float = 2) -> str:
    path = _ICON_PATHS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;flex-shrink:0;">{path}</svg>'
    )


# 카드 컬러 로테이션 (하이라이트 3선을 한눈에 구분하기 위한 색/아이콘 세트)
CARD_THEMES = [
    {"class": "c-blue", "icon": "doc"},
    {"class": "c-green", "icon": "mic"},
    {"class": "c-amber", "icon": "chart"},
]

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Noto+Sans+KR:wght@400;500;700;900&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root{{
        --brand:{BRAND};
        --brand-dark:{BRAND_DARK};
        --brand-tint:{BRAND_TINT};
        --bg-base:#F4F6F8;
        --surface:#FFFFFF;
        --border:#E1E5EA;
        --text-primary:#10161D;
        --text-secondary:#5B6570;
        --green:#1F9D6B;
        --green-tint:#E8F7F0;
        --amber:#B8790E;
        --amber-tint:#FDF3E2;
        --shadow-sm: 0 1px 3px rgba(16,22,29,0.06);
        --shadow-md: 0 4px 14px rgba(16,22,29,0.08);
    }}

    .stApp {{ background-color: var(--bg-base); }}
    body, .stApp, p, span, div {{ font-family: 'Noto Sans KR', sans-serif; }}

    /* 헤더 */
    .app-header {{ display:flex; align-items:flex-start; gap:14px; margin-bottom: 4px; }}
    .app-logo {{
        width:40px; height:40px; border-radius:10px; background:var(--brand);
        display:flex; align-items:center; justify-content:center; flex-shrink:0;
        box-shadow: var(--shadow-sm);
    }}
    .app-title {{
        font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:1.6rem;
        margin:0 0 8px; color:#0B0F14;
    }}
    .app-sub {{ color:var(--text-secondary); font-size:0.93rem; line-height:1.75; margin:0; }}

    /* 알림 배너 */
    .a11y-alert {{
        display:flex; align-items:center; gap:9px;
        border-radius:9px; padding:13px 16px; margin: 18px 0 4px;
        font-size:0.9rem; line-height:1.5; border:1px solid transparent;
    }}
    .a11y-alert-info {{ background:var(--brand-tint); border-color:#BFE1FA; color:var(--brand-dark); }}
    .a11y-alert-success {{ background:var(--green-tint); border-color:#BFE9D6; color:#0F5C3E; }}
    .a11y-alert-error {{ background:#FDEDEC; border-color:#F5C6C2; color:#8A2E27; }}

    /* 섹션 타이틀 */
    .section-title {{
        display:flex; align-items:center; gap:8px;
        font-size:1.05rem; font-weight:700; margin: 30px 0 14px; color:var(--text-primary);
    }}

    /* 업로드: 파일 선택 확인 라인 (카드 중복 제거, 단일 확인 문구만 사용) */
    .file-confirm {{
        display:flex; align-items:center; gap:10px;
        margin-top: 12px; padding: 10px 4px;
    }}
    .file-confirm .name {{ font-weight:700; color:var(--text-primary); font-size:0.9rem; }}
    .file-confirm .meta {{ color:var(--text-secondary); font-size:0.8rem; margin-left:4px; }}
    .file-confirm .ok {{ color:var(--green); font-weight:600; font-size:0.85rem; display:flex; align-items:center; gap:5px; margin-left:auto; }}

    /* Streamlit 파일 업로더 내부 요소 재스타일링 (단일 디자인 시스템으로 통일) */
    [data-testid="stFileUploaderDropzone"] {{
        background: var(--surface) !important;
        border: 1.5px dashed #C7CDD5 !important;
        border-radius: 12px !important;
        padding: 6px !important;
    }}
    [data-testid="stFileUploaderFile"] {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        box-shadow: var(--shadow-sm) !important;
        margin-top: 6px !important;
    }}
    [data-testid="stFileUploaderFileName"] {{ font-weight:600 !important; color:var(--text-primary) !important; }}

    /* 파이프라인 카드 */
    .pipe-card {{
        background:var(--surface); border:1px solid var(--border); border-radius:12px;
        padding:20px; min-height:128px; box-shadow: var(--shadow-sm);
        display:flex; flex-direction:column; gap:10px;
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
    }}
    .pipe-card.active {{ border-color:var(--brand); box-shadow: 0 0 0 3px var(--brand-tint), var(--shadow-md); }}
    .pipe-title {{ display:flex; align-items:center; gap:9px; font-size:0.9rem; font-weight:700; color:var(--text-primary); }}
    .step-num {{
        display:inline-flex; align-items:center; justify-content:center;
        width:22px; height:22px; border-radius:50%; color:#fff;
        font-size:11.5px; font-weight:700; flex-shrink:0;
    }}
    .pipe-desc {{ font-size:0.79rem; color:var(--text-secondary); line-height:1.6; flex:1; }}
    .pipe-status {{ display:flex; align-items:center; gap:6px; font-size:0.8rem; font-weight:600; }}
    .pipe-status.done {{ color:var(--green); }}
    .pipe-status.active {{ color:var(--brand); }}
    .pipe-status.pending {{ color:#AEB6C2; }}

    /* 하이라이트 카드 */
    .h-card {{
        background:var(--surface); border:1px solid var(--border); border-radius:12px;
        padding:20px; height:100%; box-shadow: var(--shadow-sm);
        display:flex; flex-direction:column; gap:10px;
    }}
    .h-top {{ display:flex; justify-content:space-between; align-items:center; }}
    .h-icon {{ width:32px; height:32px; border-radius:9px; display:flex; align-items:center; justify-content:center; }}
    .h-card h3 {{ font-size:1rem; margin:0; line-height:1.45; color:var(--text-primary); }}
    .h-row {{
        display:flex; align-items:center; gap:8px; font-family:'IBM Plex Mono', monospace;
        font-size:0.8rem; color:var(--text-secondary);
    }}
    .h-reason {{
        margin-top:2px; background:var(--bg-base); border-radius:8px;
        padding:11px 12px; font-size:0.79rem; color:var(--text-secondary); line-height:1.6;
    }}
    .h-reason b {{ color:var(--text-primary); }}
    .c-blue .h-icon {{ background:var(--brand-tint); color:var(--brand); }}
    .c-blue .step-num {{ background:var(--brand); }}
    .c-green .h-icon {{ background:var(--green-tint); color:var(--green); }}
    .c-green .step-num {{ background:var(--green); }}
    .c-amber .h-icon {{ background:var(--amber-tint); color:var(--amber); }}
    .c-amber .step-num {{ background:var(--amber); }}

    /* 다운로드 행 */
    .download-row {{
        background:var(--surface); border:1px solid var(--border); border-radius:12px;
        padding:18px 20px; display:flex; align-items:center; gap:14px;
        box-shadow: var(--shadow-sm); height:100%;
    }}
    .download-row .file-icon-box {{
        width:40px; height:40px; border-radius:9px; background:var(--brand-tint); color:var(--brand);
        display:flex; align-items:center; justify-content:center; flex-shrink:0;
    }}
    .download-row .file-name {{ font-weight:700; font-size:0.92rem; color:var(--text-primary); }}
    .download-row .file-meta {{ color:var(--text-secondary); font-size:0.79rem; }}

    /* Streamlit 버튼 (브랜드 컬러 + 여백/그림자/호버) */
    div.stButton > button[kind="primary"], div.stDownloadButton > button {{
        background-color: var(--brand) !important;
        border-color: var(--brand) !important;
        font-weight:700 !important;
        padding: 0.7rem 1.4rem !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 8px rgba(28,157,233,0.28) !important;
        transition: all 0.15s ease !important;
    }}
    div.stButton > button[kind="primary"]:hover, div.stDownloadButton > button:hover {{
        background-color: var(--brand-dark) !important;
        border-color: var(--brand-dark) !important;
        box-shadow: 0 4px 12px rgba(28,157,233,0.36) !important;
        transform: translateY(-1px);
    }}

    /* 포커스 링 */
    .focusable-heading {{ margin-top: 1rem; margin-bottom: 1rem; padding: 4px 8px; border-radius: 6px; color: var(--text-primary); }}
    .focusable-heading:focus, .focusable-heading:focus-visible {{
        outline: 3px solid var(--brand) !important; outline-offset: 3px !important;
    }}
    .sr-only {{
        position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
        overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 3. 접근성 유틸리티
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


def accessible_alert(message: str, kind: str = "info", icon_name: str = "") -> None:
    """접근성 준수 알림 박스 (aria-live 명시)"""
    css_class = {
        "info": "a11y-alert-info",
        "success": "a11y-alert-success",
        "error": "a11y-alert-error",
    }.get(kind, "a11y-alert-info")

    color_map = {"info": BRAND_DARK, "success": "#0F5C3E", "error": "#8A2E27"}

    if kind == "error":
        role = "alert"
        aria_live = "assertive"
    else:
        role = "status"
        aria_live = "polite"

    icon_html = icon(icon_name, size=16, color=color_map.get(kind, BRAND_DARK)) if icon_name else ""

    st.markdown(
        f'<div class="a11y-alert {css_class}" role="{role}" aria-live="{aria_live}">{icon_html}<span>{message}</span></div>',
        unsafe_allow_html=True,
    )


# ==============================================================================
# 4. 헤더 UI
# ==============================================================================
def render_header() -> None:
    set_page_language("ko")
    st.markdown(
        '<header class="app-header" role="banner">'
        f'<div class="app-logo" aria-hidden="true">{icon("film", size=20, color="#fff", stroke_width=2.2)}</div>'
        '<div>'
        '<h1 class="app-title">뉴스 숏폼 하이라이트 자동 추출기</h1>'
        '<p class="app-sub">뉴스 음성/영상 파일을 업로드하면 Groq Whisper로 자막과 타임코드를 추출하고, '
        'Gemini AI가 30~60초 숏폼 구간 및 자막 타이틀을 자동으로 선정합니다.</p>'
        '</div>'
        '</header>',
        unsafe_allow_html=True,
    )
    accessible_alert(
        "처리 결과는 EDIUS 영상 편집 프로그램에서 즉시 사용할 수 있는 EDL 파일로 제공됩니다.",
        kind="info",
        icon_name="bulb",
    )


# ==============================================================================
# 5. 파이프라인 스텝 카드 렌더링
# ==============================================================================
PIPELINE_STEPS = [
    {"title": "파일 처리", "desc": "임시 파일 저장 및 오디오 변환(16kHz Mono) 중..."},
    {"title": "STT 추출", "desc": "Groq Whisper AI를 활용한 자막 및 타임코드 추출 중..."},
    {"title": "AI 분석", "desc": "Gemini AI 기반 숏폼(30~60초) 하이라이트 구간 탐색 중..."},
    {"title": "EDL 생성", "desc": "EDIUS 연동 EDL (CMX 3600) 파일 생성 중..."},
]


def render_pipeline_step_html(index: int, status: str) -> str:
    """status: 'pending' | 'active' | 'done'"""
    step = PIPELINE_STEPS[index]
    num = index + 1

    if status == "done":
        card_class = ""
        num_bg = "#10161D"
        status_html = f'<div class="pipe-status done">{icon("check", 13, "currentColor", 2.5)} 완료</div>'
    elif status == "active":
        card_class = "active"
        num_bg = BRAND
        status_html = f'<div class="pipe-status active">{icon("dot", 13, "currentColor", 2)} 진행 중</div>'
    else:
        card_class = ""
        num_bg = "#C7CDD5"
        status_html = f'<div class="pipe-status pending">{icon("circle", 13, "currentColor", 2)} 대기 중</div>'

    return f"""
    <div class="pipe-card {card_class}">
        <div class="pipe-title"><span class="step-num" style="background:{num_bg};">{num}</span>{step['title']}</div>
        <div class="pipe-desc">{step['desc']}</div>
        {status_html}
    </div>
    """


def render_pipeline(placeholders: list, active_index: int, done: bool = False) -> None:
    """active_index: 현재 진행 중인 스텝(0-based). -1이면 전체 대기 상태. done=True면 전체 완료 표시."""
    for i, ph in enumerate(placeholders):
        if done or i < active_index:
            status = "done"
        elif i == active_index:
            status = "active"
        else:
            status = "pending"
        ph.markdown(render_pipeline_step_html(i, status), unsafe_allow_html=True)


# ==============================================================================
# 6. 유틸리티 함수 (미디어 처리 / 타임코드 / EDL)
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
# 7. Whisper STT
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
# 8. 데이터 보정
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
# 9. Gemini 하이라이트 추출
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
# 10. API 키 가져오기
# ==============================================================================
def get_api_keys():
    groq_api_key = st.secrets.get("GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
    gemini_api_key = st.secrets.get("GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    return groq_api_key, gemini_api_key


# ==============================================================================
# 11. 하이라이트 카드 렌더링
# ==============================================================================
def render_highlight_card(index: int, highlight: dict) -> None:
    theme = CARD_THEMES[index % len(CARD_THEMES)]
    start_sec = float(highlight.get("start_time", 0.0))
    end_sec = float(highlight.get("end_time", 0.0))
    duration = round(end_sec - start_sec, 1)

    title = html.escape(str(highlight.get("main_title", f"하이라이트 {index + 1}")))
    reason = html.escape(str(highlight.get("reason", "-")))

    icon_color = {"c-blue": BRAND, "c-green": "#1F9D6B", "c-amber": "#B8790E"}[theme["class"]]

    st.markdown(
        f"""
        <article class="h-card {theme['class']}" aria-labelledby="card-title-{index}">
            <div class="h-top">
                <span class="step-num">{index + 1}</span>
                <div class="h-icon" aria-hidden="true">{icon(theme['icon'], 16, icon_color)}</div>
            </div>
            <h3 id="card-title-{index}">{title}</h3>
            <div class="h-row">{icon('clock', 13, 'currentColor')} {seconds_to_df_timecode(start_sec)} ~ {seconds_to_df_timecode(end_sec)}</div>
            <div class="h-row">{icon('timer', 13, 'currentColor')} {seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)} ({duration}초)</div>
            <div class="h-reason"><b>선정 이유</b> — {reason}</div>
        </article>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# 12. 메인 애플리케이션
# ==============================================================================
def main():
    groq_api_key, gemini_api_key = get_api_keys()

    render_header()

    if not groq_api_key or not gemini_api_key:
        accessible_alert("API 키가 설정되지 않았습니다.", kind="error", icon_name="alert-triangle")
        accessible_alert(
            "환경 변수 또는 Streamlit Secrets에 GROQ_API_KEY와 GEMINI_API_KEY를 설정해 주세요.",
            kind="info",
            icon_name="bulb",
        )
        st.stop()

    groq_client = Groq(api_key=groq_api_key)

    st.markdown(
        f'<div class="section-title">1. 뉴스 파일 업로드</div>',
        unsafe_allow_html=True,
    )

    # 단일 디자인 시스템: 드롭존 하나만 사용하고, 업로드된 파일은
    # Streamlit 기본 컴포넌트를 브랜드 스타일로 재적용해 그대로 노출한다.
    # (별도의 중복 카드를 만들지 않아 비대칭/중복 문제를 제거)
    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 선택하세요.",
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"],
        help="MP3, MP4, TS, MOV 등 다양한 방송 미디어 포맷을 지원합니다.",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        safe_filename = html.escape(uploaded_file.name)
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.markdown(
            f"""
            <div class="file-confirm">
                <span class="name">{safe_filename}</span>
                <span class="meta">{file_size_mb:.2f} MB</span>
                <span class="ok">{icon('check-circle', 15, '#1F9D6B')} 파일 선택 완료</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if uploaded_file is None:
        return

    if uploaded_file.size > (1024 * 1024 * 1024):
        accessible_alert("파일 크기가 1GB를 초과합니다. 1GB 이하의 파일을 업로드해 주세요.", kind="error", icon_name="alert-triangle")
        return

    st.markdown('<div class="section-title">2. 하이라이트 분석</div>', unsafe_allow_html=True)
    start_button = st.button("하이라이트 추출 및 EDL 생성 시작", type="primary", use_container_width=True)

    pipe_cols = st.columns(4)
    pipe_placeholders = [c.empty() for c in pipe_cols]
    # 버튼을 누르기 전에는 4단계 모두 '대기 중' 상태여야 한다 (이전 버전의 오류 수정 지점)
    render_pipeline(pipe_placeholders, active_index=-1)

    if not start_button:
        return

    raw_input_path = None
    processed_audio_path = None

    try:
        render_pipeline(pipe_placeholders, active_index=0)
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
        render_pipeline(pipe_placeholders, active_index=1)

        segments = run_whisper_stt(groq_client, processed_audio_path)

        if not segments:
            raise RuntimeError("음성에서 자막을 추출하지 못했습니다. 오디오 트랙을 확인해주세요.")

        render_pipeline(pipe_placeholders, active_index=2)
        highlights = run_gemini_highlight_extraction(gemini_api_key, segments, media_duration)

        render_pipeline(pipe_placeholders, active_index=3)
        edl_content = generate_edl(highlights)

        render_pipeline(pipe_placeholders, active_index=3, done=True)

        st.markdown(
            '<div class="sr-only" role="status" aria-live="polite">'
            '분석이 완료되었습니다. 추천 숏폼 하이라이트 3건이 아래에 표시됩니다.'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<h2 id="results-heading" class="focusable-heading section-title" tabindex="-1">3. 추천 숏폼 하이라이트 (3선)</h2>',
            unsafe_allow_html=True,
        )
        focus_element_by_id("results-heading")

        h_cols = st.columns(3)
        for index, highlight in enumerate(highlights):
            with h_cols[index % 3]:
                render_highlight_card(index, highlight)

        st.markdown('<div class="section-title">4. EDIUS 연동 파일 다운로드</div>', unsafe_allow_html=True)

        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"

        col_info, col_btn = st.columns([2, 1])
        with col_info:
            st.markdown(
                f"""
                <div class="download-row">
                    <div class="file-icon-box" aria-hidden="true">{icon('doc', 18, BRAND)}</div>
                    <div>
                        <div class="file-name">{html.escape(edl_filename)}</div>
                        <div class="file-meta">EDIUS용 EDL 파일 (CMX 3600 Format)</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_btn:
            st.download_button(
                label="EDIUS용 EDL 파일 다운로드",
                data=edl_content,
                file_name=edl_filename,
                mime="text/plain",
                use_container_width=True,
            )

    except Exception as error:
        accessible_alert("처리 중 오류가 발생했습니다.", kind="error", icon_name="x-circle")
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
