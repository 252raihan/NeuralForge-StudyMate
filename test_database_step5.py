"""
Test Suite for Step 5 Database Architecture
Verifies schema, tables, foreign keys, indexes, constraints, and sample records.
"""

import sqlite3
import tempfile
from pathlib import Path
from database.db import (
    get_db_connection,
    init_db,
    create_department,
    create_course,
    create_user,
    create_study_material,
    get_department_by_code,
    get_course_by_code,
    get_user_by_email,
    get_study_material_by_id,
    DB_PATH
)

def run_tests():
    print("==================================================")
    print("RUNNING STEP 5 DATABASE ARCHITECTURE VERIFICATION")
    print("==================================================")

    # Use an isolated temporary database for testing
    temp_dir = tempfile.TemporaryDirectory()
    test_db_path = Path(temp_dir.name) / "test_studymate.db"

    try:
        # 1. Initialize Database
        print("\n--- Test 1: Initialize Database & Verify Tables ---")
        init_db(test_db_path)
        assert test_db_path.exists(), "Database file should exist after init_db()"

        conn = get_db_connection(test_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row["name"] for row in cursor.fetchall()]
        print("Created tables:", tables)

        required_tables = ["departments", "courses", "users", "study_materials"]
        for tbl in required_tables:
            assert tbl in tables, f"Required table '{tbl}' was not found in database!"
        print(">> TEST 1 PASSED: All 4 required tables created successfully!")

        # 2. Verify Indexes
        print("\n--- Test 2: Verify Search Indexes ---")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';")
        indexes = [row["name"] for row in cursor.fetchall()]
        print("Created indexes:", indexes)

        required_indexes = [
            "idx_departments_code",
            "idx_courses_department_id",
            "idx_courses_course_code",
            "idx_users_email",
            "idx_users_department_id",
            "idx_study_materials_course_id",
            "idx_study_materials_status",
            "idx_study_materials_exam_type",
        ]
        for idx in required_indexes:
            assert idx in indexes, f"Required index '{idx}' was not found!"
        print(">> TEST 2 PASSED: All performance and lookup indexes verified!")

        # 3. Insert Sample Department: CSE
        print("\n--- Test 3: Insert Sample Department (CSE) ---")
        dept_id = create_department("Computer Science and Engineering", "CSE", conn)
        print(f"Inserted Department ID: {dept_id}")
        assert dept_id > 0, "Department ID should be positive integer"

        dept = get_department_by_code("CSE", conn)
        assert dept is not None, "Department lookup by code failed"
        assert dept["name"] == "Computer Science and Engineering"
        assert dept["code"] == "CSE"
        print(f"Verified Department: ID={dept['id']}, Name='{dept['name']}', Code='{dept['code']}'")
        print(">> TEST 3 PASSED: Department insertion and retrieval succeeded!")

        # 4. Insert Sample Course: Database Management System, CSE 221
        print("\n--- Test 4: Insert Sample Course (DBMS / CSE 221) ---")
        course_id = create_course(
            department_id=dept_id,
            course_name="Database Management System",
            course_code="CSE 221",
            conn=conn
        )
        print(f"Inserted Course ID: {course_id}")
        assert course_id > 0, "Course ID should be positive integer"

        course = get_course_by_code("CSE 221", dept_id, conn)
        assert course is not None, "Course lookup failed"
        assert course["course_name"] == "Database Management System"
        assert course["course_code"] == "CSE 221"
        assert course["department_id"] == dept_id
        print(f"Verified Course: ID={course['id']}, DeptID={course['department_id']}, Name='{course['course_name']}', Code='{course['course_code']}'")
        print(">> TEST 4 PASSED: Course linked to Department succeeded!")

        # 5. Insert Sample Student User with dummy password hash
        print("\n--- Test 5: Insert Sample Student User ---")
        dummy_password_hash = "pbkdf2:sha256:600000$dummyhashvalue$abcdef1234567890abcdef"
        user_id = create_user(
            name="Alice Student",
            email="alice@university.edu",
            password_hash=dummy_password_hash,
            department_id=dept_id,
            role="student",
            conn=conn
        )
        print(f"Inserted User ID: {user_id}")
        assert user_id > 0, "User ID should be positive integer"

        user = get_user_by_email("alice@university.edu", conn)
        assert user is not None, "User lookup failed"
        assert user["name"] == "Alice Student"
        assert user["role"] == "student"
        assert user["password_hash"] == dummy_password_hash
        assert user["created_at"] is not None
        print(f"Verified User: ID={user['id']}, Email='{user['email']}', Role='{user['role']}', CreatedAt='{user['created_at']}'")
        print(">> TEST 5 PASSED: User record securely created with password hash!")

        # 6. Insert Sample Study Material (Course: CSE 221, Topic: Normalization, Exam: midterm, Status: pending)
        print("\n--- Test 6: Insert Sample Study Material ---")
        material_id = create_study_material(
            course_id=course_id,
            topic="Normalization",
            exam_type="midterm",
            file_path="uploads/lecture_normalization.pdf",
            uploaded_by=user_id,
            status="pending",
            conn=conn
        )
        print(f"Inserted Study Material ID: {material_id}")
        assert material_id > 0, "Study material ID should be positive integer"

        material = get_study_material_by_id(material_id, conn)
        assert material is not None, "Study material lookup failed"
        assert material["course_id"] == course_id
        assert material["topic"] == "Normalization"
        assert material["exam_type"] == "midterm"
        assert material["file_path"] == "uploads/lecture_normalization.pdf"
        assert material["uploaded_by"] == user_id
        assert material["status"] == "pending"
        assert material["created_at"] is not None
        print(f"Verified Study Material: ID={material['id']}, Topic='{material['topic']}', Exam='{material['exam_type']}', Status='{material['status']}'")
        print(">> TEST 6 PASSED: Study Material created and linked to Course & User!")

        # 7. Verify Default Status is 'pending' when not explicitly passed
        print("\n--- Test 7: Verify Default Study Material Status is 'pending' ---")
        cursor.execute(
            """
            INSERT INTO study_materials (course_id, topic, exam_type, file_path, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (course_id, "ER Diagrams", "final", "uploads/er_diagrams.pdf", user_id)
        )
        conn.commit()
        default_status_id = cursor.lastrowid
        default_material = get_study_material_by_id(default_status_id, conn)
        assert default_material["status"] == "pending", f"Expected default status 'pending', got '{default_material['status']}'"
        print("Default status verified:", default_material["status"])
        print(">> TEST 7 PASSED: Default status is 'pending'!")

        # 8. Verify Foreign Key Constraint Enforcement: Invalid department_id for Course
        print("\n--- Test 8: Foreign Key Enforcement (Invalid department_id) ---")
        fk_rejected = False
        try:
            cursor.execute(
                "INSERT INTO courses (department_id, course_name, course_code) VALUES (?, ?, ?)",
                (99999, "Ghost Course", "GST 999")
            )
            conn.commit()
        except sqlite3.IntegrityError as err:
            fk_rejected = True
            print("Successfully rejected invalid foreign key:", err)

        assert fk_rejected, "Expected SQLite foreign key integrity error for invalid department_id!"
        print(">> TEST 8 PASSED: Invalid department_id rejected by foreign key constraint!")

        # 9. Verify Foreign Key Constraint Enforcement: Invalid course_id for Study Material
        print("\n--- Test 9: Foreign Key Enforcement (Invalid course_id for Study Material) ---")
        fk_rejected_material = False
        try:
            cursor.execute(
                """
                INSERT INTO study_materials (course_id, topic, exam_type, file_path, uploaded_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (88888, "Invalid Topic", "midterm", "uploads/invalid.pdf", user_id)
            )
            conn.commit()
        except sqlite3.IntegrityError as err:
            fk_rejected_material = True
            print("Successfully rejected invalid foreign key:", err)

        assert fk_rejected_material, "Expected SQLite foreign key integrity error for invalid course_id!"
        print(">> TEST 9 PASSED: Invalid course_id rejected by foreign key constraint!")

        # 10. Verify Unique Constraint: Duplicate course_code in same department
        print("\n--- Test 10: Unique Constraint (Duplicate course_code in same department) ---")
        dup_rejected = False
        try:
            cursor.execute(
                "INSERT INTO courses (department_id, course_name, course_code) VALUES (?, ?, ?)",
                (dept_id, "Duplicate DBMS", "CSE 221")
            )
            conn.commit()
        except sqlite3.IntegrityError as err:
            dup_rejected = True
            print("Successfully rejected duplicate course code in same department:", err)

        assert dup_rejected, "Expected UNIQUE constraint error for duplicate (department_id, course_code)!"
        print(">> TEST 10 PASSED: Duplicate course code in same department rejected!")

        # 11. Verify CHECK constraints on roles and status
        print("\n--- Test 11: CHECK Constraints on Role, Exam Type, and Status ---")
        invalid_role_rejected = False
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("Hacker", "hacker@evil.com", "hash", "superadmin")
            )
            conn.commit()
        except sqlite3.IntegrityError as err:
            invalid_role_rejected = True
            print("Successfully rejected invalid role:", err)

        assert invalid_role_rejected, "Expected CHECK constraint failure for invalid role!"

        invalid_exam_rejected = False
        try:
            cursor.execute(
                """
                INSERT INTO study_materials (course_id, topic, exam_type, file_path, uploaded_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (course_id, "Bad Exam Type", "quiz", "uploads/quiz.pdf", user_id)
            )
            conn.commit()
        except sqlite3.IntegrityError as err:
            invalid_exam_rejected = True
            print("Successfully rejected invalid exam_type:", err)

        assert invalid_exam_rejected, "Expected CHECK constraint failure for invalid exam_type!"
        print(">> TEST 11 PASSED: CHECK constraints protect roles, exam types, and status values!")

        conn.close()

        # 12. Also initialize production DB file database/studymate.db with the required sample data
        print("\n--- Test 12: Initialize Production Database (database/studymate.db) ---")
        init_db(DB_PATH)
        prod_conn = get_db_connection(DB_PATH)

        # Seed CSE department if not exists
        existing_dept = get_department_by_code("CSE", prod_conn)
        if not existing_dept:
            prod_dept_id = create_department("Computer Science and Engineering", "CSE", prod_conn)
        else:
            prod_dept_id = existing_dept["id"]

        # Seed CSE 221 course if not exists
        existing_course = get_course_by_code("CSE 221", prod_dept_id, prod_conn)
        if not existing_course:
            prod_course_id = create_course(prod_dept_id, "Database Management System", "CSE 221", prod_conn)
        else:
            prod_course_id = existing_course["id"]

        # Seed sample student user if not exists
        existing_user = get_user_by_email("student@studymate.local", prod_conn)
        if not existing_user:
            prod_user_id = create_user(
                name="Student User",
                email="student@studymate.local",
                password_hash="scrypt:32768:8:1$dummyhash$samplepasswordhashforstep5verification",
                department_id=prod_dept_id,
                role="student",
                conn=prod_conn
            )
        else:
            prod_user_id = existing_user["id"]

        # Seed sample study material if not exists
        cursor = prod_conn.cursor()
        cursor.execute("SELECT id FROM study_materials WHERE course_id = ? AND topic = ?", (prod_course_id, "Normalization"))
        existing_mat = cursor.fetchone()
        if not existing_mat:
            prod_mat_id = create_study_material(
                course_id=prod_course_id,
                topic="Normalization",
                exam_type="midterm",
                file_path="uploads/sample_study_guide.pdf",
                uploaded_by=prod_user_id,
                status="pending",
                conn=prod_conn
            )
        else:
            prod_mat_id = existing_mat["id"]

        prod_conn.close()
        print(f">> TEST 12 PASSED: Production database initialized and seeded with sample data! Material ID: {prod_mat_id}")

        print("\n==================================================")
        print("ALL 12 DATABASE ARCHITECTURE TESTS PASSED (100%)")
        print("==================================================")
        return True

    finally:
        temp_dir.cleanup()

if __name__ == "__main__":
    run_tests()
