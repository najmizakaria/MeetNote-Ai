# MeetNote AI — interface review and rebuild brief

The audit refers to the previously shared MeetMind AI screenshot, **not** to an invented Figma file. Labels listed below came from the visible screenshot. No original CSS class names were supplied, so severity is based on visible layout decisions rather than guessed selectors.

## A. Slop inventory

| Severity | Evidence | Decision |
|---|---|---|
| High | Large unused white space between top caption/privacy banner and the real work area | Remove dead air; place title and recording controls within the first 280 px of content |
| High | Repeated wide gray rectangular recording container with several same-weight tiny controls | Give audio source a single primary horizontal control group and one obvious action |
| High | “1 · Live audio recording”, then distant “2 · Transcript”; product reads like a lab worksheet | Rename stages to Input source / Transcript & meeting notes / Deliverables; compact mono eyebrows |
| Medium | Persistent blue privacy banner across page width takes more visual weight than user task | Move privacy to a concise contextual sentence and an expandable policy control |
| Medium | Left sidebar occupied by a tall sequence of equal-weight form fields and a key box | Move advanced settings into one bottom expander; meeting title/date remain top-of-page |
| Medium | Four sprawling metrics (“Audio segments processed”, “Transcript sections”, “Detected language”, “Status”) look like debugging instruments | Only surface relevant transcription info below the transcript |
| Medium | Neutral gray on gray status field and chunky empty borders weaken information hierarchy | Introduce decisive ink, subdued border, and one explicit status rail |

No purple gradient, warm cream premium background, or bouncing hover effects were visible; those should **not** be fabricated as findings.

## B. What to keep

- A choice of recording sources.
- Live transcription and meeting-note outputs displayed together.
- Meeting name and date.
- A privacy/consent reminder.
- Visible indication of detected language and transcript readiness.

## C. Unslop direction

**Aesthetic: Calm editorial control room.** The one signature element is a narrow *signal/status rail* with a left colored stripe that changes from teal (ready) to rust red (recording). Everything else should be quiet.

| Role | Color |
|---|---|
| Background | `#F2F6F7` |
| Surface | `#FFFFFF` |
| Ink | `#17333B` |
| Muted text | `#516970` |
| Accent/ready | `#176B68` |
| Recording | `#B94733` |
| Border | `#CAD9DC` |

**Type pairing:** Outfit (display), IBM Plex Sans (body), DM Mono (small status labels). Do not use Inter, Roboto, Arial, or `system-ui` as the brand voice. Use semantic fallback sans-serif for unavailable external web fonts; accessibility takes precedence over type styling.

Do **not** add AI sparkle icons, glassmorphism, gradient heroes, shadows on every box, pulse animations, identical card grids or fake statistical charts.

## D. Rewrite priority

1. **Must fix:** Clarify local versus browser audio support; expose one obvious capture control; show meaningful errors without clearing the transcript; do not advertise browser microphone as live captions.
2. **High impact:** Condense header, give transcript and meeting notes a stable two-column layout, show the local summary model in Settings, provide clear export actions.
3. **Craft:** Use 8-px controls and 12-px surfaces, 1-px functional borders, consistent type scale and responsive columns; only animate if conveying actual recording state.

## E. Pixel-specific desktop rewrite brief

At a 1440×900 viewport: outer centered content **1220 px maximum** with **32 px** top space. Brand row **48 px** height with logo on the left and prototype metadata on the right; **1 px** divider. Heading around **49 px** Outfit, under it one short ~16-px description. Meeting title/date row width ratio **2.2:1**, gap ~**24 px**. Recorder immediately below a 12-px source label, with selected audio mode, one clear primary button and a slim **4 px** status rail. Transcript column ~**53%** and notes ~**47%**, **28 px** gap; transcript height around **285 px**. Exports placed below results as three equal-width controls. Model and privacy settings live in a bottom expander. On mobile (<768 px), columns must stack and inputs fill width without horizontal scrolling.
