# Call recording playback — issue log & fix reference

This document preserves full context so we can resume fixing **agent call recording playback** without losing details. Last updated when Twilio account / credentials were still unresolved.

---

## Problem (user-visible)

- Real estate agents click **Play** on call recordings (e.g. Voice Agent / call history UI). Playback shows **nothing** (no duration, no timeline), or fails silently.
- Opening the **raw Twilio recording URL** from the DB in a browser shows XML / `401` / **Authenticate** — browser prompts for username/password. Agents must **not** use Twilio credentials; playback must go through the **backend proxy** with **JWT** only.

---

## Correct architecture (how it should work)

1. **Never** expose Twilio Account SID + Auth Token to the browser.
2. **Do** store Twilio’s `RecordingUrl` (and `RecordingSid`) on the `calls` row when the recording webhook fires.
3. **Playback path**: frontend calls authenticated backend:
   - `GET {API_URL}/agent/calls/{call_id}/recording/stream`
   - Header: `Authorization: Bearer <agent_token>`
4. Backend verifies the call belongs to the logged-in agent, then fetches audio from Twilio using **HTTP Basic Auth** (`Account SID:Auth Token`), and streams bytes to the client.

**Backend routes** (see `app/controllers/call_controller.py`):

- `GET /agent/calls/{call_id}/recording` — returns metadata + **relative** proxied path `/agent/calls/{call_id}/recording/stream` (not raw Twilio URL for UI use).
- `GET /agent/calls/{call_id}/recording/stream` — proxies Twilio recording (adds `.mp3` for API-style URLs when needed).

**Frontend** (representative):

- `components/twilio/CallDetailsSheet.tsx` — fetches blob from `/recording/stream` with Bearer token, uses blob URL for `<audio>`.
- `components/agent/CallRecordingModal.tsx` — similar pattern via `getCallRecording` + stream URL.
- API base: `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8001`) — must match running backend port.

---

## Root causes we identified

### 1) Twilio credentials invalid or mismatched (primary technical blocker)

Symptoms:

- `python -c` Twilio `Client` → `TwilioRestException` / **Unable to fetch record: Authenticate** (HTTP 20003).
- Direct `requests.get(recording.mp3, auth=(sid, token))` → **401** + `application/xml` (Twilio error body).

Meaning: **Account SID and Auth Token pair is wrong**, token was **rotated**, or **wrong account** (main vs subaccount) vs resources in DB.

### 2) Twilio account suspended (billing)

- User confirmed: **Twilio account suspended due to billing**.
- A suspended account can block or severely limit API access (including recordings), even after credentials are “correct.”
- **Resolution**: restore account to **active** in Twilio Console (billing / compliance banners), then re-test API.

### 3) Local port conflict (earlier session)

- Port **8000** was taken by **Apache (`httpd.exe`)**, not FastAPI → `WinError 10013` or wrong service answering requests.
- **Workaround**: run backend on another port, e.g. `--port 8001`, and set `NEXT_PUBLIC_API_URL=http://localhost:8001` on frontend; restart Next dev server.

### 4) `alembic` not on PATH (Windows)

- Use: `python -m alembic upgrade head` instead of bare `alembic`.

---

## Diagnostic commands (run from backend repo root)

**Load `.env` and verify Twilio account fetch:**

```powershell
python -c "from twilio.rest import Client; import os; from dotenv import load_dotenv; load_dotenv(); c=Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN')); print(c.api.accounts(os.getenv('TWILIO_ACCOUNT_SID')).fetch().status)"
```

- Expect: `active` with **no** exception.

**Verify recording media (replace `RE...` with real Recording SID from DB):**

```powershell
python -c "import os, requests; from dotenv import load_dotenv; load_dotenv(); sid=os.getenv('TWILIO_ACCOUNT_SID'); tok=os.getenv('TWILIO_AUTH_TOKEN'); rec='RExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'; u=f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Recordings/{rec}.mp3'; r=requests.get(u, auth=(sid,tok), allow_redirects=True, timeout=20); print(r.status_code, r.headers.get('content-type'), len(r.content))"
```

- Expect: **200**, `audio/*` or octet-stream, **non-zero** length.

**Health:**

```powershell
curl http://127.0.0.1:8001/health
```

(Adjust port to whatever uvicorn uses.)

---

## Environment variables (backend `.env`)

Required for recording proxy:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`

Must be the **same** Twilio account that **owns** the Call SID / Recording SID stored in your database. If you use **subaccounts**, align SID + token with the account that created the recording.

---

## Frontend env

- `NEXT_PUBLIC_API_URL=http://localhost:8001` (or production API origin)
- After changing: restart `npm run dev` (Next bakes public env at build/start).

---

## Code changes made during investigation (for continuity)

- **`app/controllers/call_controller.py`**: clearer errors when Twilio returns 401/403 on recording fetch; avoid masking `HTTPException` as generic 500.
- **`components/twilio/CallDetailsSheet.tsx`**: loading/error state for recording fetch; safer `audio.play()`; disable controls when no blob.

Do **not** remove the proxy pattern; fix Twilio account + credentials instead.

---

## Checklist when resuming the fix

1. [ ] Twilio Console: account **active**, no suspension / billing block.
2. [ ] Copy fresh **Account SID** + **Auth Token** (same account as recordings).
3. [ ] Update `.env`, restart backend.
4. [ ] Run account-fetch diagnostic → `active`.
5. [ ] Run recording GET diagnostic → `200` + bytes.
6. [ ] Frontend `NEXT_PUBLIC_API_URL` matches backend URL/port.
7. [ ] Agent logged in (`agent_token` present); play uses `/recording/stream` only.

---

## Security note

Secrets (Twilio token, OpenAI keys, etc.) were discussed in chat during debugging. **Rotate** Twilio Auth Token after sharing in insecure channels and update `.env`.

---

## Related files (quick navigation)

| Area | Path |
|------|------|
| Recording proxy | `app/controllers/call_controller.py` |
| Call DB fields | `app/models/call.py`, `app/services/call_service.py` |
| Twilio client | `app/services/twilio_service/client.py` |
| Agent API client | `PropTalk-Frontend/lib/real_estate_agent/api.ts` |
| Details / audio UI | `PropTalk-Frontend/components/twilio/CallDetailsSheet.tsx` |

---

## One-line summary

**Recordings fail until Twilio accepts your credentials and the account can access the Recording API; the app proxies audio correctly once Twilio returns 200 for authenticated recording fetches.**
