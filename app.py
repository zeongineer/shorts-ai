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
    "doc": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>'
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
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }}

    .stApp {{ background-color: var(--bg-base); }}
    body, .stApp, p, span, div {{ font-family: 'Noto Sans KR', sans-serif; }}

    .block-container {{
        max-width: 1400px !important;
        margin: 0 auto;
        padding-top: 2rem !important;
    }}

    .app-header {{ display:flex; align-items:center; gap:16px; margin-bottom: 16px; }}
    .app-title-group {{ display:flex; flex-direction:column; gap:4px; }}
    .app-title {{
        font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:1.75rem;
        margin:0; color:var(--text-primary); letter-spacing:-0.5px; line-height:1.2;
    }}
    .app-sub {{ color:var(--text-secondary); font-size:0.95rem; line-height:1.4; margin:0; }}

    .a11y-alert {{
        display:flex; align-items:center; gap:10px;
        border-radius:10px; padding:12px 16px; margin: 16px 0;
        font-size:0.9rem; line-height:1.4; font-weight: 500;
    }}
    .a11y-alert-info {{ background:var(--brand-tint); color:var(--brand-dark); }}
    .a11y-alert-error {{ background:#FEF2F2; border-color:#FECACA; color:#991B1B; border:1px solid; }}

    [data-testid="stFileUploader"] {{
        background-color: var(--bg-base);
        border: 2px dashed #CBD5E1 !important;
        border-radius: 12px !important;
        padding: 16px !important;
    }}

    /* 카드 및 패널 스타일 */
    .panel-card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        box-shadow: var(--shadow-md);
    }}
    
    .panel-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--border);
    }}
    
    .panel-title {{
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
    }}

    /* 테이블 스타일 커스텀 */
    table.custom-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        text-align: left;
    }}
    table.custom-table th {{
        background-color: var(--gray-light);
        color: var(--text-secondary);
        font-weight: 600;
        padding: 10px 8px;
        border-bottom: 1px solid var(--border);
    }}
    table.custom-table td {{
        padding: 10px 8px;
        border-bottom: 1px solid var(--border);
        color: var(--text-primary);
        vertical-align: middle;
    }}

    /* 우측 패널 키-값 스타일 */
    .kv-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        font-size: 0.9rem;
        border-bottom: 1px solid var(--gray-light);
    }}
    .kv-key {{ color: var(--text-secondary); }}
    .kv-val {{ font-weight: 600; color: var(--text-primary); font-family: 'IBM Plex Mono', monospace; }}

    button[kind="primary"] {{
        background-color: #FF5722 !important; /* 이미지의 주황/다홍톤 버튼 반영 */
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 8px !important;
        border: none !important;
        width: 100%;
        margin-top: 12px;
    }}
    button[kind="primary"]:hover {{
        background-color: #E44D1B !important;
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
    icon_html = icon(icon_name, size=18, color=color_map.get(kind, BRAND_DARK)) if icon_name else ""
    st.markdown(
        f'<div class="a11y-alert {css_class}"><span>{icon_html} {message}</span></div>',
        unsafe_allow_html=True,
    )

def render_header() -> None:
    st.markdown(
        '<header class="app-header">'
        '<div class="app-title-group">'
        '<h1 class="app-title">뉴스 주제별 구간 자동 분할기</h1>'
        '<p class="app-sub">미디어 파일을 분석해 주제별 구간을 나누고, 원하는 항목을 선택하여 EDL 파일을 생성합니다.</p>'
        '</div>'
        '</header>',
        unsafe_allow_html=True,
    )

def seconds_to_timecode(seconds: float, fps: float = 29.97) -> str:
    seconds = max(0.0, float(seconds))
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
    edl_lines = ["TITLE: AI_TOPIC_SPLIT_EDL", "FCM: NON-DROP FRAME", ""]
    reel_name = _derive_reel_name(source_filename)
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
        edl_lines.append("")

    return "\n".join(edl_lines)

def get_media_duration(file_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def get_video_fps(file_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        raw = result.stdout.strip()
        if "/" in raw:
            num, den = raw.split("/")
            return float(num) / float(den) if float(den) != 0 else 29.97
        return float(raw) if raw else 29.97
    except Exception:
        return 29.97

def prepare_audio_for_groq(input_file_path: str) -> str:
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()
    cmd = ["ffmpeg", "-y", "-i", input_file_path, "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k", "-f", "mp3", output_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_path

def extract_transcript(groq_client: Groq, file_bytes: bytes, file_name: str) -> list:
    suffix = os.path.splitext(file_name)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        raw_path = tmp.name
    audio_path = prepare_audio_for_groq(raw_path)
    try:
        with open(audio_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="ko",
            )
        return [{"start": round(float(s.get("start", 0)), 2), "end": round(float(s.get("end", 0)), 2), "text": s.get("text", "").strip()} for s in getattr(transcription, "segments", [])]
    finally:
        for p in [raw_path, audio_path]:
            if p and os.path.exists(p):
                os.remove(p)

def run_gemini_topic_splitting(api_key: str, transcript_segments: list, media_duration: float = 0.0) -> list:
    client = genai.Client(api_key=api_key)
    formatted_transcript = "\n".join(f"[{seg['start']:.2f}s ~ {seg['end']:.2f}s] {seg['text']}" for seg in transcript_segments)
    prompt = f"뉴스 자막 전체를 분석하여 독립된 주제별 구간으로 나누고 임팩트 점수(0~100)를 포함해 JSON 배열로 반환해주세요:\n{formatted_transcript}"
    
    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "main_title": {"type": "STRING"},
                    "sub_title": {"type": "STRING"},
                    "start_time": {"type": "NUMBER"},
                    "end_time": {"type": "NUMBER"},
                    "impact_score": {"type": "INTEGER", "description": "임팩트 점수 (70~95 사이)"},
                    "reason": {"type": "STRING", "description": "자막 미리보기 요약"},
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "impact_score", "reason"],
            },
        },
        temperature=0.2,
    )
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=gen_config)
    return json.loads(response.text)

# ==============================================================================
# 4. 메인 애플리케이션 (2분할 레이아웃 적용)
# ==============================================================================
def main():
    render_header()

    gemini_api_key = get_gemini_api_key()
    groq_api_key = get_groq_api_key()
    if not gemini_api_key or not groq_api_key:
        accessible_alert("API Key가 설정되지 않았습니다. .env 또는 Secrets를 확인해주세요.", kind="error", icon_name="alert-triangle")
        return

    groq_client = Groq(api_key=groq_api_key)

    # 상단 파일 업로드 및 분석 트리거
    with st.container():
        uploaded_file = st.file_uploader("미디어 소스 업로드 (mp4, mp3, mov)", type=["mp4", "mp3", "mov"])
        if uploaded_file and "topics" not in st.session_state:
            if st.button("분할 및 구간 분석 시작", type="primary"):
                with st.spinner("AI가 영상을 분석하고 있습니다..."):
                    file_bytes = uploaded_file.read()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                        tmp.write(file_bytes)
                        tmp_path = tmp.name
                    media_duration = get_media_duration(tmp_path)
                    video_fps = get_video_fps(tmp_path)
                    os.remove(tmp_path)

                    segments = extract_transcript(groq_client, file_bytes, uploaded_file.name)
                    topics = run_gemini_topic_splitting(gemini_api_key, segments, media_duration)
                    
                    st.session_state["topics"] = topics
                    st.session_state["video_fps"] = video_fps
                    st.session_state["source_filename"] = uploaded_file.name
                    st.rerun()

    # 데이터가 존재할 경우 가로 2분할 레이아웃 렌더링 (비율 약 7:3)
    if "topics" in st.session_state and st.session_state["topics"]:
        topics = st.session_state["topics"]
        video_fps = st.session_state.get("video_fps", 29.97)
        source_filename = st.session_state.get("source_filename", "source.mp4")

        st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid var(--border);'>", unsafe_allow_html=True)

        # 1. 화면 가로 2분할 (7:3 비율)
        col_left, col_right = st.columns([7, 3], gap="medium")

        # 세션 상태 초기화 (체크박스 제어용)
        for idx in range(len(topics)):
            if f"chk_{idx}" not in st.session_state:
                st.session_state[f"chk_{idx}"] = True

        with col_left:
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            
            # 헤더 영역
            selected_count = sum(1 for i in range(len(topics)) if st.session_state.get(f"chk_{i}", True))
            
            h_col1, h_col2 = st.columns([7, 3])
            with h_col1:
                st.markdown('<p class="panel-title" style="padding-top:6px;">토픽 리스트</p>', unsafe_allow_html=True)
            with h_col2:
                sub_c1, sub_c2 = st.columns([6, 4])
                with sub_c1:
                    st.markdown(f"<span style='font-size:0.85rem; color:var(--text-secondary); line-height:32px;'><b>{selected_count}개</b> 선택됨</span>", unsafe_allow_html=True)
                with sub_c2:
                    if st.button("선택 해제", key="btn_deselect_all"):
                        for i in range(len(topics)):
                            st.session_state[f"chk_{i}"] = False
                        st.rerun()

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

            # 표(Table) 형태로 각 행 렌더링
            table_html = """
            <table class="custom-table">
                <thead>
                    <tr>
                        <th style="width:40px;">#</th>
                        <th style="width:130px;">구간 (IN - OUT)</th>
                        <th style="width:60px;">길이</th>
                        <th style="width:70px;">임팩트 점수</th>
                        <th>추천 제목</th>
                        <th>자막 미리보기</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for index, topic in enumerate(topics):
                start_sec = float(topic.get("start_time", 0.0))
                end_sec = float(topic.get("end_time", 0.0))
                dur = int(round(end_sec - start_sec))
                dur_str = f"00:{dur:02d}" if dur < 60 else f"{dur//60:02d}:{dur%60:02d}"
                
                tc_in = seconds_to_timecode(start_sec, video_fps)[:-3]
                tc_out = seconds_to_timecode(end_sec, video_fps)[:-3]
                
                score = topic.get("impact_score", 80)
                title = html.escape(str(topic.get("main_title", "")))
                preview = html.escape(str(topic.get("reason", "")))

                table_html += f"""
                    <tr>
                        <td><b>{index + 1}</b></td>
                        <td style="font-family:'IBM Plex Mono', monospace; font-size:0.8rem;">{tc_in} - {tc_out}</td>
                        <td style="font-family:'IBM Plex Mono', monospace;">{dur_str}</td>
                        <td style="color:#DC2626; font-weight:700; text-align:center;">{score}</td>
                        <td><b>{title}</b></td>
                        <td style="color:var(--text-secondary);">{preview[:30]}...</td>
                    </tr>
                """
            table_html += "</tbody></table>"
            st.markdown(table_html, unsafe_allow_html=True)

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            
            # Streamlit 체크박스 동기화 배치
            st.markdown("<span style='font-size:0.85rem; color:var(--text-secondary);'>개별 항목 선택/해제 토글</span>", unsafe_allow_html=True)
            chk_cols = st.columns(min(len(topics), 8))
            for i in range(len(topics)):
                col_idx = i % len(chk_cols)
                with chk_cols[col_idx]:
                    st.checkbox(f"{i+1}", key=f"chk_{i}")

            st.markdown('</div>', unsafe_allow_html=True)

        with col_right:
            # 우측 패널 (카드 형태 박스 스타일)
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            st.markdown('<p class="panel-title" style="margin-bottom:16px;">EDL 파일 생성</p>', unsafe_allow_html=True)

            selected_indices = [i for i in range(len(topics)) if st.session_state.get(f"chk_{i}", True)]
            filtered_topics = [topics[i] for i in selected_indices]
            
            total_duration_sec = sum(float(t.get("end_time", 0)) - float(t.get("start_time", 0)) for t in filtered_topics)
            td_min = int(total_duration_sec // 60)
            td_sec = int(total_duration_sec % 60)
            total_running_time = f"{td_min:02d}:{td_sec:02d}"

            # 키-값 형태 정렬 정보
            st.markdown(f"""
                <div class="kv-row">
                    <span class="kv-key">내보낼 항목</span>
                    <span class="kv-val">{len(selected_indices)}개 클립</span>
                </div>
                <div class="kv-row">
                    <span class="kv-key">총 러닝타임(선택분)</span>
                    <span class="kv-val">{total_running_time}</span>
                </div>
                <div class="kv-row">
                    <span class="kv-key">타임코드 형식</span>
                    <span class="kv-val">00:00:00:00 ({int(video_fps)}fps)</span>
                </div>
                <div class="kv-row" style="border-bottom:none;">
                    <span class="kv-key">트랙 매핑</span>
                    <span class="kv-val">V1 / A1</span>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
            
            # 파일명 입력 텍스트 박스
            default_edl_name = f"{os.path.splitext(source_filename)[0]}_highlights.edl"
            custom_filename = st.text_input("파일명", value=default_edl_name, label_visibility="collapsed")
            
            # 안내 박스 (st.info)
            st.info("EDIUS 호환 EDL (CMX 3600) 형식으로 생성됩니다.", icon="ℹ️")

            # 커스텀 버튼 및 다운로드 처리
            if st.button("EDL 파일 생성", type="primary"):
                if not selected_indices:
                    st.error("최소 1개 이상의 클립을 선택해주세요.")
                else:
                    edl_content = generate_edl(filtered_topics, source_filename=source_filename, fps=video_fps)
                    b64 = base64.b64encode(edl_content.encode('utf-8')).decode('utf-8')
                    final_name = custom_filename.strip() or default_edl_name
                    
                    href = f"data:text/plain;charset=utf-8;base64,{b64}"
                    st.markdown(
                        f'<div style="margin-top:12px; text-align:center;">'
                        f'<a href="{href}" download="{html.escape(final_name)}" style="display:block; background:#10B981; color:white; padding:10px; border-radius:8px; text-decoration:none; font-weight:600;">'
                        f'📥 {html.escape(final_name)} 다운로드 링크</a>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
