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
