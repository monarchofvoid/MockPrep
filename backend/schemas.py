from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


# ─── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: EmailStr

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Mock Test (paper metadata) ───────────────────────────────────────────────

class MockTestOut(BaseModel):
    id: str
    exam: str
    subject: str
    year: str
    duration_minutes: int
    total_marks: float
    question_count: int

    class Config:
        from_attributes = True


# ─── Question (from JSON) ─────────────────────────────────────────────────────

class QuestionOut(BaseModel):
    id: int
    type: str
    question: str
    options: Dict[str, str]
    difficulty: str
    topic: str
    marks: float
    negative_marking: float
    # 'correct' and 'explanation' are NOT exposed during the test,
    # only returned in the results response


class QuestionWithAnswer(QuestionOut):
    correct: str
    explanation: str


# ─── Start Attempt ────────────────────────────────────────────────────────────

class StartAttemptRequest(BaseModel):
    user_id: int
    mock_id: str

class StartAttemptResponse(BaseModel):
    attempt_id: int
    mock_id: str
    questions: List[QuestionOut]   # without answers
    duration_minutes: int
    total_marks: float


# ─── Submit Attempt ───────────────────────────────────────────────────────────

class QuestionStateIn(BaseModel):
    """Per-question tracking data sent from the frontend on submit."""
    question_id: int
    selected_option: Optional[str] = None   # "A" | "B" | "C" | "D" | null
    time_spent_seconds: int = 0
    visit_count: int = 0
    answer_changed_count: int = 0
    was_marked_for_review: bool = False

class SubmitAttemptRequest(BaseModel):
    attempt_id: int
    time_taken_seconds: int
    question_states: List[QuestionStateIn]


# ─── Results ──────────────────────────────────────────────────────────────────

class TopicPerformance(BaseModel):
    topic: str
    correct: int
    total: int
    accuracy: float

class QuestionReview(BaseModel):
    question_id: int
    question_text: str
    options: Dict[str, str]
    selected_option: Optional[str]
    correct_option: str
    is_correct: bool
    marks_awarded: float
    explanation: str
    time_spent_seconds: int
    visit_count: int
    answer_changed_count: int
    was_marked_for_review: bool
    difficulty: str
    topic: str

class ResultsResponse(BaseModel):
    attempt_id: int
    mock_id: str
    subject: str
    year: str

    # Summary
    score: float
    total_marks: float
    score_percentage: float
    correct_count: int
    wrong_count: int
    skipped_count: int
    accuracy: float
    attempt_rate: float
    time_taken_seconds: int
    avg_time_per_question: float

    # Breakdowns
    topic_performance: List[TopicPerformance]
    question_reviews: List[QuestionReview]


# ─── Analytics (user history) ─────────────────────────────────────────────────

class AttemptSummary(BaseModel):
    attempt_id: int
    mock_id: str
    subject: str
    year: str
    score: Optional[float]
    total_marks: Optional[float]
    accuracy: Optional[float]
    time_taken_seconds: Optional[int]
    started_at: datetime

    class Config:
        from_attributes = True

class UserAnalytics(BaseModel):
    user_id: int
    total_attempts: int
    avg_score_percentage: float
    avg_accuracy: float
    strongest_topic: Optional[str]
    weakest_topic: Optional[str]
    recent_attempts: List[AttemptSummary]
