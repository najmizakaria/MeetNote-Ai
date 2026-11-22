import io
import wave
import numpy as np
import pytest
from meetnote.audio import to_mono_16k, mix_tracks, wav_bytes, has_audible_content
from meetnote.notes import clean_notes, decode_response, notes_text
from meetnote.export import make_docx
from docx import Document


def test_resample_and_mono():
    t = np.linspace(0, 1, 48000, endpoint=False)
    stereo = np.stack([0.15*np.sin(2*np.pi*220*t), 0.15*np.sin(2*np.pi*220*t)], axis=1)
    out = to_mono_16k(stereo, 48000)
    assert out.shape == (16000,)
    assert has_audible_content(out)


def test_silence_and_invalid_rate():
    assert not has_audible_content(np.zeros(20, dtype=np.float32))
    assert len(to_mono_16k(np.array([]), 48000)) == 0
    with pytest.raises(ValueError):
        to_mono_16k(np.ones(10), 0)


def test_track_mix():
    a = np.full(4, .6, dtype=np.float32)
    b = np.full(2, .2, dtype=np.float32)
    m = mix_tracks([a,b])
    assert np.allclose(m, [.4, .4, .3, .3])


def test_wav_header():
    with wave.open(io.BytesIO(wav_bytes(np.zeros(16000, dtype=np.float32))), 'rb') as f:
        assert f.getframerate() == 16000
        assert f.getnchannels() == 1
        assert f.getnframes() == 16000


def test_json_response_validation():
    value = decode_response('```json\n{"overview":"Agreed", "decisions": ["Use a prototype"], '
                            '"action_items": [{"task":"Test app"}]}\n```')
    assert value['overview'] == 'Agreed'
    assert value['action_items'][0]['owner'] == 'Not specified'
    assert value['action_items'][0]['deadline'] == 'Not specified'
    assert value['decisions'] == ['Use a prototype']


def test_ignores_malformed_action_items():
    n = clean_notes({'action_items': ['bad', {}, {'task': 'Send notes', 'owner': 'Ali'}]})
    assert len(n['action_items']) == 1
    assert n['action_items'][0]['deadline'] == 'Not specified'


def test_notes_text_has_sections():
    text = notes_text('Weekly check-in', '2026-11-22', 'Hello team',
                      {'overview':'Testing','key_points':[], 'decisions':[], 'open_questions':[], 'action_items':[]})
    assert 'Hello team' in text and 'OVERVIEW' in text


def test_docx_output():
    payload = make_docx('Weekly check-in', '2026-11-22', 'Hello team', None)
    document = Document(io.BytesIO(payload))
    assert document.paragraphs[0].text == 'Weekly check-in'
    assert any('Hello team' in p.text for p in document.paragraphs)
