import os
import json
import subprocess
import tempfile
from typing import Any, List, Dict

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types


# ============================================================
# 1. 환경 및 페이지 설정
# ============================================================

load_dotenv()

st.set_page_config(
    page_title="뉴스 숏폼 하이라이트 추출기",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# 2. 프로페셔널 라이트 테마 + WCAG AA 접근성 CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ========================================================
       Global
       ======================================================== */

    :root {
        --primary: #2563EB;
        --primary-dark: #1D4ED8;
        --text-primary: #0F172A;
        --text-secondary: #334155;
        --text-muted: #64748B;
        --border: #E2E8F0;
        --border-strong: #CBD5E1;
        --background: #F8FAFC;
        --white: #FFFFFF;
        --success: #16A34A;
        --warning: #D97706;
        --danger: #B91C1C;
    }

    .stApp {
        background: #F8FAFC;
    }

    .main .block-container {
        max-width: 1380px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* Streamlit 기본 상단 여백 */

    header[data-testid="stHeader"] {
        background: transparent;
    }


    /* ========================================================
       Header
       ======================================================== */

    .title-container {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 26px 30px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.035);
    }

    .title-eyebrow {
        color: #2563EB;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 7px;
    }

    .main-title {
        font-size: 2.15rem;
        font-weight: 800;
        color: #0F172A;
        margin: 0 0 8px 0;
        letter-spacing: -0.035em;
        line-height: 1.25;
    }

    .sub-title {
        font-size: 0.98rem;
        color: #334155;
        margin: 0;
        line-height: 1.7;
    }


    /* ========================================================
       Accessibility Alert
       ======================================================== */

    .a11y-alert {
        border-radius: 10px;
        padding: 13px 16px;
        margin-bottom: 14px;
        font-size: 0.92rem;
        line-height: 1.55;
        border: 1px solid transparent;
    }

    .a11y-alert-info {
        background-color: #EFF6FF;
        border-color: #BFDBFE;
        color: #1E3A8A;
    }

    .a11y-alert-success {
        background-color: #F0FDF4;
        border-color: #BBF7D0;
        color: #14532D;
    }

    .a11y-alert-error {
        background-color: #FEF2F2;
        border-color: #FECACA;
        color: #7F1D1D;
    }


    /* ========================================================
       Section
       ======================================================== */

    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 28px 0 12px 0;
    }

    .section-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border-radius: 8px;
        background: #EFF6FF;
        color: #1D4ED8;
        font-size: 0.8rem;
        font-weight: 800;
    }

    .section-title {
        color: #0F172A;
        font-size: 1.12rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.015em;
    }

    .section-description {
        color: #64748B;
        font-size: 0.84rem;
        margin: 0 0 12px 40px;
    }


    /* ========================================================
       KPI Cards
       ======================================================== */

    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
        margin: 16px 0 20px 0;
    }

    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 17px 19px;
        min-height: 110px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.035);
        position: relative;
        overflow: hidden;
    }

    .kpi-card::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
        background: #2563EB;
    }

    .kpi-card.green::before {
        background: #16A34A;
    }

    .kpi-card.orange::before {
        background: #D97706;
    }

    .kpi-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }

    .kpi-label {
        color: #64748B;
        font-size: 0.76rem;
        font-weight: 700;
    }

    .kpi-icon {
        width: 30px;
        height: 30px;
        border-radius: 8px;
        background: #EFF6FF;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 15px;
    }

    .kpi-card.green .kpi-icon {
        background: #F0FDF4;
    }

    .kpi-card.orange .kpi-icon {
        background: #FFFBEB;
    }

    .kpi-value {
        color: #0F172A;
        font-size: 1.45rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.2;
    }

    .kpi-unit {
        color: #64748B;
        font-size: 0.76rem;
        font-weight: 600;
        margin-left: 3px;
    }

    .kpi-description {
        color: #94A3B8;
        font-size: 0.68rem;
        margin-top: 5px;
    }


    /* ========================================================
       Progress
       ======================================================== */

    .progress-container {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 20px 22px;
        margin: 16px 0 20px 0;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.035);
    }

    .progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    .progress-title {
        color: #0F172A;
        font-size: 0.95rem;
        font-weight: 700;
    }

    .progress-percent {
        color: #2563EB;
        font-size: 1rem;
        font-weight: 800;
    }

    .progress-track {
        width: 100%;
        height: 9px;
        background: #E2E8F0;
        border-radius: 999px;
        overflow: hidden;
    }

    .progress-fill {
        height: 100%;
        border-radius: 999px;
        transition: width 0.35s ease;
    }

    .progress-status {
        display: flex;
        align-items: center;
        gap: 7px;
        margin-top: 10px;
        color: #475569;
        font-size: 0.82rem;
    }

    .progress-status-icon {
        font-size: 0.9rem;
    }

    .progress-complete {
        color: #15803D;
    }


    /* ========================================================
       Upload Area
       ======================================================== */

    .upload-info {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 14px;
    }

    .upload-info-title {
        color: #0F172A;
        font-size: 0.92rem;
        font-weight: 750;
        margin-bottom: 5px;
    }

    .upload-info-text {
        color: #64748B;
        font-size: 0.8rem;
        line-height: 1.55;
        margin: 0;
    }


    /* ========================================================
       Highlight Cards
       ======================================================== */

    .highlight-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin-top: 14px;
    }

    .highlight-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 20px;
        min-height: 245px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.035);
        transition:
            transform 0.15s ease,
            box-shadow 0.15s ease;
    }

    .highlight-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 7px 18px rgba(15, 23, 42, 0.07);
    }

    .badge {
        background-color: #1D4ED8;
        color: #FFFFFF;
        padding: 5px 9px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 800;
        display: inline-block;
        margin-bottom: 12px;
        letter-spacing: 0.025em;
    }

    .highlight-title {
        margin: 0 0 7px 0;
        color: #0F172A;
        font-size: 1.08rem;
        font-weight: 800;
        line-height: 1.45;
    }

    .highlight-subtitle {
        margin: 0 0 14px 0;
        color: #334155;
        font-size: 0.84rem;
        font-weight: 600;
        line-height: 1.55;
    }

    .time-info {
        background-color: #F8FAFC;
        border-left: 4px solid #1D4ED8;
        padding: 11px 13px;
        font-family: monospace;
        font-size: 0.78rem;
        color: #0F172A;
        margin: 12px 0;
        border-radius: 0 7px 7px 0;
        line-height: 1.7;
    }

    .reason {
        margin: 12px 0 0 0;
        color: #475569;
        font-size: 0.78rem;
        line-height: 1.55;
    }


    /* ========================================================
       EDL Download Area
       ======================================================== */

    .download-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 18px 20px;
        margin-top: 12px;
    }

    .download-title {
        color: #0F172A;
        font-size: 0.92rem;
        font-weight: 750;
        margin-bottom: 5px;
    }

    .download-description {
        color: #64748B;
        font-size: 0.78rem;
        margin-bottom: 12px;
    }


    /* ========================================================
       Step Text
       ======================================================== */

    .step-text {
        color: #0F172A;
        font-size: 0.9rem;
        margin: 4px 0;
        line-height: 1.5;
    }


    /* ========================================================
       Screen Reader Only
       ======================================================== */

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


    /* ========================================================
       Responsive
       ======================================================== */

    @media (max-width: 900px) {

        .kpi-grid {
            grid-template-columns: 1fr;
        }

        .highlight-grid {
            grid-template-columns: 1fr;
        }

        .main-title {
            font-size: 1.75rem;
        }
    }

    @media (max-width: 640px) {

        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .title-container {
            padding: 20px;
        }

        .progress-container {
            padding: 16px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. 접근성 유틸리티
# ============================================================

def set_page_language(lang_code: str = "ko") -> None:
    """
    페이지 전체 언어를 명시적으로 지정하여 스크린리더가
    올바른 발음 규칙을 사용하도록 한다.
    """

    components.html(
        f"""
        <script>
        try {{
            window.parent.document.documentElement.lang = "{lang_code}";
        }} catch (e) {{}}
        </script>
        """,
        height=0,
        width=0,
    )


def focus_element_by_id(element_id: str) -> None:
    """
    비동기로 렌더링되는 Streamlit 콘텐츠에 대해
    지정한 id의 요소로 키보드 포커스를 이동한다.
    """

    components.html(
        f"""
        <script>
        function tryFocus(retries) {{
            try {{
                const el = window.parent.document.getElementById("{element_id}");

                if (el) {{
                    el.focus();
                }} else if (retries > 0) {{
                    setTimeout(() => tryFocus(retries - 1), 150);
                }}

            }} catch (e) {{}}
        }}

        tryFocus(10);
        </script>
        """,
        height=0,
        width=0,
    )


def accessible_alert(
    message: str,
    kind: str = "info",
    icon: str = "",
) -> None:
    """
    WCAG 접근성을 고려한 알림 박스.
    """

    css_class = {
        "info": "a11y-alert-info",
        "success": "a11y-alert-success",
        "error": "a11y-alert-error",
    }.get(
        kind,
        "a11y-alert-info",
    )

    if kind == "error":
        role = "alert"
        aria_live = "assertive"
    else:
        role = "status"
        aria_live = "polite"

    icon_html = (
        f'<span aria-hidden="true">{icon} </span>'
        if icon
        else ""
    )

    st.markdown(
        f"""
        <div
            class="a11y-alert {css_class}"
            role="{role}"
            aria-live="{aria_live}"
        >
            {icon_html}{message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def accessible_step(
    message: str,
    icon: str = "",
) -> None:
    """
    분석 단계 안내용 접근성 텍스트.
    """

    icon_html = (
        f'<span aria-hidden="true">{icon} </span>'
        if icon
        else ""
    )

    st.markdown(
        f"""
        <p
            class="step-text"
            role="status"
            aria-live="polite"
        >
            {icon_html}{message}
        </p>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 4. 헤더 UI
# ============================================================

def render_header() -> None:

    set_page_language("ko")

    st.markdown(
        """
        <div class="title-container">

            <div class="title-eyebrow">
                AI NEWS SHORTFORM EDITOR
            </div>

            <h1 class="main-title">
                <span aria-hidden="true">🎬 </span>
                뉴스 숏폼 하이라이트 자동 추출기
            </h1>

            <p class="sub-title">
                뉴스 음성/영상 파일을 업로드하면
                Groq Whisper가 자막과 타임코드를 추출하고,
                Gemini AI가 30~60초 숏폼 구간과 자막 타이틀을
                자동으로 선정합니다.
            </p>

        </div>
        """,
        unsafe_allow_html=True,
    )

    accessible_alert(
        "처리 결과는 EDIUS 영상 편집 프로그램에서 즉시 사용할 수 있는 EDL 파일로 제공됩니다.",
        kind="info",
        icon="💡",
    )


# ============================================================
# 5. KPI 카드
# ============================================================

def render_kpi_cards(
    media_duration: float = 0.0,
    segment_count: int = 0,
    highlight_count: int = 0,
) -> None:

    if media_duration > 0:
        duration_text = seconds_to_min_sec(
            media_duration
        )
    else:
        duration_text = "—"

    if segment_count > 0:
        segment_text = f"{segment_count:,}"
    else:
        segment_text = "—"

    if highlight_count > 0:
        highlight_text = str(
            highlight_count
        )
    else:
        highlight_text = "—"

    st.markdown(
        f"""
        <section
            class="kpi-grid"
            aria-label="분석 현황"
        >

            <article
                class="kpi-card"
                aria-label="영상 길이"
            >

                <div class="kpi-top">

                    <div class="kpi-label">
                        영상 길이
                    </div>

                    <div
                        class="kpi-icon"
                        aria-hidden="true"
                    >
                        🎞️
                    </div>

                </div>

                <div class="kpi-value">
                    {duration_text}
                    <span class="kpi-unit">
                        분:초
                    </span>
                </div>

                <div class="kpi-description">
                    업로드된 뉴스 미디어 전체 길이
                </div>

            </article>


            <article
                class="kpi-card green"
                aria-label="자막 구간 수"
            >

                <div class="kpi-top">

                    <div class="kpi-label">
                        자막 구간 수
                    </div>

                    <div
                        class="kpi-icon"
                        aria-hidden="true"
                    >
                        📝
                    </div>

                </div>

                <div class="kpi-value">
                    {segment_text}
                    <span class="kpi-unit">
                        개
                    </span>
                </div>

                <div class="kpi-description">
                    Groq Whisper가 추출한 음성 구간
                </div>

            </article>


            <article
                class="kpi-card orange"
                aria-label="추천 클립 수"
            >

                <div class="kpi-top">

                    <div class="kpi-label">
                        추천 클립 수
                    </div>

                    <div
                        class="kpi-icon"
                        aria-hidden="true"
                    >
                        ✂️
                    </div>

                </div>

                <div class="kpi-value">
                    {highlight_text}
                    <span class="kpi-unit">
                        개
                    </span>
                </div>

                <div class="kpi-description">
                    Gemini AI가 선정한 숏폼 하이라이트
                </div>

            </article>

        </section>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 6. 분석 진행률
# ============================================================

def render_analysis_progress(
    placeholder,
    progress: int,
    message: str,
    icon: str = "⏳",
    complete: bool = False,
) -> None:
    """
    분석 진행률 UI.

    실제 외부 API의 내부 진행률을 알 수 없기 때문에
    전체 파이프라인 단계 기준으로 진행률을 표현한다.
    """

    progress = max(
        0,
        min(100, int(progress)),
    )

    if complete:

        percent_color = "#15803D"
        fill_color = "#16A34A"
        status_class = (
            "progress-status progress-complete"
        )

    else:

        percent_color = "#2563EB"
        fill_color = "#2563EB"
        status_class = "progress-status"

    placeholder.markdown(
        f"""
        <section
            class="progress-container"
            aria-label="뉴스 분석 진행률"
            role="region"
        >

            <div class="progress-header">

                <span class="progress-title">
                    뉴스 숏폼 분석 진행률
                </span>

                <span
                    class="progress-percent"
                    style="color: {percent_color};"
                    aria-label="진행률 {progress}%"
                >
                    {progress}%
                </span>

            </div>

            <div
                class="progress-track"
                role="progressbar"
                aria-valuenow="{progress}"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-label="뉴스 숏폼 분석 진행률"
            >

                <div
                    class="progress-fill"
                    style="
                        width: {progress}%;
                        background-color: {fill_color};
                    "
                ></div>

            </div>

            <div
                class="{status_class}"
                role="status"
                aria-live="polite"
            >

                <span
                    class="progress-status-icon"
                    aria-hidden="true"
                >
                    {icon}
                </span>

                <span>
                    {message}
                </span>

            </div>

        </section>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 7. 유틸리티 함수
# ============================================================

def prepare_audio_for_groq(
    input_file_path: str,
) -> str:

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
            f"오디오 변환(ffmpeg) 실패:\n{error_message}"
        )


def seconds_to_df_timecode(
    seconds: float,
) -> str:

    seconds = max(
        0.0,
        float(seconds),
    )

    total_frames = int(
        round(seconds * 29.97)
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
            f"{idx:03d} "
            f"{reel_name:<8} "
            f"AA/V C "
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

    return "\n".join(
        edl_lines
    )


# ============================================================
# 8. Whisper STT
# ============================================================

def extract_segment_data(
    segment: Any,
) -> Dict[str, Any]:

    if isinstance(
        segment,
        dict,
    ):

        return {
            "start": segment.get(
                "start",
                0.0,
            ),
            "end": segment.get(
                "end",
                0.0,
            ),
            "text": segment.get(
                "text",
                "",
            ),
        }

    return {
        "start": getattr(
            segment,
            "start",
            0.0,
        ),
        "end": getattr(
            segment,
            "end",
            0.0,
        ),
        "text": getattr(
            segment,
            "text",
            "",
        ),
    }


def run_whisper_stt(
    client: Groq,
    audio_path: str,
) -> List[Dict[str, Any]]:

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

    raw_segments = (
        getattr(
            transcription,
            "segments",
            [],
        )
        or []
    )

    return [
        extract_segment_data(seg)
        for seg in raw_segments
    ]


# ============================================================
# 9. 데이터 보정
# ============================================================

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

            start_time = max(
                0.0,
                float(
                    item.get(
                        "start_time",
                        0.0,
                    )
                ),
            )

            end_time = max(
                0.0,
                float(
                    item.get(
                        "end_time",
                        0.0,
                    )
                ),
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
                end_time - start_time
            )

            if duration < 30.0:

                candidate_end = (
                    start_time + 30.0
                )

                if (
                    media_duration > 0
                    and candidate_end
                    > media_duration
                ):

                    start_time = max(
                        0.0,
                        media_duration - 30.0,
                    )

                    end_time = (
                        media_duration
                    )

                else:

                    end_time = (
                        candidate_end
                    )

                duration = (
                    end_time - start_time
                )

            if duration > 60.0:

                end_time = (
                    start_time + 60.0
                )

                duration = (
                    end_time - start_time
                )

            if (
                start_time >= end_time
                or not (
                    29.0
                    <= duration
                    <= 61.0
                )
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


# ============================================================
# 10. Gemini 하이라이트 추출
# ============================================================

def run_gemini_highlight_extraction(
    gemini_api_key: str,
    segments: list,
    media_duration: float = 0.0,
) -> list:

    client = genai.Client(
        api_key=gemini_api_key
    )

    preferred_models = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-2.5-flash",
    ]

    formatted_transcript = []

    for segment in segments:

        seg_data = extract_segment_data(
            segment
        )

        start = round(
            float(
                seg_data["start"]
            ),
            2,
        )

        end = round(
            float(
                seg_data["end"]
            ),
            2,
        )

        text = str(
            seg_data["text"]
        ).strip()

        if text:

            formatted_transcript.append(
                f"[{start:.2f}s ~ {end:.2f}s] {text}"
            )

    transcript_text = "\n".join(
        formatted_transcript
    )

    prompt = f"""
너는 뉴스 방송 수석 에디터이자 YouTube Shorts/TikTok 전문 숏폼 에디터이다.

아래 뉴스 자막 데이터의 타임코드를 분석하여 숏폼으로 제작하기 가장 좋은 핵심 구간 3곳을 선정하라.

[필수 규칙]

정확히 3개의 하이라이트를 반환한다.

각 구간의 길이는 반드시 30초 이상 60초 이하여야 한다.

start_time은 선택한 첫 번째 자막의 시작 시간, end_time은 마지막 자막의 종료 시간이어야 한다.

문장이 중간에 잘리지 않는 완전한 뉴스 맥락을 선택하라.

영상 전체 길이는 약 {media_duration:.2f}초이다.

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
                        "description": "메인 타이틀 (15자 이내)",
                    },
                    "sub_title": {
                        "type": "STRING",
                        "description": "핵심 요약 (25자 이내)",
                    },
                    "start_time": {
                        "type": "NUMBER",
                        "description": "시작 시간(초)",
                    },
                    "end_time": {
                        "type": "NUMBER",
                        "description": "종료 시간(초)",
                    },
                    "reason": {
                        "type": "STRING",
                        "description": "선정 이유",
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

    for model_name in preferred_models:

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

            if len(sanitized_data) == 3:

                return sanitized_data

            else:

                last_exception = RuntimeError(
                    f"모델 {model_name}이 "
                    "유효한 3개 구간을 "
                    "반환하지 않았습니다."
                )

        except Exception as error:

            last_exception = error

            continue

    raise RuntimeError(
        "하이라이트 추출에 실패했습니다. "
        "잠시 후 다시 시도해주세요."
    ) from last_exception


# ============================================================
# 11. API 키 가져오기
# ============================================================

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


# ============================================================
# 12. 섹션 헤더
# ============================================================

def render_section_header(
    number: str,
    title: str,
    description: str = "",
) -> None:

    st.markdown(
        f"""
        <div class="section-header">

            <span
                class="section-number"
                aria-hidden="true"
            >
                {number}
            </span>

            <h2 class="section-title">
                {title}
            </h2>

        </div>
        """,
        unsafe_allow_html=True,
    )

    if description:

        st.markdown(
            f"""
            <p class="section-description">
                {description}
            </p>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# 13. 메인 애플리케이션
# ============================================================

def main():

    # --------------------------------------------------------
    # API Key
    # --------------------------------------------------------

    groq_api_key, gemini_api_key = (
        get_api_keys()
    )

    if (
        not groq_api_key
        or not gemini_api_key
    ):

        accessible_alert(
            "API 키가 설정되지 않았습니다.",
            kind="error",
            icon="⚠️",
        )

        accessible_alert(
            "환경 변수 또는 Streamlit Secrets에 "
            "GROQ_API_KEY와 GEMINI_API_KEY를 "
            "설정해 주세요.",
            kind="info",
        )

        st.stop()

    groq_client = Groq(
        api_key=groq_api_key
    )


    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    render_header()

    st.divider()


    # --------------------------------------------------------
    # KPI 고정 영역
    # --------------------------------------------------------

    kpi_placeholder = st.empty()

    with kpi_placeholder.container():

        render_kpi_cards(
            media_duration=0.0,
            segment_count=0,
            highlight_count=0,
        )


    # --------------------------------------------------------
    # 1. 파일 업로드
    # --------------------------------------------------------

    render_section_header(
        "1",
        "뉴스 파일 업로드",
        "분석할 뉴스 음성 또는 영상 파일을 업로드하세요.",
    )

    st.markdown(
        """
        <div class="upload-info">

            <div class="upload-info-title">
                지원 파일 형식
            </div>

            <p class="upload-info-text">
                MP3 · MP4 · TS · MOV · M4A · WAV
                &nbsp;|&nbsp;
                최대 1GB
            </p>

        </div>
        """,
        unsafe_allow_html=True,
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
            "MP3, MP4, TS, MOV 등 "
            "다양한 방송 미디어 포맷을 지원합니다."
        ),
        label_visibility="collapsed",
    )

    if uploaded_file is None:

        accessible_alert(
            "파일을 업로드하시면 하이라이트 분석 및 EDL 생성을 시작할 수 있습니다.",
            kind="info",
            icon="📌",
        )

        return


    # --------------------------------------------------------
    # 업로드 파일 정보
    # --------------------------------------------------------

    file_size_mb = (
        uploaded_file.size
        / (1024 * 1024)
    )

    accessible_alert(
        f"파일 선택 완료: "
        f"<strong>{uploaded_file.name}</strong> "
        f"({file_size_mb:.2f} MB)",
        kind="success",
        icon="📁",
    )

    if uploaded_file.size > (
        1024 * 1024 * 1024
    ):

        accessible_alert(
            "파일 크기가 1GB를 초과합니다. "
            "1GB 이하의 파일을 업로드해 주세요.",
            kind="error",
        )

        return


    # --------------------------------------------------------
    # 2. 분석 시작
    # --------------------------------------------------------

    render_section_header(
        "2",
        "하이라이트 분석",
        "Whisper STT → Gemini AI → EDIUS EDL 순서로 자동 처리됩니다.",
    )

    start_button = st.button(
        "🚀 하이라이트 추출 및 EDL 생성 시작",
        type="primary",
        use_container_width=True,
    )

    if not start_button:
        return


    # --------------------------------------------------------
    # 진행률 고정 영역
    # --------------------------------------------------------

    progress_placeholder = st.empty()

    render_analysis_progress(
        progress_placeholder,
        5,
        "뉴스 미디어 분석을 준비하고 있습니다.",
        icon="🚀",
    )


    # --------------------------------------------------------
    # 임시 파일
    # --------------------------------------------------------

    raw_input_path = None
    processed_audio_path = None


    try:

        # ----------------------------------------------------
        # 전체 분석 상태
        # ----------------------------------------------------

        with st.status(
            "🎬 뉴스 미디어를 분석하는 중입니다...",
            expanded=True,
        ) as status:


            # =================================================
            # STEP 1
            # =================================================

            render_analysis_progress(
                progress_placeholder,
                10,
                "미디어 파일을 준비하고 있습니다.",
                icon="📁",
            )

            accessible_step(
                "임시 파일 저장 및 오디오 변환(16kHz Mono) 중...",
                icon="1️⃣",
            )


            # -------------------------------------------------
            # 임시 파일 저장
            # -------------------------------------------------

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

                raw_input_path = tmp.name


            # -------------------------------------------------
            # 영상 길이 확인
            # -------------------------------------------------

            media_duration = (
                get_media_duration(
                    raw_input_path
                )
            )


            # -------------------------------------------------
            # FFmpeg
            # -------------------------------------------------

            render_analysis_progress(
                progress_placeholder,
                18,
                "FFmpeg로 음성을 16kHz Mono 오디오로 변환하고 있습니다.",
                icon="🎧",
            )

            processed_audio_path = (
                prepare_audio_for_groq(
                    raw_input_path
                )
            )


            render_analysis_progress(
                progress_placeholder,
                30,
                "오디오 변환이 완료되었습니다.",
                icon="✓",
            )


            # =================================================
            # STEP 2 — Whisper
            # =================================================

            render_analysis_progress(
                progress_placeholder,
                35,
                "Groq Whisper AI가 음성을 분석하고 있습니다.",
                icon="🎙️",
            )

            accessible_step(
                "Groq Whisper AI를 활용한 자막 및 타임코드 추출 중...",
                icon="2️⃣",
            )

            segments = run_whisper_stt(
                groq_client,
                processed_audio_path,
            )


            if not segments:

                raise RuntimeError(
                    "음성에서 자막을 추출하지 못했습니다. "
                    "오디오 트랙을 확인해주세요."
                )


            render_analysis_progress(
                progress_placeholder,
                55,
                f"자막 구간 {len(segments):,}개를 성공적으로 추출했습니다.",
                icon="✓",
            )

            accessible_step(
                f"자막 구간 {len(segments)}개 추출 완료",
                icon="✓",
            )


            # =================================================
            # STEP 3 — Gemini
            # =================================================

            render_analysis_progress(
                progress_placeholder,
                60,
                "Gemini AI가 뉴스 맥락을 분석하고 최적의 숏폼 구간을 찾고 있습니다.",
                icon="🤖",
            )

            accessible_step(
                "Gemini AI 기반 숏폼(30~60초) 하이라이트 구간 탐색 중...",
                icon="3️⃣",
            )

            highlights = (
                run_gemini_highlight_extraction(
                    gemini_api_key,
                    segments,
                    media_duration,
                )
            )


            render_analysis_progress(
                progress_placeholder,
                82,
                f"추천 숏폼 구간 {len(highlights)}개를 선정했습니다.",
                icon="✓",
            )


            # -------------------------------------------------
            # KPI 업데이트
            # -------------------------------------------------

            with kpi_placeholder.container():

                render_kpi_cards(
                    media_duration=media_duration,
                    segment_count=len(segments),
                    highlight_count=len(highlights),
                )


            # =================================================
            # STEP 4 — EDL
            # =================================================

            render_analysis_progress(
                progress_placeholder,
                90,
                "EDIUS에서 사용할 수 있도록 EDL 파일을 생성하고 있습니다.",
                icon="🎬",
            )

            accessible_step(
                "EDIUS 연동 EDL (CMX 3600) 파일 생성 중...",
                icon="4️⃣",
            )

            edl_content = generate_edl(
                highlights
            )


            # -------------------------------------------------
            # 완료
            # -------------------------------------------------

            render_analysis_progress(
                progress_placeholder,
                100,
                "분석 및 EDL 파일 생성이 완료되었습니다.",
                icon="✓",
                complete=True,
            )

            status.update(
                label="✅ 분석 및 EDL 파일 생성이 완료되었습니다!",
                state="complete",
                expanded=False,
            )


        # ----------------------------------------------------
        # Screen Reader 완료 알림
        # ----------------------------------------------------

        st.markdown(
            """
            <div
                class="sr-only"
                role="status"
                aria-live="polite"
            >
                분석이 완료되었습니다.
                추천 숏폼 하이라이트 3건이
                아래에 표시됩니다.
            </div>
            """,
            unsafe_allow_html=True,
        )


        # ====================================================
        # 3. 결과
        # ====================================================

        st.markdown(
            """
            <h2
                id="results-heading"
                tabindex="-1"
                style="
                    outline:none;
                    color:#0F172A;
                    font-size:1.12rem;
                    font-weight:800;
                    margin-top:28px;
                "
            >
                3. 추천 숏폼 하이라이트
            </h2>
            """,
            unsafe_allow_html=True,
        )

        focus_element_by_id(
            "results-heading"
        )


        st.markdown(
            """
            <p
                style="
                    color:#64748B;
                    font-size:0.84rem;
                    margin:4px 0 14px 0;
                "
            >
                Gemini AI가 뉴스 맥락과 타임코드를 분석하여
                선정한 30~60초 숏폼 후보입니다.
            </p>
            """,
            unsafe_allow_html=True,
        )


        # ----------------------------------------------------
        # Highlight Grid
        # ----------------------------------------------------

        highlight_cards_html = ""


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
                    f"하이라이트 {index}",
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


            highlight_cards_html += f"""
            <article
                class="highlight-card"
                aria-labelledby="card-title-{index}"
            >

                <span class="badge">
                    SHORTFORM #{index}
                </span>

                <h3
                    id="card-title-{index}"
                    class="highlight-title"
                >
                    {title}
                </h3>

                <p class="highlight-subtitle">
                    {subtitle}
                </p>

                <div
                    class="time-info"
                    role="region"
                    aria-label="시간 정보"
                >

                    <span aria-hidden="true">
                        ⏱️
                    </span>

                    <strong>
                        타임코드
                    </strong>

                    <br>

                    {seconds_to_df_timecode(start_sec)}
                    ~
                    {seconds_to_df_timecode(end_sec)}

                    <br>

                    <span aria-hidden="true">
                        ⏳
                    </span>

                    <strong>
                        재생시간
                    </strong>

                    <br>

                    {seconds_to_min_sec(start_sec)}
                    ~
                    {seconds_to_min_sec(end_sec)}

                    ({duration}초)

                </div>

                <p class="reason">

                    <strong>
                        <span aria-hidden="true">
                            💡
                        </span>
                        선정 이유:
                    </strong>

                    {reason}

                </p>

            </article>
            """


        st.markdown(
            f"""
            <section
                class="highlight-grid"
                aria-label="추천 숏폼 하이라이트 목록"
            >
                {highlight_cards_html}
            </section>
            """,
            unsafe_allow_html=True,
        )


        st.divider()


        # ====================================================
        # 4. EDL 다운로드
        # ====================================================

        render_section_header(
            "4",
            "EDIUS 연동 파일",
            "생성된 EDL 파일을 다운로드하여 EDIUS 편집 프로젝트에 활용할 수 있습니다.",
        )


        edl_filename = (
            f"{os.path.splitext(uploaded_file.name)[0]}"
            f"_shortform.edl"
        )


        st.markdown(
            f"""
            <div class="download-card">

                <div class="download-title">
                    EDIUS용 CMX 3600 EDL
                </div>

                <div class="download-description">
                    파일명: {edl_filename}
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


        st.download_button(
            label="💾 EDIUS용 EDL 파일 다운로드",
            data=edl_content,
            file_name=edl_filename,
            mime="text/plain",
            use_container_width=True,
        )


    # ========================================================
    # 오류 처리
    # ========================================================

    except Exception as error:

        render_analysis_progress(
            progress_placeholder,
            0,
            "분석 중 오류가 발생했습니다.",
            icon="❌",
        )

        accessible_alert(
            "처리 중 오류가 발생했습니다.",
            kind="error",
            icon="❌",
        )

        st.markdown(
            """
            <ul
                style="
                    color:#334155;
                    font-size:0.9rem;
                    line-height:1.7;
                "
            >

                <li>
                    오디오 트랙이 정상 포함된
                    미디어 파일인지 확인해 보세요.
                </li>

                <li>
                    지속적인 실패 발생 시
                    관리자에게 문의바랍니다.
                </li>

            </ul>
            """,
            unsafe_allow_html=True,
        )


        if (
            os.getenv(
                "APP_DEBUG",
                "false",
            ).lower()
            == "true"
        ):

            st.exception(error)


    # ========================================================
    # 임시 파일 정리
    # ========================================================

    finally:

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


# ============================================================
# 14. 실행
# ============================================================

if __name__ == "__main__":
    main()
