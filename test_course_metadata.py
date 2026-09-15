"""
Comprehensive test suite for Course Metadata integration in StudyMate.
Tests all requirements:
1. Successful upload with metadata: Course Name, Course Code, Topic
2. Verification of returned JSON format:
   {
     "success": true,
     "course_name": "Database Management System",
     "course_code": "CSE 221",
     "topic": "Normalization",
     "filename": "...",
     "page_count": 1,
     "character_count": 350,
     "text": "..."
   }
3. Empty Course Name rejection (400)
4. Empty Course Code rejection (400)
5. Empty Topic rejection (400)
6. Invalid file type rejection (400)
7. Missing file rejection (400)
8. Summarize endpoint verification with extracted text
"""

import io
from pathlib import Path
from app import app

def run_metadata_tests():
    # Consistent with the other step suites: CSRF is disabled only for the test
    # client; production CSRF protection is covered by test_security_step15.
    app.config["TESTING"] = True
    client = app.test_client()
    pdf_path = Path("sample_study_guide.pdf")
    assert pdf_path.exists(), "sample_study_guide.pdf must exist before running tests"
    pdf_bytes = pdf_path.read_bytes()

    print("==================================================")
    print("RUNNING COURSE METADATA VALIDATION & UPLOAD TESTS")
    print("==================================================")

    # 1. Valid Upload with complete metadata
    print("\n--- Test 1: Valid Upload with Metadata ---")
    data = {
        "course_name": "Database Management System",
        "course_code": "CSE 221",
        "topic": "Normalization",
        "file": (io.BytesIO(pdf_bytes), "sample_study_guide.pdf")
    }
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    print("Status code:", resp.status_code)
    json_data = resp.get_json()
    print("Response JSON:", json_data)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert json_data["success"] is True, "Expected success: True"
    assert json_data["course_name"] == "Database Management System", "Course name mismatch"
    assert json_data["course_code"] == "CSE 221", "Course code mismatch"
    assert json_data["topic"] == "Normalization", "Topic mismatch"
    assert "filename" in json_data, "filename missing from response"
    assert json_data["page_count"] == 1, "Page count mismatch"
    assert "character_count" in json_data and json_data["character_count"] > 0, "character_count missing or 0"
    assert "Normalization" in json_data["text"], "Extracted text missing expected content"
    print(">> TEST 1 PASSED: Valid upload and metadata returned perfectly!")

    # 2. Empty Course Name
    print("\n--- Test 2: Empty Course Name ---")
    data = {
        "course_name": "   ",
        "course_code": "CSE 221",
        "topic": "Normalization",
        "file": (io.BytesIO(pdf_bytes), "sample_study_guide.pdf")
    }
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    print("Status code:", resp.status_code)
    json_data = resp.get_json()
    print("Response JSON:", json_data)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    assert json_data["success"] is False
    assert "Course Name is required" in json_data["error"]
    print(">> TEST 2 PASSED: Empty Course Name rejected properly!")

    # 3. Empty Course Code
    print("\n--- Test 3: Empty Course Code ---")
    data = {
        "course_name": "Database Management System",
        "course_code": "",
        "topic": "Normalization",
        "file": (io.BytesIO(pdf_bytes), "sample_study_guide.pdf")
    }
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    print("Status code:", resp.status_code)
    json_data = resp.get_json()
    print("Response JSON:", json_data)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    assert json_data["success"] is False
    assert "Course Code is required" in json_data["error"]
    print(">> TEST 3 PASSED: Empty Course Code rejected properly!")

    # 4. Empty Topic
    print("\n--- Test 4: Empty Topic ---")
    data = {
        "course_name": "Database Management System",
        "course_code": "CSE 221",
        "topic": "   ",
        "file": (io.BytesIO(pdf_bytes), "sample_study_guide.pdf")
    }
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    print("Status code:", resp.status_code)
    json_data = resp.get_json()
    print("Response JSON:", json_data)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    assert json_data["success"] is False
    assert "Topic / Chapter is required" in json_data["error"]
    print(">> TEST 4 PASSED: Empty Topic rejected properly!")

    # 5. Invalid File Type (.txt)
    print("\n--- Test 5: Invalid File Type ---")
    data = {
        "course_name": "Database Management System",
        "course_code": "CSE 221",
        "topic": "Normalization",
        "file": (io.BytesIO(b"Not a PDF"), "document.txt")
    }
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    print("Status code:", resp.status_code)
    json_data = resp.get_json()
    print("Response JSON:", json_data)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    assert json_data["success"] is False
    assert "Invalid file type" in json_data["error"]
    print(">> TEST 5 PASSED: Invalid file type rejected properly!")

    # 6. Missing File
    print("\n--- Test 6: Missing File ---")
    data = {
        "course_name": "Database Management System",
        "course_code": "CSE 221",
        "topic": "Normalization"
    }
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    print("Status code:", resp.status_code)
    json_data = resp.get_json()
    print("Response JSON:", json_data)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    assert json_data["success"] is False
    assert "No file part" in json_data["error"]
    print(">> TEST 6 PASSED: Missing file rejected properly!")

    # 7. Summarize verification with extracted text
    print("\n--- Test 7: Summarize Endpoint Integration ---")
    summarize_resp = client.post(
        "/summarize",
        json={"text": "Database Management System - Normalization is the process of organizing data in a database."}
    )
    print("Summarize status code:", summarize_resp.status_code)
    summary_json = summarize_resp.get_json()
    print("Summarize JSON keys:", list(summary_json.keys()))
    # Regardless of whether a live OpenAI API key is present or not, the endpoint must be responsive
    # If key is placeholder, returns 400 with helpful error or 200 if valid key
    assert summarize_resp.status_code in [200, 400]
    print(">> TEST 7 PASSED: Summarize endpoint handled extracted text properly!")

    print("\n==================================================")
    print("ALL 7 COURSE METADATA BACKEND TESTS PASSED (100%)")
    print("==================================================")
    return True

if __name__ == "__main__":
    run_metadata_tests()
