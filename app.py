def run_llama_highlight_extraction(client: Groq, segments: list) -> list:
    """
    Llama 모델을 활용해 30~60초 하이라이트 구간 추천 (최신 유효 모델 적용 및 자동 폴백)
    """
    # Groq에서 현재 정상 서비스 중인 유효 모델 리스트로 수정
    candidate_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama3-8b-8192"
    ]
    
    condensed_segments = []
    for seg in segments:
        condensed_segments.append({
            "start": round(seg.get("start", 0), 2),
            "end": round(seg.get("end", 0), 2),
            "text": seg.get("text", "").strip()
        })
    
    system_prompt = """
너는 뉴스 수석 에디터이자 숏폼(YouTube Shorts, TikTok, 와이숏츠) 콘텐츠 전문가이다.
제공되는 타임코드별 뉴스 자막 데이터를 분석하여, 숏폼으로 제작하기 가장 매력적인 30초~60초 길이의 하이라이트 구간 3곳을 선정하라.

[선정 기준]
1. 각 구간은 반드시 30초 이상 60초 이하이어야 한다.
2. 시청자의 후킹을 유도하는 주요 발언이나 사건의 핵심 요약이 담긴 구간이어야 한다.
3. 응답은 오직 Valid JSON 배열 형식으로만 출력하라. 다른 설명이나 마크다운 문법은 포함하지 마라.

[응답 JSON 형식]
[
  {
    "main_title": "메인 자막 타이틀 (15자 이내)",
    "sub_title": "부제목/요약 (25자 이내)",
    "start_time": 12.5,
    "end_time": 45.2,
    "reason": "선정 이유 설명"
  }
]
"""

    user_prompt = f"다음 뉴스 자막 데이터에서 숏폼 하이라이트 구간 3곳을 선정해줘:\n\n{json.dumps(condensed_segments, ensure_ascii=False)}"

    last_exception = None
    for model_name in candidate_models:
        try:
            # 모델 호출 옵션 설정
            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            
            # 3.3 및 3.1 모델에 한해 JSON mode 적용
            if "llama-3" in model_name:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content.strip()
            
            # 백틱(```) 제거 방어 로직
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            data = json.loads(content.strip())
            
            # 반환 구조에 따른 리스트 추출
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list):
                        return v
                # 키가 개별 객체인 경우 리스트로 래핑
                return [data]
            elif isinstance(data, list):
                return data
                
        except Exception as e:
            last_exception = e
            continue

    raise RuntimeError(f"모든 후보 모델 호출에 실패했습니다. 마지막 오류: {last_exception}")
