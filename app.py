import os
import json
import math
import subprocess
import tempfile
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types

# ------------------------------------------------------------------------------
# 1. 환경 설정 및 UI 초기화 (사이드바 완전 제거 UI)
# ------------------------------------------------------------------------------
load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 사용자 접근성 개선 및 사이드바 제거 CSS
st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }
        .main .block-container { max-width: 900px; padding-top: 2rem; }
        .stButton button { width: 100%; height: 3.2rem; font-weight: bold; font-size: 1.1rem; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. 유틸리티 함수: FFmpeg 오디오 전처리
# ------------------------------------------------------------------------------
def prepare_audio_for_groq(input_file_path: str) -> str:
    """
    업로드된 비디오/오디오 파일을 Groq API 전송 기준(25MB 이하)에 맞춰
    초고속 압축(MP3, 16kHz, 64kbps, 모노) 진행
    """
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()

    cmd = [
        "ffmpeg", "-y",
        "-i", input_file_path,
        "-vn",                   # 비디오 스트림 제거
        "-ar", "16000",          # 샘플링 레이트 16kHz
        "-ac", "1",              # 모노 채널
        "-b:a", "64k",           # 비트레이트 64kbps
        "-f", "mp3",
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"FFmpeg 변환 실패: {e.stderr.decode('utf-8', errors='ignore')}")

# ------------------------------------------------------------------------------
# 3. 유틸리티 함수: EDL 타임코드 변환 (Drop Frame 29.97 fps)
# ------------------------------------------------------------------------------
def seconds_to_df_timecode(seconds: float) -> str:
    """
    초 단위 실수를 NTSC Drop Frame Timecode (29.97 fps, HH:MM:SS;FF) 로 변환
    """
    total_frames = int(round(seconds * 29.97))
    
    # Drop Frame 계산 공식
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
    mm = total_minutes // 60
    hh = total_minutes // 60

    return f"{hh:02d}:{mm:02d}:{ss:02d};{frames:02d}"

def generate_edl(highlights: list, reel_name: str = "AX0101") -> str:
    """
    EDIUS 및 주요 NLE 연동용 표준 CMX 3600 EDL 텍스트 생성
    """
    edl_lines = [
        "TITLE: NEWS_SHORTFORM_HIGHLIGHTS",
        "FMT: NTSC DF",
        ""
    ]
    
    for idx, item in enumerate(highlights, 1):
        s_time = item.get("start_time", 0.0)
        e_time = item.get("end_time", 0.0)
        
        src_in = seconds_to_df_timecode(s_time)
        src_out = seconds_to_df_timecode(e_time)
        
        edl_lines.append(f"{idx:03d}  {reel_name:<8} AA/V  C        {src_in} {src_out} {src_in} {src_out}")
        edl_lines.append(f"* FROM CLIP: {item.get('main_title', 'Highlight')}")
        edl_lines.append(f"* COMMENTS: {item.get('sub_title', '')}")
        edl_lines.append("")
        
    return "\n".join(edl_lines)

# ------------------------------------------------------------------------------
# 4. AI 서비스 호출 로직 (Groq Whisper STT & Gemini LLM)
# ------------------------------------------------------------------------------
def run_whisper_stt(client: Groq, audio_path: str):
    """
    Groq Whisper API를 호출하여 타임코드가 포함된 verbose_json 반환
    """
    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="ko"
        )
    return transcription.segments

def run_gemini_highlight_extraction(gemini_api_key: str, segments: list) -> list:
    """
    Gemini 최신 추천 모델(gemini-3.6-flash 및 동적 활성 모델)을 사용하여
    Schema Enforcement 적용 후 하이라이트 추천
    """
    client = genai.Client(api_key=gemini_api_key)
    
    # 1. API 에러 메시지가 공식 안내한 최신 모델 우선 배치
    preferred_models = [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash"
    ]
    
    # 2. 계정 내 활성화된 모델 목록 동적 조회
    active_models = []
    try:
        for m in client.models.list():
            model_id = getattr(m, 'name', '') or str(m)
            # 'models/' 접두사 정제
            clean_id = model_id.replace("models/", "")
            active_models.append(clean_id)
    except Exception:
        pass

    # 우선순위 목록 중 실제 활성화된 모델 선택 (조회 실패 시 preferred_models 유지)
    final_models = [m for m in preferred_models if m in active_models]
    if not final_models:
        final_models = preferred_models

    condensed_segments = []
    for seg in segments:
        condensed_segments.append({
            "start": round(seg.get("start", 0), 2),
            "end": round(seg.get("end", 0), 2),
            "text": seg.get("text", "").strip()
        })
    
    prompt = f"""
너는 뉴스 수석 에디터이자 숏폼(YouTube Shorts, TikTok, 와이숏츠) 콘텐츠 전문가이다.
제공되는 타임코드별 뉴스 자막 데이터를 분석하여, 숏폼으로 제작하기 가장 매력적인 30초~60초 길이의 하이라이트 구간 3곳을 선정하라.

[선정 기준]
1. 각 구간은 반드시 30초 이상 60초 이하이어야 한다.
2. 시청자의 후킹을 유도하는 주요 발언이나 사건의 핵심 요약이 담긴 구간이어야 한다.
3. 제공되는 스키마 형식에 맞춰 정확한 JSON 데이터로 반환하라.

[뉴스 자막 데이터]
{json.dumps(condensed_segments, ensure_ascii=False)}
"""

    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "main_title": {"type": "STRING", "description": "메인 자막 타이틀 (15자 이내)"},
                    "sub_title": {"type": "STRING", "description": "부제목/요약 (25자 이내)"},
                    "start_time": {"type": "NUMBER", "description": "시작 시간(초)"},
                    "end_time": {"type": "NUMBER", "description": "종료 시간(초)"},
                    "reason": {"type": "STRING", "description": "선정 이유 설명"}
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "reason"]
            }
        },
        temperature=0.2
    )

    last_exception = None
    for model_name in final_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gen_config
            )
            return json.loads(response.text)
        except Exception as e:
            last_exception = e
            continue

    raise RuntimeError(f"모든 Gemini 모델 호출 실패: {last_exception}")

# ------------------------------------------------------------------------------
# 5. UI 메인 레이아웃 및 핸들러
# ------------------------------------------------------------------------------
def main():
    st.title("🎬 뉴스 숏폼 하이라이트 자동 추출기")
    st.caption("Groq Whisper STT + Gemini AI 기반 EDIUS 연동 EDL 생성 서비스")
    st.divider()

    # API 키 검증 (Secrets 또는 .env 로드)
    groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    gemini_api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not groq_api_key or not gemini_api_key:
        st.error("⚠️ API 키가 설정되지 않았습니다. Streamlit Secrets 또는 `.env` 파일에 `GROQ_API_KEY`와 `GEMINI_API_KEY`를 모두 등록해 주세요.")
        st.stop()

    groq_client = Groq(api_key=groq_api_key)

    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 업로드하세요",
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"],
        help="지원 형식: MP3, MP4, TS, MOV, M4A, WAV"
    )

    if uploaded_file is not None:
        st.info(f"📁 업로드 완료: **{uploaded_file.name}** ({uploaded_file.size / (1024*1024):.2f} MB)")
        
        if st.button("🚀 하이라이트 추출 및 EDL 생성 시작", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # 1단계: 임시 파일 저장 및 FFmpeg 전처리
                status_text.text("1/4. 파일 전처리 및 오디오 최적화 진행 중...")
                progress_bar.progress(15)

                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    raw_input_path = tmp.name

                processed_audio_path = prepare_audio_for_groq(raw_input_path)

                # 2단계: Groq Whisper STT
                status_text.text("2/4. Groq Whisper STT 타임코드 추출 중...")
                progress_bar.progress(45)
                segments = run_whisper_stt(groq_client, processed_audio_path)

                # 3단계: Gemini AI 하이라이트 추천
                status_text.text("3/4. Gemini AI 기반 숏폼 하이라이트 분석 중...")
                progress_bar.progress(75)
                highlights = run_gemini_highlight_extraction(gemini_api_key, segments)

                # 4단계: EDL 파일 생성 및 출력
                status_text.text("4/4. EDL 파일 생성 완료!")
                progress_bar.progress(100)
                status_text.empty()
                progress_bar.empty()

                st.subheader("💡 추천 숏폼 하이라이트 구간")

                for i, hl in enumerate(highlights, 1):
                    start_sec = hl.get("start_time", 0.0)
                    end_sec = hl.get("end_time", 0.0)
                    duration = round(end_sec - start_sec, 1)

                    with st.expander(f"📌 하이라이트 {i}: {hl.get('main_title', '타이틀 없음')} ({duration}초)", expanded=(i==1)):
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.markdown(f"**부제목:** {hl.get('sub_title', '-')}")
                            st.markdown(f"**구간:** `{seconds_to_df_timecode(start_sec)}` ~ `{seconds_to_df_timecode(end_sec)}`")
                            st.markdown(f"**길이:** {duration}초")
                        with col2:
                            st.markdown(f"**선정 이유:**\n{hl.get('reason', '-')}")

                # EDL 다운로드 버튼
                edl_content = generate_edl(highlights)
                edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"

                st.divider()
                st.download_button(
                    label="📥 EDIUS 연동 EDL 파일 다운로드",
                    data=edl_content,
                    file_name=edl_filename,
                    mime="text/plain",
                    use_container_width=True
                )

                # 임시 파일 정리
                if os.path.exists(raw_input_path):
                    os.remove(raw_input_path)
                if os.path.exists(processed_audio_path):
                    os.remove(processed_audio_path)

            except Exception as e:
                status_text.empty()
                progress_bar.empty()
                st.error(f"❌ 처리 도중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main()
