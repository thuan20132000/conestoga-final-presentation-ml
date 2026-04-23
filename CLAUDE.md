# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run development servers
make run                  # Django on :8000
make run-fastapi          # FastAPI (ai_service) on :5050
make run-both             # Both services simultaneously
make run-dev              # Django via uvicorn with .env.dev
make run-prod             # Django via uvicorn with .env.prod

# Database
make migrate              # Apply migrations
make makemigrations       # Generate new migrations
make fake-data            # Seed business types + sample business ("Luxenails")

# Testing
make test-django          # python manage.py test
make test-fastapi         # pytest ai_service/tests/

# Run a single Django test
python manage.py test <app>.tests.<TestClass>.<test_method>

# Code quality
make lint                 # flake8 + black --check + isort --check-only
make format               # black + isort (auto-fix)

# Utilities
make shell                # Django shell
make logs                 # tail -f logs/django.log
make kill-ports           # Kill :8000 and :5050
```

## Architecture

This project runs **two separate services**:

### 1. Django DRF — `main/` (port 8000)
The primary REST API. Entry point: `main/urls.py` → all routes under `/api/`.

**Settings split:**
- `main/settings.py` — app registration, JWT config, then imports `common_settings.py`
- `main/common_settings.py` — DB (PostgreSQL via env vars), REST framework, CORS, AWS S3, Twilio, Stripe, email

**Custom user model:** `staff.Staff` (extends `AbstractUser`). Auth is JWT via `djangorestframework_simplejwt`.

**Shared base:** `main/models.py` defines `SoftDeleteModel` — all domain models inherit from it.

**Timezone middleware:** `main/middleware.py` sets `TIME_ZONE` per-request from `X-Timezone` header. Default: `America/Toronto`.

**File storage:** All media/static files go to AWS S3 via custom backends in `main/custom_storage.py`.

### 2. FastAPI — `ai_service/` (port 5050)
Handles real-time voice AI. Entry point: `ai_service/main.py` → `ai_service/routing/main.py`.

**Internal structure:**
- `routing/` — HTTP and WebSocket route handlers (booking, twilio, websocket, health)
- `services/` — `openai_service.py` (LLM calls), `audio_service.py` (STT/TTS), `booking_api.py` (calls back into Django)
- `tools/` — LangChain/OpenAI function-calling tool definitions for the receptionist agent
- `config.py` — Pydantic `Settings` loaded from `.env`

The FastAPI service imports `CORS_ALLOWED_ORIGINS` directly from `main.common_settings`.

### Django Apps
Each app (`business`, `client`, `staff`, `service`, `appointment`, `payment`, `gift`, `review`, `notifications`, `receptionist`) follows the pattern:
`models.py` → `serializers.py` → `views.py` / `viewsets.py` → `urls.py` → `services.py`

Business logic lives in `services.py`, not in views. Signal hooks are in `signals.py`.

**Key domain relationships:**
- `Staff` (the user model) belongs to a `Business` and has a `BusinessRoles` FK
- `Staff` has `StaffWorkingHours`, `StaffWorkingHoursOverride`, `StaffOffDay`, and `TimeEntry`
- `StaffService` is the M2M through-table linking `Staff` ↔ `Service` with custom price/duration
- `receptionist` tracks `CallSession`, `ConversationMessage`, `Intent`, `AudioRecording`, `SystemLog` — all tied to a `Business`
- Stripe webhook is handled in `main/viewsets.py:StripeWebhookAPIView` at `POST /webhooks/stripe/`

### Environment
Three env files: `.env` (default), `.env.dev`, `.env.prod`. Required vars include:
`SECRET_KEY`, `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOSTNAME`, `DB_PORT`,
`OPENAI_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`,
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`,
`AWS_REGION`, `AWS_LAMBDA_SEND_SMS_ARN`, `AWS_SCHEDULER_POLICY_ARN`.
