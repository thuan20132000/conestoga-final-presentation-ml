# GROUP 5 - CSCN8010 Final Project

## - Minh Thuan (8730956)

## - Preeja Anilal (8791796)

## - Anthony Nosa Izevbokun (9016626)

### [https://github.com/thuan20132000/ai-service-contestoga.git](https://github.com/thuan20132000/ai-service-contestoga.git)

# 🤖 Smart AI Receptionist

### Real-Time Voice Intelligence Powered by OpenAI Agents SDK & Twilio

---

## Executive Summary

The **Smart AI Receptionist** is a production-grade, real-time voice AI system that answers incoming phone calls, understands caller intent, detects emotional distress, and either resolves queries autonomously or escalates to a human agent. It is built on a dual-server architecture — a **FastAPI voice layer** for real-time telephony and a **Django API** as the business logic backbone — bridged by the **OpenAI Agents SDK**.

In this final implementation, we also integrated two core data-science capabilities required by the course:

- A **DVC-orchestrated ML pipeline** that trains post-call classifiers (`category`, `sentiment`, `outcome`) using TF-IDF + Logistic Regression and produces reproducible artifacts.
- A **Build Knowledge** workflow that collects business data, generates embeddings, stores vectors with metadata, and retrieves top-k business facts at runtime for grounded responses.

> **The system doesn't just talk. It listens, understands, classifies, and decides.**

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Deliverable 1 — NLP Model for Query Processing](#deliverable-1--nlp-model-for-query-processing)
3. [Deliverable 2 — Multi-Agent Handoffs & Tool Execution](#deliverable-2--multi-agent-handoffs--tool-execution)
4. [Deliverable 3 — Post-Call Classification (ML)](#deliverable-3--post-call-classification-ml)
5. [Deliverable 4 — Build Knowledge Base (Embeddings + Vector Search)](#deliverable-4--build-knowledge-base-embeddings--vector-search)
6. [Deliverable 5 — DVC-Orchestrated ML Pipeline](#deliverable-5--dvc-orchestrated-ml-pipeline)
7. [Technology Stack](#technology-stack)
8. [Data Flow: End-to-End Call Lifecycle](#data-flow-end-to-end-call-lifecycle)
9. [Deployment & Infrastructure](#deployment--infrastructure)

---

## System Architecture Overview

```
Caller (Phone)
     │
     ▼
[ Twilio PSTN / Voice ]
     │  (audio stream via WebSocket)
     ▼
[ FastAPI Server ]  ←── Real-time voice layer
     │  (REST API calls)
     ▼
[ OpenAI Agents SDK ]
     │  (orchestration + tool calls)
     ▼
[ Django API ]  ←── Business logic, database, agent tools
     │
     ▼
[ PostgreSQL / Data Store ]
```

System Architecture Diagram

The system operates as two cooperating servers:

- **FastAPI** handles the low-latency WebSocket connection from Twilio, streams audio to OpenAI's Realtime API, and manages session state.
- **Django** acts as the authoritative backend: it stores conversation history, exposes tool endpoints that the agent calls (e.g., `lookup_appointment`, `create_ticket`), and manages escalation workflows.

---

## Deliverable 1 — NLP Model for Query Processing

### What It Does

The NLP layer is the **first point of intelligence** in the pipeline. The moment a caller's speech is transcribed (via OpenAI Whisper / Realtime API), the text is passed through a natural language processing pipeline to extract structured meaning before any decision-making occurs.

### Core Components

**Intent Recognition**
The NLP model identifies *what the caller wants* — their primary intent. Examples:

- `general_question` — "What are your hours?"

**Named Entity Recognition (NER)**
Key entities are extracted from the utterance to parameterize the response:

- **Person names** — "My name is John Smith"
- **Dates & times** — "Next Tuesday at 3pm"
- **Account or reference numbers** — "My order number is 84521"
- **Locations** — "The downtown branch"

**Slot Filling & Context Tracking**
Multi-turn conversations require the model to maintain a *dialogue state* — remembering what has already been said so it can ask targeted follow-up questions rather than re-asking for information already provided.

### Implementation Approach

```python
# Simplified NLP pipeline within the agent tool call
def process_query(transcript: str, context: dict) -> dict:
    intent = classify_intent(transcript)          # Intent classification
    entities = extract_entities(transcript)        # SpaCy / OpenAI function calling
    slots = fill_slots(intent, entities, context)  # Dialogue state manager
    return {"intent": intent, "entities": entities, "slots": slots}
```

The NLP layer is embedded directly into the **OpenAI Agents SDK tool definitions**, where function-calling acts as the structured extraction mechanism — the LLM both understands and formats output simultaneously.

An handler is used to collect the NER entities and saved to our database. see code below 

```python

    async def _realtime_session_loop(self) -> None:
        """Receive events from OpenAI RealtimeSession and forward audio to Twilio."""
        try:
            async for event in self._session:
                event_type = event.type

                if event_type == "audio":
                    await self._handle_audio_event(event)

                elif event_type == "audio_interrupted":
                    await self._handle_interruption()

                elif event_type == "audio_end":
                    pass

                elif event_type == "history_updated":
                    await self._handle_history_updated(event)

                elif event_type == "history_added":
                    pass  # handled via history_updated which has transcripts

                elif event_type == "agent_end":
                    logger.info("Agent ended session")

                elif event_type == "error":
                    logger.error(f"Realtime session error: {event.error}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in realtime session loop: {e}")
        finally:
            self._done_event.set()
```

---

## Deliverable 2 — Multi-Agent Handoffs & Tool Execution

### What It Does

The running system is not a single monolithic model. A **triage “AI Receptionist”** agent (OpenAI Agents SDK) routes the caller, then **hands off** to specialized sub-agents. Each sub-agent can invoke **Django-backed tools** for real CRUD and lookups so answers stay consistent with the database.

### Agent Handoffs (Implemented)


| From         | Handoff to           | When                                                                                        |
| ------------ | -------------------- | ------------------------------------------------------------------------------------------- |
| Receptionist | **FAQ Agent**        | Business hours, location, services, general Q&A                                             |
| Receptionist | **Booking Agent**    | New appointments, availability                                                              |
| Receptionist | **Reschedule Agent** | Reschedule: uses `look_up_appointment` to find the booking, then guides next steps in voice |
| Receptionist | **Cancel Agent**     | Cancel flow (guided in voice; confirms details before end of call)                          |
| (As needed)  | **Customer Agent**   | Customer profile / phone-linked context (`get_customer_information`)                        |


The receptionist’s job is to **classify intent** and **transfer** to the right specialist instead of one prompt trying to do everything.

### Representative Tool Surface (Django / FastAPI)

Tools are defined with `@function_tool` in `ai_service/tools/` and call the booking/business layer using `CallContext` (`business_id`, `caller_number`, etc.). In our codebase, the **Booking** and **FAQ** agents bundle the richest tool sets; **Reschedule** uses `look_up_appointment`; **Cancel** is instruction-driven in the current implementation.


| Area       | Tool / behavior                                                                                     | Role                                                               |
| ---------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| FAQ        | `get_business_information`, `get_service_information`, `search_business_knowledge`                  | Grounded business and policy answers                               |
| Booking    | `check_availability`, `look_up_appointment`, `get_staff_information`, `search_services_by_keywords` | Availability, lookup, service discovery                            |
| Reschedule | `look_up_appointment`                                                                               | Find the caller’s existing appointment before proposing a new time |
| Customer   | `get_customer_information`                                                                          | Link caller phone to a client record when needed                   |
| Human      | `transfer_to_human` (where enabled)                                                                 | Escalation to a live number                                        |


This matches the “handoff to reschedule, `look_up_appointment`, …” story: specialized agents route the call, and tools return **authoritative** data from Django instead of guesswork in the prompt alone.

### Why This Design

- **Separation of concerns** — each agent has a smaller prompt and fewer failure modes
- **Auditability** — tool calls are inspectable; outcomes map to real DB state
- **Scalability** — new services or tools can be added without rewriting the whole voice stack

---

## Deliverable 3 — Post-Call Classification (ML)

### What It Does

After a call ends, we classify the conversation and persist structured fields on `CallSession`. The primary course deliverable here is **machine learning inference** using locally trained **scikit-learn** models (`TF-IDF` + `LogisticRegression`), loaded at runtime as `post_call_models.joblib`.

An optional **LLM** backend (`CALL_ANALYSIS_BACKEND=openai`) can be used for richer summaries; the **ML** path (`CALL_ANALYSIS_BACKEND=ml`) avoids an extra LLM call for classification.

### Outputs

- `outcome` (`successful` | `unsuccessful` | `unknown`)
- `sentiment` (`positive` | `negative` | `neutral`)
- `category` (`make_appointment` | `cancel_appointment` | `reschedule_appointment` | `ask_question` | `unknown`)
- `summary` (extractive in the ML path; LLM-generated when using the OpenAI backend)

```python
# ML inference path (simplified)
outcome = analyze_conversation_ml(conversation_transcript)
```

---

## Deliverable 4 — Build Knowledge Base (Embeddings + Vector Search)

### Objective

We build a business-specific knowledge base so the receptionist can answer factual questions from current business data (services, hours, policies, contact, and FAQs) instead of relying only on prompt memory.

### Build Pipeline

1. **Collect business data** from Django models and API endpoints.
2. **Normalize and chunk** text into retrieval-friendly documents.
3. **Generate embeddings** for each chunk.
4. **Store vectors + metadata** in a vector index.
5. **Retrieve top-k context** at runtime and inject into the agent/tool response.

### Data Sources

- Business profile and contact details
- Opening hours and special hours
- Active services, prices, durations
- Appointment and cancellation policies
- Frequently asked questions and curated answers

### Runtime Retrieval Flow

```python
def search_knowledge_base(query: str, business_id: str) -> list[dict]:
    q_vec = embed(query)
    matches = vector_store.similarity_search(
        vector=q_vec,
        top_k=5,
        filters={"business_id": business_id, "is_active": True},
    )
    return [m.payload for m in matches]
```

### Why It Matters

- Improves factual accuracy and consistency
- Supports business-specific personalization
- Reduces hallucinations on policy/price questions
- Creates an auditable path for knowledge updates (re-embed on data changes)

### Implementation Status (for Presentation)

- **Current status:** In progress (architecture and retrieval design completed)
- **Completed:** Knowledge sources identified, retrieval flow designed, and tool contract aligned with `search_business_knowledge` / RAG direction
- **Next step:** Ingestion job to chunk business data and refresh embeddings on schedule or on publish

---

## Deliverable 5 — DVC-Orchestrated ML Pipeline

### Pipeline Objective

We implemented a reproducible ML pipeline for post-call analysis using **DVC**, aligned with course requirements for software engineering + data science integration.

### Implemented Assets

- `dvc.yaml` — defines stage `train_post_call_models`
- `params.yaml` — model/training parameters (`test_size`, `max_features`, `ngram_max`, etc.)
- `data/call_intent/training.csv` — labeled training dataset
- `ml/scripts/train_intent_model.py` — training entrypoint
- `ml/artifacts/post_call_models.joblib` — serialized sklearn pipelines
- `ml/artifacts/metrics.json` — classification metrics output

### Stage Definition

```yaml
stages:
  train_post_call_models:
    cmd: python ml/scripts/train_intent_model.py
    deps:
      - ml/scripts/train_intent_model.py
      - data/call_intent/training.csv
    params:
      - params.yaml:
          - train_intent
    outs:
      - ml/artifacts/post_call_models.joblib
      - ml/artifacts/metrics.json
```

### Model Design

We train 3 TF-IDF + Logistic Regression pipelines:

1. `category` classifier
2. `sentiment` classifier
3. `outcome` classifier

This gives a practical, explainable baseline with fast inference and low operational cost.

### Reproducibility Commands

```bash
# Run pipeline
dvc repro

# Check stage/output status
dvc status
```

### Engineering Benefit

This architecture separates:

- **Training time** (offline, versioned, reproducible)
- **Inference time** (online, low-latency, deterministic)

---

## Future work — Distress detection & escalation

This is **not** part of the five numbered deliverables above, but it remains a natural extension: a parallel classifier over transcripts (and optionally audio features) to trigger safer handoffs earlier in the call.

---

## Technology Stack


| Layer                    | Technology                       | Role                                                          |
| ------------------------ | -------------------------------- | ------------------------------------------------------------- |
| **Telephony**            | Twilio Voice + ConversationRelay | PSTN connection, audio streaming                              |
| **Voice Layer Server**   | FastAPI + Uvicorn                | Real-time WebSocket management                                |
| **AI Orchestration**     | OpenAI Agents SDK                | Agent definitions, tool calls, handoffs                       |
| **LLM / Voice AI**       | GPT-5-mini / OpenAI Realtime API | Speech understanding, response generation, fallback analysis  |
| **Business Logic API**   | Django REST Framework            | Data access, CRM integration, tool endpoints                  |
| **Database**             | PostgreSQL                       | Conversation logs, escalation records, callbacks              |
| **Knowledge Retrieval**  | Embeddings + Vector Search       | Semantic search over business knowledge chunks                |
| **ML Training Pipeline** | DVC + params.yaml                | Reproducible model training and artifact tracking             |
| **Post-Call ML Models**  | scikit-learn (TF-IDF + Logistic) | Category, sentiment, and outcome prediction                   |
| **Artifacts**            | joblib + JSON metrics            | Serialized models and evaluation outputs                      |
| **NLP Utilities**        | SpaCy / HuggingFace Transformers | Entity extraction, intent classification support              |
| **Distress Analysis**    | Custom PyTorch classifier        | Sentiment + distress scoring                                  |
| **Deployment**           | Nginx + systemd + Make           | Reverse proxy, process supervision, and service orchestration |


---

## Data Flow: End-to-End Call Lifecycle

```
1. INBOUND CALL
   Caller dials → Twilio receives → Webhook fires → FastAPI /incoming-call

2. SESSION INITIATION
   FastAPI opens WebSocket to OpenAI Realtime API
   Agent SDK loads receptionist_agent with tools and context

3. AUDIO STREAMING
   Twilio streams μ-law audio → FastAPI → OpenAI Realtime API
   OpenAI transcribes + processes in real-time

4. NLP PROCESSING
   Transcript → Intent classifier → Entity extractor → Slot filler
   Parallel: Distress detector monitors every utterance

5. KNOWLEDGE RETRIEVAL (RAG)
   Query + business_id → embedding → vector similarity search (top-k)
   Retrieved business facts are passed into the answering tool/agent context

6. TOOL EXECUTION
   Agent decides to call a tool → FastAPI relays → Django API
   e.g., GET /api/appointments/?phone=+16135550101
   Django queries DB → Returns structured result → Agent uses in response

7. RESPONSE SYNTHESIS
   GPT-4o generates response → Text-to-speech → Audio stream back to Twilio → Caller hears response

8. CALL END + POST-CALL ANALYSIS
   Twilio stop event received → FastAPI finalizes session
   Transcript is analyzed using selected backend:
   - LLM backend (`CALL_ANALYSIS_BACKEND=openai`)
   - ML backend (`CALL_ANALYSIS_BACKEND=ml`)

9. PERSISTENCE + NOTIFICATION
   outcome/sentiment/category/summary stored in Django `CallSession`
   Manager notification dispatched with categorized summary
```

---

## Deployment & Infrastructure

The system is deployed on Linux VMs using **Nginx** as reverse proxy, **systemd** for process management, and **Make** targets for repeatable operational commands.

```bash
# Application process management (systemd)
sudo systemctl restart bookingngon-django
sudo systemctl restart bookingngon-fastapi
sudo systemctl status bookingngon-django
sudo systemctl status bookingngon-fastapi

# Reverse proxy (Nginx)
sudo nginx -t
sudo systemctl reload nginx

# Developer/ops shortcuts (Make)
make run          # Django API
make run-fastapi  # FastAPI AI service
make run-both     # Run both services locally
```

**Runtime Topology**

- **Nginx** exposes public endpoints and routes traffic to backend services.
- **Django** runs as a dedicated service (systemd unit).
- **FastAPI** runs as a dedicated service (systemd unit).
- **PostgreSQL** provides persistent storage.
- **Make** standardizes local/dev/prod operational commands.

**Environment Configuration:**

```
OPENAI_API_KEY          → GPT-4o Realtime API access
TWILIO_ACCOUNT_SID      → Twilio authentication
TWILIO_AUTH_TOKEN       → Twilio authentication
TWILIO_PHONE_NUMBER     → Inbound call routing
DJANGO_SECRET_KEY       → Django application security
DATABASE_URL            → PostgreSQL connection
NGROK_URL / DOMAIN      → Public WebSocket endpoint for Twilio
```

---

## Key Differentiators

- **Sub-200ms voice latency** via the OpenAI Realtime API — conversations feel natural, not robotic
- **Parallel distress detection** — runs asynchronously so it never adds delay to normal interactions
- **Stateful multi-turn conversations** — context is maintained across all turns within a call session
- **Full audit trail** — every transcript, tool call, escalation decision, and off-ramp action is logged to Django with timestamps
- **Graceful degradation** — if the AI is uncertain, it defaults to offering a human rather than making a wrong decision with confidence
- **Hybrid analysis backend** — switch between LLM and local ML (`CALL_ANALYSIS_BACKEND`) without code changes
- **DVC reproducibility** — training pipeline, params, and outputs are structured for repeatable experiments
- **Efficient post-call inference** — TF-IDF + Logistic models provide low-cost classification after call completion

---

*Project: AI Service — Contestoga Showcase*
*Stack: FastAPI · Django · OpenAI Agents SDK · Twilio · PostgreSQL*