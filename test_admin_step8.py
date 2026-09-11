"Focused Step 8 admin approval workflow tests."""
import io
import uuid
from pathlib import Path
from werkzeug.security import generate_password_hash
from app import app
from database.db import (
    get_department_by_code, get_course_by_code, create_user,
    create_study_material, get_study_material_details,
    get_pending_study_materials,
)


def run_step8_tests():
    app.config["TESTING"] = True
    pdf_bytes = Path("sample_study_guide.pdf").read_bytes()
    with app.app_context():
        dept = get_department_by_code("CSE")
        course = get_course_by_code("CSE 221", dept["id"])
        token = uuid.uuid4().hex[:8]
        student_email = f"step8_student_{token}@example.com"
        admin_email = f"step8_admin_{token}@example.com"
        student_id = create_user("Step 8 Student", student_email,
                                 generate_password_hash("Pass12345"), dept["id"], "student")
        admin_id = create_user("Step 8 Admin", admin_email,
                               generate_password_hash("AdminPass123"), None, "admin")
        pending_id = create_study_material(course["id"], "Step 8 Approve Topic", "midterm",
                                           "uploads/sample_study_guide.pdf", student_id)
        reject_id = create_study_material(course["id"], "Step 8 Reject Topic", "final",
                                          "uploads/sample_study_guide.pdf", student_id)

    anon = app.test_client()
    student = app.test_client()
    admin = app.test_client()

    # 1-2: authorization
    assert anon.get("/admin/dashboard").status_code == 302
    student.post("/login", data={"email": student_email, "password": "Pass12345"})
    assert student.get("/admin/dashboard").status_code == 403
    assert student.get(f"/admin/material/{pending_id}").status_code == 403
    assert student.post(f"/admin/material/{pending_id}/approve").status_code == 403
    assert student.post(f"/admin/material/{pending_id}/reject").status_code == 403
    # 3-6, 16, 18: admin dashboard, pending queue, details and controlled PDF
    admin.post("/login", data={"email": admin_email, "password": "AdminPass123"})
    dashboard = admin.get("/admin/dashboard")
    assert dashboard.status_code == 200
    assert b"Step 8 Approve Topic" in dashboard.data
    assert b"Step 8 Reject Topic" in dashboard.data
    detail = admin.get(f"/admin/material/{pending_id}")
    assert detail.status_code == 200
    assert b"CSE 221" in detail.data and b"Step 8 Student" in detail.data
    pdf = admin.get(f"/admin/material/{pending_id}/pdf")
    assert pdf.status_code == 200 and pdf.content_type.startswith("application/pdf")
    assert b"F:\\NeuralForge-StudyMate" not in detail.data
    assert admin.get("/admin/material/999").status_code == 302
    # 7-9: approval and removal from pending queue
    approved = admin.post(f"/admin/material/{pending_id}/approve",
                          headers={"Accept": "application/json"})
    assert approved.status_code == 200
    assert approved.get_json()["status"] == "approved"
    assert get_study_material_details(pending_id)["status"] == "approved"
    assert pending_id not in [row["id"] for row in get_pending_study_materials()]

    # 10-12: rejection and removal from pending queue
    rejected = admin.post(f"/admin/material/{reject_id}/reject",
                          headers={"Accept": "application/json"})
    assert rejected.status_code == 200
    assert rejected.get_json()["status"] == "rejected"
    assert get_study_material_details(reject_id)["status"] == "rejected"
    assert reject_id not in [row["id"] for row in get_pending_study_materials()]

    # Invalid IDs and GET status mutation protection
    assert admin.post("/admin/material/999/approve",
                      headers={"Accept": "application/json"}).status_code == 404
    assert admin.get(f"/admin/material/{pending_id}/approve").status_code == 405
    # Existing student workflow and summary endpoint remain available.
    upload = student.post("/study-material/upload", data={
        "course_id": str(course["id"]), "exam_type": "both", "topic": "Regression Topic",
        "file": (io.BytesIO(pdf_bytes), "step8_regression.pdf")
    }, content_type="multipart/form-data", headers={"Accept": "application/json"})
    assert upload.status_code == 201 and upload.get_json()["status"] == "pending"
    assert student.get("/my-study-materials").status_code == 200
    summary = student.post("/summarize", json={"text": "Regression text for summary."})
    assert summary.status_code in (200, 400)

    print("ALL STEP 8 TESTS PASSED")
    return True
if __name__ == "__main__":
    run_step8_tests()
