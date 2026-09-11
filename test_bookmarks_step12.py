"Focused Step 12 bookmarks and favorites tests."""
import uuid
from werkzeug.security import generate_password_hash
from app import app
from database.db import (
    get_department_by_code, get_course_by_code, create_user,
    create_study_material, update_study_material_status,
    add_bookmark, remove_bookmark, is_material_bookmarked,
    get_user_bookmarks, get_db_connection,
)


def login(client, email, password="Pass12345"):
    return client.post("/login", data={"email": email, "password": password})


def run_step12_tests():
    app.config["TESTING"] = True
    with app.app_context():
        dept = get_department_by_code("CSE")
        course = get_course_by_code("CSE 221", dept["id"])
        token = uuid.uuid4().hex[:8]
        email_a = f"step12_a_{token}@example.com"
        email_b = f"step12_b_{token}@example.com"
        user_a = create_user("Bookmark A", email_a, generate_password_hash("Pass12345"), dept["id"], "student")
        user_b = create_user("Bookmark B", email_b, generate_password_hash("Pass12345"), dept["id"], "student")
        approved = create_study_material(course["id"], "Bookmark Normalization", "midterm", "uploads/sample_study_guide.pdf", user_a)
        pending = create_study_material(course["id"], "Bookmark Pending", "final", "uploads/sample_study_guide.pdf", user_a)
        rejected = create_study_material(course["id"], "Bookmark Rejected", "both", "uploads/sample_study_guide.pdf", user_a)
        update_study_material_status(approved, "approved")
        update_study_material_status(rejected, "rejected")
        assert add_bookmark(user_a, approved) is True
        assert add_bookmark(user_a, approved) is True
        assert is_material_bookmarked(user_a, approved)
        assert not add_bookmark(user_a, pending)
        assert not add_bookmark(user_a, rejected)
        assert not is_material_bookmarked(user_a, pending)

    anon = app.test_client()
    assert anon.post(f"/study-library/material/{approved}/bookmark", headers={"Accept": "application/json"}).status_code == 302
    assert anon.post(f"/study-library/material/{approved}/unbookmark", headers={"Accept": "application/json"}).status_code == 302
    assert anon.get("/my-bookmarks").status_code == 302
    client_a = app.test_client()
    client_b = app.test_client()
    assert login(client_a, email_a).status_code == 302
    assert login(client_b, email_b).status_code == 302
    # A sees own bookmark; B does not.
    page_a = client_a.get("/my-bookmarks")
    page_b = client_b.get("/my-bookmarks")
    assert page_a.status_code == 200 and b"Bookmark Normalization" in page_a.data
    assert page_b.status_code == 200 and b"Bookmark Normalization" not in page_b.data
    # B cannot remove A's bookmark because deletion is scoped by session user.
    assert client_b.post(f"/study-library/material/{approved}/unbookmark", headers={"Accept": "application/json"}).status_code == 200
    assert is_material_bookmarked(user_a, approved)
    # A can safely remove it and repeated removal remains successful.
    assert client_a.post(f"/study-library/material/{approved}/unbookmark", headers={"Accept": "application/json"}).get_json()["bookmarked"] is False
    assert client_a.post(f"/study-library/material/{approved}/unbookmark", headers={"Accept": "application/json"}).status_code == 200
    assert not is_material_bookmarked(user_a, approved)
    # Mutation validates approved materials and invalid IDs.
    assert client_a.post(f"/study-library/material/{pending}/bookmark", headers={"Accept": "application/json"}).status_code == 404
    assert client_a.post(f"/study-library/material/{rejected}/bookmark", headers={"Accept": "application/json"}).status_code == 404
    assert client_a.post("/study-library/material/999/bookmark", headers={"Accept": "application/json"}).status_code == 404
    # Re-add through route and verify search/filter/sorting on private page.
    assert client_a.post(f"/study-library/material/{approved}/bookmark", headers={"Accept": "application/json"}).status_code == 200
    assert b"Bookmark Normalization" in client_a.get("/my-bookmarks?q=normalization&exam_type=midterm&sort=title_asc").data
    assert b"Bookmark Normalization" not in client_a.get("/my-bookmarks?q=not-found").data
    assert client_a.get("/my-bookmarks?page=bad").status_code == 200
    # Existing public PDF security remains unchanged.
    assert anon.get(f"/study-library/material/{approved}/pdf").status_code == 200
    assert anon.get(f"/study-library/material/{pending}/pdf").status_code == 404
    assert anon.get(f"/study-library/material/{rejected}/pdf").status_code == 404
    # Public library shows bookmark prompt when logged out and bookmark state when logged in.
    assert b"Log in to bookmark" in anon.get("/study-library").data
    assert b"Bookmarked" in client_a.get("/study-library?q=normalization").data
    # No sensitive fields or paths.
    library = client_a.get("/study-library").data
    assert b"password_hash" not in library and b"F:\\NeuralForge-StudyMate" not in library
    print("ALL STEP 12 TESTS PASSED")
    return True
if __name__ == "__main__":
    run_step12_tests()
