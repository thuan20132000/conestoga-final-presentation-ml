# Client Authentication & Portal API

Passwordless OTP-based authentication for business clients. Clients log in using their email or phone number, receive a 6-digit code, and verify it to get JWT tokens.

**Base URL:** `/api/`

---

## Authentication Flow

### Existing clients (login)
1. Client requests OTP via email or phone
2. Client receives 6-digit code (email or SMS)
3. Client verifies OTP and receives JWT tokens
4. Client uses access token for authenticated endpoints

### New clients (registration)
1. Client registers with name + email/phone + business_id
2. System creates client record and sends a 6-digit OTP
3. Client verifies OTP (same verify endpoint) and receives JWT tokens

### Google login (new or existing)
1. Frontend obtains a Google ID token via Google Identity Services
2. Frontend sends the token + business_id to backend
3. Backend verifies with Google, finds or creates the client, returns JWT tokens immediately (no OTP needed)

**Token format:** `Authorization: Bearer <access_token>`

---

## Endpoints

### 1. Register (New Client)

`POST /api/client-auth/register/`

**Auth:** None (public)

Registers a new client for a business. At least one of `email` or `phone` is required. An OTP is sent automatically after registration for verification.

**Request (with email):**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "email": "jane.doe@gmail.com",
  "phone": "",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Request (with phone):**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "email": "",
  "phone": "+14165551234",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Request (with both):**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "email": "jane.doe@gmail.com",
  "phone": "+14165551234",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response (200):**
```json
{
  "results": {
    "client_id": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
    "identifier_type": "email"
  },
  "success": true,
  "status_code": 200,
  "message": "Registration successful. OTP sent for verification."
}
```

**Error - Duplicate email (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "A client with this email already exists for this business."
}
```

**Error - Duplicate phone (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "A client with this phone number already exists for this business."
}
```

**Error - Missing email and phone (400):**
```json
{
  "non_field_errors": ["Either email or phone is required."]
}
```

> After registration, use **Verify OTP** (endpoint 4) with the same identifier to complete login.

---

### 2. Google Login

`POST /api/client-auth/google/`

**Auth:** None (public)

Authenticates a client using a Google ID token. If the client doesn't exist for the given business, a new client record is created automatically using the Google profile info (name, email). Returns JWT tokens immediately — no OTP step needed.

**Prerequisites:**
- Set `GOOGLE_CLIENT_ID` in your `.env` file (your Google OAuth 2.0 Client ID from [Google Cloud Console](https://console.cloud.google.com/apis/credentials))
- Frontend uses [Google Identity Services](https://developers.google.com/identity/gsi/web) to obtain the ID token

**Request:**
```json
{
  "google_id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response (200) — existing client:**
```json
{
  "results": {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiJ9...",
      "refresh": "eyJhbGciOiJIUzI1NiJ9..."
    },
    "client": {
      "id": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
      "first_name": "Jane",
      "last_name": "Doe",
      "email": "jane.doe@gmail.com",
      "phone": "+14165551234",
      "primary_business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    },
    "is_new_client": false
  },
  "success": true,
  "status_code": 200,
  "message": "Login successful."
}
```

**Response (200) — new client auto-created:**
```json
{
  "results": {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiJ9...",
      "refresh": "eyJhbGciOiJIUzI1NiJ9..."
    },
    "client": {
      "id": "a1b2c3d4-0000-1111-2222-333344445555",
      "first_name": "Jane",
      "last_name": "Doe",
      "email": "jane.doe@gmail.com",
      "phone": null,
      "primary_business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    },
    "is_new_client": true
  },
  "success": true,
  "status_code": 200,
  "message": "Login successful."
}
```

**Error - Invalid token (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "Invalid Google token."
}
```

**Error - Not configured (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "Google login is not configured."
}
```

---

### 3. Request OTP (Login)

`POST /api/client-auth/request-otp/`

**Auth:** None (public)

Sends a 6-digit OTP to the client's email or phone. The client must already exist in the system for the given business.

**Request:**
```json
{
  "identifier": "client@example.com",
  "identifier_type": "email",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

Phone example:
```json
{
  "identifier": "+14165551234",
  "identifier_type": "phone",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response (200):**
```json
{
  "results": {
    "identifier_type": "email"
  },
  "success": true,
  "status_code": 200,
  "message": "OTP sent successfully."
}
```

**Error - Client not found (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "No account found. Please contact your salon."
}
```

---

### 4. Verify OTP

`POST /api/client-auth/verify-otp/`

**Auth:** None (public)

Verifies the OTP code and returns JWT access and refresh tokens.

**Request:**
```json
{
  "identifier": "client@example.com",
  "identifier_type": "email",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "code": "482951"
}
```

**Response (200):**
```json
{
  "results": {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    },
    "client": {
      "id": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
      "first_name": "Jane",
      "last_name": "Doe",
      "email": "client@example.com",
      "phone": "+14165551234",
      "primary_business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    }
  },
  "success": true,
  "status_code": 200,
  "message": "Login successful."
}
```

**Error - Invalid code (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "Invalid OTP code."
}
```

**Error - Expired code (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "OTP has expired. Please request a new one."
}
```

---

### 5. Refresh Token

`POST /api/client-auth/refresh/`

**Auth:** None (public)

Returns new access and refresh tokens using a valid refresh token.

**Request:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200):**
```json
{
  "results": {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
  },
  "success": true,
  "status_code": 200
}
```

**Error - Invalid token (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "Invalid or expired refresh token."
}
```

---

### 6. Get Client Profile

`GET /api/client-auth/me/`

**Auth:** Client JWT (`Authorization: Bearer <access_token>`)

Returns the authenticated client's profile.

**Request:**
```
GET /api/client-auth/me/
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200):**
```json
{
  "results": {
    "id": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
    "first_name": "Jane",
    "last_name": "Doe",
    "full_name": "Jane Doe",
    "email": "client@example.com",
    "phone": "+14165551234",
    "date_of_birth": "1990-05-15",
    "address_line1": "123 Main St",
    "address_line2": null,
    "city": "Toronto",
    "state_province": "Ontario",
    "postal_code": "M5V 2T6",
    "country": "Canada",
    "preferred_contact_method": "email",
    "primary_business": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "primary_business_name": "Luxe Nails",
    "is_vip": false,
    "bonus_time_minutes": 0,
    "created_at": "2025-01-15T10:30:00Z"
  },
  "success": true,
  "status_code": 200
}
```

---

### 7. List Appointments

`GET /api/client-portal/appointments/`

**Auth:** Client JWT (`Authorization: Bearer <access_token>`)

Returns the authenticated client's appointment history, ordered by most recent first. Supports pagination.

**Request:**
```
GET /api/client-portal/appointments/?page=1&page_size=10
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200):**
```json
{
  "count": 25,
  "next": "http://localhost:8000/api/client-portal/appointments/?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
      "appointment_date": "2026-03-20",
      "status": "CHECKED_OUT",
      "payment_status": "PAID",
      "notes": "",
      "booking_source": "ONLINE",
      "start_at": "2026-03-20T14:00:00Z",
      "appointment_services": [
        {
          "id": "a1b2c3d4-0000-1111-2222-333344445555",
          "service": {
            "id": "s1s2s3s4-5555-6666-7777-888899990000",
            "name": "Gel Manicure"
          },
          "staff": {
            "id": 1,
            "first_name": "Sarah",
            "last_name": "Smith"
          },
          "custom_price": "45.00",
          "custom_duration": 60,
          "start_at": "2026-03-20T14:00:00Z",
          "end_at": "2026-03-20T15:00:00Z",
          "tip_amount": "8.00",
          "status": "confirmed"
        }
      ],
      "latest_payment": {
        "id": "p1p2p3p4-0000-1111-2222-333344445555",
        "amount": "53.00",
        "payment_method": "CARD",
        "created_at": "2026-03-20T15:05:00Z"
      }
    }
  ]
}
```

---

### 8. Subscribe to Push Notifications

`POST /api/client-portal/push-subscribe/`

**Auth:** Client JWT (`Authorization: Bearer <access_token>`)

Registers the client's browser for web push notifications.

**Request:**
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
  "auth": "base64-encoded-auth-key",
  "p256dh": "base64-encoded-p256dh-key",
  "browser": "chrome",
  "user_agent": "Mozilla/5.0..."
}
```

**Response (200):**
```json
{
  "results": {
    "group": "client_f7e8d9c0-b1a2-3456-7890-abcdef123456"
  },
  "success": true,
  "status_code": 200,
  "message": "Push subscription registered."
}
```

---

### 9. Unsubscribe from Push Notifications

`POST /api/client-portal/push-unsubscribe/`

**Auth:** Client JWT (`Authorization: Bearer <access_token>`)

Removes the client's push notification subscription.

**Request:**
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/abc123..."
}
```

**Response (200):**
```json
{
  "results": null,
  "success": true,
  "status_code": 200,
  "message": "Unsubscribed successfully."
}
```

**Error - Not found (400):**
```json
{
  "data": null,
  "success": false,
  "status_code": 400,
  "message": "Subscription not found."
}
```

---

## JWT Token Details

| Field | Value |
|-------|-------|
| Algorithm | HS256 |
| Access token lifetime | 30 days |
| Refresh token lifetime | 90 days |
| Access token type claim | `client_access` |
| Refresh token type claim | `client_refresh` |

**Access token payload:**
```json
{
  "client_id": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "token_type": "client_access",
  "jti": "unique-token-id",
  "iat": 1711100000,
  "exp": 1713692000
}
```

---

## Notes

- **Self-registration**: New clients can register via `/api/client-auth/register/` with their name, email/phone, and a business ID. An OTP is sent immediately for verification.
- **Login (existing clients)**: Use `/api/client-auth/request-otp/` to receive an OTP, then verify it to get tokens.
- **Business-scoped**: `business_id` is required for both registration and login to handle clients with the same email/phone across different businesses.
- **OTP expiry**: Codes expire after 5 minutes. Previous unused OTPs are invalidated when a new one is requested.
- **Separate from staff auth**: Client JWT tokens use `token_type: "client_access"` and do not interfere with staff JWT authentication.
