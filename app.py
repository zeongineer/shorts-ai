def prepare_audio_for_groq(input_file_path: str) -> str:
    """
    업로드된 비디오/오디오 파일을 Groq API 전송 기준(25MB 이하)에 맞춰 고효율 압축 진행.
    오디오 스트림이 없는 영상인 경우 가상 무음 오디오를 생성하여 FFmpeg 에러 방지.
    """
    output_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_path = output_temp_file.name
    output_temp_file.close()

    # 1. 입력 파일에 오디오 스트림이 존재하는지 확인
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        input_file_path
    ]
    
    has_audio = False
    try:
        probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if "audio" in probe_result.stdout.lower():
            has_audio = True
    except Exception:
        has_audio = True  # 조회 실패 시 기본 오디오 추출 시도

    # 2. 오디오 스트림 여부에 따른 FFmpeg 명령어 구성
    if has_audio:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_file_path,
            "-vn",                   # 비디오 제거
            "-ar", "16000",          # 16kHz
            "-ac", "1",              # 모노
            "-b:a", "32k",           # 32kbps
            "-f", "mp3",
            output_path
        ]
    else:
        # 오디오 스트림이 없는 경우 1초 무음 파일 생성 (에러 방지용)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", "1",
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
