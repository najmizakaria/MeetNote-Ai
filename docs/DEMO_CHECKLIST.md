# Demo and QA checklist

- [ ] GitHub push works and `.gitignore` excludes runtime bundles and virtual environments.
- [ ] The Windows app opens and Qwen3 is installed in Ollama.
- [ ] Browser microphone records a 20–30 second consented test; stop then transcribe.
- [ ] In the Windows app, Whisper warms up, the live draft updates during speech, and the last phrase is added after Stop.
- [ ] Local laptop audio (Stereo Mix / VB-Cable) receives actual speaker output.
- [ ] Local Both uses distinct input devices and picks up both voices.
- [ ] English and Malay-language meeting scripts have their expected language set.
- [ ] Manually correct transcript before summarizing if Whisper errs.
- [ ] With the internet disconnected, Qwen3 generates notes from English and Bahasa Melayu transcripts.
- [ ] Missing owner or deadline remains 'Not specified' rather than invented.
- [ ] Stop Ollama or try before installing the model and confirm the transcript can still be exported.
- [ ] TXT and DOCX download both open and contain the correct transcript.
- [ ] Check the Windows layout at its minimum window size.
- [ ] Record screen demo showing actual audio and notes, not fabricated output.
- [ ] Capture version/library information and real screenshots for the report.

Suggested safe demo script: “For our assignment, we agreed to prepare the prototype by Thursday. Mira will test microphone recording. We still need to decide whether to add saved meeting history. The next meeting is Friday.” Expected: one agreed decision (prepare prototype), one action with owner Mira and no date, and one open question about history. Do not assign the Thursday deadline to Mira's microphone test.
