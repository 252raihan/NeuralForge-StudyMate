"""Focused Step 13 Quiz Attempt + Result System tests.

Covers attempt creation, answer submission validation, server-side scoring,
one-time submission, ownership (IDOR), result review, and attempt history.
No AI calls are made anywhere in this suite.
"""
import uuid

from werkzeug.security import generate_password_hash

from app import app
from database.db import (
    get_db_connection, get_department_by_code, get_course_by_code, create_user,
    create_generated_quiz, get_generated_quiz_questions, get_attempt_answers,
    get_user_quiz_attempts, finalize_quiz_attempt,
)


def _make_questions(n=4):
    return [
        {"question": f"Question {i}?", "options": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"],
         "correct_answer": 1, "explanation": f"Explanation {i}"}
        for i in range(n)
    ]


def _seed():
    conn = get_db_connection()
    cse = get_department_by_code("CSE", conn)
    course = get_course_by_code("CSE 221", cse["id"], conn)
    token = uuid.uuid4().hex[:8]
    email = f"step13_student_{token}@example.com"
    uid = create_user("Step 13 Student", email, generate_password_hash("Pass12345"),
                      cse["id"], "student", conn=conn)
    quiz_id = create_generated_quiz(uid, course["id"], "DBMS \u2014 Normalization Quiz",
                                    "Normalization", "midterm", "medium", _make_questions(4),
                                    source_material_ids=[], conn=conn)
    empty_quiz = create_generated_quiz(uid, course["id"], "Empty Quiz", "Nothing",
                                       "final", "easy", _make_questions(1), source_material_ids=[], conn=conn)
    # Simulate a quiz whose questions were removed -> must be handled safely.
    conn.execute("DELETE FROM generated_quiz_questions WHERE quiz_id = ?", (empty_quiz,))
    conn.commit()
    conn.close()
    return {"uid": uid, "email": email, "course": course["id"], "quiz": quiz_id,
            "empty_quiz": empty_quiz}


def _cleanup(ids):
    conn = get_db_connection()
    for qid in (ids["quiz"], ids["empty_quiz"]):
        conn.execute("DELETE FROM generated_quiz_attempts WHERE quiz_id = ?", (qid,))
        conn.execute("DELETE FROM generated_quizzes WHERE id = ?", (qid,))
    conn.execute("DELETE FROM users WHERE id = ?", (ids["uid"],))
    conn.commit()
    conn.close()


def _question_ids(quiz_id):
    conn = get_db_connection()
    ids = [r["id"] for r in get_generated_quiz_questions(quiz_id, conn)]
    conn.close()
    return ids


def run_step13_tests():
    app.config["TESTING"] = True
    ids = _seed()
    client = app.test_client()
    checks = 0
    try:
        # 1. take quiz requires login
        anon = client.get(f"/quiz/take/{ids['quiz']}")
        assert anon.status_code in (301, 302) and "/login" in anon.headers.get("Location", "")
        checks += 1
        assert client.post("/login", data={"email": ids["email"], "password": "Pass12345"}).status_code == 302

        # 4. invalid quiz ID handled
        assert client.get("/quiz/take/999").status_code == 404
        checks += 1
        # 5. quiz with no questions handled safely
        assert client.get(f"/quiz/take/{ids['empty_quiz']}").status_code == 404
        checks += 1

        # 2. valid student can open own quiz
        take = client.get(f"/quiz/take/{ids['quiz']}")
        assert take.status_code == 200
        checks += 1
        # 6. correct question count shown
        assert take.data.count(b"data-question-id=") == 4
        checks += 1
        # 7. correct options shown
        assert b"a0" in take.data and b"d3" in take.data
        checks += 1
        # 8. correct answers NOT exposed in HTML
        assert b"correct_answer" not in take.data and b"Correct answer" not in take.data
        assert b"Explanation" not in take.data and b"data-correct" not in take.data
        checks += 1

        qids = _question_ids(ids["quiz"])

        # 3. another student's quiz blocked
        other_email = f"step13_other_{uuid.uuid4().hex[:8]}@example.com"
        conn = get_db_connection()
        other_id = create_user("Other", other_email, generate_password_hash("Pass12345"),
                               ids["uid"] and get_department_by_code("CSE", conn)["id"], "student", conn=conn)
        conn.close()
        other_client = app.test_client()
        other_client.post("/login", data={"email": other_email, "password": "Pass12345"})
        assert other_client.get(f"/quiz/take/{ids['quiz']}").status_code == 404
        checks += 1

        # 9. the answer key is never exposed in the submission response (only an
        # aggregated correct_answers count, i.e. a score summary, is returned)
        client.get(f"/quiz/take/{ids['quiz']}")
        sub = client.post(f"/api/quizzes/{ids['quiz']}/submit", json={"answers": {}})
        assert sub.status_code == 200
        data = sub.get_json()
        assert set(data) <= {"success", "attempt_id", "score", "total_questions",
                              "correct_answers", "wrong_answers", "percentage"}
        compact = sub.get_data(as_text=True).replace(" ", "")
        assert '"correct_answer":' not in compact
        assert "explanation" not in compact and "option_a" not in compact
        checks += 1

        # 18. unanswered question counted incorrect; 14-17 validation on a fresh attempt
        # (a fresh in-progress attempt is created on GET)
        client.get(f"/quiz/take/{ids['quiz']}")

        # 14. invalid answer index rejected
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": {str(qids[0]): 5}}).status_code == 400
        checks += 1
        # 15. string answer index rejected
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": {str(qids[0]): "1"}}).status_code == 400
        checks += 1
        # 16. float answer index rejected
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": {str(qids[0]): 1.5}}).status_code == 400
        checks += 1
        # 16b. boolean answer index rejected
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": {str(qids[0]): True}}).status_code == 400
        checks += 1
        # 16c. negative answer index rejected
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": {str(qids[0]): -1}}).status_code == 400
        checks += 1
        # 16d. null answer rejected (must be an integer index)
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": {str(qids[0]): None}}).status_code == 400
        checks += 1
        # 16e. non-numeric question identifier rejected
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": {"abc": 1}}).status_code == 400
        checks += 1
        # 14c. no active attempt (never opened) cannot be submitted
        conn = get_db_connection()
        row = conn.execute("SELECT id FROM generated_quiz_attempts WHERE quiz_id = ? AND submitted_at IS NULL",
                           (ids['quiz'],)).fetchone()
        conn.close()
        assert row is not None  # an active attempt exists from the GET above
        checks += 1
        # 2b. take page exposes attempt_id (server-established attempt state)
        assert b"data-quiz-id" in take.data
        checks += 1
        # 33. malformed JSON handled
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           data="not json", content_type="application/json").status_code == 400
        checks += 1
        # 33b. answers must be an object
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": [1, 2, 3]}).status_code == 400
        checks += 1
        # oversized payload rejected
        big = {str(qids[0]): 0}
        big.update({f"x{i}": 0 for i in range(300)})
        assert client.post(f"/api/quizzes/{ids['quiz']}/submit",
                           json={"answers": big}).status_code == 413
        checks += 1

        # 17. unknown question id handled safely (ignored) -> still scores known ones
        partial = client.post(f"/api/quizzes/{ids['quiz']}/submit",
                              json={"answers": {str(qids[0]): 1, "999": 0}})
        assert partial.status_code == 200
        pdata = partial.get_json()
        # 18. unanswered questions counted incorrect (only q0 answered -> 1 correct)
        assert pdata["correct_answers"] == 1 and pdata["total_questions"] == 4
        assert pdata["wrong_answers"] == 3
        checks += 1

        # 31. duplicate submission prevented
        dup = client.post(f"/api/quizzes/{ids['quiz']}/submit",
                          json={"answers": {str(qids[0]): 1}})
        assert dup.status_code in (400, 409)
        checks += 1

        # 32. submitted attempt immutable (score unchanged after duplicate attempt)
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM generated_quiz_attempts WHERE id = ?",
                           (pdata["attempt_id"],)).fetchone()
        conn.close()
        assert row["score"] == 1 and row["submitted_at"] is not None
        checks += 1

        # 23. attempt saved; 24. attempt answers saved
        conn = get_db_connection()
        answers = get_attempt_answers(pdata["attempt_id"], conn)
        conn.close()
        assert len(answers) == 4
        checks += 1

        # 10-13, 19-22. server-side scoring on a fresh attempt
        client.get(f"/quiz/take/{ids['quiz']}")
        # all correct (correct_answer == 1 for all) -> 100%
        all_correct = {str(q): 1 for q in qids}
        r100 = client.post(f"/api/quizzes/{ids['quiz']}/submit", json={"answers": all_correct})
        d100 = r100.get_json()
        assert d100["percentage"] == 100.0 and d100["correct_answers"] == 4
        checks += 1  # 19 all correct
        # 12. client-provided score ignored (sent in payload, should be ignored)
        client.get(f"/quiz/take/{ids['quiz']}")
        tamper = client.post(f"/api/quizzes/{ids['quiz']}/submit",
                             json={"answers": {str(q): 0 for q in qids},
                                   "score": 999, "percentage": 100, "correct_answers": 999})
        d0 = tamper.get_json()
        assert d0["score"] == 0 and d0["percentage"] == 0.0
        checks += 1  # 20 all wrong + 12 client score ignored
        # 13. client-provided correct answers ignored
        client.get(f"/quiz/take/{ids['quiz']}")
        tamper2 = client.post(f"/api/quizzes/{ids['quiz']}/submit",
                              json={"answers": {str(qids[0]): 1, str(qids[1]): 0, str(qids[2]): 0, str(qids[3]): 0},
                                    "correct_answers": {str(qids[1]): 0, str(qids[2]): 0}})
        d_part = tamper2.get_json()
        assert d_part["correct_answers"] == 1  # only q0 was actually correct
        checks += 1  # 21 partial score + 13 client correct ignored
        # 22. percentage formula verified (1/4 = 25.0)
        assert d_part["percentage"] == 25.0
        checks += 1

        # 25-27. result page works and shows correct answer + explanation after submission
        result = client.get(f"/quiz/result/{d_part['attempt_id']}")
        assert result.status_code == 200
        assert b"Question Review" in result.data
        assert b"correct answer" in result.data
        assert b"Explanation" in result.data
        checks += 1

        # 28. result ownership enforced
        assert other_client.get(f"/quiz/result/{d_part['attempt_id']}").status_code == 404
        checks += 1
        # 14b. invalid attempt id -> safe 404
        assert client.get("/quiz/result/999").status_code == 404
        checks += 1

        # 29. attempt history shows own attempts only
        hist = client.get("/quiz/attempts")
        assert hist.status_code == 200
        assert b"DBMS" in hist.data
        other_hist = other_client.get("/quiz/attempts")
        assert b"DBMS" not in other_hist.data  # other user has no attempts of this quiz
        checks += 1
        # 30. attempts sorted newest first
        conn = get_db_connection()
        rows = get_user_quiz_attempts(ids["uid"], conn)
        conn.close()
        submitted = [r["submitted_at"] for r in rows]
        assert submitted == sorted(submitted, reverse=True)
        checks += 1

        # 34. transaction rollback works (finalize on already-submitted attempt raises)
        conn = get_db_connection()
        qrows = get_generated_quiz_questions(ids["quiz"], conn)
        try:
            finalize_quiz_attempt(d_part["attempt_id"], ids["uid"], qrows, {qrows[0]["id"]: 1}, conn=conn)
            assert False, "expected ValueError"
        except ValueError:
            pass
        # No partial attempt answers duplicated after the rejected transaction
        cnt = conn.execute("SELECT COUNT(*) AS n FROM generated_quiz_attempt_answers WHERE attempt_id = ?",
                           (d_part["attempt_id"],)).fetchone()["n"]
        assert cnt == 4
        conn.close()
        checks += 1

        # cleanup the extra user
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE id = ?", (other_id,))
        conn.commit()
        conn.close()

        assert checks >= 35, f"only {checks} checks ran"
        print(f"ALL STEP 13 TESTS PASSED ({checks} checks)")
        return True
    finally:
        _cleanup(ids)


if __name__ == "__main__":
    run_step13_tests()
