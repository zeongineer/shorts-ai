# shorts-ai 🎬

Groq Whisper STT와 Llama AI 모델을 활용하여 뉴스 영상/음성 파일에서 숏폼 하이라이트 구간을 자동으로 추출하고 EDIUS 등 NLE 프로그램용 EDL 파일을 생성하는 Streamlit 웹 애플리케이션입니다.

## 주요 기능
- 영상/음성 파일 업로드 (.mp3, .mp4, .ts, .mov, .m4a, .wav)
- FFmpeg 기반 초고속 오디오 압축 전처리 (Groq 25MB 제한 최적화)
- Groq Whisper-large-v3 기반 타임코드 자막 데이터 추출
- Llama AI 모델 기반 30~60초 하이라이트 구간 3곳 자동 선정 및 폴백 예외 처리
- NTSC Drop Frame (29.97 fps) 기반 EDL 파일 자동 생성 및 다운로드

## 배포 방법 (Streamlit Community Cloud)
1. GitHub에 `shorts-ai` 리포지토리를 생성하고 이 소스 코드를 올립니다.
2. [share.streamlit.io](https://share.streamlit.io)에 접속하여 배포합니다.
3. Advanced Settings -> Secrets 항목에 `GROQ_API_KEY = "your_groq_api_key"`를 등록합니다.
