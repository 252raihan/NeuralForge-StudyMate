"""
NeuralForge StudyMate - Entry point
Step 4: PDF upload, text extraction, and AI summarization.
"""

import os
import datetime
import json
import hmac
import logging
import secrets
import time
from collections import defaultdict
from pathlib import Path
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, abort, send_file
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

try:
    from services.pdf_processor import extract_text_from_pdf
    from services.ai_service import generate_pdf_summary, generate_quiz_questions, answer_study_question
    from services.rag_service import index_material, retrieve_context, NO_MATCH_ANSWER
    from services.ai_service import generate_quiz_from_context
except ImportError:
    from pdf_processor import extract_text_from_pdf
    from services.ai_service import generate_pdf_summary, generate_quiz_questions, answer_study_question
    from services.rag_service import index_material, retrieve_context, NO_MATCH_ANSWER
    from services.ai_service import generate_quiz_from_context
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
    get_pending_study_materials,
    get_study_material_details,
    get_study_materials_by_status,
    update_study_material_status,
    get_approved_study_materials,
    count_approved_study_materials,
    search_approved_study_materials,
    count_search_approved_study_materials,
    search_approved_materials_for_qa,
    save_material_chunks,
    delete_material_chunks,
    get_chunk_count,
    get_material_extracted_text,
    create_generated_quiz,
    get_generated_quiz_for_user,
    get_generated_quiz_questions,
    get_generated_quiz_sources,
    get_performance_overview,
    get_performance_by_quiz,
    get_performance_by_course,
    get_performance_by_topic,
    get_recent_performance,
    get_quiz_questions_with_answers,
    get_active_attempt,
    create_generated_quiz_attempt,
    get_attempt_for_user,
    finalize_quiz_attempt,
    get_attempt_answers,
    get_user_quiz_attempts,
    get_all_courses,
    add_bookmark,
    remove_bookmark,
    get_bookmarked_material_ids,
    get_user_bookmarks,
    count_user_bookmarks,
    get_student_dashboard_stats,
    get_student_course_progress,
    get_recent_student_materials,
    get_recent_student_bookmarks,
    get_recent_student_quizzes,
    create_quiz,
    get_quiz_for_user,
    get_quiz_questions,
    create_quiz_attempt,
    get_quiz_attempt_for_user,
    get_attempt_review,
    get_user_notifications,
    count_user_notifications,
    count_unread_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    get_notification_for_user,
)
from services.notification_service import (
    notify_material_approved,
    notify_material_rejected,
    notify_quiz_completed,
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

# Security & Session Configuration (Step 15)
_secret_key = os.environ.get("SECRET_KEY", "").strip()
if not _secret_key:
    _secret_key = secrets.token_urlsafe(32)
    if os.environ.get("FLASK_ENV", "development").lower() == "production":
        raise RuntimeError("SECRET_KEY must be configured in production.")
app.secret_key = _secret_key
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0").lower() in ("1", "true", "yes")
_production_mode = os.environ.get("FLASK_ENV", "development").lower() == "production"
app.config["CSRF_PROTECTION"] = os.environ.get("CSRF_PROTECTION", "1").lower() not in ("0", "false", "no")
app.config["JSON_SORT_KEYS"] = False
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("studymate")
_rate_buckets = defaultdict(list)

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
@app.context_processor
def security_context():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    user_id = session.get("user_id")
    return {
        "csrf_token": session["csrf_token"],
        "unread_notification_count": count_unread_notifications(user_id) if user_id else 0,
    }


def _csrf_valid():
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    expected = session.get("csrf_token")
    return bool(supplied and expected and hmac.compare_digest(str(supplied), str(expected)))

@app.before_request
def protect_state_changing_requests():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if not app.config.get("CSRF_PROTECTION", True) or app.config.get("TESTING"):
        return None
    if request.endpoint in {"upload_pdf", "summarize_text"} and request.is_json:
        return None
    if request.endpoint in {"quiz_generate_api", "quiz_submit_api"} and request.is_json:
        # Auth + rate-limit protected JSON APIs; the UI also sends X-CSRF-Token.
        return None
    if not _csrf_valid():
        logger.warning("CSRF validation failed for %s", request.path)
        return jsonify({"success": False, "error": "Invalid or missing security token."}), 400
    return None
@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

ALLOWED_EXTENSIONS = {"pdf"}


def is_allowed_pdf(filename: str) -> bool:
    """Check if the uploaded file has a valid .pdf extension."""
    return bool(filename) and "\x00" not in filename and "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def _has_pdf_signature(file_storage) -> bool:
        # Reject files that do not begin with the PDF magic signature."
        try:
            position = file_storage.stream.tell()
            signature = file_storage.stream.read(5)
            file_storage.stream.seek(position)
            return signature == b"%PDF-"
        except (AttributeError, OSError):
            return False

def _rate_limited(bucket: str, limit: int, window_seconds: int = 60) -> bool:
        if app.config.get("TESTING"):
            return False
        now = time.monotonic()
        key = f"{bucket}:{request.remote_addr or 'unknown'}"
        recent = [stamp for stamp in _rate_buckets[key] if now - stamp < window_seconds]
        if len(recent) >= limit:
            _rate_buckets[key] = recent
            return True
        recent.append(now)
        _rate_buckets[key] = recent
        return False
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
    if _rate_limited("public-upload", 10):
        return jsonify({"success": False, "error": "Too many upload requests. Please try again later."}), 429
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
    if not is_allowed_pdf(file.filename) or not _has_pdf_signature(file):
        return jsonify({
            "success": False,
            "error": "Invalid file type. Only valid PDF files (.pdf) are accepted."
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

    except Exception:
        logger.exception("Public PDF processing failed")
        return jsonify({
            "success": False,
            "error": "The PDF could not be processed safely."
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
    except Exception:
        logger.exception("AI summary request failed")
        return jsonify({
            "success": False,
            "error": "The AI service is temporarily unavailable."
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
        if _rate_limited("login", 10):
            return jsonify({"success": False, "error": "Too many login attempts. Please try again later."}), 429
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
        if not is_allowed_pdf(file.filename) or not _has_pdf_signature(file):
            return handle_error("Invalid file type. Only valid PDF files (.pdf) are accepted.")

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
            extraction = extract_text_from_pdf(destination_path)
            extracted_text = (extraction.get("text") or "").strip()

            # 10. Save study_materials record into database
            # uploaded_by comes strictly from session; status is strictly 'pending'
            material_id = create_study_material(
                course_id=course_id,
                topic=topic,
                exam_type=exam_type,
                file_path=f"uploads/{destination_path.name}",
                uploaded_by=session["user_id"],
                status="pending",
                extracted_text=extracted_text[:QNA_TEXT_STORE_LIMIT]
            )

            # Step 11: build the RAG chunk index now so approval needs no re-scan.
            if extracted_text:
                index_material(material_id)

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


# ===========================================================================
# Step 10: AI-Powered Question & Quiz Generator
# ===========================================================================

QUIZ_TYPES = {"mcq", "short", "mixed"}
QUIZ_DIFFICULTIES = {"easy", "medium", "hard", "mixed"}


def _quiz_error(message, status=400):
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"success": False, "error": message}), status
    flash(message, "error")
    return redirect(request.referrer or url_for("study_library"))


def _approved_material_content(material):
    if not material or material["status"] != "approved":
        return None
    stored_name = Path(material["file_path"]).name
    file_location = UPLOAD_FOLDER / stored_name
    if file_location.suffix.lower() != ".pdf" or not file_location.is_file():
        return None
    try:
        content = extract_text_from_pdf(file_location).get("text", "").strip()
    except Exception:
        return None
    return content or None
@app.route("/quiz/create/<int:material_id>", methods=["GET"])
@login_required
def quiz_create(material_id):
    material = get_study_material_details(material_id)
    if not material or material["status"] != "approved" or not _approved_material_content(material):
        return _quiz_error("This approved study material is unavailable for quiz generation.", 404)
    return render_template("quiz_create.html", material=material, quiz_types=sorted(QUIZ_TYPES), difficulties=sorted(QUIZ_DIFFICULTIES))

@app.route("/quiz/generate/<int:material_id>", methods=["POST"])
@login_required
def quiz_generate(material_id):
    if _rate_limited("quiz-generation", 10):
        return _quiz_error("Too many quiz generation requests. Please try again later.", 429)
    material = get_study_material_details(material_id)
    content = _approved_material_content(material)
    if not material or material["status"] != "approved" or not content:
        return _quiz_error("Only approved materials with usable content can generate quizzes.", 404)
    question_type = (request.form.get("question_type") or "").strip().lower()
    difficulty = (request.form.get("difficulty") or "").strip().lower()
    raw_count = (request.form.get("question_count") or "").strip()
    if question_type not in QUIZ_TYPES or difficulty not in QUIZ_DIFFICULTIES:
        return _quiz_error("Invalid quiz type or difficulty.")
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        return _quiz_error("Question count must be a whole number between 1 and 20.")
    if not 1 <= count <= 20:
        return _quiz_error("Question count must be between 1 and 20.")
    try:
        questions = generate_quiz_questions(content, question_type, difficulty, count)
        quiz_id = create_quiz(material_id, session["user_id"], f"{material['topic']} Quiz", question_type, difficulty, count, questions)
    except ValueError as exc:
        return _quiz_error(str(exc))
    except Exception:
        return _quiz_error("Quiz generation failed. Please try again later.", 503)
    return redirect(url_for("quiz_take", quiz_id=quiz_id))

@app.route("/quiz/<int:quiz_id>", methods=["GET"])
@login_required
def quiz_take(quiz_id):
    quiz = get_quiz_for_user(quiz_id, session["user_id"])
    if not quiz:
        abort(404)
    questions = get_quiz_questions(quiz_id)
    safe_questions = []
    for question in questions:
        item = dict(question)
        item["options"] = json.loads(item["options_json"]) if item.get("options_json") else []
        item.pop("correct_answer", None)
        item.pop("expected_answer", None)
        item.pop("options_json", None)
        safe_questions.append(item)
    return render_template("quiz.html", quiz=quiz, questions=safe_questions)


def _normalize_answer(value):
    return " ".join(str(value or "").casefold().split())

@app.route("/quiz/<int:quiz_id>/submit", methods=["POST"])
@login_required
def quiz_submit(quiz_id):
    quiz = get_quiz_for_user(quiz_id, session["user_id"])
    if not quiz:
        abort(404)
    questions = get_quiz_questions(quiz_id)
    if not questions:
        return _quiz_error("This quiz has no valid questions.")
    answers = []
    score = 0
    for question in questions:
        submitted = (request.form.get(f"answer_{question['id']}") or "").strip()[:2000]
        if question["question_type"] == "mcq":
            is_correct = submitted == (question["correct_answer"] or "")
        else:
            is_correct = bool(submitted) and _normalize_answer(submitted) == _normalize_answer(question["expected_answer"])
        score += int(is_correct)
        answers.append({"question_id": question["id"], "submitted_answer": submitted, "is_correct": is_correct})
    percentage = round((score / len(questions)) * 100, 2) if questions else 0
    attempt_id = create_quiz_attempt(quiz_id, session["user_id"], score, len(questions), percentage, answers)
    notify_quiz_completed(session["user_id"], quiz_id, attempt_id, quiz["title"], score, len(questions))
    return redirect(url_for("quiz_result", quiz_id=quiz_id, attempt_id=attempt_id))

@app.route("/quiz/<int:quiz_id>/result/<int:attempt_id>", methods=["GET"])
@login_required
def quiz_result(quiz_id, attempt_id):
    attempt = get_quiz_attempt_for_user(attempt_id, session["user_id"])
    if not attempt or attempt["quiz_id"] != quiz_id:
        abort(404)
    quiz = get_quiz_for_user(quiz_id, session["user_id"])
    review = get_attempt_review(attempt_id)
    return render_template("quiz_result.html", quiz=quiz, attempt=attempt, review=review)

# ===========================================================================
# Step 12: AI Quiz Generator (generation + storage only; Step 13 attempts it)
# ===========================================================================

QUIZ_GEN_COUNTS = (5, 10, 15, 20)
QUIZ_GEN_DIFFICULTIES = {"easy", "medium", "hard", "mixed"}
QUIZ_GEN_EXAM_TYPES = {"midterm", "final", "both"}
QUIZ_GEN_MAX_TOPIC = 120

def _quiz_json_error(message, status=400):
    return jsonify({"success": False, "error": message}), status

def _build_quiz_title(course_name, topic):
    # Titles are stored/rendered as text (auto-escaped in templates), never raw HTML.
    safe_topic = (topic or "General").strip()[:QUIZ_GEN_MAX_TOPIC] or "General"
    safe_course = (course_name or "Study").strip() or "Study"
    return safe_course + " \u2014 " + safe_topic + " Quiz"

@app.route("/quiz/create", methods=["GET"])
@login_required
def quiz_create_page():
    # Course selector is limited to the student's department (admins: all courses).
    user = get_user_by_id(session["user_id"])
    is_admin = session.get("user_role") == "admin"
    if is_admin:
        courses = get_all_courses()
    else:
        courses = get_courses_by_department(user["department_id"]) if user and user["department_id"] else []
    return render_template(
        "quiz_create_ai.html",
        courses=courses,
        question_counts=QUIZ_GEN_COUNTS,
        difficulties=["easy", "medium", "hard", "mixed"],
        exam_types=["midterm", "final", "both"],
    )

@app.route("/api/quizzes/generate", methods=["POST"])
@login_required
def quiz_generate_api():
    # Server-side validation: never trust the browser's course/topic/exam values.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _quiz_json_error("Invalid request body.", 400)

    if _rate_limited("quiz-generation", 10):
        return _quiz_json_error("Too many quiz generation requests. Please try again later.", 429)

    raw_course = data.get("course_id")
    topic = (data.get("topic") or "").strip()[:QUIZ_GEN_MAX_TOPIC]
    exam_type = (data.get("exam_type") or "").strip().lower()
    difficulty = (data.get("difficulty") or "").strip().lower()
    raw_count = data.get("number_of_questions")

    # Validate course id and department ownership/validity.
    try:
        course_id = int(raw_course)
    except (TypeError, ValueError):
        return _quiz_json_error("Please select a valid course.", 400)
    course = get_course_by_id(course_id)
    if not course:
        return _quiz_json_error("Selected course does not exist.", 400)
    user = get_user_by_id(session["user_id"])
    if session.get("user_role") != "admin":
        if not user or not user["department_id"] or course["department_id"] != user["department_id"]:
            return _quiz_json_error("You can only generate quizzes for courses in your department.", 403)

    if exam_type not in QUIZ_GEN_EXAM_TYPES:
        return _quiz_json_error("Invalid exam type selected.", 400)
    if difficulty not in QUIZ_GEN_DIFFICULTIES:
        return _quiz_json_error("Invalid difficulty selected.", 400)
    try:
        number_of_questions = int(raw_count)
    except (TypeError, ValueError):
        return _quiz_json_error("Invalid number of questions.", 400)
    if number_of_questions not in QUIZ_GEN_COUNTS:
        return _quiz_json_error("Number of questions must be 5, 10, 15, or 20.", 400)
    if not topic:
        return _quiz_json_error("Please enter a topic for the quiz.", 400)

    # Step 11 RAG: the TOPIC drives relevance over approved-only chunks. If the
    # topic yields nothing relevant we never fall back to a generic quiz.
    department_id = user["department_id"] if user else None
    rag = retrieve_context(topic, department_id, top_k=RAG_TOP_K,
                           max_context_chars=QNA_CONTEXT_CHAR_LIMIT)
    if not rag["has_relevant"]:
        return _quiz_json_error(
            "Not enough approved study material is available for this topic. "
            "Please choose another topic or wait for more materials to be approved.", 404
        )

    course_name = course["course_name"]
    try:
        questions = generate_quiz_from_context(
            rag["context"], number_of_questions, difficulty,
            course_name=course_name, topic=topic,
        )
    except ValueError as exc:
        return _quiz_json_error(str(exc), 503)
    except Exception:
        logger.exception("Quiz generation failed")
        return _quiz_json_error("Quiz generation failed. Please try again later.", 500)

    source_ids = [item["material_id"] for item in rag["sources"]]
    title = _build_quiz_title(course_name, topic)
    try:
        quiz_id = create_generated_quiz(
            session["user_id"], course_id, title, topic, exam_type,
            difficulty, questions, source_material_ids=source_ids,
        )
    except Exception:
        logger.exception("Saving generated quiz failed")
        return _quiz_json_error("Quiz could not be saved. Please try again later.", 500)

    return jsonify({
        "success": True,
        "quiz_id": quiz_id,
        "title": title,
        "question_count": len(questions),
    }), 201
@app.route("/quiz/view/<int:quiz_id>", methods=["GET"])
@login_required
def quiz_preview(quiz_id):
    # Ownership-scoped preview (prevents IDOR). Attempts/submission are Step 13.
    quiz = get_generated_quiz_for_user(quiz_id, session["user_id"])
    if not quiz:
        abort(404)
    questions = get_generated_quiz_questions(quiz_id)
    sources = get_generated_quiz_sources(quiz_id)
    return render_template("quiz_preview.html", quiz=quiz, questions=questions, sources=sources)

# ===========================================================================
# Step 13: Quiz Attempt + Result System
# ===========================================================================

MAX_QUIZ_ANSWER_PAYLOAD = 200  # reject oversized answer maps fail-safe
@app.route("/quiz/take/<int:quiz_id>", methods=["GET"])
@login_required
def quiz_take_page(quiz_id):
    # Ownership-scoped: students only take their own generated quizzes.
    quiz = get_generated_quiz_for_user(quiz_id, session["user_id"])
    if not quiz:
        abort(404)
    questions = get_quiz_questions_with_answers(quiz_id)
    if not questions:
        abort(404)

    # Establish (or reuse) a single in-progress attempt so refreshes don't spam rows.
    attempt = get_active_attempt(quiz_id, session["user_id"])
    if not attempt:
        attempt_id = create_generated_quiz_attempt(quiz_id, session["user_id"], len(questions))
    else:
        attempt_id = attempt["id"]

    # SECURITY: never send correct_answer / explanation to the browser pre-submission.
    safe_questions = [
        {
            "id": q["id"],
            "question_text": q["question_text"],
            "options": [q["option_a"], q["option_b"], q["option_c"], q["option_d"]],
        }
        for q in questions
    ]
    return render_template(
        "quiz_take.html",
        quiz=quiz,
        questions=safe_questions,
        attempt_id=attempt_id,
    )

@app.route("/api/quizzes/<int:quiz_id>/submit", methods=["POST"])
@login_required
def quiz_submit_api(quiz_id):
    # Server-side scoring only. Client score/correct answers are never trusted.
    user_id = session["user_id"]
    quiz = get_generated_quiz_for_user(quiz_id, user_id)
    if not quiz:
        return _quiz_json_error("Quiz not found.", 404)
    if _rate_limited("quiz-submit", 20):
        return _quiz_json_error("Too many submissions. Please try again later.", 429)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _quiz_json_error("Invalid request body.", 400)
    answers = data.get("answers")
    if not isinstance(answers, dict):
        return _quiz_json_error("Answers must be provided as an object.", 400)
    if len(answers) > MAX_QUIZ_ANSWER_PAYLOAD:
        return _quiz_json_error("Submitted answers exceed the allowed size.", 413)

    questions = get_quiz_questions_with_answers(quiz_id)
    if not questions:
        return _quiz_json_error("This quiz has no questions to score.", 400)
    valid_ids = {q["id"] for q in questions}

    # Validate and normalize each answer. Unknown questions are ignored safely.
    selected_answers = {}
    for raw_id, raw_value in answers.items():
        try:
            qid = int(raw_id)
        except (TypeError, ValueError):
            return _quiz_json_error("Invalid question identifier in submission.", 400)
        if qid not in valid_ids:
            continue  # ignore unknown/foreign question ids
        # Answer index must be a real int 0-3 (reject str, float, bool).
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            return _quiz_json_error("Answer selections must be integers between 0 and 3.", 400)
        if not 0 <= raw_value <= 3:
            return _quiz_json_error("Answer selections must be between 0 and 3.", 400)
        # Duplicate question ids are impossible in a JSON object; last write wins safely.
        selected_answers[qid] = raw_value
    # The active attempt for this quiz (created on the take page).
    attempt = get_active_attempt(quiz_id, user_id)
    if not attempt:
        return _quiz_json_error("No active attempt found for this quiz.", 400)

    try:
        result = finalize_quiz_attempt(attempt["id"], user_id, questions, selected_answers)
    except ValueError as exc:
        return _quiz_json_error(str(exc), 409)
    except Exception:
        logger.exception("Quiz submission failed")
        return _quiz_json_error("Quiz submission failed. Please try again later.", 500)

    result["success"] = True
    return jsonify(result), 200
@app.route("/quiz/result/<int:attempt_id>", methods=["GET"])
@login_required
def quiz_attempt_result(attempt_id):
    # Ownership-scoped; unknown/foreign attempts return a safe 404.
    attempt = get_attempt_for_user(attempt_id, session["user_id"])
    if not attempt or not attempt["submitted_at"]:
        abort(404)
    review = get_attempt_answers(attempt_id)
    return render_template("quiz_attempt_result.html", attempt=attempt, review=review,
                           letters=["A", "B", "C", "D"])

@app.route("/quiz/attempts", methods=["GET"])
@login_required
def quiz_attempt_history():
    attempts = get_user_quiz_attempts(session["user_id"])
    return render_template("quiz_attempts.html", attempts=attempts)

# ===========================================================================
# Step 14: Quiz Performance Analysis
# ===========================================================================

def _collect_performance(user_id):
    # Single source of truth for analytics: always scoped to the session user.
    return {
        "overview": get_performance_overview(user_id),
        "quiz_performance": get_performance_by_quiz(user_id),
        "course_performance": get_performance_by_course(user_id),
        "topic_performance": get_performance_by_topic(user_id),
        "recent_performance": get_recent_performance(user_id, limit=10),
    }

@app.route("/quiz/performance", methods=["GET"])
@login_required
def quiz_performance_page():
    # User id always comes from the authenticated session (no client override).
    data = _collect_performance(session["user_id"])
    return render_template("quiz_performance.html", **data)

@app.route("/api/quiz/performance", methods=["GET"])
@login_required
def quiz_performance_api():
    # Safe JSON analytics for the logged-in user only; no answer keys exposed.
    data = _collect_performance(session["user_id"])
    return jsonify({"success": True, **data}), 200

# ===========================================================================
# Step 10: Ask StudyMate / grounded Q&A
# ===========================================================================

# Configurable safe limits for Q&A (Step 11 will replace retrieval with RAG).
QNA_MAX_QUESTION_CHARS = int(os.environ.get("QNA_MAX_QUESTION_CHARS", "2000"))
QNA_CONTEXT_CHAR_LIMIT = int(os.environ.get("QNA_CONTEXT_CHAR_LIMIT", "12000"))
QNA_TEXT_STORE_LIMIT = int(os.environ.get("QNA_TEXT_STORE_LIMIT", "200000"))
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))  # Step 11 retrieved chunk count


def _qna_error(message, status):
    return jsonify({"success": False, "error": message}), status
@app.route("/ask-studymate", methods=["GET"])
@login_required
def ask_studymate():
    # Authenticated page; answers are grounded in approved materials only.
    return render_template("ask_studymate.html")

@app.route("/api/ask-studymate", methods=["POST"])
@login_required
def ask_studymate_api():
    # Server-side validation: never trust client-side checks alone.
    data = request.get_json(silent=True)
    question = data.get("question") if isinstance(data, dict) else ""
    question = question.strip() if isinstance(question, str) else ""
    if not question:
        return _qna_error("Please enter a question.", 400)
    if len(question) > QNA_MAX_QUESTION_CHARS:
        return _qna_error("Question must be " + format(QNA_MAX_QUESTION_CHARS, ",") + " characters or fewer.", 400)
    if _rate_limited("ask-studymate", 20):
        return _qna_error("Too many questions sent. Please try again in a minute.", 429)
    user = get_user_by_id(session["user_id"])
    # Step 11: RAG pipeline — approved-only retrieval + bounded context builder.
    rag = retrieve_context(
        question,
        user["department_id"] if user else None,
        top_k=RAG_TOP_K,
        max_context_chars=QNA_CONTEXT_CHAR_LIMIT,
    )

    # Confidence gate: don't call the AI with unrelated/unapproved context.
    if not rag["has_relevant"]:
        return jsonify({
            "success": True,
            "question": question,
            "answer": NO_MATCH_ANSWER,
            "sources": [],
            "retrieved_chunks": 0,
        }), 200
    sources = [
        {
            "material_id": item["material_id"],
            "course_name": item["course_name"],
            "course_code": item["course_code"],
            "topic": item["topic"],
            "exam_type": item["exam_type"],
            "library_url": url_for("study_library", q=item["topic"]),
        }
        for item in rag["sources"]
    ]

    try:
        result = answer_study_question(question, rag["context"])
    except ValueError as exc:
        # User-friendly, non-leaking AI error (missing key, rate limit, outage, etc.)
        return _qna_error(str(exc), 503)
    except Exception:
        logger.exception("Ask StudyMate request failed")
        return _qna_error("StudyMate is temporarily unavailable. Please try again later.", 500)
    return jsonify({
        "success": True,
        "question": question,
        "answer": result["answer"],
        "sources": sources,
        "retrieved_chunks": rag["chunk_count"],
        "context_truncated": rag["truncated"],
    }), 200
# ===========================================================================
# Step 9: Public Study Notes Library Routes
# ===========================================================================

@app.route("/study-library", methods=["GET"])
def study_library():
    # Public approved-only library with validated search, filters, and sorting.
    departments = get_all_departments()
    q = (request.args.get("q") or "").strip()[:120]
    department_raw = (request.args.get("department_id") or request.args.get("department") or "").strip()
    course_raw = (request.args.get("course_id") or request.args.get("course") or "").strip()
    exam_type = (request.args.get("exam_type") or "").strip().lower()
    topic = (request.args.get("topic") or "").strip()[:120]
    course_code = (request.args.get("course_code") or "").strip()[:80]
    sort = (request.args.get("sort") or "relevance").strip().lower()
    page_raw = (request.args.get("page") or "1").strip()
    error = None
    department_id = None
    course_id = None
    page = 1
    try:
        if department_raw:
            department_id = int(department_raw)
            if department_id <= 0 or not get_department_by_id(department_id): raise ValueError
        if course_raw:
            course_id = int(course_raw)
            selected_course = get_course_by_id(course_id)
            if not selected_course or (department_id is not None and selected_course["department_id"] != department_id): raise ValueError
        page = int(page_raw)
        if page < 1 or exam_type not in ("", "midterm", "final", "both") or sort not in ("relevance", "newest", "oldest", "title_asc", "title_desc"):
            raise ValueError
        materials = search_approved_study_materials(q, department_id, course_id, course_code, exam_type, topic, sort, page, 20)
        total_count = count_search_approved_study_materials(q, department_id, course_id, course_code, exam_type, topic)
    except (ValueError, TypeError):
        error = "Invalid search or filter values."
        materials, total_count, page = [], 0, 1
    selected_department_id = department_id
    courses = get_courses_by_department(selected_department_id) if selected_department_id else []
    total_pages = max((total_count + 19) // 20, 1)
    bookmarked_ids = get_bookmarked_material_ids(session["user_id"], [item["id"] for item in materials]) if session.get("user_id") else set()
    return render_template("study_library.html", materials=materials, departments=departments, courses=courses,
        selected_department_id=selected_department_id, selected_course_id=course_id, exam_type=exam_type,
        topic=topic, course_code=course_code, q=q, sort=sort, page=page, total_pages=total_pages,
        total_count=total_count, error=error, bookmarked_ids=bookmarked_ids)


def _serve_approved_material(material_id: int, as_attachment: bool):
    # Serve a file only after verifying its database status is approved."
    material = get_study_material_details(material_id)
    if not material or material["status"] != "approved":
        abort(404)
    stored_name = Path(material["file_path"]).name
    file_location = UPLOAD_FOLDER / stored_name
    if not file_location.is_file() or file_location.suffix.lower() != ".pdf":
        abort(404)
    return send_file(
        str(file_location),
        mimetype="application/pdf",
        as_attachment=as_attachment,
        download_name=stored_name,
    )

@app.route("/study-library/material/<int:material_id>/pdf", methods=["GET"])
def study_library_material_pdf(material_id: int):
    # Public inline PDF access for approved materials only."
    return _serve_approved_material(material_id, as_attachment=False)

@app.route("/study-library/material/<int:material_id>/download", methods=["GET"])
def study_library_material_download(material_id: int):
    # Public download access for approved materials only."
    return _serve_approved_material(material_id, as_attachment=True)

@app.route("/study-library/material/<int:material_id>/bookmark", methods=["POST"])
@login_required
def bookmark_material(material_id: int):
    # Create an approved-material bookmark for the logged-in user.
    material = get_study_material_details(material_id)
    if not material or material["status"] != "approved":
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"success": False, "error": "Only approved materials can be bookmarked."}), 404
        flash("Only approved materials can be bookmarked.", "error")
        return redirect(url_for("study_library"))
    add_bookmark(session["user_id"], material_id)
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"success": True, "bookmarked": True, "material_id": material_id}), 200
    flash("Study material bookmarked.", "success")
    return redirect(request.referrer or url_for("study_library"))

@app.route("/study-library/material/<int:material_id>/unbookmark", methods=["POST"])
@login_required
def unbookmark_material(material_id: int):
    # Remove only the logged-in user's bookmark.
    remove_bookmark(session["user_id"], material_id)
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"success": True, "bookmarked": False, "material_id": material_id}), 200
    flash("Bookmark removed.", "success")
    return redirect(request.referrer or url_for("study_library"))

@app.route("/my-bookmarks", methods=["GET"])
@login_required
def my_bookmarks():
    # Show only approved materials bookmarked by the authenticated user.
    q = (request.args.get("q") or "").strip()[:120]
    department_raw = (request.args.get("department_id") or "").strip()
    course_raw = (request.args.get("course_id") or "").strip()
    course_code = (request.args.get("course_code") or "").strip()[:80]
    exam_type = (request.args.get("exam_type") or "").strip().lower()
    topic = (request.args.get("topic") or "").strip()[:120]
    sort = (request.args.get("sort") or "recent").strip().lower()
    page_raw = (request.args.get("page") or "1").strip()
    department_id = course_id = None
    error = None
    try:
        if department_raw:
            department_id = int(department_raw)
            if department_id <= 0 or not get_department_by_id(department_id): raise ValueError
        if course_raw:
            course_id = int(course_raw)
            course = get_course_by_id(course_id)
            if not course or (department_id is not None and course["department_id"] != department_id): raise ValueError
        page = int(page_raw)
        if page < 1 or exam_type not in ("", "midterm", "final", "both") or sort not in ("recent", "oldest", "material_newest", "material_oldest", "title_asc", "title_desc"): raise ValueError
        materials = get_user_bookmarks(session["user_id"], q, department_id, course_id, course_code, exam_type, topic, sort, page, 20)
        total_count = count_user_bookmarks(session["user_id"], q, department_id, course_id, course_code, exam_type, topic)
    except (ValueError, TypeError):
        error = "Invalid bookmark search or filter values."
        materials, total_count, page = [], 0, 1
    departments = get_all_departments()
    courses = get_courses_by_department(department_id) if department_id else []
    return render_template("my_bookmarks.html", materials=materials, departments=departments, courses=courses,
        selected_department_id=department_id, selected_course_id=course_id, q=q, course_code=course_code,
        exam_type=exam_type, topic=topic, sort=sort, page=page, total_count=total_count,
        total_pages=max((total_count + 19) // 20, 1), error=error)

# ===========================================================================
# Step 14: In-app Notifications
# ===========================================================================

@app.route("/notifications", methods=["GET"])
@login_required
def notifications():
    raw_page = (request.args.get("page") or "1").strip()
    notification_type = (request.args.get("type") or "").strip().lower()
    read_filter = (request.args.get("read") or "").strip().lower()
    try:
        page = int(raw_page)
        rows = get_user_notifications(session["user_id"], page, 20, notification_type, read_filter)
        total = count_user_notifications(session["user_id"], notification_type, read_filter)
    except (ValueError, TypeError):
        page, rows, total = 1, [], 0
        flash("Invalid notification filters.", "error")
    return render_template("notifications.html", notifications=rows, page=page, total_pages=max((total + 19) // 20, 1), total=total, notification_type=notification_type, read_filter=read_filter)

@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def notification_read(notification_id):
    notification = get_notification_for_user(notification_id, session["user_id"])
    if not notification:
        abort(404)
    mark_notification_as_read(session["user_id"], notification_id)
    link = notification["link"] if notification["link"] and notification["link"].startswith("/") and not notification["link"].startswith("//") else url_for("notifications")
    return redirect(link)

@app.route("/notifications/read-all", methods=["POST"])
@login_required
def notifications_read_all():
    mark_all_notifications_as_read(session["user_id"])
    return redirect(request.referrer or url_for("notifications"))

# ===========================================================================
# Step 8: Admin Dashboard & Approval Workflow Routes
# ===========================================================================

def _admin_wants_json() -> bool:
    """True when the request expects a JSON response (API / automated tests)."""
    return request.headers.get("Accept") == "application/json" or request.is_json


@app.route("/admin/dashboard", methods=["GET"])
@login_required
@admin_required
def admin_dashboard():
    """
    Step 8: Admin-only dashboard listing pending study materials for review.
    Students and unauthenticated users are blocked server-side by the decorators.
    """
    pending_materials = get_pending_study_materials()
    return render_template(
        "admin/dashboard.html",
        materials=pending_materials,
        pending_count=len(pending_materials)
    )


@app.route("/admin/material/<int:material_id>", methods=["GET"])
@login_required
@admin_required
def admin_material_detail(material_id: int):
    """
    Step 8: Admin-only material review page. Shows full academic metadata
    and provides a controlled, in-browser PDF preview. The server filesystem
    path is never exposed — the PDF is served via /admin/material/<id>/pdf.
    """
    material = get_study_material_details(material_id)
    if not material:
        flash("Study material not found.", "error")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/material_detail.html", material=material)


@app.route("/admin/material/<int:material_id>/pdf", methods=["GET"])
@login_required
@admin_required
def admin_material_pdf(material_id: int):
    """
    Step 8: Controlled PDF access for admins only. Serves the stored file
    inline (browser preview) without exposing the server filesystem path.
    Path traversal is impossible because the stored filename is resolved
    strictly inside the uploads/ directory.
    """
    material = get_study_material_details(material_id)
    if not material:
        flash("Study material not found.", "error")
        return redirect(url_for("admin_dashboard"))

    stored_name = Path(material["file_path"]).name  # strip any prefix
    file_location = UPLOAD_FOLDER / stored_name
    if not file_location.is_file():
        flash("The uploaded PDF file could not be found on the server.", "error")
        return redirect(url_for("admin_material_detail", material_id=material_id))

    return send_file(
        str(file_location),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=stored_name,
    )


@app.route("/admin/material/<int:material_id>/approve", methods=["POST"])
@login_required
@admin_required
def admin_approve_material(material_id: int):
    """
    Step 8: Admin-only approval action. pending -> approved.
    Uses POST (never GET) so status changes cannot happen via URL navigation.
    The target status is decided server-side; no status field is read from
    the request body, so request manipulation cannot alter the outcome.
    """
    material = get_study_material_details(material_id)
    if not material:
        if _admin_wants_json():
            return jsonify({"success": False, "error": "Study material not found."}), 404
        flash("Study material not found.", "error")
        return redirect(url_for("admin_dashboard"))

    changed = update_study_material_status(material_id, "approved")
    if changed:
        # Step 11: ensure chunks exist for retrieval; re-index only if missing
        # (upload already indexed usable text, so this avoids duplication).
        try:
            if get_chunk_count(material_id) == 0:
                index_material(material_id)
        except Exception:
            logger.exception("Chunk indexing on approval failed for material %s", material_id)
        notify_material_approved(material["uploaded_by"], material_id, material["topic"])

    if _admin_wants_json():
        return jsonify({
            "success": True,
            "message": "Study material approved successfully.",
            "material_id": material_id,
            "status": "approved"
        }), 200

    flash(f"'{material['topic']}' approved successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/material/<int:material_id>/reject", methods=["POST"])
@login_required
@admin_required
def admin_reject_material(material_id: int):
    """
    Step 8: Admin-only rejection action. pending -> rejected.
    POST-only, status decided server-side, no frontend-controlled values.
    """
    material = get_study_material_details(material_id)
    if not material:
        if _admin_wants_json():
            return jsonify({"success": False, "error": "Study material not found."}), 404
        flash("Study material not found.", "error")
        return redirect(url_for("admin_dashboard"))

    changed = update_study_material_status(material_id, "rejected")
    if changed:
        notify_material_rejected(material["uploaded_by"], material_id, material["topic"])

    if _admin_wants_json():
        return jsonify({
            "success": True,
            "message": "Study material rejected successfully.",
            "material_id": material_id,
            "status": "rejected"
        }), 200

    flash(f"'{material['topic']}' rejected successfully.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/logout", methods=["POST"])
@login_required
def logout_post():
    logout_session()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("login"))

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
    # Show the authenticated student's dashboard while preserving the legacy JSON contract."
    current_user = get_current_user()
    accept_header = request.headers.get("Accept", "")
    wants_json = request.is_json or request.args.get("format") == "json" or ("text/html" not in accept_header and accept_header != "application/json") or accept_header == "application/json"
    if wants_json:
        return jsonify({
            "status": "authenticated",
            "message": f"Welcome to your private study dashboard, {current_user['name']}!",
            "user": current_user
        }), 200
    user_id = session["user_id"]
    return render_template(
        "dashboard.html",
        current_user=current_user,
        stats=get_student_dashboard_stats(user_id),
        course_progress=get_student_course_progress(user_id),
        recent_materials=get_recent_student_materials(user_id),
        recent_bookmarks=get_recent_student_bookmarks(user_id),
        recent_quizzes=get_recent_student_quizzes(user_id),
    )


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


def _safe_error_response(message, status_code):
    if request.is_json or request.path.startswith(("/api", "/summarize", "/upload")):
        return jsonify({"success": False, "error": message, "status": status_code}), status_code
    return render_template("error.html", message=message, status_code=status_code), status_code
@app.errorhandler(400)
def bad_request(error):
    return _safe_error_response("The request could not be processed.", 400)

@app.errorhandler(404)
def not_found(error):
    return _safe_error_response("The requested page was not found.", 404)

@app.errorhandler(405)
def method_not_allowed(error):
    return _safe_error_response("This method is not allowed.", 405)

@app.errorhandler(429)
def too_many_requests(error):
    return _safe_error_response("Too many requests. Please try again later.", 429)

@app.errorhandler(500)
def internal_error(error):
    logger.exception("Unhandled application error")
    return _safe_error_response("An internal error occurred. Please try again later.", 500)

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
