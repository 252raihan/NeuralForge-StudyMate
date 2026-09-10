"""
NeuralForge StudyMate - Entry point
Step 4: PDF upload, text extraction, and AI summarization.
"""

import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

try:
    from services.pdf_processor import extract_text_from_pdf
    from services.ai_service import generate_pdf_summary
except ImportError:
    from pdf_processor import extract_text_from_pdf
    from services.ai_service import generate_pdf_summary

from database.db import (
    init_db,
    get_all_departments,
    get_department_by_code,
    get_department_by_id,
    create_department,
    create_course,
    get_course_by_code,
    get_course_by_id,
    get_courses_by_department,
    get_user_by_id,
    create_study_material,
    get_study_materials_by_user,
)
from services.auth_service import (
    register_student,
    authenticate_user,
    login_session,
    logout_session,
    login_required,
    admin_required,
    get_current_user,
)

app = Flask(__name__)

# Security & Session Configuration (Step 6)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-study-mate")
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Base configuration
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Initialize database schema and ensure default departments exist (Step 5 & 6)
with app.app_context():
    init_db()
    # Seed core academic departments if empty
    departments = get_all_departments()
    if not departments:
        default_depts = [
            ("Computer Science and Engineering", "CSE"),
            ("Electrical and Electronic Engineering", "EEE"),
            ("Software Engineering", "SWE"),
            ("Business Administration", "BBA"),
        ]
        for name, code in default_depts:
            if not get_department_by_code(code):
                create_department(name, code)

    # Seed core courses for departments if empty (Step 7)
    cse_dept = get_department_by_code("CSE")
    if cse_dept:
        if not get_course_by_code("CSE 221", cse_dept["id"]):
            create_course(cse_dept["id"], "Database Management System", "CSE 221")
        if not get_course_by_code("CSE 110", cse_dept["id"]):
            create_course(cse_dept["id"], "Programming Language I", "CSE 110")
        if not get_course_by_code("CSE 220", cse_dept["id"]):
            create_course(cse_dept["id"], "Data Structures", "CSE 220")

    eee_dept = get_department_by_code("EEE")
    if eee_dept:
        if not get_course_by_code("EEE 101", eee_dept["id"]):
            create_course(eee_dept["id"], "Electrical Circuits I", "EEE 101")

# 16 MB max upload size
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf"}


def is_allowed_pdf(filename: str) -> bool:
    """Check if the uploaded file has a valid .pdf extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    """Home route - shows landing page with PDF upload studio."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_pdf():
    """
    Handles PDF file upload, validates metadata (course_name, course_code, topic)
    and PDF file, saves to uploads/ folder, and extracts text using pypdf.
    Returns JSON response with success status, course metadata, and extracted text preview.
    """
    # 1. Validate Course Metadata
    course_name = (request.form.get("course_name") or "").strip()
    course_code = (request.form.get("course_code") or "").strip()
    topic = (request.form.get("topic") or "").strip()

    if not course_name:
        return jsonify({
            "success": False,
            "error": "Course Name is required. Please provide a course name."
        }), 400

    if not course_code:
        return jsonify({
            "success": False,
            "error": "Course Code is required. Please provide a course code."
        }), 400

    if not topic:
        return jsonify({
            "success": False,
            "error": "Topic / Chapter is required. Please provide a topic or chapter."
        }), 400

    # 2. Verify file presence in request
    if "file" not in request.files:
        return jsonify({
            "success": False,
            "error": "No file part in the request. Please choose a PDF file."
        }), 400

    file = request.files["file"]

    # 3. Verify file selection
    if not file or file.filename.strip() == "":
        return jsonify({
            "success": False,
            "error": "No file selected. Please choose a PDF file to upload."
        }), 400

    # 4. Verify PDF extension
    if not is_allowed_pdf(file.filename):
        return jsonify({
            "success": False,
            "error": "Invalid file type. Only PDF files (.pdf) are accepted."
        }), 400

    # 5. Secure filename and save
    original_filename = file.filename
    clean_filename = secure_filename(original_filename)
    if not clean_filename or not clean_filename.lower().endswith(".pdf"):
        clean_filename = f"document_{clean_filename}.pdf" if clean_filename else "document.pdf"

    destination_path = UPLOAD_FOLDER / clean_filename

    # If file exists, avoid overwriting by appending an incremental index
    counter = 1
    stem = destination_path.stem
    while destination_path.exists():
        destination_path = UPLOAD_FOLDER / f"{stem}_{counter}.pdf"
        counter += 1

    try:
        file.save(str(destination_path))

        # 6. Extract text via pypdf
        extraction = extract_text_from_pdf(destination_path)

        return jsonify({
            "success": True,
            "message": f"Successfully processed '{original_filename}'.",
            "course_name": course_name,
            "course_code": course_code,
            "topic": topic,
            "filename": destination_path.name,
            "page_count": extraction["page_count"],
            "character_count": extraction["char_count"],
            "char_count": extraction["char_count"],
            "text": extraction["text"]
        }), 200

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"Failed to process PDF: {str(exc)}"
        }), 500


@app.route("/summarize", methods=["POST"])
def summarize_text():
    """
    Step 4: AI Summarization Endpoint.
    Accepts extracted PDF text as JSON and calls the AI service to
    generate a structured study summary.
    """
    # Accept JSON or form-encoded payload
    data = request.get_json(silent=True) or request.form

    if not data or "text" not in data:
        return jsonify({
            "success": False,
            "error": "No text provided. Please provide extracted PDF text to summarize."
        }), 400

    extracted_text = data.get("text", "").strip()

    if not extracted_text:
        return jsonify({
            "success": False,
            "error": "Extracted text is empty. Cannot summarize an empty document."
        }), 400

    try:
        summary_result = generate_pdf_summary(extracted_text)
        return jsonify({
            "success": True,
            "summary": summary_result["summary"],
            "model_used": summary_result["model_used"],
            "truncated": summary_result["truncated"],
            "original_length": summary_result["original_length"],
            "processed_length": summary_result["processed_length"]
        }), 200

    except ValueError as val_err:
        # User-correctable or configuration error (e.g. missing API key, empty text)
        return jsonify({
            "success": False,
            "error": str(val_err)
        }), 400
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"AI service failed: {str(exc)}"
        }), 500


# ===========================================================================
# Step 6: Authentication Routes
# ===========================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Student registration endpoint.
    GET: renders registration form with dynamic department list.
    POST: validates inputs, enforces student role, hashes password, redirects to login.
    """
    # If user is already authenticated, redirect to home
    if session.get("user_id"):
        return redirect(url_for("home"))

    departments = get_all_departments()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        department_id = request.form.get("department_id", "")

        success, error_msg, _ = register_student(
            name=name,
            email=email,
            password=password,
            confirm_password=confirm_password,
            department_id=department_id
        )

        if not success:
            flash(error_msg, "error")
            return render_template(
                "register.html",
                departments=departments,
                form_data={"name": name, "email": email, "department_id": department_id}
            ), 400

        flash("Account created successfully! Please log in with your credentials.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", departments=departments, form_data=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    User login endpoint.
    GET: renders login form.
    POST: verifies credentials using check_password_hash, creates session.
    """
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        success, error_msg, user_dict = authenticate_user(email, password)

        if not success or not user_dict:
            flash("Invalid email or password.", "error")
            return render_template("login.html", form_data={"email": email}), 401

        # Establish authenticated session
        login_session(user_dict)
        flash(f"Welcome back, {user_dict['name']}!", "success")

        # Handle safe next redirect
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)

        return redirect(url_for("home"))

    return render_template("login.html", form_data=None)


# ===========================================================================
# Step 7: Student Study Material Upload & History Routes
# ===========================================================================

@app.route("/study-material/upload", methods=["GET", "POST"])
@login_required
def upload_study_material():
    """
    Step 7: Student Study Material Upload Endpoint.
    - Requires authenticated user session.
    - Validates course existence and department consistency.
    - Validates exam_type in ('midterm', 'final', 'both').
    - Validates topic non-empty.
    - Validates PDF file and stores in uploads/.
    - Saves study material in SQLite with status='pending' and uploaded_by=session['user_id'].
    """
    user = get_user_by_id(session["user_id"])
    if not user:
        logout_session()
        flash("Session expired. Please log in again.", "warning")
        return redirect(url_for("login"))

    user_dept_id = user["department_id"]
    user_department = get_department_by_id(user_dept_id) if user_dept_id else None
    courses = get_courses_by_department(user_dept_id) if user_dept_id else []

    if request.method == "POST":
        course_id_raw = request.form.get("course_id", "").strip()
        exam_type = request.form.get("exam_type", "").strip().lower()
        topic = request.form.get("topic", "").strip()

        # Helper to respond with error in HTML or JSON
        def handle_error(msg: str, status_code: int = 400):
            if request.headers.get("Accept") == "application/json" or request.is_json:
                return jsonify({"success": False, "error": msg}), status_code
            flash(msg, "error")
            return render_template(
                "upload_material.html",
                user_department=user_department,
                courses=courses,
                form_data={"course_id": course_id_raw, "exam_type": exam_type, "topic": topic}
            ), status_code

        # 1. Validate course presence & numeric ID
        if not course_id_raw:
            return handle_error("Please select a course.")

        try:
            course_id = int(course_id_raw)
        except (ValueError, TypeError):
            return handle_error("Invalid course selected.")

        # 2. Verify selected course exists in database
        course = get_course_by_id(course_id)
        if not course:
            return handle_error("Selected course does not exist in the database.")

        # 3. Department consistency validation: Course MUST belong to student's department
        if user_dept_id and course["department_id"] != user_dept_id:
            return handle_error("You can only upload study materials for courses in your registered department.")

        # 4. Validate exam type
        allowed_exam_types = {"midterm", "final", "both"}
        if exam_type not in allowed_exam_types:
            return handle_error("Invalid exam type. Must be 'midterm', 'final', or 'both'.")

        # 5. Validate topic / chapter
        if not topic:
            return handle_error("Topic / Chapter is required. Please provide a topic.")

        # 6. Validate PDF file presence
        if "file" not in request.files:
            return handle_error("Please choose a PDF file to upload.")

        file = request.files["file"]
        if not file or not file.filename or not file.filename.strip():
            return handle_error("No file selected. Please choose a PDF file.")

        # 7. Validate PDF extension
        if not is_allowed_pdf(file.filename):
            return handle_error("Invalid file type. Only PDF files (.pdf) are accepted.")

        # 8. Check file size (16 MB limit)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > app.config["MAX_CONTENT_LENGTH"]:
            return handle_error("File size exceeds the 16 MB limit. Please upload a smaller PDF.", 413)

        # 9. Secure filename and save to uploads/
        original_filename = file.filename
        clean_filename = secure_filename(original_filename)
        if not clean_filename or not clean_filename.lower().endswith(".pdf"):
            clean_filename = f"study_material_{clean_filename}.pdf" if clean_filename else "study_material.pdf"

        destination_path = UPLOAD_FOLDER / clean_filename
        counter = 1
        stem = destination_path.stem
        while destination_path.exists():
            destination_path = UPLOAD_FOLDER / f"{stem}_{counter}.pdf"
            counter += 1

        try:
            file.save(str(destination_path))

            # Verify PDF extraction using existing pdf_processor
            extract_text_from_pdf(destination_path)

            # 10. Save study_materials record into database
            # uploaded_by comes strictly from session; status is strictly 'pending'
            material_id = create_study_material(
                course_id=course_id,
                topic=topic,
                exam_type=exam_type,
                file_path=f"uploads/{destination_path.name}",
                uploaded_by=session["user_id"],
                status="pending"
            )

            success_message = "Study material submitted successfully."
            status_message = "Status: Pending Approval"

            if request.headers.get("Accept") == "application/json" or request.is_json:
                return jsonify({
                    "success": True,
                    "message": success_message,
                    "status": "pending",
                    "material_id": material_id,
                    "course_code": course["course_code"],
                    "course_name": course["course_name"],
                    "topic": topic,
                    "exam_type": exam_type,
                    "filename": destination_path.name
                }), 201

            flash(f"{success_message} Your note has been queued for administrator review.", "success")
            return redirect(url_for("my_study_materials"))

        except Exception as exc:
            return handle_error(f"Failed to process study material: {str(exc)}", 500)

    return render_template(
        "upload_material.html",
        user_department=user_department,
        courses=courses,
        form_data=None
    )


@app.route("/my-study-materials", methods=["GET"])
@login_required
def my_study_materials():
    """
    Step 7: Student Study Material History Endpoint.
    Displays only the authenticated user's uploaded materials.
    """
    user_id = session["user_id"]
    materials = get_study_materials_by_user(user_id)
    return render_template("my_materials.html", materials=materials)


@app.route("/logout", methods=["GET"])
def logout():
    """
    Logs out the user and clears session state.
    """
    logout_session()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """
    Sample protected student route verifying @login_required decorator.
    """
    current_user = get_current_user()
    return jsonify({
        "status": "authenticated",
        "message": f"Welcome to your private study dashboard, {current_user['name']}!",
        "user": current_user
    }), 200


@app.route("/admin/verify")
@admin_required
def admin_verify():
    """
    Sample protected admin route verifying @admin_required decorator.
    """
    current_user = get_current_user()
    return jsonify({
        "status": "admin_authenticated",
        "message": "Admin authorization check passed.",
        "user": current_user
    }), 200


@app.errorhandler(403)
def forbidden_access(error):
    """Handle 403 Forbidden access denial."""
    if request.path.startswith("/admin"):
        return jsonify({
            "error": "Access denied. Administrator privileges required.",
            "status": 403
        }), 403
    flash("Access denied. You do not have permission to view that page.", "error")
    return redirect(url_for("home")), 403


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle files that exceed the configured size limit."""
    return jsonify({
        "success": False,
        "error": "File size exceeds the 16MB limit. Please upload a smaller PDF."
    }), 413


if __name__ == "__main__":
    # debug=True auto-reloads the server when you change code.
    app.run(debug=True)
