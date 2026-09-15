# NeuralForge StudyMate
An AI-powered study assistant for students. Upload study PDFs, generate AI
summaries, ask grounded questions about approved study materials, generate and
take quizzes that are scored on the server, and track your performance over
time.

> This README describes the project **as it is actually implemented today**,
> not an aspirational roadmap. Anything not implemented is called out explicitly
> in the limitations section.

---

## Project purpose
StudyMate helps students turn raw lecture notes, slides, and article excerpts
into structured study material. Every AI answer and quiz is grounded in
**approved** study materials only, so the assistant never invents facts from
unrelated sources.

---

## Main features
- **PDF upload & text extraction** — upload a PDF (max 16 MB, PDF signature
  verified) and extract its text with `pypdf`.
- **AI summaries** — generate a structured Markdown study summary from extracted
  text using the OpenAI API.
- **Study Notes Library** — a public, searchable library of **approved** study
  materials with filters (department, course, exam type, topic, course code) and
  sorting.
- **Admin approval workflow** — students upload materials as `pending`; an admin
  reviews and either approves or rejects them. Only approved materials become
  public and available to AI features.
- **Ask StudyMate (RAG Q&A)** — ask a question and get an answer grounded in
  approved materials, with source references back to the library.
- **AI Quiz Generator** — generate multiple-choice quizzes from approved
  materials for a chosen course/topic.
- **Quiz Attempt + server-side scoring** — quizzes are taken in the browser but
  always scored on the server; answer keys are never sent to the client before
  submission.
- **Quiz history** — browse your previously submitted attempts.
- **Performance analytics** — overview, per-quiz, per-course, per-topic and
  recent performance metrics.
- **Notifications** — in-app notifications for material approvals/rejections and
  quiz completion, with read/unread state.
- **Bookmarks** — bookmark approved materials and browse them from a personal
  page.
- **Student dashboard** — a personal overview of counts, course progress, recent
  materials, bookmarks, and quizzes.

---

## AI features
- **AI summary** (`POST /summarize`) — structured Markdown summary of a document.
- **Grounded Q&A** (`POST /api/ask-studymate`) — answers only from retrieved,
  approved document context.
- **AI quiz generation** (`POST /api/quizzes/generate`) — validated MCQ quizzes
  generated from retrieved, approved context.
- **Legacy quiz generation** (`POST /quiz/generate/<material_id>`) — quiz built
  directly from a single approved material (kept for backward compatibility).

All document text is treated as **untrusted data**. Prompts explicitly instruct
the model to ignore any instructions embedded in uploaded documents.

---

## Retrieval-Augmented Generation (RAG)

The RAG pipeline is **keyword-based** (no embeddings):

1. The uploaded document's text is split into overlapping chunks and stored in
   the `material_chunks` table.
2. A question or quiz topic is preprocessed into significant terms.
3. Chunks are scored by keyword/phrase overlap and ranked.
4. Only chunks belonging to **approved** materials are eligible (enforced in SQL).
5. A bounded context string is assembled and passed to the model.

> Semantics/embeddings retrieval and a vector database are **not** implemented.
> The retrieval interface is intentionally stable so a future embeddings backend
> can replace the scoring internals without changing the API.

---

## Tech stack
- **Backend:** Python 3 + Flask
- **Frontend:** HTML + Tailwind CSS (CDN) + vanilla JavaScript
- **AI:** OpenAI API (`openai` Python SDK)
- **PDF extraction:** `pypdf`
- **Database:** SQLite (stdlib `sqlite3`)
- **Auth/security:** Werkzeug password hashing, session cookies, CSRF tokens,
  per-IP rate limiting
Dependencies (`requirements.txt`): `flask`, `python-dotenv`, `pypdf`, `openai`.

---

## Project structure
```
NeuralForge-StudyMate/
├── app.py                      # Flask app: routes, CSRF, rate limiting, errors
├── database/
│   ├── db.py                   # SQLite data-access layer
│   └── schema.sql              # Base schema
├── services/
│   ├── ai_service.py           # OpenAI summary, Q&A, quiz generation
│   ├── auth_service.py         # Registration, login, decorators
│   ├── rag_service.py          # Chunking, retrieval, context building
│   ├── pdf_processor.py        # PDF text extraction
│   └── notification_service.py # In-app notifications
├── templates/                  # Jinja2 templates (Tailwind UI)
├── static/                     # CSS/JS/images
├── uploads/                    # Stored PDFs (created at runtime, gitignored)
├── docs/QUIZ_ARCHITECTURE.md   # Legacy vs generated quiz systems
├── test_*.py                   # Step-by-step regression suites
└── requirements.txt
```

---

## Local setup
### 1. Virtual environment
```powershell
python -m venv venv
.\venv\Scripts\activate
```

(On macOS/Linux: `python3 -m venv venv && source venv/bin/activate`.)

### 2. Install dependencies
```powershell
pip install -r requirements.txt
```

### 3. Configure `.env`

Copy `.env.example` to `.env` and fill in real values:

```
OPENAI_API_KEY=sk-...your-real-key...
SECRET_KEY=some-long-random-string
FLASK_ENV=development
SESSION_COOKIE_SECURE=0
CSRF_PROTECTION=1
LOG_LEVEL=INFO
```

`.env` is gitignored and must never be committed.

### 4. Run Flask locally
```powershell
python app.py
```

Then open http://127.0.0.1:5000. Debug mode is **off by default**; set
`FLASK_DEBUG=1` for local development only (never in production).

---

## Database initialization / migration

The database is initialized automatically on startup: `init_db()` creates all
required tables and performance indexes if they are missing, and default
departments/courses are seeded. There is no separate manual migration step for a
fresh database. Schema changes for existing databases are applied through the
idempotent `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` statements
in `database/db.py`.

---

## Test commands
Run every suite at once (recommended):

```powershell
python run_all_tests.py
```

Or run the regression suites individually (each file is a standalone suite):

```powershell
python -m py_compile app.py database/db.py
python test_database_step5.py
python test_auth_step6.py
python test_study_material_step7.py
python test_admin_step8.py
python test_public_library_step9.py
python test_ask_studymate_step10.py
python test_rag_step11.py
python test_quiz_generation_step12.py
python test_quiz_attempt_step13.py
python test_quiz_performance_step14.py
python test_bookmarks_step12.py
python test_notifications_step14.py
python test_dashboard_step13.py
python test_smart_search_step11.py
python test_security_step15.py
python test_hardening_step145.py
```

Some suites need `sample_study_guide.pdf` in the project root. Browser E2E QA
scripts (`browser_*_qa.mjs`) can be run with `node browser_<name>_qa.mjs`; they
spawn their own Flask server on a fixture port.

---

## GitHub usage
```powershell
git status
git add <files>
git commit -m "message"
git push
```

Ensure `.env`, `studymate.db`, and `uploads/` are never committed — they are
listed in `.gitignore`. Commit and push are manual steps; nothing is pushed
automatically.

---

## Deployment notes
- Run behind a production WSGI server (e.g. `waitress` or `gunicorn`), not
  `flask run` / `app.run`.
- Set `FLASK_ENV=production`, a strong `SECRET_KEY`, and
  `SESSION_COOKIE_SECURE=1` behind HTTPS.
- Debug must remain disabled (`FLASK_DEBUG` unset).

### SQLite / local uploads limitation
This project uses **SQLite** for storage and the **local filesystem** (`uploads/`)
for PDFs. This is fine for a single-instance prototype but is **not** suitable
for production multi-worker or multi-host deployment: SQLite does not scale for
concurrent writers, and local files do not exist across multiple instances. A
production deployment requires a persistent, shared database (e.g. PostgreSQL)
and object storage (e.g. S3) for uploads.

### AI API dependency
All AI features require a valid `OPENAI_API_KEY`. Without it, summary, Q&A, and
quiz-generation endpoints return safe, generic "service unavailable" errors.

---

## Security limitations
- **Malware scanning is NOT implemented.** Uploads are validated as PDFs by
  extension and magic signature only; there is no antivirus/content scanning.
  This is a known production limitation.
- **Rate limiting is in-memory and per-process.** It is sufficient for a single
  process prototype, but a multi-worker/multi-host production deployment needs a
  centralized limiter (e.g. Redis) so limits are enforced consistently.
- **RAG is keyword-based**, not semantic; retrieval quality is limited to lexical
  overlap.
- **CSRF** is enforced for all state-changing requests (form, multipart, and
  JSON), using a per-session token compared in constant time.
- **Authorization** revalidates the admin role against the database on every
  admin request rather than trusting the session copy.
- Error responses never expose stack traces, raw exceptions, SQL errors,
  filesystem paths, or API keys; details are logged server-side only.

---

## Current roadmap / not yet implemented
- **Step 15 — Weak Topic Detection** (not implemented).
- **Step 16 — Personalized Study Plan** (not implemented).
- Semantic/embeddings RAG and a vector database.
- Centralized (multi-worker) rate limiting.
- Malware scanning for uploads.
- Retirement/migration of the legacy single-material quiz system (both systems
  are preserved today; see `docs/QUIZ_ARCHITECTURE.md`).
