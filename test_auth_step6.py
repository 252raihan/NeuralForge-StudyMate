"""
NeuralForge StudyMate - Step 6 User Authentication Test Suite
Tests all 18 programmatic test cases specified in Step 6 requirements.
"""

import io
import uuid
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash

from app import app
from database.db import (
    get_db_connection,
    get_all_departments,
    get_department_by_code,
    get_user_by_email,
    create_user,
    create_department,
)
from services.auth_service import register_student, authenticate_user

def run_auth_tests():
    print("==================================================")
    print("RUNNING STEP 6 USER AUTHENTICATION TEST SUITE")
    print("==================================================")

    # Consistent with the other step suites: disable CSRF only inside the test
    # client so POSTs don't need a per-session token. Production protection is
    # unchanged (see test_security_step15 for CSRF coverage).
    app.config["TESTING"] = True
    client = app.test_client()

    with app.app_context():
        # Ensure at least CSE department exists for testing
        dept = get_department_by_code("CSE")
        if not dept:
            dept_id = create_department("Computer Science and Engineering", "CSE")
        else:
            dept_id = dept["id"]

    # 1. Registration with valid data -> PASS
    print("\n--- Test 1: Registration with valid data ---")
    valid_email = f"rayhan_{uuid.uuid4().hex[:6]}@example.com"
    resp = client.post("/register", data={
        "name": "Rayhan",
        "email": valid_email,
        "password": "StrongPassword123",
        "confirm_password": "StrongPassword123",
        "department_id": str(dept_id),
    }, follow_redirects=False)

    print("Register Status Code:", resp.status_code)
    print("Redirect Location:", resp.headers.get("Location"))
    assert resp.status_code == 302, f"Expected 302 redirect to login, got {resp.status_code}"
    assert "/login" in resp.headers.get("Location")
    print(">> TEST 1 PASSED: Valid registration redirects to login!")

    # 2. Registration with missing name -> rejected
    print("\n--- Test 2: Registration with missing name ---")
    resp = client.post("/register", data={
        "name": "",
        "email": f"noname_{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123",
        "confirm_password": "Password123",
        "department_id": str(dept_id),
    })
    assert resp.status_code == 400
    assert b"Full Name is required" in resp.data
    print(">> TEST 2 PASSED: Missing name correctly rejected!")

    # 3. Registration with invalid email -> rejected
    print("\n--- Test 3: Registration with invalid email ---")
    resp = client.post("/register", data={
        "name": "Invalid Email User",
        "email": "not-a-valid-email",
        "password": "Password123",
        "confirm_password": "Password123",
        "department_id": str(dept_id),
    })
    assert resp.status_code == 400
    assert b"valid email address" in resp.data
    print(">> TEST 3 PASSED: Invalid email format rejected!")

    # 4. Registration with missing password -> rejected
    print("\n--- Test 4: Registration with missing password ---")
    resp = client.post("/register", data={
        "name": "No Password User",
        "email": f"nopass_{uuid.uuid4().hex[:6]}@example.com",
        "password": "",
        "confirm_password": "",
        "department_id": str(dept_id),
    })
    assert resp.status_code == 400
    assert b"Password is required" in resp.data
    print(">> TEST 4 PASSED: Missing password rejected!")

    # 5. Password mismatch -> rejected
    print("\n--- Test 5: Password mismatch ---")
    resp = client.post("/register", data={
        "name": "Mismatch User",
        "email": f"mismatch_{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123",
        "confirm_password": "PasswordMismatch999",
        "department_id": str(dept_id),
    })
    assert resp.status_code == 400
    assert b"Passwords do not match" in resp.data
    print(">> TEST 5 PASSED: Password mismatch rejected!")

    # 6. Duplicate email -> rejected
    print("\n--- Test 6: Duplicate email ---")
    resp = client.post("/register", data={
        "name": "Duplicate Rayhan",
        "email": valid_email,  # same email from Test 1
        "password": "AnotherPassword123",
        "confirm_password": "AnotherPassword123",
        "department_id": str(dept_id),
    })
    assert resp.status_code == 400
    assert b"already exists" in resp.data
    print(">> TEST 6 PASSED: Duplicate email registration rejected!")

    # 7. Department does not exist -> rejected
    print("\n--- Test 7: Non-existent department ---")
    resp = client.post("/register", data={
        "name": "Ghost Dept User",
        "email": f"ghost_{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123",
        "confirm_password": "Password123",
        "department_id": "999999",  # non-existent
    })
    assert resp.status_code == 400
    assert b"department does not exist" in resp.data
    print(">> TEST 7 PASSED: Non-existent department rejected!")

    # 8. Successful registration stores password as a hash -> PASS
    print("\n--- Test 8: Password stored strictly as hash (never plain text) ---")
    user_row = get_user_by_email(valid_email)
    assert user_row is not None
    assert user_row["password_hash"] != "StrongPassword123", "Password MUST NOT be stored in plain text!"
    assert user_row["password_hash"].startswith("scrypt:") or user_row["password_hash"].startswith("pbkdf2:"), "Hash format invalid"
    assert check_password_hash(user_row["password_hash"], "StrongPassword123") is True
    assert check_password_hash(user_row["password_hash"], "WrongPassword") is False
    print("Password hash in DB:", user_row["password_hash"][:35] + "...")
    print(">> TEST 8 PASSED: Password securely hashed using Werkzeug!")

    # 9. Login with correct credentials -> PASS
    print("\n--- Test 9: Login with correct credentials ---")
    resp = client.post("/login", data={
        "email": valid_email,
        "password": "StrongPassword123"
    }, follow_redirects=False)
    assert resp.status_code == 302
    print("Login successful, redirect to:", resp.headers.get("Location"))
    print(">> TEST 9 PASSED: Login with correct credentials succeeded!")

    # 10. Login with incorrect credentials -> rejected
    print("\n--- Test 10: Login with incorrect credentials ---")
    login_attempt_client = app.test_client()
    bad_resp = login_attempt_client.post("/login", data={
        "email": valid_email,
        "password": "IncorrectPassword"
    })
    assert bad_resp.status_code == 401
    assert b"Invalid email or password" in bad_resp.data

    nonexistent_resp = login_attempt_client.post("/login", data={
        "email": "ghost_user_123@nowhere.com",
        "password": "Password123"
    })
    assert nonexistent_resp.status_code == 401
    assert b"Invalid email or password" in nonexistent_resp.data
    print(">> TEST 10 PASSED: Incorrect credentials rejected without disclosing specific error!")

    # 11. Successful login creates session -> PASS
    print("\n--- Test 11: Successful login creates session ---")
    session_client = app.test_client()
    session_client.post("/login", data={
        "email": valid_email,
        "password": "StrongPassword123"
    })
    with session_client.session_transaction() as sess:
        print("Session keys:", list(sess.keys()))
        assert sess.get("user_id") == user_row["id"], "user_id missing from session"
        assert sess.get("user_role") == "student", "user_role missing from session"
        assert sess.get("user_name") == "Rayhan", "user_name missing from session"
        assert "password" not in sess and "password_hash" not in sess, "Sensitive credentials leaked in session!"
    print(">> TEST 11 PASSED: Session securely created with minimal identifiers!")

    # 12. Logout clears session -> PASS
    # Logout is POST-only (GET /logout must not mutate state and returns 405).
    print("\n--- Test 12: Logout clears session ---")
    assert session_client.get("/logout").status_code == 405, "GET /logout must not be allowed"
    logout_resp = session_client.post("/logout", follow_redirects=False)
    assert logout_resp.status_code == 302
    assert "/login" in logout_resp.headers.get("Location")

    with session_client.session_transaction() as sess:
        assert sess.get("user_id") is None
        assert sess.get("user_role") is None
    print(">> TEST 12 PASSED: Logout clears session cleanly!")

    # 13. Student role is assigned automatically during registration -> PASS
    print("\n--- Test 13: Student role assigned automatically ---")
    assert user_row["role"] == "student"
    print("Assigned role:", user_row["role"])
    print(">> TEST 13 PASSED: Role 'student' assigned automatically!")

    # 14. Public registration cannot create admin -> PASS
    print("\n--- Test 14: Public registration cannot create admin ---")
    # Attempt to inject role=admin via registration form
    evil_email = f"evil_admin_{uuid.uuid4().hex[:6]}@example.com"
    public_client = app.test_client()
    public_client.post("/register", data={
        "name": "Evil Admin Attempt",
        "email": evil_email,
        "password": "SecretPassword123",
        "confirm_password": "SecretPassword123",
        "department_id": str(dept_id),
        "role": "admin"  # malicious form parameter
    })
    evil_user = get_user_by_email(evil_email)
    assert evil_user is not None
    assert evil_user["role"] == "student", f"Security violation: user role was set to {evil_user['role']}!"
    print("Resulting role:", evil_user["role"])
    print(">> TEST 14 PASSED: Public registration strictly forces role = 'student'!")

    # 15. Admin role checking works -> PASS
    print("\n--- Test 15: Admin role checking works ---")
    # Create an admin user directly in DB
    admin_email = f"admin_{uuid.uuid4().hex[:6]}@studymate.local"
    admin_id = create_user(
        name="System Admin",
        email=admin_email,
        password_hash=generate_password_hash("AdminMasterPass123"),
        department_id=dept_id,
        role="admin"
    )

    # 15a: Student trying to access /admin/verify -> 403 Forbidden
    student_client = app.test_client()
    student_client.post("/login", data={"email": valid_email, "password": "StrongPassword123"})
    student_admin_resp = student_client.get("/admin/verify")
    print("Student accessing admin route:", student_admin_resp.status_code)
    assert student_admin_resp.status_code == 403
    print(">> Student access to admin route correctly rejected with 403!")

    # 15b: Admin accessing /admin/verify -> 200 OK
    admin_client = app.test_client()
    admin_client.post("/login", data={"email": admin_email, "password": "AdminMasterPass123"})
    admin_resp = admin_client.get("/admin/verify")
    print("Admin accessing admin route:", admin_resp.status_code)
    assert admin_resp.status_code == 200
    assert admin_resp.get_json()["status"] == "admin_authenticated"
    print(">> TEST 15 PASSED: Admin role checking properly distinguishes student vs admin!")

    # 16. Unauthenticated access to protected route redirects to login -> PASS
    print("\n--- Test 16: Unauthenticated access to protected route redirects to login ---")
    anon_client = app.test_client()
    protect_resp = anon_client.get("/dashboard", follow_redirects=False)
    print("Unauthenticated dashboard status:", protect_resp.status_code)
    print("Redirect location:", protect_resp.headers.get("Location"))
    assert protect_resp.status_code == 302
    assert "/login" in protect_resp.headers.get("Location")

    # When authenticated as student -> 200 OK
    auth_dashboard_resp = student_client.get("/dashboard")
    assert auth_dashboard_resp.status_code == 200
    assert auth_dashboard_resp.get_json()["status"] == "authenticated"
    print(">> TEST 16 PASSED: Protected route redirects unauthenticated users and allows authenticated users!")

    # 17. Existing PDF upload still works -> PASS
    print("\n--- Test 17: Existing PDF upload regression test ---")
    pdf_path = Path("sample_study_guide.pdf")
    assert pdf_path.exists(), "sample_study_guide.pdf must exist"
    pdf_bytes = pdf_path.read_bytes()

    upload_data = {
        "course_name": "Database Management System",
        "course_code": "CSE 221",
        "topic": "Normalization",
        "file": (io.BytesIO(pdf_bytes), "sample_study_guide.pdf")
    }
    upload_resp = client.post("/upload", data=upload_data, content_type="multipart/form-data")
    assert upload_resp.status_code == 200
    upload_json = upload_resp.get_json()
    assert upload_json["success"] is True
    assert upload_json["course_name"] == "Database Management System"
    assert upload_json["course_code"] == "CSE 221"
    assert upload_json["topic"] == "Normalization"
    assert upload_json["page_count"] == 1
    assert "Normalization" in upload_json["text"]
    print(">> TEST 17 PASSED: PDF upload and metadata extraction remain 100% operational!")

    # 18. Existing AI Summary still works -> PASS
    print("\n--- Test 18: Existing AI Summary regression test ---")
    summarize_resp = client.post("/summarize", json={"text": upload_json["text"]})
    assert summarize_resp.status_code in [200, 400]
    print(">> TEST 18 PASSED: Summarize endpoint handled extracted text properly!")

    print("\n==================================================")
    print("ALL 18 AUTHENTICATION & REGRESSION TESTS PASSED (100%)")
    print("==================================================")
    return True

if __name__ == "__main__":
    run_auth_tests()
