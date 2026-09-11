"""
NeuralForge StudyMate - Database Access Layer (Step 5)
Handles SQLite connection management, foreign key enforcement, schema initialization,
and modular data access methods.
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List

# Define project base and database paths
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "studymate.db"
SCHEMA_PATH = DB_DIR / "schema.sql"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Creates and returns a sqlite3 connection with:
    1. Row factory enabled (dict-like column access).
    2. Foreign key constraints strictly enforced via PRAGMA foreign_keys = ON.
    """
    target_path = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """
    Initializes the database by executing schema.sql.
    Creates all necessary tables and performance indexes.
    """
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_db_connection(db_path)
    try:
        conn.executescript(schema_sql)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(study_materials)")}
        if "extracted_text" not in columns:
            conn.execute("ALTER TABLE study_materials ADD COLUMN extracted_text TEXT")
        conn.commit()
    finally:
        conn.close()


def close_db_connection(conn: sqlite3.Connection) -> None:
    """Safely closes a database connection."""
    if conn:
        conn.close()


# ---------------------------------------------------------------------------
# Department Data Access Functions
# ---------------------------------------------------------------------------

def create_department(name: str, code: str, conn: Optional[sqlite3.Connection] = None) -> int:
    """Inserts a new department and returns its generated ID."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO departments (name, code) VALUES (?, ?)",
            (name.strip(), code.strip().upper())
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        if close_on_exit:
            conn.close()


def get_department_by_code(code: str, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieves a department by its unique code (case-insensitive)."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM departments WHERE code = ? COLLATE NOCASE", (code.strip(),))
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


def get_all_departments(conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    """Retrieves all departments ordered alphabetically by name."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM departments ORDER BY name ASC")
        return cursor.fetchall()
    finally:
        if close_on_exit:
            conn.close()


def get_department_by_id(dept_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieves a department by its primary key ID."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM departments WHERE id = ?", (dept_id,))
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


# ---------------------------------------------------------------------------
# Course Data Access Functions
# ---------------------------------------------------------------------------

def create_course(
    department_id: int,
    course_name: str,
    course_code: str,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Inserts a new course linked to a department and returns its generated ID."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO courses (department_id, course_name, course_code)
            VALUES (:dept, :name, :code)
            """,
            {"dept": department_id, "name": course_name.strip(), "code": course_code.strip()}
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        if close_on_exit:
            conn.close()


def get_course_by_code(
    course_code: str,
    department_id: Optional[int] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[sqlite3.Row]:
    """Retrieves a course by code, optionally filtered by department_id."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        if department_id is not None:
            cursor.execute(
                "SELECT * FROM courses WHERE course_code = ? COLLATE NOCASE AND department_id = ?",
                (course_code.strip(), department_id)
            )
        else:
            cursor.execute(
                "SELECT * FROM courses WHERE course_code = ? COLLATE NOCASE",
                (course_code.strip(),)
            )
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


def get_course_by_id(course_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieves a course by its primary key ID."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


def get_courses_by_department(
    department_id: int,
    conn: Optional[sqlite3.Connection] = None
) -> List[sqlite3.Row]:
    """Retrieves all courses belonging to a given department."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM courses WHERE department_id = ? ORDER BY course_code ASC",
            (department_id,)
        )
        return cursor.fetchall()
    finally:
        if close_on_exit:
            conn.close()


def get_all_courses(conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    """Retrieves all courses joined with department code."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.*, d.name AS department_name, d.code AS department_code
            FROM courses c
            JOIN departments d ON c.department_id = d.id
            ORDER BY d.code ASC, c.course_code ASC
            """
        )
        return cursor.fetchall()
    finally:
        if close_on_exit:
            conn.close()


# ---------------------------------------------------------------------------
# User Data Access Functions
# ---------------------------------------------------------------------------

def create_user(
    name: str,
    email: str,
    password_hash: str,
    department_id: Optional[int] = None,
    role: str = "student",
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Inserts a new user. Passwords MUST already be hashed with a secure algorithm
    (e.g., werkzeug.security.generate_password_hash). Never plain text.
    Role must be either 'student' or 'admin'.
    """
    role = role.lower().strip()
    if role not in ("student", "admin"):
        raise ValueError(f"Invalid role: '{role}'. Must be 'student' or 'admin'.")

    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash, department_id, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), email.strip().lower(), password_hash, department_id, role)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        if close_on_exit:
            conn.close()


def get_user_by_email(email: str, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieves a user by email address (case-insensitive)."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip().lower(),))
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


def get_user_by_id(user_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieves a user by primary key ID."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


# ---------------------------------------------------------------------------
# Study Material Data Access Functions
# ---------------------------------------------------------------------------

def create_study_material(
    course_id: int,
    topic: str,
    exam_type: str,
    file_path: str,
    uploaded_by: int,
    status: str = "pending",
    extracted_text: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Inserts a study material reference.
    - file_path: Relative or absolute path to the stored PDF in uploads/ (never stores binary).
    - exam_type: 'midterm', 'final', or 'both'.
    - status: 'pending' (default), 'approved', or 'rejected'.
    """
    exam_type = exam_type.lower().strip()
    status = status.lower().strip()

    if exam_type not in ("midterm", "final", "both"):
        raise ValueError(f"Invalid exam_type: '{exam_type}'. Must be 'midterm', 'final', or 'both'.")
    if status not in ("pending", "approved", "rejected"):
        raise ValueError(f"Invalid status: '{status}'. Must be 'pending', 'approved', or 'rejected'.")

    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_materials (course_id, topic, exam_type, file_path, uploaded_by, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (course_id, topic.strip(), exam_type, file_path.strip(), uploaded_by, status)
        )
        material_id = cursor.lastrowid
        # Store extracted PDF text separately (named parameter avoids placeholder limits).
        cursor.execute(
            "UPDATE study_materials SET extracted_text = :text WHERE id = :mid",
            {"text": extracted_text, "mid": material_id},
        )
        conn.commit()
        return material_id
    finally:
        if close_on_exit:
            conn.close()


def get_study_material_by_id(material_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    """Retrieves a study material record by its primary key ID."""
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM study_materials WHERE id = ?", (material_id,))
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


def get_study_materials_by_user(
    user_id: int,
    conn: Optional[sqlite3.Connection] = None
) -> List[sqlite3.Row]:
    """
    Retrieves all study materials uploaded by a specific user,
    joined with course and department details for display.
    Ordered by creation date descending (newest first).
    """
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                sm.id,
                sm.course_id,
                sm.topic,
                sm.exam_type,
                sm.file_path,
                sm.uploaded_by,
                sm.status,
                sm.created_at,
                c.course_name,
                c.course_code,
                d.name AS department_name,
                d.code AS department_code
            FROM study_materials sm
            JOIN courses c ON sm.course_id = c.id
            JOIN departments d ON c.department_id = d.id
            WHERE sm.uploaded_by = ?
            ORDER BY sm.created_at DESC, sm.id DESC
            """,
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        if close_on_exit:
            conn.close()


def search_approved_materials_for_qa(question: str, department_id: Optional[int] = None,
                                     limit: int = 5, context_limit: int = 12000,
                                     conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    # Retrieve only approved, keyword-ranked material for Q&A.
    import re as _re
    raw_terms = _re.findall(r"[A-Za-z0-9]+", (question or "").casefold())
    stop = {"the", "what", "how", "why", "and", "for", "are", "with", "does", "can", "explain", "define", "tell", "about", "from"}
    terms = [t for t in raw_terms if len(t) > 2 and t not in stop][:12]
    own = conn is None
    conn = conn or get_db_connection()
    try:
        rows = conn.execute(
            '''SELECT sm.id, sm.topic, sm.exam_type, sm.extracted_text,
                      c.course_name, c.course_code, c.department_id
               FROM study_materials sm JOIN courses c ON sm.course_id = c.id
               WHERE sm.status = 'approved' AND sm.extracted_text IS NOT NULL
               ORDER BY sm.id DESC LIMIT 200'''
        ).fetchall()
        ranked = []
        for row in rows:
            searchable = ' '.join((row['topic'], row['course_name'], row['course_code'], row['extracted_text'] or '')).casefold()
            score = sum(searchable.count(term) for term in terms)
            if score:
                ranked.append((score + (100 if department_id and row['department_id'] == department_id else 0), row))
        ranked.sort(key=lambda item: (-item[0], -item[1]['id']))
        result, used = [], 0
        for _, row in ranked[:max(1, min(int(limit or 5), 10))]:
            text = (row['extracted_text'] or '').strip()
            remaining = context_limit - used
            if remaining <= 0: break
            excerpt = text[:remaining]
            result.append({'material_id': row['id'], 'course_name': row['course_name'], 'course_code': row['course_code'], 'topic': row['topic'], 'exam_type': row['exam_type'], 'text': excerpt})
            used += len(excerpt)
        return result
    finally:
        if own: conn.close()


def get_material_text(material_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[str]:
    # Returns stored extracted text ONLY for approved materials (safe for Q&A reuse).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        row = conn.execute(
            "SELECT extracted_text FROM study_materials WHERE id = ? AND status = 'approved'",
            (material_id,),
        ).fetchone()
        return row["extracted_text"] if row else None
    finally:
        if own:
            conn.close()

# ---------------------------------------------------------------------------
# Material Chunks Data Access Functions (Step 11 RAG)
# ---------------------------------------------------------------------------

def save_material_chunks(material_id: int, chunks: List[str],
                         conn: Optional[sqlite3.Connection] = None) -> int:
    # Replace all chunks for a material in one transaction (idempotent re-index).
    clean_chunks = [c for c in (chunks or []) if isinstance(c, str) and c.strip()]
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM material_chunks WHERE material_id = ?", (material_id,))
        for index, content in enumerate(clean_chunks):
            cursor.execute(
                "INSERT INTO material_chunks (material_id, chunk_index, content) VALUES (?, ?, ?)",
                (material_id, index, content.strip()),
            )
        conn.commit()
        return len(clean_chunks)
    except Exception:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def delete_material_chunks(material_id: int, conn: Optional[sqlite3.Connection] = None) -> int:
    # Remove all chunks for a material. Returns the number of rows deleted.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM material_chunks WHERE material_id = ?", (material_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        if own:
            conn.close()


def get_chunk_count(material_id: int, conn: Optional[sqlite3.Connection] = None) -> int:
    # Count stored chunks for a material.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM material_chunks WHERE material_id = ?", (material_id,)
        ).fetchone()
        return int(row["n"])
    finally:
        if own:
            conn.close()


def get_material_extracted_text(material_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[str]:
    # Raw extracted text for indexing — independent of approval status.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        row = conn.execute(
            "SELECT extracted_text FROM study_materials WHERE id = ?", (material_id,)
        ).fetchone()
        return row["extracted_text"] if row else None
    finally:
        if own:
            conn.close()

# ---------------------------------------------------------------------------
# AI Quiz Generator Data Access Functions (Step 12)
# ---------------------------------------------------------------------------

def create_generated_quiz(user_id: int, course_id: int, title: str, topic: str,
                          exam_type: str, difficulty: str, questions: List[Dict[str, Any]],
                          source_material_ids: Optional[List[int]] = None,
                          conn: Optional[sqlite3.Connection] = None) -> int:
    # Persist a generated quiz, its questions and its source traceability in one tx.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO generated_quizzes (user_id, course_id, title, topic, exam_type, difficulty, question_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, course_id, title, topic, exam_type, difficulty, len(questions)),
        )
        quiz_id = cursor.lastrowid
        for order, question in enumerate(questions):
            options = question["options"]
            cursor.execute(
                "INSERT INTO generated_quiz_questions "
                "(quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, question_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (quiz_id, question["question"], options[0], options[1], options[2], options[3],
                 int(question["correct_answer"]), question["explanation"], order),
            )
        for material_id in (source_material_ids or []):
            cursor.execute(
                "INSERT OR IGNORE INTO quiz_sources (quiz_id, material_id) VALUES (?, ?)",
                (quiz_id, material_id),
            )
        conn.commit()
        return quiz_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def get_generated_quiz_for_user(quiz_id: int, user_id: int,
                                conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    # Ownership-scoped fetch (prevents IDOR); joined with course/department labels.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT gq.*, c.course_name, c.course_code, d.code AS department_code "
            "FROM generated_quizzes gq JOIN courses c ON gq.course_id = c.id "
            "JOIN departments d ON c.department_id = d.id "
            "WHERE gq.id = ? AND gq.user_id = ?",
            (quiz_id, user_id),
        ).fetchone()
    finally:
        if own:
            conn.close()


def get_generated_quiz_questions(quiz_id: int,
                                 conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT * FROM generated_quiz_questions WHERE quiz_id = ? ORDER BY question_order ASC",
            (quiz_id,),
        ).fetchall()
    finally:
        if own:
            conn.close()


def get_generated_quiz_sources(quiz_id: int,
                               conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    # Safe source metadata only — never file paths or hidden columns.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT qs.material_id, sm.topic, c.course_name, c.course_code "
            "FROM quiz_sources qs JOIN study_materials sm ON qs.material_id = sm.id "
            "JOIN courses c ON sm.course_id = c.id WHERE qs.quiz_id = ?",
            (quiz_id,),
        ).fetchall()
    finally:
        if own:
            conn.close()

# ---------------------------------------------------------------------------
# Quiz Attempt Data Access Functions (Step 13)
# ---------------------------------------------------------------------------

def get_quiz_questions_with_answers(quiz_id: int,
                                    conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    # Server-side only: includes correct_answer. NEVER render this directly to the browser.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT id, quiz_id, question_text, option_a, option_b, option_c, option_d, "
            "correct_answer, explanation, question_order "
            "FROM generated_quiz_questions WHERE quiz_id = ? ORDER BY question_order ASC",
            (quiz_id,),
        ).fetchall()
    finally:
        if own:
            conn.close()


def get_active_attempt(quiz_id: int, user_id: int,
                       conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    # The most recent UNSUBMITTED attempt for this user/quiz (to avoid new rows on refresh).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT * FROM generated_quiz_attempts "
            "WHERE quiz_id = ? AND user_id = ? AND submitted_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (quiz_id, user_id),
        ).fetchone()
    finally:
        if own:
            conn.close()


def create_generated_quiz_attempt(quiz_id: int, user_id: int, total_questions: int,
                                  conn: Optional[sqlite3.Connection] = None) -> int:
    # Create an in-progress attempt (score/submitted_at stay NULL until submission).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO generated_quiz_attempts (quiz_id, user_id, total_questions) VALUES (?, ?, ?)",
            (quiz_id, user_id, total_questions),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        if own:
            conn.close()


def get_attempt_for_user(attempt_id: int, user_id: int,
                         conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    # Ownership-scoped attempt fetch (prevents IDOR).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT a.*, gq.title, gq.topic, gq.difficulty, gq.exam_type, "
            "c.course_name, c.course_code "
            "FROM generated_quiz_attempts a "
            "JOIN generated_quizzes gq ON a.quiz_id = gq.id "
            "JOIN courses c ON gq.course_id = c.id "
            "WHERE a.id = ? AND a.user_id = ?",
            (attempt_id, user_id),
        ).fetchone()
    finally:
        if own:
            conn.close()


def finalize_quiz_attempt(attempt_id: int, user_id: int, questions: List[sqlite3.Row],
                          selected_answers: Dict[int, Optional[int]],
                          conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    # Atomically score and finalize an attempt.
    # - Rejects an already-submitted attempt (one-time submission).
    # - Scores strictly using the database correct_answer (never client input).
    # - Unanswered questions count as incorrect.
    # - Writes attempt answers + finalized attempt in one transaction; rolls back on error.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cursor = conn.cursor()
        # Lock/verify this attempt row is still unsubmitted and owned by the user.
        row = cursor.execute(
            "SELECT id, submitted_at FROM generated_quiz_attempts WHERE id = ? AND user_id = ?",
            (attempt_id, user_id),
        ).fetchone()
        if row is None:
            raise ValueError("Attempt not found.")
        if row["submitted_at"]:
            raise ValueError("This attempt has already been submitted.")

        correct = 0
        answers_to_save = []
        for question in questions:
            qid = question["id"]
            selected = selected_answers.get(qid)
            is_correct = int(selected is not None and selected == question["correct_answer"])
            if is_correct:
                correct += 1
            answers_to_save.append((attempt_id, qid, selected, is_correct))

        total = len(questions)
        wrong = total - correct
        percentage = round((correct / total) * 100, 2) if total else 0.0
        cursor.executemany(
            "INSERT OR REPLACE INTO generated_quiz_attempt_answers "
            "(attempt_id, question_id, selected_answer, is_correct) VALUES (?, ?, ?, ?)",
            answers_to_save,
        )
        cursor.execute(
            "UPDATE generated_quiz_attempts SET score = ?, correct_answers = ?, wrong_answers = ?, "
            "percentage = ?, submitted_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ? AND submitted_at IS NULL",
            (correct, correct, wrong, percentage, attempt_id, user_id),
        )
        if cursor.rowcount != 1:
            # Lost a race: another request already finalized this attempt.
            conn.rollback()
            raise ValueError("This attempt has already been submitted.")
        conn.commit()
        return {
            "attempt_id": attempt_id,
            "score": correct,
            "total_questions": total,
            "correct_answers": correct,
            "wrong_answers": wrong,
            "percentage": percentage,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def get_attempt_answers(attempt_id: int,
                        conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    # Per-question review rows (joined with the stored questions for display).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT aa.question_id, aa.selected_answer, aa.is_correct, "
            "qq.question_text, qq.option_a, qq.option_b, qq.option_c, qq.option_d, "
            "qq.correct_answer, qq.explanation, qq.question_order "
            "FROM generated_quiz_attempt_answers aa "
            "JOIN generated_quiz_questions qq ON aa.question_id = qq.id "
            "WHERE aa.attempt_id = ? ORDER BY qq.question_order ASC",
            (attempt_id,),
        ).fetchall()
    finally:
        if own:
            conn.close()


def get_user_quiz_attempts(user_id: int,
                           conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    # Only finalized attempts, newest first, for the logged-in user.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            "SELECT a.id, a.score, a.total_questions, a.correct_answers, a.wrong_answers, "
            "a.percentage, a.submitted_at, gq.title, gq.topic, gq.difficulty, gq.exam_type, "
            "c.course_name, c.course_code "
            "FROM generated_quiz_attempts a "
            "JOIN generated_quizzes gq ON a.quiz_id = gq.id "
            "JOIN courses c ON gq.course_id = c.id "
            "WHERE a.user_id = ? AND a.submitted_at IS NOT NULL "
            "ORDER BY a.submitted_at DESC, a.id DESC",
            (user_id,),
        ).fetchall()
    finally:
        if own:
            conn.close()

# ---------------------------------------------------------------------------
# Quiz Performance Analytics Data Access Functions (Step 14)
# All queries are scoped to a single authenticated user_id (passed from the
# session by the route) and only consider FINALIZED attempts. No client- supplied
# user id is ever accepted. No answer keys are exposed here.
# ---------------------------------------------------------------------------

def get_performance_overview(user_id: int,
                             conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    # Aggregate finalized attempts for one user. Zero-data safe (never divides by zero).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS completed_quizzes, "
            "COALESCE(SUM(total_questions), 0) AS total_questions, "
            "COALESCE(SUM(correct_answers), 0) AS total_correct, "
            "COALESCE(SUM(wrong_answers), 0) AS total_wrong, "
            "COALESCE(AVG(percentage), 0) AS average_percentage "
            "FROM generated_quiz_attempts "
            "WHERE user_id = ? AND submitted_at IS NOT NULL",
            (user_id,),
        ).fetchone()
        completed = int(row["completed_quizzes"] or 0)
        total_questions = int(row["total_questions"] or 0)
        total_correct = int(row["total_correct"] or 0)
        total_wrong = int(row["total_wrong"] or 0)
        accuracy = round((total_correct / total_questions) * 100, 2) if total_questions else 0.0
        return {
            "completed_quizzes": completed,
            "total_questions": total_questions,
            "total_correct": total_correct,
            "total_wrong": total_wrong,
            "overall_accuracy": accuracy,
            "average_percentage": round(float(row["average_percentage"] or 0.0), 2),
        }
    finally:
        if own:
            conn.close()


def get_performance_by_quiz(user_id: int,
                            conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    # Per-attempt performance for finalized attempts, newest first.
    own = conn is None
    conn = conn or get_db_connection()
    try:
        rows = conn.execute(
            "SELECT a.id AS attempt_id, a.quiz_id, gq.title AS quiz_title, gq.topic, "
            "a.score, a.total_questions, a.correct_answers, a.wrong_answers, "
            "a.percentage, a.submitted_at, c.course_name, c.course_code "
            "FROM generated_quiz_attempts a "
            "JOIN generated_quizzes gq ON a.quiz_id = gq.id "
            "LEFT JOIN courses c ON gq.course_id = c.id "
            "WHERE a.user_id = ? AND a.submitted_at IS NOT NULL "
            "ORDER BY a.submitted_at DESC, a.id DESC",
            (user_id,),
        ).fetchall()
        return [
            {
                "attempt_id": r["attempt_id"],
                "quiz_id": r["quiz_id"],
                "quiz_title": r["quiz_title"],
                "course_name": r["course_name"],
                "course_code": r["course_code"],
                "topic": r["topic"],
                "score": r["score"],
                "total_questions": r["total_questions"],
                "correct_answers": r["correct_answers"],
                "wrong_answers": r["wrong_answers"],
                "percentage": round(float(r["percentage"] or 0.0), 2),
                "submitted_at": r["submitted_at"],
            }
            for r in rows
        ]
    finally:
        if own:
            conn.close()


def get_performance_by_course(user_id: int,
                              conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    # Aggregate finalized attempts by course (LEFT JOIN keeps orphans safe).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        rows = conn.execute(
            "SELECT c.id AS course_id, c.course_name, c.course_code, "
            "COUNT(*) AS quiz_count, "
            "COALESCE(SUM(a.total_questions), 0) AS total_questions, "
            "COALESCE(SUM(a.correct_answers), 0) AS total_correct, "
            "COALESCE(SUM(a.wrong_answers), 0) AS total_wrong, "
            "COALESCE(AVG(a.percentage), 0) AS average_percentage "
            "FROM generated_quiz_attempts a "
            "JOIN generated_quizzes gq ON a.quiz_id = gq.id "
            "LEFT JOIN courses c ON gq.course_id = c.id "
            "WHERE a.user_id = ? AND a.submitted_at IS NOT NULL "
            "GROUP BY c.id "
            "ORDER BY average_percentage DESC",
            (user_id,),
        ).fetchall()
        result = []
        for r in rows:
            total_questions = int(r["total_questions"] or 0)
            total_correct = int(r["total_correct"] or 0)
            result.append({
                "course_id": r["course_id"],
                "course_name": r["course_name"] or "Unknown course",
                "course_code": r["course_code"] or "N/A",
                "quiz_count": int(r["quiz_count"] or 0),
                "total_questions": total_questions,
                "total_correct": total_correct,
                "total_wrong": int(r["total_wrong"] or 0),
                "accuracy": round((total_correct / total_questions) * 100, 2) if total_questions else 0.0,
                "average_percentage": round(float(r["average_percentage"] or 0.0), 2),
            })
        return result
    finally:
        if own:
            conn.close()


def get_performance_by_topic(user_id: int,
                             conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    # Aggregate finalized attempts by quiz topic (raw performance only; no weak/strong labels).
    own = conn is None
    conn = conn or get_db_connection()
    try:
        rows = conn.execute(
            "SELECT gq.topic, COUNT(*) AS quiz_count, "
            "COALESCE(SUM(a.total_questions), 0) AS total_questions, "
            "COALESCE(SUM(a.correct_answers), 0) AS total_correct, "
            "COALESCE(SUM(a.wrong_answers), 0) AS total_wrong, "
            "COALESCE(AVG(a.percentage), 0) AS average_percentage "
            "FROM generated_quiz_attempts a "
            "JOIN generated_quizzes gq ON a.quiz_id = gq.id "
            "WHERE a.user_id = ? AND a.submitted_at IS NOT NULL "
            "GROUP BY gq.topic "
            "ORDER BY average_percentage DESC",
            (user_id,),
        ).fetchall()
        result = []
        for r in rows:
            total_questions = int(r["total_questions"] or 0)
            total_correct = int(r["total_correct"] or 0)
            result.append({
                "topic": r["topic"] or "General",
                "quiz_count": int(r["quiz_count"] or 0),
                "total_questions": total_questions,
                "total_correct": total_correct,
                "total_wrong": int(r["total_wrong"] or 0),
                "accuracy": round((total_correct / total_questions) * 100, 2) if total_questions else 0.0,
                "average_percentage": round(float(r["average_percentage"] or 0.0), 2),
            })
        return result
    finally:
        if own:
            conn.close()


def get_recent_performance(user_id: int, limit: int = 10,
                           conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    # Latest finalized attempts, newest first (bounded).
    limit = max(1, min(int(limit or 10), 50))
    own = conn is None
    conn = conn or get_db_connection()
    try:
        rows = conn.execute(
            "SELECT a.id AS attempt_id, gq.title AS quiz_title, gq.topic, "
            "a.percentage, a.submitted_at, c.course_name, c.course_code "
            "FROM generated_quiz_attempts a "
            "JOIN generated_quizzes gq ON a.quiz_id = gq.id "
            "LEFT JOIN courses c ON gq.course_id = c.id "
            "WHERE a.user_id = ? AND a.submitted_at IS NOT NULL "
            "ORDER BY a.submitted_at DESC, a.id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [
            {
                "attempt_id": r["attempt_id"],
                "quiz_title": r["quiz_title"],
                "topic": r["topic"],
                "course_name": r["course_name"] or "Unknown course",
                "course_code": r["course_code"] or "N/A",
                "percentage": round(float(r["percentage"] or 0.0), 2),
                "submitted_at": r["submitted_at"],
            }
            for r in rows
        ]
    finally:
        if own:
            conn.close()

# ---------------------------------------------------------------------------
# Admin Approval Workflow Data Access Functions (Step 8)
# ---------------------------------------------------------------------------

def get_study_materials_by_status(
    status: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[sqlite3.Row]:
    """
    Retrieves all study materials with the given status ('pending', 'approved',
    'rejected'), joined with course, department and uploader details.
    Ordered by creation date ascending (oldest first, for fair admin review).
    """
    if status not in ("pending", "approved", "rejected"):
        raise ValueError(f"Invalid status filter: '{status}'.")

    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                sm.id,
                sm.course_id,
                sm.topic,
                sm.exam_type,
                sm.file_path,
                sm.uploaded_by,
                sm.status,
                sm.created_at,
                c.course_name,
                c.course_code,
                d.name AS department_name,
                d.code AS department_code,
                u.name AS uploader_name,
                u.email AS uploader_email
            FROM study_materials sm
            JOIN courses c ON sm.course_id = c.id
            JOIN departments d ON c.department_id = d.id
            JOIN users u ON sm.uploaded_by = u.id
            WHERE sm.status = ?
            ORDER BY sm.created_at ASC, sm.id ASC
            """,
            (status,)
        )
        return cursor.fetchall()
    finally:
        if close_on_exit:
            conn.close()


def get_pending_study_materials(conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    """Convenience wrapper: retrieves all materials with status = 'pending'."""
    return get_study_materials_by_status("pending", conn=conn)


def get_study_material_details(
    material_id: int,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[sqlite3.Row]:
    """
    Retrieves a single study material with full joined details
    (course, department, uploader) for the admin review page.
    """
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                sm.id,
                sm.course_id,
                sm.topic,
                sm.exam_type,
                sm.file_path,
                sm.uploaded_by,
                sm.status,
                sm.created_at,
                c.course_name,
                c.course_code,
                d.name AS department_name,
                d.code AS department_code,
                u.name AS uploader_name,
                u.email AS uploader_email
            FROM study_materials sm
            JOIN courses c ON sm.course_id = c.id
            JOIN departments d ON c.department_id = d.id
            JOIN users u ON sm.uploaded_by = u.id
            WHERE sm.id = ?
            """,
            (material_id,)
        )
        return cursor.fetchone()
    finally:
        if close_on_exit:
            conn.close()


def update_study_material_status(
    material_id: int,
    new_status: str,
    conn: Optional[sqlite3.Connection] = None
) -> bool:
    """
    Updates a study material's approval status (admin approval workflow).
    Allowed transitions (from any current status):
        pending -> approved | rejected
        approved -> rejected   (admin may change their mind)
        rejected -> approved   (admin may change their mind)
    Transitions to 'pending' are NOT allowed — a material can never go back
    into the pending queue via status update.
    Returns True if a row was updated, False if the material does not exist.
    Raises ValueError for invalid target status.
    """
    new_status = (new_status or "").lower().strip()
    if new_status not in ("approved", "rejected"):
        raise ValueError(f"Invalid status: '{new_status}'. Must be 'approved' or 'rejected'.")

    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE study_materials SET status = ? WHERE id = ? AND status = 'pending'",
            (new_status, material_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        if close_on_exit:
            conn.close()


# ---------------------------------------------------------------------------
# Public Study Library Data Access Functions (Step 9)
# ---------------------------------------------------------------------------

def get_approved_study_materials(
    department_id: Optional[int] = None,
    course_id: Optional[int] = None,
    course_code: str = "",
    exam_type: str = "",
    topic: str = "",
    page: int = 1,
    per_page: int = 20,
    conn: Optional[sqlite3.Connection] = None,
) -> List[sqlite3.Row]:
    # Return only approved materials, with validated relational filters.
    if exam_type and exam_type not in ("midterm", "final", "both"):
        raise ValueError("Invalid exam type filter.")
    page = max(int(page or 1), 1)
    per_page = min(max(int(per_page or 20), 1), 100)
    clauses = ["sm.status = 'approved'"]
    params: List[Any] = []
    if department_id is not None:
        clauses.append("c.department_id = ?")
        params.append(department_id)
    if course_id is not None:
        clauses.append("sm.course_id = ?")
        params.append(course_id)
    if course_code:
        clauses.append("c.course_code LIKE ? COLLATE NOCASE")
        params.append(f"%{course_code.strip()}%")
    if exam_type:
        clauses.append("sm.exam_type = ?")
        params.append(exam_type)
    if topic:
        clauses.append("sm.topic LIKE ? COLLATE NOCASE")
        params.append(f"%{topic.strip()}%")
    params.extend([per_page, (page - 1) * per_page])

    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True
    try:
        cursor = conn.cursor()
        query = (
            "SELECT sm.id, sm.course_id, sm.topic, sm.exam_type, sm.file_path, "
            "sm.uploaded_by, sm.status, sm.created_at, c.course_name, c.course_code, "
            "d.name AS department_name, d.code AS department_code, u.name AS uploader_name "
            "FROM study_materials sm JOIN courses c ON sm.course_id = c.id "
            "JOIN departments d ON c.department_id = d.id JOIN users u ON sm.uploaded_by = u.id "
            "WHERE " + " AND ".join(clauses) +
            " ORDER BY sm.created_at DESC, sm.id DESC LIMIT ? OFFSET ?"
        )
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        if close_on_exit:
            conn.close()


def count_approved_study_materials(
    department_id: Optional[int] = None,
    course_id: Optional[int] = None,
    course_code: str = "",
    exam_type: str = "",
    topic: str = "",
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    # Count approved materials using the same filters as the library query.
    # Keep count behavior aligned by querying IDs with a generous bounded limit.
    # The library only needs a boolean/count for pagination display.
    rows = get_approved_study_materials(
        department_id, course_id, course_code, exam_type, topic,
        page=1, per_page=100000, conn=conn
    )
    return len(rows)


# ---------------------------------------------------------------------------
# Quiz Data Access Functions (Step 10)
# ---------------------------------------------------------------------------

def create_quiz(material_id: int, created_by: int, title: str, question_type: str,
                difficulty: str, question_count: int,
                questions: List[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None) -> int:
    # Persist a generated quiz and its answer key in one transaction.
    close_on_exit = False
    if conn is None:
        conn = get_db_connection()
        close_on_exit = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO quizzes (material_id, created_by, title, question_type, difficulty, question_count) VALUES (?, ?, ?)",
            (material_id, created_by, title.strip(), question_type, difficulty, question_count),
        )
        quiz_id = cursor.lastrowid
        for position, question in enumerate(questions, start=1):
            cursor.execute(
                "INSERT INTO quiz_questions (quiz_id, position, question_type, question_text, options_json, correct_answer, expected_answer, explanation, difficulty) VALUES (?, ?, ?)","",
                (quiz_id, position, question["question_type"], question["question"],
                 question.get("options_json"), question.get("correct_answer"),
                 question.get("expected_answer"), question["explanation"], question["difficulty"]),
            )
        conn.commit()
        return quiz_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if close_on_exit:
            conn.close()


def get_quiz_for_user(quiz_id: int, user_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    # Return a quiz only when owned by the authenticated user.
    close_on_exit = False
    if conn is None:
        conn = get_db_connection(); close_on_exit = True
    try:
        return conn.execute(
            "SELECT q.*, sm.topic, c.course_name, c.course_code, d.code AS department_code FROM quizzes q JOIN study_materials sm ON q.material_id = sm.id JOIN courses c ON sm.course_id = c.id JOIN departments d ON c.department_id = d.id WHERE q.id = ? AND q.created_by = ?", (quiz_id, user_id)
        ).fetchone()
    finally:
        if close_on_exit: conn.close()


def get_quiz_questions(quiz_id: int, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    close_on_exit = False
    if conn is None: conn = get_db_connection(); close_on_exit = True
    try:
        return conn.execute("SELECT * FROM quiz_questions WHERE quiz_id = ? ORDER BY position", (quiz_id,)).fetchall()
    finally:
        if close_on_exit: conn.close()


def create_quiz_attempt(quiz_id: int, user_id: int, score: int, total: int, percentage: float,
                       answers: List[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None) -> int:
    close_on_exit = False
    if conn is None: conn = get_db_connection(); close_on_exit = True
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions, percentage) VALUES (?, ?, ?)",
                       (quiz_id, user_id, score, total, percentage))
        attempt_id = cursor.lastrowid
        for answer in answers:
            cursor.execute("INSERT INTO quiz_answers (attempt_id, question_id, submitted_answer, is_correct) VALUES (?, ?, ?)",
                           (attempt_id, answer["question_id"], answer["submitted_answer"], int(answer["is_correct"])))
        conn.commit()
        return attempt_id
    except Exception:
        conn.rollback(); raise
    finally:
        if close_on_exit: conn.close()


def get_quiz_attempt_for_user(attempt_id: int, user_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    close_on_exit = False
    if conn is None: conn = get_db_connection(); close_on_exit = True
    try:
        return conn.execute("SELECT a.*, q.title, q.created_by, q.material_id FROM quiz_attempts a JOIN quizzes q ON a.quiz_id = q.id WHERE a.id = ? AND a.user_id = ?", (attempt_id, user_id)).fetchone()
    finally:
        if close_on_exit: conn.close()


def get_attempt_review(attempt_id: int, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    close_on_exit = False
    if conn is None: conn = get_db_connection(); close_on_exit = True
    try:
        return conn.execute("SELECT qq.*, qa.submitted_answer, qa.is_correct FROM quiz_answers qa JOIN quiz_questions qq ON qa.question_id = qq.id WHERE qa.attempt_id = ? ORDER BY qq.position", (attempt_id,)).fetchall()
    finally:
        if close_on_exit: conn.close()


# Step 10 corrected quiz persistence helpers (defined after legacy helpers).
def create_quiz(material_id: int, created_by: int, title: str, question_type: str,
                difficulty: str, question_count: int, questions: List[Dict[str, Any]],
                conn: Optional[sqlite3.Connection] = None) -> int:
    close_on_exit = False
    if conn is None:
        conn = get_db_connection(); close_on_exit = True
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO quizzes (material_id, created_by, title, question_type, difficulty, question_count) VALUES (?, ?, ?)",
                    (material_id, created_by, title.strip(), question_type, difficulty, question_count))
        quiz_id = cur.lastrowid
        for position, question in enumerate(questions, 1):
            cur.execute("INSERT INTO quiz_questions (quiz_id, position, question_type, question_text, options_json, correct_answer, expected_answer, explanation, difficulty) VALUES (?, ?, ?)",
                        (quiz_id, position, question["question_type"], question["question"], question.get("options_json"), question.get("correct_answer"), question.get("expected_answer"), question["explanation"], question["difficulty"]))
        conn.commit()
        return quiz_id
    except Exception:
        conn.rollback(); raise
    finally:
        if close_on_exit: conn.close()


def create_quiz_attempt(quiz_id: int, user_id: int, score: int, total: int, percentage: float,
                        answers: List[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None) -> int:
    close_on_exit = False
    if conn is None:
        conn = get_db_connection(); close_on_exit = True
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions, percentage) VALUES (?, ?, ?)",
                    (quiz_id, user_id, score, total, percentage))
        attempt_id = cur.lastrowid
        for answer in answers:
            cur.execute("INSERT INTO quiz_answers (attempt_id, question_id, submitted_answer, is_correct) VALUES (?, ?, ?)",
                        (attempt_id, answer["question_id"], answer["submitted_answer"], int(answer["is_correct"])))
        conn.commit(); return attempt_id
    except Exception:
        conn.rollback(); raise
    finally:
        if close_on_exit: conn.close()


# Final Step 10 SQL implementations.
def create_quiz(material_id: int, created_by: int, title: str, question_type: str, difficulty: str, question_count: int, questions: List[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None) -> int:
    close_on_exit = False
    if conn is None:
        conn = get_db_connection(); close_on_exit = True
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO quizzes (material_id, created_by, title, question_type, difficulty, question_count) VALUES (?, ?, ?)", (material_id, created_by, title.strip(), question_type, difficulty, question_count))
        quiz_id = cur.lastrowid
        for position, question in enumerate(questions, 1):
            cur.execute("INSERT INTO quiz_questions (quiz_id, position, question_type, question_text, options_json, correct_answer, expected_answer, explanation, difficulty) VALUES (?, ?, ?)", (quiz_id, position, question["question_type"], question["question"], question.get("options_json"), question.get("correct_answer"), question.get("expected_answer"), question["explanation"], question["difficulty"]))
        conn.commit(); return quiz_id
    except Exception:
        conn.rollback(); raise
    finally:
        if close_on_exit: conn.close()


def create_quiz_attempt(quiz_id: int, user_id: int, score: int, total: int, percentage: float, answers: List[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None) -> int:
    close_on_exit = False
    if conn is None:
        conn = get_db_connection(); close_on_exit = True
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions, percentage) VALUES (?, ?, ?)", (quiz_id, user_id, score, total, percentage))
        attempt_id = cur.lastrowid
        for answer in answers:
            cur.execute("INSERT INTO quiz_answers (attempt_id, question_id, submitted_answer, is_correct) VALUES (?, ?, ?)", (attempt_id, answer["question_id"], answer["submitted_answer"], int(answer["is_correct"])))
        conn.commit(); return attempt_id
    except Exception:
        conn.rollback(); raise
    finally:
        if close_on_exit: conn.close()


# Definitive Step 10 persistence implementations.
def create_quiz(material_id, created_by, title, question_type, difficulty, question_count, questions, conn=None):
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('INSERT INTO quizzes (material_id, created_by, title, question_type, difficulty, question_count) VALUES (:material_id, :created_by, :title, :question_type, :difficulty, :question_count)', {'material_id': material_id, 'created_by': created_by, 'title': title.strip(), 'question_type': question_type, 'difficulty': difficulty, 'question_count': question_count})
        quiz_id = cur.lastrowid
        sql = 'INSERT INTO quiz_questions (quiz_id, position, question_type, question_text, options_json, correct_answer, expected_answer, explanation, difficulty) VALUES (:quiz_id, :position, :question_type, :question, :options, :correct, :expected, :explanation, :difficulty)'
        for position, q in enumerate(questions, 1):
            cur.execute(sql, {'quiz_id': quiz_id, 'position': position, 'question_type': q['question_type'], 'question': q['question'], 'options': q.get('options_json'), 'correct': q.get('correct_answer'), 'expected': q.get('expected_answer'), 'explanation': q['explanation'], 'difficulty': q['difficulty']})
        conn.commit()
        return quiz_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if own: conn.close()


def get_quiz_for_user(quiz_id, user_id, conn=None):
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute('SELECT q.*, sm.topic, c.course_name, c.course_code, d.code AS department_code FROM quizzes q JOIN study_materials sm ON q.material_id=sm.id JOIN courses c ON sm.course_id=c.id JOIN departments d ON c.department_id=d.id WHERE q.id=? AND q.created_by=?', (quiz_id, user_id)).fetchone()
    finally:
        if own: conn.close()


def get_quiz_questions(quiz_id, conn=None):
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute('SELECT * FROM quiz_questions WHERE quiz_id=? ORDER BY position', (quiz_id,)).fetchall()
    finally:
        if own: conn.close()


def create_quiz_attempt(quiz_id, user_id, score, total, percentage, answers, conn=None):
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions, percentage) VALUES (:quiz_id, :user_id, :score, :total, :percentage)', {'quiz_id': quiz_id, 'user_id': user_id, 'score': score, 'total': total, 'percentage': percentage})
        attempt_id = cur.lastrowid
        for answer in answers:
            cur.execute('INSERT INTO quiz_answers (attempt_id, question_id, submitted_answer, is_correct) VALUES (:attempt_id, :question_id, :answer, :correct)', {'attempt_id': attempt_id, 'question_id': answer['question_id'], 'answer': answer['submitted_answer'], 'correct': int(answer['is_correct'])})
        conn.commit()
        return attempt_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if own: conn.close()


def get_quiz_attempt_for_user(attempt_id, user_id, conn=None):
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute('SELECT a.*, q.title, q.created_by, q.material_id FROM quiz_attempts a JOIN quizzes q ON a.quiz_id=q.id WHERE a.id=? AND a.user_id=?', (attempt_id, user_id)).fetchone()
    finally:
        if own: conn.close()


def get_attempt_review(attempt_id, conn=None):
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute('SELECT qq.*, qa.submitted_answer, qa.is_correct FROM quiz_answers qa JOIN quiz_questions qq ON qa.question_id=qq.id WHERE qa.attempt_id=? ORDER BY qq.position', (attempt_id,)).fetchall()
    finally:
        if own: conn.close()


# ---------------------------------------------------------------------------
# Smart Search & Discovery (Step 11)
# ---------------------------------------------------------------------------

def search_approved_study_materials(
    query_text: str = "", department_id: Optional[int] = None,
    course_id: Optional[int] = None, course_code: str = "",
    exam_type: str = "", topic: str = "", sort: str = "relevance",
    page: int = 1, per_page: int = 20,
    conn: Optional[sqlite3.Connection] = None,
) -> List[sqlite3.Row]:
    # Searches approved materials only, with parameterized filters and sorting."
    allowed_sorts = {"relevance", "newest", "oldest", "title_asc", "title_desc"}
    if exam_type and exam_type not in ("midterm", "final", "both"):
        raise ValueError("Invalid exam type filter.")
    if sort not in allowed_sorts:
        raise ValueError("Invalid sort option.")
    page = max(int(page or 1), 1)
    per_page = min(max(int(per_page or 20), 1), 100)
    clauses = ["sm.status = 'approved'"]
    params: List[Any] = []
    clean_query = (query_text or "").strip()[:120]
    if clean_query:
        pattern = f"%{clean_query}%"
        clauses.append("(sm.topic LIKE ? COLLATE NOCASE OR c.course_name LIKE ? COLLATE NOCASE OR c.course_code LIKE ? COLLATE NOCASE OR d.name LIKE ? COLLATE NOCASE OR d.code LIKE ? COLLATE NOCASE)")
        params.extend([pattern] * 5)
    if department_id is not None:
        clauses.append("c.department_id = ?"); params.append(department_id)
    if course_id is not None:
        clauses.append("sm.course_id = ?"); params.append(course_id)
    if course_code:
        clauses.append("c.course_code LIKE ? COLLATE NOCASE"); params.append(f"%{course_code.strip()[:80]}%")
    if exam_type:
        clauses.append("sm.exam_type = ?"); params.append(exam_type)
    if topic:
        clauses.append("sm.topic LIKE ? COLLATE NOCASE"); params.append(f"%{topic.strip()[:120]}%")
    order_map = {
        "newest": "sm.created_at DESC, sm.id DESC",
        "oldest": "sm.created_at ASC, sm.id ASC",
        "title_asc": "sm.topic COLLATE NOCASE ASC, sm.id DESC",
        "title_desc": "sm.topic COLLATE NOCASE DESC, sm.id DESC",
    }
    if clean_query and sort == "relevance":
        order_sql = "CASE WHEN sm.topic = ? COLLATE NOCASE THEN 0 WHEN sm.topic LIKE ? COLLATE NOCASE THEN 1 WHEN c.course_name LIKE ? COLLATE NOCASE THEN 2 WHEN c.course_code LIKE ? COLLATE NOCASE THEN 3 ELSE 4 END, sm.created_at DESC, sm.id DESC"
        order_params = [clean_query, f"{clean_query}%", f"%{clean_query}%", f"%{clean_query}%"]
    else:
        order_sql = order_map.get(sort, "sm.created_at DESC, sm.id DESC")
        order_params = []
    params.extend(order_params)
    params.extend([per_page, (page - 1) * per_page])
    own = conn is None
    conn = conn or get_db_connection()
    try:
        sql = ("SELECT sm.id, sm.course_id, sm.topic, sm.exam_type, sm.file_path, sm.uploaded_by, sm.status, sm.created_at, "
               "c.course_name, c.course_code, d.name AS department_name, d.code AS department_code, u.name AS uploader_name "
               "FROM study_materials sm JOIN courses c ON sm.course_id=c.id JOIN departments d ON c.department_id=d.id JOIN users u ON sm.uploaded_by=u.id WHERE "
               + " AND ".join(clauses) + " ORDER BY " + order_sql + " LIMIT ? OFFSET ?")
        return conn.execute(sql, params).fetchall()
    finally:
        if own: conn.close()


def count_search_approved_study_materials(
    query_text: str = "", department_id: Optional[int] = None,
    course_id: Optional[int] = None, course_code: str = "",
    exam_type: str = "", topic: str = "", conn: Optional[sqlite3.Connection] = None,
) -> int:
    # Counts approved search results using the exact same filter predicates."
    clean_query = (query_text or "").strip()[:120]
    clauses = ["sm.status = 'approved'"]; params: List[Any] = []
    if clean_query:
        pattern = f"%{clean_query}%"
        clauses.append("(sm.topic LIKE ? COLLATE NOCASE OR c.course_name LIKE ? COLLATE NOCASE OR c.course_code LIKE ? COLLATE NOCASE OR d.name LIKE ? COLLATE NOCASE OR d.code LIKE ? COLLATE NOCASE)"); params.extend([pattern] * 5)
    if department_id is not None: clauses.append("c.department_id = ?"); params.append(department_id)
    if course_id is not None: clauses.append("sm.course_id = ?"); params.append(course_id)
    if course_code: clauses.append("c.course_code LIKE ? COLLATE NOCASE"); params.append(f"%{course_code.strip()[:80]}%")
    if exam_type: clauses.append("sm.exam_type = ?"); params.append(exam_type)
    if topic: clauses.append("sm.topic LIKE ? COLLATE NOCASE"); params.append(f"%{topic.strip()[:120]}%")
    own = conn is None; conn = conn or get_db_connection()
    try:
        sql = ("SELECT COUNT(*) FROM study_materials sm JOIN courses c ON sm.course_id=c.id JOIN departments d ON c.department_id=d.id JOIN users u ON sm.uploaded_by=u.id WHERE " + " AND ".join(clauses))
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        if own: conn.close()


# ---------------------------------------------------------------------------
# Bookmark Data Access Functions (Step 12)
# ---------------------------------------------------------------------------

def add_bookmark(user_id: int, material_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
    # Adds a bookmark only for an existing approved material."
    own = conn is None
    conn = conn or get_db_connection()
    try:
        material = conn.execute("SELECT id FROM study_materials WHERE id = ? AND status = 'approved'", (material_id,)).fetchone()
        if not material:
            return False
        conn.execute("INSERT OR IGNORE INTO bookmarks (user_id, material_id) VALUES (?, ?)", (user_id, material_id))
        conn.commit()
        return True
    finally:
        if own: conn.close()


def remove_bookmark(user_id: int, material_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
    # Removes only the current user's bookmark; repeated removal is safe."
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cur = conn.execute("DELETE FROM bookmarks WHERE user_id = ? AND material_id = ?", (user_id, material_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if own: conn.close()


def is_material_bookmarked(user_id: int, material_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute("SELECT 1 FROM bookmarks WHERE user_id = ? AND material_id = ?", (user_id, material_id)).fetchone() is not None
    finally:
        if own: conn.close()


def get_bookmarked_material_ids(user_id: int, material_ids: List[int], conn: Optional[sqlite3.Connection] = None) -> set:
    # Batch bookmark lookup to avoid an N+1 query pattern.
    if not material_ids: return set()
    own = conn is None
    conn = conn or get_db_connection()
    try:
        placeholders = ",".join("?" for _ in material_ids)
        rows = conn.execute(f"SELECT material_id FROM bookmarks WHERE user_id = ? AND material_id IN ({placeholders})", [user_id, *material_ids]).fetchall()
        return {row["material_id"] for row in rows}
    finally:
        if own: conn.close()


def get_user_bookmarks(user_id: int, query_text: str = "", department_id: Optional[int] = None,
                       course_id: Optional[int] = None, course_code: str = "", exam_type: str = "",
                       topic: str = "", sort: str = "recent", page: int = 1,
                       per_page: int = 20, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    # Returns only approved materials bookmarked by the specified user.
    allowed = {"recent", "oldest", "material_newest", "material_oldest", "title_asc", "title_desc"}
    if exam_type and exam_type not in ("midterm", "final", "both"): raise ValueError("Invalid exam type.")
    if sort not in allowed: raise ValueError("Invalid bookmark sort.")
    page = max(int(page or 1), 1); per_page = min(max(int(per_page or 20), 1), 100)
    clauses = ["b.user_id = ?", "sm.status = 'approved'"]; params: List[Any] = [user_id]
    clean = (query_text or "").strip()[:120]
    if clean:
        pattern = f"%{clean}%"; clauses.append("(sm.topic LIKE ? COLLATE NOCASE OR c.course_name LIKE ? COLLATE NOCASE OR c.course_code LIKE ? COLLATE NOCASE OR d.code LIKE ? COLLATE NOCASE)"); params.extend([pattern] * 4)
    if department_id is not None: clauses.append("c.department_id = ?"); params.append(department_id)
    if course_id is not None: clauses.append("sm.course_id = ?"); params.append(course_id)
    if course_code: clauses.append("c.course_code LIKE ? COLLATE NOCASE"); params.append(f"%{course_code.strip()[:80]}%")
    if exam_type: clauses.append("sm.exam_type = ?"); params.append(exam_type)
    if topic: clauses.append("sm.topic LIKE ? COLLATE NOCASE"); params.append(f"%{topic.strip()[:120]}%")
    order = {"recent": "b.created_at DESC, b.id DESC", "oldest": "b.created_at ASC, b.id ASC", "material_newest": "sm.created_at DESC, sm.id DESC", "material_oldest": "sm.created_at ASC, sm.id ASC", "title_asc": "sm.topic COLLATE NOCASE ASC, sm.id DESC", "title_desc": "sm.topic COLLATE NOCASE DESC, sm.id DESC"}[sort]
    params.extend([per_page, (page - 1) * per_page]); own = conn is None; conn = conn or get_db_connection()
    try:
        sql = "SELECT b.id AS bookmark_id, b.created_at AS bookmarked_at, sm.id, sm.course_id, sm.topic, sm.exam_type, sm.file_path, sm.uploaded_by, sm.status, sm.created_at, c.course_name, c.course_code, d.name AS department_name, d.code AS department_code, u.name AS uploader_name FROM bookmarks b JOIN study_materials sm ON b.material_id=sm.id JOIN courses c ON sm.course_id=c.id JOIN departments d ON c.department_id=d.id JOIN users u ON sm.uploaded_by=u.id WHERE " + " AND ".join(clauses) + " ORDER BY " + order + " LIMIT ? OFFSET ?"
        return conn.execute(sql, params).fetchall()
    finally:
        if own: conn.close()


def count_user_bookmarks(user_id: int, query_text: str = "", department_id: Optional[int] = None, course_id: Optional[int] = None, course_code: str = "", exam_type: str = "", topic: str = "", conn: Optional[sqlite3.Connection] = None) -> int:
    rows = get_user_bookmarks(user_id, query_text, department_id, course_id, course_code, exam_type, topic, "recent", 1, 100000, conn)
    return len(rows)


# ---------------------------------------------------------------------------
# Student Dashboard & Learning Progress (Step 13)
# ---------------------------------------------------------------------------

def get_student_dashboard_stats(user_id: int, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    # Return aggregate dashboard statistics scoped to one authenticated user."
    own = conn is None
    conn = conn or get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM study_materials WHERE uploaded_by = :user_id) AS materials_count,
                (SELECT COUNT(*) FROM bookmarks b JOIN study_materials sm ON sm.id = b.material_id
                 WHERE b.user_id = :user_id AND sm.status = 'approved') AS bookmarks_count,
                (SELECT COUNT(*) FROM quizzes WHERE created_by = :user_id) AS quizzes_count,
                (SELECT COUNT(*) FROM quiz_attempts WHERE user_id = :user_id) AS attempts_count,
                COALESCE((SELECT ROUND(AVG(percentage), 2) FROM quiz_attempts WHERE user_id = :user_id), 0) AS average_score,
                COALESCE((SELECT MAX(percentage) FROM quiz_attempts WHERE user_id = :user_id), 0) AS highest_score,
                COALESCE((SELECT MIN(percentage) FROM quiz_attempts WHERE user_id = :user_id), 0) AS lowest_score,
                (SELECT COUNT(DISTINCT quiz_id) FROM quiz_attempts WHERE user_id = :user_id) AS completed_quizzes
            """, {"user_id": user_id}
        ).fetchone()
        return dict(row)
    finally:
        if own:
            conn.close()


def get_student_course_progress(user_id: int, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    # Aggregate materials, quizzes, attempts, and scores by the student's courses."
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute(
            """
            WITH material_counts AS (
                SELECT course_id, COUNT(*) AS materials_count
                FROM study_materials WHERE uploaded_by = :user_id GROUP BY course_id
            ), quiz_counts AS (
                SELECT sm.course_id, COUNT(*) AS quizzes_count
                FROM quizzes q JOIN study_materials sm ON sm.id = q.material_id
                WHERE q.created_by = :user_id GROUP BY sm.course_id
            ), attempt_stats AS (
                SELECT sm.course_id, COUNT(a.id) AS attempts_count,
                       ROUND(AVG(a.percentage), 2) AS average_score
                FROM quiz_attempts a JOIN quizzes q ON q.id = a.quiz_id
                JOIN study_materials sm ON sm.id = q.material_id
                WHERE a.user_id = :user_id GROUP BY sm.course_id
            )
            SELECT c.id, c.course_name, c.course_code,
                   COALESCE(mc.materials_count, 0) AS materials_count,
                   COALESCE(qc.quizzes_count, 0) AS quizzes_count,
                   COALESCE(ast.attempts_count, 0) AS attempts_count,
                   COALESCE(ast.average_score, 0) AS average_score
            FROM courses c
            LEFT JOIN material_counts mc ON mc.course_id = c.id
            LEFT JOIN quiz_counts qc ON qc.course_id = c.id
            LEFT JOIN attempt_stats ast ON ast.course_id = c.id
            WHERE mc.course_id IS NOT NULL OR qc.course_id IS NOT NULL OR ast.course_id IS NOT NULL
            ORDER BY c.course_code COLLATE NOCASE
            """, {"user_id": user_id}
        ).fetchall()
    finally:
        if own:
            conn.close()


def get_recent_student_materials(user_id: int, limit: int = 5, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        limit = min(max(int(limit), 1), 20)
        return conn.execute(
            """
            SELECT sm.*, c.course_name, c.course_code, d.code AS department_code
            FROM study_materials sm JOIN courses c ON c.id = sm.course_id
            JOIN departments d ON d.id = c.department_id
            WHERE sm.uploaded_by = ? ORDER BY sm.created_at DESC, sm.id DESC LIMIT ?
            """, (user_id, limit)
        ).fetchall()
    finally:
        if own:
            conn.close()


def get_recent_student_bookmarks(user_id: int, limit: int = 5, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        limit = min(max(int(limit), 1), 20)
        return conn.execute(
            """
            SELECT b.created_at AS bookmarked_at, sm.id, sm.topic, sm.exam_type,
                   c.course_name, c.course_code
            FROM bookmarks b JOIN study_materials sm ON sm.id = b.material_id
            JOIN courses c ON c.id = sm.course_id
            WHERE b.user_id = ? AND sm.status = 'approved'
            ORDER BY b.created_at DESC, b.id DESC LIMIT ?
            """, (user_id, limit)
        ).fetchall()
    finally:
        if own:
            conn.close()


def get_recent_student_quizzes(user_id: int, limit: int = 5, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        limit = min(max(int(limit), 1), 20)
        return conn.execute(
            """
            SELECT q.id, q.title, q.question_count, q.difficulty, q.created_at,
                   sm.id AS material_id, sm.topic, c.course_code,
                   MAX(a.id) AS attempt_id, MAX(a.percentage) AS latest_score
            FROM quizzes q JOIN study_materials sm ON sm.id = q.material_id
            JOIN courses c ON c.id = sm.course_id
            LEFT JOIN quiz_attempts a ON a.quiz_id = q.id AND a.user_id = ?
            WHERE q.created_by = ? GROUP BY q.id
            ORDER BY q.created_at DESC, q.id DESC LIMIT ?
            """, (user_id, user_id, limit)
        ).fetchall()
    finally:
        if own:
            conn.close()


# ---------------------------------------------------------------------------
# In-app Notifications (Step 14)
# ---------------------------------------------------------------------------

NOTIFICATION_TYPES = {"material_approved", "material_rejected", "quiz_completed", "new_material"}


def create_notification(user_id: int, notification_type: str, title: str, message: str, link: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> int:
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError("Invalid notification type.")
    if link is not None and (not link.startswith("/") or link.startswith("//")):
        raise ValueError("Notification links must be internal paths.")
    own = conn is None
    conn = conn or get_db_connection()
    try:
        clean_title = str(title).strip()
        clean_message = str(message).strip()
        existing = conn.execute(
            "SELECT id FROM notifications WHERE user_id = :user_id AND type = :type AND title = :title AND message = :message AND link IS :link LIMIT 1",
            {"user_id": user_id, "type": notification_type, "title": clean_title, "message": clean_message, "link": link},
        ).fetchone()
        if existing:
            return existing["id"]
        cursor = conn.execute(
            "INSERT INTO notifications (user_id, type, title, message, link) VALUES (:user_id, :type, :title, :message, :link)",
            {"user_id": user_id, "type": notification_type, "title": clean_title, "message": clean_message, "link": link},
        )
        if own:
            conn.commit()
        return cursor.lastrowid
    finally:
        if own:
            conn.close()


def get_user_notifications(user_id: int, page: int = 1, per_page: int = 20, notification_type: str = "", read_filter: str = "", conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
    if notification_type and notification_type not in NOTIFICATION_TYPES:
        raise ValueError("Invalid notification type filter.")
    if read_filter and read_filter not in ("read", "unread"):
        raise ValueError("Invalid notification read filter.")
    page = int(page)
    per_page = min(max(int(per_page), 1), 50)
    if page < 1:
        raise ValueError("Invalid notification page.")
    clauses = ["user_id = ?"]
    params: List[Any] = [user_id]
    if notification_type:
        clauses.append("type = ?"); params.append(notification_type)
    if read_filter:
        clauses.append("is_read = ?"); params.append(1 if read_filter == "read" else 0)
    params.extend([per_page, (page - 1) * per_page])
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute("SELECT * FROM notifications WHERE " + " AND ".join(clauses) + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", params).fetchall()
    finally:
        if own:
            conn.close()


def count_user_notifications(user_id: int, notification_type: str = "", read_filter: str = "", conn: Optional[sqlite3.Connection] = None) -> int:
    clauses = ["user_id = ?"]
    params: List[Any] = [user_id]
    if notification_type:
        if notification_type not in NOTIFICATION_TYPES: raise ValueError("Invalid notification type filter.")
        clauses.append("type = ?"); params.append(notification_type)
    if read_filter:
        if read_filter not in ("read", "unread"): raise ValueError("Invalid notification read filter.")
        clauses.append("is_read = ?"); params.append(1 if read_filter == "read" else 0)
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM notifications WHERE " + " AND ".join(clauses), params).fetchone()[0]
    finally:
        if own: conn.close()


def count_unread_notifications(user_id: int, conn: Optional[sqlite3.Connection] = None) -> int:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)).fetchone()[0]
    finally:
        if own: conn.close()


def mark_notification_as_read(user_id: int, notification_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cursor = conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, user_id))
        if own: conn.commit()
        return cursor.rowcount > 0
    finally:
        if own: conn.close()


def mark_all_notifications_as_read(user_id: int, conn: Optional[sqlite3.Connection] = None) -> int:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        cursor = conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
        if own: conn.commit()
        return cursor.rowcount
    finally:
        if own: conn.close()


def get_notification_for_user(notification_id: int, user_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[sqlite3.Row]:
    own = conn is None
    conn = conn or get_db_connection()
    try:
        return conn.execute("SELECT * FROM notifications WHERE id = ? AND user_id = ?", (notification_id, user_id)).fetchone()
    finally:
        if own: conn.close()
