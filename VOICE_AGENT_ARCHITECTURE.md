# Voice Agent System - Complete Architecture

End-to-end service-based platform for Twilio Voice Agent integration.

---

## 📋 Database Models

### 1. `voice_agent_requests` Table
```sql
CREATE TABLE voice_agent_requests (
    id VARCHAR PRIMARY KEY,
    real_estate_agent_id VARCHAR NOT NULL REFERENCES real_estate_agents(id) ON DELETE CASCADE,
    status VARCHAR NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR REFERENCES admins(id), -- Admin who reviewed
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_voice_agent_request_agent ON voice_agent_requests(real_estate_agent_id) 
WHERE status = 'pending';
```

### 2. `voice_agents` Table
```sql
CREATE TABLE voice_agents (
    id VARCHAR PRIMARY KEY,
    real_estate_agent_id VARCHAR NOT NULL UNIQUE REFERENCES real_estate_agents(id) ON DELETE CASCADE,
    phone_number_id VARCHAR REFERENCES phone_numbers(id) ON DELETE SET NULL,
    name VARCHAR NOT NULL, -- Custom name: "Sarah", "Property Assistant", etc.
    system_prompt TEXT, -- Custom system prompt (if use_default_prompt = false)
    use_default_prompt BOOLEAN DEFAULT true,
    status VARCHAR NOT NULL DEFAULT 'pending_setup', -- 'active', 'inactive', 'pending_setup'
    settings JSONB DEFAULT '{}', -- Voice settings, greeting, commands
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Settings JSON Structure:**
```json
{
    "voice_gender": "female",  // "female" | "male"
    "voice_speed": "normal",    // "normal" | "slow" | "fast"
    "language": "en-US",
    "greeting_message": "Hello! How can I help you today?",
    "custom_commands": ["show properties", "schedule viewing", "contact agent"],
    "recording_enabled": true
}
```

### 3. `calls` Table (NEW - For Call Recording & Statistics)
```sql
CREATE TABLE calls (
    id VARCHAR PRIMARY KEY,
    voice_agent_id VARCHAR NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    real_estate_agent_id VARCHAR NOT NULL REFERENCES real_estate_agents(id) ON DELETE CASCADE,
    twilio_call_sid VARCHAR UNIQUE NOT NULL, -- Twilio Call SID
    contact_id VARCHAR REFERENCES contacts(id) ON DELETE SET NULL, -- If call was to a contact
    from_number VARCHAR NOT NULL, -- Caller's phone number
    to_number VARCHAR NOT NULL, -- Voice agent's Twilio number
    status VARCHAR NOT NULL, -- 'initiated', 'ringing', 'in-progress', 'completed', 'failed', 'busy', 'no-answer'
    direction VARCHAR NOT NULL, -- 'inbound' | 'outbound'
    duration_seconds INTEGER DEFAULT 0,
    recording_url TEXT, -- Twilio recording URL
    recording_sid VARCHAR, -- Twilio Recording SID
    transcript TEXT, -- STT transcript (if available)
    started_at TIMESTAMP WITH TIME ZONE,
    answered_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_calls_voice_agent ON calls(voice_agent_id);
CREATE INDEX idx_calls_agent ON calls(real_estate_agent_id);
CREATE INDEX idx_calls_created_at ON calls(created_at);
CREATE INDEX idx_calls_status ON calls(status);
```

---

## 🔌 API Endpoints

### Agent Endpoints

#### Voice Agent Management
```
POST   /agent/voice-agent/request
       Body: {} (no body needed, uses authenticated agent)
       Response: { "request_id": "...", "status": "pending" }

GET    /agent/voice-agent
       Response: VoiceAgentResponse (if approved) or 404

GET    /agent/voice-agent/status
       Response: { "status": "pending|approved|rejected", "rejection_reason": "..." }

PATCH  /agent/voice-agent
       Body: {
         "name": "Sarah",
         "use_default_prompt": false,
         "system_prompt": "Custom prompt...",
         "settings": { "voice_gender": "female", ... }
       }

POST   /agent/voice-agent/toggle-status
       Body: { "status": "active" | "inactive" }
```

#### Call Management (Agent)
```
GET    /agent/calls
       Query: ?page=1&page_size=20&status=completed
       Response: PaginatedCallsResponse

GET    /agent/calls/{call_id}
       Response: CallResponse with full details

GET    /agent/calls/{call_id}/recording
       Response: { "recording_url": "...", "recording_sid": "..." }

GET    /agent/calls/{call_id}/transcript
       Response: { "transcript": "..." }
```

### Admin Endpoints

#### Voice Agent Requests
```
GET    /admin/voice-agent-requests
       Query: ?status=pending&agent_id=...
       Response: List[VoiceAgentRequestResponse]

GET    /admin/voice-agent-requests/{request_id}
       Response: VoiceAgentRequestResponse

POST   /admin/voice-agent-requests/{request_id}/approve
       Response: { "voice_agent_id": "...", "phone_number": "..." }

POST   /admin/voice-agent-requests/{request_id}/reject
       Body: { "reason": "..." }
       Response: { "status": "rejected" }
```

#### Voice Agent Management (Admin)
```
GET    /admin/voice-agents
       Response: List[VoiceAgentResponse]

GET    /admin/voice-agents/{agent_id}
       Response: VoiceAgentResponse with full details
```

#### Call Statistics (Admin)
```
GET    /admin/voice-agents/{agent_id}/call-stats
       Query: ?period=day|week|month
       Response: {
         "period": "day",
         "total_calls": 45,
         "completed_calls": 42,
         "failed_calls": 3,
         "total_duration_seconds": 3600,
         "average_duration_seconds": 85,
         "calls_by_status": { "completed": 42, "failed": 3 },
         "calls_by_day": [ { "date": "2025-01-15", "count": 5 }, ... ]
       }
```

### Twilio Webhook Endpoints (Public - No Auth)
```
POST   /webhooks/twilio/voice
       Body: Twilio Voice Webhook (FormData)
       Response: TwiML XML

POST   /webhooks/twilio/status
       Body: Twilio Status Callback (FormData)
       Response: 200 OK

POST   /webhooks/twilio/recording
       Body: Twilio Recording Status Callback (FormData)
       Response: 200 OK
```

### Call Initiation Endpoints
```
POST   /agent/calls/initiate
       Body: { "contact_id": "...", "phone_number": "+1234567890" }
       Response: { "call_sid": "...", "status": "initiated" }

POST   /agent/calls/batch
       Body: { "contact_ids": ["...", "..."], "delay_seconds": 30 }
       Response: { "call_count": 5, "calls": [...] }
```

---

## 🔄 Complete Flow Diagrams

### Flow 1: Voice Agent Request & Approval
```
1. Agent Dashboard
   └─> "Request Voice Agent" button
       └─> POST /agent/voice-agent/request
           └─> Creates VoiceAgentRequest (status: pending)

2. Admin Dashboard
   └─> "Voice Agent Requests" section
       └─> Shows pending requests with agent info
           └─> Admin clicks "Approve"
               └─> POST /admin/voice-agent-requests/{id}/approve
                   ├─> Creates VoiceAgent record
                   ├─> Calls assign_phone_number_to_agent()
                   ├─> Links phone_number_id to VoiceAgent
                   ├─> Configures Twilio webhooks on phone number
                   └─> Sets status to 'active'

3. Agent Dashboard (after approval)
   └─> "Voice Agent" card appears
       └─> Shows: Status (Active), Phone Number, "Configure" button
           └─> Click "Configure"
               └─> GET /agent/voice-agent
                   └─> Shows configuration form
```

### Flow 2: Call Initiation & Recording
```
1. Agent initiates call
   └─> POST /agent/calls/initiate
       └─> Creates Call record (status: 'initiated')
       └─> Calls Twilio API to make outbound call
       └─> Returns call_sid

2. Twilio makes call
   └─> Call connects
       └─> POST /webhooks/twilio/status (status: 'in-progress')
           └─> Updates Call record
           └─> Starts recording (if enabled)

3. Voice interaction
   └─> POST /webhooks/twilio/voice (Gather speech)
       ├─> STT: Convert speech to text
       ├─> LLM: Process with OpenAI
       └─> TTS: Convert response to speech
       └─> Returns TwiML with response

4. Call ends
   └─> POST /webhooks/twilio/status (status: 'completed')
       └─> Updates Call record (duration, ended_at)
       └─> POST /webhooks/twilio/recording
           └─> Saves recording_url to Call record
```

### Flow 3: View Call Recordings
```
1. Agent Dashboard
   └─> "Call History" section
       └─> GET /agent/calls?page=1
           └─> Shows list of calls with:
               - Date/Time
               - Contact name (if linked)
               - Duration
               - Status
               - "Listen" button (if recording available)

2. Agent clicks "Listen"
   └─> GET /agent/calls/{id}/recording
       └─> Returns recording_url
       └─> Frontend plays audio from Twilio URL
```

### Flow 4: Admin View Statistics
```
1. Admin Dashboard
   └─> "Voice Agents" section
       └─> Shows list of agents with voice agents
           └─> Click on agent
               └─> GET /admin/voice-agents/{agent_id}/call-stats?period=week
                   └─> Shows:
                       - Total calls (week)
                       - Completed/Failed breakdown
                       - Average duration
                       - Calls per day chart
```

---

## 🎯 Service Layer Functions

### `voice_agent_service.py`
```python
async def request_voice_agent(agent_id: str) -> dict
async def get_voice_agent_request(agent_id: str) -> Optional[dict]
async def approve_voice_agent_request(request_id: str, admin_id: str) -> dict
async def reject_voice_agent_request(request_id: str, admin_id: str, reason: str) -> dict
async def get_voice_agent(agent_id: str) -> Optional[dict]
async def update_voice_agent(agent_id: str, update_data: dict) -> dict
async def toggle_voice_agent_status(agent_id: str, status: str) -> dict
async def get_default_system_prompt(agent_name: str, company_name: str) -> str
```

### `call_service.py` (NEW)
```python
async def initiate_call(agent_id: str, contact_id: Optional[str], phone_number: str) -> dict
async def initiate_batch_calls(agent_id: str, contact_ids: List[str], delay_seconds: int) -> dict
async def get_calls_by_agent(agent_id: str, page: int, page_size: int, status: Optional[str]) -> Tuple[List[dict], int]
async def get_call_by_id(call_id: str, agent_id: str) -> Optional[dict]
async def update_call_status(call_sid: str, status: str, duration: Optional[int]) -> Optional[dict]
async def save_recording(call_sid: str, recording_url: str, recording_sid: str) -> Optional[dict]
async def save_transcript(call_id: str, transcript: str) -> Optional[dict]
```

### `call_statistics_service.py` (NEW)
```python
async def get_call_statistics(agent_id: str, period: str) -> dict
# period: 'day' | 'week' | 'month'
# Returns: total_calls, completed_calls, failed_calls, duration stats, daily breakdown
```

### `twilio_webhook_service.py` (NEW)
```python
async def handle_voice_webhook(form_data: dict, voice_agent_id: str) -> str  # Returns TwiML XML
async def handle_status_webhook(form_data: dict) -> None
async def handle_recording_webhook(form_data: dict) -> None
async def process_speech_to_text(audio_url: str) -> str  # OpenAI Whisper
async def process_with_llm(transcript: str, system_prompt: str, context: dict) -> str  # OpenAI GPT
async def text_to_speech(text: str, voice_settings: dict) -> str  # OpenAI TTS
```

---

## 📊 Pydantic Schemas

### Voice Agent Schemas
```python
class VoiceAgentRequestResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    status: str
    requested_at: str
    reviewed_at: Optional[str]
    rejection_reason: Optional[str]

class VoiceAgentResponse(BaseModel):
    id: str
    real_estate_agent_id: str
    phone_number_id: Optional[str]
    phone_number: Optional[str]  # Twilio number
    name: str
    system_prompt: Optional[str]
    use_default_prompt: bool
    status: str
    settings: dict

class VoiceAgentUpdateRequest(BaseModel):
    name: Optional[str]
    use_default_prompt: Optional[bool]
    system_prompt: Optional[str]
    settings: Optional[dict]
```

### Call Schemas
```python
class CallResponse(BaseModel):
    id: str
    voice_agent_id: str
    real_estate_agent_id: str
    twilio_call_sid: str
    contact_id: Optional[str]
    contact_name: Optional[str]
    from_number: str
    to_number: str
    status: str
    direction: str
    duration_seconds: int
    recording_url: Optional[str]
    transcript: Optional[str]
    started_at: Optional[str]
    answered_at: Optional[str]
    ended_at: Optional[str]
    created_at: str

class PaginatedCallsResponse(BaseModel):
    items: List[CallResponse]
    total: int
    page: int
    page_size: int

class CallStatisticsResponse(BaseModel):
    period: str
    total_calls: int
    completed_calls: int
    failed_calls: int
    total_duration_seconds: int
    average_duration_seconds: float
    calls_by_status: dict
    calls_by_day: List[dict]
```

---

## 🎨 Default System Prompts

### Professional Real Estate Assistant
```
"You are a professional real estate assistant for {agent_name} at {company_name}. 
You help potential clients with property inquiries, schedule viewings, and provide 
information about available properties. Be friendly, professional, and helpful. 
Always confirm important details like property addresses and viewing times. 
Keep responses concise and informative."
```

### Property Specialist
```
"You are a knowledgeable real estate assistant specializing in property listings. 
You can answer questions about property features, pricing, availability, and location. 
You can schedule property viewings and connect callers with the real estate agent 
for detailed discussions. Be concise, informative, and professional. 
If you don't know something, offer to connect them with the agent directly."
```

---

## 🔐 Security Considerations

1. **Webhook Authentication:**
   - Validate Twilio signature on webhook requests
   - Use `twilio.request_validator` to verify requests

2. **Agent Isolation:**
   - Agents can only access their own calls/voice agents
   - Admin can view all but cannot modify agent settings

3. **Recording Privacy:**
   - Recordings stored securely in Twilio
   - Only accessible to the agent who owns the voice agent
   - Admin can see statistics but not recordings

---

## 📝 Implementation Checklist

### Phase 1: Database & Models
- [ ] Create `voice_agent_requests` model
- [ ] Create `voice_agents` model
- [ ] Create `calls` model
- [ ] Create Alembic migration
- [ ] Run migration

### Phase 2: Voice Agent Management
- [ ] Create voice agent schemas
- [ ] Create voice agent service
- [ ] Create agent endpoints (request, get, update)
- [ ] Create admin endpoints (list, approve, reject)
- [ ] Integrate phone number assignment

### Phase 3: Call System
- [ ] Create call schemas
- [ ] Create call service
- [ ] Create call initiation endpoints
- [ ] Create call listing endpoints (agent)
- [ ] Create call statistics service (admin)

### Phase 4: Twilio Integration
- [ ] Create Twilio webhook handlers
- [ ] Implement STT (OpenAI Whisper)
- [ ] Implement LLM (OpenAI GPT)
- [ ] Implement TTS (OpenAI TTS)
- [ ] Implement TwiML generation
- [ ] Configure call recording

### Phase 5: Frontend (Separate)
- [ ] Voice agent request UI
- [ ] Voice agent configuration UI
- [ ] Call history/listening interface
- [ ] Admin approval interface
- [ ] Statistics dashboard

---

## 🚀 Next Steps

1. **Complete Twilio Setup** (follow TWILIO_SETUP_GUIDE.md)
2. **Start Implementation** (follow checklist above)
3. **Test with ngrok** (local development)
4. **Deploy to production** (with proper webhook URLs)

---

**Ready to build!** 🎉

