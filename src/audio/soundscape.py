"""
Zero-dependency Retro Soundscape & Procedural Audio Engine for Astra 3D.
Generates pure standard library WAV synthesizers and non-blocking sound playback.
Also hosts the in-game Radio Tuner (stations, tracklists, EQ visualizer)
ported from the M2 engine branch's sound system.
Author: Valerie Sterling ⚡ (3D Raycaster & Rasterization Specialist)
Status: M2 INTEGRATION — sole production audio engine; wired into the main
Game loop (src/game.py) for effects and radio playback.
"""

import os
import sys
import wave
import struct
import math
import time
import tempfile
import threading
import subprocess
from typing import Dict, List, Optional


class RadioStation:
    """One tunable radio channel with a rotating tracklist."""

    def __init__(self, freq: str, name: str, genre: str, tracklist: List[str]):
        self.freq = freq
        self.name = name
        self.genre = genre
        self.tracklist = tracklist
        self.current_track_idx = 0
        self.track_timer = 0.0
        self.track_duration = 25.0

    def update(self, dt: float):
        self.track_timer += dt
        if self.track_timer >= self.track_duration:
            self.track_timer = 0.0
            self.current_track_idx = (self.current_track_idx + 1) % len(self.tracklist)

    def get_now_playing(self) -> str:
        return self.tracklist[self.current_track_idx]


class RadioTuner:
    """Cycles radio stations and animates the ASCII equalizer readout."""

    def __init__(self):
        self.current_station_idx = 0
        self.eq_anim_timer = 0.0

        self.stations: List[RadioStation] = [
            RadioStation(
                "98.4 FM",
                "ASTRA RETROWAVE",
                "Synthwave / Cyberpunk",
                [
                    "Midnight Overdrive — Neon Highway",
                    "Laser Grid Horizon — CyberVance",
                    "Metropolis Dreams — 80s Skyline",
                    "Tokyo Drift 2099 — Synth Core"
                ]
            ),
            RadioStation(
                "104.2 FM",
                "CYBERPUNK BEATS",
                "Dark Electro / Industrial",
                [
                    "Neural Uplink — Glitch Mob",
                    "Subway Bass Pulse — District 4",
                    "Neon Shadow — Hacker Groove",
                    "Matrix Collision — Overclocked"
                ]
            ),
            RadioStation(
                "88.9 FM",
                "METRO JAZZ NOCTURNE",
                "Lofi / Smooth City Jazz",
                [
                    "Raindrops on Asphalt — Blue Note",
                    "Late Night Diner — Coffee & Sax",
                    "Streetlamp Solitude — Midnight Trio",
                    "Brownstone Balcony — Acoustic Vibes"
                ]
            ),
            RadioStation(
                "92.5 FM",
                "METROPOLIS NEWS & POLICE RADAR",
                "Live Radio Broadcast",
                [
                    "Traffic Alert: 2nd Avenue Clear",
                    "Weather Report: Night Rain Expected",
                    "City Mayor: Central Plaza Renovation",
                    "Scanner: Patrol Active in Downtown"
                ]
            )
        ]

    def next_station(self) -> RadioStation:
        self.current_station_idx = (self.current_station_idx + 1) % len(self.stations)
        return self.stations[self.current_station_idx]

    def get_current_station(self) -> RadioStation:
        return self.stations[self.current_station_idx]

    def update(self, dt: float):
        self.eq_anim_timer += dt * 6.0
        for station in self.stations:
            station.update(dt)

    def get_eq_visualizer(self, bars: int = 6) -> str:
        """Returns animated ASCII audio equalizer bars e.g. ' ▃▅█▅▃'."""
        eq_chars = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
        out = []
        for i in range(bars):
            val = (math.sin(self.eq_anim_timer + i * 1.3) + 1.0) / 2.0
            idx = int(val * (len(eq_chars) - 1))
            out.append(eq_chars[idx])
        return "".join(out)


class SoundscapeManager:
    """Zero-dependency asynchronous sound manager using standard library WAV synthesis & system audio.

    EXPERIMENTAL for v1.0 (T-39): audio is explicitly not a v1.0 quality target.
    Ships mute-default; synthesis runs on a background thread and the system
    player probe is cached once, so neither startup nor the [V] toggle can
    hitch a render frame.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # Tempdir is created lazily on first real synthesis need so a
        # mute-default session never touches the filesystem at construction
        self.temp_dir: Optional[str] = None
        self.sound_cache: Dict[str, str] = {}
        self.is_muted = not enabled
        self._lock = threading.Lock()
        self.radio = RadioTuner()
        self._synth_thread: Optional[threading.Thread] = None
        self._linux_player: Optional[str] = None

        # Pre-synthesize retro 8-bit sound effects — off the calling thread so
        # startup with --audio cannot stall the first frame (T-39)
        if self.enabled:
            self.start_synthesis()

    def _ensure_tempdir(self) -> str:
        if self.temp_dir is None:
            self.temp_dir = tempfile.mkdtemp(prefix="astra_audio_")
        return self.temp_dir

    def play_beep(self):
        """Emits a short acoustic terminal bell pulse (UI confirmation)."""
        if self.is_muted:
            return
        try:
            sys.stdout.write('\a')
            sys.stdout.flush()
        except Exception:
            pass

    def next_station(self) -> RadioStation:
        """Tunes to the next radio station and returns it."""
        return self.radio.next_station()

    def get_current_station(self) -> RadioStation:
        return self.radio.get_current_station()

    def get_eq_visualizer(self, bars: int = 6) -> str:
        return self.radio.get_eq_visualizer(bars)

    def update_radio(self, dt: float):
        self.radio.update(dt)

    def _generate_wav(self, filename: str, duration: float, sample_rate: int, wave_gen_fn) -> str:
        filepath = os.path.join(self._ensure_tempdir(), filename)
        num_samples = int(duration * sample_rate)
        
        with wave.open(filepath, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)

            raw_data = bytearray()
            for i in range(num_samples):
                t = float(i) / sample_rate
                sample_val = wave_gen_fn(t, duration)
                # Clamp to 16-bit signed integer [-32767, 32767]
                clamped = max(-32767, min(32767, int(sample_val * 32767.0)))
                raw_data.extend(struct.pack('<h', clamped))

            wav_file.writeframes(raw_data)
        return filepath

    def start_synthesis(self):
        """Kicks off sound-bank synthesis on a daemon thread (no-op if one is
        already running), so the calling thread never hitches a frame (T-39)."""
        with self._lock:
            if self._synth_thread is not None and self._synth_thread.is_alive():
                return
            self._synth_thread = threading.Thread(
                target=self._synthesize_sound_bank, daemon=True)
            self._synth_thread.start()

    def _synthesize_sound_bank(self):
        sample_rate = 22050
        try:
            # 1. Car Horn
            def horn_fn(t, dur):
                env = 1.0 if t < dur - 0.05 else (dur - t) / 0.05
                tone1 = math.sin(2.0 * math.pi * 440.0 * t)
                tone2 = math.sin(2.0 * math.pi * 554.37 * t)  # C# note for dual-tone horn
                return (tone1 * 0.5 + tone2 * 0.5) * env * 0.45

            self.sound_cache["horn"] = self._generate_wav("horn.wav", 0.35, sample_rate, horn_fn)

            # 2. Thunderclap Rumble
            def thunder_fn(t, dur):
                env = math.exp(-t * 3.0)
                # Low frequency noise modulation
                noise = (math.sin(t * 1234.5) * 43758.5453) % 1.0 * 2.0 - 1.0
                rumble = math.sin(2.0 * math.pi * 65.0 * t) * 0.6 + math.sin(2.0 * math.pi * 45.0 * t) * 0.4
                return (rumble * 0.6 + noise * 0.4) * env * 0.7

            self.sound_cache["thunder"] = self._generate_wav("thunder.wav", 1.2, sample_rate, thunder_fn)

            # 3. Enter/Exit Vehicle Chime
            def chime_fn(t, dur):
                freq = 523.25 if t < 0.1 else 659.25  # C5 -> E5
                env = math.exp(-(t % 0.1) * 20.0)
                return math.sin(2.0 * math.pi * freq * t) * env * 0.4

            self.sound_cache["chime"] = self._generate_wav("chime.wav", 0.25, sample_rate, chime_fn)

            # 4. Engine Rev
            def rev_fn(t, dur):
                freq = 80.0 + (t / dur) * 140.0
                sawtooth = (t * freq) % 1.0 * 2.0 - 1.0
                return sawtooth * 0.35

            self.sound_cache["rev"] = self._generate_wav("rev.wav", 0.4, sample_rate, rev_fn)

            # 5. Collision Thud
            def thud_fn(t, dur):
                env = math.exp(-t * 25.0)
                tone = math.sin(2.0 * math.pi * 90.0 * t)
                return tone * env * 0.6

            self.sound_cache["thud"] = self._generate_wav("thud.wav", 0.2, sample_rate, thud_fn)

        except Exception:
            # If audio synthesis fails on any environment, fail gracefully
            pass

    def play(self, sound_name: str):
        """Asynchronously plays sound without blocking engine frame rate."""
        if self.is_muted or sound_name not in self.sound_cache:
            return

        sound_path = self.sound_cache[sound_name]
        threading.Thread(target=self._play_subprocess, args=(sound_path,), daemon=True).start()

    def _probe_linux_player(self) -> str:
        """Resolves the Linux CLI player exactly once and caches the result,
        so playback never pays a `which` subprocess per sound (T-39)."""
        if self._linux_player is None:
            try:
                has_pulse = subprocess.run(
                    ["which", "paplay"], stdout=subprocess.DEVNULL
                ).returncode == 0
            except Exception:
                has_pulse = False
            self._linux_player = "paplay" if has_pulse else "aplay"
        return self._linux_player

    def _play_subprocess(self, path: str):
        try:
            if sys.platform == "darwin":
                # macOS native ultra-low latency CLI player
                subprocess.run(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
            elif sys.platform.startswith("linux"):
                # Linux aplay / paplay — player resolved once, then cached
                subprocess.run([self._probe_linux_player(), path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        self.is_muted = not self.is_muted
        if not self.is_muted and not self.sound_cache:
            # First audible request without a synthesized bank: build it in
            # the background so pressing [V] cannot hitch a frame (T-39)
            self.start_synthesis()
        return not self.is_muted

    def join_synthesis(self, timeout: float = 5.0):
        """Blocks until any in-flight sound-bank synthesis completes."""
        synth = self._synth_thread
        if synth is not None and synth.is_alive():
            synth.join(timeout=timeout)

    def cleanup(self):
        # Wait out any in-flight synthesis so we never delete half-written
        # WAVs or the tempdir out from under the background thread
        self.join_synthesis()
        try:
            for f in self.sound_cache.values():
                if os.path.exists(f):
                    os.remove(f)
            self.sound_cache.clear()
            if self.temp_dir and os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
            self.temp_dir = None
        except Exception:
            pass
