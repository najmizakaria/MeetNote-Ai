"""MeetNote AI's native Windows workspace."""
from __future__ import annotations

from collections import deque
from datetime import date
from functools import lru_cache
import os
from pathlib import Path
from queue import Empty, Queue
import re
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from meetnote.notes import DEFAULT_MODEL, create_notes, notes_text
from meetnote.transcriber import LANGUAGES, make_model, transcribe_bytes, transcribe_file


PAPER = "#F2F6F7"
WHITE = "#FFFFFF"
INK = "#17333B"
MUTED = "#51676D"
BORDER = "#D5E1E3"
TEAL = "#176B68"
PALE = "#E6F1EF"
RUST = "#A73827"
FONT = "Segoe UI"
CHUNK_SECONDS = 8
AUDIO_TYPES = [("Audio and recordings", "*.wav *.mp3 *.m4a *.mp4 *.ogg *.opus *.flac *.webm *.aac"),
               ("All files", "*.*")]
MODELS = ("tiny", "base", "small")
SOURCES = ("Microphone", "Laptop audio", "Both")
get_model = lru_cache(maxsize=1)(make_model)


def describe(error, secret=""):
    text = " ".join(str(error).split()) or type(error).__name__
    if secret:
        text = text.replace(secret, "[hidden]")
    text = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[hidden]", text)
    return text[:240]


def recognize(source, language, model_name):
    model = get_model(model_name)
    if isinstance(source, Path):
        return transcribe_file(source, model, language)
    return transcribe_bytes(source, ".wav", model, language)


class MeetNoteApp:
    def __init__(self, root):
        self.root = root
        root.title("MeetNote AI")
        icon = Path(__file__).with_name("meetnote.ico")
        if os.name == "nt" and icon.is_file():
            root.iconbitmap(str(icon))
        root.configure(bg=PAPER)
        width = min(1240, root.winfo_screenwidth() - 55)
        height = min(770, root.winfo_screenheight() - 105)
        root.geometry(f"{width}x{height}")
        root.minsize(min(980, width), min(610, height))
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.capture = None
        self.audio = deque()
        self.results = Queue()
        self.job = None
        self.job_source = None
        self.failed = False
        self.notes = None
        self.notes_source = ""
        self.devices = {}
        self.capture_settings = None
        self.audio_warning = ""
        self.settings_window = None

        self.title = tk.StringVar(value="Untitled meeting")
        self.date = tk.StringVar(value=date.today().isoformat())
        self.mode = tk.StringVar(value=SOURCES[0])
        self.mic = tk.StringVar()
        self.loopback = tk.StringVar()
        self.language = tk.StringVar(value="Auto detect")
        self.whisper = "tiny"
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
        self.status = tk.StringVar(value="Record a meeting or open an audio file to begin.")
        self.timer = tk.StringVar(value="00:00")
        self.capture_label = tk.StringVar(value="Ready to record")
        self.transcript_label = tk.StringVar(value="0 words")
        self.language_label = ""

        self.style()
        self.layout()
        root.bind("<Control-o>", lambda event: self.open_audio())
        root.after(100, self.refresh_devices)
        root.after(100, self.tick)

    def style(self):
        self.theme = ttk.Style(self.root)
        self.theme.theme_use("clam")
        self.theme.configure(".", font=(FONT, 10), foreground=INK)
        self.theme.configure("TButton", background=WHITE, bordercolor=BORDER,
                             lightcolor=WHITE, darkcolor=WHITE, padding=(12, 6),
                             focusthickness=2, focuscolor=TEAL)
        self.theme.map("TButton", background=[("active", PALE)],
                       foreground=[("disabled", "#637579")])
        for variant, color, hover in (("Primary", TEAL, "#125754"),
                                       ("Danger", RUST, "#842C20")):
            name = f"{variant}.TButton"
            self.theme.configure(name, background=color, foreground=WHITE,
                                 bordercolor=color, lightcolor=color, darkcolor=color,
                                 focuscolor=WHITE)
            self.theme.map(name, background=[("disabled", PALE), ("active", hover)],
                           foreground=[("disabled", MUTED)])
        self.theme.configure("TEntry", fieldbackground=WHITE, bordercolor=BORDER, padding=6)
        self.theme.configure("TCombobox", fieldbackground=WHITE, background=PALE,
                             bordercolor=BORDER, arrowcolor=TEAL, padding=5)
        self.theme.map("TCombobox", fieldbackground=[("readonly", WHITE)],
                       selectbackground=[("readonly", WHITE)], selectforeground=[("readonly", INK)])
        self.theme.configure("Vertical.TScrollbar", background=PALE, troughcolor=WHITE,
                             bordercolor=WHITE, arrowcolor=MUTED)

    def label(self, parent, text="", *, bg=WHITE, fg=INK, size=10, face=FONT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=bg, fg=fg, anchor="w",
                        font=(face, size, "bold" if bold else "normal"), **kwargs)

    def card(self, parent):
        return tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1,
                        padx=17, pady=11)

    def field(self, parent, label, variable, values=None):
        self.label(parent, label, bold=True).pack(anchor="w", pady=(5, 3))
        control = (ttk.Entry(parent, textvariable=variable) if values is None else
                   ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=25))
        control.pack(fill="x")
        return control

    def editor(self, parent, *, editable=False):
        frame = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, pady=(13, 12))
        editor = tk.Text(frame, wrap="word", highlightthickness=0, borderwidth=0,
                         bg="#FAFCFC", fg=INK, insertbackground=TEAL, selectbackground="#C3E4DF",
                         padx=12, pady=12, spacing1=2, spacing3=5, width=5, height=7,
                         undo=editable, font=(FONT, 11), tabs=("16p",))
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=editor.yview)
        editor.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        editor.pack(side="left", fill="both", expand=True)
        return editor

    def layout(self):
        header = tk.Frame(self.root, bg=WHITE, padx=25, pady=9)
        header.pack(fill="x")
        logo = tk.Canvas(header, width=34, height=34, bg=TEAL, highlightthickness=0)
        logo.pack(side="left", padx=(0, 10))
        for x, amplitude in ((7, 4), (12, 8), (17, 12), (22, 7), (27, 3)):
            logo.create_line(x, 17-amplitude, x, 17+amplitude, fill=WHITE, width=2, capstyle="round")
        self.label(header, "MeetNote AI", size=16, bold=True).pack(side="left")
        ttk.Button(header, text="Settings", command=self.settings).pack(side="right")
        self.new_button = ttk.Button(header, text="New meeting", command=self.reset)
        self.new_button.pack(side="right", padx=(0, 8))

        intro = tk.Frame(self.root, bg=PAPER, padx=25, pady=10)
        intro.pack(fill="x")
        self.label(intro, "Meeting workspace", bg=PAPER, size=23, bold=True).pack(anchor="w")


        body = tk.Frame(self.root, bg=PAPER)
        body.pack(fill="both", expand=True, padx=25, pady=(2, 10))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, minsize=255)
        body.grid_columnconfigure(1, weight=3, minsize=260)
        body.grid_columnconfigure(2, weight=2, minsize=265)
        capture = self.card(body)
        capture.grid(row=0, column=0, sticky="nsew")
        transcript = self.card(body)
        transcript.grid(row=0, column=1, sticky="nsew", padx=12)
        notes = self.card(body)
        notes.grid(row=0, column=2, sticky="nsew")

        capture_header = tk.Frame(capture, bg=WHITE)
        capture_header.pack(fill="x")
        self.label(capture_header, "Capture", size=17, bold=True).pack(side="left")
        self.refresh_button = ttk.Button(capture_header, text="Refresh", command=self.refresh_devices)
        self.refresh_button.pack(side="right")
        meter = tk.Frame(capture, bg=INK, padx=12, pady=5)
        meter.pack(fill="x", pady=(7, 3))
        self.label(meter, textvariable=self.timer, bg=INK, fg=WHITE, size=21,
                   face="Consolas").pack(anchor="w")
        self.meter_status = self.label(meter, textvariable=self.capture_label, bg=INK, fg="#BCE1DB")
        self.meter_status.pack(anchor="w")

        self.mode_box = self.field(capture, "Audio source", self.mode, SOURCES)
        self.mode_box.bind("<<ComboboxSelected>>", lambda event: self.refresh_controls())
        self.device_box = self.field(capture, "Input device", self.mic, ())
        self.second_device = tk.Frame(capture, bg=WHITE)
        self.second_box = self.field(self.second_device, "Laptop audio input", self.loopback, ())

        self.record_button = ttk.Button(capture, text="Start recording", style="Primary.TButton",
                                        command=self.toggle_recording)
        self.record_button.pack(fill="x", pady=(9, 5))
        self.open_button = ttk.Button(capture, text="Open audio file…", command=self.open_audio)
        self.open_button.pack(fill="x")


        self.label(transcript, "Transcript", size=17, bold=True).pack(anchor="w")
        metadata = tk.Frame(transcript, bg=WHITE)
        metadata.pack(fill="x", pady=(3, 0))
        self.field(metadata, "Meeting title", self.title)
        self.field(metadata, "Meeting date", self.date)
        self.transcript = self.editor(transcript, editable=True)
        self.transcript.bind("<<Modified>>", self.transcript_changed)
        self.placeholder = self.label(self.transcript, "Record, open audio or type here.", bg="#FAFCFC", fg=MUTED)
        self.placeholder.place(x=12, y=11)
        self.placeholder.bind("<Button-1>", lambda event: self.transcript.focus_set())
        self.transcript.bind("<FocusIn>", lambda event: self.placeholder.place_forget())
        self.transcript.bind("<FocusOut>", lambda event: self.update_transcript_label())
        self.label(transcript, textvariable=self.transcript_label, fg=MUTED).pack(anchor="w")

        self.label(notes, "Meeting notes", size=17, bold=True).pack(anchor="w")
        self.label(notes, "Generated from the current transcript", fg=MUTED).pack(anchor="w", pady=(4, 0))
        self.note_view = self.editor(notes)
        self.note_view.tag_configure("heading", font=(FONT, 11, "bold"), foreground=TEAL, spacing1=10)
        self.note_view.tag_configure("hint", foreground=MUTED)
        self.render_notes()
        self.summarize_button = ttk.Button(notes, text="Generate notes", style="Primary.TButton",
                                           command=self.summarize)
        self.summarize_button.pack(fill="x", pady=(0, 8))
        exports = tk.Frame(notes, bg=WHITE)
        exports.pack(fill="x")
        exports.grid_columnconfigure((0, 1), weight=1)
        self.txt_button = ttk.Button(exports, text="Save TXT", command=lambda: self.export(".txt"))
        self.txt_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.docx_button = ttk.Button(exports, text="Save Word", command=lambda: self.export(".docx"))
        self.docx_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.status_bar = self.label(self.root, textvariable=self.status, bg=PAPER, fg=MUTED,
                                     padx=25, pady=6, justify="left", wraplength=920)
        self.status_bar.pack(fill="x", side="bottom", before=body)
        self.refresh_controls()

    def message(self, text, error=False):
        self.status.set(text)
        self.status_bar.configure(fg=RUST if error else MUTED)

    def refresh_devices(self):
        if self.capture:
            return
        try:
            import sounddevice as sd
            from meetnote.local_capture import list_inputs

            apis = sd.query_hostapis()
            all_devices = sd.query_devices()
            self.devices = {
                f"{d['name']} [{apis[all_devices[d['index']]['hostapi']]['name']}] · {d['index']}": d["index"]
                for d in list_inputs()
            }
            names = tuple(self.devices)
            default = sd.default.device[0]
            default_name = next((label for label, index in self.devices.items() if index == default), "")
            if self.mic.get() not in self.devices:
                self.mic.set(default_name or next(iter(names), ""))
            if self.loopback.get() not in self.devices:
                self.loopback.set(next((label for label in names if any(
                    token in label.lower() for token in ("stereo mix", "cable output", "loopback"))), ""))
            for box in (self.device_box, self.second_box):
                box.configure(values=names)
            if not names:
                self.message("No recording devices found. You can still open an audio file.", error=True)
            elif self.job is None and not self.failed:
                self.message("Audio devices ready. Select a source or open an audio file.")
        except Exception as error:
            self.message(f"Could not list audio devices. {describe(error)}", error=True)
        self.refresh_controls()

    def refresh_controls(self):
        recording = self.capture is not None
        busy = self.job is not None
        mode = self.mode.get()
        both = mode == SOURCES[2]
        if both and not self.second_device.winfo_manager():
            self.second_device.pack(before=self.record_button, fill="x")
        elif not both:
            self.second_device.pack_forget()
        variable = self.loopback if mode == SOURCES[1] else self.mic
        if str(self.device_box.cget("textvariable")) != str(variable):
            self.device_box.configure(textvariable=variable)

        for control in (self.mode_box, self.device_box, self.second_box):
            control.configure(state="disabled" if recording or busy else "readonly")
        self.record_button.configure(
            text="Stop recording" if recording else ("Retry audio" if self.failed else "Start recording"),
            style="Danger.TButton" if recording else "Primary.TButton",
            state="normal" if recording or (not busy and (self.failed or self.devices)) else "disabled",
        )
        self.open_button.configure(state="disabled" if recording or busy else "normal")
        self.refresh_button.configure(state="disabled" if recording or busy else "normal")
        self.new_button.configure(state="disabled" if recording or busy else "normal")
        has_text = bool(self.current_transcript())
        self.summarize_button.configure(state="normal" if has_text and not recording and not busy else "disabled")
        for control in (self.txt_button, self.docx_button):
            control.configure(state="normal" if has_text else "disabled")

    def toggle_recording(self):
        if self.capture:
            self.stop_capture()
            self.start_audio_job()
            return
        if self.failed:
            language = LANGUAGES[self.language.get()]
            self.audio = deque((source, language, self.whisper) for source, _, _ in self.audio)
            self.failed = False
            self.start_audio_job()
            return

        try:
            from meetnote.local_capture import LocalCapture

            mode = self.mode.get()
            devices = {}
            if mode in (SOURCES[0], SOURCES[2]):
                if self.mic.get() not in self.devices:
                    raise ValueError("Choose a microphone input device.")
                devices["microphone"] = self.devices[self.mic.get()]
            if mode in (SOURCES[1], SOURCES[2]):
                if self.loopback.get() not in self.devices:
                    raise ValueError("Select a laptop-audio input such as Stereo Mix or CABLE Output.")
                devices["laptop audio"] = self.devices[self.loopback.get()]
            capture = LocalCapture(devices)
            capture.start()
        except Exception as error:
            self.message(f"Recording could not start. {describe(error)}", error=True)
            return
        self.capture = capture
        self.capture_settings = (LANGUAGES[self.language.get()], self.whisper)
        self.audio_warning = ""
        self.timer.set("00:00")
        self.capture_label.set("Recording live")
        self.meter_status.configure(fg="#FFB7A5")
        self.message("Recording. Whisper processes audio in sections as it becomes available.")
        self.refresh_controls()

    def enqueue_recording(self):
        try:
            audio = self.capture.drain()
            if audio:
                self.audio.append((audio, *self.capture_settings))
        except Exception as error:
            self.audio_warning = f"Audio could not be read. {describe(error)}"

    def stop_capture(self):
        self.capture.stop()
        self.enqueue_recording()
        if self.capture.last_error and not self.audio_warning:
            self.audio_warning = f"Audio device reported {self.capture.last_error}. Check for missing speech."
        self.capture = None
        self.capture_label.set("Recording stopped")
        self.meter_status.configure(fg="#BCE1DB")
        if self.audio_warning:
            self.message(self.audio_warning, error=True)
        elif not self.audio:
            self.message("Recording stopped. No additional audio was captured.")
        self.refresh_controls()

    def open_audio(self):
        if self.job or self.capture:
            return
        filename = filedialog.askopenfilename(parent=self.root, title="Open meeting audio", filetypes=AUDIO_TYPES)
        if not filename:
            return
        if self.failed and not messagebox.askyesno(
            "Replace pending audio?", "This discards pending audio and keeps the current transcript.",
            parent=self.root,
        ):
            return
        self.audio.clear()
        self.failed = False
        self.audio_warning = ""
        self.audio.append((Path(filename), LANGUAGES[self.language.get()], self.whisper))
        self.start_audio_job()

    def start_job(self, name, function, *args, secret=""):
        def run():
            try:
                self.results.put((name, function(*args), ""))
            except Exception as error:
                self.results.put((name, None, describe(error, secret)))

        self.job = name
        self.refresh_controls()
        Thread(target=run, daemon=True).start()

    def start_audio_job(self):
        if self.job or not self.audio or self.failed:
            return
        source, language, model = self.audio[0]
        label = source.name if isinstance(source, Path) else "recorded audio"
        self.message(f"Transcribing {label}. This can take a moment.")
        self.start_job("audio", recognize, source, language, model)

    def tick(self):
        try:
            name, value, error = self.results.get_nowait()
        except Empty:
            pass
        else:
            self.job = None
            if name == "audio":
                self.audio_result(value, error)
            else:
                self.notes_result(value, error)
            self.refresh_controls()
        if self.capture:
            elapsed = int(self.capture.elapsed)
            minutes, seconds = divmod(elapsed, 60)
            self.timer.set(f"{minutes:02d}:{seconds:02d}")
            if not self.job and self.capture.buffered_seconds() >= CHUNK_SECONDS:
                self.enqueue_recording()
                self.start_audio_job()
        self.root.after(100, self.tick)

    def audio_result(self, value, error):
        if error:
            self.failed = True
            if self.capture:
                self.stop_capture()
            self.message(f"Transcription failed. {error} Use Retry audio or open another file.", error=True)
            return
        self.audio.popleft()
        sentence, language = value
        if sentence:
            if self.current_transcript():
                self.transcript.insert("end-1c", "\n\n")
            self.transcript.insert("end-1c", sentence)
            if self.root.focus_get() != self.transcript:
                self.transcript.see("end")
            self.language_label = {code: name for name, code in LANGUAGES.items()}.get(language, language or "")
            self.transcript_changed()
        if self.audio:
            self.start_audio_job()
        elif self.audio_warning:
            self.message(self.audio_warning, error=True)
        elif self.capture:
            self.message("Recording. Transcript updated." if sentence else "Recording. No clear speech in the last section.")
        else:
            self.message("Transcription complete." if sentence else "No clear speech in this audio section.")

    def current_transcript(self):
        return self.transcript.get("1.0", "end-1c").strip() if hasattr(self, "transcript") else ""

    def update_transcript_label(self):
        text = self.current_transcript()
        words = len(text.split())
        suffix = f"  ·  {self.language_label}" if self.language_label else ""
        self.transcript_label.set(f"{words} {'word' if words == 1 else 'words'}{suffix}")
        if not text and self.root.focus_get() != self.transcript:
            self.placeholder.place(x=12, y=11)
        else:
            self.placeholder.place_forget()

    def transcript_changed(self, event=None):
        if event and not self.transcript.edit_modified():
            return
        self.transcript.edit_modified(False)
        self.update_transcript_label()
        if self.notes is not None and self.current_transcript() != self.notes_source:
            self.notes = None
            self.render_notes("The transcript changed. Generate notes again.")
        self.refresh_controls()

    def settings(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        window = self.settings_window = tk.Toplevel(self.root)
        window.title("MeetNote AI Settings")
        window.transient(self.root)
        window.resizable(False, False)
        window.configure(bg=WHITE, padx=20, pady=16)
        key = tk.StringVar(value=self.api_key)
        gemini = tk.StringVar(value=self.gemini)
        model = tk.StringVar(value=self.whisper)
        language = tk.StringVar(value=self.language.get())
        self.label(window, "AI settings", size=17, bold=True).pack(anchor="w")
        key_field = self.field(window, "Gemini API key", key)
        key_field.configure(show="•", width=45)
        self.label(window, "The key stays in memory for this session.", fg=MUTED).pack(anchor="w", pady=(4, 0))
        self.field(window, "Gemini model", gemini)
        self.field(window, "Speech language", language, tuple(LANGUAGES))
        self.field(window, "Whisper model", model, MODELS)
        self.label(window, "Tiny is fastest. Larger models take longer on a CPU.", fg=MUTED).pack(anchor="w", pady=(4, 0))
        self.label(window, "For laptop audio, enable Stereo Mix or use a virtual cable.",
                   fg=MUTED, wraplength=315, justify="left").pack(anchor="w", pady=(5, 3))

        def save():
            self.api_key = key.get().strip()
            self.gemini = gemini.get().strip() or DEFAULT_MODEL
            self.whisper = model.get()
            self.language.set(language.get())
            window.destroy()
            if not self.job and not self.capture and not self.failed:
                self.message("Settings saved for this session.")

        actions = tk.Frame(window, bg=WHITE)
        actions.pack(fill="x", pady=(13, 0))
        ttk.Button(actions, text="Save settings", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(actions, text="Cancel", command=window.destroy).pack(side="right", padx=(0, 8))
        window.bind("<Escape>", lambda event: window.destroy())
        key_field.focus_set()

    def summarize(self):
        source = self.current_transcript()
        if not source or self.capture or self.job:
            return
        if not self.api_key:
            self.message("Add a Gemini API key in Settings to generate notes.", error=True)
            self.settings()
            return
        if len(source) > 60000:
            self.message("This transcript exceeds 60,000 characters. Summarize it in smaller sections.", error=True)
            return
        self.job_source = source
        self.message("Generating notes with Gemini. The transcript is sent to Google.")
        self.start_job("notes", create_notes, source, self.api_key, self.gemini, secret=self.api_key)

    def notes_result(self, value, error):
        if error:
            self.message(f"Gemini could not generate notes. {error} Your transcript is available.", error=True)
        elif self.current_transcript() != self.job_source:
            self.message("The transcript changed while Gemini was working. Generate notes again.", error=True)
        else:
            self.notes = value
            self.notes_source = self.job_source
            self.render_notes()
            self.message("Meeting notes ready. Review the decisions and deadlines before sharing.")
        self.job_source = None

    def render_notes(self, hint="Add a transcript, then select Generate notes."):
        view = self.note_view
        view.configure(state="normal")
        view.delete("1.0", "end")
        if self.notes:
            view.insert("end", "Overview\n", "heading")
            view.insert("end", self.notes["overview"] or "None stated", ())
            for key, heading in (("key_points", "Key points"), ("decisions", "Decisions"),
                                 ("action_items", "Action items"), ("open_questions", "Open questions")):
                view.insert("end", f"\n{heading}\n", "heading")
                lines = self.notes[key]
                if key == "action_items":
                    lines = [f"{item['task']}\n     Owner: {item['owner']}  ·  Due: {item['deadline']}" for item in lines]
                view.insert("end", "\n".join(f"•  {line}" for line in lines) or "None stated", ())
        else:
            view.insert("end", hint, "hint")
        view.configure(state="disabled")

    def export(self, suffix):
        transcript = self.current_transcript()
        if not transcript:
            return
        title = self.title.get().strip() or "Untitled meeting"
        meeting_date = self.date.get().strip() or date.today().isoformat()
        notes = self.notes if self.notes_source == transcript else None
        filename = re.sub(r'[^a-zA-Z0-9 _.-]', "", title).strip(" .")[:80] or "Meeting notes"
        label = "Word document" if suffix == ".docx" else "Text file"
        destination = filedialog.asksaveasfilename(parent=self.root, title="Save meeting",
                                                   initialfile=filename + suffix, defaultextension=suffix,
                                                   filetypes=[(label, "*" + suffix)])
        if not destination:
            return
        try:
            path = Path(destination)
            if suffix == ".docx":
                from meetnote.export import make_docx

                path.write_bytes(make_docx(title, meeting_date, transcript, notes))
            else:
                path.write_text(notes_text(title, meeting_date, transcript, notes), encoding="utf-8")
        except Exception as error:
            self.message(f"Could not save the file. {describe(error)}", error=True)
        else:
            self.message(f"Saved {path.name}.")

    def reset(self):
        if self.capture or self.job:
            return
        if (self.current_transcript() or self.audio) and not messagebox.askyesno(
            "Start a new meeting?", "This clears the current transcript, notes and pending audio.",
            parent=self.root,
        ):
            return
        self.audio.clear()
        self.failed = False
        self.notes = None
        self.notes_source = ""
        self.language_label = ""
        self.audio_warning = ""
        self.transcript.delete("1.0", "end")
        self.transcript.edit_reset()
        self.title.set("Untitled meeting")
        self.date.set(date.today().isoformat())
        self.timer.set("00:00")
        self.capture_label.set("Ready to record")
        self.render_notes()
        self.transcript_changed()
        self.message("New meeting ready.")

    def close(self):
        if (self.capture or self.job or self.audio or self.current_transcript()) and not messagebox.askyesno(
            "Close MeetNote AI?", "The current session will close. Saved exports remain on your computer.",
            parent=self.root,
        ):
            return
        if self.capture:
            self.capture.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    MeetNoteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
