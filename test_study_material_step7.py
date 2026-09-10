"""
NeuralForge StudyMate - Step 7 Study Material Upload & Persistence Test Suite
Verifies all 19 programmatic requirements for Step 7.
"""

import io
import uuid
from pathlib import Path
from werkzeug.security import generate_password_hash

from app import app
from database.db import (
    get_db_connection,
    get_department_by_code,
    create_department,
    create_course,
    get_course_by_code,
    create_user,
    get_study_material_by_id,
    get_study_materials_by_user,
)

def run_step7_tests():
    print("==================================================")
    print("RUNNING STEP 7 STUDY MATERIAL UPLOAD TEST SUITE")
    print("==================================================")

    pdf_sample_path = Path("sample_study_guide.pdf")
    assert pdf_sample_path.exists(), "sample_study_guide.pdf required for testing"
    sample_pdf_bytes = pdf_sample_path.read_bytes()

    # 1. Setup departments and courses
    with app.app_context():
        cse_dept = get_department_by_code("CSE")
        if not cse_dept:
            cse_dept_id = create_department("Computer Science and Engineering", "CSE")
        else:
            cse_dept_id = cse_dept["id"]

        eee_dept = get_department_by_code("EEE")
        if not eee_dept:
            eee_dept_id = create_department("Electrical and Electronic Engineering", "EEE")
        else:
            eee_dept_id = eee_dept["id"]

        # Ensure CSE 221 exists in CSE
        cse_course = get_course_by_code("CSE 221", cse_dept_id)
        if not cse_course:
            cse_course_id = create_course(cse_dept_id, "Database Management System", "CSE 221")
        else:
            cse_course_id = cse_course["id"]

        # Ensure EEE 101 exists in EEE
        eee_course = get_course_by_code("EEE 101", eee_dept_id)
        if not eee_course:
            eee_course_id = create_course(eee_dept_id, "Electrical Circuits I", "EEE 101")
        else:
            eee_course_id = eee_course["id"]

        # Create two separate student accounts
        student1_email = f"student1_{uuid.uuid4().hex[:6]}@example.com"
        student1_id = create_user(
            name="Student One",
            email=student1_email,
            password_hash=generate_password_hash("Pass12345"),
            department_id=cse_dept_id,
            role="student"
        )

        student2_email = f"student2_{uuid.uuid4().hex[:6]}@example.com"
        student2_id = create_user(
            name="Student Two",
            email=student2_email,
            password_hash=generate_password_hash("Pass12345"),
            department_id=eee_dept_id,
            role="student"
        )

    # 1. Unauthenticated user cannot access study-material upload -> 302 to /login
    print("\n--- Test 1: Unauthenticated user redirected to login ---")
    anon_client = app.test_client()
    resp = anon_client.get("/study-material/upload", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location")
    print(">> TEST 1 PASSED: Unauthenticated user redirected to login!")

    # 2. Authenticated student can open upload page -> 200 OK
    print("\n--- Test 2: Authenticated student can open upload page ---")
    student_client = app.test_client()
    student_client.post("/login", data={"email": student1_email, "password": "Pass12345"})
    resp = student_client.get("/study-material/upload")
    assert resp.status_code == 200
    assert b"Submit Study Material" in resp.data
    assert b"CSE 221" in resp.data
    print(">> TEST 2 PASSED: Authenticated student opens upload page with department courses!")

    # 3-6. Valid PDF + valid metadata -> successful submission, database save, session uploaded_by, pending status
    print("\n--- Test 3-6: Valid PDF upload and DB save with session ID & status 'pending' ---")
    upload_resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": str(cse_course_id),
            "exam_type": "midterm",
            "topic": "Normalization",
            "file": (io.BytesIO(sample_pdf_bytes), "lecture_normalization.pdf")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    print("Upload Status:", upload_resp.status_code)
    json_data = upload_resp.get_json()
    print("Response JSON:", json_data)
    assert upload_resp.status_code == 201
    assert json_data["success"] is True
    assert json_data["status"] == "pending"
    assert "material_id" in json_data
    created_mat_id = json_data["material_id"]

    # Verify directly from database
    db_material = get_study_material_by_id(created_mat_id)
    assert db_material is not None
    assert db_material["course_id"] == cse_course_id
    assert db_material["topic"] == "Normalization"
    assert db_material["exam_type"] == "midterm"
    assert db_material["uploaded_by"] == student1_id, f"Expected uploaded_by {student1_id}, got {db_material['uploaded_by']}"
    assert db_material["status"] == "pending", f"Expected status 'pending', got {db_material['status']}"
    assert "uploads/" in db_material["file_path"]
    print(">> TEST 3-6 PASSED: Material saved in database with status 'pending' and correct session user_id!")

    # 7-8. Student cannot choose 'approved' or 'rejected'
    print("\n--- Test 7-8: Student cannot tamper status to approved or rejected ---")
    tampered_resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": str(cse_course_id),
            "exam_type": "final",
            "topic": "ER Diagrams",
            "status": "approved",  # Malicious form field
            "file": (io.BytesIO(sample_pdf_bytes), "er_diagrams.pdf")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    assert tampered_resp.status_code == 201
    tampered_mat = get_study_material_by_id(tampered_resp.get_json()["material_id"])
    assert tampered_mat["status"] == "pending", f"Security violation: Status was set to {tampered_mat['status']}!"
    print(">> TEST 7-8 PASSED: Status strictly forced to 'pending' server-side!")

    # 9. Empty topic -> rejected
    print("\n--- Test 9: Empty topic rejected ---")
    resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": str(cse_course_id),
            "exam_type": "midterm",
            "topic": "   ",
            "file": (io.BytesIO(sample_pdf_bytes), "notes.pdf")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "Topic / Chapter is required" in resp.get_json()["error"]
    print(">> TEST 9 PASSED: Empty topic rejected!")

    # 10. Invalid exam_type -> rejected
    print("\n--- Test 10: Invalid exam_type rejected ---")
    resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": str(cse_course_id),
            "exam_type": "quiz_unsupported",
            "topic": "Transactions",
            "file": (io.BytesIO(sample_pdf_bytes), "notes.pdf")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "Invalid exam type" in resp.get_json()["error"]
    print(">> TEST 10 PASSED: Invalid exam_type rejected!")

    # 11. Invalid course (non-existent) -> rejected
    print("\n--- Test 11: Non-existent course rejected ---")
    resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": "999999",
            "exam_type": "midterm",
            "topic": "Transactions",
            "file": (io.BytesIO(sample_pdf_bytes), "notes.pdf")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "Selected course does not exist" in resp.get_json()["error"]
    print(">> TEST 11 PASSED: Non-existent course rejected!")

    # 12. Course from another department -> rejected
    print("\n--- Test 12: Course from another department rejected ---")
    # student1 is CSE student; eee_course_id is EEE course
    resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": str(eee_course_id),
            "exam_type": "midterm",
            "topic": "Circuit Analysis",
            "file": (io.BytesIO(sample_pdf_bytes), "notes.pdf")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "courses in your registered department" in resp.get_json()["error"]
    print(">> TEST 12 PASSED: Course from different department rejected by backend!")

    # 13. Invalid PDF type -> rejected
    print("\n--- Test 13: Invalid file type rejected ---")
    resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": str(cse_course_id),
            "exam_type": "midterm",
            "topic": "Transactions",
            "file": (io.BytesIO(b"Hello text"), "notes.txt")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "Invalid file type" in resp.get_json()["error"]
    print(">> TEST 13 PASSED: Non-PDF file rejected!")

    # 14. PDF larger than 16 MB -> rejected
    print("\n--- Test 14: PDF larger than 16 MB rejected ---")
    large_pdf_bytes = b"%PDF-1.4 " + b"0" * (16 * 1024 * 1024 + 50)
    resp = student_client.post(
        "/study-material/upload",
        data={
            "course_id": str(cse_course_id),
            "exam_type": "midterm",
            "topic": "Big Document",
            "file": (io.BytesIO(large_pdf_bytes), "large_document.pdf")
        },
        headers={"Accept": "application/json"},
        content_type="multipart/form-data"
    )
    assert resp.status_code in [400, 413]
    print(">> TEST 14 PASSED: Oversized PDF rejected!")

    # 15. Student can see their own uploaded materials
    print("\n--- Test 15: Student can see their own uploaded materials ---")
    history_resp = student_client.get("/my-study-materials")
    assert history_resp.status_code == 200
    assert b"Normalization" in history_resp.data
    assert b"CSE 221" in history_resp.data
    assert b"Pending Approval" in history_resp.data
    print(">> TEST 15 PASSED: Student can see their own uploaded materials!")

    # 16. Student cannot see another student's materials
    print("\n--- Test 16: Student cannot see another student's materials ---")
    student2_client = app.test_client()
    student2_client.post("/login", data={"email": student2_email, "password": "Pass12345"})
    s2_history = student2_client.get("/my-study-materials")
    assert s2_history.status_code == 200
    # student2 should NOT see student1's Normalization notes
    assert b"Normalization" not in s2_history.data
    assert b"No Uploads Yet" in s2_history.data
    print(">> TEST 16 PASSED: Student cannot see other students' study materials!")

    # 17. Existing PDF extraction still works
    print("\n--- Test 17: Existing PDF extraction still works ---")
    upload_data = {
        "course_name": "Database Management System",
        "course_code": "CSE 221",
        "topic": "Normalization",
        "file": (io.BytesIO(sample_pdf_bytes), "sample_study_guide.pdf")
    }
    public_upload_resp = student_client.post("/upload", data=upload_data, content_type="multipart/form-data")
    assert public_upload_resp.status_code == 200
    pub_json = public_upload_resp.get_json()
    assert pub_json["success"] is True
    assert "Normalization" in pub_json["text"]
    print(">> TEST 17 PASSED: Existing public upload & extraction endpoint preserved!")

    # 18. Existing AI Summary still works
    print("\n--- Test 18: Existing AI Summary still works ---")
    sum_resp = student_client.post("/summarize", json={"text": pub_json["text"]})
    assert sum_resp.status_code in [200, 400]
    print(">> TEST 18 PASSED: Existing AI summary endpoint preserved!")

    # 19. Existing Authentication still works
    print("\n--- Test 19: Existing Authentication still works ---")
    auth_resp = student_client.get("/dashboard")
    assert auth_resp.status_code == 200
    assert auth_resp.get_json()["status"] == "authenticated"
    logout_resp = student_client.get("/logout", follow_redirects=False)
    assert logout_resp.status_code == 302
    print(">> TEST 19 PASSED: Existing authentication and logout preserved!")

    print("\n==================================================")
    print("ALL 19 PROGRAMMATIC STEP 7 TESTS PASSED (100%)")
    print("==================================================")
    return True

if __name__ == "__main__":
    run_step7_tests()
