# Third-Party APIs and SDKs Used in PropTalk Project

## Backend

| Service/API/SDK | Version | Type | Purpose | Endpoint/Connection |
|-----------------|---------|------|---------|---------------------|
| Twilio / Twilio SDK | 8.10.0 | SDK | Voice calls, Speech-to-Text (STT), Text-to-Speech (TTS), phone number management | twilio.rest.Client<br>client.calls.create()<br>client.incoming_phone_numbers.create()<br>client.available_phone_numbers().local.list()<br>twilio.twiml.voice_response.VoiceResponse<br>twilio.twiml.voice_response.Gather |
| Google Gemini / Google Gemini API | gemini-2.5-flash-lite | API | Generate conversational responses for voice agent interactions | https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent |
| Cloudinary / Cloudinary SDK | 1.41.0 | SDK | Uploading and storing property images, documents, and files | cloudinary.uploader.upload()<br>cloudinary.uploader.destroy()<br>https://api.cloudinary.com/v1_1/{cloud_name}/upload |
| Google OAuth / Google OAuth SDK | 2.23.4 | SDK | User authentication via Google Sign-In for admins and real estate agents | google.oauth2.id_token.verify_oauth2_token()<br>google.auth.transport.requests.Request() |
| OpenAI / OpenAI SDK | 1.3.7 | SDK | Reserved for future LLM, STT, TTS functionality (Legacy) | openai (configured but currently using Gemini) |

## Frontend

| Service/API/SDK | Version | Type | Purpose | Endpoint/Connection |
|-----------------|---------|------|---------|---------------------|
| Google OAuth / Google OAuth JavaScript API | - | API | Client-side Google authentication for admins and real estate agents | https://accounts.google.com/gsi/client<br>window.google.accounts.id.initialize()<br>window.google.accounts.id.prompt() |
| @react-oauth/google | 0.11.1 | Library | React components and hooks for Google Sign-In integration | @react-oauth/google (installed but using native Google script) |
| @tanstack/react-query | 5.90.11 | Library | Caching, synchronization, and server state management for API calls | @tanstack/react-query<br>useQuery()<br>QueryClient<br>QueryClientProvider |

