# MeetNote AI for Windows

**SDT 2143 Mini AI Hackathon · AI for Productivity**

MeetNote AI records meeting audio or opens an existing recording, turns speech into an editable transcript with Whisper, and uses Gemini to draft minutes. The notes cover the overview, key points, decisions, actions, and open questions.

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

## Generate and export notes

1. Obtain a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Enter it under **Settings**, select **Save settings**, and choose **Generate notes**. If your key requires a different model, enter the model ID in Settings.
3. Review the generated names, deadlines, and decisions. **Save TXT** and **Save Word** export the edited transcript and any notes generated from that version of the transcript.

Get participants' consent before recording. Audio transcription runs locally. Selecting **Generate notes** sends the transcript to Gemini. A key entered in Settings stays in memory for the session. Export your work before closing the app.

## Source and verification

- **desktop_app.py** provides the native Tk interface and runs transcription and Gemini calls in background threads.
- **meetnote/** contains audio conversion, device capture, transcription, Gemini integration, and Word export.
- **tools/Launcher.cs** launches the portable Python runtime from the same folder.
- **app.py** remains the Streamlit entry point. See [the web prototype guide](docs/STREAMLIT.md) to run it.
- To run the source tests, install **pytest** in the project virtual environment and execute **python -m pytest -q** from this folder.
