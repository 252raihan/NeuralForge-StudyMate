-- NeuralForge StudyMate Database Schema (Step 5)
-- SQLite Database supporting Departments, Courses, Users, Study Materials, and Admin Approval Workflow

PRAGMA foreign_keys = ON;

-- 1. DEPARTMENTS TABLE
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. COURSES TABLE
-- A Course belongs to a Department.
-- Enforce unique course_code within the same department.
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,
    course_code TEXT NOT NULL COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (department_id, course_code)
);

-- 3. USERS TABLE
-- Roles: 'student', 'admin'
-- Passwords must ALWAYS be stored as hashes. Never store API keys or plain passwords.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    department_id INTEGER,
    role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL ON UPDATE CASCADE
);

-- 4. STUDY MATERIALS TABLE
-- A Study Material belongs to a Course and is uploaded by a User.
-- Stores file_path reference (never stores PDF binary in database).
-- Status: 'pending' (default), 'approved', 'rejected'
-- Exam Type: 'midterm', 'final', 'both'
CREATE TABLE IF NOT EXISTS study_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    exam_type TEXT NOT NULL CHECK (exam_type IN ('midterm', 'final', 'both')),
    file_path TEXT NOT NULL,
    extracted_text TEXT,
    content_hash TEXT,
    uploaded_by INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- 4b. MATERIAL CHUNKS TABLE (Step 11 RAG)
-- Stores chunked extracted text for retrieval. Never stores PDF binary data.
CREATE TABLE IF NOT EXISTS material_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES study_materials(id) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE (material_id, chunk_index)
);

-- INDEXES FOR OPTIMAL QUERY PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_departments_code ON departments(code);
CREATE INDEX IF NOT EXISTS idx_courses_department_id ON courses(department_id);
CREATE INDEX IF NOT EXISTS idx_courses_course_code ON courses(course_code);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_department_id ON users(department_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_study_materials_course_id ON study_materials(course_id);
CREATE INDEX IF NOT EXISTS idx_study_materials_status ON study_materials(status);
CREATE INDEX IF NOT EXISTS idx_study_materials_exam_type ON study_materials(exam_type);
CREATE INDEX IF NOT EXISTS idx_study_materials_uploaded_by ON study_materials(uploaded_by);
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_materials_content_hash ON study_materials(content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_study_materials_course_status ON study_materials(course_id, status);
CREATE INDEX IF NOT EXISTS idx_material_chunks_material_id ON material_chunks(material_id);

-- 5. QUIZZES TABLE (Step 10)
CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    title TEXT NOT NULL,
    question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'short', 'mixed')),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard', 'mixed')),
    question_count INTEGER NOT NULL CHECK (question_count BETWEEN 1 AND 20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES study_materials(id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

-- Correct answers are stored server-side and never rendered in the quiz form.
CREATE TABLE IF NOT EXISTS quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'short')),
    question_text TEXT NOT NULL,
    options_json TEXT,
    correct_answer TEXT,
    expected_answer TEXT,
    explanation TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
    UNIQUE (quiz_id, position)
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    percentage REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS quiz_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    submitted_answer TEXT NOT NULL DEFAULT '',
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE RESTRICT,
    UNIQUE (attempt_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_quizzes_created_by ON quizzes(created_by);
CREATE INDEX IF NOT EXISTS idx_quizzes_material_id ON quizzes(material_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz_id ON quiz_questions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_id ON quiz_attempts(user_id);

-- 5b. AI QUIZ GENERATOR TABLES (Step 12)
-- A separate, RAG-driven quiz model generated from a course/topic/exam selection.
-- Attempt/submission logic (Step 13) will build on top of these tables.
CREATE TABLE IF NOT EXISTS generated_quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    exam_type TEXT NOT NULL CHECK (exam_type IN ('midterm', 'final', 'both')),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard', 'mixed')),
    question_count INTEGER NOT NULL CHECK (question_count BETWEEN 1 AND 20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT
);

-- Questions store the answer server-side; option columns keep it simple and queryable.
CREATE TABLE IF NOT EXISTS generated_quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_answer INTEGER NOT NULL CHECK (correct_answer BETWEEN 0 AND 3),
    explanation TEXT NOT NULL,
    question_order INTEGER NOT NULL,
    FOREIGN KEY (quiz_id) REFERENCES generated_quizzes(id) ON DELETE CASCADE,
    UNIQUE (quiz_id, question_order)
);

-- Traceability: which approved materials backed a generated quiz (no paths stored).
CREATE TABLE IF NOT EXISTS quiz_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    FOREIGN KEY (quiz_id) REFERENCES generated_quizzes(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES study_materials(id) ON DELETE RESTRICT,
    UNIQUE (quiz_id, material_id)
);

CREATE INDEX IF NOT EXISTS idx_generated_quizzes_user_id ON generated_quizzes(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_quizzes_course_id ON generated_quizzes(course_id);
CREATE INDEX IF NOT EXISTS idx_generated_quiz_questions_quiz_id ON generated_quiz_questions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sources_quiz_id ON quiz_sources(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sources_material_id ON quiz_sources(material_id);

-- 5c. QUIZ ATTEMPTS (Step 13)
-- A student's attempt at a generated quiz. Finalized server-side on submission.
CREATE TABLE IF NOT EXISTS generated_quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score INTEGER,
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER,
    wrong_answers INTEGER,
    percentage REAL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP,
    FOREIGN KEY (quiz_id) REFERENCES generated_quizzes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Per-question record of an attempt (supports Step 14 performance analysis).
CREATE TABLE IF NOT EXISTS generated_quiz_attempt_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    selected_answer INTEGER,
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    FOREIGN KEY (attempt_id) REFERENCES generated_quiz_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES generated_quiz_questions(id) ON DELETE CASCADE,
    UNIQUE (attempt_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_gen_attempts_user_id ON generated_quiz_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_gen_attempts_quiz_id ON generated_quiz_attempts(quiz_id);
CREATE INDEX IF NOT EXISTS idx_gen_attempts_user_submitted ON generated_quiz_attempts(user_id, submitted_at);
CREATE INDEX IF NOT EXISTS idx_gen_attempt_answers_attempt_id ON generated_quiz_attempt_answers(attempt_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_generated_attempt ON generated_quiz_attempts(quiz_id, user_id) WHERE submitted_at IS NULL;

-- 6. BOOKMARKS TABLE (Step 12)
CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES study_materials(id) ON DELETE CASCADE,
    UNIQUE (user_id, material_id)
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_material_id ON bookmarks(material_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_user_created ON bookmarks(user_id, created_at);

-- 7. IN-APP NOTIFICATIONS (Step 14)
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('material_approved', 'material_rejected', 'quiz_completed', 'new_material')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at);
