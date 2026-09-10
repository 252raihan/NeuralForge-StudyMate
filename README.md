# NeuralForge StudyMate 🚀

An AI-powered study assistant for students: upload study PDFs, get summaries,
ask questions about your materials, take generated quizzes, track weak topics,
and receive a personalized study plan.

## Tech Stack

- **Backend:** Python + Flask
- **Frontend:** HTML/CSS/JS + Tailwind CSS
- **AI:** OpenAI API (key stored in `.env`)
- **PDF extraction:** pypdf (added in a later step)
- **Database:** SQLite (added in a later step)

## Setup

1. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your real API key.
4. Run the server:
   ```powershell
   python app.py
   ```
5. Open http://127.0.0.1:5000 in your browser.

## Status

- [x] Step 1: Project skeleton
- [ ] Step 2: Frontend skeleton
- [ ] Step 3: Database
- [ ] Step 4: Authentication
- [ ] Step 5: PDF upload + text extraction
- [ ] Step 6: AI summaries
- [ ] Step 7: Q&A chat
- [ ] Step 8: MCQ quiz generation
- [ ] Step 9: Performance dashboard
- [ ] Step 10: Personalized study plan
- [ ] Step 11: Polish + deploy
