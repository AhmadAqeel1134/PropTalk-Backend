"""
PropTalk Voice Agent - Core Algorithm Pseudocode
Main Algorithm: STT → LLM → TTS Pipeline
"""

async def handle_voice_webhook(form_data):
    """
    Main entry point: Orchestrates STT → Context Building → LLM → TTS pipeline
    """
    
    # PHASE 1: Extract Call Information & Determine Direction
    call_sid = form_data.get("CallSid")
    from_number = form_data.get("From")
    to_number = form_data.get("To")
    direction = form_data.get("Direction")
    speech_result = form_data.get("SpeechResult", "")
    
    is_outbound = direction.startswith("outbound")  # Determine call direction
    twilio_number = from_number if is_outbound else to_number
    
    # PHASE 2: Voice Agent Lookup (Cached or Database Query)
    cached_data = get_cached_phone_data(twilio_number)
    
    if cached_data:
        voice_agent_id = cached_data["voice_agent_id"]
        voice_agent_name = cached_data["voice_agent_name"]
        real_estate_agent_id = cached_data["real_estate_agent_id"]
    else:
        # Database lookup with optimized query
        phone_record = await database.query(
            PhoneNumber.join(VoiceAgent).where(
                PhoneNumber.twilio_phone_number == twilio_number
            )
        )
        voice_agent_id = phone_record.voice_agent_id
        voice_agent_name = phone_record.voice_agent_name
        real_estate_agent_id = phone_record.real_estate_agent_id
        
        # Cache for future requests
        cache_phone_data(twilio_number, {
            "voice_agent_id": voice_agent_id,
            "voice_agent_name": voice_agent_name,
            "real_estate_agent_id": real_estate_agent_id
        })
    
    # PHASE 3: Check if User Spoke (Continuation) or Initial Call
    is_continuation = bool(speech_result and speech_result.strip())
    
    if is_continuation:
        # USER SPOKE - Process with LLM Pipeline
        conversation_state = get_conversation_state(call_sid) or \
            create_conversation_state(
                call_sid, direction, {}, 
                voice_agent_id, real_estate_agent_id
            )
        
        update_conversation_history(call_sid, "user", speech_result)
        history = get_conversation_history(call_sid)
        context = conversation_state.get("context", {})
        
        # Build context-aware prompt
        if is_outbound:
            system_prompt = build_outbound_prompt(context)
        else:
            system_prompt = build_inbound_prompt(context)
        
        try:
            # Process with Google Gemini LLM
            llm_response = await process_with_llm(
                user_input=speech_result,
                system_prompt=system_prompt,
                conversation_history=history,
                max_tokens=150,
                timeout=3.5
            )
            
            update_conversation_history(call_sid, "assistant", llm_response)
            
            # Check if call should end
            if should_end_call(speech_result, llm_response, conversation_state):
                return generate_twiml_with_hangup(llm_response)
            
            return generate_twiml_with_speech(llm_response)
            
        except TimeoutError:
            # Fallback on timeout
            fallback = generate_natural_fallback(
                speech_result, conversation_state, is_outbound
            )
            return generate_twiml_with_speech(fallback)
    
    else:
        # INITIAL CALL - Generate Personalized Greeting
        conversation_state = create_conversation_state(
            call_sid, direction, {}, 
            voice_agent_id, real_estate_agent_id
        )
        
        if is_outbound:
            # Quick contact lookup
            contact = await database.query(
                Contact.where(phone_number == to_number)
            )
            contact_name = contact.name if contact else None
            
            greeting_context = {
                "voice_agent": {"name": voice_agent_name},
                "real_estate_agent": {
                    "name": agent_name, 
                    "company": company_name
                },
                "contact": {"name": contact_name} if contact_name else {}
            }
        else:
            greeting_context = {
                "voice_agent": {"name": voice_agent_name},
                "real_estate_agent": {
                    "name": agent_name, 
                    "company": company_name
                }
            }
        
        try:
            # LLM-generated greeting
            greeting_prompt = get_initial_greeting_prompt(
                greeting_context, direction
            )
            greeting = await generate_initial_greeting(
                greeting_prompt, timeout=2.5
            )
        except TimeoutError:
            # Fallback greeting
            if is_outbound and contact_name:
                greeting = f"Hello, this is {voice_agent_name}. " \
                          f"Am I contacting {contact_name}?"
            else:
                greeting = f"Hello, this is {voice_agent_name}. " \
                          f"How can I help you?"
        
        update_conversation_history(call_sid, "assistant", greeting)
        return generate_twiml_with_speech(greeting)
    
    # PHASE 4: Background Tasks (Non-blocking)
    asyncio.create_task(background_tasks(
        call_sid, is_outbound, 
        voice_agent_id, real_estate_agent_id
    ))


async def build_outbound_context(contact_id, real_estate_agent_id, voice_agent_id):
    """
    Build rich context for outbound calls: 
    Contact info, Properties, Agent details
    """
    # Query contact information
    contact = await database.query(Contact.where(id == contact_id))
    
    # Query contact's properties
    properties = await database.query(
        Property.where(contact_id == contact_id)
    )
    
    # Query voice agent configuration
    voice_agent = await database.query(
        VoiceAgent.where(id == voice_agent_id)
    )
    
    # Query real estate agent information
    agent = await database.query(
        RealEstateAgent.where(id == real_estate_agent_id)
    )
    
    # Format properties for context
    properties_list = []
    for prop in properties:
        properties_list.append({
            "address": prop.address,
            "price": prop.price,
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "square_feet": prop.square_feet
        })
    
    # Build context dictionary
    return {
        "contact": {
            "name": contact.name,
            "phone_number": contact.phone_number,
            "email": contact.email
        },
        "properties": properties_list,
        "voice_agent": {"name": voice_agent.name},
        "real_estate_agent": {
            "name": agent.full_name,
            "company_name": agent.company_name
        }
    }


async def build_inbound_context(real_estate_agent_id, voice_agent_id, caller_phone):
    """
    Build rich context for inbound calls: 
    Available properties, Caller info
    """
    # Query all available properties
    properties = await database.query(
        Property.where(
            real_estate_agent_id == real_estate_agent_id,
            is_available == True
        )
    )
    
    # Check if caller is existing contact
    caller_contact = await database.query(
        Contact.where(phone_number == caller_phone)
    )
    
    # Format properties summary
    properties_summary = format_properties_for_prompt(properties)
    
    # Build context dictionary
    return {
        "voice_agent": {"name": voice_agent.name},
        "real_estate_agent": {
            "name": agent.full_name,
            "company_name": agent.company_name
        },
        "properties": [
            {
                "address": p.address,
                "price": p.price,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms
            } for p in properties
        ],
        "properties_summary": properties_summary,
        "total_properties": len(properties),
        "caller_contact": caller_contact if caller_contact else None
    }


def build_outbound_prompt(context):
    """
    Generate dynamic system prompt for outbound calls 
    with injected context variables
    """
    template = (
        "You are {voice_agent_name}, a professional real estate assistant "
        "speaking on behalf of {agent_name} at {company_name}.\n"
        "CALL TYPE: OUTBOUND CALL\n"
        "You are calling: {contact_name} at {contact_phone}\n"
        "Contact has {property_count} property/properties\n"
        "PROPERTIES:\n{properties_text}\n"
        "YOUR ROLE:\n"
        "1. Verify you're speaking with {contact_name}\n"
        "2. Confirm property details\n"
        "3. Ask about property condition\n"
        "4. Ask if interested in selling\n"
        "5. Gather information\n"
        "6. Answer questions"
    )
    
    return template.format(
        voice_agent_name=context["voice_agent"]["name"],
        agent_name=context["real_estate_agent"]["name"],
        company_name=context["real_estate_agent"]["company_name"],
        contact_name=context["contact"]["name"],
        contact_phone=context["contact"]["phone_number"],
        property_count=len(context["properties"]),
        properties_text=format_properties_text(context["properties"])
    )


def build_inbound_prompt(context):
    """
    Generate dynamic system prompt for inbound calls 
    with injected context variables
    """
    template = (
        "You are {voice_agent_name} from {company_name} "
        "calling on behalf of {agent_name}.\n"
        "CALL TYPE: INBOUND CALL\n"
        "Total available properties: {total_properties}\n"
        "AVAILABLE PROPERTIES:\n{properties_summary}\n"
        "YOUR ROLE:\n"
        "1. Introduce yourself\n"
        "2. Help caller find properties\n"
        "3. Answer property questions\n"
        "4. Filter properties by criteria\n"
        "5. Provide property details"
    )
    
    return template.format(
        voice_agent_name=context["voice_agent"]["name"],
        company_name=context["real_estate_agent"]["company_name"],
        agent_name=context["real_estate_agent"]["name"],
        total_properties=context["total_properties"],
        properties_summary=context["properties_summary"]
    )


async def process_with_llm(user_input, system_prompt, conversation_history, 
                           max_tokens=150, timeout=3.5):
    """
    Process user input with Google Gemini LLM API: 
    Build request, call API, extract response
    """
    # Format conversation history for Gemini API
    contents = []
    for msg in conversation_history:
        if msg["role"] in ["user", "assistant"]:
            contents.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["content"]}]
            })
    
    # Add current user input
    contents.append({
        "role": "user",
        "parts": [{"text": user_input}]
    })
    
    # Build API request payload
    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7
        }
    }
    
    # Call Gemini API with timeout
    response = await asyncio.wait_for(
        http_client.post(GEMINI_API_URL, json=payload),
        timeout=timeout
    )
    
    # Extract and return response text
    return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def get_conversation_state(call_sid):
    """
    Get conversation state from in-memory storage, 
    check expiration (TTL: 1 hour)
    """
    if call_sid in conversation_states:
        state = conversation_states[call_sid]
        
        # Check if expired
        if datetime.now() - state["created_at"] > timedelta(hours=1):
            del conversation_states[call_sid]
            return None
        
        return state
    
    return None


def create_conversation_state(call_sid, direction, context, 
                             voice_agent_id, real_estate_agent_id):
    """
    Create new conversation state: 
    Store call metadata, initialize history, set timestamps
    """
    state = {
        "call_sid": call_sid,
        "direction": direction,
        "context": context,
        "history": [],
        "voice_agent_id": voice_agent_id,
        "real_estate_agent_id": real_estate_agent_id,
        "created_at": datetime.now(),
        "turn_count": 0
    }
    
    conversation_states[call_sid] = state
    return state


def update_conversation_history(call_sid, role, content):
    """
    Add message to conversation history, update turn count
    """
    state = get_conversation_state(call_sid)
    if not state:
        return False
    
    state["history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now()
    })
    
    state["turn_count"] = len([
        h for h in state["history"] if h["role"] == "user"
    ])
    
    return True


def should_end_call(user_input, llm_response, conversation_state, is_outbound):
    """
    Determine if call should be terminated: 
    Check for wrong person, not interested, ending keywords
    """
    user_lower = user_input.lower()
    
    wrong_person = [
        "wrong person", "wrong number", "not me", 
        "that's not me", "this is not"
    ]
    not_interested = [
        "not interested", "don't want", 
        "not selling", "no interest"
    ]
    ending = ["no questions", "that's all", "goodbye", "bye"]
    
    # Check for termination keywords
    if any(k in user_lower for k in wrong_person + not_interested + ending):
        return True
    
    # Check LLM response for ending signals
    if "goodbye" in llm_response.lower() or \
       "have a great day" in llm_response.lower():
        return True
    
    return False


def generate_twiml_with_speech(text):
    """
    Generate TwiML XML: 
    Convert text to speech, gather next speech input, handle redirect
    """
    response = VoiceResponse()
    response.say(text, voice="alice")  # Text-to-Speech output
    
    # Gather speech for next turn
    gather = Gather(
        input="speech",
        action=WEBHOOK_URL,
        method="POST",
        timeout=5,
        speech_timeout="auto",
        language="en-US"
    )
    response.append(gather)
    
    # Redirect if no speech detected
    response.redirect(WEBHOOK_URL, method="POST")
    
    return str(response)


async def background_tasks(call_sid, is_outbound, voice_agent_id, 
                          real_estate_agent_id):
    """
    Execute non-critical background tasks: 
    Update call record, build full context if needed
    """
    # Task 1: Update call record
    await update_call_record(
        call_sid, is_outbound, 
        voice_agent_id, real_estate_agent_id
    )
    
    # Task 2: Build full context if not already built
    conversation_state = get_conversation_state(call_sid)
    if conversation_state and not conversation_state.get("context"):
        if is_outbound:
            call_record = await database.query(
                Call.where(twilio_call_sid == call_sid)
            )
            if call_record and call_record.contact_id:
                conversation_state["context"] = await build_outbound_context(
                    call_record.contact_id,
                    real_estate_agent_id,
                    voice_agent_id
                )
        else:
            conversation_state["context"] = await build_inbound_context(
                real_estate_agent_id,
                voice_agent_id,
                from_number
            )
"""
MAIN ALGORITHM FLOW:
1. Webhook Received
   ↓
2. Extract Call Metadata (From, To, CallSid, Direction, SpeechResult)
   ↓
3. Lookup Voice Agent (Cached/DB)
   ↓
4. Check Initial Call or Continuation
   ↓
5a. IF Initial: 
    - Create State
    - Build Greeting Context
    - Generate Greeting (LLM)
    - Return TwiML
   ↓
5b. IF Continuation:
    - Get State
    - Add User Message
    - Get Context
    - Build Prompt
    - Process LLM
    - Add Response
    - Check Termination
    - Return TwiML
   ↓
6. Schedule Background Tasks:
    - Update Call Record
    - Build Full Context (if needed)
   ↓
7. Return TwiML Response (< 3 seconds)

PERFORMANCE TARGETS:
- Database Lookup: < 500ms
- TwiML Generation: < 1s
- LLM Processing: < 3.5s
- Total Response: < 3s
"""

