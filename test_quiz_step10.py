"Focused Step 10 quiz generator tests."""
import json
import unittest
from unittest.mock import patch, MagicMock
from app import app
from services.ai_service import _validate_quiz_questions

def valid_payload(kind="mcq", count=1):
    questions = []
    for index in range(count):
        if kind == "short":
            questions.append({"type": "short", "question": f"Define concept {index}", "expected_answer": "database", "explanation": "The supplied material defines it.", "difficulty": "medium"})
        else:
            questions.append({"type": "mcq", "question": f"Which is true {index}?", "options": ["A", "B", "C", "D"], "correct_answer": "A", "explanation": "A is supported by the material.", "difficulty": "medium"})
    return {"questions": questions}

class TestQuizStep10(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_logged_out_quiz_routes_are_protected(self):
        self.assertEqual(self.client.get("/quiz/create/1").status_code, 302)
        self.assertEqual(self.client.post("/quiz/generate/1").status_code, 302)
        self.assertEqual(self.client.get("/quiz/1").status_code, 302)
        self.assertEqual(self.client.post("/quiz/1/submit").status_code, 302)

    def test_ai_validation_rejects_invalid_mcq_and_duplicates(self):
        bad = valid_payload()
        bad["questions"][0]["options"] = ["A", "B"]
        with self.assertRaises(ValueError):
            _validate_quiz_questions(bad, "mcq", "medium", 1)
        duplicate = valid_payload("mcq", 2)
        duplicate["questions"][1]["question"] = duplicate["questions"][0]["question"]
        with self.assertRaises(ValueError):
            _validate_quiz_questions(duplicate, "mcq", "medium", 2)

    def test_ai_validation_supports_short_and_mixed(self):
        short = _validate_quiz_questions(valid_payload("short"), "short", "medium", 1)
        self.assertEqual(short[0]["question_type"], "short")
        mixed = {"questions": valid_payload("mcq")["questions"] + valid_payload("short")["questions"]}
        result = _validate_quiz_questions(mixed, "mixed", "medium", 2)
        self.assertEqual({item["question_type"] for item in result}, {"mcq", "short"})

    def test_generation_validates_count_and_approved_material(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 41
        material = {"id": 7, "status": "approved", "file_path": "uploads/guide.pdf", "topic": "Transactions", "course_code": "CSE 221", "course_name": "DBMS", "department_code": "CSE", "exam_type": "midterm"}
        with patch("app.get_study_material_details", return_value=material), patch("app._approved_material_content", return_value="transaction content"), patch("app.generate_quiz_questions", return_value=[{"question_type": "mcq", "question": "Q", "options_json": json.dumps(["A", "B", "C", "D"]), "correct_answer": "A", "expected_answer": None, "explanation": "Because.", "difficulty": "easy"}]), patch("app.create_quiz", return_value=9) as create:
            response = self.client.post("/quiz/generate/7", data={"question_type": "mcq", "difficulty": "easy", "question_count": "1"})
        self.assertEqual(response.status_code, 302)
        create.assert_called_once()
        self.assertEqual(create.call_args.args[1], 41)

    def test_quiz_page_does_not_render_answer_keys(self):
        quiz = {"id": 3, "title": "Private Quiz", "topic": "Topic", "course_code": "CSE 221", "question_count": 1, "difficulty": "easy"}
        question = {"id": 1, "question_text": "What?", "question_type": "mcq", "options_json": json.dumps(["A", "B", "C", "D"]), "correct_answer": "A", "expected_answer": None, "explanation": "Hidden", "difficulty": "easy"}
        with self.client.session_transaction() as session:
            session["user_id"] = 41
        with patch("app.get_quiz_for_user", return_value=quiz), patch("app.get_quiz_questions", return_value=[question]):
            response = self.client.get("/quiz/3")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"correct_answer", response.data)
        self.assertNotIn(b"expected_answer", response.data)
        self.assertIn(b">A<", response.data)  # options are public; only answer keys must remain private

if __name__ == "__main__":
    unittest.main()
