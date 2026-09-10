"""
Automated test script for the /upload endpoint.
"""
import urllib.request
import uuid
import json
from pathlib import Path

def test_upload():
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    filename = "sample_study_guide.pdf"
    file_path = Path(filename)
    if not file_path.exists():
        print("ERROR: sample file not found")
        return False

    pdf_bytes = file_path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="course_name"\r\n\r\n'
        f"Database Management System\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="course_code"\r\n\r\n'
        f"CSE 221\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="topic"\r\n\r\n'
        f"Normalization\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + pdf_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:5000/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            content = response.read().decode("utf-8")
            data = json.loads(content)
            print("Status Code:", status)
            print("Response JSON:")
            print(json.dumps(data, indent=2))

            assert data["success"] is True
            assert data["course_name"] == "Database Management System"
            assert data["course_code"] == "CSE 221"
            assert data["topic"] == "Normalization"
            assert data["page_count"] == 1
            assert (data.get("character_count") or data.get("char_count")) > 0
            assert "Normalization" in data["text"]
            print("\n>> VERIFICATION PASSED: PDF uploaded and text extracted successfully! <<")
            return True
    except Exception as exc:
        print("Upload test failed:", exc)
        return False

def test_invalid_file_rejection():
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    filename = "fake_document.txt"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="course_name"\r\n\r\n'
        f"Database Management System\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="course_code"\r\n\r\n'
        f"CSE 221\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="topic"\r\n\r\n'
        f"Normalization\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
        f"Hello this is not a pdf"
        f"\r\n--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:5000/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    try:
        urllib.request.urlopen(req)
        print("ERROR: Invalid file was accepted!")
        return False
    except urllib.error.HTTPError as exc:
        data = json.loads(exc.read().decode("utf-8"))
        print("\nInvalid File Test:")
        print("Status Code:", exc.code)
        print("Response JSON:", data)
        assert exc.code == 400
        assert data["success"] is False
        assert "Invalid file type" in data["error"]
        print(">> VERIFICATION PASSED: Invalid file correctly rejected with 400 error! <<")
        return True

if __name__ == "__main__":
    t1 = test_upload()
    t2 = test_invalid_file_rejection()
    if t1 and t2:
        print("\nALL BACKEND API TESTS PASSED!")

