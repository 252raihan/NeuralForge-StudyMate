"Test-only Step 10 server launcher with deterministic AI and content fixtures."""
import uuid
from werkzeug.security import generate_password_hash
import app as app_module
from database.db import (
    get_db_connection, get_department_by_code, get_course_by_code, create_user,
    create_study_material, update_study_material_status,
)
app = app_module.app
app.config["CSRF_PROTECTION"] = False
# Seed a login-capable student and an approved material with stored text for Q&A QA.
BROWSER_EMAIL = "step10_browser@example.com"
BROWSER_PASSWORD = "Pass12345"
with app.app_context():
    _conn = get_db_connection()
    _cse = get_department_by_code("CSE", _conn)
    _course = get_course_by_code("CSE 221", _cse["id"], _conn)
    _row = _conn.execute("SELECT id FROM users WHERE email = ?", (BROWSER_EMAIL,)).fetchone()
    _uid = _row["id"] if _row else create_user(
        "Step 10 Browser", BROWSER_EMAIL, generate_password_hash(BROWSER_PASSWORD),
        _cse["id"], "student", conn=_conn)
    _existing = _conn.execute("SELECT id FROM study_materials WHERE topic = 'Browser Normalization'").fetchone()
    if not _existing:
        create_study_material(
            _course["id"], "Browser Normalization", "midterm",
            "uploads/sample_study_guide.pdf", _uid, status="approved",
            extracted_text="Normalization organizes data to reduce redundancy. 1NF, 2NF and 3NF are common normal forms.",
            conn=_conn)
    if not _conn.execute("SELECT id FROM study_materials WHERE topic = 'Browser Pending Secret'").fetchone():
        create_study_material(
            _course["id"], "Browser Pending Secret", "final",
            "uploads/sample_study_guide.pdf", _uid, status="pending",
            extracted_text="Pending secret normalization content that must never surface.",
            conn=_conn)
    _conn.close()

# Step 11: build the RAG chunk index for every material (approval still gates retrieval).
from services.rag_service import index_material
with app.app_context():
    _i = get_db_connection()
    for _r in _i.execute("SELECT id FROM study_materials WHERE topic IN ('Browser Normalization', 'Browser Pending Secret')"):
        index_material(_r["id"], conn=_i)
    _i.close()


def fake_answer(question, context):
    return {
        "success": True,
        "answer": "### Normalization\nNormalization reduces data redundancy by organizing tables into well-formed relations (1NF, 2NF, 3NF).",
        "model_used": "mock-model",
    }

app_module.answer_study_question = fake_answer

def fake_quiz_from_context(context, number_of_questions, difficulty, course_name=None, topic=None):
    # Deterministic MCQs for browser QA; never calls a real AI API.
    questions = []
    for index in range(number_of_questions):
        questions.append({
            "question": "Sample normalization question " + str(index + 1) + "?",
            "options": ["1NF", "2NF", "3NF", "BCNF"],
            "correct_answer": 1,
            "explanation": "Second normal form removes partial dependency.",
        })
    return questions
app_module.generate_quiz_from_context = fake_quiz_from_context

def fake_content(material):
    if material and material["status"] == "approved":
        return "Database normalization organizes relational data and reduces redundancy."
    return None

def fake_quiz(text, question_type, difficulty, count):
    questions = []
    mcq_count = (count + 1) // 2 if question_type == "mixed" else (count if question_type == "mcq" else 0)
    for index in range(count):
        if index < mcq_count:
            questions.append({"question_type": "mcq", "question": f"Which statement is supported by the material? {index + 1}", "options_json": '["Normalization reduces redundancy", "It removes all tables", "It requires no keys", "It prevents relationships"]', "correct_answer": "Normalization reduces redundancy", "expected_answer": None, "explanation": "The material states that normalization reduces redundancy.", "difficulty": difficulty if difficulty != "mixed" else "medium"})
        else:
            questions.append({"question_type": "short", "question": f"What does normalization reduce? {index + 1}", "options_json": None, "correct_answer": None, "expected_answer": "redundancy", "explanation": "Normalization reduces redundancy.", "difficulty": difficulty if difficulty != "mixed" else "medium"})
    return questions
app_module._approved_material_content = fake_content
app_module.generate_quiz_questions = fake_quiz
app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)
