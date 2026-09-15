"""
NeuralForge StudyMate - Authentication Service (Step 6)
Handles user registration, authentication verification, session management,
and access control decorators (@login_required, @admin_required).
"""

import logging
import re
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from flask import session, redirect, url_for, flash, request, abort
from werkzeug.security import generate_password_hash, check_password_hash
logger = logging.getLogger("studymate")

from database.db import (
    get_user_by_email,
    get_user_by_id,
    create_user,
    get_department_by_id,
    get_all_departments,
)

# Email validation regex (standard RFC 5322 simplified pattern)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Password policy (Step 14.5 hardening).
# A reasonable minimum for a study-notes app: long enough to matter, without
# forcing awkward character-class rules that hurt usability.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128  # bound hashing work / reject absurd payloads
# A very short deny-list of the most trivially guessable passwords. Kept
# deliberately small so common-but-legitimate study passwords (e.g. those
# containing the word "password") are not rejected unnecessarily.
COMMON_WEAK_PASSWORDS = frozenset({
    "password", "12345678", "123456789", "qwertyuiop", "abcdefgh", "11111",
})


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    # Validate a raw password against the project password policy.
    # Returns (is_valid, error_message). Never stores or logs the password.
    if not password:
        return False, "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must be at most {MAX_PASSWORD_LENGTH} characters long."
    if password.strip() == "":
        return False, "Password cannot be only whitespace."
    if password.casefold() in COMMON_WEAK_PASSWORDS:
        return False, "That password is too common. Please choose a stronger one."
    return True, None


def validate_email_format(email: str) -> bool:
    """Checks if the given string matches a basic valid email address format."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def register_student(
    name: str,
    email: str,
    password: str,
    confirm_password: str,
    department_id: Any
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Registers a new student user.
    - Strictly forces role = 'student' (never permits admin).
    - Validates presence of all fields.
    - Validates email format.
    - Enforces password confirmation match.
    - Enforces the project password policy (see validate_password_strength).
    - Verifies department exists in the database.
    - Prevents duplicate email accounts (case-insensitive).
    - Uses Werkzeug generate_password_hash().

    Returns:
        (success: bool, error_message: Optional[str], user_id: Optional[int])
    """
    clean_name = (name or "").strip()
    clean_email = (email or "").strip().lower()

    # 1. Check required fields
    if not clean_name:
        return False, "Full Name is required.", None

    if not clean_email:
        return False, "Email address is required.", None

    if not validate_email_format(clean_email):
        return False, "Please enter a valid email address.", None

    password_ok, password_error = validate_password_strength(password)
    if not password_ok:
        return False, password_error, None
    if not confirm_password:
        return False, "Please confirm your password.", None
    if password != confirm_password:
        return False, "Passwords do not match.", None

    # 2. Validate department
    if not department_id:
        return False, "Please select your department.", None

    try:
        dept_id_int = int(department_id)
    except (ValueError, TypeError):
        return False, "Invalid department selected.", None

    dept = get_department_by_id(dept_id_int)
    if not dept:
        return False, "Selected department does not exist.", None

    # 3. Check for existing email
    existing_user = get_user_by_email(clean_email)
    if existing_user:
        return False, "An account with this email address already exists. Please log in.", None

    # 4. Hash password with Werkzeug (scrypt / pbkdf2 default)
    hashed_password = generate_password_hash(password)

    # 5. Insert user with strictly 'student' role
    try:
        new_user_id = create_user(
            name=clean_name,
            email=clean_email,
            password_hash=hashed_password,
            department_id=dept_id_int,
            role="student"
        )
        return True, None, new_user_id
    except Exception:
        # SECURITY: never surface raw exception text (may contain SQL/paths).
        logger.exception("Student registration failed for %s", clean_email)
        return False, "We could not create your account right now. Please try again later.", None


def authenticate_user(email: str, password: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validates user credentials.
    - Checks email existence.
    - Verifies password with check_password_hash().
    - Never reveals whether email or password specifically was incorrect.

    Returns:
        (success: bool, error_message: Optional[str], user_dict: Optional[dict])
    """
    clean_email = (email or "").strip().lower()

    if not clean_email or not password:
        return False, "Invalid email or password.", None

    user = get_user_by_email(clean_email)
    if not user:
        # Prevent user enumeration with generic error
        return False, "Invalid email or password.", None

    if not check_password_hash(user["password_hash"], password):
        return False, "Invalid email or password.", None

    user_data = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "department_id": user["department_id"]
    }
    return True, None, user_data


def login_session(user_data: Dict[str, Any]) -> None:
    """
    Establishes an authenticated session.
    Stores only minimal, non-sensitive session identifiers.
    Never stores passwords or password hashes.
    """
    session.clear()
    session["user_id"] = user_data["id"]
    session["user_name"] = user_data["name"]
    session["user_role"] = user_data["role"]
    session["user_email"] = user_data["email"]
    session.permanent = True


def logout_session() -> None:
    """Clears all session data to log out the user."""
    session.clear()


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Retrieves the currently logged-in user from the database based on session['user_id'].
    Returns None if not authenticated or user no longer exists.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None

    user_row = get_user_by_id(user_id)
    if not user_row:
        session.clear()
        return None

    return {
        "id": user_row["id"],
        "name": user_row["name"],
        "email": user_row["email"],
        "role": user_row["role"],
        "department_id": user_row["department_id"]
    }


def login_required(view_func):
    """
    Decorator that ensures the requesting user is authenticated.
    Redirects unauthenticated visitors to the login page.
    """
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return decorated_view


def admin_required(view_func):
    """
    Decorator that ensures the user is logged in AND has the 'admin' role.
    - If unauthenticated: redirects to login.
    - If authenticated but not admin: returns 403 Forbidden or redirects with warning.
    """
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("Administrator login required.", "warning")
            return redirect(url_for("login", next=request.path))

        # SECURITY: re-read the role from the LIVE database on every admin request.
        # A stale or forged session role must never grant admin access after a
        # role change; authorization never trusts the session copy.
        user_row = get_user_by_id(user_id)
        if not user_row or user_row["role"] != "admin":
            session.pop("user_role", None)
            flash("Access denied. Administrator privileges required.", "error")
            return abort(403)

        return view_func(*args, **kwargs)
    return decorated_view
