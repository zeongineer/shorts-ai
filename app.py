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

# 커스텀 CSS 스타일링 (UI 이미지 반영)
st.markdown(
    """
    <style>
    /* 전체 배경 및 폰트 */
    .stApp { background-color: #F8F9FA; }
    
    /* 섹션 컨테이너 (흰색 박스) */
    .section-box {
        background-color: #FFFFFF;
        border: 1px solid #E9ECEF;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* 타이틀 */
    .main-title { font-size: 2rem; font-weight: 800; color: #111827; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 10px; }
    .sub-title { font-size: 1rem; color: #6B7280; margin-bottom: 1.5rem; }
    .section-title { font-size: 1.25rem; font-weight: 700; color: #111827; margin-bottom: 16px; }
    
    /* 안내 박스 */
    .info-box {
        background-color: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-radius: 8px;
        padding: 12px 16px;
        color: #1E40AF;
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 24px;
    }

    /* 파일 업로드 결과 카드 */
    .file-result-card {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px 24px;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        background-color: #FAFAFA;
        height: 100%;
    }
    .file-icon { font-size: 2.5rem; color: #3B82F6; }
    
    /* 가로형 스텝퍼 (진행률) */
    .stepper-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 20px 0;
        gap: 10px;
    }
    .step-item {
        flex: 1;
        text-align: center;
        padding: 16px;
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        position: relative;
        color: #9CA3AF;
        font-weight: 600;
        font-size: 0.9rem;
    }
    /* 스텝 활성화/완료 상태 */
    .step-item.active { border-color: #3B82F6; color: #3B82F6; background: #EFF6FF; }
    .step-item.completed { border-color: #10B981; color: #10B981; }
    .step-number {
        display: inline-block;
        width: 24px; height: 24px;
        line-height: 24px;
        border-radius: 4px;
        background: currentColor;
        color: white;
        margin-right: 6px;
    }
    .step-desc { font-size: 0.8rem; color: #6B7280; margin-top: 6px; font-weight: 400; }
    
    /* 3단 하이라이트 카드 공통 */
    .highlight-card {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 20px;
        height: 100%;
        position: relative;
    }
    .card-title-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px; }
    .card-num { 
        width: 28px; height: 28px; border-radius: 6px; 
        display: flex; align-items: center; justify-content: center; 
        color: white; font-weight: bold; font-size: 1rem; flex-shrink: 0;
    }
    .card-title { font-size: 1.1rem; font-weight: 700; color: #111827; margin: 0; }
    .card-sub { font-size: 0.9rem; color: #6B7280; margin: 4px 0 16px 40px; }
    
    .time-box {
        background-color: #F9FAFB;
        border-radius: 6px;
        padding: 12px;
        font-size: 0.9rem;
        color: #374151;
        margin-bottom: 16px;
    }
    .time-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    
    /* 테마별 색상 (1: 파랑, 2: 초록, 3: 주황) */
    .theme-1 { border-top: 4px solid #3B82F6; }
    .theme-1 .card-num { background-color: #3B82F6; }
    .theme-1 .card-title { color: #1D4ED8; }
    
    .theme-2 { border-top: 4px solid #10B981; }
    .theme-2 .card-num { background-color: #10B981; }
    .theme-2 .card-title { color: #047857; }
    
    .theme-3 { border-top: 4px solid #F59E0B; }
    .theme-3 .card-num { background-color: #F59E0B; }
    .theme-3 .card-title { color: #B45309; }

    /* 다운로드 섹션 하단 박스 */
    .download-box {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px 24px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. UI 렌더링 헬퍼 함수
# ==============================================================================
def render_stepper(current_step: int):
    """가로형 상태 진행바(Stepper) 렌더링"""
    steps = [
        {"title": "파일 처리", "desc": "임시 파일 저장 및<br>오디오 변환(16kHz Mono) 중..."},
        {"title": "STT 추출", "desc": "Groq Whisper AI를 활용한<br>자막 및 타임코드 추출 중..."},
        {"title": "AI 분석", "desc": "Gemini AI 기반 숏폼(30~60초)<br>하이라이트 구간 탐색 중..."},
        {"title": "EDL 생성", "desc": "EDIUS 연동 EDL (CMX 3600)<br>파일 생성 중..."},
    ]
    
    html_parts = ['<div class="stepper-container">']
    for i, step in enumerate(steps, 1):
        status_class = ""
        icon = str(i)
        if i < current_step:
            status_class = "completed"
            icon = "✓"
        elif i == current_step:
            status_class = "active"
            
        html_parts.append(f"""
            <div class="step-item {status_class}">
                <div><span class="step-number">{icon}</span> {step['title']}</div>
                <div class="step-desc">{step['desc']}</div>
            </div>
        """)
    html_parts.append('</div>')
    return "".join(html_parts)

# [이전 코드의 유틸리티, Whisper, 보정, Gemini 함수 부분 동일하게 유지]
def prepare_audio_for_groq(input_file_path: str) -> str:
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()
    cmd = ["ffmpeg", "-y", "-i", input_file_path, "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k", "-f", "mp3", output_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_path

def seconds_to_df_timecode(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_frames = int(round(seconds * 29.97))
    D = total_frames // 17982
    M = total_frames % 17982
    if M >= 2: total_frames += 18 * D + 2 * ((M - 2) // 1798)
    else: total_frames += 18 * D
    frames, total_seconds = total_frames % 30, total_frames // 30
    ss, total_minutes = total_seconds % 60, total_seconds // 60
    mm, hh = total_minutes % 60, total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d};{frames:02d}"

def seconds_to_min_sec(seconds: float) -> str:
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{seconds:02d}"

def get_media_duration(file_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
    return float(result.stdout.strip())

def generate_edl(highlights: list, reel_name: str = "AX0101") -> str:
    edl_lines = ["TITLE: NEWS_SHORTFORM_HIGHLIGHTS", "FMT: NTSC DF", ""]
    for idx, item in enumerate(highlights, 1):
        src_in = seconds_to_df_timecode(float(item.get("start_time", 0.0)))
        src_out = seconds_to_df_timecode(float(item.get("end_time", 0.0)))
        edl_lines.append(f"{idx:03d}  {reel_name:<8} AA/V  C        {src_in} {src_out} {src_in} {src_out}")
        edl_lines.append(f"* FROM CLIP: {item.get('main_title', 'Highlight')}")
        edl_lines.append(f"* COMMENTS: {item.get('sub_title', '')}\n")
    return "\n".join(edl_lines)

def run_whisper_stt(client: Groq, audio_path: str) -> List[Dict[str, Any]]:
    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file.read()), model="whisper-large-v3", response_format="verbose_json", language="ko"
        )
    return [{"start": s.get("start", 0.0), "end": s.get("end", 0.0), "text": s.get("text", "")} for s in getattr(transcription, "segments", [])]

def run_gemini_highlight_extraction(api_key: str, segments: list, media_duration: float) -> list:
    client = genai.Client(api_key=api_key)
    transcript_text = "\n".join([f"[{round(s['start'], 2)}s ~ {round(s['end'], 2)}s] {s['text']}" for s in segments if str(s['text']).strip()])
    prompt = f"뉴스 숏폼 에디터로서 다음 자막에서 30~60초 분량의 하이라이트 3개를 추출하라. 영상 총 길이: {media_duration}초\n\n{transcript_text}"
    gen_config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=gen_config)
    return json.loads(response.text) # 단순화 처리

# ==============================================================================
# 3. 메인 애플리케이션
# ==============================================================================
def main():
    groq_api_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
    gemini_api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    groq_client = Groq(api_key=groq_api_key) if groq_api_key else None

    # 헤더
    st.markdown('<div class="main-title">🎬 뉴스 숏폼 하이라이트 자동 추출기</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">뉴스 음성/영상 파일을 업로드하면 Groq Whisper로 자막과 타임코드를 추출하고,<br>Gemini AI가 30~60초 숏폼 구간 및 자막 타이틀을 자동으로 선정합니다.</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">💡 처리 결과는 EDIUS 영상 편집 프로그램에서 즉시 사용할 수 있는 EDL 파일로 제공됩니다.</div>', unsafe_allow_html=True)

    # 섹션 1: 업로드
    st.markdown('<div class="section-title">1. 뉴스 파일 업로드</div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns([1, 1])
        with col1:
            uploaded_file = st.file_uploader("뉴스 음성 또는 영상 파일을 선택하세요.", type=["mp3", "mp4", "ts", "mov", "wav"], label_visibility="collapsed")
        
        with col2:
            if uploaded_file:
                file_size = uploaded_file.size / (1024 * 1024)
                st.markdown(f"""
                <div class="file-result-card">
                    <div class="file-icon">📄</div>
                    <div>
                        <div style="font-weight: 600; color:#111827;">{html.escape(uploaded_file.name)} <span style="color:#9CA3AF; font-weight:normal;">({file_size:.2f} MB)</span></div>
                        <div style="color: #10B981; font-size: 0.85rem; margin-top: 4px;">✓ 파일 선택 완료</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    if not uploaded_file:
        return

    # 섹션 2: 분석
    st.write("")
    header_col, btn_col = st.columns([3, 1])
    with header_col:
        st.markdown('<div class="section-title">2. 하이라이트 분석</div>', unsafe_allow_html=True)
    with btn_col:
        start_button = st.button("🚀 하이라이트 추출 및 EDL 생성 시작", type="primary", use_container_width=True)

    stepper_placeholder = st.empty()
    stepper_placeholder.markdown(render_stepper(0), unsafe_allow_html=True)

    if start_button:
        try:
            # 1단계: 파일 처리
            stepper_placeholder.markdown(render_stepper(1), unsafe_allow_html=True)
            suffix = "." + uploaded_file.name.split(".")[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                raw_input_path = tmp.name
            media_duration = get_media_duration(raw_input_path)
            processed_audio_path = prepare_audio_for_groq(raw_input_path)

            # 2단계: STT 추출
            stepper_placeholder.markdown(render_stepper(2), unsafe_allow_html=True)
            segments = run_whisper_stt(groq_client, processed_audio_path)

            # 3단계: AI 분석
            stepper_placeholder.markdown(render_stepper(3), unsafe_allow_html=True)
            highlights = run_gemini_highlight_extraction(gemini_api_key, segments, media_duration)

            # 4단계: EDL 생성
            stepper_placeholder.markdown(render_stepper(4), unsafe_allow_html=True)
            edl_content = generate_edl(highlights)

            # 완료 상태
            stepper_placeholder.markdown(render_stepper(5), unsafe_allow_html=True)

            # 섹션 3: 추천 하이라이트 출력 (3단 가로 배치)
            st.write("")
            st.markdown('<div class="section-title">3. 추천 숏폼 하이라이트 (3선)</div>', unsafe_allow_html=True)
            
            card_cols = st.columns(3)
            for idx, (col, hl) in enumerate(zip(card_cols, highlights), 1):
                start_sec, end_sec = float(hl.get("start_time", 0)), float(hl.get("end_time", 0))
                duration = round(end_sec - start_sec, 1)
                
                with col:
                    st.markdown(f"""
                    <div class="highlight-card theme-{idx}">
                        <div class="card-title-row">
                            <div class="card-num">{idx}</div>
                            <h3 class="card-title">{html.escape(hl.get('main_title', ''))}</h3>
                        </div>
                        <p class="card-sub">{html.escape(hl.get('sub_title', ''))}</p>
                        
                        <div class="time-box">
                            <div class="time-row"><span>⏱️</span> {seconds_to_df_timecode(start_sec)} ~ {seconds_to_df_timecode(end_sec)}</div>
                            <div class="time-row"><span>⏳</span> {seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)} <span style="color:#6B7280">({duration}초)</span></div>
                        </div>
                        <div style="font-size: 0.9rem; color:#4B5563;">
                            <strong>💡 선정 이유:</strong> {html.escape(hl.get('reason', ''))}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # 섹션 4: 다운로드
            st.write("")
            st.markdown('<div class="section-title">4. EDIUS 연동 파일 다운로드</div>', unsafe_allow_html=True)
            
            edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"
            dl_col1, dl_col2 = st.columns([3, 1])
            
            with dl_col1:
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:12px; padding:10px 0;">
                    <div style="font-size:2rem; color:#3B82F6;">📄</div>
                    <div>
                        <div style="font-weight:bold; color:#111827;">{edl_filename}</div>
                        <div style="font-size:0.85rem; color:#6B7280;">EDIUS용 EDL 파일 (CMX 3600 Format)</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with dl_col2:
                st.download_button("📥 EDIUS용 EDL 파일 다운로드", data=edl_content, file_name=edl_filename, mime="text/plain", use_container_width=True)

        except Exception as e:
            st.error(f"오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main()
