import os
import json
import subprocess
import tempfile
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types


# ==============================================================================
# 1. 환경 설정
# ==============================================================================

load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==============================================================================
# 2. 전문적인 업무용 UI CSS
# ==============================================================================

st.markdown(
    """
    <style>

    /* =========================================================================
       기본 전역 설정
       ========================================================================= */

    html {
        scroll-behavior: smooth;
    }

    body {
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            "Noto Sans KR",
            "Malgun Gothic",
            sans-serif;
    }

    .stApp {
        background:
            linear-gradient(
                180deg,
                #f7f9fc 0%,
                #ffffff 42%,
                #f7f9fc 100%
            );
    }

    /* =========================================================================
       메인 컨테이너
       ========================================================================= */

    .main .block-container {
        max-width: 1180px;
        padding-top: 2.5rem;
        padding-bottom: 4rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }

    /* =========================================================================
       헤더
       ========================================================================= */

    .app-header {
        margin-bottom: 2rem;
    }

    .app-header-eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;

        padding: 0.35rem 0.7rem;

        border-radius: 999px;

        background: #eef3ff;
        border: 1px solid #dbe5ff;

        color: #3158b7;

        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }

    .app-header-title {
        margin-top: 0.8rem;
        margin-bottom: 0.45rem;

        color: #111827;

        font-size: 2.15rem;
        line-height: 1.2;
        font-weight: 800;
        letter-spacing: -0.04em;
    }

    .app-header-description {
        margin: 0;

        color: #667085;

        font-size: 1rem;
        line-height: 1.7;
    }

    /* =========================================================================
       섹션
       ========================================================================= */

    .section-heading {
        margin-top: 2.2rem;
        margin-bottom: 1rem;
    }

    .section-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;

        width: 28px;
        height: 28px;

        margin-right: 0.55rem;

        border-radius: 8px;

        background: #172b4d;
        color: #ffffff;

        font-size: 0.82rem;
        font-weight: 800;
    }

    .section-title {
        color: #172033;

        font-size: 1.2rem;
        font-weight: 750;
        letter-spacing: -0.025em;
    }

    .section-description {
        margin-top: 0.35rem;
        margin-left: 2.55rem;

        color: #667085;

        font-size: 0.9rem;
        line-height: 1.6;
    }

    /* =========================================================================
       파일 업로드 카드
       ========================================================================= */

    [data-testid="stFileUploader"] {
        padding: 0.25rem;
    }

    [data-testid="stFileUploaderDropzone"] {
        min-height: 190px;

        border: 1.5px dashed #b9c4d6;
        border-radius: 16px;

        background: #ffffff;

        transition:
            border-color 0.18s ease,
            background-color 0.18s ease,
            box-shadow 0.18s ease;
    }

    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #4969b8;
        background: #f8faff;

        box-shadow:
            0 8px 25px rgba(31, 56, 100, 0.07);
    }

    [data-testid="stFileUploaderDropzone"]:focus-within {
        border-color: #3158b7;

        box-shadow:
            0 0 0 3px rgba(49, 88, 183, 0.18);
    }

    [data-testid="stFileUploaderDropzoneInstructions"] {
        color: #475467;
    }

    /* =========================================================================
       일반 Streamlit 텍스트
       ========================================================================= */

    .stMarkdown p {
        color: #344054;
        line-height: 1.7;
    }

    /* =========================================================================
       버튼
       ========================================================================= */

    .stButton > button {
        min-height: 52px;

        border: 1px solid #172b4d;
        border-radius: 10px;

        background: #172b4d;
        color: #ffffff;

        font-size: 0.98rem;
        font-weight: 750;

        box-shadow:
            0 2px 5px rgba(16, 24, 40, 0.08);

        transition:
            background-color 0.16s ease,
            border-color 0.16s ease,
            box-shadow 0.16s ease,
            transform 0.16s ease;
    }

    .stButton > button:hover {
        border-color: #0f1e35;
        background: #0f1e35;

        box-shadow:
            0 5px 14px rgba(23, 43, 77, 0.18);

        transform: translateY(-1px);
    }

    .stButton > button:active {
        transform: translateY(0);
    }

    .stButton > button:focus-visible {
        outline: 3px solid #7c9df2;
        outline-offset: 3px;
    }

    .stDownloadButton > button {
        min-height: 54px;

        border: 1px solid #3158b7;
        border-radius: 10px;

        background: #3158b7;
        color: #ffffff;

        font-size: 0.98rem;
        font-weight: 750;

        box-shadow:
            0 4px 12px rgba(49, 88, 183, 0.18);

        transition:
            background-color 0.16s ease,
            box-shadow 0.16s ease,
            transform 0.16s ease;
    }

    .stDownloadButton > button:hover {
        background: #26499c;

        box-shadow:
            0 7px 18px rgba(49, 88, 183, 0.22);

        transform: translateY(-1px);
    }

    .stDownloadButton > button:focus-visible {
        outline: 3px solid #7c9df2;
        outline-offset: 3px;
    }

    /* =========================================================================
       성공 / 정보 / 오류 메시지
       ========================================================================= */

    [data-testid="stAlert"] {
        border-radius: 10px;
    }

    /* =========================================================================
       Status 영역
       ========================================================================= */

    [data-testid="stStatusWidget"] {
        border-radius: 14px;
        border: 1px solid #d9e0eb;
        background: #ffffff;

        box-shadow:
            0 4px 18px rgba(16, 24, 40, 0.05);
    }

    /* =========================================================================
       Expander
       ========================================================================= */

    [data-testid="stExpander"] {
        margin-bottom: 0.9rem;

        border: 1px solid #dfe5ee;
        border-radius: 14px;

        background: #ffffff;

        box-shadow:
            0 2px 10px rgba(16, 24, 40, 0.035);

        overflow: hidden;
    }

    [data-testid="stExpander"] details {
        border: none;
    }

    [data-testid="stExpander"] summary {
        min-height: 58px;

        padding: 0.8rem 1rem;

        color: #172033;

        font-weight: 700;
    }

    [data-testid="stExpander"] summary:hover {
        background: #f8faff;
    }

    [data-testid="stExpander"] summary:focus-visible {
        outline: 3px solid #7c9df2;
        outline-offset: -3px;
    }

    /* =========================================================================
       타임코드 카드
       ========================================================================= */

    .timecode-card {
        margin-top: 0.75rem;
        margin-bottom: 0.75rem;

        padding: 1rem 1.1rem;

        border-radius: 12px;

        background: #f5f7fb;
        border: 1px solid #e1e7f0;
    }

    .timecode-label {
        margin-bottom: 0.35rem;

        color: #667085;

        font-size: 0.75rem;
        font-weight: 750;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }

    .timecode-value {
        color: #172b4d;

        font-family:
            "SFMono-Regular",
            Consolas,
            "Liberation Mono",
            monospace;

        font-size: 1.05rem;
        font-weight: 750;
        letter-spacing: 0.01em;
    }

    /* =========================================================================
       결과 정보 카드
       ========================================================================= */

    .result-meta {
        display: grid;

        grid-template-columns:
            repeat(3, minmax(0, 1fr));

        gap: 0.8rem;

        margin-top: 0.8rem;
        margin-bottom: 1rem;
    }

    .result-meta-item {
        padding: 0.9rem;

        border: 1px solid #e2e7ef;
        border-radius: 10px;

        background: #fafbfc;
    }

    .result-meta-label {
        color: #667085;

        font-size: 0.75rem;
        font-weight: 700;
    }

    .result-meta-value {
        margin-top: 0.3rem;

        color: #172033;

        font-size: 0.95rem;
        font-weight: 700;
    }

    /* =========================================================================
       EDL 다운로드 영역
       ========================================================================= */

    .download-card {
        margin-top: 1rem;
        margin-bottom: 1rem;

        padding: 1.4rem;

        border: 1px solid #d8e1f0;
        border-radius: 14px;

        background:
            linear-gradient(
                135deg,
                #f7f9ff 0%,
                #ffffff 100%
            );
    }

    .download-card-title {
        margin-bottom: 0.3rem;

        color: #172033;

        font-size: 1rem;
        font-weight: 750;
    }

    .download-card-description {
        margin-bottom: 1rem;

        color: #667085;

        font-size: 0.88rem;
        line-height: 1.6;
    }

    /* =========================================================================
       구분선
       ========================================================================= */

    hr {
        margin-top: 2rem !important;
        margin-bottom: 2rem !important;

        border: none !important;
        border-top: 1px solid #e4e8ef !important;
    }

    /* =========================================================================
       작은 안내 문구
       ========================================================================= */

    .helper-text {
        color: #667085;

        font-size: 0.82rem;
        line-height: 1.6;
    }

    /* =========================================================================
       Footer
       ========================================================================= */

    .app-footer {
        margin-top: 3rem;
        padding-top: 1.2rem;

        border-top: 1px solid #e4e8ef;

        color: #98a2b3;

        font-size: 0.76rem;
        line-height: 1.6;

        text-align: center;
    }

    /* =========================================================================
       반응형
       ========================================================================= */

    @media (max-width: 768px) {

        .main .block-container {
            padding-top: 1.5rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .app-header-title {
            font-size: 1.7rem;
        }

        .result-meta {
            grid-template-columns: 1fr;
        }

    }

    /* =========================================================================
       모션 감소 설정
       WCAG 2.3.3 / 사용자 환경 고려
       ========================================================================= */

    @media (prefers-reduced-motion: reduce) {

        html {
            scroll-behavior: auto;
        }

        *,
        *::before,
        *::after {
            transition-duration: 0.01ms !important;
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
        }

    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 3. 유틸리티 함수
# ==============================================================================

def prepare_audio_for_groq(input_file_path: str) -> str:

    output_temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3",
    )

    output_path = output_temp_file.name
    output_temp_file.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_file_path,
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "32k",
        "-f",
        "mp3",
        output_path,
    ]

    try:

        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        return output_path

    except subprocess.CalledProcessError as e:

        if os.path.exists(output_path):
            os.remove(output_path)

        error_message = e.stderr.decode(
            "utf-8",
            errors="ignore",
        )

        raise RuntimeError(
            f"오디오 변환에 실패했습니다.\n{error_message}"
        )


def seconds_to_df_timecode(
    seconds: float,
) -> str:

    seconds = max(
        0.0,
        float(seconds),
    )

    total_frames = int(
        round(
            seconds * 29.97
        )
    )

    D = total_frames // 17982
    M = total_frames % 17982

    if M >= 2:

        total_frames += (
            18 * D
            + 2 * ((M - 2) // 1798)
        )

    else:

        total_frames += 18 * D

    frames = total_frames % 30

    total_seconds = total_frames // 30

    ss = total_seconds % 60

    total_minutes = total_seconds // 60

    mm = total_minutes % 60

    hh = total_minutes // 60

    return (
        f"{hh:02d}:"
        f"{mm:02d}:"
        f"{ss:02d};"
        f"{frames:02d}"
    )


def seconds_to_min_sec(
    seconds: float,
) -> str:

    seconds = max(
        0,
        int(seconds),
    )

    minutes, seconds = divmod(
        seconds,
        60,
    )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def get_media_duration(
    file_path: str,
) -> float:

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]

    try:

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )

        return float(
            result.stdout.strip()
        )

    except (
        subprocess.CalledProcessError,
        ValueError,
    ):

        return 0.0


def generate_edl(
    highlights: list,
    reel_name: str = "AX0101",
) -> str:

    edl_lines = [
        "TITLE: NEWS_SHORTFORM_HIGHLIGHTS",
        "FMT: NTSC DF",
        "",
    ]

    for index, item in enumerate(
        highlights,
        1,
    ):

        start_time = float(
            item.get(
                "start_time",
                0.0,
            )
        )

        end_time = float(
            item.get(
                "end_time",
                0.0,
            )
        )

        src_in = seconds_to_df_timecode(
            start_time
        )

        src_out = seconds_to_df_timecode(
            end_time
        )

        main_title = str(
            item.get(
                "main_title",
                "Highlight",
            )
        )

        sub_title = str(
            item.get(
                "sub_title",
                "",
            )
        )

        edl_lines.append(
            f"{index:03d}  "
            f"{reel_name:<8} "
            f"AA/V  C        "
            f"{src_in} "
            f"{src_out} "
            f"{src_in} "
            f"{src_out}"
        )

        edl_lines.append(
            f"* FROM CLIP: {main_title}"
        )

        edl_lines.append(
            f"* COMMENTS: {sub_title}"
        )

        edl_lines.append("")

    return "\n".join(edl_lines)


# ==============================================================================
# 4. Whisper STT
# ==============================================================================

def run_whisper_stt(
    client: Groq,
    audio_path: str,
):

    with open(
        audio_path,
        "rb",
    ) as file:

        transcription = (
            client.audio.transcriptions.create(
                file=(
                    os.path.basename(
                        audio_path
                    ),
                    file.read(),
                ),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="ko",
            )
        )

    return transcription.segments


# ==============================================================================
# 5. 하이라이트 검증
# ==============================================================================

def sanitize_and_fix_highlights(
    raw_highlights: list,
    media_duration: float = 0.0,
) -> list:

    fixed_list = []

    if not isinstance(
        raw_highlights,
        list,
    ):
        return fixed_list

    for item in raw_highlights:

        if not isinstance(
            item,
            dict,
        ):
            continue

        try:

            start_time = float(
                item.get(
                    "start_time",
                    0.0,
                )
            )

            end_time = float(
                item.get(
                    "end_time",
                    0.0,
                )
            )

            start_time = max(
                0.0,
                start_time,
            )

            end_time = max(
                0.0,
                end_time,
            )

            if start_time > end_time:

                start_time, end_time = (
                    end_time,
                    start_time,
                )

            if media_duration > 0:

                start_time = min(
                    start_time,
                    media_duration,
                )

                end_time = min(
                    end_time,
                    media_duration,
                )

            duration = (
                end_time
                - start_time
            )

            if duration < 30.0:

                candidate_end = (
                    start_time
                    + 30.0
                )

                if (
                    media_duration > 0
                    and candidate_end
                    > media_duration
                ):
                    continue

                end_time = candidate_end

            duration = (
                end_time
                - start_time
            )

            if duration > 60.0:

                end_time = (
                    start_time
                    + 60.0
                )

            duration = (
                end_time
                - start_time
            )

            if not (
                start_time
                < end_time
            ):
                continue

            if not (
                30.0
                <= duration
                <= 60.0
            ):
                continue

            item["start_time"] = round(
                start_time,
                2,
            )

            item["end_time"] = round(
                end_time,
                2,
            )

            fixed_list.append(
                item
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

    return fixed_list


# ==============================================================================
# 6. Gemini 하이라이트 추출
# ==============================================================================

def run_gemini_highlight_extraction(
    gemini_api_key: str,
    segments: list,
    media_duration: float = 0.0,
) -> list:

    client = genai.Client(
        api_key=gemini_api_key
    )

    preferred_models = [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]

    active_models = []

    try:

        for model in client.models.list():

            model_id = (
                getattr(
                    model,
                    "name",
                    "",
                )
                or str(model)
            )

            clean_id = (
                model_id.replace(
                    "models/",
                    "",
                )
            )

            active_models.append(
                clean_id
            )

    except Exception:

        pass

    final_models = [
        model
        for model in preferred_models
        if model in active_models
    ]

    if not final_models:

        final_models = (
            preferred_models
        )

    formatted_transcript = []

    for segment in segments:

        start = round(
            float(
                segment.get(
                    "start",
                    0,
                )
            ),
            2,
        )

        end = round(
            float(
                segment.get(
                    "end",
                    0,
                )
            ),
            2,
        )

        text = str(
            segment.get(
                "text",
                "",
            )
        ).strip()

        if text:

            formatted_transcript.append(
                f"[{start:.2f}s ~ "
                f"{end:.2f}s] {text}"
            )

    transcript_text = "\n".join(
        formatted_transcript
    )

    prompt = f"""
너는 뉴스 방송 수석 에디터이자
YouTube Shorts와 TikTok 전문 콘텐츠 에디터이다.

아래 뉴스 자막 데이터의 타임코드를 정확하게 분석하여
숏폼으로 제작하기 가장 적합한 구간 3곳을 선정하라.

[필수 규칙]

1. 정확히 3개의 하이라이트를 반환한다.

2. start_time은 반드시 end_time보다 작아야 한다.

3. 각 구간의 길이는 반드시 30초 이상 60초 이하여야 한다.

4. start_time은 선택한 첫 번째 자막의 시작 시간이다.

5. end_time은 선택한 마지막 자막의 종료 시간이다.

6. 문장이 중간에서 잘리지 않아야 한다.

7. 하나의 하이라이트는 하나의 완전한 뉴스 맥락을 가져야 한다.

8. 서로 지나치게 겹치는 구간은 피한다.

9. 제공된 자막의 실제 타임코드를 사용한다.

10. 영상 전체 길이는 약 {media_duration:.2f}초이다.

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
                    "main_title": {
                        "type": "STRING",
                    },
                    "sub_title": {
                        "type": "STRING",
                    },
                    "start_time": {
                        "type": "NUMBER",
                    },
                    "end_time": {
                        "type": "NUMBER",
                    },
                    "reason": {
                        "type": "STRING",
                    },
                },
                "required": [
                    "main_title",
                    "sub_title",
                    "start_time",
                    "end_time",
                    "reason",
                ],
            },
        },
        temperature=0.1,
    )

    last_exception = None

    for model_name in final_models:

        try:

            response = (
                client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=gen_config,
                )
            )

            raw_data = json.loads(
                response.text
            )

            sanitized_data = (
                sanitize_and_fix_highlights(
                    raw_data,
                    media_duration,
                )
            )

            if len(
                sanitized_data
            ) != 3:

                last_exception = RuntimeError(
                    "유효한 하이라이트 3개를 "
                    "생성하지 못했습니다."
                )

                continue

            return sanitized_data

        except Exception as error:

            last_exception = error

    raise RuntimeError(
        "AI 하이라이트 추출에 실패했습니다. "
        "잠시 후 다시 시도해 주세요."
    ) from last_exception


# ==============================================================================
# 7. API Key
# ==============================================================================

def get_api_keys():

    groq_api_key = (
        st.secrets.get(
            "GROQ_API_KEY",
            None,
        )
        or os.getenv(
            "GROQ_API_KEY"
        )
    )

    gemini_api_key = (
        st.secrets.get(
            "GEMINI_API_KEY",
            None,
        )
        or os.getenv(
            "GEMINI_API_KEY"
        )
    )

    return (
        groq_api_key,
        gemini_api_key,
    )


# ==============================================================================
# 8. 메인 앱
# ==============================================================================

def main():

    # ==========================================================================
    # Header
    # ==========================================================================

    st.markdown(
        """
        <header class="app-header">
            <div class="app-header-eyebrow">
                NEWS SHORTFORM · AI EDITOR
            </div>

            <div class="app-header-title">
                뉴스 숏폼 하이라이트 추출기
            </div>

            <p class="app-header-description">
                뉴스 영상의 음성을 분석하여 숏폼에 적합한
                핵심 구간을 자동으로 선정하고,
                EDIUS용 EDL 파일을 생성합니다.
            </p>
        </header>
        """,
        unsafe_allow_html=True,
    )

    # ==========================================================================
    # API Key
    # ==========================================================================

    groq_api_key, gemini_api_key = (
        get_api_keys()
    )

    if (
        not groq_api_key
        or not gemini_api_key
    ):

        st.error(
            "API 키가 설정되지 않았습니다."
        )

        st.write(
            "GROQ_API_KEY와 GEMINI_API_KEY를 "
            "Streamlit Secrets 또는 .env에 설정해 주세요."
        )

        st.stop()

    groq_client = Groq(
        api_key=groq_api_key
    )

    # ==========================================================================
    # STEP 01
    # ==========================================================================

    st.markdown(
        """
        <div class="section-heading">
            <span class="section-number">01</span>
            <span class="section-title">
                뉴스 파일 업로드
            </span>

            <div class="section-description">
                분석할 뉴스 음성 또는 영상 파일을 선택하세요.
                최대 1GB까지 업로드할 수 있습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write(
        "지원 형식: MP3 · MP4 · TS · MOV · M4A · WAV"
    )

    uploaded_file = st.file_uploader(
        "분석할 뉴스 파일을 선택하세요.",
        type=[
            "mp3",
            "mp4",
            "ts",
            "mov",
            "m4a",
            "wav",
        ],
        help=(
            "뉴스 음성 또는 영상 파일을 선택하면 "
            "AI가 숏폼 하이라이트를 분석합니다."
        ),
        label_visibility="collapsed",
    )

    if uploaded_file is None:

        st.info(
            "분석할 뉴스 파일을 업로드하면 "
            "하이라이트 추출을 시작할 수 있습니다."
        )

        st.markdown(
            """
            <div class="helper-text">
                파일을 업로드한 후 아래 분석 시작 버튼을
                선택할 수 있습니다.
            </div>
            """,
            unsafe_allow_html=True,
        )

        return

    # ==========================================================================
    # 업로드 파일 정보
    # ==========================================================================

    file_size_mb = (
        uploaded_file.size
        / (1024 * 1024)
    )

    max_file_size = (
        1024 * 1024 * 1024
    )

    if (
        uploaded_file.size
        > max_file_size
    ):

        st.error(
            "파일 크기가 1GB를 초과합니다. "
            "1GB 이하의 파일을 선택해 주세요."
        )

        return

    st.success(
        f"파일 준비 완료 · "
        f"{uploaded_file.name} · "
        f"{file_size_mb:.2f}MB"
    )

    # ==========================================================================
    # STEP 02
    # ==========================================================================

    st.markdown(
        """
        <div class="section-heading">
            <span class="section-number">02</span>
            <span class="section-title">
                AI 하이라이트 분석
            </span>

            <div class="section-description">
                Whisper STT로 자막과 타임코드를 추출한 뒤
                Gemini AI가 숏폼에 적합한 구간을 선정합니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    start_button = st.button(
        "하이라이트 추출 및 EDL 생성 시작",
        type="primary",
        use_container_width=True,
        help=(
            "업로드한 뉴스 파일을 분석하여 "
            "3개의 숏폼 하이라이트와 EDL 파일을 생성합니다."
        ),
    )

    if not start_button:
        return

    raw_input_path = None
    processed_audio_path = None

    try:

        # ======================================================================
        # 처리 상태
        # ======================================================================

        with st.status(
            "뉴스 파일을 분석하고 있습니다.",
            expanded=True,
        ) as status:

            # ------------------------------------------------------------------
            # 01 파일 저장
            # ------------------------------------------------------------------

            st.write(
                "1단계 · 파일 저장 및 오디오 최적화"
            )

            suffix = (
                "."
                + uploaded_file.name.split(
                    "."
                )[-1]
            )

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as tmp:

                chunk_size = (
                    8 * 1024 * 1024
                )

                while True:

                    chunk = (
                        uploaded_file.read(
                            chunk_size
                        )
                    )

                    if not chunk:
                        break

                    tmp.write(chunk)

                raw_input_path = (
                    tmp.name
                )

            media_duration = (
                get_media_duration(
                    raw_input_path
                )
            )

            processed_audio_path = (
                prepare_audio_for_groq(
                    raw_input_path
                )
            )

            st.write(
                "파일 저장 및 오디오 최적화 완료"
            )

            # ------------------------------------------------------------------
            # 02 Whisper
            # ------------------------------------------------------------------

            st.write(
                "2단계 · Whisper STT 타임코드 분석"
            )

            segments = run_whisper_stt(
                groq_client,
                processed_audio_path,
            )

            if not segments:

                raise RuntimeError(
                    "음성에서 자막을 추출하지 못했습니다."
                )

            st.write(
                f"자막 구간 {len(segments)}개 추출 완료"
            )

            # ------------------------------------------------------------------
            # 03 Gemini
            # ------------------------------------------------------------------

            st.write(
                "3단계 · Gemini AI 하이라이트 선정"
            )

            highlights = (
                run_gemini_highlight_extraction(
                    gemini_api_key,
                    segments,
                    media_duration,
                )
            )

            if len(
                highlights
            ) != 3:

                raise RuntimeError(
                    "유효한 하이라이트 3개를 "
                    "생성하지 못했습니다."
                )

            st.write(
                "숏폼 하이라이트 3개 선정 완료"
            )

            # ------------------------------------------------------------------
            # 04 EDL
            # ------------------------------------------------------------------

            st.write(
                "4단계 · EDIUS용 EDL 생성"
            )

            edl_content = generate_edl(
                highlights
            )

            st.write(
                "EDL 파일 생성 완료"
            )

            status.update(
                label="분석이 완료되었습니다.",
                state="complete",
                expanded=False,
            )

        # ======================================================================
        # STEP 03 결과
        # ======================================================================

        st.markdown(
            """
            <div class="section-heading">
                <span class="section-number">03</span>
                <span class="section-title">
                    추천 숏폼 하이라이트
                </span>

                <div class="section-description">
                    AI가 뉴스의 맥락과 내용의 중요도를 분석하여
                    선정한 숏폼 후보 구간입니다.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for index, highlight in enumerate(
            highlights,
            1,
        ):

            start_sec = float(
                highlight.get(
                    "start_time",
                    0.0,
                )
            )

            end_sec = float(
                highlight.get(
                    "end_time",
                    0.0,
                )
            )

            duration = round(
                end_sec
                - start_sec,
                1,
            )

            title = str(
                highlight.get(
                    "main_title",
                    "하이라이트",
                )
            )

            subtitle = str(
                highlight.get(
                    "sub_title",
                    "-",
                )
            )

            reason = str(
                highlight.get(
                    "reason",
                    "-",
                )
            )

            with st.expander(
                f"하이라이트 {index} · {title}",
                expanded=(
                    index == 1
                ),
            ):

                st.subheader(
                    title
                )

                st.write(
                    f"핵심 요약: {subtitle}"
                )

                # --------------------------------------------------------------
                # 타임코드
                # --------------------------------------------------------------

                st.markdown(
                    f"""
                    <div class="timecode-card">
                        <div class="timecode-label">
                            EDIUS SOURCE TIMECODE
                        </div>

                        <div class="timecode-value">
                            {seconds_to_df_timecode(start_sec)}
                            &nbsp; → &nbsp;
                            {seconds_to_df_timecode(end_sec)}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # --------------------------------------------------------------
                # Meta 정보
                # --------------------------------------------------------------

                st.markdown(
                    f"""
                    <div class="result-meta">

                        <div class="result-meta-item">
                            <div class="result-meta-label">
                                시작 시간
                            </div>

                            <div class="result-meta-value">
                                {seconds_to_min_sec(start_sec)}
                            </div>
                        </div>

                        <div class="result-meta-item">
                            <div class="result-meta-label">
                                종료 시간
                            </div>

                            <div class="result-meta-value">
                                {seconds_to_min_sec(end_sec)}
                            </div>
                        </div>

                        <div class="result-meta-item">
                            <div class="result-meta-label">
                                구간 길이
                            </div>

                            <div class="result-meta-value">
                                {duration:.1f}초
                            </div>
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.write(
                    f"선정 이유: {reason}"
                )

        # ======================================================================
        # STEP 04
        # ======================================================================

        st.divider()

        st.markdown(
            """
            <div class="section-heading">
                <span class="section-number">04</span>
                <span class="section-title">
                    EDIUS 프로젝트 연동
                </span>

                <div class="section-description">
                    생성된 하이라이트 타임코드를 기반으로
                    CMX 3600 형식의 EDL 파일을 제공합니다.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        edl_filename = (
            f"{os.path.splitext(uploaded_file.name)[0]}"
            "_shortform.edl"
        )

        st.markdown(
            f"""
            <div class="download-card">

                <div class="download-card-title">
                    EDL 파일 준비 완료
                </div>

                <div class="download-card-description">
                    파일명:
                    <strong>{edl_filename}</strong>
                    <br>
                    총 {len(highlights)}개의
                    숏폼 하이라이트가 포함되어 있습니다.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        st.download_button(
            label="EDIUS 연동 EDL 파일 다운로드",
            data=edl_content,
            file_name=edl_filename,
            mime="text/plain",
            use_container_width=True,
            help=(
                "생성된 CMX 3600 EDL 파일을 "
                "컴퓨터에 저장합니다."
            ),
        )

        # ======================================================================
        # Footer
        # ======================================================================

        st.markdown(
            """
            <footer class="app-footer">
                News Shortform AI Editor
                · Groq Whisper STT
                · Gemini AI
                · EDIUS EDL
            </footer>
            """,
            unsafe_allow_html=True,
        )

    except Exception as error:

        st.error(
            "파일을 처리하는 동안 문제가 발생했습니다."
        )

        st.write(
            "파일 형식, 음성 포함 여부, "
            "인터넷 연결 상태를 확인한 후 다시 시도해 주세요."
        )

        # 개발 환경에서만 상세 오류 표시
        if (
            os.getenv(
                "APP_DEBUG",
                "false",
            ).lower()
            == "true"
        ):

            st.exception(error)

    finally:

        # ======================================================================
        # 임시 파일 정리
        # ======================================================================

        if (
            raw_input_path
            and os.path.exists(
                raw_input_path
            )
        ):

            try:
                os.remove(
                    raw_input_path
                )
            except OSError:
                pass

        if (
            processed_audio_path
            and os.path.exists(
                processed_audio_path
            )
        ):

            try:
                os.remove(
                    processed_audio_path
                )
            except OSError:
                pass


# ==============================================================================
# 9. 실행
# ==============================================================================

if __name__ == "__main__":
    main()
