"""Focused Step 14.5 security hardening tests.

These assert real behavior (HTTP responses, database state), not that the
implementation text exists.
"""

import io
import unittest
import uuid

from werkzeug.security import generate_password_hash

from app import app
from tests_helpers import unique_pdf
from database.db import (
    get_db_connection,
    get_department_by_code,
    get_course_by_code,
    create_user,
)
from services.auth_service import validate_password_strength, register_student


class TestStep145Hardening(unittest.TestCase):
    def setUp(self):
        # CSRF protection is ON for these tests; we drive it explicitly.
        app.config["CSRF_PROTECTION"] = True
        app.config["TESTING"] = False
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = False

    # --- CSRF: JSON endpoints must require the token -----------------------
    def test_json_post_without_csrf_is_rejected(self):
        resp = self.client.post("/api/ask-studymate", json={"question": "what is normalization?"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("security token", resp.get_json()["error"].lower())

    def test_json_post_with_valid_csrf_header_is_accepted(self):
        # Prime a session + token by rendering a page that embeds it.
        self.client.get("/")
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"]
        # Authenticated JSON API still requires login, but CSRF must pass first:
        # expect a login redirect / 302 rather than a CSRF 400.
        resp = self.client.post(
            "/api/ask-studymate",
            json={"question": "what is normalization?"},
            headers={"X-CSRF-Token": token},
        )
        self.assertNotEqual(resp.status_code, 400)

    def test_summarize_json_requires_csrf(self):
        resp = self.client.post("/summarize", json={"text": "hello world"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("security token", resp.get_json()["error"].lower())

    # --- Logout must be POST-only ------------------------------------------
    def test_get_logout_is_not_allowed(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_post_logout_requires_csrf(self):
        with app.app_context():
            dept = get_department_by_code("CSE")
            email = f"step145_{uuid.uuid4().hex[:8]}@example.com"
            create_user("S145", email, generate_password_hash("Pass12345"),
                        dept["id"], "student")
        # Log in with a valid CSRF token.
        self.client.get("/")
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"]
        self.client.post("/login", data={"email": email, "password": "Pass12345",
                                         "csrf_token": token})
        # Logout without a token -> rejected.
        self.assertEqual(self.client.post("/logout").status_code, 400)
        # login_session clears the session, so re-read the (new) token.
        self.client.get("/dashboard")
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"]
        # Logout with the token -> redirect to login and session cleared.
        resp = self.client.post("/logout", data={"csrf_token": token})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers.get("Location"))
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # --- Admin authorization is revalidated against the DB -----------------
    def test_admin_route_rejects_demoted_user_even_with_stale_session(self):
        with app.app_context():
            dept = get_department_by_code("CSE")
            token = uuid.uuid4().hex[:8]
            email = f"admin_demote_{token}@example.com"
            uid = create_user("Admin Demote", email,
                              generate_password_hash("AdminPass123"), dept["id"], "admin")
        self.client.get("/")
        with self.client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        self.client.post("/login", data={"email": email, "password": "AdminPass123",
                                         "csrf_token": csrf})
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 200)
        # Demote in the database; session still says admin.
        with app.app_context():
            conn = get_db_connection()
            try:
                conn.execute("UPDATE users SET role = 'student' WHERE id = ?", (uid,))
                conn.commit()
            finally:
                conn.close()
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 403)

    # --- Password policy ----------------------------------------------------
    def test_password_policy_rejects_short_passwords(self):
        ok, msg = validate_password_strength("short")
        self.assertFalse(ok)
        self.assertIn("at least", msg)

    def test_password_policy_accepts_reasonable_password(self):
        ok, _ = validate_password_strength("StudyNotes2024")
        self.assertTrue(ok)

    def test_registration_enforces_minimum_length(self):
        with app.app_context():
            dept = get_department_by_code("CSE")
            success, err, _ = register_student(
                "Short Pw", f"shortpw_{uuid.uuid4().hex[:8]}@example.com",
                "abc123", "abc123", dept["id"],
            )
            self.assertFalse(success)
            self.assertIn("at least", err)

    # --- SHA-256 duplicate content detection --------------------------------
    def test_duplicate_pdf_content_is_rejected(self):
        app.config["TESTING"] = True
        with app.app_context():
            dept = get_department_by_code("CSE")
            course = get_course_by_code("CSE 221", dept["id"])
            email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
            create_user("Dup User", email, generate_password_hash("Pass12345"),
                        dept["id"], "student")
            course_id = course["id"]

        client = app.test_client()
        client.post("/login", data={"email": email, "password": "Pass12345"})
        from pathlib import Path
        base_pdf = Path("sample_study_guide.pdf").read_bytes()
        payload = unique_pdf(base_pdf)
        r1 = client.post("/study-material/upload", data={
            "course_id": str(course_id), "exam_type": "midterm",
            "topic": "Duplicate Test",
            "file": (io.BytesIO(payload), "first.pdf"),
        }, content_type="multipart/form-data", headers={"Accept": "application/json"})
        self.assertEqual(r1.status_code, 201)
        r2 = client.post("/study-material/upload", data={
            "course_id": str(course_id), "exam_type": "midterm",
            "topic": "Duplicate Test 2",
            "file": (io.BytesIO(payload), "second.pdf"),
        }, content_type="multipart/form-data", headers={"Accept": "application/json"})
        self.assertEqual(r2.status_code, 409)


if __name__ == "__main__":
    unittest.main()
