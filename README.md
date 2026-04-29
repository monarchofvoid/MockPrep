# VYAS — Virtual Yield Assessment System

> A full-stack competitive exam mock test platform with JWT authentication,
> timed test engine, automated evaluation, and analytics dashboard.

---

## Stack

| Layer      | Technology              |
|------------|-------------------------|
| Frontend   | React 18 + Vite         |
| Routing    | react-router-dom v6     |
| Auth       | JWT (Bearer tokens)     |
| Backend    | FastAPI + SQLAlchemy    |
| Database   | SQLite (dev) / PostgreSQL (prod) |
| Deploy FE  | Vercel                  |
| Deploy BE  | Render / Railway        |

---

## Local Development

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set SECRET_KEY to a long random string

uvicorn main:app --reload --port 8000
```

API available at: http://localhost:8000  
Swagger docs at:  http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install

cp .env.example .env.local
# Edit .env.local — set VITE_API_URL=http://localhost:8000

npm run dev
```

App available at: http://localhost:5173

---

## Project Structure

```
vyas/
├── backend/
│   ├── main.py              # FastAPI app + all routes
│   ├── auth.py              # JWT + bcrypt helpers
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── database.py          # DB engine + session dependency
│   ├── services/
│   │   ├── evaluation.py    # Scoring engine (Module D)
│   │   └── analytics.py     # Analytics aggregation (Module E)
│   ├── requirements.txt
│   ├── .env.example
│   └── render.yaml
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx          # Router + AuthProvider
│   │   ├── api/
│   │   │   └── client.js    # All API calls + token management
│   │   ├── context/
│   │   │   └── AuthContext.jsx
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   └── ProtectedRoute.jsx
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx   # Public: login + signup modal
│   │   │   ├── Dashboard.jsx     # Analytics overview
│   │   │   ├── MockBrowser.jsx   # Paper catalogue
│   │   │   ├── TestPage.jsx      # Exam engine + palette
│   │   │   └── ResultsPage.jsx   # Results + question review
│   │   └── styles/               # CSS Modules per page
│   ├── index.html
│   ├── vite.config.js
│   ├── vercel.json
│   └── package.json
└── question_bank/
    ├── dbms/
    │   └── pyq_2021.json
    └── os/
        └── pyq_2022.json
```

---

## Auth Flow

```
User visits /         → LandingPage (public)
  ↓ signup / login
POST /auth/signup or /auth/login
  ↓ returns { access_token, user }
Stored in localStorage (vyas_token, vyas_user)
  ↓
All subsequent API calls include Authorization: Bearer <token>
  ↓
Protected routes guarded by <ProtectedRoute>
401 response → auto-logout + redirect to /
```

---

## API Endpoints

| Method | Path                  | Auth | Description                       |
|--------|-----------------------|------|-----------------------------------|
| POST   | /auth/signup          | No   | Register + get token              |
| POST   | /auth/login           | No   | Login + get token                 |
| GET    | /auth/me              | Yes  | Current user profile              |
| GET    | /mocks                | Yes  | List all mock tests               |
| POST   | /start-attempt        | Yes  | Begin test session                |
| POST   | /submit-attempt       | Yes  | Submit + evaluate answers         |
| GET    | /results/{attempt_id} | Yes  | Get results for an attempt        |
| GET    | /analytics/me         | Yes  | Aggregated user analytics         |
| GET    | /users/me/attempts    | Yes  | All attempts list                 |

---

## Deployment

### Backend (Render)

1. Push repo to GitHub
2. Create new **Web Service** on Render, point to `backend/`
3. Set environment variables (see `render.yaml`)
4. Add a free **PostgreSQL** database and link via `DATABASE_URL`
5. Deploy — Render auto-runs `uvicorn main:app`

### Frontend (Vercel)

1. Import frontend directory into Vercel
2. Set **Root Directory** to `frontend`
3. Add environment variable: `VITE_API_URL=https://your-api.onrender.com`
4. Deploy — `vercel.json` handles SPA routing

---

## Adding More Question Banks

1. Create a JSON file in `question_bank/<subject>/` following the schema:
```json
{
  "meta": { "exam": "GATE", "subject": "...", "year": "...", ... },
  "questions": [
    {
      "id": 1,
      "type": "MCQ",
      "question": "...",
      "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
      "correct": "A",
      "explanation": "...",
      "difficulty": "Easy|Medium|Hard",
      "topic": "...",
      "marks": 1,
      "negative_marking": 0.33
    }
  ]
}
```
2. Add an entry to the `registry` list in `main.py → seed_mock_tests()`.
3. Restart the backend — the new paper appears in MockBrowser automatically.
