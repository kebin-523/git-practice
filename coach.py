from pathlib import Path

import pandas as pd

TOTAL_QUESTIONS = 5
MAX_FOLLOW_UPS = 1
MAX_CLARIFICATIONS = 2

QUESTIONS_PATH = Path(__file__).parent / "data" / "questions.csv"
DESIGN_JOBS = ["프로덕트 디자인", "UX/UI 디자인", "그래픽 디자인", "브랜드 디자인"]
QUESTION_TYPES = ["자기소개", "공통", "직무", "경험", "상황"]
SHARED_JOB = "공통"


def load_questions(path=QUESTIONS_PATH):
    return pd.read_csv(path, encoding="utf-8-sig")


def pick_questions(df, job):
    """유형마다 1개씩, 정해진 순서로 뽑는다. 직군 칸이 '공통' 인 질문도 후보."""
    picked = []
    for kind in QUESTION_TYPES:
        pool = df[(df["유형"] == kind) & (df["직군"].isin([job, SHARED_JOB]))]
        if pool.empty:
            raise ValueError(f"'{job}' 의 '{kind}' 질문이 질문 은행에 없어요.")
        row = pool.sample(1).iloc[0]
        picked.append({"유형": kind, "질문": row["질문"], "보는 점": row["보는 점"]})
    return picked


def can_follow_up(follow_ups_done):
    return follow_ups_done < MAX_FOLLOW_UPS


def can_clarify(clarifications_done):
    """되묻기 응답은 꼬리 질문 횟수와 따로 센다."""
    return clarifications_done < MAX_CLARIFICATIONS


def clamp_understanding(value):
    return max(0, min(100, int(value)))


PANEL_MAX = 10
CRITERION_MAX = 5
CRITERIA = ["specific", "relevance", "structure", "evidence"]
REWRITE_BELOW = 14


def _clamp(value, high):
    return max(0, min(high, int(value)))


def panel_scores(panel):
    return [_clamp(member["score"], PANEL_MAX) for member in panel]


def panel_average(panel):
    scores = panel_scores(panel)
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def criterion_scores(answer):
    return {name: _clamp(answer[name], CRITERION_MAX) for name in CRITERIA}


def answer_total(answer):
    return sum(criterion_scores(answer).values())


def needs_rewrite(answer):
    return answer_total(answer) < REWRITE_BELOW


def format_record(record):
    """면접 기록(질문별 주고받은 말)을 평가 프롬프트에 넣을 글로 만든다."""
    blocks = []
    for item in record:
        lines = [f"[질문 {item['no']}]"] + [f"{who}: {text}" for who, text in item["turns"]]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
