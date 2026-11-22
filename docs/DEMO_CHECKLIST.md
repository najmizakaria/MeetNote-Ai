# Demo and QA checklist

- [ ] GitHub push works and `.gitignore` excludes API keys and virtual environments.
- [ ] Public app opens at an HTTPS Streamlit URL.
- [ ] Browser microphone records a 20–30 second consented test; stop then transcribe.
- [ ] Local microphone records and the transcript updates after approx 8 seconds.
- [ ] Local laptop audio (Stereo Mix / VB-Cable) receives actual speaker output.
- [ ] Local Both uses distinct input devices and picks up both voices.
- [ ] English and Malay-language meeting scripts have their expected language set.
- [ ] Manually correct transcript before summarizing if Whisper errs.
- [ ] Gemini generates overview, points, decisions and actions from known reference script.
- [ ] Missing owner or deadline remains 'Not specified' rather than invented.
- [ ] Simulate invalid API key or unavailable model: transcript remains available for retry.
- [ ] TXT and DOCX download both open and contain the correct transcript.
- [ ] Test on a phone browser for narrow-viewport overflow.
- [ ] Record screen demo showing actual audio and notes, not fabricated output.
- [ ] Capture version/library information and real screenshots for the report.

Suggested safe demo script: “For our assignment, we agreed to prepare the prototype by Thursday. Mira will test microphone recording. We still need to decide whether to add saved meeting history. The next meeting is Friday.” Expected: one agreed decision (prepare prototype), one action with owner Mira and no date, and one open question about history. Do not assign the Thursday deadline to Mira's microphone test.
