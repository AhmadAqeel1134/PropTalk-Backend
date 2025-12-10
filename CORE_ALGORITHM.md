# PropTalk Backend - Core Algorithm Documentation

## Main Working Algorithm: STT → LLM → TTS Pipeline

The core algorithm of PropTalk Backend is the **Intelligent Voice Conversation Pipeline** that enables real-time, AI-powered voice interactions between voice agents and callers. This algorithm orchestrates Speech-to-Text (STT), Large Language Model (LLM) processing, and Text-to-Speech (TTS) to create natural, context-aware conversations.

---

## Algorithm Overview

### Core Pipeline: STT → LLM → TTS

```
┌─────────────────────────────────────────────────────────────────┐
│                    VOICE CONVERSATION PIPELINE                   │
└─────────────────────────────────────────────────────────────────┘

1. SPEECH INPUT (Twilio STT)
   ↓
2. CONTEXT BUILDING (Database + State Management)
   ↓
3. PROMPT GENERATION (Dynamic Context-Aware Prompts)
   ↓
4. LLM PROCESSING (Google Gemini - Natural Language Understanding)
   ↓
5. RESPONSE GENERATION (Context-Aware Conversational Response)
   ↓
6. SPEECH OUTPUT (Twilio TTS)
   ↓
7. CONVERSATION STATE UPDATE (History & Context Persistence)
```

---

## Algorithm Components

### 1. Speech-to-Text (STT) Layer
**Location:** `app/services/twilio_service/webhook_service.py`

**Function:** Captures user speech from phone calls and converts it to text

**Implementation:**
- Uses Twilio's built-in Speech Recognition API
- Captures speech via `<Gather>` TwiML verb
- Processes speech in real-time during conversation
- Extracts `SpeechResult` from webhook form data

**Key Code:**
```python
speech_result = form_data.get("SpeechResult", "")
gather = Gather(
    input="speech",
    action=voice_webhook_url,
    method="POST",
    timeout=5,
    speech_timeout="auto",
    language="en-US"
)
```

**Crucial Features:**
- Real-time speech capture with automatic timeout
- Language-specific recognition (en-US)
- Handles silence and speech interruptions
- Returns text immediately for LLM processing

---

### 2. Context Building Service
**Location:** `app/services/ai/context_service.py`

**Function:** Builds rich, dynamic context from database for LLM responses

**Two Context Types:**

#### A. Outbound Context (For Calling Contacts)
**Algorithm:**
1. Query Contact table by contact_id
2. Query all Properties linked to contact
3. Query VoiceAgent configuration
4. Query RealEstateAgent information
5. Format property details (address, price, bedrooms, bathrooms, etc.)
6. Build structured context dictionary

**Key Data Structures:**
```python
context = {
    "contact": {
        "name": "Ali Khan",
        "phone_number": "+923331234567",
        "email": "ali.khan@example.com"
    },
    "properties": [
        {
            "address": "House 123, Bahria Town",
            "price": "$450,000",
            "bedrooms": 5,
            "bathrooms": 4,
            "square_feet": 3200
        }
    ],
    "voice_agent": {
        "name": "Sarah",
        "system_prompt": "..."
    },
    "real_estate_agent": {
        "name": "John Doe",
        "company_name": "ABC Realty"
    }
}
```

#### B. Inbound Context (For Receiving Calls)
**Algorithm:**
1. Query VoiceAgent configuration
2. Query RealEstateAgent information
3. Query all available properties (is_available = true)
4. Optionally check if caller is existing contact
5. Group properties by type and city
6. Build properties summary for prompt

**Crucial Features:**
- **Read-only operations** - No database writes during context building
- **Optimized queries** - Single query with joins where possible
- **Caching support** - Context can be cached for performance
- **Error handling** - Graceful fallback if context building fails

---

### 3. Prompt Generation Service
**Location:** `app/services/ai/prompt_service.py`

**Function:** Generates dynamic, context-aware system prompts for LLM

**Algorithm:**
1. Receive context dictionary from context service
2. Determine call type (outbound/inbound)
3. Select appropriate prompt template
4. Inject context variables into template:
   - Contact name, phone number
   - Property details (address, price, bedrooms, bathrooms)
   - Voice agent name
   - Real estate agent name and company
   - Current date
5. Format properties list as structured text
6. Return complete system prompt

**Prompt Templates:**

#### Outbound Prompt Structure:
```
You are {voice_agent_name}, a professional real estate assistant 
speaking on behalf of {agent_name} at {company_name}.

CALL TYPE: OUTBOUND CALL
You are calling: {contact_name} at {contact_phone}
Contact has {property_count} property/properties

PROPERTIES:
{properties_text}  # Formatted property details

YOUR ROLE:
1. Verify you're speaking with {contact_name}
2. Confirm property details
3. Ask about property condition
4. Ask if interested in selling
5. Gather information
6. Answer questions

CONVERSATION FLOW:
[Detailed step-by-step conversation flow]
```

#### Inbound Prompt Structure:
```
You are {voice_agent_name} from {company_name}
Calling on behalf of {agent_name}

CALL TYPE: INBOUND CALL
Total available properties: {total_properties}

AVAILABLE PROPERTIES:
{properties_summary}  # All available properties

YOUR ROLE:
1. Introduce yourself
2. Help caller find properties
3. Answer property questions
4. Filter properties by criteria
5. Provide property details
```

**Crucial Features:**
- **Dynamic injection** - All context variables automatically inserted
- **Conversation flow guidance** - Step-by-step instructions for LLM
- **Error handling** - Handles wrong person, not interested, etc.
- **Natural language** - Prompts written in natural English for LLM understanding

---

### 4. LLM Processing Service
**Location:** `app/services/ai/llm_service.py`

**Function:** Processes user input with Google Gemini API to generate natural responses

**Algorithm:**
1. Receive user input (from STT)
2. Receive system prompt (from prompt service)
3. Receive conversation history (from state manager)
4. Format conversation history for Gemini API
5. Build API request payload:
   - Contents array (conversation history + current input)
   - System instruction (system prompt)
   - Generation config (max tokens, temperature)
6. Call Gemini API with timeout protection
7. Extract response text from API response
8. Return natural language response

**API Integration:**
```python
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"

payload = {
    "contents": [
        {"role": "user", "parts": [{"text": "previous message"}]},
        {"role": "model", "parts": [{"text": "previous response"}]},
        {"role": "user", "parts": [{"text": "current user input"}]}
    ],
    "systemInstruction": {
        "parts": [{"text": system_prompt}]
    },
    "generationConfig": {
        "maxOutputTokens": 150,
        "temperature": 0.7
    }
}
```

**Model Configuration:**
- **Model:** `gemini-2.5-flash-lite` (optimized for low latency)
- **Max Tokens:** 150-200 (concise responses)
- **Temperature:** 0.7 (balanced creativity/consistency)
- **Timeout:** 3.5-4.0 seconds (critical for real-time)

**Crucial Features:**
- **Conversation history support** - Maintains context across turns
- **Timeout protection** - Prevents blocking on slow API responses
- **Error handling** - Graceful fallback on API failures
- **Token optimization** - Limits response length for natural conversation flow
- **Fast response** - Target < 1 second for best user experience

---

### 5. Conversation State Management
**Location:** `app/services/conversation/state_manager.py`

**Function:** Manages conversation state, history, and context in memory

**Algorithm:**
1. Create conversation state on call start:
   - Store call_sid as key
   - Store direction (inbound/outbound)
   - Store context dictionary
   - Initialize empty history array
   - Store metadata (voice_agent_id, real_estate_agent_id, contact_id)
2. Update history on each turn:
   - Add user message with role "user"
   - Add assistant response with role "assistant"
   - Track turn count
   - Update timestamp
3. Retrieve history for LLM:
   - Get conversation state by call_sid
   - Extract history array
   - Format for LLM API
4. Cleanup expired states:
   - TTL: 1 hour
   - Automatic cleanup on access

**Data Structure:**
```python
conversation_state = {
    "call_sid": "CA1234567890",
    "direction": "outbound",
    "context": {...},  # Full context from context_service
    "history": [
        {"role": "assistant", "content": "Hello...", "timestamp": "..."},
        {"role": "user", "content": "Yes, this is Ali", "timestamp": "..."},
        {"role": "assistant", "content": "Thank you...", "timestamp": "..."}
    ],
    "voice_agent_id": "...",
    "real_estate_agent_id": "...",
    "contact_id": "...",
    "created_at": datetime,
    "updated_at": datetime,
    "turn_count": 2
}
```

**Crucial Features:**
- **In-memory storage** - Fast access, no database latency
- **Automatic expiration** - TTL prevents memory leaks
- **History tracking** - Complete conversation record
- **Context caching** - Avoids repeated database queries
- **Thread-safe** - Handles concurrent calls

---

### 6. Text-to-Speech (TTS) Layer
**Location:** `app/services/twilio_service/webhook_service.py`

**Function:** Converts LLM text response to speech output

**Implementation:**
- Uses Twilio's built-in TTS engine
- Converts LLM response text to speech via `<Say>` TwiML verb
- Uses natural voice ("alice" - female voice)
- Returns TwiML XML for Twilio to process

**Key Code:**
```python
response = VoiceResponse()
response.say(llm_response, voice="alice")
return str(response)  # Returns TwiML XML
```

**Crucial Features:**
- **Natural voice** - Human-like speech synthesis
- **Immediate output** - No external API calls needed
- **Language support** - Configurable language settings
- **Voice selection** - Can use different voices (male/female)

---

## Complete Algorithm Flow

### Phase 1: Initial Call Setup (< 500ms)
```
1. Twilio webhook received
2. Extract call metadata (From, To, CallSid, Direction)
3. Determine call direction (inbound/outbound)
4. Lookup voice agent (cached or database)
5. Validate voice agent is active
6. Create conversation state
```

### Phase 2: Context Building (Background, Non-blocking)
```
1. If outbound:
   - Query contact by phone number
   - Query contact's properties
   - Build outbound context
2. If inbound:
   - Query all available properties
   - Check if caller is existing contact
   - Build inbound context
3. Update conversation state with context
```

### Phase 3: Initial Greeting Generation (< 2.5s)
```
1. Build greeting prompt with context
2. Call LLM to generate personalized greeting
3. If timeout/error: Use fallback greeting
4. Add greeting to conversation history
5. Return TwiML with greeting + speech gather
```

### Phase 4: Conversation Loop (Per Turn, < 3.5s)
```
1. User speaks → Twilio STT captures speech
2. Extract SpeechResult from webhook
3. Get conversation state and history
4. Build system prompt from context
5. Call LLM with:
   - User input (speech result)
   - System prompt (context-aware)
   - Conversation history
6. Generate response (timeout: 3.5s)
7. If timeout/error: Use natural fallback
8. Update conversation history
9. Check if call should end (wrong person, not interested, etc.)
10. Return TwiML with response + speech gather
11. Repeat until call ends
```

### Phase 5: Call Termination
```
1. Detect termination conditions:
   - Wrong person
   - Not interested
   - No more questions
   - LLM indicates ending
2. Send hangup command
3. Clear conversation state
4. Update call record in database
```

---

## Crucial Algorithm Features

### 1. Performance Optimization
**Requirement:** Must respond within 3 seconds (Twilio timeout)

**Optimizations:**
- **Caching:** Phone number lookups cached for 5 minutes
- **Background tasks:** Context building runs in background
- **Minimal database queries:** Single optimized query for voice agent lookup
- **Timeout protection:** All LLM calls have timeout limits
- **Fast fallbacks:** Natural language fallbacks if LLM fails

**Performance Targets:**
- Database lookup: < 500ms
- TwiML generation: < 1 second
- LLM processing: < 3.5 seconds
- Total response time: < 3 seconds

### 2. Context-Aware Intelligence
**Feature:** LLM responses are contextually aware of:
- Contact information (name, phone, email)
- Property details (address, price, bedrooms, bathrooms)
- Real estate agent information
- Conversation history
- Call direction (inbound/outbound)

**Implementation:**
- Dynamic prompt generation based on context
- Conversation history maintained across turns
- Property filtering for inbound calls
- Contact verification for outbound calls

### 3. Natural Conversation Flow
**Feature:** Maintains natural, human-like conversation flow

**Algorithm Components:**
- **Greeting generation:** Personalized initial greeting
- **Turn management:** Tracks conversation turns
- **Context switching:** Adapts to conversation direction
- **Error recovery:** Natural fallbacks on errors
- **Termination detection:** Intelligently ends calls when appropriate

### 4. Error Handling & Resilience
**Feature:** System continues functioning even when components fail

**Error Handling Strategies:**
- **LLM timeout:** Natural language fallback responses
- **API quota exceeded:** Graceful degradation with fallbacks
- **Database errors:** Fallback prompts without context
- **Missing data:** Default values and error messages
- **Network issues:** Retry logic and timeouts

### 5. State Management
**Feature:** Maintains conversation state across multiple webhook calls

**State Management:**
- **In-memory storage:** Fast access for active calls
- **History tracking:** Complete conversation record
- **Context caching:** Avoids repeated database queries
- **Automatic cleanup:** Expires old states after 1 hour
- **Thread safety:** Handles concurrent calls

### 6. Call Direction Intelligence
**Feature:** Different behavior for inbound vs outbound calls

**Outbound Call Algorithm:**
1. Verify contact identity
2. Confirm property details
3. Gather property information
4. Assess selling interest
5. Answer questions about selling process

**Inbound Call Algorithm:**
1. Introduce voice agent
2. Help find matching properties
3. Filter by criteria (bedrooms, price, location)
4. Provide property details
5. Answer questions about properties

---

## Algorithm Complexity

### Time Complexity
- **Database Lookup:** O(1) with indexing
- **Context Building:** O(n) where n = number of properties
- **LLM Processing:** O(1) - API call (external)
- **State Management:** O(1) - Hash map lookup
- **Overall per turn:** O(n) where n = properties count (typically < 20)

### Space Complexity
- **Conversation States:** O(m) where m = active calls
- **Context Storage:** O(n) where n = properties per call
- **History Storage:** O(t) where t = conversation turns
- **Overall:** O(m × (n + t)) - Linear with active calls

---

## Key Algorithm Files

1. **Main Orchestrator:**
   - `app/services/twilio_service/webhook_service.py` - Handles webhook, orchestrates pipeline

2. **Context Building:**
   - `app/services/ai/context_service.py` - Builds rich context from database

3. **Prompt Generation:**
   - `app/services/ai/prompt_service.py` - Generates dynamic prompts

4. **LLM Processing:**
   - `app/services/ai/llm_service.py` - Processes with Google Gemini

5. **State Management:**
   - `app/services/conversation/state_manager.py` - Manages conversation state

---

## Algorithm Advantages

1. **Real-time Processing:** Responds within 3 seconds
2. **Context-Aware:** Understands full conversation context
3. **Natural Language:** Human-like conversation flow
4. **Scalable:** Handles multiple concurrent calls
5. **Resilient:** Continues functioning with component failures
6. **Intelligent:** Adapts to conversation direction and context
7. **Efficient:** Optimized queries and caching reduce latency

---

## Summary

The core algorithm is a **real-time, context-aware, AI-powered voice conversation pipeline** that:
- Captures speech via Twilio STT
- Builds rich context from database
- Generates dynamic prompts
- Processes with Google Gemini LLM
- Maintains conversation state and history
- Outputs natural speech via Twilio TTS

This algorithm enables PropTalk to conduct intelligent, natural conversations with callers about real estate properties, making it the **crucial feature** that differentiates PropTalk from traditional phone systems.

