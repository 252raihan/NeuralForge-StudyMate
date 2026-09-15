"Focused Step 9 public Study Notes Library tests."""
import io
import uuid
from pathlib import Path
from werkzeug.security import generate_password_hash
from app import app
from tests_helpers import unique_pdf
from database.db import (
    get_department_by_code, get_course_by_code, get_department_by_id,
    create_user, create_study_material, get_study_material_details,
    update_study_material_status,
)


def run_step9_tests():
    app.config["TESTING"] = True
    pdf = Path("sample_study_guide.pdf").read_bytes()
    with app.app_context():
        cse = get_department_by_code("CSE")
        eee = get_department_by_code("EEE")
        cse_course = get_course_by_code("CSE 221", cse["id"])
        eee_course = get_course_by_code("EEE 101", eee["id"])
        token = uuid.uuid4().hex[:8]
        student_email = f"step9_student_{token}@example.com"
        student_id = create_user("Step 9 Student", student_email,
                                 generate_password_hash("Pass12345"), cse["id"], "student")
        approved_id = create_study_material(cse_course["id"], "Database Normalization", "midterm",
                                            "uploads/sample_study_guide.pdf", student_id)
        pending_id = create_study_material(cse_course["id"], "Pending Secret Topic", "final",
                                           "uploads/sample_study_guide.pdf", student_id)
        rejected_id = create_study_material(eee_course["id"], "Rejected Circuit Topic", "both",
                                            "uploads/sample_study_guide.pdf", student_id)
        update_study_material_status(approved_id, "approved")
        update_study_material_status(rejected_id, "rejected")
        cse_id, cse_course_id = cse["id"], cse_course["id"]

    client = app.test_client()
    # 1: public access without login
    library = client.get("/study-library")
    assert library.status_code == 200
    assert b"Study Notes Library" in library.data
    assert b"Database Normalization" in library.data
    assert b"Pending Secret Topic" not in library.data
    assert b"Rejected Circuit Topic" not in library.data
    assert b"F:\\NeuralForge-StudyMate" not in library.data
    # 5-11: department, course, relationship, exam, topic, course code, combined filters
    assert b"Database Normalization" in client.get(f"/study-library?department_id={cse_id}").data
    assert b"Database Normalization" in client.get(f"/study-library?course_id={cse_course_id}").data
    assert b"Database Normalization" in client.get("/study-library?exam_type=midterm").data
    assert b"Database Normalization" in client.get("/study-library?topic=normalization").data
    assert b"Database Normalization" in client.get("/study-library?course_code=CSE+221").data
    combined = client.get(f"/study-library?department_id={cse_id}&course_id={cse_course_id}&exam_type=midterm&topic=normalization&course_code=CSE+221")
    assert b"Database Normalization" in combined.data
    # Invalid relationship must not leak results.
    assert b"Database Normalization" not in client.get(f"/study-library?department_id={eee['id']}&course_id={cse_course_id}").data
    assert client.get("/study-library?exam_type=unsupported").status_code == 200
    # 12-18: approved PDF works; pending/rejected/invalid IDs are blocked.
    approved_pdf = client.get(f"/study-library/material/{approved_id}/pdf")
    assert approved_pdf.status_code == 200
    assert approved_pdf.content_type.startswith("application/pdf")
    download = client.get(f"/study-library/material/{approved_id}/download")
    assert download.status_code == 200
    assert "attachment" in download.headers.get("Content-Disposition", "")
    for material_id in (pending_id, rejected_id, 999):
        assert client.get(f"/study-library/material/{material_id}/pdf").status_code == 404
        assert client.get(f"/study-library/material/{material_id}/download").status_code == 404
    # 19: private path is never rendered or returned as an application path.
    assert b"uploads/" not in library.data
    # 20-23: existing upload, history, auth and summary.
    upload = client.post("/study-material/upload", data={
        "course_id": str(cse_course_id), "exam_type": "both", "topic": "Step 9 Regression",
        "file": (io.BytesIO(unique_pdf(pdf)), "step9_regression.pdf")
    }, content_type="multipart/form-data", headers={"Accept": "application/json"})
    assert upload.status_code == 302
    login = client.post("/login", data={"email": student_email, "password": "Pass12345"})
    assert login.status_code == 302
    assert client.get("/my-study-materials").status_code == 200
    assert client.get("/dashboard").status_code == 200
    summary = client.post("/summarize", json={"text": "Step 9 regression text."})
    assert summary.status_code in (200, 400)
    print("ALL STEP 9 TESTS PASSED")
    return True
if __name__ == "__main__":
    run_step9_tests()
