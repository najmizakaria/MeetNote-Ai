"""Check that the desktop workflow keeps transcript and export state consistent."""
import io
from pathlib import Path
import tkinter as tk
from types import SimpleNamespace

from docx import Document
import numpy as np
import pytest

import desktop_app as desktop
from meetnote import live_transcription as live
from meetnote.notes import clean_notes


@pytest.fixture
def workspace():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display unavailable: {error}")
    root.withdraw()
    app = desktop.MeetNoteApp(root)
    try:
        yield app
    finally:
        root.destroy()


def test_failed_audio_remains_available_for_retry(workspace, monkeypatch):
    audio = (Path("test.wav"), "en", "tiny")
    workspace.audio.append(audio)
    workspace.audio_result(None, "Model unavailable")
    assert workspace.failed and list(workspace.audio) == [audio]
    monkeypatch.setattr(workspace, "start_audio_job", lambda: None)
    workspace.toggle_recording()
    assert not workspace.failed
    workspace.audio_result(("The team agreed to test.", "en"), "")
    assert not workspace.audio
    assert workspace.current_transcript() == "The team agreed to test."


def test_source_switch_preserves_the_live_session_and_transcript_edits(workspace, monkeypatch):
    from meetnote import local_capture

    class FakeCapture:
        elapsed = 2
        last_error = ""

        def __init__(self, devices):
            self.devices = devices
            self.samples = np.ones(live.FIRST_DRAFT, dtype=np.float32)

        def start(self):
            pass

        def switch_devices(self, devices):
            self.devices = devices

        def stop(self):
            self.samples = np.full(1600, 0.5, dtype=np.float32)

        def buffered_seconds(self):
            return len(self.samples) / live.TARGET_RATE

        def drain_samples(self):
            samples = self.samples
            self.samples = self.samples[:0]
            return samples

    jobs = []

    def start_job(name, function, *args):
        workspace.job = name
        jobs.append((name, args))

    monkeypatch.setattr(local_capture, "LocalCapture", FakeCapture)
    monkeypatch.setattr(live, "speech_timestamps",
                        lambda samples: [{"start": 0, "end": len(samples)}])
    monkeypatch.setattr(workspace, "start_job", start_job)
    workspace.tick()
    assert jobs[-1] == ("warmup", ("tiny",))
    workspace.results.put(("warmup", "tiny", ""))
    workspace.tick()
    assert workspace.whisper_status.get() == "Whisper ready (tiny)"

    workspace.devices = {"Microphone": 0, "Stereo Mix": 1}
    workspace.mic.set("Microphone")
    workspace.toggle_recording()
    workspace.tick()
    assert jobs[-1][0] == "draft"
    capture, live_session = workspace.capture, workspace.live
    assert workspace.mode_box.instate(["readonly"])
    workspace.mode.set("Both")
    workspace.refresh_controls()
    assert workspace.second_box.instate(["readonly"])
    assert workspace.second_device.winfo_manager() == "pack"
    workspace.mode.set("Laptop audio")
    workspace.refresh_controls()
    workspace.source_button.invoke()
    assert workspace.source_error.winfo_manager() == "pack"
    assert capture.devices == {"microphone": 0}
    assert workspace.capture_label.get() == "Recording · Microphone"
    workspace.loopback.set("Stereo Mix")
    workspace.source_button.invoke()
    assert workspace.source_error.winfo_manager() == ""
    assert workspace.capture is capture and workspace.live is live_session
    assert capture.devices == {"laptop audio": 1}
    assert workspace.capture_label.get() == "Recording · Laptop audio"
    workspace.transcript.insert("1.0", "My edit.")
    workspace.toggle_recording()
    workspace.results.put(("draft", "This draft is out of date.", ""))
    workspace.tick()
    name, (clip, _, _) = jobs[-1]
    assert name == "audio"
    assert len(clip.samples) == live.FIRST_DRAFT + 1600
    assert clip.samples[-1] == 0.5
    assert "out of date" not in workspace.transcript.get("1.0", "end")
    workspace.results.put(("audio", ("The last phrase.", "en"), ""))
    workspace.tick()
    assert workspace.current_transcript() == "My edit.\n\nThe last phrase."
    assert workspace.summarize_button.instate(["!disabled"])


def test_continuous_speech_updates_the_transcript_before_a_pause(workspace, monkeypatch):
    def detect(samples):
        voiced = np.flatnonzero(samples)
        return [{"start": voiced[0], "end": voiced[-1] + 1}] if len(voiced) else []

    monkeypatch.setattr(live, "speech_timestamps", detect)
    monkeypatch.setattr(workspace, "start_job", lambda name, *args: setattr(workspace, "job", name))
    workspace.capture = SimpleNamespace(elapsed=1, buffered_seconds=lambda: 0)
    workspace.live = live.LiveSpeech()
    workspace.capture_settings = ("en", "tiny")
    workspace.transcript.insert("1.0", "Earlier speech.")
    workspace.capture.drain_samples = lambda: np.ones(live.FIRST_DRAFT, dtype=np.float32)
    workspace.enqueue_recording()
    workspace.tick()
    assert workspace.job == "draft"

    workspace.results.put(("draft", "The next", ""))
    workspace.tick()
    assert not workspace.audio
    assert workspace.transcript.get("1.0", "end-1c") == "Earlier speech.\n\nThe next"
    assert workspace.current_transcript() == "Earlier speech."

    workspace.capture.drain_samples = lambda: np.ones(live.DRAFT_INTERVAL, dtype=np.float32)
    workspace.enqueue_recording()
    workspace.tick()
    assert workspace.job == "draft"
    workspace.capture.drain_samples = lambda: np.zeros(live.PAUSE, dtype=np.float32)
    workspace.enqueue_recording()
    workspace.results.put(("draft", "The next phrase", ""))
    workspace.tick()
    assert workspace.job == "audio"
    assert workspace.transcript.get("1.0", "end-1c") == "Earlier speech.\n\nThe next phrase"

    workspace.results.put(("audio", ("The next phrase.", "en"), ""))
    workspace.tick()
    assert workspace.transcript.get("1.0", "end-1c") == workspace.current_transcript()
    assert workspace.current_transcript() == "Earlier speech.\n\nThe next phrase."
    assert workspace.draft_status.get() == desktop.LISTENING


def test_live_updates_preserve_transcript_edits_and_undo(workspace):
    transcript = workspace.transcript
    transcript.insert("1.0", "Earlier speech.")
    transcript.edit_separator()
    workspace.show_draft("Draft")
    transcript.insert("end-1c", " Edited.")
    workspace.show_draft("Latest draft")
    assert workspace.current_transcript() == "Earlier speech. Edited."
    transcript.edit_undo()
    assert workspace.current_transcript() == "Earlier speech."
    assert transcript.get("1.0", "end-1c") == "Earlier speech.\n\nLatest draft"
    transcript.edit_redo()
    transcript.delete("end-2c")
    assert transcript.get("1.0", "end-1c") == "Earlier speech. Edited.\n\nLatest draft"


def test_notes_only_export_with_matching_transcript(workspace, tmp_path, monkeypatch):
    transcript = "We agreed to test. Maya will review on Friday."
    workspace.transcript.insert("1.0", transcript)
    workspace.job_source = transcript
    notes = clean_notes({"decisions": ["Test the app"], "action_items": [
        {"task": "Review", "owner": "Maya", "deadline": "Friday"},
    ]})
    workspace.notes_result(notes, "")
    word = tmp_path / "notes.docx"
    monkeypatch.setattr(desktop.filedialog, "asksaveasfilename", lambda **_: str(word))
    workspace.export(".docx")
    paragraphs = [p.text for p in Document(io.BytesIO(word.read_bytes())).paragraphs]
    assert "Test the app" in paragraphs
    assert transcript in paragraphs
    assert any("Owner: Maya" in line and "Due: Friday" in line for line in paragraphs)

    workspace.transcript.insert("end-1c", " The date changed.")
    workspace.transcript_changed()
    assert workspace.notes is None
    text = tmp_path / "notes.txt"
    monkeypatch.setattr(desktop.filedialog, "asksaveasfilename", lambda **_: str(text))
    workspace.export(".txt")
    saved = text.read_text(encoding="utf-8")
    assert "The date changed." in saved
    assert "Test the app" not in saved


def test_english_map_keeps_notes_separate_and_blocks_saving_stale_maps(workspace, tmp_path, monkeypatch):
    from PIL import Image

    transcript = "Mira akan menguji mikrofon pada hari Khamis."
    workspace.title.set("Ujian Mikrofon")
    workspace.transcript.insert("1.0", transcript)
    workspace.transcript_changed()
    workspace.notes = clean_notes({"overview": transcript})
    workspace.notes_source = transcript
    assert workspace.map_button.instate(["!disabled"])
    jobs = []
    monkeypatch.setattr(workspace, "start_job", lambda *args: jobs.append(args))
    workspace.map_button.invoke()
    assert jobs == [("map", desktop.create_mind_map, transcript, "qwen3:4b")]

    mind_map = {"topic": "Microphone Testing", "branches": ["Mira tests on Thursday"]}
    workspace.notes_result(mind_map, "", show_map=True)
    assert workspace.map_preview.topic == "Microphone Testing"
    assert workspace.notes["overview"] == transcript
    destination = tmp_path / "mind map.png"
    monkeypatch.setattr(desktop.filedialog, "asksaveasfilename", lambda **_: str(destination))
    workspace.map_preview.save_button.invoke()
    with Image.open(destination) as png:
        assert png.size == (1800, 1800)

    workspace.map_button.invoke()
    assert len(jobs) == 1
    workspace.transcript.insert("end-1c", " Kami tukar hari.")
    workspace.transcript_changed()
    assert workspace.map_preview.save_button.instate(["disabled"])
    workspace.map_button.invoke()
    assert len(jobs) == 2



def test_local_summary_failure_preserves_transcript_and_export(workspace, monkeypatch):
    text = "Maya will check the audio."
    workspace.transcript.insert("1.0", text)
    workspace.transcript_changed()
    pending = []
    monkeypatch.setattr(workspace, "start_job", lambda *args: pending.append(args))
    workspace.summarize_button.invoke()
    assert pending == [("notes", desktop.create_notes, text, "qwen3:4b")]
    workspace.notes_result(None, "Start Ollama for Windows.")
    workspace.refresh_controls()
    assert workspace.current_transcript() == text
    assert "Start Ollama" in workspace.status.get()
    assert workspace.txt_button.instate(["!disabled"])
    assert workspace.docx_button.instate(["!disabled"])



def test_summary_model_picker_uses_installed_gemma(workspace, monkeypatch):
    monkeypatch.setattr(desktop, "installed_models", lambda: ("gemma4:latest", "qwen3:4b"))
    workspace.settings()
    window = workspace.settings_window
    picker = next(child for child in window.winfo_children() if child.winfo_class() == "TCombobox")
    choices = tuple(picker.cget("values"))
    assert set(choices) == {"qwen3:4b", "gemma4:latest"}
    picker.current(choices.index("gemma4:latest"))
    actions = next(child for child in window.winfo_children() if child.winfo_class() == "Frame")
    save = next(child for child in actions.winfo_children() if child.cget("text") == "Save settings")
    save.invoke()

    workspace.transcript.insert("1.0", "The team agreed to test.")
    workspace.transcript_changed()
    pending = []
    monkeypatch.setattr(workspace, "start_job", lambda *args: pending.append(args))
    workspace.summarize_button.invoke()
    assert pending == [("notes", desktop.create_notes, "The team agreed to test.", "gemma4:latest")]

