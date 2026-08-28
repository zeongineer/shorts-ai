import html
import os
import subprocess
import tempfile
import base64
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
}

def icon(name: str, size: int = 16, color: str = "currentColor", stroke_width: float = 2) -> str:
    path = _ICON_PATHS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;flex-shrink:0;">{path}</svg>'
    )

CARD_THEMES = [
    {"class": "c-brand", "icon": "doc"},
    {"class": "c-brand", "icon": "mic"},
    {"class": "c-brand", "icon": "chart"},
]

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
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }}

    .stApp {{ background-color: var(--bg-base); }}
    body, .stApp, p, span, div {{ font-family: 'Noto Sans KR', sans-serif; }}

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

    .section-title {{
        font-size:1.15rem; font-weight:700; margin: 36px 0 16px; color:var(--text-primary);
        letter-spacing:-0.3px; display: flex; align-items: center; gap: 8px;
    }}

    [data-testid="stFileUploaderDropzone"] {{
        background: var(--surface) !important;
        border: 2px dashed #CBD5E1 !important;
        border-radius: 12px !important;
        transition: all 0.2s ease;
    }}
    [data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--brand) !important; }}
    [data-testid="stFileUploaderFile"] {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        box-shadow: var(--shadow-sm) !important;
    }}
    [data-testid="stFileUploaderFileName"] {{ font-weight:600 !important; color:var(--text-primary) !important; }}

    .pipe-card {{
        background:var(--surface); border:1px solid var(--border); border-radius:12px;
        padding:20px 24px; box-shadow: var(--shadow-sm);
        display:flex; flex-direction:column; gap:12px;
        transition: all 0.2s ease;
        justify-content: center;
        min-height: 80px; 
    }}
    .pipe-card.active {{ border-color:var(--brand); box-shadow: 0 0 0 2px var(--brand-tint), var(--shadow-md); }}
    .pipe-title {{ display:flex; align-items:center; gap:10px; font-size:1rem; font-weight:700; color:var(--text-primary); }}
    .pipe-status {{ display:flex; align-items:center; gap:6px; font-size:0.85rem; font-weight:600; margin-top: 4px; }}
    .pipe-status.done {{ color:var(--green); }}
    .pipe-status.active {{ color:var(--brand); }}
    .pipe-status.pending {{ color:#94A3B8; }}

    .h-card {{
        background:var(--surface); border:1px solid var(--border); border-radius:12px;
        padding:24px; box-shadow: var(--shadow-sm);
        display:flex; flex-direction:column; gap:12px;
    }}
    .h-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px; }}
    .h-card h3 {{ font-size:1.1rem; margin:0; line-height:1.4; color:var(--text-primary); font-weight:700; }}
    .h-row {{
        display:flex; align-items:center; gap:8px; font-family:'IBM Plex Mono', monospace;
        font-size:0.85rem; color:var(--text-secondary);
    }}
    .h-reason {{
        margin-top:auto; background:var(--bg-base); border-radius:10px;
        padding:16px 20px; font-size:0.85rem; color:var(--text-secondary); line-height:1.65;
        border: 1px solid var(--border);
    }}
    .h-reason b {{ color:var(--text-primary); display:block; margin-bottom:4px; }}
    .c-brand .step-num {{ background:var(--brand); }}

    .dl-wrapper {{
        flex-direction: row; 
        align-items: center; 
        justify-content: space-between;
    }}
    .download-icon-box {{
        width:48px; height:48px; border-radius:10px; background:var(--brand-tint); color:var(--brand);
        display:flex; align-items:center; justify-content:center; flex-shrink:0;
    }}
    .file-name {{ font-weight:700; font-size:1rem; color:var(--text-primary); margin-bottom:2px; }}
    .file-meta {{ color:var(--text-secondary); font-size:0.85rem; }}
    
    .dl-btn {{
        background-color: var(--brand);
        color: #FFFFFF !important;
        font-weight: 600; font-size: 0.95rem;
        padding: 0.6rem 1.5rem;
        border-radius: 8px;
        text-decoration: none !important;
        display: inline-block;
        box-shadow: 0 2px 4px rgba(28,157,233,0.2);
        transition: all 0.2s ease;
        border: 1px solid var(--brand);
    }}
    .dl-btn:hover {{
        background-color: var(--brand-dark);
        border-color: var(--brand-dark);
        box-shadow: 0 4px 12px rgba(28,157,233,0.3);
        transform: translateY(-1px);
        text-decoration: none !important;
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
        '<p class="app-sub">뉴스 미디어 파일을 업로드하면 Whisper AI로 자막을 추출하고, Gemini가 가장 임팩트 있는 숏폼 구간을 자동 선정합니다.</p>'
        '</div>'
        '</header>',
        unsafe_allow_html=True,
    )
    accessible_alert("처리 완료 시 편집기(EDIUS)에 즉시 임포트 가능한 타임코드 EDL 파일이 제공됩니다.", kind="info", icon_name="bulb")

# ==============================================================================
# 4. 파이프라인 및 방송 데이터 포맷팅
# ==============================================================================
PIPELINE_STEPS = [
    {"title": "미디어 전처리", "desc": "16kHz Mono 오디오 최적화 및 임시 파일 생성"},
    {"title": "음성 인식 (STT)", "desc": "Groq Whisper를 활용한 정밀 텍스트 및 타임코드 추출"},
    {"title": "AI 숏폼 분석", "desc": "Gemini AI 기반 핵심 문맥 파악 및 30~60초 하이라이트 선정"},
    {"title": "EDL 패키징", "desc": "선정된 데이터 기반 CMX 3600 표준 EDL 포맷 렌더링"},
]

def render_pipeline(placeholders: list, active_index: int, done: bool = False) -> None:
    for i, ph in enumerate(placeholders):
        step = PIPELINE_STEPS[i]
        if done or i < active_index:
            card_class, status_html = "", f'<div class="pipe-status done">{icon("check", 14, "currentColor", 2.5)} 완료</div>'
        elif i == active_index:
            card_class, status_html = "active", f'<div class="pipe-status active">{icon("dot", 14, "currentColor", 2)} 진행 중</div>'
        else:
            card_class, status_html = "", f'<div class="pipe-status pending">{icon("circle", 14, "currentColor", 2)} 대기 중</div>'

        ph.markdown(f"""
            <div class="pipe-card {card_class}">
                <div class="pipe-title">{step['title']}</div>
                {status_html}
            </div>
            """, unsafe_allow_html=True)

# 방송 표준 시:분:초:프레임 (HH:MM:SS:FF) 변환기 - 29.97/30fps NDF 기준
def seconds_to_timecode(seconds: float, fps: int = 30) -> str:
    total_frames = int(round(seconds * fps))
    hh = total_frames // (3600 * fps)
    mm = (total_frames % (3600 * fps)) // (60 * fps)
    ss = (total_frames % (60 * fps)) // fps
    ff = total_frames % fps
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

def seconds_to_min_sec(seconds: float) -> str:
    minutes, secs = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{secs:02d}"

# 하이라이트 배열을 순회하여 실제 CMX 3600 EDL 라인 생성
def generate_edl(highlights: list, reel_name: str = "AX0101") -> str:
    edl_lines = ["TITLE: MOCK_EDL", "FCM: NON-DROP FRAME"]
    
    for i, hl in enumerate(highlights):
        start_tc = seconds_to_timecode(hl.get("start_time", 0.0))
        end_tc = seconds_to_timecode(hl.get("end_time", 0.0))
        
        event_num = f"{(i+1):03d}"
        # CMX 3600 형식: 이벤트번호 | 릴이름 | 트랙 | 트랜지션 | 소스IN | 소스OUT | 레코드IN | 레코드OUT
        line1 = f"{event_num}  {reel_name:<8} V     C        {start_tc} {end_tc} {start_tc} {end_tc}"
        line2 = f"* FROM CLIP NAME: {hl.get('main_title', 'Unknown')}"
        
        edl_lines.extend([line1, line2])
        
    return "\n".join(edl_lines) + "\n"

def run_gemini_highlight_extraction(api_key: str, segments: list, media_duration: float = 0.0) -> list:
    return [ 
        {"main_title": "누리호 발사", "sub_title": "우주 과학 이슈", "start_time": 10.5, "end_time": 45.0, "reason": "발사 성공의 역사적 순간을 잘 포착했습니다."},
        {"main_title": "가을 태풍", "sub_title": "기상 정보", "start_time": 120.0, "end_time": 155.5, "reason": "높은 대중적 관심도를 끌어낼 수 있습니다."},
        {"main_title": "성과급 부결", "sub_title": "경제 이슈", "start_time": 210.0, "end_time": 250.0, "reason": "원인과 배경을 명확하게 설명하고 있습니다."}
    ]

# ==============================================================================
# 5. 하이라이트 카드 렌더링
# ==============================================================================
def render_highlight_card(index: int, highlight: dict) -> None:
    theme = CARD_THEMES[index % len(CARD_THEMES)]
    start_sec = float(highlight.get("start_time", 0.0))
    end_sec = float(highlight.get("end_time", 0.0))
    duration = round(end_sec - start_sec, 1)

    title = html.escape(str(highlight.get("main_title", f"하이라이트 {index + 1}")))
    reason = html.escape(str(highlight.get("reason", "-")))

    st.markdown(
        f"""
        <article class="h-card {theme['class']}" style="height:100%;">
            <div class="h-top">
                <span class="step-num">{index + 1}</span>
            </div>
            <h3>{title}</h3>
            <div class="h-row">{icon('clock', 14, 'currentColor')} {seconds_to_timecode(start_sec)} ~ {seconds_to_timecode(end_sec)}</div>
            <div class="h-row">{icon('timer', 14, 'currentColor')} {seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)} ({duration}초)</div>
            <div class="h-reason"><b>선정 이유</b>{reason}</div>
        </article>
        """,
        unsafe_allow_html=True,
    )

# ==============================================================================
# 6. 메인 애플리케이션
# ==============================================================================
def main():
    render_header()

    st.markdown('<div class="section-title">📁 뉴스 파일 업로드</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("파일 업로드", type=["mp4", "mp3", "mov"], label_visibility="collapsed")

    if not uploaded_file:
        return

    st.markdown('<div class="section-title">🔍 하이라이트 분석</div>', unsafe_allow_html=True)
    
    start_button = st.button("추출 및 EDL 생성 시작", type="primary", use_container_width=True)

    pipe_cols = st.columns(4)
    pipe_placeholders = [c.empty() for c in pipe_cols]
    render_pipeline(pipe_placeholders, active_index=-1)

    if not start_button:
        return

    try:
        render_pipeline(pipe_placeholders, active_index=0)
        render_pipeline(pipe_placeholders, active_index=1)
        render_pipeline(pipe_placeholders, active_index=2)
        
        highlights = run_gemini_highlight_extraction("mock_key", [])
        
        render_pipeline(pipe_placeholders, active_index=3)
        edl_content = generate_edl(highlights)
        render_pipeline(pipe_placeholders, active_index=3, done=True)

        st.markdown('<div class="section-title">✨ 추천 숏폼 하이라이트 (3선)</div>', unsafe_allow_html=True)

        h_cols = st.columns(3)
        for index, highlight in enumerate(highlights):
            with h_cols[index % 3]:
                render_highlight_card(index, highlight)

        st.markdown('<div class="section-title">💾 EDIUS 연동 파일 다운로드</div>', unsafe_allow_html=True)
        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"

        b64_content = base64.b64encode(edl_content.encode('utf-8')).decode('utf-8')
        href = f"data:text/plain;charset=utf-8;base64,{b64_content}"

        st.markdown(f"""
            <div class="h-card dl-wrapper">
                <div style="display: flex; align-items: center; gap: 16px;">
                    <div class="download-icon-box">{icon('doc', 24, BRAND)}</div>
                    <div>
                        <div class="file-name">{html.escape(edl_filename)}</div>
                        <div class="file-meta">CMX 3600 Format 타임코드 데이터</div>
                    </div>
                </div>
                <a href="{href}" download="{html.escape(edl_filename)}" class="dl-btn">
                    EDL 파일 다운로드
                </a>
            </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        accessible_alert("처리 중 문제가 발생했습니다. 미디어 파일을 확인해주세요.", kind="error", icon_name="x-circle")

if __name__ == "__main__":
    main()
