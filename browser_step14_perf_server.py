"""Test-only Step 14 performance fixture server (browser QA).

Seeds two students:
  - step14_perf@example.com        -> completed attempts + one ACTIVE attempt
  - step14_perf_empty@example.com  -> no completed attempts (empty state)
Run on :5002. No real AI calls are made.
"""
from werkzeug.security import generate_password_hash

import app as app_module
from database.db import (
    get_db_connection, get_department_by_code, get_course_by_code, create_user,
    create_generated_quiz, create_generated_quiz_attempt, finalize_quiz_attempt,
    get_quiz_questions_with_answers,
)

app = app_module.app
app.config["CSRF_PROTECTION"] = False

MAIN_EMAIL = "step14_perf@example.com"
EMPTY_EMAIL = "step14_perf_empty@example.com"
OTHER_EMAIL = "step14_perf_other@example.com"
PASSWORD = "Pass12345"


def _questions(n, correct):
    return [{"question": f"Q{i}", "options": ["a", "b", "c", "d"],
             "correct_answer": correct, "explanation": f"e{i}"} for i in range(n)]


def _finish(uid, quiz_id, answers_idx, conn):
    aid = create_generated_quiz_attempt(quiz_id, uid, len(answers_idx), conn=conn)
    rows = get_quiz_questions_with_answers(quiz_id, conn)
    answers = {rows[i]["id"]: answers_idx[i] for i in range(len(answers_idx))}
    return finalize_quiz_attempt(aid, uid, rows, answers, conn=conn)


def _ensure(conn, email, name, dept_id):
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    return row["id"] if row else create_user(name, email, generate_password_hash(PASSWORD),
                                             dept_id, "student", conn=conn)


with app.app_context():
    conn = get_db_connection()
    cse = get_department_by_code("CSE", conn)
    course = get_course_by_code("CSE 221", cse["id"], conn)

    main_id = _ensure(conn, MAIN_EMAIL, "Step 14 Perf", cse["id"])
    _ensure(conn, EMPTY_EMAIL, "Step 14 Perf Empty", cse["id"])
    other_id = _ensure(conn, OTHER_EMAIL, "Step 14 Perf Other", cse["id"])

    already = conn.execute(
        "SELECT COUNT(*) AS n FROM generated_quizzes WHERE user_id = ? AND topic LIKE 'PerfBrowser%'",
        (main_id,),
    ).fetchone()["n"]
    if not already:
        qa = create_generated_quiz(main_id, course["id"], "PerfBrowser Normalization Quiz",
                                   "PerfBrowser Normalization", "midterm", "medium",
                                   _questions(5, 2), source_material_ids=[], conn=conn)
        _finish(main_id, qa, [2, 2, 2, 2, 2], conn)  # 100%
        qb = create_generated_quiz(main_id, course["id"], "PerfBrowser Indexing Quiz",
                                   "PerfBrowser Indexing", "final", "hard",
                                   _questions(5, 3), source_material_ids=[], conn=conn)
        _finish(main_id, qb, [3, 3, 3, 0, 0], conn)  # 60%
        # ACTIVE attempt -> must NOT affect metrics
        create_generated_quiz_attempt(qa, main_id, 5, conn=conn)
        # Other student's data -> must never appear for the main user
        qo = create_generated_quiz(other_id, course["id"], "SECRET Other User Quiz",
                                   "SECRET Topic", "midterm", "easy",
                                   _questions(4, 0), source_material_ids=[], conn=conn)
        _finish(other_id, qo, [0, 0, 0, 1], conn)
    conn.close()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False, use_reloader=False, threaded=True)
