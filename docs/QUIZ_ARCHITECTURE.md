# Quiz Architecture (NeuralForge StudyMate)

This document records the **two quiz subsystems** that currently coexist in the
project. Both are intentionally preserved in Step 14.5 — nothing here should be
removed or merged without a dedicated migration step.

## 1. Legacy quiz system (Step 10)

The original, single-material quiz flow. It reads one approved PDF directly
(no RAG) and scores submissions inline.

| Concern | Route | Notes |
|---|---|---|
| Create form | `GET /quiz/create/<material_id>` → `quiz_create.html` | HTML form |
| Generate | `POST /quiz/generate/<material_id>` | calls `generate_quiz_questions()` |
| Take | `GET /quiz/<quiz_id>` → `quiz.html` | strips answer keys before render |
| Submit | `POST /quiz/<quiz_id>/submit` | scored in-route |
| Result | `GET /quiz/<quiz_id>/result/<attempt_id>` → `quiz_result.html` | |

- Database tables: `quizzes`, `quiz_questions`, `quiz_attempts`.
- Generation source: the raw extracted text of a single approved material.
- Entry points in the UI: the **"Generate Quiz"** button on
  `/my-study-materials`.
- Tests: `test_quiz_step10.py`.

## 2. Generated quiz system (Steps 12–14)

The RAG-backed MCQ generator with server-side attempts and analytics.

| Concern | Route | Notes |
|---|---|---|
| Create form | `GET /quiz/create` → `quiz_create_ai.html` | course + topic driven |
| Generate | `POST /api/quizzes/generate` | RAG retrieval + `generate_quiz_from_context()` |
| Preview | `GET /quiz/view/<quiz_id>` → `quiz_preview.html` | ownership-scoped |
| Take | `GET /quiz/take/<quiz_id>` → `quiz_take.html` | never sends answer keys |
| Submit | `POST /api/quizzes/<quiz_id>/submit` | server-side scoring only |
| Result | `GET /quiz/result/<attempt_id>` → `quiz_attempt_result.html` | |
| History | `GET /quiz/attempts` → `quiz_attempts.html` | |
| Performance | `GET /quiz/performance` and `GET /api/quiz/performance` | |

- Database tables: `generated_quizzes`, `generated_quiz_questions`,
  `generated_quiz_attempts`, `generated_quiz_attempt_answers`,
  `generated_quiz_sources`.
- Generation source: **RAG-retrieved, approved-only** context
  (`services/rag_service.py`).
- Entry points in the UI: the **"AI Quiz Generator"** link in the navbar and the
  **"Generate Quiz"** button on `/study-library`.
- Tests: `test_quiz_generation_step12.py`, `test_quiz_attempt_step13.py`,
  `test_quiz_performance_step14.py`.

## 3. Which system owns what (as of Step 14.5)

| Capability | System used |
|---|---|
| Quiz generation from the Study Library / navbar | **Generated** |
| Quiz generation from "My Materials" | **Legacy** |
| Quiz attempts & scoring | **Generated** |
| Quiz history (`/quiz/attempts`) | **Generated** |
| Performance analytics (`/quiz/performance`) | **Generated** |
| Notifications on quiz completion | **Generated** (in-app) and **Legacy** (`quiz_submit`) |

## 4. Step 14.5 stance

- Both systems remain live and fully tested.
- No routes were removed, renamed, or merged.
- New features (notifications, bookmarks, analytics, dashboard) build on the
  **Generated** system.
- A future step may retire the legacy system, but that requires an explicit
  migration of existing `quiz_attempts` data and is out of scope for Step 14.5.
