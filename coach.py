from pathlib import Path

import pandas as pd

TOTAL_QUESTIONS = 5
MAX_FOLLOW_UPS = 1

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


def clamp_understanding(value):
    return max(0, min(100, int(value)))
