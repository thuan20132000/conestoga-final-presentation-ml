# Business Social Auth (Google & Facebook)

Business owners can register a new business and log in to an existing one using **Google** or **Facebook** as the identity provider. No password is set — identity is proved by a verified OAuth token on every request.

## Endpoints

Base path: `/api/business/auth/`. All four endpoints are public (`AllowAny`, no Authorization header required).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/google/register/` | Create business + owner from a Google ID token |
| `POST` | `/google/login/`    | Log in an existing owner with a Google ID token |
| `POST` | `/facebook/register/` | Create business + owner from a Facebook access token |
| `POST` | `/facebook/login/`    | Log in an existing owner with a Facebook access token |

Routes are declared in `business/urls.py`.

## Token verification

| Provider | Library / endpoint | Verified field used as identity |
|----------|--------------------|---------------------------------|
| Google   | `google.oauth2.id_token.verify_oauth2_token` against `GOOGLE_CLIENT_ID` | `email` (must be `email_verified=true`) |
| Facebook | Graph API `debug_token` (app-token gated) + `/me?fields=id,first_name,last_name[,email]` | Facebook user `id` (+ email if scope granted) |

Verification code:

- `BusinessGoogleAuthService._verify_google_token` — `business/services.py`
- `BusinessFacebookAuthService._verify_facebook_token` — `business/services.py`

### Required environment variables

```
GOOGLE_CLIENT_ID=<google-oauth-client-id>
FACEBOOK_APP_ID=<facebook-app-id>
FACEBOOK_APP_SECRET=<facebook-app-secret>
```

Wired in `main/common_settings.py`.

## Identity storage

Both providers identify the owner through `staff.StaffSocialAccount`, which links a provider's `provider_user_id` (Google `sub` / Facebook `id`) to a `Staff` row.

### `StaffSocialAccount` model (`staff/models.py`)

| Field | Type | Notes |
|-------|------|-------|
| `staff` | FK → Staff | `related_name="social_accounts"` |
| `provider` | CharField | `"google"` or `"facebook"` |
| `provider_user_id` | CharField(255) | Google `sub` / Facebook `id` |
| `email` | EmailField (nullable) | As returned by the provider |
| `created_at` / `updated_at` | DateTimeField | Auto timestamps |

`unique_together = ("provider", "provider_user_id")`.

> **Legacy data:** owners who registered via Google before this table existed are matched by email on first login and a `StaffSocialAccount` row is created lazily at that point. Subsequent logins use the provider-identity lookup directly.

## Register

### Request

`POST /api/business/auth/google/register/`

```json
{
  "google_id_token": "<google-id-token>",
  "business": {
    "name": "Jane's Salon",
    "business_type": "<BusinessType uuid>",
    "phone_number": "15550002",
    "email": "salon@example.com",
    "city": "Toronto",
    "country": "Canada"
  },
  "settings": {
    "timezone": "America/Toronto",
    "currency": "CAD"
  }
}
```

`POST /api/business/auth/facebook/register/` — identical shape, with `google_id_token` replaced by `facebook_access_token`.

Serializers: `GoogleBusinessRegisterSerializer`, `FacebookBusinessRegisterSerializer` in `business/serializers.py`.

### What happens on register

`BusinessGoogleAuthService.register` / `BusinessFacebookAuthService.register` in `business/services.py`:

1. Verify the provider token and extract `{first_name, last_name, email[, id]}`.
2. Reject if a `Staff` with that email already exists (HTTP 400 `"An account with this email already exists."`).
3. Facebook only — reject if a `StaffSocialAccount(provider="facebook", provider_user_id=…)` already exists.
4. Call `BusinessRegisterService(...).initialize(send_sms=False)`, which creates:
   - `Business`, `BusinessSettings`
   - `BusinessRoles` (Owner, Manager, Technician, Receptionist)
   - `OperatingHours` (7 days, 09:30–19:30)
   - `PaymentMethod` defaults
   - `BusinessManagersGroup` (webpush)
   - `BusinessOnlineBooking`
   - Default `ServiceCategory` + `Service` from the bundled CSV/JSON
   - Free-trial `BusinessSubscription`
   - Two default technician `Staff` records
   - Owner `Staff` record (linked to the Owner role)
   - Welcome email via `EmailService.send_async`
5. `owner.set_unusable_password()` — password auth is never available for social owners.
6. Facebook only — create the `StaffSocialAccount` row.
7. Issue JWTs with `RefreshToken.for_user(owner)`.

### Response (201 Created)

```json
{
  "success": true,
  "message": "Registration successful",
  "results": {
    "user": { "id": 1, "email": "jane.doe@example.com", "first_name": "Jane", "last_name": "Doe", "phone": null },
    "tokens": { "access": "<jwt>", "refresh": "<jwt>" }
  }
}
```

## Login

### Request

```
POST /api/business/auth/google/login/
POST /api/business/auth/facebook/login/
```

```json
{ "google_id_token":     "<google-id-token>" }
{ "facebook_access_token": "<facebook-access-token>" }
```

### Lookup rule

Both providers look up by `StaffSocialAccount(provider, provider_user_id)` first.

| Provider | Primary lookup | Fallback | Failure message (HTTP 400) |
|----------|----------------|----------|----------------------------|
| Google   | `StaffSocialAccount(provider="google", provider_user_id=idinfo["sub"])` | Match existing `Staff` by email and create the `StaffSocialAccount` row lazily (one-time migration for legacy owners) | `No account found for this Google email. Please register first.` |
| Facebook | `StaffSocialAccount(provider="facebook", provider_user_id=fb_id)` | — | `No account found for this Facebook identity. Please register first.` |

If the provider returns a new/different email, the stored `StaffSocialAccount.email` is updated in place on each login.

### Response (200 OK)

```json
{
  "success": true,
  "message": "Login successful",
  "results": {
    "user": { "id": 1, "email": "jane.doe@example.com", "first_name": "Jane", "last_name": "Doe", "phone": null },
    "tokens": { "access": "<jwt>", "refresh": "<jwt>" }
  }
}
```

## Error responses

All four endpoints return HTTP 400 with the same envelope on failure:

```json
{ "success": false, "message": "<human-readable reason>" }
```

Common messages:

- `Google login is not configured.` / `Facebook login is not configured.` — env vars missing
- `Invalid Google token.` / `Facebook token is not valid for this application.`
- `Google account email is not verified.`
- `An account with this email already exists.` (register)
- `A business is already registered with this Google account.` / `A business is already registered with this Facebook account.` (register)
- `No account found for this <Google email|Facebook identity>. Please register first.` (login)
- `This account is no longer active.` (login when `staff.is_active=False` or soft-deleted)

## Design notes

- **No password is ever set** on social-registered owners (`set_unusable_password`). They must continue logging in through the same provider.
- **SMS credentials are skipped** (`send_sms=False` in `BusinessRegisterService.initialize`) — no SMS goes out during social registration.
- **Cross-provider collisions** are rejected at register time by email: an owner who registered via Google cannot later register via Facebook with the same email. They would have to log in through the original provider.
- **Facebook email is optional**: Facebook users can deny the email scope. Registration still succeeds — `Staff.email` is stored as `""` (the model doesn't allow `NULL`) and `StaffSocialAccount.email` is stored as `NULL`. Identity is tracked by `provider_user_id`, so login works the same way regardless of whether email was granted.
- **Google does not use `StaffSocialAccount`** today — it's email-only. Retrofitting Google to write a `StaffSocialAccount` row on register/login is a straightforward follow-up if cross-provider linking becomes a requirement.

## Tests

`business/tests.py::BusinessFacebookAuthAPITests` covers the Facebook flow end-to-end by mocking `BusinessFacebookAuthService._verify_facebook_token`:

- `test_register_success` — 201, JWT returned, `Business` + `Staff` + `StaffSocialAccount` created
- `test_register_duplicate_email` — 400 when a `Staff` already has the email
- `test_login_success` — register, then log in with the same mocked token → 200
- `test_login_unknown_identity` — login with no matching `StaffSocialAccount` → 400

Run with:

```bash
python manage.py test business.tests.BusinessFacebookAuthAPITests --keepdb
```

The test class uses `@override_settings(MIDDLEWARE=...)` to strip `SignatureVerificationMiddleware` so the public auth endpoints can be exercised without request signing.
