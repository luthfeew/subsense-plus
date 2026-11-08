import re
from typing import List, Dict, Any, Tuple, Optional

def parse_time_to_seconds(time_str: str) -> float:
    """
    Parses timestamp string like '00:01:23,456' or '01:23.456' into seconds (float).
    """
    time_str = time_str.strip().replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60 + float(s)
    return float(time_str)

def format_seconds_to_srt_time(seconds: float) -> str:
    """
    Formats seconds (float) into SRT timestamp 'HH:MM:SS,mmm'.
    """
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms -= 1000
    if s >= 60:
        m += 1
        s -= 60
    if m >= 60:
        h += 1
        m -= 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def format_seconds_to_vtt_time(seconds: float) -> str:
    """
    Formats seconds (float) into WebVTT timestamp 'HH:MM:SS.mmm'.
    """
    srt_time = format_seconds_to_srt_time(seconds)
    return srt_time.replace(',', '.')

class SubtitleCue:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text.strip()

    def __repr__(self):
        return f"<Cue {self.start:.2f}->{self.end:.2f}: {self.text[:20]}>"

def parse_srt_or_vtt(content: str) -> Tuple[List[SubtitleCue], bool]:
    """
    Parses SRT or WebVTT content into a list of SubtitleCue objects.
    Returns (cues, is_vtt).
    """
    is_vtt = "WEBVTT" in content[:100]
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Regex to find timestamp lines: e.g. 00:01:20,000 --> 00:01:23,000
    cue_pattern = re.compile(
        r'(?:(\d+)\n)?'  # Optional sequence number
        r'(\d{1,2}:\d{2}(?::\d{2})?[.,]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}(?::\d{2})?[.,]\d{2,3})[^\n]*\n'
        r'([\s\S]*?)(?=\n\s*(?:\d+\n)?\d{1,2}:\d{2}(?::\d{2})?[.,]\d{2,3}\s*-->|\Z)',
        re.MULTILINE
    )

    cues: List[SubtitleCue] = []
    for match in cue_pattern.finditer(content):
        _, start_str, end_str, text = match.groups()
        start_sec = parse_time_to_seconds(start_str)
        end_sec = parse_time_to_seconds(end_str)
        cleaned_text = text.strip()
        if cleaned_text and end_sec > start_sec:
            cues.append(SubtitleCue(start_sec, end_sec, cleaned_text))

    cues.sort(key=lambda c: c.start)
    return cues, is_vtt

def serialize_cues(cues: List[SubtitleCue], is_vtt: bool = False) -> str:
    """
    Converts list of SubtitleCue back to SRT or WebVTT string.
    """
    cues.sort(key=lambda c: c.start)
    output = []
    
    if is_vtt:
        output.append("WEBVTT\n\n")

    for idx, cue in enumerate(cues, 1):
        if is_vtt:
            time_line = f"{format_seconds_to_vtt_time(cue.start)} --> {format_seconds_to_vtt_time(cue.end)}"
            output.append(f"{time_line}\n{cue.text}\n\n")
        else:
            time_line = f"{format_seconds_to_srt_time(cue.start)} --> {format_seconds_to_srt_time(cue.end)}"
            output.append(f"{idx}\n{time_line}\n{cue.text}\n\n")

    return "".join(output).strip() + "\n"

def inject_status_badge(
    cues: List[SubtitleCue],
    status_text: str,
    start_time: float = 15.0,
    duration: float = 4.0
):
    """
    Injects a status badge at start_time (default 15.0s, duration 4.0s)
    without overwriting any existing subtitle dialogue.
    """
    if not status_text:
        return

    end_time = start_time + duration
    overlapping = [c for c in cues if c.start < end_time and c.end > start_time]

    if not overlapping:
        cues.append(SubtitleCue(start_time, end_time, status_text))
    else:
        for c in overlapping:
            if status_text not in c.text:
                c.text = f"{status_text}\n{c.text}"
        first_cue = min(overlapping, key=lambda c: c.start)
        if first_cue.start - start_time > 0.8:
            cues.append(SubtitleCue(start_time, first_cue.start, status_text))
        last_cue = max(overlapping, key=lambda c: c.end)
        if end_time - last_cue.end > 0.8:
            cues.append(SubtitleCue(last_cue.end, end_time, status_text))

def inject_jumpscares(
    subtitle_content: str,
    jumpscares: List[Dict[str, Any]],
    lead_time_seconds: float = 5.0,
    alert_color: str = "#FFD700",  # Clean subtitle yellow
    status_text: Optional[str] = None,
    status_start_time: float = 15.0,
    status_duration: float = 4.0
) -> str:
    """
    Injects jumpscare warning tags and optional status notice into subtitle text without losing existing dialogue.
    - jumpscares: list of jumpscare dictionaries with 'time' and 'intensity'.
    - lead_time_seconds: how many seconds before jumpscare the warning appears (default 5.0).
    - alert_color: subtitle text color (default clean yellow #FFD700).
    - status_text: optional status badge to display at status_start_time (default 15.0s).
    """
    if not subtitle_content.strip():
        return subtitle_content

    if not jumpscares and not status_text:
        return subtitle_content

    cues, is_vtt = parse_srt_or_vtt(subtitle_content)

    # 1. Inject status notice at specified second (default 15s)
    if status_text:
        inject_status_badge(
            cues=cues,
            status_text=status_text,
            start_time=status_start_time,
            duration=status_duration
        )

    # 2. Inject jumpscare warning cues
    for js in jumpscares:
        js_time = float(js.get("time", 0))
        if js_time <= 0:
            continue
            
        alert_start = max(0.0, js_time - lead_time_seconds)
        alert_end = js_time
        warning_msg = f'<font color="{alert_color}"><b>⚠️ Jumpscare ⚠️</b></font>'

        overlapping_cues = [c for c in cues if c.start < alert_end and c.end > alert_start]

        if not overlapping_cues:
            cues.append(SubtitleCue(alert_start, alert_end, warning_msg))
        else:
            for cue in overlapping_cues:
                if warning_msg not in cue.text:
                    cue.text = f"{warning_msg}\n{cue.text}"
            
            # Fill gaps around existing dialogue exceeding threshold
            first_cue = min(overlapping_cues, key=lambda c: c.start)
            if first_cue.start - alert_start > 0.8:
                cues.append(SubtitleCue(alert_start, first_cue.start, warning_msg))
                
            last_cue = max(overlapping_cues, key=lambda c: c.end)
            if alert_end - last_cue.end > 0.8:
                cues.append(SubtitleCue(last_cue.end, alert_end, warning_msg))

    return serialize_cues(cues, is_vtt=is_vtt)
