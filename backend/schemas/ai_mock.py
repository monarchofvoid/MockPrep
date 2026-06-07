"""
VYAS v2.1 — AI Mock and AI Job Schemas
========================================

SCHEMA FIX (v2.1.5):
  The security-hardened router (routers/ai_mock.py) was updated to use a new
  set of schema classes that better reflect the production data model, but
  schemas/ai_mock.py was not updated in lockstep. This caused an ImportError
  at server startup because CreateMockTestRequest, CreateMockTestResponse,
  CancelJobResponse, and the updated AIJobStatusResponse were referenced but
  not defined.

  Added / corrected classes:
    - CreateMockTestRequest  (replaces GenerateAIMockV2Request)
    - CreateMockTestResponse (replaces GenerateAIMockV2Response)
    - AIJobStatusResponse    (fields rewritten to match router + AIJob frontend type)
    - CancelJobResponse      (new)

  Legacy classes (GenerateAIMockV2Request etc.) are preserved at the bottom
  so any old import in tests or scripts does not break immediately.

Frontend contract (lib/api.ts) matches:
  MockTestRequest     → CreateMockTestRequest
  AIJob               → AIJobStatusResponse
  cancelJob response  → CancelJobResponse
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ══════════════════════════════════════════════════════════════════════════════
# Current production schemas (used by routers/ai_mock.py)
# ══════════════════════════════════════════════════════════════════════════════

class CreateMockTestRequest(BaseModel):
    """
    Request body for POST /api/v1/mock-tests/generate.
    Frontend sends MockTestRequest; field names must match exactly.
    """
    subject: str
    topic: str
    difficulty: str = "medium"   # 'easy' | 'medium' | 'hard' | 'auto'
    num_questions: int = 10
    exam_type: str


class CreateMockTestResponse(BaseModel):
    """
    202 response for POST /api/v1/mock-tests/generate.
    Frontend polls job status after receiving this.
    Matches api.ts generateMockTest() return type.
    """
    job_id: str
    status: str
    estimated_seconds: int
    credits_deducted: Optional[int] = None   # None when job deduction pending


class AIJobStatusResponse(BaseModel):
    """
    Response for GET /api/v1/ai-jobs/{job_id} and GET /api/v1/ai-jobs/.
    Matches the frontend AIJob interface in lib/api.ts exactly so JSON
    serialisation produces the shape the frontend expects.
    """
    job_id: str
    status: str                              # pending|processing|completed|failed|cancelled
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    mock_test_id: Optional[str] = None       # set when status == 'completed'
    progress_message: Optional[str] = None   # human-readable progress hint

    class Config:
        from_attributes = True


class CancelJobResponse(BaseModel):
    """
    Response for DELETE /api/v1/ai-jobs/{job_id}.
    Matches api.ts cancelJob() return type.
    """
    job_id: str
    cancelled: bool
    refunded_credits: Optional[float] = None


# ══════════════════════════════════════════════════════════════════════════════
# Legacy schemas — kept for backward-compat with tests and seed scripts.
# Do not use in new router code.
# ══════════════════════════════════════════════════════════════════════════════

class GenerateAIMockV2Request(BaseModel):
    """DEPRECATED — use CreateMockTestRequest."""
    exam: str
    subject: str
    difficulty: str = "auto"
    question_count: int = 10
    use_proficiency: bool = True


class GenerateAIMockV2Response(BaseModel):
    """DEPRECATED — use CreateMockTestResponse."""
    job_id: str
    status: str
    cost_credits: float
    balance_after_credits: float
    estimated_seconds: int
    message: str


class AIMockHistoryItem(BaseModel):
    job_id: str
    exam: str
    subject: str
    difficulty: str
    question_count: int
    status: str
    cost_credits: float
    mock_id: Optional[str]
    created_at: str


class AIMockHistoryResponse(BaseModel):
    ai_mocks: List[AIMockHistoryItem]
