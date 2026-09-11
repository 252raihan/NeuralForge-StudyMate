"Test-only Step 10 server launcher with deterministic AI and content fixtures."""
import app as app_module
app = app_module.app

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
app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
