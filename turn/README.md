# Turn Management App

Staff turn queue system for managing FIFO (first-in, first-out) service rotation within a business.

## Models

### StaffTurn
Tracks a staff member's position in the daily turn queue.

| Field | Type | Description |
|-------|------|-------------|
| business | FK → Business | The business this queue belongs to |
| staff | FK → Staff | The staff member |
| position | PositiveInteger | Position in queue (lower = sooner) |
| date | Date | The date this turn applies to |
| is_available | Boolean | Whether staff is currently available |
| current_turn_type | FULL/HALF | Turn type for current service (set on mark-busy, cleared on complete) |
| joined_at | DateTime | When staff joined the queue |

### Turn
Tracks each individual service turn for a staff member.

| Field | Type | Description |
|-------|------|-------------|
| staff_turn | FK → StaffTurn | The staff's queue entry for the day |
| service | FK → Service | The service being performed |
| service_price | Decimal | Price of the service |
| status | pending/in_service/completed | Current status of this turn |
| in_service_at | DateTime | When the turn started |
| completed_at | DateTime | When the turn was completed |

**Turn Status Flow:** `pending` → `in_service` → `completed`

## How It Works

- Staff join the queue via the **Join Queue** API (`POST /api/staff-turns/join/`)
- Staff leave the queue via the **Leave Queue** API (`POST /api/staff-turns/leave/`)
- The staff at the **front** of the queue serves the next client
- After finishing a service, the staff moves to the **back** of the queue

### Full Turn vs Half Turn

Turn type is determined by service price compared to the business's `half_turn_threshold` (configurable per business in BusinessSettings, default: $25.00):

| Condition | Turn Type | Staff Assigned | After Service |
|-----------|-----------|----------------|---------------|
| Price > threshold | **Full Turn** | First available (front of queue) | Moves to back of queue |
| Price <= threshold | **Half Turn** | Last available (back of queue) | Stays in current position |

### Configuration

Each business can set its own threshold via the BusinessSettings API:

```
PATCH /api/business-settings/{id}/
{ "half_turn_threshold": 30.00 }
```

---

## API Endpoints

**Base URL:** `/api/staff-turns/`

**Authentication:** Required (JWT)

**Permissions:** Business Manager or Receptionist

### 1. List Queue

Get the turn queue for a business on a given date.

```
GET /api/staff-turns/?business_id={uuid}&date={YYYY-MM-DD}
```

**Query Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| business_id | Yes | Business UUID |
| date | No | Date to query (defaults to today) |

**Response:**
```json
{
  "results": [
    {
      "id": 1,
      "business": "uuid",
      "staff_id": 1,
      "staff_name": "John Doe",
      "staff_photo": null,
      "position": 1,
      "date": "2026-03-23",
      "is_available": true,
      "current_turn_type": null,
      "joined_at": "2026-03-23T09:00:00Z",
      "created_at": "2026-03-23T09:00:00Z",
      "updated_at": "2026-03-23T09:00:00Z"
    }
  ],
  "success": true,
  "status_code": 200
}
```

### 2. Get Joined Staff with Turns

Get all joined staff ordered by join time, with each staff's turn records for the day.

```
GET /api/staff-turns/joined/?business_id={uuid}&date={YYYY-MM-DD}
```

**Query Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| business_id | Yes | Business UUID |
| date | No | Date to query (defaults to today) |

**Response:**
```json
{
  "results": [
    {
      "id": 1,
      "staff_id": 1,
      "staff_name": "Staff A",
      "staff_photo": null,
      "position": 1,
      "date": "2026-03-23",
      "is_available": true,
      "current_turn_type": null,
      "turns": [
        {
          "id": 1,
          "service": 2,
          "service_name": "Pedicure",
          "service_price": "40.00",
          "status": "completed",
          "in_service_at": "2026-03-23T10:00:00Z",
          "completed_at": "2026-03-23T10:30:00Z",
          "created_at": "2026-03-23T10:00:00Z"
        },
        {
          "id": 2,
          "service": 1,
          "service_name": "Manicure",
          "service_price": "20.00",
          "status": "in_service",
          "in_service_at": "2026-03-23T11:00:00Z",
          "completed_at": null,
          "created_at": "2026-03-23T11:00:00Z"
        }
      ]
    },
    {
      "id": 2,
      "staff_id": 2,
      "staff_name": "Staff B",
      "staff_photo": null,
      "position": 2,
      "date": "2026-03-23",
      "is_available": true,
      "current_turn_type": null,
      "turns": []
    }
  ],
  "success": true,
  "status_code": 200
}
```

### 3. Get Next Available Staff

Get the next available staff in the queue (first by position). Optionally filter by service.

```
GET /api/staff-turns/next/?business_id={uuid}&date={YYYY-MM-DD}&service_id={id}
```

**Query Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| business_id | Yes | Business UUID |
| date | No | Date to query (defaults to today) |
| service_id | No | Only return staff who can perform this service |

### 4. Mark Staff as Busy

Mark a staff member as currently serving a client. Creates a `Turn` record linked to the service with `in_service` status. Pass `service_price` to store the turn type (full/half) for queue repositioning on completion.

```
POST /api/staff-turns/mark-busy/
```

**Request Body:**
```json
{
  "staff_id": 1,
  "service_id": 2,
  "service_price": 40.00
}
```

| Field | Required | Description |
|-------|----------|-------------|
| staff_id | Yes | Staff ID |
| service_id | Yes | Service ID for the turn |
| service_price | No | Price to determine turn type (stored for completion) |

**Response:**
```json
{
  "results": {
    "id": 1,
    "service": 2,
    "service_name": "Pedicure",
    "service_price": "40.00",
    "status": "in_service",
    "in_service_at": "2026-03-23T10:00:00Z",
    "completed_at": null,
    "created_at": "2026-03-23T10:00:00Z"
  },
  "message": "Staff marked as busy",
  "success": true,
  "status_code": 200
}
```

### 5. Complete Service

Mark a service as complete and update the staff's queue position. The latest `in_service` Turn record is marked as `completed`. Uses the turn type stored when the staff was marked busy — no need to pass price again.

```
POST /api/staff-turns/complete-service/
```

**Request Body:**
```json
{
  "staff_id": 1,
  "date": "2026-03-23"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| staff_id | Yes | Staff ID |
| date | No | Defaults to today |

**Response:** Returns the updated StaffTurn. Full turn moves staff to back; half turn keeps position.

### 6. Update Turn

Update an existing turn's details. All fields except `turn_id` are optional — only provided fields get updated.

```
POST /api/staff-turns/update-turn/
```

**Request Body:**
```json
{
  "turn_id": 1,
  "service_id": 3,
  "service_price": 50.00,
  "turn_type": "FULL",
  "is_client_request": true,
  "completed_at": "2026-03-25T14:30:00Z",
  "status": "completed"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| turn_id | Yes | Turn ID to update |
| service_id | No | Change the service |
| service_price | No | Change the service price |
| turn_type | No | Change turn type (FULL or HALF) |
| is_client_request | No | Whether client requested this staff |
| completed_at | No | Override the completion timestamp |
| status | No | Change turn status (pending, in_service, completed) |

**Response:**
```json
{
  "results": {
    "id": 1,
    "service": 3,
    "service_name": "Gel Nails",
    "service_price": "50.00",
    "status": "in_service",
    "in_service_at": "2026-03-25T10:00:00Z",
    "turn_type": "FULL",
    "is_client_request": true,
    "completed_at": "2026-03-25T14:30:00Z",
    "created_at": "2026-03-25T10:00:00Z"
  },
  "success": true,
  "status_code": 200
}
```

### 7. Get Completed Turns

Get all completed turns for a business on a given date, grouped by staff with individual turn records.

```
GET /api/staff-turns/completed/?business_id={uuid}&date={YYYY-MM-DD}
```

**Query Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| business_id | Yes | Business UUID |
| date | No | Date to query (defaults to today) |

**Response:**
```json
{
  "results": [
    {
      "staff_id": 1,
      "staff_name": "John Doe",
      "staff_photo": null,
      "total_turns": 3,
      "full_turns": 2,
      "half_turns": 1,
      "turns": [
        {
          "id": 1,
          "service": 2,
          "service_name": "Pedicure",
          "service_price": "40.00",
          "status": "completed",
          "in_service_at": "2026-03-23T10:00:00Z",
          "completed_at": "2026-03-23T10:30:00Z",
          "created_at": "2026-03-23T10:00:00Z"
        },
        {
          "id": 2,
          "service": 1,
          "service_name": "Manicure",
          "service_price": "20.00",
          "status": "completed",
          "in_service_at": "2026-03-23T11:00:00Z",
          "completed_at": "2026-03-23T11:15:00Z",
          "created_at": "2026-03-23T11:00:00Z"
        },
        {
          "id": 3,
          "service": 3,
          "service_name": "Gel Nails",
          "service_price": "50.00",
          "status": "completed",
          "in_service_at": "2026-03-23T12:00:00Z",
          "completed_at": "2026-03-23T12:45:00Z",
          "created_at": "2026-03-23T12:00:00Z"
        }
      ]
    }
  ],
  "success": true,
  "status_code": 200
}
```

### 8. Send Staff to Back

Manually move a staff member to the back of the queue.

```
POST /api/staff-turns/send-to-back/
```

**Request Body:**
```json
{
  "staff_id": 1
}
```

### 9. Reorder Queue

Manually set the order of the entire queue.

```
POST /api/staff-turns/reorder/
```

**Request Body:**
```json
{
  "ordered_staff_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "date": "2026-03-23"
}
```

**Response:** Returns the full reordered queue.

### 10. Skip Turn

Move a staff member one position back (swap with the next person).

```
POST /api/staff-turns/skip/
```

**Request Body:**
```json
{
  "staff_id": 1
}
```

### 11. Join Queue

Add a staff member to the back of the queue.

```
POST /api/staff-turns/join/
```

**Request Body:**
```json
{
  "staff_id": 1
}
```

### 12. Leave Queue

Remove a staff member from the queue.

```
POST /api/staff-turns/leave/
```

**Request Body:**
```json
{
  "staff_id": 1
}
```

---

## Workflow

### Setup

- Staff A does: Manicure ($20), Pedicure ($40), Gel Nails ($50)
- Staff B does: Manicure ($20), Pedicure ($40)
- Staff C does: Manicure ($20), Gel Nails ($50), Acrylic ($60)
- Business half_turn_threshold: $25.00

### Step 1. Staff Join the Queue

When the business opens or staff arrive, they join the queue.

```
POST /api/staff-turns/join/  {staff_id: 1}   → Queue: [A]
POST /api/staff-turns/join/  {staff_id: 2}   → Queue: [A, B]
POST /api/staff-turns/join/  {staff_id: 3}   → Queue: [A, B, C]
```

### Step 2. Client Arrives and Asks for a Service

Client walks in and requests **Pedicure** (service_id: 2, price: $40).

Call `next` to get available staff who can do Pedicure, ordered by queue position:

```
GET /api/staff-turns/next/?business_id={uuid}&service_id=2

→ Response: [
    {staff_id: 1, staff_name: "Staff A", position: 1, is_available: true},
    {staff_id: 2, staff_name: "Staff B", position: 2, is_available: true},
  ]
  (Staff C is not listed — doesn't do Pedicure)
```

The frontend displays this list to the receptionist.

### Step 3. Receptionist Selects a Staff

Receptionist picks **Staff A** (first in line). Call `mark-busy` with the service and price:

```
POST /api/staff-turns/mark-busy/  {staff_id: 1, service_id: 2, service_price: 40.00}

→ Staff A is now busy, turn type "FULL" stored
→ Turn record created: {service: Pedicure, status: "in_service", service_price: 40.00}
→ Queue: [A(busy/FULL), B, C]
```

### Step 4. Another Client Arrives

Client wants **Manicure** (service_id: 1, price: $20).

```
GET /api/staff-turns/next/?business_id={uuid}&service_id=1

→ Response: [
    {staff_id: 2, staff_name: "Staff B", position: 2, is_available: true},
    {staff_id: 3, staff_name: "Staff C", position: 3, is_available: true},
  ]
  (Staff A is busy)
```

Receptionist picks **Staff C** (or B — their choice):

```
POST /api/staff-turns/mark-busy/  {staff_id: 3, service_id: 1, service_price: 20.00}

→ Staff C is now busy, turn type "HALF" stored
→ Turn record created: {service: Manicure, status: "in_service", service_price: 20.00}
→ Queue: [A(busy/FULL), B, C(busy/HALF)]
```

### Step 5. Service Done

Staff A finishes Pedicure (stored turn type: FULL):

```
POST /api/staff-turns/complete-service/  {staff_id: 1}

→ Turn record updated: {status: "completed", completed_at: "..."}
→ Stored turn type "FULL" → Staff A moves to back of queue
→ Queue: [B, C(busy/HALF), A]
```

Staff C finishes Manicure (stored turn type: HALF):

```
POST /api/staff-turns/complete-service/  {staff_id: 3}

→ Turn record updated: {status: "completed", completed_at: "..."}
→ Stored turn type "HALF" → Staff C stays in current position
→ Queue: [B, C, A]
```

### Step 6. Next Client

Client wants **Gel Nails** (service_id: 3, price: $50).

```
GET /api/staff-turns/next/?business_id={uuid}&service_id=3

→ Response: [
    {staff_id: 3, staff_name: "Staff C", position: 2, is_available: true},
    {staff_id: 1, staff_name: "Staff A", position: 3, is_available: true},
  ]
  (Staff B not listed — doesn't do Gel Nails)
```

Receptionist picks **Staff C**:

```
POST /api/staff-turns/mark-busy/  {staff_id: 3, service_id: 3, service_price: 50.00}
→ Queue: [B, C(busy/FULL), A]
```

### Queue Management

**Skip a staff member's turn:**
```
POST /api/staff-turns/skip/  {staff_id: 1}
→ Staff A swaps with the next person
→ Queue: [B, A, C(busy)]
```

**Manually reorder the entire queue:**
```
POST /api/staff-turns/reorder/  {ordered_staff_ids: [1, 2, 3]}
→ Queue: [A, B, C]
```

**Staff leaves for the day:**
```
POST /api/staff-turns/leave/  {staff_id: 2}
→ Queue: [A, C]
```

### Full Workflow Summary

```
Staff A: Manicure, Pedicure, Gel Nails
Staff B: Manicure, Pedicure
Staff C: Manicure, Gel Nails, Acrylic

Queue: []

1. Staff join
   → A joins, B joins, C joins                        Queue: [A, B, C]

2. Client wants Pedicure ($40)
   → GET /next/?service_id=2
   → Available: [A, B]                                (C can't do Pedicure)
   → Receptionist picks A
   → POST /mark-busy/ {staff_id: A, service_id: 2, service_price: 40}
   → Turn created: Pedicure, in_service, $40
   → Stored: FULL                                     Queue: [A(busy/FULL), B, C]

3. Client wants Manicure ($20)
   → GET /next/?service_id=1
   → Available: [B, C]                                (A is busy)
   → Receptionist picks C
   → POST /mark-busy/ {staff_id: C, service_id: 1, service_price: 20}
   → Turn created: Manicure, in_service, $20
   → Stored: HALF                                     Queue: [A(busy/FULL), B, C(busy/HALF)]

4. Staff A finishes Pedicure
   → POST /complete-service/ {staff_id: A}
   → Turn updated: completed
   → Stored type FULL → moves to back                 Queue: [B, C(busy/HALF), A]

5. Staff C finishes Manicure
   → POST /complete-service/ {staff_id: C}
   → Turn updated: completed
   → Stored type HALF → stays in position             Queue: [B, C, A]

6. Client wants Gel Nails ($50)
   → GET /next/?service_id=3
   → Available: [C, A]                                (B can't do Gel Nails)
   → Receptionist picks C
   → POST /mark-busy/ {staff_id: C, service_id: 3, service_price: 50}
   → Turn created: Gel Nails, in_service, $50
   → Stored: FULL                                     Queue: [B, C(busy/FULL), A]

7. Staff C finishes Gel Nails
   → POST /complete-service/ {staff_id: C}
   → Turn updated: completed
   → Stored type FULL → moves to back                 Queue: [B, A, C]

8. Staff B leaves
   → POST /leave/ {staff_id: B}                       Queue: [A, C]
```
