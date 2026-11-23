# MeetNote AI for Windows

**SDT 2143 Mini AI Hackathon · AI for Productivity**

MeetNote AI records meeting audio or opens an existing recording, turns speech into an editable transcript with Whisper, and uses local Ollama models to draft minutes. The notes cover the overview, key points, decisions, actions, and open questions.

## Open the app

- Open **MeetNote AI.exe** on 64-bit Windows. Keep the app files together.
- To run or modify the Python source, install 64-bit Python 3.11 with Tcl/Tk and the Windows launcher, then double-click **run_windows.bat**. The first run installs the dependencies into a project-local virtual environment.

Whisper runs on your CPU. The Windows package includes the **Tiny** model, so the default transcription works offline. **Base** and **Small** download on first use. Use **Settings** to change the model or explicitly select English, Bahasa Melayu, or Indonesian.

## Record or open audio

1. Enter the meeting title and date. You can also edit them after transcription.
2. Choose **Microphone**, **Laptop audio**, or **Both**. In **Both**, select two distinct devices.
3. Select **Start recording**, then **Stop recording** at the end. Transcription starts on roughly eight seconds of buffered audio. On a slower PC or during the model's first load, more audio may accumulate before the next update.
4. To transcribe an existing recording, select **Open audio file**. WAV, MP3, M4A, and other common formats are supported.
5. Review and edit the transcript. You can also paste a transcript directly into the editor.

To try transcription without recording, open **examples/Sample meeting.wav**. This synthetic example contains a decision about testing and two named actions.

For **Laptop audio**, use an input such as **Stereo Mix** if your Windows sound driver provides it. With [VB-Cable](https://vb-audio.com/Cable/), send the meeting application's sound to **CABLE Input** and select **CABLE Output** in MeetNote AI. Select **Refresh** after changing devices. Using two devices can introduce slight alignment drift.

## Set up local notes

1. Install [Ollama for Windows](https://ollama.com/download/windows) and start Ollama.
2. Run **ollama pull qwen3:4b** in PowerShell. Ollama downloads roughly 2.5 GB once. The audio and local notes models are separate downloads.
3. Enable [Ollama local-only mode](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features) by setting **OLLAMA_NO_CLOUD** to **1** for your Windows user. Quit and reopen Ollama so the change takes effect.
4. Open MeetNote AI, add a transcript, and choose **Generate notes**. The app connects to Ollama at **127.0.0.1:11434** and defaults to **qwen3:4b**. Longer transcripts are summarized in sections.
5. Check names, decisions, and due dates. Use **Save TXT** or **Save Word** to export the edited transcript and its current notes.

To switch the Windows app to an installed model such as **gemma4:latest**, open **Settings → Summary model**, select its exact tag, and click **Save settings**. Your choice applies to the current session. Open Settings again after a new model finishes downloading so the list refreshes.

If Ollama is stopped, open it and retry. If a selected model is missing, choose an installed model in Settings or download the selected tag with Ollama. Recording, transcription, and transcript export are available independently of Ollama. After the models are downloaded, the complete workflow can run offline and needs no API key.

Get participants' consent before recording. Export your work before closing the app.

## Source and verification

- **desktop_app.py** provides the native Tk interface and runs transcription and summary requests in background threads.
- **meetnote/** contains audio conversion, device capture, transcription, local Ollama summaries, and Word export.
- **tools/Launcher.cs** launches the portable Python runtime from the same folder.
- **app.py** runs the local Streamlit interface. See [the web prototype guide](docs/STREAMLIT.md) to run it.
- To run the source tests, install **pytest** in the project virtual environment and execute **python -m pytest -q** from this folder.
