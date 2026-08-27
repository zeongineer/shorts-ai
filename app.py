import os
import re
import tempfile
import json
from dotenv import load_dotenv
import streamlit as st
from groq import Groq
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# ==============================================================================
# 1. 초기 환경 설정 및 페이지 레이아웃
# ==============================================================================
load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------------------------
# 다크 모드 전문 편집 툴 UI 스타일링 (CSS)
# ------------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
    :root {
        --bg-primary: #0F172A;
        --bg-secondary: #1E293B;
        --bg-card: #182234;
        --accent-color: #10B981;
        --accent-hover: #059669;
        --text-primary: #F8FAFC;
        --text-secondary: #94A3B8;
        --border-color: #334155;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background-color: var(--bg-primary);
        color: var(--text-primary);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    h1 {
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: #F8FAFC !important;
        padding-bottom: 0.5rem;
    }

    .stMarkdown p {
        color: var(--text-secondary);
        font-size: 0.95rem;
        line-height: 1.6;
    }

    div[data-testid="stForm"], 
    div[data-testid="stExpander"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }

    section[data-testid="stFileUploadDropzone"] {
        background-color: var(--bg-secondary) !important;
        border: 2px dashed var(--border-color) !important;
        border-radius: 8px !important;
        transition: all 0.2s ease;
    }
    section[data-testid="stFileUploadDropzone"]:hover {
        border-color: var(--accent-color) !important;
    }

    .stButton > button {
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button[kind="primary"] {
        background-color: var(--accent-color) !important;
        border: none !important;
        color: #FFFFFF !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--accent-hover) !important;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
    }

    div[data-testid="stDownloadButton"] > button {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #1D4ED8 !important;
        box-shadow: 0 0 12px rgba(37, 99, 235, 0.4);
    }

    .streamlit-expanderHeader {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
    }

    div[data-testid="stStatusWidget"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
    }

    .stAlert {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        color: var(--text-primary) !important;
        border-radius: 6px !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==============================================================================
# 2. 데이터 구조 및 유틸리티 함수 (타임코드 및 EDL 생성)
# ==============================================================================
class HighlightItem(BaseModel):
    title: str = Field(description="하이라이트 구간의 핵심 요약 제목")
    start_time: float = Field(description="시작 시간(초 단위)")
    end_time: float = Field(description="종료 시간(초 단위)")
    reason: str = Field(description="해당 구간을 선택한 이유")

class HighlightResponse(BaseModel):
    highlights: list[HighlightItem]


def seconds_to_df_timecode(seconds: float, fps: float = 29.97) -> str:
    """초 단위 시간을 29.97 Drop-Frame 타임코드(HH:MM:SS;FF) 형태로 변환합니다."""
    total_frames = int(round(seconds * fps))

    # Drop frame 규칙 계산 (29.97 fps)
    frames_per_10min = int(round(10 * 60 * fps))  # 17982
    frames_per_min = int(round(60 * fps - 2))     # 1798
    
    d = total_frames // frames_per_10min
    m = total_frames % frames_per_10min

    if m >= 2:
        total_frames += 18 * d + 2 * ((m - 2) // frames_per_min)
    else:
        total_frames += 18 * d

    frames = total_frames % 30
    total_seconds = total_frames // 30
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60

    return f"{hh:02d}:{mm:02d}:{ss:02d};{frames:02d}"


def generate_edl(highlights: list[HighlightItem], reel_name: str = "AX0101") -> str:
    """추출된 하이라이트 목록을 EDIUS 호환 CMX 3600 포맷의 EDL 문자열로 변환합니다."""
    edl_lines = [
        f"TITLE: NEWS_HIGHLIGHTS",
        f"FCM: DROP FRAME",
        ""
    ]

    record_time = 0.0  # 타임라인 기준 누적 기록 시간

    for idx, item in enumerate(highlights, start=1):
        src_in = item.start_time
        src_out = item.end_time
        duration = src_out - src_in

        rec_in = record_time
        rec_out = record_time + duration

        tc_src_in = seconds_to_df_timecode(src_in)
        tc_src_out = seconds_to_df_timecode(src_out)
        tc_rec_in = seconds_to_df_timecode(rec_in)
        tc_rec_out = seconds_to_df_timecode(rec_out)

        # EDL Event Line (V: Video, C: Cut)
        event_line = f"{idx:03d}  {reel_name:<8} V     C        {tc_src_in} {tc_src_out} {tc_rec_in} {tc_rec_out}"
        comment_line = f"* FROM CLIP COMMENT: {item.title}"

        edl_lines.append(event_line)
        edl_lines.append(comment_line)
        edl_lines.append("")

        record_time = rec_out

    return "\n".join(edl_lines)


# ==============================================================================
# 3. 파이프라인 처리 함수 (Groq STT & Gemini API)
# ==============================================================================
def process_audio_stt(file_path: str) -> str:
    """Groq Whisper API를 사용하여 오디오 파일에서 타임코드가 포함된 자막을 추출합니다."""
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    with open(file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(file_path), file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            language="ko"
        )
    
    # 세그먼트별 타임코드와 텍스트 조합
    formatted_transcript = ""
    for segment in transcription.segments:
        start = segment.get('start', 0.0)
        end = segment.get('end', 0.0)
        text = segment.get('text', '')
        formatted_transcript += f"[{start:.2f}s -> {end:.2f}s] {text}\n"
        
    return formatted_transcript


def extract_highlights_gemini(transcript: str) -> HighlightResponse:
    """Gemini Structured Output을 활용해 영상의 주요 하이라이트 구간을 분석 및 추출합니다."""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    prompt = f"""
다음은 뉴스/방송 영상의 음성을 텍스트로 변환한 타임코드 기록입니다.
이 중 숏폼(Shorts/Reels) 콘텐츠로 제작하기에 가장 몰입도가 높고 임팩트 있는 핵심 하이라이트 구간 3~5개를 선정해주세요.

[자막 기록]:
{transcript}

[주의사항]:
- 각 하이라이트 구간의 시작 시간(start_time)과 종료 시간(end_time)은 제공된 자막의 초 단위 시간을 기준으로 정확히 지정하세요.
- 매력적인 요약 제목과 해당 구간을 선정한 이유를 함께 작성해주세요.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=HighlightResponse,
            temperature=0.2,
        ),
    )

    return HighlightResponse.model_validate_json(response.text)


# ==============================================================================
# 4. Streamlit UI 메인 화면 구성
# ==============================================================================
st.title("🎬 뉴스 숏폼 하이라이트 자동 추출기")
st.markdown("영상/음성 파일을 업로드하면 **STT 음성 인식 $\\rightarrow$ AI 핵심 구간 분석 $\\rightarrow$ EDIUS EDL 파일**까지 자동으로 생성합니다.")

st.divider()

# API 키 확인
groq_key = os.environ.get("GROQ_API_KEY")
gemini_key = os.environ.get("GEMINI_API_KEY")

if not groq_key or not gemini_key:
    st.error("⚠️ `.env` 파일에 `GROQ_API_KEY`와 `GEMINI_API_KEY`가 설정되어 있는지 확인해주세요.")
    st.stop()

# 파일 업로더
uploaded_file = st.file_uploader(
    "클립 편집에 사용할 미디어 파일을 선택하세요", 
    type=["mp3", "mp4", "m4a", "wav"],
    help="지원 형식: MP3, MP4, M4A, WAV"
)

# Reel ID 지정 (EDIUS 콘폼용)
col_opt1, col_opt2 = st.columns([1, 2])
with col_opt1:
    reel_id = st.text_input("Reel ID (EDL 릴 이름)", value="AX0101", max_chars=8)

if uploaded_file is not None:
    if st.button("🚀 하이라이트 추출 시작", type="primary", use_container_width=True):
        
        with st.status("하이라이트 파이프라인 작동 중...", expanded=True) as status:
            # 1. 임시 파일 저장
            st.write("📁 미디어 임시 저장 중...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            try:
                # 2. STT 음성 인식 (Groq)
                st.write("🎙️ Groq Whisper API로 타임코드 및 자막 추출 중...")
                transcript = process_audio_stt(tmp_file_path)
                st.session_state["transcript"] = transcript

                # 3. AI 구간 분석 (Gemini)
                st.write("🧠 Gemini 2.5 Flash 기반 핵심 구간 분석 중...")
                highlight_data = extract_highlights_gemini(transcript)
                st.session_state["highlights"] = highlight_data.highlights

                # 4. EDL 변환
                st.write("🎞️ EDIUS EDL 타임코드 데이터 생성 중...")
                edl_content = generate_edl(highlight_data.highlights, reel_name=reel_id)
                st.session_state["edl_content"] = edl_content

                status.update(label="✅ 하이라이트 분석 및 EDL 생성 완료!", state="complete", expanded=False)

            except Exception as e:
                status.update(label="❌ 오류 발생", state="error")
                st.error(f"처리 중 오류가 발생했습니다: {e}")
            finally:
                if os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)

# ==============================================================================
# 5. 분석 결과 출력 및 EDL 다운로드
# ==============================================================================
if "highlights" in st.session_state and st.session_state["highlights"]:
    st.divider()
    
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📌 추출된 하이라이트 리스트")
        for idx, item in enumerate(st.session_state["highlights"], 1):
            start_tc = seconds_to_df_timecode(item.start_time)
            end_tc = seconds_to_df_timecode(item.end_time)
            
            with st.expander(f"**[{idx}] {item.title}** ({start_tc} ~ {end_tc})", expanded=True):
                st.write(f"**구간:** `{item.start_time:.2f}s` ~ `{item.end_time:.2f}s` ({item.end_time - item.start_time:.1f}초 동안)")
                st.write(f"**선정 사유:** {item.reason}")

    with col_right:
        st.subheader("📥 EDIUS EDL 출력")
        st.caption("아래 EDL 파일을 다운로드하여 EDIUS / Premiere Pro 타임라인으로 바로 가져오기 하세요.")
        
        # EDL 텍스트 미리보기
        st.text_area("EDL 파일 내용 미리보기", value=st.session_state["edl_content"], height=220)

        # EDL 다운로드 버튼
        st.download_button(
            label="💾 EDL 파일 다운로드 (.edl)",
            data=st.session_state["edl_content"],
            file_name=f"{os.path.splitext(uploaded_file.name)[0]}_highlights.edl",
            mime="text/plain",
            use_container_width=True
        )

    # 전체 STT 기록 확인
    with st.expander("📄 전체 자막 (Groq Whisper STT 결과) 확인"):
        st.text_area("전체 자막", value=st.session_state.get("transcript", ""), height=250)
