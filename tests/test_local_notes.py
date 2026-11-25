"""Check requests, model validation, and long transcripts using a local HTTP fixture."""
import json

import httpx
import pytest

from meetnote import notes


def ollama_fixture(monkeypatch, handler):
    client = httpx.Client
    requests = []

    def record(request):
        assert request.url.host == "127.0.0.1"
        assert request.url.port == 11434
        requests.append(request)
        return handler(request)

    def create_client(**kwargs):
        assert kwargs.pop("trust_env") is False
        assert kwargs.pop("follow_redirects") is False
        return client(transport=httpx.MockTransport(record), **kwargs)

    monkeypatch.setattr(notes.httpx, "Client", create_client)
    return requests


def test_local_model_generates_the_existing_notes_format(monkeypatch):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3:4b"
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details": {"family": "qwen3"}})
        assert request.url.path == "/api/chat"
        assert payload["stream"] is False and payload["think"] is False
        assert payload["format"]["required"] == notes.NOTES_SCHEMA["required"]
        assert payload["messages"][1]["content"] == "Maya will test the microphone on Friday."
        return httpx.Response(200, json={"message": {"content": json.dumps({
            "overview": "The group planned a test.",
            "action_items": [{"task": "Test the microphone", "owner": "Maya", "deadline": "Friday"}],
        })}})

    requests = ollama_fixture(monkeypatch, handler)
    result = notes.create_notes("Maya will test the microphone on Friday.")
    assert [request.url.path for request in requests] == ["/api/show", "/api/chat"]
    assert result["model"] == "qwen3:4b"
    assert result["action_items"][0]["deadline"] == "Friday"


@pytest.mark.parametrize(("details", "match"), [
    (httpx.Response(404, json={}), "ollama pull qwen3:4b"),
    (httpx.Response(200, json={"remote_host": "https://example.com"}), "local copy"),
])
def test_missing_or_remote_model_never_receives_transcript(monkeypatch, details, match):
    requests = ollama_fixture(monkeypatch, lambda _: details)
    with pytest.raises(RuntimeError, match=match):
        notes.create_notes("Private meeting transcript")
    assert len(requests) == 1
    assert b"Private meeting transcript" not in requests[0].content


def test_unavailable_ollama_suggests_starting_the_app(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    ollama_fixture(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="Start Ollama"):
        notes.create_notes("Meeting transcript")


def test_long_unicode_transcript_is_split_and_notes_are_merged(monkeypatch):
    pieces = []

    def handler(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={})
        content = json.loads(request.content)["messages"][1]["content"]
        assert len(content.encode("utf-8")) <= notes.SECTION_BYTES
        pieces.append(content)
        return httpx.Response(200, json={"message": {"content": json.dumps({
            "overview": f"Section {len(pieces)}",
            "decisions": ["Uji mikrofon."],
            "open_questions": ["Siapa akan membentang?"] if "AKHIR" in content else [],
        })}})

    ollama_fixture(monkeypatch, handler)
    transcript = "Mesyuarat: keputusan telah dipersetujui ✅. " * 200 + "AKHIR"
    result = notes.create_notes(transcript)
    assert len(pieces) > 1 and pieces[-1].endswith("AKHIR")
    assert "".join("".join(pieces).split()) == "".join(transcript.split())
    assert result["decisions"] == ["Uji mikrofon."]
    assert result["open_questions"] == ["Siapa akan membentang?"]
    assert result["overview"].startswith("Section 1\n\nSection 2")


def test_english_map_uses_its_own_format_and_merges_later_sections(monkeypatch):
    def handler(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={})
        payload = json.loads(request.content)
        assert payload["format"]["required"] == ["topic", "branches"]
        assert "every branch in English" in payload["messages"][0]["content"]
        transcript = payload["messages"][1]["content"]
        return httpx.Response(200, json={"message": {"content": json.dumps({
            "topic": "Meeting Preparation",
            "branches": ["Microphone Test", "Choose Presenter"] if "AKHIR" in transcript else
                        ["Microphone Test", "microphone test."],
        })}})

    requests = ollama_fixture(monkeypatch, handler)
    result = notes.create_mind_map("Keputusan mesyuarat telah dipersetujui. " * 160 + "AKHIR")
    assert len(requests) >= 3
    assert result == {"topic": "Meeting Preparation", "branches": ["Microphone Test", "Choose Presenter"]}


def test_invalid_summary_returns_an_actionable_error(monkeypatch):
    def handler(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"message": {"content": "invalid JSON"}})

    ollama_fixture(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="invalid response"):
        notes.create_notes("Meeting transcript")



def test_model_picker_excludes_remote_tags(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [
            {"name": "qwen3:4b"},
            {"name": "gemma4:latest"},
            {"name": "gemma4:31b-cloud"},
            {"name": "remote:latest", "remote_model": "cloud-model"},
        ]})

    ollama_fixture(monkeypatch, handler)
    assert notes.installed_models() == ("gemma4:latest", "qwen3:4b")


def test_selected_gemma_tag_is_used_for_check_and_generation(monkeypatch):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "gemma4:latest"
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details": {"family": "gemma4"}})
        return httpx.Response(200, json={"message": {"content": '{"overview":"Notes from Gemma."}'}})

    requests = ollama_fixture(monkeypatch, handler)
    result = notes.create_notes("The meeting is on Friday.", "gemma4:latest")
    assert [request.url.path for request in requests] == ["/api/show", "/api/chat"]
    assert result["model"] == "gemma4:latest"
    assert result["overview"] == "Notes from Gemma."


def test_explicit_cloud_model_is_rejected_before_network_call(monkeypatch):
    requests = ollama_fixture(monkeypatch, lambda _: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ValueError, match="installed local"):
        notes.create_notes("Private transcript", "gemma4:31b-cloud")
    assert requests == []

