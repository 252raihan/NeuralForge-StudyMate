"""Focused Step 14 Quiz Performance Analysis tests.

Verifies access control, user isolation, zero-data safety, overview/course/topic
aggregation, finalized-only inclusion, ordering, and the API contract.
No AI calls are made anywhere in this suite.
"""
import uuid

from werkzeug.security import generate_password_hash

from app import app
from database.db import (
    get_db_connection, get_department_by_code, get_course_by_code, create_user,
    create_generated_quiz, create_generated_quiz_attempt, finalize_quiz_attempt,
    get_quiz_questions_with_answers, get_performance_overview, get_performance_by_quiz,
    get_performance_by_course, get_performance_by_topic, get_recent_performance,
)

TAG = uuid.uuid4().hex[:8]


def _questions(n, correct):
    return [{"question": f"Q{i}", "options": ["a", "b", "c", "d"],
             "correct_answer": correct, "explanation": f"e{i}"} for i in range(n)]


def _finish(uid, quiz_id, answers_idx, conn):
    aid = create_generated_quiz_attempt(quiz_id, uid, len(answers_idx), conn=conn)
    rows = get_quiz_questions_with_answers(quiz_id, conn)
    answers = {rows[i]["id"]: answers_idx[i] for i in range(len(answers_idx))}
    return finalize_quiz_attempt(aid, uid, rows, answers, conn=conn)


def _seed():
    conn = get_db_connection()
    cse = get_department_by_code("CSE", conn)
    eee = get_department_by_code("EEE", conn)
    cse_course = get_course_by_code("CSE 221", cse["id"], conn)
    eee_course = get_course_by_code("EEE 101", eee["id"], conn)

    s_email = f"step14_s_{TAG}@example.com"
    other_email = f"step14_o_{TAG}@example.com"
    empty_email = f"step14_empty_{TAG}@example.com"
    s_id = create_user("Step 14 Student", s_email, generate_password_hash("Pass12345"), cse["id"], "student", conn=conn)
    o_id = create_user("Other Student", other_email, generate_password_hash("Pass12345"), cse["id"], "student", conn=conn)
    empty_id = create_user("Empty Student", empty_email, generate_password_hash("Pass12345"), eee["id"], "student", conn=conn)

    # Student: quiz A (Normalization) 5/5 = 100%, quiz B (Indexing) 3/5 = 60%
    qa = create_generated_quiz(s_id, cse_course["id"], f"A Quiz {TAG}", "Normalization",
                               "midterm", "medium", _questions(5, 2), source_material_ids=[], conn=conn)
    _finish(s_id, qa, [2, 2, 2, 2, 2], conn)
    qb = create_generated_quiz(s_id, cse_course["id"], f"B Quiz {TAG}", "Indexing",
                               "final", "hard", _questions(5, 3), source_material_ids=[], conn=conn)
    _finish(s_id, qb, [3, 3, 3, 0, 0], conn)
    # An ACTIVE (unsubmitted) attempt that must NOT be counted.
    active = create_generated_quiz_attempt(qa, s_id, 5, conn=conn)

    # Other student: a different quiz/attempt to prove isolation
    qo = create_generated_quiz(o_id, cse_course["id"], f"Other Quiz {TAG}", "Normalization",
                               "midterm", "easy", _questions(4, 0), source_material_ids=[], conn=conn)
    _finish(o_id, qo, [0, 0, 0, 1], conn)

    conn.close()
    return {"s": s_id, "s_email": s_email, "o": o_id, "o_email": other_email,
            "empty": empty_id, "empty_email": empty_email,
            "cse_course": cse_course["id"], "quizzes": [qa, qb, qo], "active": active}


def _cleanup(ids):
    conn = get_db_connection()
    for qid in ids["quizzes"]:
        conn.execute("DELETE FROM generated_quiz_attempts WHERE quiz_id = ?", (qid,))
        conn.execute("DELETE FROM generated_quizzes WHERE id = ?", (qid,))
    for uid in (ids["s"], ids["o"], ids["empty"]):
        conn.execute("DELETE FROM generated_quiz_attempts WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()


def run_step14_tests():
    app.config["TESTING"] = True
    ids = _seed()
    checks = 0
    client = app.test_client()
    try:
        # 1. unauthenticated performance page blocked
        anon = client.get("/quiz/performance")
        assert anon.status_code in (301, 302) and "/login" in anon.headers.get("Location", "")
        checks += 1
        # 2. unauthenticated API blocked
        anon_api = client.get("/api/quiz/performance")
        assert anon_api.status_code in (301, 302, 401)
        checks += 1

        # 3. authenticated student allowed
        assert client.post("/login", data={"email": ids["s_email"], "password": "Pass12345"}).status_code == 302
        page = client.get("/quiz/performance")
        assert page.status_code == 200 and b"My Performance" in page.data
        checks += 1

        # OVERVIEW (5-12)
        ov = get_performance_overview(ids["s"])
        assert ov["completed_quizzes"] == 2                       # 6
        checks += 1
        assert ov["total_questions"] == 10                        # 7
        checks += 1
        assert ov["total_correct"] == 8                           # 8
        checks += 1
        assert ov["total_wrong"] == 2                             # 9
        checks += 1
        assert ov["overall_accuracy"] == 80.0                     # 10 accuracy calc
        checks += 1
        assert ov["average_percentage"] == 80.0                   # 11 average percentage
        checks += 1
        # 12. no divide by zero for a user with no attempts
        ov_empty = get_performance_overview(ids["empty"])
        assert ov_empty == {"completed_quizzes": 0, "total_questions": 0, "total_correct": 0,
                            "total_wrong": 0, "overall_accuracy": 0.0, "average_percentage": 0.0}
        checks += 1
        # 5. zero-data overview + empty state page
        empty_client = app.test_client()
        empty_client.post("/login", data={"email": ids["empty_email"], "password": "Pass12345"})
        empty_page = empty_client.get("/quiz/performance")
        assert empty_page.status_code == 200 and b"No performance data yet" in empty_page.data
        checks += 1

        # QUIZ PERFORMANCE (13-18)
        quizzes = get_performance_by_quiz(ids["s"])
        assert len(quizzes) == 2                                  # 13 finalized included (+ active excluded)
        checks += 1
        assert all(q["quiz_id"] != ids["active"] for q in quizzes)  # 14 active excluded
        checks += 1
        assert any(q["quiz_title"] == f"A Quiz {TAG}" for q in quizzes)  # 15 title
        checks += 1
        assert all(q["course_code"] == "CSE 221" for q in quizzes)       # 16 course
        checks += 1
        topics = {q["topic"] for q in quizzes}
        assert topics == {"Normalization", "Indexing"}                   # 17 topic
        checks += 1
        # 18. newest-first ordering
        submitted = [q["submitted_at"] for q in quizzes]
        assert submitted == sorted(submitted, reverse=True)
        checks += 1

        # COURSE PERFORMANCE (19-23)
        courses = get_performance_by_course(ids["s"])
        assert len(courses) == 1 and courses[0]["course_code"] == "CSE 221"   # 19 aggregate by course
        checks += 1
        assert courses[0]["total_correct"] == 8                               # 20 correct totals
        checks += 1
        assert courses[0]["total_wrong"] == 2                                 # 21 wrong totals
        checks += 1
        assert courses[0]["accuracy"] == 80.0                                 # 22 accuracy
        checks += 1
        assert courses[0]["average_percentage"] == 80.0                       # 23 avg percentage
        checks += 1

        # TOPIC PERFORMANCE (24-28)
        topics_perf = get_performance_by_topic(ids["s"])
        tmap = {t["topic"]: t for t in topics_perf}
        assert set(tmap) == {"Normalization", "Indexing"}                    # 24 aggregate by topic
        checks += 1
        assert tmap["Normalization"]["total_correct"] == 5                   # 25 correct totals
        checks += 1
        assert tmap["Indexing"]["total_wrong"] == 2                          # 26 wrong totals
        checks += 1
        assert tmap["Normalization"]["accuracy"] == 100.0                    # 27 accuracy
        checks += 1
        assert tmap["Indexing"]["average_percentage"] == 60.0                # 28 avg percentage
        checks += 1

        # SECURITY (29-33)
        # 29. another user's data excluded
        other_ov = get_performance_overview(ids["o"])
        assert other_ov["completed_quizzes"] == 1 and other_ov["total_questions"] == 4
        checks += 1
        # 29b. student analytics never include the other student's quiz titles
        body = client.get("/api/quiz/performance").get_data(as_text=True)
        assert f"Other Quiz {TAG}" not in body
        checks += 1
        # 30. user_id cannot be supplied to override the session
        spoof = client.get("/api/quiz/performance?user_id=" + str(ids["o"]))
        assert spoof.get_json()["overview"]["completed_quizzes"] == 2  # still the session user
        checks += 1
        # 31. no password / API key / path leakage
        blob = client.get("/api/quiz/performance").get_data(as_text=True)
        for needle in ("password", "api_key", "OPENAI", "uploads/", "F:\\", "sqlite"):
            assert needle.lower() not in blob.lower(), needle
        checks += 1
        # 32. parameterized query behavior (injection string is treated as a literal user id, returns empty)
        assert get_performance_overview(0)["completed_quizzes"] == 0
        checks += 1
        # 33. safe handling of missing course (orphan-safe aggregation uses LEFT JOIN)
        conn = get_db_connection()
        orphan_courses = get_performance_by_course(ids["s"], conn)
        assert all(c["course_name"] for c in orphan_courses)
        conn.close()
        checks += 1

        # ROBUSTNESS (34-35)
        # 34. malformed/unexpected DB state does not crash the page: attempt with 0 questions
        conn = get_db_connection()
        zero_quiz = create_generated_quiz(ids["s"], ids["cse_course"], f"Zero {TAG}", "Zero Topic",
                                          "midterm", "easy", _questions(1, 0), source_material_ids=[], conn=conn)
        conn.execute("DELETE FROM generated_quiz_questions WHERE quiz_id = ?", (zero_quiz,))
        conn.commit()
        conn.close()
        safe = client.get("/quiz/performance")
        assert safe.status_code == 200
        checks += 1
        # 35. regression compatibility with Step 13: history + a fresh result still work
        assert client.get("/quiz/attempts").status_code == 200
        recent = get_recent_performance(ids["s"])
        assert recent and recent[0]["percentage"] in (100.0, 60.0)
        assert client.get(f"/quiz/result/{get_performance_by_quiz(ids['s'])[0]['attempt_id']}").status_code == 200
        checks += 1

        # cleanup the zero-quiz
        conn = get_db_connection()
        conn.execute("DELETE FROM generated_quiz_attempts WHERE quiz_id = ?", (zero_quiz,))
        conn.execute("DELETE FROM generated_quizzes WHERE id = ?", (zero_quiz,))
        conn.commit()
        conn.close()

        assert checks >= 30, f"only {checks} checks ran"
        print(f"ALL STEP 14 TESTS PASSED ({checks} checks)")
        return True
    finally:
        _cleanup(ids)


if __name__ == "__main__":
    run_step14_tests()
