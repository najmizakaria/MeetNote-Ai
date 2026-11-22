# MeetNote AI

**SDT 2143 Mini AI Hackathon — AI for Productivity**

Meeting audio → `faster-whisper` transcript → Gemini summary → Streamlit workspace.

This is a **new, standalone project**. It does not modify the earlier MeetMind AI project.

## Recording modes and limitations

| Mode | Runs where? | Input | Transcription timing |
|---|---|---|---|
| **Browser microphone** | Laptop **and Streamlit Community Cloud** | Visitor's microphone through `st.audio_input` | **After** pressing Stop and Transcribe |
| **Local audio devices** | **Windows/macOS laptop running Python locally** | `sounddevice` input devices | Approx. every 8 seconds, with a final segment at Stop |
| **Local laptop/system sound** | Laptop only | Select `Stereo Mix`, `CABLE Output` (VB-Cable), BlackHole or an equivalent input | Approx. every 8 seconds |
| **Local both** | Laptop only | One microphone input + a **different** system loopback/virtual input | Approx. every 8 seconds, mixed |
| **Upload audio** | Laptop and cloud | MP3, WAV, M4A, WebM, MP4, OGG | After upload and Transcribe |

**Important:** `sounddevice` records from devices attached to the Python server. Streamlit Community Cloud does not have access to the website visitor's microphone or system speakers via `sounddevice`; this is why `st.audio_input` handles browser microphone recording. Browser mode is not continuous/live captions. Cloud laptop/tab audio recording would need a separate browser recording component; it is **not implemented** in this simpler project.

Mixing two independent devices in local Both mode is approximate, so the first few milliseconds may not line up perfectly. For best recording quality use matching hardware settings and check levels before the demo.

## Windows installation

1. Install [Python 3.11](https://www.python.org/downloads/), Git and VS Code.
2. Extract this folder anywhere, e.g. `C:\Users\najmi\Documents\VS_Code\MeetNote_AI`.
3. Run the web entry point using PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://localhost:8501` in a browser.

On the first transcription `faster-whisper` downloads a model. `tiny` is fastest, `base` provides a moderate accuracy increase, and `small` is better suited for a sufficiently powerful local PC. All run on CPU in this implementation.

### How to record your laptop's meeting audio (Windows)

There are two supported **input-device** approaches. The app does **not** magically read your speaker output as a microphone.

**Option A: Stereo Mix** — In Windows Sound settings, enable the `Stereo Mix` recording device if your sound driver supplies it. Then choose **Local audio devices → Laptop audio → Stereo Mix**.

**Option B: VB-Cable** — Install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/). Select **CABLE Input** as the meeting app or Windows audio **output**. In MeetNote AI, choose **CABLE Output** as the **recording input**. You may need Windows “Listen to this device” or a mixer to hear audio in your headphones at the same time.

For **Both**, choose your actual microphone under Microphone and Stereo Mix/CABLE Output under Laptop audio. They must be two different input devices. Request consent from meeting participants before recording.

To list available devices from PowerShell:

```powershell
.\.venv\Scripts\python.exe -m sounddevice
```

If you receive “PortAudioError: invalid sample rate” switch device, confirm it has an input channel, and check that no other application is locking it.

## Gemini summarization

Get your own API key from [Google AI Studio](https://aistudio.google.com/apikey).

1. Open **Model, language and privacy settings** at the bottom of the app.
2. Paste the key into the password field **or** supply it through Streamlit Secrets.
3. Choose the model ID your key supports (`gemini-3.8-flash` is the default at project creation, not guaranteed for every key).
4. Generate AI meeting notes after transcribing. A short retry handles transient `503 UNAVAILABLE` responses. Your transcript is preserved if the API call fails.

**Do not put API keys in `app.py`, `README.md`, or a GitHub commit.** A server key on a public app may be used by your visitors and exhaust quota. For an assignment demo, consider requiring each user to enter their own API key and keep the server secret unset.

## Deploy the public app from GitHub

The cloud version uses `requirements.txt` (without `sounddevice`). Only browser microphone and audio uploads work on Community Cloud.

1. [Create an empty GitHub repo](https://github.com/new) named `MeetNote-AI`.
2. Open PowerShell in the *extracted project folder* and run:

```powershell
git init
git branch -M main
git add .
git status
# Check no .env, API keys, .venv, or secrets.toml are staged.
git commit -m "Initial MeetNote AI prototype"
git remote add origin https://github.com/YOUR_USERNAME/MeetNote-AI.git
git push -u origin main
```

3. Visit [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
4. Create app → Existing repo → select your repo, branch `main`, **Main file** `app.py`.
5. If necessary configure Python 3.11 in Advanced settings.
6. If you choose to provide a server-side Gemini key, use **Secrets**, not a file committed to the repo:

```toml
GEMINI_API_KEY = "your-private-key"
```

7. Click Deploy and test browser microphone recording with Chrome or Edge on the HTTPS page.

Cloud constraints: Whisper model inference uses server CPU and model memory; try `tiny` first. Other visitors' requests may share the server. This demonstration is **not** a scalable production meeting service, and meetings do not persist after the session ends.

## Project structure

```
MeetNote_AI/
├── app.py                      # Streamlit UX and workflow
├── meetnote/
│   ├── audio.py                # resampling, mixing, WAV output
│   ├── local_capture.py        # sounddevice recording
│   ├── transcriber.py          # faster-whisper inference
│   ├── notes.py                # Gemini and structured meeting notes
│   └── export.py               # Word export
├── .streamlit/config.toml      # app colors and uploads
├── .streamlit/secrets.toml.example
├── requirements.txt           # cloud dependencies
├── requirements-local.txt     # adds local sounddevice dependency
├── run_windows.bat
├── tests/
└── docs/
    ├── UX_REDESIGN.md
    ├── TEAM_ASSIGNMENTS.md
    └── DEMO_CHECKLIST.md
```

## Privacy and responsible use

Always obtain participant consent. Audio is processed on the running application server; a transcript sent to Gemini is processed by an external AI provider. Do not rely blindly on AI summaries for decisions or deadlines. This student version holds notes only in Streamlit session state and does not save recordings to Supabase or another database. If you add persistence, require authentication, row-level access controls, and a deletion policy.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Automated tests cover audio transformation, notes parsing and Word output. They **do not** prove physical microphone access, model download/inference, Gemini model access, or deployed hardware behavior: those must be tested on your computer and public site.
