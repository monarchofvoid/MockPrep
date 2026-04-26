# MockPrep — Exam Mock Test Platform

> Real exam environment · Deep per-question analytics · Solution review dashboard

A full-stack mock test platform built with **FastAPI + React**, covering all 5 modules from the product spec:
Module A (Question Bank) → B (Test Engine) → C (Response Tracking) → D (Evaluation) → E (Analytics Dashboard).

---

## Project Structure

```
mock-platform/
├── backend/
│   ├── main.py                  # FastAPI app — all routes
│   ├── models.py                # SQLAlchemy ORM (Users, MockTests, Attempts, Responses)
│   ├── schemas.py               # Pydantic request/response models
│   ├── database.py              # DB engine + session factory
│   ├── seed.py                  # One-time DB seed script
│   ├── requirements.txt
│   ├── .env.example
│   └── services/
│       ├── evaluation.py        # Module D — scoring + topic analysis
│       └── analytics.py         # Module E — cross-attempt user analytics
│
├── question_bank/               # Module A — JSON question banks
│   ├── dbms/
│   │   └── pyq_2021.json
│   └── os/
│       └── pyq_2022.json
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    ├── .env.example
    └── src/
        ├── main.jsx
        ├── App.jsx                  # Screen router (Home → Test → Results)
        ├── api/
        │   └── client.js            # All fetch calls to FastAPI
        ├── components/
        │   ├── Home.jsx             # Paper selection screen
        │   ├── Timer.jsx            # Countdown with warning/critical states
        │   ├── QuestionPalette.jsx  # Sidebar palette (5 colour states)
        │   ├── TestEngine.jsx       # Core exam interface + submit modal
        │   └── ResultsDashboard.jsx # Score, topic analysis, solution review
        └── styles/
            ├── global.css
            ├── Home.module.css
            ├── Timer.module.css
            ├── QuestionPalette.module.css
            ├── TestEngine.module.css
            └── ResultsDashboard.module.css
```

---

## Quick Start

### 1 — Backend

```bash
cd mock-platform/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env              # Edit if needed (defaults work for SQLite)

# Seed the database (creates guest user + registers papers)
python seed.py

# Start the API server
uvicorn main:app --reload --port 8000
```

API docs available at: **http://localhost:8000/docs**

---

### 2 — Frontend

```bash
cd mock-platform/frontend

# Install dependencies
npm install

# Set up environment
cp .env.example .env              # VITE_API_URL=http://localhost:8000

# Start dev server
npm run dev
```

Open: **http://localhost:5173**

---

## API Reference

| Method | Endpoint                  | Description                                    |
|--------|---------------------------|------------------------------------------------|
| GET    | `/mocks`                  | List all available papers                      |
| GET    | `/mocks/{id}`             | Get paper metadata                             |
| POST   | `/start-attempt`          | Create test session, return questions (no answers) |
| POST   | `/submit-attempt`         | Submit responses → evaluate → save → return results |
| GET    | `/results/{attempt_id}`   | Retrieve saved results for a past attempt      |
| GET    | `/analytics/{user_id}`    | Aggregated cross-attempt performance           |
| GET    | `/users/{id}/attempts`    | All attempts by a user                         |
| POST   | `/users`                  | Register a new user                            |

---

## Database Schema

```
users           id, name, email, created_at
mock_tests      id (str), exam, subject, year, duration_minutes, total_marks, question_count, json_file_path
attempts        id, user_id, mock_id, score, accuracy, attempt_rate, time_taken_seconds, submitted_at
responses       id, attempt_id, question_id, selected_option, is_correct, marks_awarded,
                time_spent_seconds, visit_count, answer_changed_count, was_marked_for_review,
                topic, difficulty
```

---

## Adding New Papers

1. Create the JSON file following this schema:

```json
{
  "exam": "GATE",
  "subject": "Computer Networks",
  "year": "2023",
  "duration": 30,
  "total_marks": 15,
  "questions": [
    {
      "id": 1,
      "type": "mcq",
      "question": "...",
      "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
      "correct": "B",
      "explanation": "...",
      "difficulty": "easy|medium|hard",
      "topic": "...",
      "marks": 1,
      "negative_marking": 0.33
    }
  ]
}
```

2. Place it in `question_bank/<subject>/filename.json`

3. Add an entry to the `seed_mock_tests` list in `backend/main.py` (or insert directly into the `mock_tests` table).

---

## Per-Question Tracking (Module C)

Every question in the test session tracks:

| Field                  | Meaning                                      |
|------------------------|----------------------------------------------|
| `selectedOption`       | Current answer: A / B / C / D / null        |
| `timeSpentSeconds`     | Cumulative time (re-accumulated on revisit)  |
| `visitCount`           | How many times the user opened this question |
| `answerChangedCount`   | Number of times the answer was changed       |
| `markedForReview`      | Whether the question was flagged             |

This data is sent to `/submit-attempt` and stored in the `responses` table.

---

## Evaluation Engine (Module D)

`services/evaluation.py` computes on submit:

- **Score** = Σ (marks for correct) − Σ (negative marking for wrong), floored at 0
- **Accuracy** = correct / attempted × 100
- **Attempt Rate** = attempted / total × 100
- **Avg time / question** = time_taken / attempted
- **Topic performance** = per-topic correct/total/accuracy
- **Per-question review** = your answer, correct answer, explanation, time, visits, changes

---

## Phase 2 Roadmap

### Analytics Upgrades
- [ ] Question-level time bar chart (already in ResultsDashboard — connect to real data)
- [ ] Score trend line across attempts (use `/users/{id}/attempts`)
- [ ] Difficulty-wise breakdown (easy/medium/hard accuracy)

### Phase 3 — User History
- [ ] Auth (JWT or OAuth2) — replace the hardcoded `GUEST_USER_ID=1`
- [ ] Past attempts listing page
- [ ] Progress graphs across sessions

### Phase 4 — AI Features
- [ ] Personalized weak-topic mock generation (filter question bank by topic)
- [ ] AI explanation enhancement (call Claude API on wrong answers)
- [ ] Adaptive difficulty (track rolling accuracy, adjust question pool)
- [ ] Predicted exam score (regression on historical attempt data)

---

## Deployment

### Backend (Render / Railway / EC2)
```bash
# Production: switch DATABASE_URL to PostgreSQL
# Run migrations (or let SQLAlchemy create tables on startup)
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend (Vercel / Netlify)
```bash
npm run build
# Set VITE_API_URL to your deployed backend URL
```

---

## Tech Stack

| Layer       | Technology                             |
|-------------|----------------------------------------|
| Frontend    | React 18 + Vite + CSS Modules          |
| Backend     | FastAPI + Uvicorn                      |
| ORM         | SQLAlchemy 2.0                         |
| Validation  | Pydantic v2                            |
| Database    | SQLite (dev) → PostgreSQL (prod)       |
| Question DB | JSON files (→ DB migration in Phase 2) |
| Deploy      | Vercel (frontend) + Render (backend)   |
