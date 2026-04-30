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
```

# VYAS — Virtual Yield Assessment System

> An intelligent mock examination platform built to simulate real competitive exams, evaluate performance, and help aspirants improve through data-driven practice.

---

## Overview

VYAS is a full-stack assessment platform designed to make exam preparation more structured, measurable, and effective.

Instead of treating mock tests as isolated practice sessions, VYAS approaches preparation as a complete ecosystem where users can:

- Take realistic timed mock examinations  
- Receive instant automated evaluation  
- Analyze strengths and weaknesses  
- Track performance over multiple attempts  
- Practice in an environment close to actual exams

The objective is simple:

**Transform preparation from random practice into strategic improvement.**

---

## Why VYAS?

Competitive exam preparation often lacks a unified system for testing, evaluation, and progress tracking.

VYAS brings these together into one platform by combining:

- Real exam simulation  
- Automated scoring engine  
- Analytics-driven feedback  
- Secure user accounts and attempt history  
- Structured question bank management

It is designed not just to conduct tests, but to support better learning through assessment.

---

## Key Features

### Timed Mock Test Engine
- Realistic exam-like interface  
- Question palette navigation  
- Timed submissions  
- Automated result generation  
- Support for negative marking

### Performance Analytics
- Score breakdowns  
- Accuracy insights  
- Topic-wise analysis  
- Attempt history tracking  
- Progress monitoring over time

### Secure Full-Stack Architecture
- JWT-based authentication  
- Protected routes and sessions  
- Fast and scalable API architecture  
- Persistent user data and results

---

## Tech Stack
```
| Layer | Technology |
|-------|------------|
| Frontend | React + Vite |
| Backend | FastAPI |
| Authentication | JWT |
| ORM | SQLAlchemy |
| Database | SQLite / PostgreSQL |
| Deployment | Vercel + Render |
```
---

## Project Vision

VYAS was built with a broader vision beyond mock testing.

Future scope includes:

- Adaptive testing systems  
- Personalized performance feedback  
- AI-assisted evaluation insights  
- Multi-exam support  
- Smarter learning analytics

This project is a step toward intelligent assessment systems.

---

## Project Structure

```bash
vyas/
├── backend/
│   ├── main.py
│   ├── auth.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   └── services/
│       ├── evaluation.py
│       └── analytics.py
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── context/
│   │   └── api/
│   └── package.json
│
└── question_bank/
```

---

## Core Modules

- Authentication System  
- Mock Test Engine  
- Automated Evaluation Module  
- Analytics Dashboard  
- Question Bank Management

---

## Running Locally

### Backend

```bash
cd backend

python -m venv venv
source venv/bin/activate
# Windows:
# venv\Scripts\activate

pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

Backend runs at:

```bash
http://localhost:8000
```

---

### Frontend

```bash
cd frontend

npm install
npm run dev
```

Frontend runs at:

```bash
http://localhost:5173
```

---

## Deployment

### Frontend
Deployed using **Vercel**

### Backend
Deployed using **Render / Railway**

Production Database:

- PostgreSQL

---

## Why the Name VYAS?

Inspired by **Vyasa**, symbolizing knowledge, wisdom, and authorship,

**VYAS** represents structured learning powered by intelligent assessment.

---

## Author

**Abhinav Singh**  
B.Tech Student | AI/ML Enthusiast | Full Stack Developer

Built as a vision to combine software engineering with educational impact.

---

## Support

If you found this project interesting, consider giving it a ⭐ on GitHub.