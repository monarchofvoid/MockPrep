"""Payment schemas."""
from typing import Optional
from pydantic import BaseModel

class CreditPlanOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    amount_paise: int
    amount_inr: float
    credits_granted: int
    is_popular: bool
    sort_order: int
    class Config:
        from_attributes = True

class CreateOrderRequest(BaseModel):
    plan_id: int

class CreateOrderResponse(BaseModel):
    internal_order_id: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount_paise: int
    currency: str
    credits_to_grant: int

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class VerifyPaymentResponse(BaseModel):
    status: str
    order_id: str
    razorpay_order_id: str
    message: str

class PaymentStatusResponse(BaseModel):
    internal_order_id: str
    razorpay_order_id: str
    status: str
    credits_granted: Optional[int]
    amount_inr: float
    failure_reason: Optional[str]
