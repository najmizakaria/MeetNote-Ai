# MeetNote AI in a Local Browser

The Streamlit interface runs on the same Windows PC as Ollama. Its recording and upload workflows use Whisper for transcription and Qwen3 4B for structured notes. The browser interface is served on loopback.

## Set up and run

1. Follow the [local notes setup in the project README](../README.md#set-up-local-notes).
2. From the project directory, run these commands in PowerShell.

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
~~~

3. Open the local address shown in the terminal. The default is **http://127.0.0.1:8501**.

The portable Windows project includes the Tiny Whisper model. A fresh source checkout or a switch to Base or Small may require a one-time Whisper download.

## Capture and generate notes

- **Browser microphone** records a clip, then transcribes it after you stop. Allow microphone access when the browser asks.
- **Local audio devices** captures a microphone, a system audio input such as Stereo Mix, or both. To switch during recording, choose the new inputs and select **Apply audio source**. Whisper updates as audio sections finish.
- **Upload audio** transcribes an existing recording.
- Edit the transcript, choose **Generate AI meeting notes**, and check the results. Download the output as TXT, Word, or plain transcript.

Ollama needs to be running with the local Qwen3 model installed. If it is stopped or the model is missing, the transcript remains available for editing and export. Keep the session open until you have saved your work.
