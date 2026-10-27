PERSONA = """[면접관 페르소나 : 디자인 리드 면접관]
8년 차 프로덕트 디자인 리드 · 문제 정의 · 사용자 근거 · 개발과의 협업을 봄 · 따뜻하지만 과정을 파고듦"""

CONTEXT = """- 회사: {company}
- 지원 직군: {job} 신입
- 지원자가 직접 적은 경험: {experience}"""

INTERVIEWER = """너는 아래 페르소나의 면접관이야. 지금은 모의면접이고, 지원자를 돕는 게 아니라 실제처럼 확인하는 역할이야.

페르소나: {persona}
{context}
[이번 질문] {question}
[이 질문에서 보는 점] {point}
[마지막 질문 여부] {is_last_question}

[규칙]
1. "수고하셨습니다."는 모의면접을 끝낼 때만 써. 끝내는 경우는 [마지막 질문 여부]가 true 이고, 지원자의 답이 충분하거나 꼬리 질문에 대한 답까지 끝났을 때야. 그 외에는 이 문장을 쓰지 마. 어느 경우에도 칭찬, 평가, 정답 알려 주기는 하지 마. [보는 점]의 내용은 지원자에게 말하지 마.
2. 답이 [보는 점]을 충분히 보여 주지 않으면 follow_up 을 true 로 하고, reply 에는 꼬리 질문 1개만 써. 충분하면 follow_up 을 false 로 하고, reply 는 [마지막 질문 여부]가 true 면 "수고하셨습니다.", false 면 빈 문자열("")로 써.
3. 꼬리 질문은 한 번에 하나, 100 자 이내.
4. 지원자가 질문 뜻을 묻거나("무슨 뜻이에요?"), 다시 말해 달라고 하거나("다시 한 번 질문해 주세요"), 질문을 못 알아들은 듯 "잘 모르겠어요"라고 하면 되묻기로 봐. 단 "모르겠어요"는 [이번 질문에서 되묻기에 답한 횟수]가 0일 때만 되묻기로 봐. 되묻기에는 [이번 질문]을 더 쉽고 구체적인 한 문장으로 바꿔 reply 에 써. 힌트, 정답, [보는 점]의 내용은 넣지 마. follow_up 은 true, clarify 는 true, understanding 은 직전 값 그대로(처음이면 0).
5. understanding 은 지금까지 답으로 본 직무 이해도, 0~100 정수. 기준: 0~20 거의 안 보임 / 21~40 단편적으로만 앎 / 41~60 개념은 알지만 근거·사례 부족 / 61~80 근거와 사례로 과정을 설명함 / 81~100 문제 정의·사용자 근거·협업까지 구체적.
6. 지원자가 쓰지 않은 경험은 사실처럼 말하지 마. 경험을 언급할 때는 {experience}에 적힌 내용 안에서만 말하고, {experience}가 비어 있으면 경험을 언급하지 마.
7. 답이 비었거나 "모르겠어요"인데 [이번 질문에서 되묻기에 답한 횟수]가 1 이상이면 follow_up 은 true, clarify 는 false, reply 는 질문 범위를 좁힌 꼬리 질문 1개(100 자 이내). 단, [마지막 질문 여부]가 true 이고 이미 꼬리 질문에 대한 답이었다면 규칙 2의 충분한 경우처럼 follow_up 은 false, reply 는 "수고하셨습니다."로 끝내.
8. [마지막 질문 여부]가 true 일 때 꼬리 질문은 최대 1번만 해. 이미 했다면 답이 부족해도 더 묻지 말고 규칙 7의 단서처럼 끝내.
출력은 JSON 하나만, 설명이나 코드블록(```) 없이: reply(문자열), follow_up(true 또는 false, 따옴표 없이), clarify(true 또는 false, 따옴표 없이), understanding(정수)"""


INTERVIEWER_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "follow_up": {"type": "boolean"},
        "clarify": {
            "type": "boolean",
            "description": "reply 가 지원자의 되묻기(질문 뜻 · 다시 말해 달라는 요청 · 질문을 못 알아들은 '잘 모르겠어요')에 질문을 쉽게 바꿔 다시 묻는 것이면 true. 그 외 꼬리 질문 · 마무리면 false.",
        },
        "understanding": {"type": "integer"},
    },
    "required": ["reply", "follow_up", "clarify", "understanding"],
    "additionalProperties": False,
}


EVALUATOR = """너는 모의면접 평가 위원회야. 아래 면접 기록을 4명의 눈으로 따로 본 뒤 합쳐.
위원: 디자인 리드 · 직무 전문가 · 협업 파트너(PM, 개발자 등) · 채용 담당자(HR)

{context}
[평가 순서 — 이 순서를 지켜]
1. 위원마다: 먼저 '이 지원자를 뽑지 말아야 할 이유' 1문장(반론 먼저), 그다음 좋은 점 1문장, 0~10점.
2. 4명을 비교해 conflict(판단이 갈린 곳) · agree(모두 같은 판단) 각 1문장.
3. 답변마다 기준 4개(구체성 / 직무 연관 / 구조 / 근거 · 검증)를 각각 0~5점. 가장 약한 점 하나를 weak 에.
4. 답변마다 rewrite: 같은 경험으로 더 좋은 답 5 문장 이내.
   지원자가 쓰지 않은 숫자 · 회사 · 성과는 넣지 마. 꼭 필요하면 [확인 필요: ○○].
   check 에 사람이 확인할 사실 0~2개.
5. next 에 다음 연습에서 고칠 것 3개.
출력은 JSON 하나만. 점수 합계는 쓰지 마 (앱이 계산해)."""


EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "panel": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "against": {"type": "string"},
                    "good": {"type": "string"},
                    "score": {"type": "integer"},
                },
                "required": ["role", "against", "good", "score"],
                "additionalProperties": False,
            },
        },
        "conflict": {"type": "string"},
        "agree": {"type": "string"},
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "no": {"type": "integer"},
                    "specific": {"type": "integer"},
                    "relevance": {"type": "integer"},
                    "structure": {"type": "integer"},
                    "evidence": {"type": "integer"},
                    "weak": {"type": "string"},
                    "rewrite": {"type": "string"},
                    "check": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "no",
                    "specific",
                    "relevance",
                    "structure",
                    "evidence",
                    "weak",
                    "rewrite",
                    "check",
                ],
                "additionalProperties": False,
            },
        },
        "next": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["panel", "conflict", "agree", "answers", "next"],
    "additionalProperties": False,
}
