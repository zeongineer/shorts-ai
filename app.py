def run_gemini_highlight_extraction(gemini_api_key: str, segments: list) -> list:
    """
    구간 오차 방지 및 30~60초 길이 강제 검증 로직이 포함된 하이라이트 추천
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

    # 타임코드 정밀도 보장을 위한 자막 데이터 정제
    condensed_segments = []
    for seg in segments:
        s = round(float(seg.get("start", 0)), 2)
        e = round(float(seg.get("end", 0)), 2)
        text = seg.get("text", "").strip()
        if text:
            condensed_segments.append({"start": s, "end": e, "text": text})
    
    prompt = f"""
너는 대한민국 뉴스 전문 수석 에디터이자 숏폼(YouTube Shorts, TikTok) 제작 전문가이다.
아래 제공되는 타임코드별 자막 데이터를 정밀하게 분석하여, 숏폼으로 제작할 핵심 하이라이트 구간 3곳을 선정하라.

[엄격한 타임코드 선정 규칙]
1. **구간 길이 절대 준수**: `end_time` - `start_time`은 **반드시 30.0초 이상 60.0초 이하**이어야 한다.
2. **실제 타임코드 매칭**: `start_time`과 `end_time`은 제공된 자막 데이터의 실제 `start`와 `end` 값 범위를 벗어나면 안 된다. 문장의 중간이 모호하게 끊기지 않고 완전한 맥락을 갖추도록 시작과 끝 시간을 결정하라.
3. **핵심 후킹 요소**: 앵커의 핵심 리포팅, 관계자의 주요 인터뷰 발언, 결정적 사건 요약 문장이 포함된 구간을 선정하라.

[자막 데이터]
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
                    "reason": {"type": "STRING", "description": "선정 이유"}
                },
                "required": ["main_title", "sub_title", "start_time", "end_time", "reason"]
            }
        },
        temperature=0.1
    )

    raw_highlights = None
    for model_name in final_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gen_config
            )
            raw_highlights = json.loads(response.text)
            break
        except Exception:
            continue

    if not raw_highlights:
        raise RuntimeError("Gemini 모델을 통한 하이라이트 추출에 실패했습니다.")

    # [후처리 코드 레벨 구간 길이 보정 로직]
    validated_highlights = []
    for item in raw_highlights:
        st_time = float(item.get("start_time", 0))
        ed_time = float(item.get("end_time", 0))
        duration = ed_time - st_time

        # 30초 미만일 경우 종료 시간을 연장하여 35초로 보정
        if duration < 30.0:
            ed_time = st_time + 35.0
        # 60초 초과일 경우 종료 시간을 줄여 55초로 보정
        elif duration > 60.0:
            ed_time = st_time + 55.0

        item["start_time"] = round(st_time, 2)
        item["end_time"] = round(ed_time, 2)
        validated_highlights.append(item)

    return validated_highlights
