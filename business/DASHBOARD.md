# Business Dashboard API — Frontend Reference

## Endpoint

```
GET /api/business/{business_id}/dashboard/
```

**Auth:** Bearer token required (`Authorization: Bearer <access_token>`)

### Query Parameters

| Parameter   | Type   | Required | Default                    | Description                        |
|-------------|--------|----------|----------------------------|------------------------------------|
| `from_date` | string | No       | First day of current month | Start of date range (`YYYY-MM-DD`) |
| `to_date`   | string | No       | Last day of current month  | End of date range (`YYYY-MM-DD`)   |

Both `from_date` and `to_date` must be provided together. If either is omitted, the entire current month is used.

**Examples:**

```
GET /api/business/1/dashboard/
GET /api/business/1/dashboard/?from_date=2026-04-01&to_date=2026-04-30
GET /api/business/1/dashboard/?from_date=2026-04-01&to_date=2026-04-16
```

---

## Response Envelope

```json
{
  "success": true,
  "results": { ...dashboard data... }
}
```

All dashboard data lives under `results`.

---

## Response Schema

### Top-Level Fields

| Field                      | Type              | Description                                                    |
|----------------------------|-------------------|----------------------------------------------------------------|
| `total_appointments`       | object            | Total appointments in the period + % change vs prior period    |
| `total_revenue`            | object            | Total completed payment revenue + % change vs prior period     |
| `total_customers`          | object            | New customers in period + new this week + % change             |
| `average_rating`           | object            | Average review rating + review count                           |
| `pending_appointments`     | object            | Count of scheduled (unconfirmed) appointments                  |
| `completed_payments`       | object            | Count of completed payment transactions                        |
| `active_staff`             | object            | Count of currently active staff members                        |
| `todays_appointments`      | array             | Today's appointments list (always today, ignores date range)   |
| `appointments_by_status`   | object            | Appointment counts broken down by status                       |
| `booking_sources`          | object            | Appointment counts broken down by booking source               |
| `revenue_by_payment_method`| array             | Revenue totals per payment method type                         |
| `total_tips`               | number (float)    | Total tips collected in the period                             |
| `average_ticket_value`     | number (float)    | Total revenue / number of completed payments                   |
| `cancellation_rate`        | number (float)    | Percentage of appointments that were cancelled                 |
| `no_show_rate`             | number (float)    | Percentage of appointments that were no-shows                  |
| `staff_performance`        | array             | Per-staff appointment count, revenue, and client requests, sorted by revenue |
| `daily_trends`             | array             | Day-by-day appointment count and revenue for the selected range|
| `staff_requested_by_client`| object            | Count of distinct staff members specifically requested by a client in the period |

---

## Detailed Field Shapes

### `total_appointments`
```json
{
  "count": 142,
  "change_percentage": 12.5
}
```
- `change_percentage`: `null` if no data in prior period.

### `total_revenue`
```json
{
  "amount": 4820.50,
  "change_percentage": -3.2
}
```
- Only counts payments with `status = "completed"`.
- `change_percentage`: `null` if no revenue in prior period.

### `total_customers`
```json
{
  "count": 38,
  "new_this_week": 7,
  "change_percentage": 5.0
}
```
- `count`: new clients created in the selected date range.
- `new_this_week`: new clients in the last 7 days (always rolling, ignores date range).
- `change_percentage`: `null` if no new customers in prior period.

### `average_rating`
```json
{
  "value": 4.7,
  "review_count": 29
}
```
- `value`: `null` if no reviews in the period.

### `pending_appointments`
```json
{
  "count": 11
}
```

### `completed_payments`
```json
{
  "count": 98
}
```

### `active_staff`
```json
{
  "count": 6
}
```
- Not date-scoped — reflects current active staff count.

---

### `todays_appointments`
Always shows **today's** appointments regardless of the `from_date`/`to_date` range.

```json
[
  {
    "id": 501,
    "status": "scheduled",
    "client_name": "Jane Doe",
    "start_at": "2026-04-16T10:30:00Z",
    "booking_source": "online",
    "services": ["Gel Manicure", "Pedicure"]
  },
  {
    "id": 502,
    "status": "in_service",
    "client_name": null,
    "start_at": null,
    "booking_source": "walk_in",
    "services": ["Acrylic Full Set"]
  }
]
```

**`status` values:**

| Value             | Label           |
|-------------------|-----------------|
| `scheduled`       | Scheduled       |
| `in_service`      | In Service      |
| `checked_in`      | Checked In      |
| `checked_out`     | Checked Out     |
| `cancelled`       | Cancelled       |
| `no_show`         | No Show         |
| `pending_payment` | Pending Payment |

**`booking_source` values:**

| Value              | Label             |
|--------------------|-------------------|
| `online`           | Online Booking    |
| `phone`            | Phone Booking     |
| `walk_in`          | Walk-in           |
| `staff`            | Staff Booking     |
| `ai_receptionist`  | AI Receptionist   |

---

### `appointments_by_status`
```json
{
  "scheduled": 11,
  "in_service": 2,
  "checked_in": 0,
  "checked_out": 89,
  "cancelled": 14,
  "no_show": 5,
  "pending_payment": 3
}
```

---

### `booking_sources`
```json
{
  "online": 65,
  "phone": 20,
  "walk_in": 30,
  "staff": 10,
  "ai_receptionist": 17
}
```

---

### `revenue_by_payment_method`
Sorted descending by amount. Only methods that have completed payments in the period appear.

```json
[
  { "method": "cash",        "amount": 2100.00 },
  { "method": "debit_card",  "amount": 1450.50 },
  { "method": "gift_card",   "amount": 870.00  },
  { "method": "credit_card", "amount": 400.00  }
]
```

**`method` possible values:** `cash`, `credit_card`, `debit_card`, `bank_transfer`, `online`, `gift_card`, `store_credit`, `split_payment`, `other`

---

### `total_tips`
```json
7.50
```
Float — total tips collected across all appointment services in the period.

### `average_ticket_value`
```json
49.19
```
Float — `total_revenue / completed_payment_count`. Returns `0.0` if no completed payments.

### `cancellation_rate`
```json
9.8
```
Float — percentage (0–100). Returns `0.0` if no appointments in the range.

### `no_show_rate`
```json
3.5
```
Float — percentage (0–100). Returns `0.0` if no appointments in the range.

---

### `staff_performance`
Sorted descending by `revenue`. Includes all active staff even if they had zero appointments.

```json
[
  {
    "staff_id": 12,
    "name": "Diana Le",
    "appointment_count": 34,
    "revenue": 1670.00,
    "total_staff_requested": 18
  },
  {
    "staff_id": 8,
    "name": "John Nguyen",
    "appointment_count": 28,
    "revenue": 1240.50,
    "total_staff_requested": 10
  },
  {
    "staff_id": 15,
    "name": "Tony Pham",
    "appointment_count": 0,
    "revenue": 0.0,
    "total_staff_requested": 0
  }
]
```

- `total_staff_requested`: number of checked-out appointment services where the client specifically requested this staff member (`is_staff_request = true`).

---

### `daily_trends`
One entry per day in `[from_date, to_date]`, inclusive. Useful for line/bar charts.

```json
[
  { "date": "2026-04-01", "appointments": 12, "revenue": 480.00 },
  { "date": "2026-04-02", "appointments": 9,  "revenue": 355.00 },
  { "date": "2026-04-03", "appointments": 0,  "revenue": 0.0    },
  ...
  { "date": "2026-04-16", "appointments": 7,  "revenue": 290.50 }
]
```

---

### `staff_requested_by_client`
```json
{
  "count": 4
}
```
- `count`: number of **distinct staff members** who had at least one appointment service in the period where the client explicitly requested them (`is_staff_request = true`). Only considers appointments that are not soft-deleted.

---

## Full Example Response

```json
{
  "success": true,
  "results": {
    "total_appointments":       { "count": 142, "change_percentage": 12.5 },
    "total_revenue":            { "amount": 4820.50, "change_percentage": -3.2 },
    "total_customers":          { "count": 38, "new_this_week": 7, "change_percentage": 5.0 },
    "average_rating":           { "value": 4.7, "review_count": 29 },
    "pending_appointments":     { "count": 11 },
    "completed_payments":       { "count": 98 },
    "active_staff":             { "count": 6 },
    "todays_appointments": [
      {
        "id": 501,
        "status": "scheduled",
        "client_name": "Jane Doe",
        "start_at": "2026-04-16T10:30:00Z",
        "booking_source": "online",
        "services": ["Gel Manicure", "Pedicure"]
      }
    ],
    "appointments_by_status": {
      "scheduled": 11,
      "in_service": 2,
      "checked_in": 0,
      "checked_out": 89,
      "cancelled": 14,
      "no_show": 5,
      "pending_payment": 3
    },
    "booking_sources": {
      "online": 65,
      "phone": 20,
      "walk_in": 30,
      "staff": 10,
      "ai_receptionist": 17
    },
    "revenue_by_payment_method": [
      { "method": "cash",       "amount": 2100.00 },
      { "method": "debit_card", "amount": 1450.50 }
    ],
    "total_tips": 320.00,
    "average_ticket_value": 49.19,
    "cancellation_rate": 9.8,
    "no_show_rate": 3.5,
    "staff_performance": [
      { "staff_id": 12, "name": "Diana Le",    "appointment_count": 34, "revenue": 1670.00, "total_staff_requested": 18 },
      { "staff_id": 8,  "name": "John Nguyen", "appointment_count": 28, "revenue": 1240.50, "total_staff_requested": 10 }
    ],
    "daily_trends": [
      { "date": "2026-04-01", "appointments": 12, "revenue": 480.00 },
      { "date": "2026-04-02", "appointments": 9,  "revenue": 355.00 }
    ],
    "staff_requested_by_client": { "count": 4 }
  }
}
```

---

## Suggested UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Date Range Picker  [Apr 1 – Apr 30, 2026]                          │
├───────────┬───────────┬───────────┬───────────┬────────────┬────────┤
│ Total     │ Revenue   │ Customers │ Avg Rating│ Pending    │ Active │
│ Appts     │           │           │           │ Appts      │ Staff  │
│ 142 ↑12%  │ $4,820 ↓3%│ 38 ↑5%   │ ★ 4.7     │ 11         │ 6      │
├───────────┴───────────┴───────────┴───────────┴────────────┴────────┤
│                                                                     │
│  Today's Appointments (live list)                                   │
│  [Table: time | client | services | status | source]                │
│                                                                     │
├─────────────────────────────┬───────────────────────────────────────┤
│  Revenue Trend (line chart) │  Appointments by Status (donut chart) │
│  daily_trends               │  appointments_by_status               │
├─────────────────────────────┼───────────────────────────────────────┤
│  Revenue by Method          │  Booking Sources (bar chart)          │
│  (horizontal bar chart)     │  booking_sources                      │
│  revenue_by_payment_method  │                                       │
├─────────────────────────────┴───────────────────────────────────────┤
│  Staff Performance                                                  │
│  [Table: staff name | appointments | client requests | revenue]     │
├─────────────────────────────────────────────────────────────────────┤
│  Rate Cards                                                         │
│  Cancellation Rate: 9.8%   No-Show Rate: 3.5%                       │
│  Avg Ticket: $49.19        Total Tips: $320.00                      │
│  Staff Requested by Client: 4                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Notes for Frontend

- **`change_percentage`** can be `null` — render as `N/A` or hide the indicator when null.
- **`todays_appointments`** is always anchored to the server's current date (today), not the selected date range. Poll or refresh this section more frequently (e.g., every 60 seconds) for an operational feel.
- **`daily_trends`** length equals `(to_date - from_date).days + 1`. For a full month it will have 28–31 entries.
- **`staff_performance`** includes all active staff. Staff with 0 appointments will appear at the bottom.
- **`average_ticket_value`** returns `0.0` when there are no completed payments — guard against divide-by-zero display.
- **`client_name`** in `todays_appointments` can be `null` for walk-in clients with no profile.
- **`start_at`** in `todays_appointments` can be `null` if the appointment was created without a specific time slot.
- **`staff_requested_by_client`** counts distinct staff, not total request events — a staff member with multiple client-requested appointments counts as 1.
- **`total_staff_requested`** in `staff_performance` is the raw count of individual appointment services where that staff was requested by a client (checked-out only).
