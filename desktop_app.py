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

from meetnote.live_transcription import LiveClip, LiveSpeech
from meetnote.notes import MAX_TRANSCRIPT_CHARS, MODEL, create_mind_map, create_notes, installed_models, notes_text
from meetnote.transcriber import LANGUAGES, make_model, transcribe_file, transcribe_live


PAPER = "#F2F6F7"
WHITE = "#FFFFFF"
INK = "#17333B"
MUTED = "#51676D"
BORDER = "#D5E1E3"
TEAL = "#176B68"
PALE = "#E6F1EF"
RUST = "#A73827"
FONT = "Segoe UI"
LIVE_POLL_SECONDS = 0.25
DRAFT_HINT = "Draft captions appear here while you speak."
AUDIO_TYPES = [("Audio and recordings", "*.wav *.mp3 *.m4a *.mp4 *.ogg *.opus *.flac *.webm *.aac"),
               ("All files", "*.*")]
MODELS = ("tiny", "base", "small")
SOURCES = ("Microphone", "Laptop audio", "Both")
get_model = lru_cache(maxsize=1)(make_model)


def describe(error):
    return (" ".join(str(error).split()) or type(error).__name__)[:240]


def recognize(source, language, model_name):
    model = get_model(model_name)
    if isinstance(source, Path):
        return transcribe_file(source, model, language)
    return transcribe_live(source.samples, model, language, start=source.start, cutoff=source.cutoff)


def recognize_draft(samples, language, model_name):
    return transcribe_live(samples, get_model(model_name), language, draft=True)[0]


def warm_whisper(model_name):
    from faster_whisper.vad import get_vad_model
    import numpy as np
    from meetnote.audio import TARGET_RATE

    model = get_model(model_name)
    get_vad_model()
    transcribe_live(np.zeros(TARGET_RATE // 4, dtype=np.float32), model, "en", draft=True)


class MindMapPreview(tk.Toplevel):
    def __init__(self, parent, image, topic, source, save):
        super().__init__(parent)
        self.title("Mind map · MeetNote AI")
        self.transient(parent)
        self.configure(bg=WHITE)
        size = min(720, self.winfo_screenheight() - 170, self.winfo_screenwidth() - 90)
        self.geometry(f"{size}x{size + 56}")
        self.minsize(445, 400)
        self.image = image
        self.topic = topic
        self.source = source
        self.status = tk.StringVar(master=self, value=f"{image.width} × {image.height} PNG")

        toolbar = tk.Frame(self, bg=PAPER, padx=14, pady=9)
        toolbar.pack(side="bottom", fill="x")
        ttk.Button(toolbar, text="Close", command=self.destroy).pack(side="right")
        self.save_button = ttk.Button(toolbar, text="Save PNG", style="Primary.TButton", command=save)
        self.save_button.pack(side="right", padx=(0, 8))
        tk.Label(toolbar, textvariable=self.status, bg=PAPER, fg=INK, font=(FONT, 10),
                 anchor="w", justify="left", wraplength=230).pack(side="left", fill="x", expand=True)

        self.canvas = tk.Canvas(self, bg=WHITE, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.picture = self.canvas.create_image(0, 0)
        self.canvas.bind("<Configure>", self.resize_image)
        self.bind("<Escape>", lambda event: self.destroy())
        self.save_button.focus_set()

    def resize_image(self, event):
        from PIL import Image, ImageTk

        size = max(1, min(event.width, event.height) - 16)
        if not hasattr(self, "preview_image") or self.preview_image.width() != size:
            scaled = self.image.resize((size, size), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(scaled, master=self)
            self.canvas.itemconfigure(self.picture, image=self.preview_image)
        self.canvas.coords(self.picture, event.width / 2, event.height / 2)

    def invalidate(self):
        self.save_button.state(["disabled"])
        self.status.set("Transcript changed. Select Create mind map again.")


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
        self.live = None
        self.draft_revision = None
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
        self.map_preview = None
        self.mind_map = {}
        self.map_source = ""

        self.title = tk.StringVar(value="Untitled meeting")
        self.date = tk.StringVar(value=date.today().isoformat())
        self.mode = tk.StringVar(value=SOURCES[0])
        self.mic = tk.StringVar()
        self.loopback = tk.StringVar()
        self.language = tk.StringVar(value="Auto detect")
        self.whisper = "tiny"
        self.warm_model = None
        self.warm_error = ""
        self.whisper_status = tk.StringVar(value="Loading Whisper…")
        self.summary_model = tk.StringVar(value=MODEL)
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

        self.source_button = ttk.Button(capture, text="Apply audio source", command=self.switch_audio_source)
        self.source_error = self.label(capture, fg=RUST, wraplength=210, justify="left")
        self.record_button = ttk.Button(capture, text="Start recording", style="Primary.TButton",
                                        command=self.toggle_recording)
        self.record_button.pack(fill="x", pady=(9, 5))
        self.open_button = ttk.Button(capture, text="Open audio file…", command=self.open_audio)
        self.open_button.pack(fill="x")
        self.label(capture, textvariable=self.whisper_status, fg=MUTED,
                   wraplength=210, justify="left").pack(anchor="w", pady=(8, 0))


        self.label(transcript, "Transcript", size=17, bold=True).pack(anchor="w")
        metadata = tk.Frame(transcript, bg=WHITE)
        metadata.pack(fill="x", pady=(3, 0))
        self.field(metadata, "Meeting title", self.title)
        self.field(metadata, "Meeting date", self.date)
        self.label(transcript, "Live draft", bold=True).pack(anchor="w", pady=(9, 3))
        self.draft_view = tk.Text(transcript, height=2, width=1, wrap="word", borderwidth=0,
                                  highlightthickness=0, bg=PALE, fg=INK, padx=9, pady=5,
                                  font=(FONT, 10))
        self.draft_view.pack(fill="x")
        self.show_draft(DRAFT_HINT)
        self.transcript = self.editor(transcript, editable=True)
        self.transcript.bind("<<Modified>>", self.transcript_changed)
        self.placeholder = self.label(self.transcript, "Record, open audio or type here.", bg="#FAFCFC", fg=MUTED)
        self.placeholder.place(x=12, y=11)
        self.placeholder.bind("<Button-1>", lambda event: self.transcript.focus_set())
        self.transcript.bind("<FocusIn>", lambda event: self.placeholder.place_forget())
        self.transcript.bind("<FocusOut>", lambda event: self.update_transcript_label())
        self.label(transcript, textvariable=self.transcript_label, fg=MUTED).pack(anchor="w")

        self.label(notes, "Meeting notes", size=17, bold=True).pack(anchor="w")
        self.label(notes, textvariable=self.summary_model, fg=MUTED).pack(anchor="w", pady=(4, 0))
        self.note_view = self.editor(notes)
        self.note_view.configure(height=3)
        self.note_view.tag_configure("heading", font=(FONT, 11, "bold"), foreground=TEAL, spacing1=10)
        self.note_view.tag_configure("hint", foreground=MUTED)
        self.render_notes()
        self.summarize_button = ttk.Button(notes, text="Generate notes", style="Primary.TButton",
                                           command=self.summarize)
        self.summarize_button.pack(fill="x", pady=(0, 8))
        self.map_button = ttk.Button(notes, text="Create mind map",
                                     command=lambda: self.summarize(show_map=True))
        self.map_button.pack(fill="x", pady=(0, 8))
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

    def show_draft(self, text):
        view = self.draft_view
        view.configure(state="normal")
        view.delete("1.0", "end")
        view.insert("1.0", text)
        view.configure(state="disabled")
        view.see("end-1c")

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
        busy = self.job is not None or (bool(self.audio) and not self.failed)
        warming = self.warm_model != self.whisper
        mode = self.mode.get()
        both = mode == SOURCES[2]
        if both and not self.second_device.winfo_manager():
            before = self.source_button if self.source_button.winfo_manager() else self.record_button
            self.second_device.pack(before=before, fill="x")
        elif not both:
            self.second_device.pack_forget()
        variable = self.loopback if mode == SOURCES[1] else self.mic
        if str(self.device_box.cget("textvariable")) != str(variable):
            self.device_box.configure(textvariable=variable)

        for control in (self.mode_box, self.device_box, self.second_box):
            control.configure(state="readonly" if recording or not busy else "disabled")
        if recording and not self.source_button.winfo_manager():
            self.source_button.pack(before=self.record_button, fill="x", pady=(8, 0))
        elif not recording:
            self.source_button.pack_forget()
            self.source_error.pack_forget()
        self.record_button.configure(
            text=("Stop recording" if recording else "Retry audio" if self.failed else
                  "Retry Whisper" if self.warm_error and not warming else "Start recording"),
            style="Danger.TButton" if recording else "Primary.TButton",
            state="normal" if recording or (
                not busy and (self.failed or (not warming and (self.devices or self.warm_error)))
            ) else "disabled",
        )
        self.open_button.configure(state="disabled" if recording or busy else "normal")
        self.refresh_button.configure(state="disabled" if recording or busy else "normal")
        self.new_button.configure(state="disabled" if recording or busy else "normal")
        transcript = self.current_transcript()
        has_text = bool(transcript)
        can_summarize = has_text and not recording and not busy
        self.summarize_button.configure(state="normal" if can_summarize else "disabled")
        self.map_button.configure(state="normal" if can_summarize else "disabled")
        for control in (self.txt_button, self.docx_button):
            control.configure(state="normal" if has_text else "disabled")

    def selected_devices(self):
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
        return devices

    def switch_audio_source(self):
        if not self.capture:
            return
        try:
            self.capture.switch_devices(self.selected_devices())
        except Exception as error:
            self.source_error.configure(text=f"Could not switch audio. {describe(error)[:140]}")
            self.source_error.pack(after=self.open_button, fill="x", pady=(5, 0))
            return
        self.source_error.pack_forget()
        self.capture_label.set(f"Recording · {self.mode.get()}")
        self.message("Audio source applied. Recording continues.")

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
        if self.warm_model != self.whisper or self.job:
            return
        if self.warm_error:
            self.start_whisper_warmup()
            return

        try:
            from meetnote.local_capture import LocalCapture

            capture = LocalCapture(self.selected_devices())
            capture.start()
        except Exception as error:
            self.message(f"Recording could not start. {describe(error)}", error=True)
            return
        self.capture = capture
        self.live = LiveSpeech()
        self.capture_settings = (LANGUAGES[self.language.get()], self.whisper)
        self.audio_warning = ""
        self.timer.set("00:00")
        self.capture_label.set(f"Recording · {self.mode.get()}")
        self.meter_status.configure(fg="#FFB7A5")
        self.show_draft("Listening for speech…")
        self.message("Recording. Draft captions update while you speak.")
        self.refresh_controls()

    def enqueue_recording(self):
        try:
            samples = self.capture.drain_samples()
            clip = self.live.add(samples) if len(samples) else None
        except Exception as error:
            self.audio_warning = f"Audio could not be read. {describe(error)}"
            clip = self.live.finish()
        if clip is not None:
            self.audio.append((clip, *self.capture_settings))
            self.show_draft("Finalizing phrase…")

    def stop_capture(self):
        self.capture.stop()
        self.enqueue_recording()
        tail = self.live.finish()
        if tail is not None:
            self.audio.append((tail, *self.capture_settings))
        if self.capture.last_error and not self.audio_warning:
            self.audio_warning = f"Audio device reported {self.capture.last_error}. Check for missing speech."
        self.capture = None
        self.live = None
        self.capture_label.set("Recording stopped")
        self.meter_status.configure(fg="#BCE1DB")
        self.show_draft("Finishing transcript…" if self.audio and not self.failed else DRAFT_HINT)
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

    def start_job(self, name, function, *args):
        def run():
            try:
                self.results.put((name, function(*args), ""))
            except Exception as error:
                self.results.put((name, None, describe(error)))

        self.job = name
        self.refresh_controls()
        Thread(target=run, daemon=True).start()

    def start_audio_job(self):
        if self.job or not self.audio or self.failed:
            return
        source, language, model = self.audio[0]
        if isinstance(source, Path):
            self.message(f"Transcribing {source.name}. This can take a moment.")
        elif not self.capture:
            self.message("Finishing the recorded audio…")
        self.start_job("audio", recognize, source, language, model)

    def start_whisper_warmup(self):
        self.warm_model = self.whisper
        self.warm_error = ""
        self.whisper_status.set(f"Loading Whisper ({self.whisper})…")
        self.start_job("warmup", warm_whisper, self.whisper)

    def tick(self):
        if self.capture:
            elapsed = int(self.capture.elapsed)
            minutes, seconds = divmod(elapsed, 60)
            self.timer.set(f"{minutes:02d}:{seconds:02d}")
            if self.capture.buffered_seconds() >= LIVE_POLL_SECONDS:
                self.enqueue_recording()

        try:
            name, value, error = self.results.get_nowait()
        except Empty:
            pass
        else:
            self.job = None
            if name == "audio":
                self.audio_result(value, error)
            elif name in ("notes", "map"):
                self.notes_result(value, error, show_map=name == "map")
            elif name == "draft":
                if value and self.live and self.draft_revision == self.live.revision:
                    self.show_draft(value)
            elif name == "warmup":
                if error:
                    self.warm_error = error
                    self.whisper_status.set(f"Whisper ({self.warm_model}) could not load")
                    if self.warm_model == self.whisper:
                        self.message(f"Whisper could not load. {error}", error=True)
                else:
                    self.whisper_status.set(f"Whisper ready ({self.warm_model})")
            self.refresh_controls()
        if not self.job:
            self.start_audio_job()
            if not self.job:
                if self.live:
                    draft = self.live.draft()
                    if draft is not None:
                        self.draft_revision = self.live.revision
                        self.start_job("draft", recognize_draft, draft, *self.capture_settings)
                elif self.warm_model != self.whisper:
                    self.start_whisper_warmup()
        self.root.after(100, self.tick)

    def audio_result(self, value, error):
        if error:
            self.failed = True
            if self.capture:
                self.stop_capture()
            self.message(f"Transcription failed. {error} Use Retry audio or open another file.", error=True)
            return
        source, _, _ = self.audio.popleft()
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
            return
        if self.capture:
            self.show_draft("Listening for speech…")
        else:
            self.show_draft(DRAFT_HINT)
        if self.audio_warning:
            self.message(self.audio_warning, error=True)
        elif self.capture:
            self.message("Recording. Transcript updated." if sentence else "Recording. No clear speech in the last section.")
        else:
            has_speech = sentence or (isinstance(source, LiveClip) and self.current_transcript())
            self.message("Transcription complete." if has_speech else "No clear speech in this audio section.")

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
        if self.map_preview and self.map_preview.winfo_exists():
            if self.map_preview.source != self.current_transcript():
                self.map_preview.invalidate()
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
        model = tk.StringVar(value=self.whisper)
        language = tk.StringVar(value=self.language.get())
        self.label(window, "AI settings", size=17, bold=True).pack(anchor="w")
        selected_summary_model = tk.StringVar(value=self.summary_model.get())
        try:
            detected = installed_models()
            hint = "Select a model installed in Ollama." if detected else "Install a model in Ollama and reopen Settings."
        except RuntimeError as error:
            detected = ()
            hint = str(error)
        choices = tuple(dict.fromkeys((selected_summary_model.get(), *detected)))
        self.field(window, "Summary model", selected_summary_model, choices)
        self.label(window, hint, fg=MUTED, wraplength=315, justify="left").pack(anchor="w", pady=(4, 0))
        self.field(window, "Speech language", language, tuple(LANGUAGES))
        self.field(window, "Whisper model", model, MODELS)
        self.label(window, "Tiny is fastest. Larger models take longer on a CPU.", fg=MUTED).pack(anchor="w", pady=(4, 0))
        self.label(window, "For laptop audio, enable Stereo Mix or use a virtual cable.",
                   fg=MUTED, wraplength=315, justify="left").pack(anchor="w", pady=(5, 3))

        def save():
            self.summary_model.set(selected_summary_model.get())
            self.whisper = model.get()
            self.language.set(language.get())
            window.destroy()
            self.refresh_controls()
            if not self.job and not self.capture and not self.failed:
                self.message("Settings saved for this session.")

        actions = tk.Frame(window, bg=WHITE)
        actions.pack(fill="x", pady=(13, 0))
        ttk.Button(actions, text="Save settings", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(actions, text="Cancel", command=window.destroy).pack(side="right", padx=(0, 8))
        window.bind("<Escape>", lambda event: window.destroy())
        window.focus_set()

    def summarize(self, *, show_map=False):
        source = self.current_transcript()
        if not source or self.capture or self.job:
            return
        if show_map and self.map_source == source and self.mind_map.get("branches"):
            self.open_mind_map()
            return
        if len(source) > MAX_TRANSCRIPT_CHARS:
            self.message("This transcript exceeds 60,000 characters. Summarize it in smaller sections.", error=True)
            return
        self.job_source = source
        model = self.summary_model.get()
        purpose = "a mind map" if show_map else "notes"
        self.message(f"Generating {purpose} locally with {model}. Longer transcripts may take a few minutes.")
        self.start_job("map" if show_map else "notes", create_mind_map if show_map else create_notes,
                       source, model)

    def notes_result(self, value, error, *, show_map=False):
        if error:
            if self.notes is None and not show_map:
                self.render_notes("Notes unavailable. See the status below for the next step.")
            self.message(f"{error} Your transcript is available.", error=True)
        elif self.current_transcript() != self.job_source:
            purpose = "the mind map" if show_map else "notes"
            self.message(f"The transcript changed during generation. Try creating {purpose} again.", error=True)
        elif show_map:
            self.mind_map = value
            self.map_source = self.job_source
            self.open_mind_map()
        else:
            self.notes = value
            self.notes_source = self.job_source
            self.render_notes()
            model = value.get("model") or self.summary_model.get()
            self.message(f"Meeting notes ready from {model}. Review decisions and deadlines before sharing.")
        self.job_source = None

    def open_mind_map(self):
        from meetnote.mind_map import render_mind_map

        source = self.current_transcript()
        topic = self.mind_map.get("topic") or "Meeting Summary"
        branches = self.mind_map.get("branches")
        if not branches:
            self.message("No distinct points were found for a mind map. Add more detail to the transcript.", error=True)
            return
        try:
            image = render_mind_map(topic, branches)
        except (OSError, ValueError) as error:
            self.message(f"Could not draw the mind map. {describe(error)}", error=True)
            return
        if self.map_preview and self.map_preview.winfo_exists():
            self.map_preview.destroy()
        self.map_preview = MindMapPreview(self.root, image, topic, source, self.save_mind_map)
        self.message("Mind map ready. Select Save PNG to export it.")

    def save_mind_map(self):
        preview = self.map_preview
        if preview.source != self.current_transcript():
            preview.invalidate()
            return
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", preview.topic).strip(" .")[:80] or "Meeting"
        destination = filedialog.asksaveasfilename(
            parent=preview, title="Save mind map", initialfile=f"{filename} mind map.png",
            defaultextension=".png", filetypes=[("PNG image", "*.png")],
        )
        if destination:
            try:
                preview.image.save(destination, format="PNG")
            except OSError as error:
                preview.status.set(f"Could not save PNG. {describe(error)}")
            else:
                preview.status.set("Mind map saved.")
                self.message(f"Saved {Path(destination).name}.")

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
        self.mind_map = {}
        self.map_source = ""
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
        if (self.capture or self.job in ("audio", "notes", "map") or self.audio or self.current_transcript()) and not messagebox.askyesno(
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
