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
# 2. 접근성을 고려한 기본 UI
# ==============================================================================

st.title("뉴스 숏폼 하이라이트 자동 추출기")

st.write(
    "뉴스 음성 또는 영상 파일을 업로드하면 "
    "Groq Whisper로 자막과 타임코드를 추출하고, "
    "Gemini AI가 숏폼 제작에 적합한 구간을 선정합니다."
)

st.info(
    "처리 결과는 EDIUS에서 사용할 수 있는 EDL 파일로 다운로드할 수 있습니다."
)

st.divider()


# ==============================================================================
# 3. 유틸리티 함수
# ==============================================================================

def prepare_audio_for_groq(input_file_path: str) -> str:
    """
    대용량 영상/음성 파일을 Groq API 전송 기준에 맞춰
    16kHz / mono / 32kbps MP3로 변환한다.
    """

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


def seconds_to_df_timecode(seconds: float) -> str:
    """
    초 단위 시간을 NTSC Drop Frame Timecode
    29.97fps / HH:MM:SS;FF 형식으로 변환한다.
    """

    seconds = max(0.0, float(seconds))

    total_frames = int(round(seconds * 29.97))

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


def seconds_to_min_sec(seconds: float) -> str:
    """
    UI 표시용 mm:ss 변환.
    """

    seconds = max(0, int(seconds))

    minutes, seconds = divmod(
        seconds,
        60,
    )

    return f"{minutes:02d}:{seconds:02d}"


def get_media_duration(file_path: str) -> float:
    """
    FFprobe를 이용해 원본 미디어의 전체 재생 시간을 가져온다.
    """

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

        return float(result.stdout.strip())

    except (
        subprocess.CalledProcessError,
        ValueError,
    ):
        return 0.0


def generate_edl(
    highlights: list,
    reel_name: str = "AX0101",
) -> str:
    """
    EDIUS 연동 CMX 3600 EDL 생성.
    """

    edl_lines = [
        "TITLE: NEWS_SHORTFORM_HIGHLIGHTS",
        "FMT: NTSC DF",
        "",
    ]

    for idx, item in enumerate(
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
            f"{idx:03d}  "
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
    """
    Groq Whisper API를 호출하여
    타임코드가 포함된 verbose_json을 반환한다.
    """

    with open(
        audio_path,
        "rb",
    ) as file:

        transcription = client.audio.transcriptions.create(
            file=(
                os.path.basename(audio_path),
                file.read(),
            ),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="ko",
        )

    return transcription.segments


# ==============================================================================
# 5. 하이라이트 데이터 검증
# ==============================================================================

def sanitize_and_fix_highlights(
    raw_highlights: list,
    media_duration: float = 0.0,
) -> list:
    """
    Gemini 결과를 Python 단계에서 다시 검증한다.

    WCAG와 직접적인 관련은 없지만,
    사용자에게 잘못된 시간 정보를 보여주는 것을 방지하기 위한
    데이터 무결성 검증이다.
    """

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

            # ----------------------------------------------------------
            # 1. 음수 방지
            # ----------------------------------------------------------

            start_time = max(
                0.0,
                start_time,
            )

            end_time = max(
                0.0,
                end_time,
            )

            # ----------------------------------------------------------
            # 2. 시작/종료 역전 방지
            # ----------------------------------------------------------

            if start_time > end_time:
                start_time, end_time = (
                    end_time,
                    start_time,
                )

            # ----------------------------------------------------------
            # 3. 미디어 길이를 넘어가는 경우 제한
            # ----------------------------------------------------------

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
                end_time - start_time
            )

            # ----------------------------------------------------------
            # 4. 최소 30초 조건
            # ----------------------------------------------------------

            if duration < 30.0:

                candidate_end = (
                    start_time + 30.0
                )

                if (
                    media_duration > 0
                    and candidate_end > media_duration
                ):
                    continue

                end_time = candidate_end

            # ----------------------------------------------------------
            # 5. 최대 60초 조건
            # ----------------------------------------------------------

            duration = (
                end_time - start_time
            )

            if duration > 60.0:
                end_time = (
                    start_time + 60.0
                )

            # ----------------------------------------------------------
            # 6. 최종 검증
            # ----------------------------------------------------------

            duration = (
                end_time - start_time
            )

            if not (
                start_time < end_time
            ):
                continue

            if not (
                30.0 <= duration <= 60.0
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

            fixed_list.append(item)

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

            clean_id = model_id.replace(
                "models/",
                "",
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
        final_models = preferred_models

    # ------------------------------------------------------------------
    # 타임코드가 포함된 transcript 생성
    # ------------------------------------------------------------------

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
                f"[{start:.2f}s ~ {end:.2f}s] {text}"
            )

    transcript_text = "\n".join(
        formatted_transcript
    )

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

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

9. 타임코드는 반드시 제공된 자막의 타임코드를 기준으로 한다.

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
                        "description": (
                            "메인 타이틀. "
                            "15자 이내."
                        ),
                    },
                    "sub_title": {
                        "type": "STRING",
                        "description": (
                            "핵심 요약. "
                            "25자 이내."
                        ),
                    },
                    "start_time": {
                        "type": "NUMBER",
                        "description": (
                            "구간 시작 시간. "
                            "초 단위 실수."
                        ),
                    },
                    "end_time": {
                        "type": "NUMBER",
                        "description": (
                            "구간 종료 시간. "
                            "초 단위 실수."
                        ),
                    },
                    "reason": {
                        "type": "STRING",
                        "description": (
                            "해당 구간을 "
                            "선정한 이유."
                        ),
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

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gen_config,
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

            # 정확히 3개가 아니면 다음 모델을 시도
            if len(sanitized_data) != 3:
                last_exception = RuntimeError(
                    "Gemini가 유효한 하이라이트 3개를 반환하지 않았습니다."
                )
                continue

            return sanitized_data

        except Exception as error:

            last_exception = error

            continue

    raise RuntimeError(
        "하이라이트 추출에 실패했습니다. "
        "잠시 후 다시 시도해 주세요."
    ) from last_exception


# ==============================================================================
# 7. API 키 확인
# ==============================================================================

def get_api_keys():
    """
    Streamlit Secrets 또는 .env에서 API 키를 가져온다.
    """

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
# 8. 메인 UI
# ==============================================================================

def main():

    groq_api_key, gemini_api_key = (
        get_api_keys()
    )

    if not groq_api_key or not gemini_api_key:

        st.error(
            "API 키가 설정되지 않았습니다."
        )

        st.write(
            "관리자에게 GROQ_API_KEY와 "
            "GEMINI_API_KEY 설정을 요청해 주세요."
        )

        st.stop()

    groq_client = Groq(
        api_key=groq_api_key
    )

    # ------------------------------------------------------------------
    # 파일 업로드
    # ------------------------------------------------------------------

    st.header("1. 뉴스 파일 업로드")

    st.write(
        "지원 파일 형식: MP3, MP4, TS, MOV, M4A, WAV"
    )

    st.write(
        "최대 업로드 용량: 1GB"
    )

    uploaded_file = st.file_uploader(
        "뉴스 음성 또는 영상 파일을 선택하세요.",
        type=[
            "mp3",
            "mp4",
            "ts",
            "mov",
            "m4a",
            "wav",
        ],
        help=(
            "뉴스 음성 또는 영상 파일을 "
            "선택하면 하이라이트 구간을 자동으로 분석합니다."
        ),
    )

    if uploaded_file is None:

        st.info(
            "분석할 뉴스 파일을 선택하면 "
            "하이라이트 추출을 시작할 수 있습니다."
        )

        return

    # ------------------------------------------------------------------
    # 업로드 정보
    # ------------------------------------------------------------------

    file_size_mb = (
        uploaded_file.size
        / (1024 * 1024)
    )

    st.success(
        f"파일이 선택되었습니다: "
        f"{uploaded_file.name}"
    )

    st.write(
        f"파일 크기: {file_size_mb:.2f}MB"
    )

    # ------------------------------------------------------------------
    # 실제 업로드 제한 검사
    # ------------------------------------------------------------------

    max_file_size = (
        1024 * 1024 * 1024
    )

    if uploaded_file.size > max_file_size:

        st.error(
            "파일 크기가 1GB를 초과합니다. "
            "1GB 이하의 파일을 선택해 주세요."
        )

        return

    # ------------------------------------------------------------------
    # 실행 버튼
    # ------------------------------------------------------------------

    st.header("2. 하이라이트 분석")

    start_button = st.button(
        "하이라이트 추출 및 EDL 생성 시작",
        type="primary",
        use_container_width=True,
        help=(
            "업로드한 뉴스 파일을 분석하여 "
            "숏폼 하이라이트와 EDL 파일을 생성합니다."
        ),
    )

    if not start_button:
        return

    raw_input_path = None
    processed_audio_path = None

    try:

        # ==============================================================
        # 진행 상태
        # ==============================================================

        with st.status(
            "뉴스 파일을 분석하고 있습니다.",
            expanded=True,
        ) as status:

            # ----------------------------------------------------------
            # 1단계
            # ----------------------------------------------------------

            st.write(
                "1단계: 파일 저장 및 오디오 최적화를 진행합니다."
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

                    chunk = uploaded_file.read(
                        chunk_size
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
                "파일 저장 및 오디오 최적화가 완료되었습니다."
            )

            # ----------------------------------------------------------
            # 2단계
            # ----------------------------------------------------------

            st.write(
                "2단계: 음성을 분석하여 자막과 타임코드를 추출합니다."
            )

            segments = run_whisper_stt(
                groq_client,
                processed_audio_path,
            )

            if not segments:

                raise RuntimeError(
                    "음성에서 자막을 추출하지 못했습니다. "
                    "음성이 포함된 파일인지 확인해 주세요."
                )

            st.write(
                f"자막 구간 {len(segments)}개를 추출했습니다."
            )

            # ----------------------------------------------------------
            # 3단계
            # ----------------------------------------------------------

            st.write(
                "3단계: AI가 숏폼 하이라이트 구간을 선정합니다."
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
                    "유효한 하이라이트 3개를 "
                    "생성하지 못했습니다."
                )

            st.write(
                "하이라이트 3개를 선정했습니다."
            )

            # ----------------------------------------------------------
            # 4단계
            # ----------------------------------------------------------

            st.write(
                "4단계: EDIUS용 EDL 파일을 생성합니다."
            )

            edl_content = generate_edl(
                highlights
            )

            st.write(
                "EDL 파일 생성이 완료되었습니다."
            )

            status.update(
                label="뉴스 하이라이트 분석이 완료되었습니다.",
                state="complete",
                expanded=False,
            )

        # ==============================================================
        # 결과
        # ==============================================================

        st.header("3. 추천 숏폼 하이라이트")

        st.write(
            "AI가 선정한 3개의 하이라이트입니다. "
            "각 구간은 30초 이상 60초 이하로 검증되었습니다."
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
                end_sec - start_sec,
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
                f"하이라이트 {index}: {title}",
                expanded=(index == 1),
            ):

                st.subheader(
                    f"하이라이트 {index}"
                )

                st.write(
                    f"제목: {title}"
                )

                st.write(
                    f"요약: {subtitle}"
                )

                st.write(
                    "타임코드: "
                    f"{seconds_to_df_timecode(start_sec)} "
                    "부터 "
                    f"{seconds_to_df_timecode(end_sec)}"
                )

                st.write(
                    "재생 시간: "
                    f"{seconds_to_min_sec(start_sec)} "
                    "부터 "
                    f"{seconds_to_min_sec(end_sec)} "
                    f"({duration:.1f}초)"
                )

                st.write(
                    f"선정 이유: {reason}"
                )

        # ==============================================================
        # 다운로드
        # ==============================================================

        st.divider()

        st.header("4. EDIUS용 EDL 파일")

        st.write(
            "아래 버튼을 선택하면 생성된 EDL 파일을 "
            "다운로드할 수 있습니다."
        )

        edl_filename = (
            f"{os.path.splitext(uploaded_file.name)[0]}"
            "_shortform.edl"
        )

        st.download_button(
            label="EDIUS 연동 EDL 파일 다운로드",
            data=edl_content,
            file_name=edl_filename,
            mime="text/plain",
            use_container_width=True,
            help=(
                "생성된 EDIUS용 CMX 3600 EDL 파일을 "
                "컴퓨터에 저장합니다."
            ),
        )

    except Exception as error:

        st.error(
            "파일을 처리하는 동안 문제가 발생했습니다."
        )

        st.write(
            "다음 사항을 확인한 후 다시 시도해 주세요."
        )

        st.write(
            "• 파일이 정상적으로 재생되는지 확인하세요."
        )

        st.write(
            "• 음성이 포함된 파일인지 확인하세요."
        )

        st.write(
            "• 인터넷 연결 상태를 확인하세요."
        )

        st.write(
            "• 문제가 계속되면 관리자에게 문의하세요."
        )

        # 개발 환경에서만 상세 오류 표시
        if os.getenv(
            "APP_DEBUG",
            "false",
        ).lower() == "true":

            st.exception(error)

    finally:

        # ==============================================================
        # 임시 파일 삭제
        # ==============================================================

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
