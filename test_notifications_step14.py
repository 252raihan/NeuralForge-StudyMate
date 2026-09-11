"Focused Step 14 in-app notification tests."""
import unittest
import uuid
from werkzeug.security import generate_password_hash
from app import app
from database.db import (
    create_user, get_department_by_code, create_notification,
    get_user_notifications, count_unread_notifications,
    mark_notification_as_read, mark_all_notifications_as_read,
)

class TestNotificationsStep14(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        dept = get_department_by_code("CSE")
        token = uuid.uuid4().hex[:8]
        cls.email_a = f"step14_a_{token}@example.com"
        cls.email_b = f"step14_b_{token}@example.com"
        cls.user_a = create_user("Notify A", cls.email_a, generate_password_hash("Pass12345"), dept["id"], "student")
        cls.user_b = create_user("Notify B", cls.email_b, generate_password_hash("Pass12345"), dept["id"], "student")
        cls.notification_a = create_notification(cls.user_a, "material_approved", "Approved", "Material approved.", "/dashboard")
        create_notification(cls.user_a, "quiz_completed", "Quiz completed", "Score: 8/10.", "/dashboard")
        create_notification(cls.user_b, "material_rejected", "Rejected", "Material rejected.", "/dashboard")

    def login(self, client, email):
        return client.post("/login", data={"email": email, "password": "Pass12345"})

    def test_authentication(self):
        client = app.test_client()
        self.assertEqual(client.get("/notifications").status_code, 302)
        self.assertEqual(client.post(f"/notifications/{self.notification_a}/read").status_code, 302)
        self.assertEqual(client.post("/notifications/read-all").status_code, 302)

    def test_user_scoping_and_list(self):
        create_notification(self.user_a, "material_approved", "Fresh approval", "A fresh notification.", "/dashboard")
        client = app.test_client()
        self.login(client, self.email_a)
        page = client.get("/notifications", headers={"Accept": "text/html"})
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Quiz completed", page.data)
        self.assertNotIn(b"Rejected", page.data)
        self.assertIn(b"Mark all as", page.data)
        self.assertEqual(client.post(f"/notifications/{self.notification_a + 2}/read").status_code, 404)

    def test_read_state_is_owned(self):
        self.assertGreaterEqual(count_unread_notifications(self.user_a), 1)
        self.assertFalse(mark_notification_as_read(self.user_b, self.notification_a))
        self.assertTrue(mark_notification_as_read(self.user_a, self.notification_a))
        self.assertEqual(count_unread_notifications(self.user_a), 1)
        changed = mark_all_notifications_as_read(self.user_a)
        self.assertEqual(changed, 1)
        self.assertEqual(count_unread_notifications(self.user_a), 0)
        self.assertGreaterEqual(count_unread_notifications(self.user_b), 1)

    def test_filters_pagination_and_safe_link(self):
        client = app.test_client()
        self.login(client, self.email_a)
        self.assertEqual(client.get("/notifications?type=quiz_completed").status_code, 200)
        self.assertEqual(client.get("/notifications?read=unread").status_code, 200)
        self.assertEqual(client.get("/notifications?page=bad").status_code, 200)
        self.assertEqual(client.get("/notifications?type=invalid").status_code, 200)
        self.assertEqual(client.post(f"/notifications/{self.notification_a}/read").status_code, 302)

    def test_invalid_external_link_rejected(self):
        with self.assertRaises(ValueError):
            create_notification(self.user_a, "new_material", "Unsafe", "Unsafe", "https://example.com")

if __name__ == "__main__":
    unittest.main()
