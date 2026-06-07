"""
VYAS v2.1 — OAuth Service
============================
Handles Google OAuth account linking and user creation.

v2.1 changes:
  - find_or_create_user now accepts profile_picture parameter
  - Stores/updates profile_picture on the User record every login
    so the avatar stays fresh when the user changes their Google photo.

Account linking strategy (unchanged):
  1. Check if OAuthAccount already exists (provider + provider_account_id)
     → If yes: return the linked user (existing login)
  2. Check if a VYAS user exists with the provider email
     → If yes: link the new OAuth account to the existing user
  3. Otherwise: create a new VYAS user with hashed_password=None (OAuth-only)
     and create their wallet + signup bonus in the same transaction
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from core.config import get_settings
from models.user import OAuthAccount, User
from models.wallet import LedgerEntryType
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)
settings = get_settings()


class OAuthService:
    def __init__(self, db: Session):
        self.db = db

    def find_or_create_user(
        self,
        *,
        provider: str,
        provider_account_id: str,
        provider_email: str,
        name: str,
        profile_picture: str = "",
        access_token: str = "",
        refresh_token: str = "",
    ) -> User:
        """
        Find or create a VYAS user for an OAuth login.

        Returns the User. Caller is responsible for reloading with relationships
        if needed (profile, wallet, etc.) for full response building.

        Raises:
            ValueError: if required fields are missing
        """
        if not provider or not provider_account_id:
            raise ValueError("provider and provider_account_id are required")

        # ── Step 1: Existing OAuth account → return linked user ───────────────
        existing_oauth = (
            self.db.query(OAuthAccount)
            .filter_by(
                provider=provider,
                provider_account_id=provider_account_id,
            )
            .first()
        )

        if existing_oauth:
            # Update stored tokens (they may have refreshed)
            existing_oauth.access_token  = access_token
            if refresh_token:
                existing_oauth.refresh_token = refresh_token
            existing_oauth.provider_email = provider_email

            user = self.db.query(User).filter_by(id=existing_oauth.user_id).first()
            if not user:
                raise ValueError(
                    f"OAuthAccount.user_id={existing_oauth.user_id} references missing user"
                )
            if not user.is_active:
                raise ValueError(f"User {user.id} is deactivated")

            # v2.1: refresh profile picture if Google provides one
            if profile_picture:
                user.profile_picture = profile_picture

            self.db.commit()
            logger.info(
                "OAuth login (existing account): provider=%s user_id=%s",
                provider, user.id,
            )
            return user

        # ── Step 2: Existing VYAS user with same email → link OAuth account ───
        existing_user = (
            self.db.query(User)
            .filter_by(email=provider_email)
            .first()
        )

        if existing_user:
            if not existing_user.is_active:
                raise ValueError(f"User {existing_user.id} is deactivated")

            oauth_account = OAuthAccount(
                user_id=existing_user.id,
                provider=provider,
                provider_account_id=provider_account_id,
                provider_email=provider_email,
                access_token=access_token,
                refresh_token=refresh_token,
            )
            self.db.add(oauth_account)

            # v2.1: set profile_picture for the existing user if they don't have one
            if profile_picture and not existing_user.profile_picture:
                existing_user.profile_picture = profile_picture

            self.db.commit()

            logger.info(
                "OAuth account linked to existing user: provider=%s user_id=%s email=%s",
                provider, existing_user.id, provider_email,
            )
            return existing_user

        # ── Step 3: New user — create account, wallet, signup bonus ───────────
        new_user = User(
            name=name.strip() or provider_email.split("@")[0],
            email=provider_email,
            hashed_password=None,       # OAuth-only user — cannot password-login
            email_verified=True,        # Google has already verified the email
            profile_picture=profile_picture or None,  # v2.1: store Google avatar
        )
        self.db.add(new_user)
        self.db.flush()  # populate new_user.id

        oauth_account = OAuthAccount(
            user_id=new_user.id,
            provider=provider,
            provider_account_id=provider_account_id,
            provider_email=provider_email,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        self.db.add(oauth_account)

        # Create wallet and grant signup bonus in the same transaction
        wallet_service = WalletService(self.db)
        wallet_service.create_wallet(new_user.id)
        wallet_service.grant_credits(
            user_id=new_user.id,
            amount_microcredits=settings.SIGNUP_BONUS_MICROCREDITS,
            entry_type=LedgerEntryType.SIGNUP_BONUS,
            idempotency_key=f"oauth_signup_bonus:{new_user.id}",
            description=(
                f"Welcome bonus — "
                f"{settings.SIGNUP_BONUS_MICROCREDITS // settings.MICROCREDITS_PER_CREDIT} "
                f"free credits!"
            ),
        )

        self.db.commit()

        logger.info(
            "New user created via OAuth: provider=%s user_id=%s email=%s",
            provider, new_user.id, provider_email,
        )
        return new_user
