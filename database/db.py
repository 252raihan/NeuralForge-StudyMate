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
            VALUES (?, ?, ?)
            """,
            (department_id, course_name.strip(), course_code.strip())
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
        conn.commit()
        return cursor.lastrowid
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
            "UPDATE study_materials SET status = ? WHERE id = ?",
            (new_status, material_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        if close_on_exit:
            conn.close()
