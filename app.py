"""MeetNote AI — local/live and browser meeting transcription.

Run locally: streamlit run app.py
"""
from __future__ import annotations
from datetime import date
import streamlit as st
from meetnote.notes import MODEL, create_notes, notes_text
from meetnote.export import make_docx
from meetnote.transcriber import LANGUAGES, make_model, transcribe_bytes
from meetnote.local_capture import LocalCapture, list_inputs

st.set_page_config(page_title="MeetNote AI | Meeting workspace", page_icon="◉", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root {--paper:#F2F6F7;--surface:#FFFFFF;--ink:#17333B;--muted:#516970;--teal:#176B68;--border:#CAD9DC;--record:#B94733;}
html,body,[class*="css"],.stApp {font-family:'Segoe UI',sans-serif!important;color:var(--ink)!important}
.stApp {background:var(--paper)!important}
section.main .block-container {max-width:1220px;padding-top:2.1rem;padding-bottom:4rem}
h1,h2,h3 {font-family:'Segoe UI',sans-serif!important;letter-spacing:-.025em!important;color:var(--ink)!important}
h1 {font-size:3.05rem!important;line-height:1.06!important;margin:.45rem 0 1.3rem!important}
h2 {font-size:1.45rem!important}
[data-testid="stMetricValue"] {font-family:Consolas,monospace!important;font-size:1.4rem!important}
[data-testid="stMetricLabel"] {color:var(--muted)!important;font-family:Consolas,monospace!important;font-size:.69rem!important;letter-spacing:.07em;text-transform:uppercase}
[data-testid="stVerticalBlockBorderWrapper"] {background:var(--surface);border-color:var(--border)!important;border-radius:12px!important}
[data-testid="stButton"] button[kind="primary"] {background:var(--teal)!important;border-color:var(--teal)!important;color:white!important;font-weight:600;min-height:2.7rem;border-radius:8px}
[data-testid="stButton"] button {border-radius:8px!important;font-family:'Segoe UI',sans-serif!important}
[data-testid="stFileUploader"], [data-testid="stTextArea"] {border-color:var(--border)}
.hero-top {display:flex;justify-content:space-between;align-items:center;gap:1rem;border-bottom:1px solid var(--border);padding-bottom:1.15rem;margin-bottom:1.7rem}
.wordmark {font-family:'Segoe UI',sans-serif;font-weight:700;letter-spacing:-.045em;font-size:1.31rem}
.wordmark-dot {color:var(--teal)}
.edition {font-family:Consolas,monospace;font-size:.68rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.eyebrow {font-family:Consolas,monospace;font-size:.72rem;letter-spacing:.13em;text-transform:uppercase;color:var(--teal)}
.hero-sub {font-size:1.04rem;color:var(--muted);margin-top:-.4rem;margin-bottom:1.35rem;max-width:730px}
.section-tag {font-family:Consolas,monospace;color:var(--muted);font-size:.76rem;letter-spacing:.075em;text-transform:uppercase;margin:.65rem 0 .7rem}
.narrow-note {font-size:.85rem;color:var(--muted);line-height:1.45}
.live-track {display:flex;align-items:center;gap:12px;background:#E2EFEF;border-left:4px solid var(--teal);padding:13px 16px;margin:.55rem 0 1.1rem;border-radius:0 8px 8px 0}
.live-track.recording {border-left-color:var(--record);background:#F7E9E5}
.signal {font-size:1.2rem;color:var(--teal)}
.live-track.recording .signal {color:var(--record)}
.live-label {font-family:Consolas,monospace;font-size:.83rem;letter-spacing:.01em}
.transcript-display {font-size:1.03rem;line-height:1.7;padding:.3rem 0 .7rem;white-space:pre-wrap}
.output-label {font-family:Consolas,monospace;font-size:.75rem;letter-spacing:.06em;color:var(--teal);text-transform:uppercase}
.minor {font-size:.84rem;color:var(--muted)}
/* Restore contrast and avoid heavy button motion. */
button {transition:background-color .12s ease,border-color .12s ease!important}
[data-testid="stSidebar"] {background:#EAF1F2}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading Whisper speech recognition model…")
def cached_transcription_model(model_name: str):
    return make_model(model_name)


def init_state():
    defaults = {"segments": [], "notes": None, "detected_language": "—",
                "capture": None, "message": "", "last_audio": None,
                "recorder_serial": 0}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if "language_choice" in st.session_state and st.session_state.language_choice not in LANGUAGES:
        st.session_state.language_choice = next(iter(LANGUAGES))


def transcript() -> str:
    return "\n".join(item["text"] for item in st.session_state.segments if item["text"].strip())


def transcribe_clip(payload: bytes, ext: str, model_name: str, language: str | None):
    if not payload:
        return False
    try:
        with st.spinner("Transcribing audio using Whisper…"):
            text, lang = transcribe_bytes(payload, ext, cached_transcription_model(model_name), language)
        if not text:
            st.session_state.message = "No clear speech detected in this segment. Try another device or speak closer to the microphone."
            return False
        st.session_state.segments.append({"text": text, "language": lang})
        st.session_state.detected_language = (lang or "—").upper()
        st.session_state.notes = None  # invalidate old summary when transcript changes
        st.session_state.last_audio = payload
        st.session_state.message = "Audio transcribed successfully."
        return True
    except Exception as exc:
        st.session_state.message = f"Transcription failed: {exc}"
        return False


def summarize_current():
    try:
        with st.spinner("Generating meeting notes locally with Qwen3…"):
            st.session_state.notes = create_notes(transcript())
        st.session_state.message = "Meeting notes generated. Check names and dates before sharing."
    except Exception as exc:
        st.session_state.message = f"AI summary unavailable: {exc}. Your transcript is preserved."


def reset_meeting():
    recorder = st.session_state.get("capture")
    if recorder and recorder.active:
        recorder.stop()
    st.session_state.capture = None
    st.session_state.segments = []
    st.session_state.notes = None
    st.session_state.detected_language = "—"
    st.session_state.message = "New meeting ready."
    st.session_state.last_audio = None
    st.session_state.recorder_serial += 1


init_state()
st.markdown('<div class="hero-top"><span class="wordmark">meetnote<span class="wordmark-dot">.</span> ai</span>'
            '<span class="edition">SDT 2143 / Audio workspace / v1.0</span></div>', unsafe_allow_html=True)
st.markdown('<span class="eyebrow">Meeting intelligence / one workspace</span>', unsafe_allow_html=True)
st.title("Record the meeting. Keep the decisions.")
st.markdown('<div class="hero-sub">Record or upload audio, edit the transcript, and generate local meeting notes.</div>', unsafe_allow_html=True)

settings, extra = st.columns([2.2, 1], gap="large")
with settings:
    meeting_name = st.text_input("Meeting title", value="Team project discussion", max_chars=90)
with extra:
    meeting_date = st.date_input("Date", date.today())

st.markdown('<div class="section-tag">01 / Input source</div>', unsafe_allow_html=True)
mode = st.radio("Recording workflow", ["Browser microphone", "Local audio devices", "Upload audio"],
                horizontal=True, label_visibility="collapsed")

with st.container(border=True):
    if mode == "Browser microphone":
        st.markdown('<div class="live-track"><span class="signal">◉</span><span class="live-label">BROWSER CAPTURE · record then transcribe</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="narrow-note">Press Record, allow microphone access, speak, then Stop. The browser sends the finished audio clip for transcription; this mode is not live captioning.</div>', unsafe_allow_html=True)
        recording = st.audio_input("Record your meeting", sample_rate=16000,
                                   key=f"browser_rec_{st.session_state.recorder_serial}")
        if recording is not None:
            st.audio(recording)
            if st.button("Transcribe recording", type="primary", key="transcribe_browser"):
                transcribe_clip(recording.getvalue(), ".wav", st.session_state.model_choice,
                                LANGUAGES[st.session_state.language_choice])
    elif mode == "Upload audio":
        st.markdown('<div class="live-track"><span class="signal">↥</span><span class="live-label">FILE IMPORT · mp3 / wav / m4a / webm</span></div>', unsafe_allow_html=True)
        upload = st.file_uploader("Choose an audio recording", type=["wav", "mp3", "m4a", "webm", "mp4", "ogg"],
                                  key=f"upload_{st.session_state.recorder_serial}")
        if upload is not None:
            st.audio(upload)
            if st.button("Transcribe uploaded file", type="primary"):
                transcribe_clip(upload.getvalue(), os.path.splitext(upload.name)[-1],
                                st.session_state.model_choice,
                                LANGUAGES[st.session_state.language_choice])
    else:
        st.markdown('<div class="live-track"><span class="signal">●</span><span class="live-label">LOCAL LIVE CAPTURE · audio input devices connected to this Python computer</span></div>', unsafe_allow_html=True)
        st.caption("Only works when Python runs on your own computer. A public Streamlit server has no access to your laptop's audio hardware. For laptop sound, select Stereo Mix or VB-Cable CABLE Output as the input device.")
        try:
            devices = list_inputs()
        except Exception as exc:
            devices = []
            st.warning(f"Local audio recording unavailable: {exc}. Install requirements-local.txt and run on Windows.")
        capture = st.session_state.capture
        names = {d["index"]: f'{d["name"]} · {d["rate"]} Hz' for d in devices}
        if not devices:
            st.info("No audio inputs found. To use this mode, run locally with a connected microphone or virtual audio cable.")
        else:
            ids = list(names)
            kind = st.radio("Capture from", ["Microphone", "Laptop audio", "Both"], horizontal=True)
            selected = {}
            if kind in ("Microphone", "Both"):
                selected["mic"] = st.selectbox("Microphone input device", ids, format_func=lambda x: names[x])
            if kind in ("Laptop audio", "Both"):
                best = next((i for i,d in enumerate(devices) if any(w in d["name"].lower()
                    for w in ["stereo mix", "cable output", "blackhole", "loopback", "monitor"])), 0)
                selected["laptop"] = st.selectbox("Laptop / loopback input device", ids,
                    index=best, format_func=lambda x: names[x])
                st.caption("Windows: play a meeting through VB-Cable and choose 'CABLE Output' here, or enable Stereo Mix in Windows Sound settings.")
            if capture and capture.active:
                if st.button("Apply audio source", disabled=selected == capture.devices):
                    try:
                        capture.switch_devices(selected)
                    except Exception as exc:
                        st.error(f"Could not switch audio. {exc}")
                    else:
                        st.success("Audio source applied. Recording continues.")
            elif st.button("Start local live recording", type="primary", use_container_width=False):
                try:
                    capture = LocalCapture(selected)
                    capture.start()
                    st.session_state.capture = capture
                    st.session_state.message = "Recording. Transcript updates approximately every 8 seconds."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Recording failed: {exc}")

        @st.fragment(run_every="2s")
        def live_monitor():
            rec = st.session_state.get("capture")
            if rec and rec.active:
                st.markdown('<div class="live-track recording"><span class="signal">●</span>'
                            '<span class="live-label">RECORDING LIVE · processing 8-second audio chunks</span></div>',
                            unsafe_allow_html=True)
                active_sources = ", ".join(names.get(device_id, f"Input {device_id}")
                                           for device_id in rec.devices.values())
                st.caption(f"Recording from {active_sources}")
                st.caption(f"Elapsed: {int(rec.elapsed)} seconds · buffered: {rec.buffered_seconds():.1f} seconds")
                if rec.buffered_seconds() >= 8:
                    data = rec.drain()
                    if data:
                        transcribe_clip(data, ".wav", st.session_state.model_choice,
                                        LANGUAGES[st.session_state.language_choice])
                if st.button("Stop and transcribe remainder", type="primary", key="stop_local"):
                    rec.stop()
                    data = rec.drain()
                    if data:
                        transcribe_clip(data, ".wav", st.session_state.model_choice,
                                        LANGUAGES[st.session_state.language_choice])
                    if st.session_state.auto_notes and transcript().strip():
                        summarize_current()
                    st.rerun()
                if st.session_state.segments:
                    st.markdown("**Live transcript so far**")
                    st.text(transcript())
                if rec.last_error:
                    st.warning(f"Audio device warning: {rec.last_error}")
            elif rec:
                st.caption("Local recording stopped.")
        live_monitor()

st.markdown('<div class="section-tag">02 / Transcript & meeting notes</div>', unsafe_allow_html=True)
left, right = st.columns([1.12, 1], gap="large")
with left:
    st.subheader("Transcript")
    st.caption("Editable before AI summarization. Review misheard names and technical terms.")
    current = transcript()
    revised = st.text_area("Transcript text", value=current, height=285, label_visibility="collapsed",
                           placeholder="Your meeting transcript will appear here…")
    if revised != current:
        if st.button("Use edited transcript"):
            st.session_state.segments = [{"text": revised.strip(), "language": "edited"}] if revised.strip() else []
            st.session_state.notes = None
            st.rerun()
    st.caption(f"{len(st.session_state.segments)} transcribed section(s) · Detected language: {st.session_state.detected_language}")
    if st.button("Generate AI meeting notes", type="primary", disabled=not transcript().strip()):
        summarize_current()

with right:
    st.subheader("Meeting notes")
    notes = st.session_state.notes
    if not notes:
        st.caption("Generate notes from the transcript using local Qwen3.")
        st.markdown("**Expected output**")
        st.markdown("Meeting overview · Key points · Decisions · Action items · Open questions")
    else:
        st.markdown('<div class="output-label">Overview</div>', unsafe_allow_html=True)
        st.text(notes.get("overview") or "No overview provided.")
        for key, title in [("key_points", "Key points"), ("decisions", "Decisions"),
                           ("open_questions", "Open questions")]:
            st.markdown(f'<div class="output-label">{title}</div>', unsafe_allow_html=True)
            values = notes.get(key, [])
            if values:
                for v in values:
                    st.text(f"• {v}")
            else:
                st.caption("None stated")
        st.markdown('<div class="output-label">Action items</div>', unsafe_allow_html=True)
        if notes.get("action_items"):
            for a in notes["action_items"]:
                st.text(f"{a['task']}\nOwner: {a['owner']} · Due: {a['deadline']}")
        else:
            st.caption("No explicit tasks identified")

if st.session_state.message:
    if st.session_state.message.lower().startswith(("ai summary unavailable", "transcription failed")):
        st.warning(st.session_state.message)
    else:
        st.info(st.session_state.message)

st.markdown('<div class="section-tag">03 / Deliverables</div>', unsafe_allow_html=True)
if transcript().strip():
    safe_filename = "".join(x if x.isalnum() or x in "-_" else "_" for x in meeting_name).strip("_")[:60] or "Meeting"
    export1, export2, export3 = st.columns([1, 1, 1])
    with export1:
        st.download_button("Download TXT", notes_text(meeting_name, meeting_date.isoformat(),
                            transcript(), st.session_state.notes), file_name=f"{safe_filename}.txt",
                            mime="text/plain", use_container_width=True)
    with export2:
        st.download_button("Download Word", make_docx(meeting_name, meeting_date.isoformat(),
                            transcript(), st.session_state.notes), file_name=f"{safe_filename}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True)
    with export3:
        st.download_button("Download transcript", transcript(), file_name=f"{safe_filename}_transcript.txt",
                            mime="text/plain", use_container_width=True)
else:
    st.caption("Exports become available after the first successful transcription.")

st.divider()
with st.expander("Model, language and privacy settings", expanded=False):
    st.selectbox("Whisper model", ["tiny", "base", "small"], index=0, key="model_choice",
                 help="Tiny runs fastest. Larger models need more memory.")
    st.selectbox("Language", list(LANGUAGES.keys()), index=0, key="language_choice",
                 help="Auto detect chooses between English and Bahasa Melayu.")
    st.caption(f"Summary model: {MODEL} via local Ollama.")
    st.checkbox("Generate notes automatically after stopping LOCAL recording", value=False, key="auto_notes")
    st.caption("Record only with consent. This local workspace processes audio and generates notes on your computer.")
    if st.button("Clear transcript and start new meeting"):
        reset_meeting()
        st.rerun()
st.caption("MeetNote AI · Student prototype · Verify AI-generated notes before sharing")
