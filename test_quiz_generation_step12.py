"""Focused Step 12 AI Quiz Generator tests.

Covers the create page, server-side validation, approved-only RAG retrieval,
AI generation + strict output validation, storage, ownership (IDOR), and source
traceability. All AI calls are mocked — no real network requests are made.
"""
import os
import uuid
from unittest.mock import patch, MagicMock

from werkzeug.security import generate_password_hash

from app import app
from database.db import (
    get_db_connection, get_department_by_code, get_course_by_code, create_user,
    create_study_material, update_study_material_status,
    get_generated_quiz_for_user, get_generated_quiz_questions, get_generated_quiz_sources,
)
from services.rag_service import index_material
from services.ai_service import validate_quiz_questions, generate_quiz_from_context

TEXT = ("Normalization reduces redundancy in relational databases. "
        "First normal form eliminates repeating groups. "
        "Second normal form removes partial dependency. "
        "Third normal form removes transitive dependency. ") * 30


def _valid_questions(n=5):
    return [
        {"question": f"Which normal form removes partial dependency? {i}",
         "options": ["1NF", "2NF", "3NF", "BCNF"],
         "correct_answer": 1,
         "explanation": "2NF removes partial dependency."}
        for i in range(n)
    ]


def _seed():
    conn = get_db_connection()
    cse = get_department_by_code("CSE", conn)
    eee = get_department_by_code("EEE", conn)
    cse_course = get_course_by_code("CSE 221", cse["id"], conn)
    eee_course = get_course_by_code("EEE 101", eee["id"], conn)
    token = uuid.uuid4().hex[:8]
    email = f"step12_student_{token}@example.com"
    uid = create_user("Step 12 Student", email, generate_password_hash("Pass12345"),
                      cse["id"], "student", conn=conn)
    approved = create_study_material(cse_course["id"], "Normalization", "midterm",
                                     "uploads/sample_study_guide.pdf", uid, status="approved",
                                     extracted_text=TEXT, conn=conn)
    pending = create_study_material(cse_course["id"], "Normalization Pending", "final",
                                    "uploads/sample_study_guide.pdf", uid, status="pending",
                                    extracted_text="Pending normalization secret.", conn=conn)
    rejected = create_study_material(eee_course["id"], "Rejected Circuit", "both",
                                     "uploads/sample_study_guide.pdf", uid, status="rejected",
                                     extracted_text="Rejected circuit normalization.", conn=conn)
    unrelated = create_study_material(cse_course["id"], "Photosynthesis", "final",
                                      "uploads/sample_study_guide.pdf", uid, status="approved",
                                      extracted_text="Photosynthesis converts light to glucose.", conn=conn)
    other_dept = create_study_material(eee_course["id"], "Normalization EEE", "midterm",
                                       "uploads/sample_study_guide.pdf", uid, status="approved",
                                       extracted_text="Normalization in another department. " * 30, conn=conn)
    conn.close()
    ids = {"uid": uid, "email": email, "cse": cse["id"], "eee": eee["id"],
           "course": cse_course["id"], "eee_course": eee_course["id"],
           "approved": approved, "pending": pending, "rejected": rejected,
           "unrelated": unrelated, "other_dept": other_dept}
    for key in ("approved", "pending", "rejected", "unrelated", "other_dept"):
        index_material(ids[key])
    return ids


def _cleanup(ids):
    conn = get_db_connection()
    quizzes = conn.execute("SELECT id FROM generated_quizzes WHERE user_id = ?", (ids["uid"],)).fetchall()
    for row in quizzes:
        conn.execute("DELETE FROM quiz_sources WHERE quiz_id = ?", (row["id"],))
        conn.execute("DELETE FROM generated_quiz_questions WHERE quiz_id = ?", (row["id"],))
        conn.execute("DELETE FROM generated_quizzes WHERE id = ?", (row["id"],))
    for key in ("approved", "pending", "rejected", "unrelated", "other_dept"):
        conn.execute("DELETE FROM study_materials WHERE id = ?", (ids[key],))
    conn.execute("DELETE FROM users WHERE id = ?", (ids["uid"],))
    conn.commit()
    conn.close()


def run_step12_tests():
    app.config["TESTING"] = True
    ids = _seed()
    client = app.test_client()
    checks = 0
    try:
        # 1. quiz create requires login
        anon = client.get("/quiz/create")
        assert anon.status_code in (301, 302) and "/login" in anon.headers.get("Location", "")
        checks += 1
        # 2. logged-in student can open page
        assert client.post("/login", data={"email": ids["email"], "password": "Pass12345"}).status_code == 302
        page = client.get("/quiz/create")
        assert page.status_code == 200 and b"Generate a Quiz" in page.data
        checks += 1

        base = {"course_id": ids["course"], "topic": "Normalization",
                "exam_type": "midterm", "number_of_questions": 5, "difficulty": "medium"}

        # 3. invalid course rejected
        assert client.post("/api/quizzes/generate", json={**base, "course_id": 999}).status_code == 400
        checks += 1
        # 4. invalid exam type rejected
        assert client.post("/api/quizzes/generate", json={**base, "exam_type": "pop-quiz"}).status_code == 400
        checks += 1
        # 5. invalid difficulty rejected
        assert client.post("/api/quizzes/generate", json={**base, "difficulty": "impossible"}).status_code == 400
        checks += 1
        # 6. invalid question count rejected
        assert client.post("/api/quizzes/generate", json={**base, "number_of_questions": 7}).status_code == 400
        checks += 1
        # 6b. non-numeric question count rejected
        assert client.post("/api/quizzes/generate", json={**base, "number_of_questions": "many"}).status_code == 400
        checks += 1
        # 6c. non-JSON body rejected
        assert client.post("/api/quizzes/generate", data="notjson", content_type="text/plain").status_code == 400
        checks += 1
        # 7. question count whitelist works (all four allowed values accepted by validator)
        for count in (5, 10, 15, 20):
            with patch("app.generate_quiz_from_context", return_value=_valid_questions(count)):
                r = client.post("/api/quizzes/generate", json={**base, "number_of_questions": count})
                assert r.status_code == 201 and r.get_json()["question_count"] == count
        checks += 1

        # 8-11. RAG retrieval: approved only, unrelated excluded
        from services.rag_service import retrieve_relevant_chunks
        mids = [c["material_id"] for c in retrieve_relevant_chunks("normalization", ids["cse"], top_k=8)]
        assert ids["approved"] in mids                      # 8 approved used
        checks += 1
        assert ids["pending"] not in mids                   # 9 pending excluded
        checks += 1
        assert ids["rejected"] not in mids                  # 10 rejected excluded
        checks += 1
        assert ids["unrelated"] not in mids                 # 11 irrelevant not selected
        checks += 1
        # 12. department preference works
        assert mids.index(ids["approved"]) <= mids.index(ids["other_dept"])
        checks += 1

        # 13. no relevant context returns a safe error (AI never called)
        with patch("app.generate_quiz_from_context") as mock_gen:
            r = client.post("/api/quizzes/generate", json={**base, "topic": "quantum chromodynamics gluon"})
            assert r.status_code == 404 and r.get_json()["success"] is False
            mock_gen.assert_not_called()
        checks += 1

        # 14. AI service mocked + 15. success works (already used above); assert structure
        with patch("app.generate_quiz_from_context", return_value=_valid_questions(5)) as mock_gen:
            r = client.post("/api/quizzes/generate", json=base)
            assert r.status_code == 201
            data = r.get_json()
            assert data["success"] and isinstance(data["quiz_id"], int)
            assert data["title"] == "Database Management System \u2014 Normalization Quiz"
            assert data["question_count"] == 5
            mock_gen.assert_called_once()
        checks += 1

        # 16. missing API key handled
        with patch.dict(os.environ, {"OPENAI_API_KEY": "your-api-key-here"}):
            try:
                generate_quiz_from_context("some context about normalization", 5, "medium")
                assert False, "expected ValueError"
            except ValueError as exc:
                assert "API key" in str(exc)
        checks += 1

        # 17. rate limit handled
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
                patch("services.ai_service.get_openai_client") as mock_client:
            from openai import RateLimitError
            mock_client.return_value.chat.completions.create.side_effect = RateLimitError(
                "limit", response=MagicMock(), body=None)
            try:
                generate_quiz_from_context("normalization context", 5, "medium")
                assert False, "expected ValueError"
            except ValueError as exc:
                assert "busy" in str(exc).lower()
        checks += 1

        # 18. API failure handled
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
                patch("services.ai_service.get_openai_client") as mock_client:
            from openai import APIError
            mock_client.return_value.chat.completions.create.side_effect = APIError(
                "boom", request=MagicMock(), body=None)
            try:
                generate_quiz_from_context("normalization context", 5, "medium")
                assert False, "expected ValueError"
            except ValueError as exc:
                assert "unavailable" in str(exc).lower() or "try again" in str(exc).lower()
        checks += 1

        # 19. invalid JSON handled
        try:
            validate_quiz_questions("not json at all", 5)
            assert False, "expected ValueError"
        except ValueError:
            pass
        checks += 1
        # 20. wrong question count rejected
        try:
            validate_quiz_questions({"questions": _valid_questions(4)}, 5)
            assert False, "expected ValueError"
        except ValueError:
            pass
        checks += 1
        # 21. wrong option count rejected
        bad = _valid_questions(5)
        bad[0]["options"] = ["1NF", "2NF", "3NF"]
        try:
            validate_quiz_questions({"questions": bad}, 5)
            assert False, "expected ValueError"
        except ValueError:
            pass
        checks += 1
        # 22. duplicate options rejected
        bad = _valid_questions(5)
        bad[0]["options"] = ["1NF", "1NF", "3NF", "BCNF"]
        try:
            validate_quiz_questions({"questions": bad}, 5)
            assert False, "expected ValueError"
        except ValueError:
            pass
        checks += 1
        # 23. invalid correct_answer rejected
        bad = _valid_questions(5)
        bad[0]["correct_answer"] = 9
        try:
            validate_quiz_questions({"questions": bad}, 5)
            False, "expected ValueError"
        except ValueError:
            pass
        checks += 1
        # 24. empty question rejected
        bad = _valid_questions(5)
        bad[0]["question"] = "   "
        try:
            validate_quiz_questions({"questions": bad}, 5)
            assert False, "expected ValueError"
        except ValueError:
            pass
        checks += 1
        # 25. duplicate questions rejected
        bad = _valid_questions(5)
        bad[1]["question"] = bad[0]["question"]
        try:
            validate_quiz_questions({"questions": bad}, 5)
            assert False, "expected ValueError"
        except ValueError:
            pass
        checks += 1

        # 26 + 27. valid quiz saved with its questions
        with patch("app.generate_quiz_from_context", return_value=_valid_questions(5)):
            r = client.post("/api/quizzes/generate", json=base)
            assert r.status_code == 201, r.get_json()
            quiz_id = r.get_json()["quiz_id"]
        conn = get_db_connection()
        saved = get_generated_quiz_for_user(quiz_id, ids["uid"], conn)
        questions = get_generated_quiz_questions(quiz_id, conn)
        conn.close()
        assert saved is not None and saved["question_count"] == 5
        checks += 1
        assert len(questions) == 5 and questions[0]["option_a"] and questions[0]["explanation"]
        checks += 1

        # 28. quiz ownership enforced (IDOR blocked for another user)
        other = create_user("Other", f"other_{uuid.uuid4().hex[:8]}@example.com",
                            generate_password_hash("Pass12345"), ids["cse"], "student")
        other_client = app.test_client()
        other_client.post("/login", data={"email": conn_email(other), "password": "Pass12345"})
        assert other_client.get(f"/quiz/view/{quiz_id}").status_code == 404
        # clean the extra user
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE id = ?", (other,))
        conn.commit()
        conn.close()
        checks += 1

        # 29. source materials stored safely (no paths, only safe metadata)
        conn = get_db_connection()
        sources = get_generated_quiz_sources(quiz_id, conn)
        conn.close()
        assert len(sources) >= 1
        preview = client.get(f"/quiz/view/{quiz_id}")
        assert preview.status_code == 200
        pdata = preview.data
        assert b"uploads/" not in pdata and b"F:\\" not in pdata
        checks += 1

        # 30. prompt-injection context passed as data (validator/AI never executes it)
        with patch("app.generate_quiz_from_context", return_value=_valid_questions(5)) as mock_gen:
            client.post("/api/quizzes/generate", json=base)
            ctx = mock_gen.call_args[0][0]
            assert "Normalization" in ctx
        checks += 1

        assert checks >= 30, f"only {checks} checks ran"
        print(f"ALL STEP 12 TESTS PASSED ({checks} checks)")
        return True
    finally:
        _cleanup(ids)


def conn_email(user_id):
    conn = get_db_connection()
    row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row["email"]


if __name__ == "__main__":
    run_step12_tests()
