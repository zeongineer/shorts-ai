import os
import json
import subprocess
import tempfile
from typing import Any, List

import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types


# ==============================================================================
# 1. 환경 설정 및 페이지 기본 세팅
# ==============================================================================

load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 방송실 대시보드 톤앤매너 CSS (unsafe_allow_html=True 로 수정)
st.markdown("""
<style>
    .stApp {
        background-color: #111827;
        color: #f3f4f6;
    }
    .card-box {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 12px;
    }
    .badge-num {
        background-color: #2563eb;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .badge-time {
        background-color: #059669;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85rem;
        margin-left: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 2. 안전한 데이터 처리 헬퍼 함수
# ==============================================================================

def get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    """Dict 형태든 SDK 데이터 객체 형태든 안전하게 값을 가져옴"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def prepare_audio_for_groq(input_file_path: str) -> str:
    """FFmpeg를 사용해 오디오를 16kHz / Mono / 32kbps MP3로 인코딩"""
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()

    cmd = [
        "ffmpeg", "-y", "-i", input_file_path,
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
        "-f", "mp3", output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        err_msg = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg 변환 오류:\n{err_msg}")


def seconds_to_df_timecode(seconds: float) -> str:
    """NTSC Drop Frame Timecode (29.97fps, HH:MM:SS;FF) 변환"""
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
    """UI 표출용 mm:ss 포맷터"""
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def get_media_duration(file_path: str) -> float:
    """FFprobe로 전체 미디어 재생 길이 측정"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def generate_edl(highlights: list, reel_name: str = "AX0101") -> str:
    """EDIUS 연동용 CMX 3600 EDL 생성"""
    edl_lines = [
        "TITLE: NEWS_SHORTFORM_HIGHLIGHTS",
        "FMT: NTSC DF",
        "",
    ]

    for idx, item in enumerate(highlights, 1):
        st_t = float(get_attr_or_key(item, "start_time", 0.0))
        et_t = float(get_attr_or_key(item, "end_time", 0.0))

        src_in = seconds_to_df_timecode(st_t)
        src_out = seconds_to_df_timecode(et_t)

        m_title = str(get_attr_or_key(item, "main_title", "Highlight"))
        s_title = str(get_attr_or_key(item, "sub_title", ""))

        edl_lines.append(f"{idx:03d}  {reel_name:<8} AA/V  C        {src_in} {src_out} {src_in} {src_out}")
        edl_lines.append(f"* FROM CLIP: {m_title}")
        edl_lines.append(f"* COMMENTS: {s_title}")
        edl_lines.append("")

    return "\n".join(edl_lines)


# ==============================================================================
# 3. Groq STT 모듈
# ==============================================================================

def run_whisper_stt(client: Groq, audio_path: str) -> List[Any]:
    """Groq Whisper API를 호출하여 타임코드가 명시된 Segments 수집"""
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb > 24.5:
        raise RuntimeError("변환된 오디오 파일이 Groq 전송 용량 제한(25MB)을 넘었습니다.")

    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="ko",
        )

    # Groq SDK 리턴 타입에 맞게 파싱
    segments = get_attr_or_key(transcription, "segments", None)
    if segments is None and isinstance(transcription, dict):
        segments = transcription.get("segments", [])
    
    return segments or []


# ==============================================================================
# 4. 하이라이트 검증 (Python Validation)
# ==============================================================================

def sanitize_and_fix_highlights(raw_highlights: list, media_duration: float = 0.0) -> list:
    """30~60초 하이라이트 길이 무결성 재검증 및 교정"""
    fixed_list = []
    if not isinstance(raw_highlights, list):
        return fixed_list

    for item in raw_highlights:
        try:
            start_time = float(get_attr_or_key(item, "start_time", 0.0))
            end_time = float(get_attr_or_key(item, "end_time", 0.0))

            start_time = max(0.0, start_time)
            end_time = max(0.0, end_time)

            if start_time > end_time:
                start_time, end_time = end_time, start_time

            if media_duration > 0:
                start_time = min(start_time, media_duration)
                end_time = min(end_time, media_duration)

            duration = end_time - start_time

            # 30초 미만 시 확장
            if duration < 30.0:
                cand_end = start_time + 30.0
                if media_duration > 0 and cand_end > media_duration:
                    continue
                end_time = cand_end

            # 60초 초과 시 잘라냄
            duration = end_time - start_time
            if duration > 60.0:
                end_time = start_time + 60.0

            duration = end_time - start_time
            if not (start_time < end_time and 30.0 <= duration <= 60.0):
                continue

            fixed_list.append({
                "main_title": str(get_attr_or_key(item, "main_title", "하이라이트")),
                "sub_title": str(get_attr_or_key(item, "sub_title", "")),
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "reason": str(get_attr_or_key(item, "reason", ""))
            })

        except (TypeError, ValueError):
            continue

    return fixed_list


# ==============================================================================
# 5. Gemini API 분석 모듈
# ==============================================================================

def run_gemini_highlight_extraction(
    gemini_api_key: str,
    segments: list,
    media_duration: float = 0.0,
) -> list:

    client = genai.Client(api_key=gemini_api_key)

    # 최신 Gemini 모델 우선순위
    target_models = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-2.5-flash",
    ]

    formatted_transcript = []
    for seg in segments:
        st_val = round(float(get_attr_or_key(seg, "start", 0)), 2)
        et_val = round(float(get_attr_or_key(seg, "end", 0)), 2)
        text_val = str(get_attr_or_key(seg, "text", "")).strip()

        if text_val:
            formatted_transcript.append(f"[{st_val:.2f}s ~ {et_val:.2f}s] {text_val}")

    transcript_text = "\n".join(formatted_transcript)

    prompt = f"""
너는 뉴스 전문 에디터이다. 아래 자막의 타임코드를 분석하여 숏폼에 최적화된 구간 3개를 추출해라.

[규칙]
1. 정확히 3개의 하이라이트 구간을 JSON 배열로 출력한다.
2. 각 구간의 길이(end_time - start_time)는 반드시 30초 이상 60초 이하여야 한다.
3. 타임코드는 제공된 자막 구간에 맞춰 문장이 중간에 끊기지 않는 지점을 선택한다.
4. 전체 미디어 길이는 약 {media_duration:.2f}초이다.

[자막 데이터]
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
                    "start_time": {"type": "NUMBER", "description": "구간 시작 (초)"},
                    "end_time": {"type": "NUMBER", "description": "구간 종료 (초)"},
                    "reason": {"type": "STRING", "description": "선정 이유"},
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "reason"],
            },
        },
        temperature=0.1,
    )

    last_error = None

    for m_name in target_models:
        try:
            res = client.models.generate_content(
                model=m_name,
                contents=prompt,
                config=gen_config,
            )

            raw_json = json.loads(res.text)
            sanitized = sanitize_and_fix_highlights(raw_json, media_duration)

            if len(sanitized) == 3:
                return sanitized

            last_error = RuntimeError(f"모델({m_name})의 추출 개수가 3개가 아닙니다.")

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError("하이라이트 구간을 추출할 수 없습니다. 다시 시도해 주세요.") from last_error


# ==============================================================================
# 6. 메인 UI 및 실행 로직
# ==============================================================================

def main():
    st.title("🎬 뉴스 숏폼 하이라이트 자동 추출기")
    st.caption("Groq Whisper STT + Gemini Flash + EDIUS EDL Integration")
    st.divider()

    groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    gemini_api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not groq_api_key or not gemini_api_key:
        st.error("🔑 API 키(GROQ_API_KEY, GEMINI_API_KEY)가 필요합니다.")
        st.stop()

    groq_client = Groq(api_key=groq_api_key)

    st.subheader("1. 뉴스 파일 업로드")
    uploaded_file = st.file_uploader(
        "음성/영상 파일을 등록하세요",
        type=["mp3", "mp4", "ts", "mov", "m4a", "wav"]
    )

    if not uploaded_file:
        st.info("파일을 선택해 주시면 분석 준비가 진행됩니다.")
        return

    st.success(f"선택된 파일: {uploaded_file.name} ({(uploaded_file.size / (1024 * 1024)):.2f} MB)")

    st.subheader("2. 추출 시작")
    if not st.button("🚀 하이라이트 추출 실행", type="primary", use_container_width=True):
        return

    raw_input_path = None
    processed_audio_path = None

    try:
        with st.status("분석 프로세스를 수행 중입니다...", expanded=True) as status:

            # 1단계: 임시 파일 수신 및 오디오 최적화
            st.write("1️⃣ 미디어 저장 및 16kHz MP3 변환 진행 중...")
            suffix = "." + uploaded_file.name.split(".")[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                while chunk := uploaded_file.read(8 * 1024 * 1024):
                    tmp.write(chunk)
                raw_input_path = tmp.name

            media_duration = get_media_duration(raw_input_path)
            processed_audio_path = prepare_audio_for_groq(raw_input_path)

            # 2단계: Groq Whisper 자막 추출
            st.write("2️⃣ Groq Whisper API 자막 및 타임코드 수집 중...")
            segments = run_whisper_stt(groq_client, processed_audio_path)
            if not segments:
                raise RuntimeError("오디오에서 음성을 인식하지 못했습니다.")

            # 3단계: Gemini 하이라이트 분석
            st.write("3️⃣ Gemini AI가 30~60초 하이라이트 3곳 선정 중...")
            highlights = run_gemini_highlight_extraction(gemini_api_key, segments, media_duration)

            # 4단계: EDL 생성
            st.write("4️⃣ EDIUS용 EDL 파일 생성 중...")
            edl_content = generate_edl(highlights)

            status.update(label="✨ 모든 작업이 완료되었습니다!", state="complete", expanded=False)

        # ------------------------------------------------------------------
        # 결과 대시보드
        # ------------------------------------------------------------------
        st.subheader("3. 추출 결과")

        for idx, item in enumerate(highlights, 1):
            st_sec = float(item["start_time"])
            et_sec = float(item["end_time"])
            dur = round(et_sec - st_sec, 1)

            st.markdown(f"""
            <div class="card-box">
                <div>
                    <span class="badge-num">하이라이트 {idx}</span>
                    <span class="badge-time">{dur}초 ({seconds_to_min_sec(st_sec)} ~ {seconds_to_min_sec(et_sec)})</span>
                </div>
                <h3 style="margin: 8px 0 4px 0; color: #f9fafb;">{item['main_title']}</h3>
                <p style="color: #9ca3af; margin-bottom: 8px;">{item['sub_title']}</p>
                <div style="font-size:0.85rem; color:#6b7280; margin-bottom:8px;">
                    NTSC DF 타임코드: {seconds_to_df_timecode(st_sec)} ~ {seconds_to_df_timecode(et_sec)}
                </div>
                <div style="background-color: #111827; padding: 10px; border-left: 3px solid #2563eb; font-size: 0.9rem;">
                    <strong>선정 이유:</strong> {item['reason']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.subheader("4. EDL 다운로드")
        edl_filename = f"{os.path.splitext(uploaded_file.name)[0]}_shortform.edl"

        st.download_button(
            label="📥 EDIUS EDL 파일 다운로드",
            data=edl_content,
            file_name=edl_filename,
            mime="text/plain",
            use_container_width=True
        )

    except Exception as err:
        st.error(f"오류가 발생했습니다: {str(err)}")
        if os.getenv("APP_DEBUG", "false").lower() == "true":
            st.exception(err)

    finally:
        for p in [raw_input_path, processed_audio_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
