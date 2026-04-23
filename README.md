# Bookngon AI - Virtual Receptionist (Django DRF + Twilio + OpenAI)

## Environment variables
Set these in your shell or a .env loaded by your process manager:

- OPENAI_API_KEY
- OPENAI_MODEL (optional, default: gpt-4o-mini)
- OPENAI_TEMPERATURE (optional, default: 0.4)
- ALLOWED_HOSTS (comma-separated, e.g. "localhost,127.0.0.1,*.ngrok-free.app")
- TWILIO_AUTH_TOKEN (optional for signature verification)

## Install & run (dev)
```bash
python -m venv env && source env/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## Endpoints
- Voice webhook: `POST /api/receptionist/twilio/voice/`
- SMS webhook: `POST /api/receptionist/twilio/sms/`

Both return TwiML (`text/xml`).

## Twilio configuration
1. Expose your local server (e.g. using ngrok):
   ```bash
   ngrok http http://localhost:8000
   ```
2. In Twilio Console, set webhook URLs:
   - Voice: `https://<your-domain>/api/receptionist/twilio/voice/`
   - Messaging: `https://<your-domain>/api/receptionist/twilio/sms/`
3. Set request method to POST.

## Optional: Verify Twilio signatures
The code includes a placeholder `verify_twilio_signature` in `receptionist/views.py`. To enable robust verification, compute and check the `X-Twilio-Signature` header using `TWILIO_AUTH_TOKEN`.

## Quick test (without Twilio)
```bash
# SMS simulate
curl -X POST http://localhost:8000/api/receptionist/twilio/sms/ \
  -d 'From=+15551234567' -d 'Body=Hi, I want to book a table'

# Voice simulate (Twilio normally sends many params)
curl -X POST http://localhost:8000/api/receptionist/twilio/voice/ \
  -d 'SpeechResult=I would like a reservation at 7pm'
```

## Turn Service APIs

Base path: `/api/turn-services/`

All endpoints require authentication (`Authorization: Bearer <token>`) and business manager/receptionist permission.
`business_id` is resolved from the query param, request body, or the authenticated user's business.

---

### CRUD

#### List turn services

```
GET /api/turn-services/?business_id=<uuid>
```

Response:
```json
{
  "results": [
    {
      "id": 1,
      "business": "a1b2c3d4-...",
      "name": "Nail Full Set",
      "services": [
        { "id": 10, "name": "Acrylic Full Set", "price": "45.00", "duration_minutes": 60 },
        { "id": 11, "name": "Gel Full Set", "price": "55.00", "duration_minutes": 50 }
      ],
      "is_active": true,
      "created_at": "2026-03-25T10:00:00Z",
      "updated_at": "2026-03-25T10:00:00Z"
    }
  ],
  "success": true,
  "status_code": 200
}
```

#### Create a turn service

```
POST /api/turn-services/
Content-Type: application/json
```

Request:
```json
{
  "business_id": "a1b2c3d4-...",
  "name": "Nail Full Set",
  "service_ids": [10, 11]
}
```

Response:
```json
{
  "results": {
    "id": 1,
    "business": "a1b2c3d4-...",
    "name": "Nail Full Set",
    "services": [
      { "id": 10, "name": "Acrylic Full Set", "price": "45.00", "duration_minutes": 60 },
      { "id": 11, "name": "Gel Full Set", "price": "55.00", "duration_minutes": 50 }
    ],
    "is_active": true,
    "created_at": "2026-03-26T12:00:00Z",
    "updated_at": "2026-03-26T12:00:00Z"
  },
  "success": true,
  "status_code": 200
}
```

#### Update a turn service

```
PUT /api/turn-services/1/
Content-Type: application/json
```

Request:
```json
{
  "name": "Nail Full Set (Updated)",
  "is_active": true,
  "service_ids": [10, 11, 12]
}
```

Response: same shape as create.

#### Delete a turn service

```
DELETE /api/turn-services/1/
```

Response:
```json
{
  "results": null,
  "success": true,
  "status_code": 200,
  "message": "Turn service deleted"
}
```

---

### Staff Assignment

#### Assign staff to a turn service

```
POST /api/turn-services/1/assign-staff/
Content-Type: application/json
```

Request:
```json
{
  "staff_ids": [5, 8]
}
```

Response:
```json
{
  "results": [
    {
      "id": 1,
      "staff_id": 5,
      "staff_name": "Jane Doe",
      "staff_photo": null,
      "turn_service": 1,
      "turn_service_name": "Nail Full Set",
      "created_at": "2026-03-26T12:00:00Z"
    },
    {
      "id": 2,
      "staff_id": 8,
      "staff_name": "John Smith",
      "staff_photo": "https://bucket.s3.amazonaws.com/staff_photos/john.jpg",
      "turn_service": 1,
      "turn_service_name": "Nail Full Set",
      "created_at": "2026-03-26T12:00:00Z"
    }
  ],
  "success": true,
  "status_code": 200,
  "message": "Staff assigned"
}
```

#### Remove staff from a turn service

```
POST /api/turn-services/1/remove-staff/
Content-Type: application/json
```

Request:
```json
{
  "staff_ids": [8]
}
```

Response:
```json
{
  "results": null,
  "success": true,
  "status_code": 200,
  "message": "Staff removed"
}
```

#### List staff assigned to a turn service

```
GET /api/turn-services/1/staff/
```

Response:
```json
{
  "results": [
    {
      "id": 1,
      "staff_id": 5,
      "staff_name": "Jane Doe",
      "staff_photo": null,
      "turn_service": 1,
      "turn_service_name": "Nail Full Set",
      "created_at": "2026-03-26T12:00:00Z"
    }
  ],
  "success": true,
  "status_code": 200
}
```

#### List turn services for a staff member

```
GET /api/turn-services/by-staff/?staff_id=5
```

Response:
```json
{
  "results": [
    {
      "id": 1,
      "business": "a1b2c3d4-...",
      "name": "Nail Full Set",
      "services": [
        { "id": 10, "name": "Acrylic Full Set", "price": "45.00", "duration_minutes": 60 }
      ],
      "is_active": true,
      "created_at": "2026-03-25T10:00:00Z",
      "updated_at": "2026-03-25T10:00:00Z"
    }
  ],
  "success": true,
  "status_code": 200
}
```

---

### Staff Turn Queue (updated endpoints)

These existing endpoints now accept `turn_service_id` instead of `service_id`.

#### Next available staff filtered by turn service

```
GET /api/staff-turns/next/?business_id=a1b2c3d4-...&turn_service_id=1
```

Response:
```json
{
  "results": [
    {
      "id": 42,
      "business": "a1b2c3d4-...",
      "staff_id": 5,
      "staff_name": "Jane Doe",
      "staff_photo": null,
      "position": 1,
      "date": "2026-03-26",
      "is_available": true,
      "joined_at": "2026-03-26T09:00:00Z",
      "created_at": "2026-03-26T09:00:00Z",
      "updated_at": "2026-03-26T09:00:00Z"
    }
  ],
  "success": true,
  "status_code": 200
}
```

#### Mark staff as in service

```
POST /api/staff-turns/mark-in-service/
Content-Type: application/json
```

Request:
```json
{
  "staff_turn_id": 42,
  "turn_service_id": 1,
  "turn_type": "FULL",
  "is_client_request": false
}
```

Response:
```json
{
  "results": {
    "id": 100,
    "turn_service": 1,
    "turn_service_name": "Nail Full Set",
    "services": [
      { "id": 10, "name": "Acrylic Full Set", "price": "45.00", "duration_minutes": 60 }
    ],
    "service_price": "0.00",
    "status": "in_service",
    "in_service_at": "2026-03-26T14:30:00Z",
    "turn_type": "FULL",
    "is_client_request": false,
    "completed_at": null,
    "created_at": "2026-03-26T14:30:00Z"
  },
  "success": true,
  "status_code": 200,
  "message": "Staff marked as in service"
}
```

#### Delete a turn

```
POST /api/staff-turns/delete-turn/
Content-Type: application/json
```

Request:
```json
{
  "turn_id": 100,
  "staff_turn_id": 42
}
```

Response:
```json
{
  "results": null,
  "success": true,
  "status_code": 200,
  "message": "Turn deleted successfully"
}
```

## Notes
- Responses are generated via OpenAI Chat Completions; adjust `SYSTEM_PROMPT` in `receptionist/views.py` as needed.
- Voice flow uses TwiML `Gather` to collect speech/DTMF and loops back to continue the conversation.
