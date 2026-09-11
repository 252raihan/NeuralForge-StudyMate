"Focused Step 11 Smart Search tests."""
from app import app
from database.db import get_department_by_code, get_course_by_code, search_approved_study_materials

def run_step11_tests():
    app.config["TESTING"] = True
    c = app.test_client()
    with app.app_context():
        cse = get_department_by_code("CSE")
        course = get_course_by_code("CSE 221", cse["id"])
        rows = search_approved_study_materials("normalization")
        assert rows and all(row["status"] == "approved" for row in rows)
        assert search_approved_study_materials("NORMALIZATION")
        assert search_approved_study_materials("CSE 221")
        assert search_approved_study_materials("Database", course_id=course["id"])
        assert search_approved_study_materials("normalization", department_id=cse["id"], exam_type="midterm")
        assert not search_approved_study_materials("unlikely-no-match-xyz")
        assert search_approved_study_materials("  normalization  ")
        assert search_approved_study_materials("' OR 1=1 --") == []
        assert search_approved_study_materials("normalization", sort="newest")
        assert search_approved_study_materials("normalization", sort="oldest")
        assert search_approved_study_materials("normalization", sort="title_asc")
        assert search_approved_study_materials("normalization", sort="title_desc")
        try:
            search_approved_study_materials("x", sort="drop_table")
            raise AssertionError("invalid sort accepted")
        except ValueError:
            pass
        try:
            search_approved_study_materials("x", exam_type="quiz")
            raise AssertionError("invalid exam accepted")
        except ValueError:
            pass
    assert c.get("/study-library").status_code == 200
    response = c.get("/study-library?q=normalization&sort=relevance")
    assert response.status_code == 200 and b"Normalization" in response.data
    assert c.get("/study-library?page=abc").status_code == 200
    assert c.get("/study-library?department_id=999").status_code == 200
    assert c.get(f"/study-library?department_id={cse['id']}&course_id=999").status_code == 200
    assert c.get("/study-library?sort=drop_table").status_code == 200
    assert b"password_hash" not in response.data and b"F:\\NeuralForge-StudyMate" not in response.data
    print("ALL STEP 11 TESTS PASSED")
    return True
if __name__ == "__main__":
    run_step11_tests()
