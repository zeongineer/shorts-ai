import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
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
# 2. 디자인 / CSS
# ==============================================================================

CUSTOM_CSS = """
<style>

/* -------------------------------------------------------------------------- */
/* 전체 기본 설정 */
/* -------------------------------------------------------------------------- */

html,
body,
[class*="css"] {
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        "Noto Sans KR",
        "Malgun Gothic",
        Arial,
        sans-serif;
}

.stApp {
    background: #f5f7fb;
}

.block-container {
    max-width: 1280px;
    padding-top: 2.2rem;
    padding-bottom: 4rem;
}


/* -------------------------------------------------------------------------- */
/* 상단 헤더 */
/* -------------------------------------------------------------------------- */

.app-header {
    background: linear-gradient(
        135deg,
        #111827 0%,
        #1f2937 55%,
        #111827 100%
    );

    border-radius: 20px;
    padding: 32px 36px;
    margin-bottom: 28px;

    box-shadow:
        0 12px 30px rgba(15, 23, 42, 0.12);

    color: white;
}

.app-header-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;

    padding: 6px 12px;
    margin-bottom: 14px;

    border-radius: 999px;

    background: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.14);

    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.02em;
}

.app-header-title {
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.04em;

    margin: 0 0 10px 0;
}

.app-header-description {
    font-size: 15px;
    line-height: 1.7;

    color: rgba(255, 255, 255, 0.78);

    margin: 0;
}


/* -------------------------------------------------------------------------- */
/* 섹션 타이틀 */
/* -------------------------------------------------------------------------- */

.section-title {
    display: flex;
    align-items: center;
    gap: 12px;

    margin-top: 28px;
    margin-bottom: 14px;
}

.section-number {
    display: inline-flex;

    width: 30px;
    height: 30px;

    align-items: center;
    justify-content: center;

    border-radius: 9px;

    background: #111827;
    color: white;

    font-size: 13px;
    font-weight: 800;
}

.section-title-text {
    font-size: 20px;
    font-weight: 800;

    color: #111827;

    letter-spacing: -0.025em;
}


/* -------------------------------------------------------------------------- */
/* 정보 카드 */
/* -------------------------------------------------------------------------- */

.info-card {
    background: white;

    border: 1px solid #e5e7eb;
    border-radius: 16px;

    padding: 20px 22px;

    box-shadow:
        0 5px 18px rgba(15, 23, 42, 0.045);

    margin-bottom: 16px;
}

.info-card-title {
    font-size: 15px;
    font-weight: 700;

    color: #111827;

    margin-bottom: 6px;
}

.info-card-text {
    font-size: 13px;
    line-height: 1.65;

    color: #6b7280;
}


/* -------------------------------------------------------------------------- */
/* 파일 정보 */
/* -------------------------------------------------------------------------- */

.file-info-card {
    background: white;

    border: 1px solid #e5e7eb;
    border-radius: 16px;

    padding: 18px 20px;

    margin-top: 14px;
    margin-bottom: 18px;
}

.file-name {
    font-size: 16px;
    font-weight: 700;

    color: #111827;

    word-break: break-all;
}

.file-meta {
    margin-top: 6px;

    font-size: 13px;

    color: #6b7280;
}


/* -------------------------------------------------------------------------- */
/* 하이라이트 카드 */
/* -------------------------------------------------------------------------- */

.highlight-card {
    background: white;

    border: 1px solid #e5e7eb;
    border-radius: 18px;

    padding: 22px;

    margin-bottom: 16px;

    box-shadow:
        0 7px 22px rgba(15, 23, 42, 0.055);
}

.highlight-top {
    display: flex;

    align-items: flex-start;
    justify-content: space-between;

    gap: 20px;

    margin-bottom: 18px;
}

.highlight-number {
    font-size: 12px;
    font-weight: 800;

    color: #2563eb;

    margin-bottom: 5px;
}

.highlight-title {
    font-size: 20px;
    font-weight: 800;

    color: #111827;

    letter-spacing: -0.025em;

    margin: 0;
}

.highlight-subtitle {
    font-size: 13px;

    color: #6b7280;

    margin-top: 6px;
}

.duration-badge {
    flex-shrink: 0;

    padding: 7px 11px;

    border-radius: 999px;

    background: #eff6ff;
    color: #2563eb;

    font-size: 12px;
    font-weight: 800;
}

.highlight-grid {
    display: grid;

    grid-template-columns:
        repeat(3, minmax(0, 1fr));

    gap: 10px;

    margin-bottom: 16px;
}

.metric-box {
    background: #f8fafc;

    border: 1px solid #eef2f7;

    border-radius: 12px;

    padding: 13px 14px;
}

.metric-label {
    font-size: 11px;
    font-weight: 700;

    color: #9ca3af;

    margin-bottom: 5px;
}

.metric-value {
    font-size: 14px;
    font-weight: 750;

    color: #1f2937;

    font-variant-numeric: tabular-nums;
}

.reason-box {
    background: #f8fafc;

    border-left: 3px solid #2563eb;

    border-radius: 0 10px 10px 0;

    padding: 13px 15px;
}

.reason-label {
    font-size: 11px;
    font-weight: 800;

    color: #6b7280;

    margin-bottom: 4px;
}

.reason-text {
    font-size: 13px;

    color: #374151;

    line-height: 1.65;
}


/* -------------------------------------------------------------------------- */
/* 다운로드 카드 */
/* -------------------------------------------------------------------------- */

.download-card {
    background: linear-gradient(
        135deg,
        #ffffff 0%,
        #f8fafc 100%
    );

    border: 1px solid #dbe3ef;
    border-radius: 18px;

    padding: 22px;

    margin-top: 18px;
}

.download-title {
    font-size: 17px;
    font-weight: 800;

    color: #111827;

    margin-bottom: 5px;
}

.download-description {
    font-size: 13px;

    color: #6b7280;

    margin-bottom: 14px;
}


/* -------------------------------------------------------------------------- */
/* Streamlit 기본 버튼 */
/* -------------------------------------------------------------------------- */

.stButton > button,
.stDownloadButton > button {
    border-radius: 11px;

    min-height: 44px;

    font-weight: 700;

    border: 1px solid #d1d5db;

    transition:
        transform 0.15s ease,
        box-shadow 0.15s ease,
        background 0.15s ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    transform: translateY(-1px);

    box-shadow:
        0 7px 18px rgba(15, 23, 42, 0.10);
}


/* Primary button */

.stButton > button[kind="primary"] {
    background: #111827;

    border-color: #111827;

    color: white;
}

.stButton > button[kind="primary"]:hover {
    background: #1f2937;

    border-color: #1f2937;
}


/* -------------------------------------------------------------------------- */
/* 파일 업로더 */
/* -------------------------------------------------------------------------- */

[data-testid="stFileUploader"] {
    background: white;

    border: 1px dashed #cbd5e1;

    border-radius: 16px;

    padding: 8px;

    transition:
        border-color 0.15s ease,
        background 0.15s ease;
}

[data-testid="stFileUploader"]:hover {
    border-color: #94a3b8;

    background: #fafcff;
}


/* -------------------------------------------------------------------------- */
/* Expander */
/* -------------------------------------------------------------------------- */

[data-testid="stExpander"] {
    border: 1px solid #e5e7eb;

    border-radius: 14px;

    overflow: hidden;

    background: white;
}


/* -------------------------------------------------------------------------- */
/* Status */
/* -------------------------------------------------------------------------- */

[data-testid="stStatusWidget"] {
    border-radius: 14px;
}


/* -------------------------------------------------------------------------- */
/* Alert */
/* -------------------------------------------------------------------------- */

[data-testid="stAlert"] {
    border-radius: 12px;
}


/* -------------------------------------------------------------------------- */
/* 모바일 대응 */
/* -------------------------------------------------------------------------- */

@media (max-width: 768px) {

    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .app-header {
        padding: 25px 22px;
        border-radius: 16px;
    }

    .app-header-title {
        font-size: 24px;
    }

    .highlight-grid {
        grid-template-columns: 1fr;
    }

    .highlight-top {
        flex-direction: column;
    }

    .duration-badge {
        align-self: flex-start;
    }
}

</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==============================================================================
# 3. 상단 헤더
# ==============================================================================

st.markdown(
    """
    <div class="app-header">
        <div class="app-header-badge">
            🎬 BROADCAST SHORTFORM TOOL
        </div>

        <h1 class="app-header-title">
            뉴스 숏폼 하이라이트 자동 추출기
        </h1>

        <p class="app-header-description">
            뉴스 음성 또는 영상에서 음성을 자동으로 분석하고,
            AI가 숏폼 제작에 적합한 핵심 구간을 선정합니다.
            최종 결과는 EDIUS에서 활용할 수 있는 EDL 파일로 제공합니다.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 4. 유틸리티
# ==============================================================================

SUPPORTED_EXTENSIONS = [
    "mp3",
    "mp4",
    "ts",
    "mov",
    "m4a",
    "wav",
]

MAX_UPLOAD_SIZE = 1024 * 1024 * 1024

TRANSCRIPTION_CHUNK_SECONDS = 600
TRANSCRIPTION_OVERLAP_SECONDS = 1


def safe_float(value: Any, default: float = 0.0) -> float:
    """값을 안전하게 float으로 변환한다."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_segment_value(
    segment: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Groq segment가 dict 또는 객체 형태로 반환되는 경우
    모두 대응한다.
    """

    if isinstance(segment, dict):
        return segment.get(key, default)

    return getattr(
        segment,
        key,
        default,
    )


def seconds_to_df_timecode(
    seconds: float,
) -> str:
    """
    29.97fps NTSC Drop Frame
    HH:MM:SS;FF 형식.
    """

    seconds = max(
        0.0,
        safe_float(seconds),
    )

    total_frames = int(
        round(seconds * 29.97)
    )

    frames_per_10_minutes = 17982

    ten_minute_blocks = (
        total_frames
        // frames_per_10_minutes
    )

    remaining_frames = (
        total_frames
        % frames_per_10_minutes
    )

    dropped_frames = (
        18 * ten_minute_blocks
    )

    if remaining_frames >= 2:
        dropped_frames += (
            2
            * (
                (remaining_frames - 2)
                // 1798
            )
        )

    total_frames += dropped_frames

    frames = total_frames % 30

    total_seconds = (
        total_frames // 30
    )

    seconds_part = (
        total_seconds % 60
    )

    total_minutes = (
        total_seconds // 60
    )

    minutes_part = (
        total_minutes % 60
    )

    hours_part = (
        total_minutes // 60
    )

    return (
        f"{hours_part:02d}:"
        f"{minutes_part:02d}:"
        f"{seconds_part:02d};"
        f"{frames:02d}"
    )


def seconds_to_min_sec(
    seconds: float,
) -> str:
    """UI용 MM:SS."""

    total_seconds = max(
        0,
        int(seconds),
    )

    minutes, seconds = divmod(
        total_seconds,
        60,
    )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def get_media_duration(
    file_path: str,
) -> float:
    """FFprobe로 미디어 전체 길이를 가져온다."""

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

        return max(
            0.0,
            float(
                result.stdout.strip()
            ),
        )

    except (
        subprocess.CalledProcessError,
        ValueError,
        FileNotFoundError,
    ):

        return 0.0


# ==============================================================================
# 5. FFmpeg
# ==============================================================================

def prepare_audio_for_groq(
    input_file_path: str,
) -> str:
    """
    영상/음성을 Groq Whisper용
    16kHz / mono / 32kbps MP3로 변환한다.
    """

    output_temp_file = (
        tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3",
        )
    )

    output_path = (
        output_temp_file.name
    )

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
        "-map",
        "0:a:0",
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

    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as error:

        if os.path.exists(
            output_path
        ):
            os.remove(
                output_path
            )

        raise RuntimeError(
            "FFmpeg 오디오 변환에 실패했습니다. "
            "FFmpeg가 설치되어 있는지 확인해 주세요."
        ) from error


def split_audio_for_transcription(
    audio_path: str,
) -> list[str]:
    """
    긴 오디오를 Groq 전송에 적합하도록
    10분 단위로 분할한다.

    각 chunk에는 1초 overlap을 적용한다.
    """

    duration = get_media_duration(
        audio_path
    )

    if duration <= 0:
        raise RuntimeError(
            "오디오 길이를 확인할 수 없습니다."
        )

    chunk_paths = []

    start = 0.0

    while start < duration:

        remaining = (
            duration - start
        )

        if remaining <= (
            TRANSCRIPTION_CHUNK_SECONDS
        ):
            chunk_duration = remaining
        else:
            chunk_duration = (
                TRANSCRIPTION_CHUNK_SECONDS
                + TRANSCRIPTION_OVERLAP_SECONDS
            )

        output_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3",
        )

        output_path = (
            output_file.name
        )

        output_file.close()

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            audio_path,
            "-t",
            str(chunk_duration),
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-b:a",
            "32k",
            "-map",
            "0:a:0",
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

            chunk_paths.append(
                output_path
            )

        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):

            if os.path.exists(
                output_path
            ):
                os.remove(
                    output_path
                )

            raise RuntimeError(
                "긴 오디오 파일 분할에 실패했습니다."
            )

        start += (
            TRANSCRIPTION_CHUNK_SECONDS
        )

    return chunk_paths


# ==============================================================================
# 6. Groq Whisper
# ==============================================================================

def transcribe_single_audio(
    client: Groq,
    audio_path: str,
) -> list[dict]:
    """하나의 오디오 파일을 Whisper로 분석한다."""

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
                timestamp_granularities=[
                    "segment"
                ],
                language="ko",
                temperature=0.0,
            )
        )

    segments = (
        getattr(
            transcription,
            "segments",
            None,
        )
        or []
    )

    result = []

    for segment in segments:

        start = safe_float(
            get_segment_value(
                segment,
                "start",
                0.0,
            )
        )

        end = safe_float(
            get_segment_value(
                segment,
                "end",
                0.0,
            )
        )

        text = str(
            get_segment_value(
                segment,
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        if end <= start:
            continue

        result.append(
            {
                "start": start,
                "end": end,
                "text": text,
            }
        )

    return result


def run_whisper_stt(
    client: Groq,
    audio_path: str,
) -> list[dict]:
    """
    긴 오디오를 안전하게 분할하여
    전체 타임코드 기준으로 다시 합친다.
    """

    duration = get_media_duration(
        audio_path
    )

    if duration <= 0:
        raise RuntimeError(
            "오디오 길이를 확인할 수 없습니다."
        )

    chunk_paths = []

    try:

        chunk_paths = (
            split_audio_for_transcription(
                audio_path
            )
        )

        all_segments = []

        for index, chunk_path in enumerate(
            chunk_paths
        ):

            chunk_start = (
                index
                * TRANSCRIPTION_CHUNK_SECONDS
            )

            segments = (
                transcribe_single_audio(
                    client,
                    chunk_path,
                )
            )

            for segment in segments:

                global_start = (
                    chunk_start
                    + segment["start"]
                )

                global_end = (
                    chunk_start
                    + segment["end"]
                )

                if global_start >= duration:
                    continue

                global_end = min(
                    global_end,
                    duration,
                )

                all_segments.append(
                    {
                        "start": round(
                            global_start,
                            2,
                        ),
                        "end": round(
                            global_end,
                            2,
                        ),
                        "text": segment[
                            "text"
                        ],
                    }
                )

        # 시간순 정렬
        all_segments.sort(
            key=lambda item:
            item["start"]
        )

        # overlap으로 인해 발생할 수 있는
        # 중복 segment 제거
        deduplicated = []

        for segment in all_segments:

            duplicate = False

            for existing in reversed(
                deduplicated[-5:]
            ):

                time_difference = abs(
                    segment["start"]
                    - existing["start"]
                )

                if (
                    time_difference < 1.0
                    and segment["text"].strip()
                    == existing["text"].strip()
                ):
                    duplicate = True
                    break

            if not duplicate:
                deduplicated.append(
                    segment
                )

        return deduplicated

    finally:

        for chunk_path in chunk_paths:

            if os.path.exists(
                chunk_path
            ):

                try:
                    os.remove(
                        chunk_path
                    )
                except OSError:
                    pass


# ==============================================================================
# 7. Highlight 검증
# ==============================================================================

def sanitize_and_fix_highlights(
    raw_highlights: Any,
    media_duration: float = 0.0,
) -> list[dict]:

    fixed_list = []

    if not isinstance(
        raw_highlights,
        list,
    ):
        return fixed_list

    for raw_item in raw_highlights:

        if not isinstance(
            raw_item,
            dict,
        ):
            continue

        try:

            start_time = safe_float(
                raw_item.get(
                    "start_time",
                    0.0,
                )
            )

            end_time = safe_float(
                raw_item.get(
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

            # 30초 미만이면 30초로 확장
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

            # 60초 초과하면 60초로 제한
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
                30.0
                <= duration
                <= 60.0
            ):
                continue

            if not (
                start_time
                < end_time
            ):
                continue

            fixed_item = {
                "main_title": str(
                    raw_item.get(
                        "main_title",
                        "Highlight",
                    )
                ).strip(),

                "sub_title": str(
                    raw_item.get(
                        "sub_title",
                        "",
                    )
                ).strip(),

                "start_time": round(
                    start_time,
                    2,
                ),

                "end_time": round(
                    end_time,
                    2,
                ),

                "reason": str(
                    raw_item.get(
                        "reason",
                        "",
                    )
                ).strip(),
            }

            fixed_list.append(
                fixed_item
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

    return fixed_list


# ==============================================================================
# 8. Gemini
# ==============================================================================

def extract_json_from_response(
    response: Any,
) -> Any:
    """
    Gemini response.text를 안전하게 JSON으로 변환한다.
    """

    text = getattr(
        response,
        "text",
        None,
    )

    if not text:
        raise RuntimeError(
            "Gemini 응답이 비어 있습니다."
        )

    text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:

        # 혹시 ```json ... ``` 형태로 반환된 경우
        if text.startswith(
            "```"
        ):

            text = (
                text.replace(
                    "```json",
                    "",
                )
                .replace(
                    "```",
                    "",
                )
                .strip()
            )

            return json.loads(text)

        raise


def build_transcript_text(
    segments: list[dict],
) -> str:

    formatted = []

    for segment in segments:

        start = safe_float(
            segment.get(
                "start",
                0.0,
            )
        )

        end = safe_float(
            segment.get(
                "end",
                0.0,
            )
        )

        text = str(
            segment.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        formatted.append(
            f"[{start:.2f}s ~ {end:.2f}s] "
            f"{text}"
        )

    return "\n".join(
        formatted
    )


def run_gemini_highlight_extraction(
    gemini_api_key: str,
    segments: list[dict],
    media_duration: float = 0.0,
) -> list[dict]:

    client = genai.Client(
        api_key=gemini_api_key
    )

    # 현재 사용 가능한 안정적인 모델 우선순위
    preferred_models = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-2.5-flash",
    ]

    transcript_text = (
        build_transcript_text(
            segments
        )
    )

    if not transcript_text.strip():
        raise RuntimeError(
            "분석할 자막 데이터가 없습니다."
        )

    prompt = f"""
너는 대한민국 방송사의 뉴스 영상 편집을 담당하는
수석 영상편집자이다.

아래는 뉴스 방송의 음성 자막과 정확한 타임코드이다.

목표는 YouTube Shorts / TikTok / Instagram Reels 등에
사용하기 좋은 뉴스 숏폼 후보 구간 3개를 선정하는 것이다.

반드시 아래 규칙을 지켜라.

[선정 규칙]

1. 정확히 3개의 하이라이트를 반환한다.

2. 각 하이라이트의 길이는
   반드시 30초 이상 60초 이하여야 한다.

3. start_time은 실제 자막 segment의 시작 시간이어야 한다.

4. end_time은 실제 자막 segment의 종료 시간이어야 한다.

5. 문장이나 발언이 중간에서 끊기지 않아야 한다.

6. 하나의 하이라이트만 봐도
   하나의 완전한 뉴스 맥락을 이해할 수 있어야 한다.

7. 단순 인사, 반복 멘트, 의미 없는 연결 멘트는 피한다.

8. 시청자의 관심을 끌 수 있는
   핵심 정보, 사건, 숫자, 변화, 발언,
   반전, 긴급성 또는 사회적 의미가 있는 구간을 우선한다.

9. 서로 지나치게 겹치는 구간은 선택하지 않는다.

10. 제공된 자막에 존재하는 타임코드만 사용한다.

11. start_time < end_time이어야 한다.

12. 영상 전체 길이는 약
    {media_duration:.2f}초이다.

13. main_title은 15자 이내로 작성한다.

14. sub_title은 25자 이내로 작성한다.

15. reason에는 왜 숏폼으로 적합한지 간단하게 설명한다.

[출력 형식]

반드시 JSON 배열만 반환한다.

[
  {{
    "main_title": "제목",
    "sub_title": "핵심 요약",
    "start_time": 10.2,
    "end_time": 48.7,
    "reason": "선정 이유"
  }},
  {{
    "main_title": "제목",
    "sub_title": "핵심 요약",
    "start_time": 80.1,
    "end_time": 125.4,
    "reason": "선정 이유"
  }},
  {{
    "main_title": "제목",
    "sub_title": "핵심 요약",
    "start_time": 150.0,
    "end_time": 195.0,
    "reason": "선정 이유"
  }}
]

[뉴스 자막]

{transcript_text}
"""

    response_schema = {
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
    }

    generation_config = (
        types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.1,
        )
    )

    last_exception = None

    for model_name in preferred_models:

        try:

            response = (
                client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=generation_config,
                )
            )

            raw_data = (
                extract_json_from_response(
                    response
                )
            )

            sanitized = (
                sanitize_and_fix_highlights(
                    raw_data,
                    media_duration,
                )
            )

            if len(sanitized) != 3:

                raise RuntimeError(
                    f"{model_name}이 "
                    f"유효한 하이라이트 3개를 "
                    f"반환하지 않았습니다."
                )

            return sanitized

        except Exception as error:

            last_exception = error
            continue

    raise RuntimeError(
        "Gemini 하이라이트 분석에 실패했습니다. "
        "API 키와 모델 상태를 확인해 주세요."
    ) from last_exception


# ==============================================================================
# 9. EDL
# ==============================================================================

def generate_edl(
    highlights: list[dict],
    reel_name: str = "AX0101",
) -> str:
    """
    CMX 3600 / NTSC DF 기반 EDL 생성.
    """

    lines = [
        "TITLE: NEWS_SHORTFORM_HIGHLIGHTS",
        "FCM: DROP FRAME",
        "",
    ]

    for index, item in enumerate(
        highlights,
        1,
    ):

        start_time = safe_float(
            item.get(
                "start_time",
                0.0,
            )
        )

        end_time = safe_float(
            item.get(
                "end_time",
                0.0,
            )
        )

        src_in = (
            seconds_to_df_timecode(
                start_time
            )
        )

        src_out = (
            seconds_to_df_timecode(
                end_time
            )
        )

        # EDL 이벤트 라인
        lines.append(
            f"{index:03d}  "
            f"{reel_name:<8} "
            f"V     C        "
            f"{src_in} "
            f"{src_out} "
            f"{src_in} "
            f"{src_out}"
        )

        title = str(
            item.get(
                "main_title",
                "Highlight",
            )
        ).replace(
            "\n",
            " ",
        )

        subtitle = str(
            item.get(
                "sub_title",
                "",
            )
        ).replace(
            "\n",
            " ",
        )

        reason = str(
            item.get(
                "reason",
                "",
            )
        ).replace(
            "\n",
            " ",
        )

        lines.append(
            f"* FROM CLIP: {title}"
        )

        lines.append(
            f"* COMMENTS: {subtitle}"
        )

        lines.append(
            f"* REASON: {reason}"
        )

        lines.append("")

    return "\n".join(
        lines
    )


# ==============================================================================
# 10. API Key
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
# 11. UI Helper
# ==============================================================================

def render_section_title(
    number: int,
    title: str,
):

    st.markdown(
        f"""
        <div class="section-title">
            <div class="section-number">
                {number}
            </div>

            <div class="section-title-text">
                {title}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_highlight_card(
    index: int,
    highlight: dict,
):

    start_sec = safe_float(
        highlight.get(
            "start_time",
            0.0,
        )
    )

    end_sec = safe_float(
        highlight.get(
            "end_time",
            0.0,
        )
    )

    duration = (
        end_sec - start_sec
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

    start_tc = (
        seconds_to_df_timecode(
            start_sec
        )
    )

    end_tc = (
        seconds_to_df_timecode(
            end_sec
        )
    )

    start_display = (
        seconds_to_min_sec(
            start_sec
        )
    )

    end_display = (
        seconds_to_min_sec(
            end_sec
        )
    )

    st.markdown(
        f"""
        <div class="highlight-card">

            <div class="highlight-top">

                <div>
                    <div class="highlight-number">
                        HIGHLIGHT {index}
                    </div>

                    <h3 class="highlight-title">
                        {title}
                    </h3>

                    <div class="highlight-subtitle">
                        {subtitle}
                    </div>
                </div>

                <div class="duration-badge">
                    {duration:.1f}초
                </div>

            </div>

            <div class="highlight-grid">

                <div class="metric-box">
                    <div class="metric-label">
                        START
                    </div>

                    <div class="metric-value">
                        {start_tc}
                    </div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">
                        END
                    </div>

                    <div class="metric-value">
                        {end_tc}
                    </div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">
                        PLAYBACK
                    </div>

                    <div class="metric-value">
                        {start_display}
                        →
                        {end_display}
                    </div>
                </div>

            </div>

            <div class="reason-box">

                <div class="reason-label">
                    AI SELECTION REASON
                </div>

                <div class="reason-text">
                    {reason}
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# 12. Main
# ==============================================================================

def main():

    groq_api_key, gemini_api_key = (
        get_api_keys()
    )

    # --------------------------------------------------------------------------
    # API Key 확인
    # --------------------------------------------------------------------------

    if (
        not groq_api_key
        or not gemini_api_key
    ):

        st.error(
            "API 키가 설정되지 않았습니다."
        )

        st.info(
            "GROQ_API_KEY와 GEMINI_API_KEY를 "
            ".env 또는 Streamlit Secrets에 설정해 주세요."
        )

        st.stop()

    groq_client = Groq(
        api_key=groq_api_key
    )

    # --------------------------------------------------------------------------
    # 1. 업로드
    # --------------------------------------------------------------------------

    render_section_title(
        1,
        "뉴스 파일 업로드",
    )

    st.markdown(
        """
        <div class="info-card">

            <div class="info-card-title">
                분석 가능한 파일
            </div>

            <div class="info-card-text">
                MP3 · MP4 · TS · MOV · M4A · WAV
                <br>
                영상 파일을 업로드하면 음성만 추출하여
                Whisper가 자막과 타임코드를 분석합니다.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 선택하세요.",
        type=SUPPORTED_EXTENSIONS,
        help=(
            "최대 1GB까지 업로드할 수 있습니다. "
            "뉴스 영상 또는 음성 파일을 선택하세요."
        ),
        label_visibility="collapsed",
    )

    if uploaded_file is None:

        st.info(
            "분석할 뉴스 파일을 업로드해 주세요."
        )

        return

    # --------------------------------------------------------------------------
    # 파일 정보
    # --------------------------------------------------------------------------

    file_size_mb = (
        uploaded_file.size
        / (1024 * 1024)
    )

    st.markdown(
        f"""
        <div class="file-info-card">

            <div class="file-name">
                📄 {uploaded_file.name}
            </div>

            <div class="file-meta">
                {file_size_mb:.2f} MB
                ·
                {uploaded_file.type or "알 수 없는 형식"}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    if (
        uploaded_file.size
        > MAX_UPLOAD_SIZE
    ):

        st.error(
            "파일 크기가 1GB를 초과합니다. "
            "1GB 이하의 파일을 선택해 주세요."
        )

        return

    # --------------------------------------------------------------------------
    # 2. 분석
    # --------------------------------------------------------------------------

    render_section_title(
        2,
        "AI 하이라이트 분석",
    )

    st.markdown(
        """
        <div class="info-card">

            <div class="info-card-title">
                분석 과정
            </div>

            <div class="info-card-text">
                ① 원본 미디어 분석
                →
                ② 음성 최적화
                →
                ③ Whisper 자막 추출
                →
                ④ Gemini 하이라이트 선정
                →
                ⑤ EDIUS용 EDL 생성
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    start_button = st.button(
        "🎬 하이라이트 추출 시작",
        type="primary",
        use_container_width=True,
    )

    if not start_button:
        return

    raw_input_path = None
    processed_audio_path = None

    try:

        # ======================================================================
        # 진행 상태
        # ======================================================================

        with st.status(
            "뉴스 파일을 분석하고 있습니다.",
            expanded=True,
        ) as status:

            # ------------------------------------------------------------------
            # Step 1
            # ------------------------------------------------------------------

            st.write(
                "① 원본 파일을 서버에 저장하고 있습니다."
            )

            suffix = Path(
                uploaded_file.name
            ).suffix.lower()

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

            if media_duration <= 0:

                raise RuntimeError(
                    "미디어 재생 시간을 확인하지 못했습니다."
                )

            st.write(
                "✓ 원본 파일 확인 완료"
            )

            st.write(
                "② 음성을 Whisper 분석용으로 변환하고 있습니다."
            )

            processed_audio_path = (
                prepare_audio_for_groq(
                    raw_input_path
                )
            )

            st.write(
                "✓ 오디오 최적화 완료"
            )

            # ------------------------------------------------------------------
            # Step 2
            # ------------------------------------------------------------------

            st.write(
                "③ Groq Whisper가 음성과 타임코드를 분석하고 있습니다."
            )

            segments = (
                run_whisper_stt(
                    groq_client,
                    processed_audio_path,
                )
            )

            if not segments:

                raise RuntimeError(
                    "음성에서 자막을 추출하지 못했습니다."
                )

            st.write(
                f"✓ 자막 {len(segments)}개 구간 추출 완료"
            )

            # ------------------------------------------------------------------
            # Step 3
            # ------------------------------------------------------------------

            st.write(
                "④ Gemini AI가 숏폼에 적합한 구간을 선정하고 있습니다."
            )

            highlights = (
                run_gemini_highlight_extraction(
                    gemini_api_key,
                    segments,
                    media_duration,
                )
            )

            if len(highlights) != 3:

                raise RuntimeError(
                    "유효한 하이라이트 3개를 생성하지 못했습니다."
                )

            st.write(
                "✓ 숏폼 하이라이트 3개 선정 완료"
            )

            # ------------------------------------------------------------------
            # Step 4
            # ------------------------------------------------------------------

            st.write(
                "⑤ EDIUS용 EDL 파일을 생성하고 있습니다."
            )

            edl_content = (
                generate_edl(
                    highlights
                )
            )

            st.write(
                "✓ EDL 생성 완료"
            )

            status.update(
                label=(
                    "분석이 완료되었습니다."
                ),
                state="complete",
                expanded=False,
            )

        # ======================================================================
        # 3. 결과
        # ======================================================================

        render_section_title(
            3,
            "추천 숏폼 하이라이트",
        )

        st.success(
            "AI가 뉴스의 핵심 내용을 기준으로 "
            "숏폼 후보 3개를 선정했습니다."
        )

        for index, highlight in enumerate(
            highlights,
            1,
        ):

            render_highlight_card(
                index,
                highlight,
            )

        # ======================================================================
        # 4. EDL
        # ======================================================================

        render_section_title(
            4,
            "EDIUS용 EDL 파일",
        )

        edl_filename = (
            f"{Path(uploaded_file.name).stem}"
            "_shortform.edl"
        )

        st.markdown(
            """
            <div class="download-card">

                <div class="download-title">
                    EDIUS 편집용 프로젝트 데이터
                </div>

                <div class="download-description">
                    AI가 선정한 3개의 하이라이트 타임코드가
                    CMX 3600 기반 EDL로 저장됩니다.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        st.download_button(
            label="⬇ EDIUS EDL 파일 다운로드",
            data=edl_content,
            file_name=edl_filename,
            mime="text/plain",
            use_container_width=True,
        )

        # ======================================================================
        # 처리 정보
        # ======================================================================

        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "영상 길이",
                seconds_to_min_sec(
                    media_duration
                ),
            )

        with col2:
            st.metric(
                "자막 구간",
                f"{len(segments)}개",
            )

        with col3:
            st.metric(
                "하이라이트",
                "3개",
            )

    except Exception as error:

        st.error(
            "파일을 처리하는 동안 문제가 발생했습니다."
        )

        st.warning(
            "파일 형식, 음성 포함 여부, "
            "FFmpeg 설치 상태 또는 API 연결 상태를 확인해 주세요."
        )

        # 개발 환경에서만 상세 오류
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
        # 임시 파일 삭제
        # ======================================================================

        for path in [
            raw_input_path,
            processed_audio_path,
        ]:

            if (
                path
                and os.path.exists(path)
            ):

                try:
                    os.remove(path)

                except OSError:
                    pass


# ==============================================================================
# 13. 실행
# ==============================================================================

if __name__ == "__main__":
    main()
