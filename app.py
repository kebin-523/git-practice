import pandas as pd
import streamlit as st

import coach
from llm import LLMError, ask_json
from prompts import (
    CONTEXT,
    EVAL_SCHEMA,
    EVALUATOR,
    INTERVIEWER,
    INTERVIEWER_SCHEMA,
    PERSONA,
    RETRY,
    RETRY_SCHEMA,
)

MIN_EXPERIENCE_LEN = 30
MAX_EXPERIENCE_LEN = 300
END_MESSAGE = "수고하셨습니다. 면접이 끝났어요."

st.set_page_config(page_title="AI 면접 코치", page_icon="🎤")


@st.cache_data
def get_questions():
    return coach.load_questions()


def reset():
    st.session_state.clear()


def question_label(no, follow_up_no=0):
    """화면에만 붙이는 번호표. Q-1 은 기본 질문, Q-1-1 은 그 질문의 꼬리 질문."""
    return f"Q-{no}-{follow_up_no}" if follow_up_no else f"Q-{no}"


def start_interview(name, job, company, experience):
    try:
        questions = coach.pick_questions(get_questions(), job)
    except (FileNotFoundError, ValueError) as e:
        st.error(f"질문을 준비하지 못했어요. {e}")
        return
    first = questions[0]["질문"]
    st.session_state.profile = {
        "name": name,
        "job": job,
        "company": company,
        "experience": experience,
    }
    st.session_state.questions = questions
    st.session_state.q_idx = 0
    st.session_state.follow_ups = 0
    st.session_state.clarifications = 0
    st.session_state.understanding = 0
    st.session_state.record = [{"no": 1, "question": first, "turns": [("면접관", first)]}]
    st.session_state.evaluation = None
    st.session_state.retries = {}
    st.session_state.done = False
    st.session_state.messages = [
        {"role": "assistant", "content": f"안녕하세요, {name}님. 면접을 시작할게요."},
        {"role": "assistant", "content": first, "label": question_label(1)},
    ]
    st.rerun()


# 글자 수(0/300)는 Streamlit 이 입력창 안에 겹쳐 그려서 잘 안 보이므로 입력창 아래로 내린다
COUNTER_CSS = """<style>
[data-testid="stTextArea"] { padding-bottom: 1.6rem; }
[data-testid="stTextArea"] [data-testid="InputInstructions"] {
    bottom: 0; right: 0.25rem; font-size: 0.85rem; color: inherit; opacity: 0.8;
}
</style>"""


def show_start():
    st.markdown(COUNTER_CSS, unsafe_allow_html=True)
    st.title("AI 면접 코치 · 디자인 직군")
    with st.form("start"):
        name = st.text_input("이름")
        job = st.selectbox("지원 직군", coach.DESIGN_JOBS)
        company = st.text_input("지원 회사")
        experience = st.text_area(
            "내 경험 (직접 한 일을 구체적으로)",
            height=160,
            max_chars=MAX_EXPERIENCE_LEN,
        )
        submitted = st.form_submit_button("면접 시작")
    if not submitted:
        return
    name, company, experience = name.strip(), company.strip(), experience.strip()
    if not name or not company:
        st.warning("이름과 지원 회사를 입력해 주세요.")
    elif len(experience) < MIN_EXPERIENCE_LEN:
        st.warning(f"경험을 {MIN_EXPERIENCE_LEN}자 이상 적어 주세요. (지금 {len(experience)}자)")
    else:
        start_interview(name, job, company, experience)


def build_context(profile):
    return CONTEXT.format(
        company=profile["company"],
        job=profile["job"],
        experience=profile["experience"],
    )


def build_instructions(profile, question, is_last):
    return INTERVIEWER.format(
        persona=PERSONA,
        context=build_context(profile),
        experience=profile["experience"],
        question=question["질문"],
        point=question["보는 점"],
        is_last_question="true" if is_last else "false",
    )


def handle_answer(answer):
    state = st.session_state
    idx = state.q_idx
    question = state.questions[idx]
    is_last = idx == coach.TOTAL_QUESTIONS - 1

    with st.chat_message("user"):
        st.write(answer)

    turns = state.record[idx]["turns"] + [("지원자", answer)]
    user_input = "\n".join(f"{who}: {text}" for who, text in turns)
    user_input += f"\n\n[직전 understanding] {state.understanding}"
    user_input += f"\n[이번 질문에서 되묻기에 답한 횟수] {state.clarifications}"

    with st.spinner("면접관이 듣고 있어요..."):
        try:
            result = ask_json(
                build_instructions(state.profile, question, is_last),
                user_input,
                INTERVIEWER_SCHEMA,
                "interviewer",
            )
        except LLMError as e:
            st.error(str(e))
            return

    state.messages.append({"role": "user", "content": answer})
    state.understanding = coach.clamp_understanding(result["understanding"])
    reply = result["reply"].strip()

    # 되묻기 응답은 꼬리 질문 횟수를 쓰지 않고, 되묻기 횟수는 코드가 따로 막는다
    if result["clarify"] and reply and coach.can_clarify(state.clarifications):
        state.clarifications += 1
        state.record[idx]["turns"] = turns + [("면접관", reply)]
        state.messages.append(
            {"role": "assistant", "content": reply, "label": f"{question_label(idx + 1)} 다시 설명"}
        )
    # AI 가 더 묻자고 해도 질문당 꼬리 질문 횟수는 코드가 막는다
    elif result["follow_up"] and reply and coach.can_follow_up(state.follow_ups):
        state.follow_ups += 1
        state.record[idx]["turns"] = turns + [("면접관", reply)]
        state.messages.append(
            {
                "role": "assistant",
                "content": reply,
                "label": question_label(idx + 1, state.follow_ups),
            }
        )
    elif is_last:
        state.record[idx]["turns"] = turns
        state.done = True
        state.messages.append({"role": "assistant", "content": END_MESSAGE})
    else:
        state.record[idx]["turns"] = turns
        state.q_idx = idx + 1
        state.follow_ups = 0
        state.clarifications = 0
        next_question = state.questions[state.q_idx]["질문"]
        state.record.append(
            {"no": state.q_idx + 1, "question": next_question, "turns": [("면접관", next_question)]}
        )
        state.messages.append(
            {"role": "assistant", "content": next_question, "label": question_label(state.q_idx + 1)}
        )
    st.rerun()


def show_sidebar():
    state = st.session_state
    n = coach.TOTAL_QUESTIONS if state.done else state.q_idx + 1
    with st.sidebar:
        st.header("상태창")
        st.write(f"질문 {n}/{coach.TOTAL_QUESTIONS}")
        st.progress(n / coach.TOTAL_QUESTIONS)
        st.metric("면접관이 본 이해도", f"{state.understanding}점")
        st.button("처음부터 다시", on_click=reset)


def show_chat():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if "label" in message:
                st.markdown(f"**{message['label']}**")
            st.write(message["content"])
    if st.session_state.done:
        st.info("면접이 끝났어요. '📊 평가' 탭에서 평가를 받아 보세요.")


def run_evaluation():
    state = st.session_state
    instructions = EVALUATOR.format(context=build_context(state.profile))
    with st.spinner("위원 4명이 평가하고 있어요..."):
        try:
            state.evaluation = ask_json(
                instructions,
                coach.format_record(state.record),
                EVAL_SCHEMA,
                "evaluation",
            )
        except LLMError as e:
            st.error(str(e))


def score_color(score):
    if score >= 8:
        return "green"
    if score >= 5:
        return "orange"
    return "red"


def show_evaluation_result(evaluation):
    panel = evaluation["panel"]
    st.metric("위원 평균 (0~10)", coach.panel_average(panel))
    scores = coach.panel_scores(panel)
    columns = st.columns(2)
    for i, member in enumerate(panel):
        with columns[i % 2].container(border=True):
            title, tag = st.columns([3, 1], vertical_alignment="center")
            title.markdown(f"**{member['role']}**")
            with tag.container(horizontal_alignment="right"):
                st.badge(f"{scores[i]}/{coach.PANEL_MAX}점", color=score_color(scores[i]))
            st.markdown(f"**뽑지 말아야 할 이유**  \n{member['against']}")
            st.markdown(f"**좋은 점**  \n{member['good']}")
    st.markdown(f"**갈린 곳**  \n{evaluation['conflict']}")
    st.markdown(f"**같은 판단**  \n{evaluation['agree']}")

    st.subheader("답변별 평가")
    questions = {item["no"]: item["question"] for item in st.session_state.record}
    turns_by_no = {item["no"]: item["turns"] for item in st.session_state.record}
    for answer in evaluation["answers"]:
        total = coach.answer_total(answer)
        with st.expander(f"질문 {answer['no']} · 답변 점수 {total}/20"):
            if answer["no"] in questions:
                st.caption(questions[answer["no"]])
            scores = coach.criterion_scores(answer)
            cols = st.columns(len(coach.CRITERIA))
            for col, key in zip(cols, coach.CRITERIA):
                col.metric(coach.CRITERIA_LABELS[key], f"{scores[key]}/{coach.CRITERION_MAX}")
            st.write(f"가장 약한 점: {answer['weak']}")
            # 첫 turn 은 기본 질문이라 위 caption 에 이미 있다. 꼬리 질문 · 되묻기 주고받은 말까지 보여 준다
            my_turns = turns_by_no.get(answer["no"], [])[1:]
            if my_turns and st.toggle("내 답변 보기", key=f"show_my_answer_{answer['no']}"):
                for who, text in my_turns:
                    st.markdown(f"**{'나' if who == '지원자' else '면접관'}**  \n{text}")
            if coach.needs_rewrite(answer):
                st.markdown("**고친 답**")
                st.write(answer["rewrite"])
                if answer["check"]:
                    st.markdown("**사람이 확인할 것**")
                    for item in answer["check"]:
                        st.markdown(f"- {item}")

    st.subheader("다음 연습에서 고칠 것")
    for item in evaluation["next"]:
        st.markdown(f"- {item}")


def show_evaluation():
    state = st.session_state
    if not state.done:
        st.info("면접을 끝까지 마치면 평가를 받을 수 있어요.")
        return
    if st.button("위원 4명에게 평가받기"):
        run_evaluation()
    if state.evaluation:
        show_evaluation_result(state.evaluation)


def run_retry(question, answer):
    state = st.session_state
    instructions = RETRY.format(context=build_context(state.profile))
    user_input = f"[질문] {question}\n[지원자의 답] {answer}"
    with st.spinner("다시 채점하고 있어요..."):
        try:
            return ask_json(instructions, user_input, RETRY_SCHEMA, "retry")
        except LLMError as e:
            st.error(str(e))
            return None


def show_comparison(before, after):
    result = coach.compare(before, after)
    st.metric(
        "다시 채점 점수",
        f"{result['after_total']}/{coach.CRITERION_MAX * len(coach.CRITERIA)}",
        delta=result["delta"],
    )
    st.dataframe(
        pd.DataFrame(
            {
                "기준": [coach.CRITERIA_LABELS[r["criterion"]] for r in result["rows"]],
                "전": [r["before"] for r in result["rows"]],
                "후": [r["after"] for r in result["rows"]],
                "차이": [r["delta"] for r in result["rows"]],
            }
        ),
        hide_index=True,
    )
    st.write(f"가장 약한 점: {after['weak']}")


def show_retry():
    state = st.session_state
    if not state.evaluation:
        st.info("'📊 평가' 탭에서 평가를 먼저 받으면 재도전할 수 있어요.")
        return
    answers = {a["no"]: a for a in coach.lowest_first(state.evaluation["answers"])}
    questions = {item["no"]: item["question"] for item in state.record}
    no = st.selectbox(
        "다시 답할 질문 (점수 낮은 순)",
        list(answers),
        format_func=lambda n: f"질문 {n} · {coach.answer_total(answers[n])}/20 · {questions.get(n, '')}",
    )
    before = answers[no]
    st.markdown(f"**질문 {no}**  \n{questions.get(no, '')}")
    st.write(f"지난 점수: {coach.answer_total(before)}/20")
    st.write(f"가장 약한 점: {before['weak']}")

    new_answer = st.text_area("다시 답하기", key=f"retry_answer_{no}", height=160)
    if st.button("다시 채점"):
        if not new_answer.strip():
            st.warning("답을 적은 뒤에 눌러 주세요.")
        else:
            after = run_retry(questions.get(no, ""), new_answer.strip())
            if after:
                state.retries[no] = after
    if no in state.retries:
        show_comparison(before, state.retries[no])


def show_interview():
    profile = st.session_state.profile
    st.title(f"{profile['company']} {profile['job']} 모의면접")
    show_sidebar()
    chat_tab, eval_tab, retry_tab = st.tabs(["💬 면접", "📊 평가", "🔁 재도전"])
    with chat_tab:
        show_chat()
    with eval_tab:
        show_evaluation()
    with retry_tab:
        show_retry()
    if st.session_state.done:
        return
    answer = st.chat_input("답변을 입력하세요")
    if answer and answer.strip():
        handle_answer(answer.strip())


if "profile" not in st.session_state:
    show_start()
else:
    show_interview()
