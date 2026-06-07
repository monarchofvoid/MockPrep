"""Wallet schemas — Pydantic v2."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_microcredits: int
    balance_after_microcredits: int
    entry_type: str
    description: Optional[str] = None
    payment_order_id: Optional[str] = None
    ai_job_id: Optional[str] = None
    created_at: datetime

    @property
    def amount_credits(self) -> float:
        return self.amount_microcredits / 100


class WalletOut(BaseModel):
    balance_microcredits: int
    balance_credits: float
    lifetime_earned_credits: float
    lifetime_spent_credits: float
    recent_transactions: List[LedgerEntryOut] = []


class TransactionListResponse(BaseModel):
    transactions: List[LedgerEntryOut]
    total: int
    page: int
    per_page: int
    total_pages: int


class AdminGrantRequest(BaseModel):
    user_id: int
    amount_credits: int
    reason: Optional[str] = None