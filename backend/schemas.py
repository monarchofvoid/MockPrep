"""
VYAS v0.6 — Pydantic Schemas
================================
Changes vs v0.5:
  D2: Added UserProfileOut, UserProfileUpdate schemas
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


# ─── Auth ─────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


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


# ─── User Profile (D2) ────────────────────────────────────────────────────────

VALID_EXAMS   = ("CUET", "GATE", "JEE", "UPSC", "NEET", "CAT", "OTHER")
VALID_AVATARS = ("owl", "fox", "bear", "cat", "robot", "astronaut", "penguin", "tiger")

class UserProfileOut(BaseModel):
    user_id:         int
    preparing_exam:  Optional[str]
    target_year:     Optional[int]
    subject_focus:   Optional[str]
    avatar:          Optional[str]
    daily_goal_mins: Optional[int]
    bio:             Optional[str]
    updated_at:      Optional[datetime]

    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    preparing_exam:  Optional[str]  = None
    target_year:     Optional[int]  = None
    subject_focus:   Optional[str]  = None
    avatar:          Optional[str]  = None
    daily_goal_mins: Optional[int]  = None
    bio:             Optional[str]  = None


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
    passage: Optional[str] = None
    passage_title: Optional[str] = None
    options: Dict[str, str]
    difficulty: str
    topic: str
    marks: float
    negative_marking: float


class QuestionWithAnswer(QuestionOut):
    correct: str
    explanation: str


# ─── Start Attempt ────────────────────────────────────────────────────────────

class StartAttemptRequest(BaseModel):
    mock_id: str

class StartAttemptResponse(BaseModel):
    attempt_id: int
    mock_id: str
    questions: List[QuestionOut]
    duration_minutes: int
    total_marks: float


# ─── Submit Attempt ───────────────────────────────────────────────────────────

class QuestionStateIn(BaseModel):
    question_id: int
    selected_option: Optional[str] = None
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
    passage: Optional[str] = None
    passage_title: Optional[str] = None
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
    topic_performance: List[TopicPerformance]
    question_reviews: List[QuestionReview]


# ─── Analytics ────────────────────────────────────────────────────────────────

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

class TopicMastery(BaseModel):
    topic:    str
    subject:  str
    accuracy: float
    correct:  int
    total:    int
    strength: str

class UserAnalytics(BaseModel):
    user_id: int
    total_attempts: int
    avg_score_percentage: float
    avg_accuracy: float
    strongest_topic: Optional[str]
    weakest_topic: Optional[str]
    topic_mastery: List[TopicMastery] = []
    recent_attempts: List[AttemptSummary]


# Resolve forward ref
TokenResponse.model_rebuild()

# ─── Password Reset ────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ─── Phase 1: Proficiency Engine schemas ──────────────────────────────────────

class DifficultyProfile(BaseModel):
    easy:   float
    medium: float
    hard:   float

class TopicProficiency(BaseModel):
    exam:        str
    subject:     str
    topic:       str
    subtopic:    Optional[str]
    proficiency: float
    level:       str
    accuracy_rate:        float
    total_count:          int
    correct_count:        int
    difficulty_profile:   DifficultyProfile
    avg_time_efficiency:  float
    last_updated:         datetime

    class Config:
        from_attributes = True

class UserProficiencyResponse(BaseModel):
    user_id:       int
    overall_level: str
    overall_score: float
    topic_count:   int
    topics:        List[TopicProficiency]


# ─── Phase 2A: Tutor Schemas ──────────────────────────────────────────────────

class TutorExplainRequest(BaseModel):
    attempt_id:    int
    question_id:   int
    force_refresh: bool = False

class TutorExplanation(BaseModel):
    opening:       str
    core_concept:  str
    why_correct:   str
    why_wrong:     Optional[str]
    memory_anchor: str
    follow_up:     Optional[str]

class TutorExplainResponse(BaseModel):
    interaction_id:      int
    question_id:         int
    proficiency_level:   str
    proficiency_score:   float
    was_cache_hit:       bool
    behavioral_note:     Optional[str]
    explanation:         TutorExplanation

class TutorRateRequest(BaseModel):
    interaction_id: int
    rating:         int

class TutorRateResponse(BaseModel):
    interaction_id: int
    rating:         int
    message:        str


# ─── Phase 2B: AI Mock Generator Schemas ──────────────────────────────────────

class GenerateAIMockRequest(BaseModel):
    exam:            str
    subject:         str
    difficulty:      str = "auto"
    question_count:  int = 10
    use_proficiency: bool = True

class AIMockHistoryItem(BaseModel):
    mock_id:        str
    exam:           str
    subject:        str
    difficulty:     str
    question_count: int
    attempt_id:     Optional[int]
    score:          Optional[float]
    total_marks:    Optional[float]
    created_at:     datetime

    class Config:
        from_attributes = True

class AIMockHistoryResponse(BaseModel):
    ai_mocks: List[AIMockHistoryItem]


# ─── Phase 3: Recommendation Engine Schemas ───────────────────────────────────

class WeakTopic(BaseModel):
    subject:      str
    topic:        str
    proficiency:  float
    accuracy_rate: float
    total_count:  int

class RecommendedMock(BaseModel):
    mock_id:          str
    exam:             str
    subject:          str
    year:             str
    duration_minutes: int
    total_marks:      float
    question_count:   int
    reason:           str

class AIMockSuggestion(BaseModel):
    exam:       str
    subject:    str
    topic:      str
    difficulty: str
    reason:     str

class RecommendationResponse(BaseModel):
    overall_level:        str
    overall_score:        float
    has_proficiency_data: bool
    weak_topics:          List[WeakTopic]
    recommended_mocks:    List[RecommendedMock]
    ai_mock_suggestion:   Optional[AIMockSuggestion]
