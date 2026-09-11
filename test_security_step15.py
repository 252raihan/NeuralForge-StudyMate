"Step 15 security hardening tests."""
import io
import unittest
import uuid
from app import app, is_allowed_pdf
from database.db import create_notification, get_department_by_code, create_user
from werkzeug.security import generate_password_hash
class TestSecurityStep15(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_headers_and_public_safe_errors(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self.client.get("/does-not-exist").status_code, 404)
        self.assertNotIn(b"Traceback", self.client.get("/does-not-exist").data)

    def test_csrf_rejects_when_enabled(self):
        old = app.config["CSRF_PROTECTION"]
        old_testing = app.config["TESTING"]
        app.config["CSRF_PROTECTION"] = True
        app.config["TESTING"] = False
        try:
            response = self.client.post("/login", data={"email":"nobody@example.com", "password":"bad"})
            self.assertEqual(response.status_code, 400)
            with self.client.session_transaction() as session:
                token = session["csrf_token"]
            valid = self.client.post("/login", data={"email":"nobody@example.com", "password":"bad", "csrf_token":token})
            self.assertEqual(valid.status_code, 401)
        finally:
            app.config["CSRF_PROTECTION"] = old
            app.config["TESTING"] = old_testing
    def test_pdf_validation(self):
        self.assertFalse(is_allowed_pdf("../secret.txt"))
        self.assertFalse(is_allowed_pdf("safe.pdf\x00.txt"))
        response = self.client.post("/upload", data={"course_name":"CSE", "course_code":"CSE 221", "topic":"X", "file":(io.BytesIO(b"not a pdf"), "fake.pdf")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_safe_notification_link_and_ownership(self):
        dept = get_department_by_code("CSE")
        token = uuid.uuid4().hex[:8]
        user_a = create_user("Security A", f"security_a_{token}@example.com", generate_password_hash("Pass12345"), dept["id"], "student")
        user_b = create_user("Security B", f"security_b_{token}@example.com", generate_password_hash("Pass12345"), dept["id"], "student")
        with self.assertRaises(ValueError):
            create_notification(user_a, "new_material", "Unsafe", "Message", "https://evil.example")
        notification_id = create_notification(user_a, "new_material", "Private", "A private notification", "/dashboard")
        self.client.post("/login", data={"email":f"security_b_{token}@example.com", "password":"Pass12345"})
        self.assertEqual(self.client.post(f"/notifications/{notification_id}/read").status_code, 404)

    def test_external_next_is_not_followed(self):
        response = self.client.get("/login?next=https://evil.example")
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
