"Focused Step 13 student dashboard tests."""
import unittest
import uuid
from werkzeug.security import generate_password_hash
from app import app
from database.db import (get_department_by_code, get_course_by_code, create_user,
    create_study_material, update_study_material_status, add_bookmark,
    create_quiz, create_quiz_attempt, get_student_dashboard_stats,
    get_student_course_progress)

class TestDashboardStep13(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        dept = get_department_by_code("CSE")
        course = get_course_by_code("CSE 221", dept["id"])
        token = uuid.uuid4().hex[:8]
        cls.email_a = f"step13_a_{token}@example.com"
        cls.email_b = f"step13_b_{token}@example.com"
        cls.user_a = create_user("Dashboard A", cls.email_a, generate_password_hash("Pass12345"), dept["id"], "student")
        cls.user_b = create_user("Dashboard B", cls.email_b, generate_password_hash("Pass12345"), dept["id"], "student")
        cls.material_a = create_study_material(course["id"], "Dashboard Material A", "midterm", "uploads/sample_study_guide.pdf", cls.user_a)
        cls.material_b = create_study_material(course["id"], "Dashboard Material B", "final", "uploads/sample_study_guide.pdf", cls.user_b)
        update_study_material_status(cls.material_a, "approved")
        update_study_material_status(cls.material_b, "approved")
        add_bookmark(cls.user_a, cls.material_a)
        questions = [{"question_type":"mcq", "question":"Q", "options_json":"[\"A\",\"B\",\"C\",\"D\"]", "correct_answer":"A", "expected_answer":None, "explanation":"E", "difficulty":"easy"}]
        cls.quiz_a = create_quiz(cls.material_a, cls.user_a, "Dashboard Quiz", "mcq", "easy", 1, questions)
        cls.attempt_a = create_quiz_attempt(cls.quiz_a, cls.user_a, 1, 1, 100, [])

    def login(self, client, email):
        return client.post("/login", data={"email": email, "password": "Pass12345"})

    def test_logged_out_dashboard_is_protected(self):
        response = app.test_client().get("/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)

    def test_dashboard_html_and_json_compatibility(self):
        client = app.test_client()
        self.login(client, self.email_a)
        html = client.get("/dashboard", headers={"Accept":"text/html"})
        self.assertEqual(html.status_code, 200)
        self.assertIn(b"Student Dashboard", html.data)
        self.assertIn(b"Dashboard Material A", html.data)
        self.assertNotIn(b"Dashboard Material B", html.data)
        legacy = client.get("/dashboard", headers={"Accept":"*/*"})
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.get_json()["status"], "authenticated")

    def test_stats_are_owned_and_calculated_server_side(self):
        stats_a = get_student_dashboard_stats(self.user_a)
        stats_b = get_student_dashboard_stats(self.user_b)
        self.assertEqual(stats_a["materials_count"], 1)
        self.assertEqual(stats_a["bookmarks_count"], 1)
        self.assertEqual(stats_a["quizzes_count"], 1)
        self.assertEqual(stats_a["attempts_count"], 1)
        self.assertEqual(stats_a["average_score"], 100)
        self.assertEqual(stats_b["materials_count"], 1)
        self.assertEqual(stats_b["quizzes_count"], 0)
        self.assertEqual(len(get_student_course_progress(self.user_a)), 1)

    def test_zero_activity_dashboard_loads(self):
        client = app.test_client()
        self.login(client, self.email_b)
        response = client.get("/dashboard", headers={"Accept":"text/html"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"haven't generated any quizzes", response.data)

    def test_admin_route_remains_admin_only(self):
        client = app.test_client()
        self.login(client, self.email_a)
        self.assertEqual(client.get("/admin/dashboard").status_code, 403)

if __name__ == "__main__":
    unittest.main()
