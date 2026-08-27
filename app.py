import os  
import json  
import subprocess  
import tempfile  
from typing import Any, List, Dict  
  
import streamlit as st  
from dotenv import load_dotenv  
from groq import Groq  
from google import genai  
from google.genai import types  
  
  
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
 
# 웹 접근성(WCAG AA) 준수 커스텀 CSS 스타일링 
st.markdown(  
    """  
    <style>  
    /* 색상 대비 4.5:1 이상 준수 */ 
    .main-title {  
        font-size: 2.2rem;  
        font-weight: 700;  
        color: #0F172A; /* 대비 강화 (15.8:1) */ 
        margin-bottom: 0.5rem;  
    }  
    .sub-title {  
        font-size: 1.05rem;  
        color: #334155; /* 대비 강화 (9.5:1) */ 
        margin-bottom: 1.5rem;  
        line-height: 1.6; 
    }  
    .highlight-card {  
        background-color: #FFFFFF;  
        border: 2px solid #CBD5E1; /* 테두리 명확화 */ 
        border-radius: 12px;  
        padding: 20px;  
        margin-bottom: 20px;  
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);  
    }  
    .badge {  
        background-color: #1D4ED8; /* 대비 강화 (4.6:1) */ 
        color: #FFFFFF;  
        padding: 4px 10px;  
        border-radius: 6px;  
        font-size: 0.85rem;  
        font-weight: 700;  
        display: inline-block;  
        margin-bottom: 10px;  
    }  
    .time-info {  
        background-color: #F8FAFC;  
        border-left: 5px solid #1D4ED8;  
        padding: 12px 14px;  
        font-family: monospace;  
        font-size: 0.95rem;  
        color: #0F172A;  
        margin: 12px 0;  
        border-radius: 0 6px 6px 0;  
    }  
    /* 스크린 리더 전용 숨김 클래스 */ 
    .sr-only { 
        position: absolute; 
        width: 1px; 
        height: 1px; 
        padding: 0; 
        margin: -1px; 
        overflow: hidden; 
        clip: rect(0, 0, 0, 0); 
        white-space: nowrap; 
        border: 0; 
    } 
    </style>  
    """,  
    unsafe_allow_html=True,  
)  
  
  
# ==============================================================================  
# 2. 헤더 UI (접근성 태그 및 대체텍스트 적용) 
# ==============================================================================  
  
st.markdown( 
    '<h1 class="main-title"><span aria-hidden="true">🎬 </span>뉴스 숏폼 하이라이트 자동 추출기</h1>',  
    unsafe_allow_html=True 
)  
st.markdown(  
    '<p class="sub-title">'  
    '뉴스 음성/영상 파일을 업로드하면 Groq Whisper로 자막과 타임코드를 추출하고, '  
    'Gemini AI가 30~60초 숏폼 구간 및 자막 타이틀을 자동으로 선정합니다.'  
    '</p>',  
    unsafe_allow_html=True,  
)  
  
st.info("💡 처리 결과는 EDIUS 영상 편집 프로그램에서 즉시 사용할 수 있는 EDL 파일로 제공됩니다.")  
st.divider()  
  
  
# ==============================================================================  
# 3. 유틸리티 함수  
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
# 4. Whisper STT 
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
# 5. 데이터 보정  
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
# 6. Gemini 하이라이트 추출  
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
# 7. API 키 가져오기  
# ==============================================================================  
 
def get_api_keys():  
    groq_api_key = st.secrets.get("GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")  
    gemini_api_key = st.secrets.get("GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")  
    return groq_api_key, gemini_api_key  
 
 
# ==============================================================================  
# 8. 메인 애플리케이션 (접근성 보완 구조) 
# ==============================================================================  
 
def main():  
    groq_api_key, gemini_api_key = get_api_keys()  
 
    if not groq_api_key or not gemini_api_key:  
        st.error("⚠️ API 키가 설정되지 않았습니다.")  
        st.info("환경 변수 또는 Streamlit Secrets에 GROQ_API_KEY와 GEMINI_API_KEY를 설정해 주세요.")  
        st.stop()  
 
    groq_client = Groq(api_key=groq_api_key)  
 
    # H2 헤딩 정의 
    st.header("1. 뉴스 파일 업로드")  
    uploaded_file = st.file_uploader(  
        "뉴스 음성 또는 영상 파일을 선택하세요.",  
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"],  
        help="MP3, MP4, TS, MOV 등 다양한 방송 미디어 포맷을 지원합니다.",  
    )  
 
    if uploaded_file is None:  
        st.info("📌 파일을 업로드하시면 하이라이트 분석 및 EDL 생성을 시작할 수 있습니다.")  
        return  
 
    file_size_mb = uploaded_file.size / (1024 * 1024)  
    st.success(f"📁 파일 선택 완료: **{uploaded_file.name}** ({file_size_mb:.2f} MB)")  
 
    if uploaded_file.size > (1024 * 1024 * 1024):  
        st.error("파일 크기가 1GB를 초과합니다. 1GB 이하의 파일을 업로드해 주세요.")  
        return  
 
    st.header("2. 하이라이트 분석")  
    start_button = st.button("🚀 하이라이트 추출 및 EDL 생성 시작", type="primary", use_container_width=True)  
 
    if not start_button:  
        return  
 
    raw_input_path = None  
    processed_audio_path = None  
 
    try:  
        with st.status("🎬 뉴스 미디어를 분석하는 중입니다...", expanded=True) as status:  
            st.write("1️⃣ 임시 파일 저장 및 오디오 변환(16kHz Mono) 중...")  
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
 
            st.write("2️⃣ Groq Whisper AI를 활용한 자막 및 타임코드 추출 중...")  
            segments = run_whisper_stt(groq_client, processed_audio_path)  
 
            if not segments:  
                raise RuntimeError("음성에서 자막을 추출하지 못했습니다. 오디오 트랙을 확인해주세요.")  
 
            st.write(f"✓ 자막 구간 {len(segments)}개 추출 완료")  
 
            st.write("3️⃣ Gemini AI 기반 숏폼(30~60초) 하이라이트 구간 탐색 중...")  
            highlights = run_gemini_highlight_extraction(gemini_api_key, segments, media_duration)  
 
            st.write("4️⃣ EDIUS 연동 EDL (CMX 3600) 파일 생성 중...")  
            edl_content = generate_edl(highlights)  
 
            status.update(label="✅ 분석 및 EDL 파일 생성이 완료되었습니다!", state="complete", expanded=False)  
 
        # H2 헤딩 
        st.header("3. 추천 숏폼 하이라이트 (3선)")  
 
        for index, highlight in enumerate(highlights, 1):  
            start_sec = float(highlight.get("start_time", 0.0))  
            end_sec = float(highlight.get("end_time", 0.0))  
            duration = round(end_sec - start_sec, 1)  
 
            title = str(highlight.get("main_title", f"하이라이트 {index}"))  
            subtitle = str(highlight.get("sub_title", "-"))  
            reason = str(highlight.get("reason", "-"))  
 
            # 접근성이 준수된 커스텀 카드 HTML 
            st.markdown(  
                f"""  
                <article class="highlight-card" aria-labelledby="card-title-{index}">  
                    <span class="badge">SHORTFORM #{index}</span>  
                    <h3 id="card-title-{index}" style="margin: 0 0 8px 0; color: #0F172A; font-size: 1.3rem;">{title}</h3>  
                    <p style="margin: 0 0 12px 0; color: #334155; font-weight: 600;">{subtitle}</p>  
                    <div class="time-info" role="region" aria-label="시간 정보">  
                        <span aria-hidden="true">⏱️ </span><strong>타임코드:</strong> {seconds_to_df_timecode(start_sec)} ~ {seconds_to_df_timecode(end_sec)}<br>  
                        <span aria-hidden="true">⏳ </span><strong>재생시간:</strong> {seconds_to_min_sec(start_sec)} ~ {seconds_to_min_sec(end_sec)} ({duration}초)  
                    </div>  
                    <p style="margin: 8px 0 0 0; font-size: 0.95rem; color: #334155;">  
                        <strong><span aria-hidden="true">💡 </span>선정 이유:</strong> {reason}  
                    </p>  
                </article>  
                """,  
                unsafe_allow_html=True,  
            )  
 
        st.divider()  
        st.header("4. EDIUS 연동 파일 다운로드")  
 
        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"  
 
        st.download_button(  
            label="💾 EDIUS용 EDL 파일 다운로드",  
            data=edl_content,  
            file_name=edl_filename,  
            mime="text/plain",  
            use_container_width=True,  
        )  
 
    except Exception as error:  
        st.error("❌ 처리 중 오류가 발생했습니다.")  
        st.write("• 오디오 트랙이 정상 포함된 미디어 파일인지 확인해 보세요.")  
        st.write("• 지속적인 실패 발생 시 관리자에게 문의바랍니다.")  
 
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
