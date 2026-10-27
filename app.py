import streamlit as st

import coach
from llm import LLMError, ask_json
from prompts import CONTEXT, INTERVIEWER, INTERVIEWER_SCHEMA, PERSONA

MIN_EXPERIENCE_LEN = 30
END_MESSAGE = "수고하셨습니다. 면접이 끝났어요."

st.set_page_config(page_title="AI 면접 코치", page_icon="🎤")


@st.cache_data
def get_questions():
    return coach.load_questions()


def reset():
    st.session_state.clear()


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
    st.session_state.understanding = 0
    st.session_state.turns = [("면접관", first)]
    st.session_state.done = False
    st.session_state.messages = [
        {"role": "assistant", "content": f"안녕하세요, {name}님. 면접을 시작할게요."},
        {"role": "assistant", "content": first},
    ]
    st.rerun()


def show_start():
    st.title("AI 면접 코치 · 디자인 직군")
    with st.form("start"):
        name = st.text_input("이름")
        job = st.selectbox("지원 직군", coach.DESIGN_JOBS)
        company = st.text_input("지원 회사")
        experience = st.text_area("내 경험 (직접 한 일을 구체적으로)", height=160)
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


def build_instructions(profile, question, is_last):
    context = CONTEXT.format(
        company=profile["company"],
        job=profile["job"],
        experience=profile["experience"],
    )
    return INTERVIEWER.format(
        persona=PERSONA,
        context=context,
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

    turns = state.turns + [("지원자", answer)]
    user_input = "\n".join(f"{who}: {text}" for who, text in turns)
    user_input += f"\n\n[직전 understanding] {state.understanding}"

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

    # AI 가 더 묻자고 해도 질문당 꼬리 질문 횟수는 코드가 막는다
    if result["follow_up"] and reply and coach.can_follow_up(state.follow_ups):
        state.follow_ups += 1
        state.turns = turns + [("면접관", reply)]
        state.messages.append({"role": "assistant", "content": reply})
    elif is_last:
        state.done = True
        state.messages.append({"role": "assistant", "content": END_MESSAGE})
    else:
        state.q_idx = idx + 1
        state.follow_ups = 0
        next_question = state.questions[state.q_idx]["질문"]
        state.turns = [("면접관", next_question)]
        state.messages.append({"role": "assistant", "content": next_question})
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


def show_interview():
    profile = st.session_state.profile
    st.title(f"{profile['company']} {profile['job']} 모의면접")
    show_sidebar()
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    if st.session_state.done:
        return
    answer = st.chat_input("답변을 입력하세요")
    if answer and answer.strip():
        handle_answer(answer.strip())


if "profile" not in st.session_state:
    show_start()
else:
    show_interview()
