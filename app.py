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
# 1. 환경 설정 및 UI 초기화
# ------------------------------------------------------------------------------
load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }
        .main .block-container { max-width: 900px; padding-top: 2rem; }
        .stButton button { width: 100%; height: 3.2rem; font-weight: bold; font-size: 1.1rem; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. 유틸리티 함수: 오디오 전처리 및 타임코드 변환
# ------------------------------------------------------------------------------
def prepare_audio_for_groq(input_file_path: str) -> str:
    """
    대용량 영상/음성 파일을 Groq API 전송 기준(25MB 이하)에 맞춰 초고속 압축
    """
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()

    cmd = [
        "ffmpeg", "-y",
        "-i", input_file_path,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "32k",
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

def seconds_to_df_timecode(seconds: float) -> str:
    """
    초 단위 실수를 NTSC Drop Frame Timecode (29.97 fps, HH:MM:SS;FF) 로 변환
    """
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
    mm = total_minutes // 60
    hh = total_minutes // 60

    return f"{hh:02d}:{mm:02d}:{ss:02d};{frames:02d}"

def seconds_to_min_sec(seconds: float) -> str:
    """초를 mm:ss 형식으로 변환 (프롬프트 전달용)"""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

def generate_edl(highlights: list, reel_name: str = "AX0101") -> str:
    """EDIUS 연동 CMX 3600 EDL 생성"""
    edl_lines = [
        "TITLE: NEWS_SHORTFORM_HIGHLIGHTS",
        "FMT: NTSC DF",
        ""
    ]
    
    for idx, item in enumerate(highlights, 1):
        s_time = float(item.get("start_time", 0.0))
        e_time = float(item.get("end_time", 0.0))
        
        src_in = seconds_to_df_timecode(s_time)
        src_out = seconds_to_df_timecode(e_time)
        
        edl_lines.append(f"{idx:03d}  {reel_name:<8} AA/V  C        {src_in} {src_out} {src_in} {src_out}")
        edl_lines.append(f"* FROM CLIP: {item.get('main_title', 'Highlight')}")
        edl_lines.append(f"* COMMENTS: {item.get('sub_title', '')}")
        edl_lines.append("")
        
    return "\n".join(edl_lines)

# ------------------------------------------------------------------------------
# 3. AI 서비스 호출 로직
# ------------------------------------------------------------------------------
def run_whisper_stt(client: Groq, audio_path: str):
    """Groq Whisper API를 호출하여 타임코드가 포함된 verbose_json 반환"""
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
    정밀 타임코드 파싱 로직이 강화된 Gemini 하이라이트 추출
    """
    client = genai.Client(api_key=gemini_api_key)
    
    preferred_models = [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash"
    ]
    
    active_models = []
    try:
        for m in client.models.list():
            model_id = getattr(m, 'name', '') or str(m)
            clean_id = model_id.replace("models/", "")
            active_models.append(clean_id)
    except Exception:
        pass

    final_models = [m for m in preferred_models if m in active_models]
    if not final_models:
        final_models = preferred_models

    # 타임코드 가독성 정제 (AI가 시작/끝 지점을 완벽하게 인식하도록 매핑)
    formatted_transcript = []
    for seg in segments:
        s_sec = round(seg.get("start", 0), 2)
        e_sec = round(seg.get("end", 0), 2)
        text = seg.get("text", "").strip()
        if text:
            formatted_transcript.append(f"[{s_sec:.2f}s ~ {e_sec:.2f}s] {text}")
    
    transcript_text = "\n".join(formatted_transcript)

    prompt = f"""
너는 뉴스 방송 수석 에디터이자 숏폼(YouTube Shorts, TikTok) 전문 크리에이터이다.
아래 제공된 뉴스 자막 데이터(타임코드 포함)를 철저히 분석하여, 숏폼으로 제작하기 가장 매력적인 구간 3곳을 선정하라.

[핵심 지침 - 타임코드 정밀 측정]
1. 각 하이라이트 구간의 총 길이는 **반드시 30초 이상 60초 이하**이어야 한다.
2. `start_time`은 시작하는 첫 자막의 시작 시간(초 숫자)을 정확히 가져와야 한다.
3. `end_time`은 끝나는 마지막 자막의 종료 시간(초 숫자)을 정확히 가져와야 한다. (계산 수식: end_time - start_time = 30~60초)
4. 문장이 중간에 어색하게 끊기지 않고 완전한 맥락을 이루도록 자막 블록들을 연속적으로 묶어서 선택하라.

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
                    "start_time": {"type": "NUMBER", "description": "구간 시작 시간 (실수 초 단위)"},
                    "end_time": {"type": "NUMBER", "description": "구간 종료 시간 (실수 초 단위)"},
                    "reason": {"type": "STRING", "description": "선정 이유"}
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "reason"]
            }
        },
        temperature=0.1  # 정확한 타임코드 추출을 위해 창의성 낮춤
    )

    last_exception = None
    for model_name in final_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gen_config
            )
            data = json.loads(response.text)
            
            # 검증 로직: 30~60초 보정 및 검수
            valid_highlights = []
            for item in data:
                s_t = float(item.get("start_time", 0))
                e_t = float(item.get("end_time", 0))
                duration = e_t - s_t
                
                # 최소 15초 이상인 경우 수용 (너무 짧게 잡히는 것 방지)
                if duration >= 15:
                    valid_highlights.append(item)

            return valid_highlights if valid_highlights else data

        except Exception as e:
            last_exception = e
            continue

    raise RuntimeError(f"모든 Gemini 모델 호출 실패: {last_exception}")

# ------------------------------------------------------------------------------
# 4. UI 및 메인 핸들러
# ------------------------------------------------------------------------------
def main():
    st.title("🎬 뉴스 숏폼 하이라이트 자동 추출기")
    st.caption("Groq Whisper STT + Gemini AI 기반 EDIUS 연동 EDL 생성 서비스")
    st.divider()

    groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    gemini_api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not groq_api_key or not gemini_api_key:
        st.error("⚠️ API 키가 설정되지 않았습니다. Secrets 또는 `.env`에 키를 설정해 주세요.")
        st.stop()

    groq_client = Groq(api_key=groq_api_key)

    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 업로드하세요 (최대 1GB)",
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"]
    )

    if uploaded_file is not None:
        st.info(f"📁 업로드 완료: **{uploaded_file.name}** ({uploaded_file.size / (1024*1024):.2f} MB)")
        
        if st.button("🚀 하이라이트 추출 및 EDL 생성 시작", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                status_text.text("1/4. 대용량 파일 저장 및 오디오 최적화 진행 중...")
                progress_bar.progress(10)

                suffix = f".{uploaded_file.name.split('.')[-1]}"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    chunk_size = 8 * 1024 * 1024
                    while True:
                        chunk = uploaded_file.read(chunk_size)
                        if not chunk:
                            break
                        tmp.write(chunk)
                    raw_input_path = tmp.name

                progress_bar.progress(25)
                processed_audio_path = prepare_audio_for_groq(raw_input_path)

                status_text.text("2/4. Groq Whisper STT 타임코드 분석 중...")
                progress_bar.progress(50)
                segments = run_whisper_stt(groq_client, processed_audio_path)

                status_text.text("3/4. Gemini AI 정밀 구간 추출 중...")
                progress_bar.progress(75)
                highlights = run_gemini_highlight_extraction(gemini_api_key, segments)

                status_text.text("4/4. EDL 파일 생성 완료!")
                progress_bar.progress(100)
                status_text.empty()
                progress_bar.empty()

                st.subheader("💡 추천 숏폼 하이라이트 구간")

                for i, hl in enumerate(highlights, 1):
                    start_sec = float(hl.get("start_time", 0.0))
                    end_sec = float(hl.get("end_time", 0.0))
                    duration = round(end_sec - start_sec, 1)

                    with st.expander(f"📌 하이라이트 {i}: {hl.get('main_title', '타이틀 없음')} ({duration}초)", expanded=(i==1)):
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.markdown(f"**부제목:** {hl.get('sub_title', '-')}")
                            st.markdown(f"**타임코드:** `{seconds_to_df_timecode(start_sec)}` ~ `{seconds_to_df_timecode(end_sec)}`")
                            st.markdown(f"**재생 시간:** {seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)} ({duration}초)")
                        with col2:
                            st.markdown(f"**선정 이유:**\n{hl.get('reason', '-')}")

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
