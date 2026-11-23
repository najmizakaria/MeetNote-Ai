"""Check that the desktop workflow keeps transcript and export state consistent."""
import io
from pathlib import Path
import tkinter as tk

from docx import Document
import pytest

import desktop_app as desktop
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

