import json
import math
import random
import struct
import sys
import time
import wave
from pathlib import Path
from typing import Dict, List, Optional

import pygame
import pygame.midi
from PySide6.QtCore import QObject, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

APP_DIR = Path(__file__).resolve().parent
MAPPING_FILE = APP_DIR / "mapping.json"
HOTCUES_FILE = APP_DIR / "hotcues.json"
LIBRARY_FILE = APP_DIR / "library.json"
SAMPLES_DIR = APP_DIR / "samples"

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

SUPPORTED_FILTER = (
    "Medios (*.mp4 *.mov *.mkv *.avi *.webm *.mp3 *.wav *.ogg *.flac *.m4a *.aac);;"
    "Video (*.mp4 *.mov *.mkv *.avi *.webm);;"
    "Audio (*.mp3 *.wav *.ogg *.flac *.m4a *.aac);;"
    "Todos los archivos (*.*)"
)

ACTIONS = [
    "deck1_play", "deck1_cue", "deck1_stop", "deck1_sync", "deck1_volume", "deck1_seek",
    "deck1_hotcue_1", "deck1_hotcue_2", "deck1_hotcue_3", "deck1_hotcue_4",
    "deck2_play", "deck2_cue", "deck2_stop", "deck2_sync", "deck2_volume", "deck2_seek",
    "deck2_hotcue_1", "deck2_hotcue_2", "deck2_hotcue_3", "deck2_hotcue_4",
    "crossfader", "master_volume",
    "sample_air_horn", "sample_siren", "sample_explosion", "sample_applause",
    "sample_laugh", "sample_drop", "sample_kick", "sample_fx", "sample_stop_all",
]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ms_to_time(ms: int) -> str:
    if ms <= 0:
        return "00:00"
    seconds = int(ms // 1000)
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def media_type_for(path: str) -> str:
    return "Video" if Path(path).suffix.lower() in VIDEO_EXTENSIONS else "Audio"


def safe_read_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def safe_write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_default_samples():
    """Crea samples WAV pequeños para que los pads del sampler funcionen sin archivos externos."""
    SAMPLES_DIR.mkdir(exist_ok=True)
    sample_defs = {
        "AIR HORN": "air_horn.wav",
        "SIREN": "siren.wav",
        "EXPLOSION": "explosion.wav",
        "APPLAUSE": "applause.wav",
        "LAUGH": "laugh.wav",
        "DROP": "drop.wav",
        "KICK": "kick.wav",
        "FX": "fx.wav",
    }
    for label, filename in sample_defs.items():
        path = SAMPLES_DIR / filename
        if not path.exists():
            write_sample_wav(path, label)
    return {label: str(SAMPLES_DIR / filename) for label, filename in sample_defs.items()}


def write_sample_wav(path: Path, label: str, sample_rate: int = 44100):
    duration = {
        "AIR HORN": 0.85,
        "SIREN": 1.15,
        "EXPLOSION": 0.95,
        "APPLAUSE": 1.25,
        "LAUGH": 0.9,
        "DROP": 0.8,
        "KICK": 0.45,
        "FX": 0.75,
    }.get(label, 0.8)
    total = int(sample_rate * duration)
    rng = random.Random(hash(label) & 0xFFFFFFFF)
    frames = []
    for i in range(total):
        t = i / sample_rate
        x = 0.0
        if label == "AIR HORN":
            freq = 410 + 55 * math.sin(t * 18)
            env = min(1.0, i / 5000) * max(0.0, 1.0 - t / duration * 0.35)
            x = math.sin(2 * math.pi * freq * t) * env
        elif label == "SIREN":
            freq = 520 + 300 * math.sin(2 * math.pi * 2.2 * t)
            x = math.sin(2 * math.pi * freq * t) * 0.75
        elif label == "EXPLOSION":
            env = max(0.0, 1.0 - t / duration) ** 1.8
            x = (rng.uniform(-1, 1) * 0.9 + math.sin(2 * math.pi * 65 * t) * 0.45) * env
        elif label == "APPLAUSE":
            burst = 1.0 if (i // 900) % 3 == 0 else 0.45
            env = max(0.0, 1.0 - t / duration * 0.2)
            x = rng.uniform(-1, 1) * burst * env * 0.75
        elif label == "LAUGH":
            freq = 300 + 90 * math.sin(2 * math.pi * 6 * t)
            gate = 1.0 if math.sin(2 * math.pi * 5 * t) > -0.2 else 0.15
            x = math.sin(2 * math.pi * freq * t) * gate * max(0.0, 1 - t / duration * 0.25)
        elif label == "DROP":
            freq = max(45, 230 - 190 * (t / duration))
            x = math.sin(2 * math.pi * freq * t) * max(0.0, 1 - t / duration * 0.1)
        elif label == "KICK":
            freq = max(48, 150 - 110 * (t / duration))
            env = math.exp(-9 * t)
            x = math.sin(2 * math.pi * freq * t) * env * 1.2
        else:  # FX
            freq = 240 + 780 * (t / duration)
            x = math.sin(2 * math.pi * freq * t) * max(0.0, 1 - t / duration)
        x = max(-1.0, min(1.0, x * 0.55))
        frames.append(struct.pack("<h", int(x * 32767)))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(frames))


class JogDisplay(QWidget):
    """Indicador visual tipo jog wheel. No es una waveform real."""

    def __init__(self, label: str, compact: bool = False):
        super().__init__()
        self.label = label
        self.compact = compact
        self.angle = 0.0
        self.active = False
        self.accent = QColor("#38bdf8")
        size = 96 if compact else 145
        self.setMinimumSize(size, size)
        self.setMaximumHeight(120 if compact else 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_active(self, active: bool):
        self.active = active
        self.update()

    def spin(self, bpm: int = 0):
        if self.active:
            speed = 5.0 if bpm <= 0 else max(2.0, min(10.0, bpm / 24))
            self.angle = (self.angle + speed) % 360
            self.update()

    def paintEvent(self, event):
        width = self.width()
        height = self.height()
        side = min(width, height) - 18
        cx = width / 2
        cy = height / 2
        radius = side / 2

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(cx - radius, cy - radius, side, side)
        painter.setPen(QPen(QColor("#1e293b"), 7))
        painter.setBrush(QColor("#020617"))
        painter.drawEllipse(rect)

        # anillo exterior
        painter.setPen(QPen(QColor("#334155"), 3))
        painter.drawEllipse(rect.adjusted(12, 12, -12, -12))

        color = self.accent if self.active else QColor("#64748b")
        painter.setPen(QPen(color, 6))
        painter.drawArc(rect.adjusted(8, 8, -8, -8), int((90 - self.angle) * 16), int(90 * 16))

        # líneas decorativas del jog
        painter.setPen(QPen(QColor("#475569"), 1))
        for i in range(0, 360, 30):
            rad = math.radians(i + self.angle)
            x1 = cx + math.cos(rad) * (radius * 0.72)
            y1 = cy + math.sin(rad) * (radius * 0.72)
            x2 = cx + math.cos(rad) * (radius * 0.88)
            y2 = cy + math.sin(rad) * (radius * 0.88)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        painter.setPen(QPen(QColor("#e5e7eb"), 3))
        rad = math.radians(self.angle)
        x2 = cx + math.cos(rad) * (radius * 0.52)
        y2 = cy + math.sin(rad) * (radius * 0.52)
        painter.drawLine(int(cx), int(cy), int(x2), int(y2))

        painter.setBrush(QColor("#f8fafc"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - 6, cy - 6, 12, 12))

        painter.setPen(QColor("#cbd5e1"))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.label)


class WaveformDisplay(QWidget):
    """Waveform visual sintética para dar una vista DJ. No analiza el audio real."""

    def __init__(self, color: str = "#00b7d8", compact: bool = False, label: str = ""):
        super().__init__()
        self.color = QColor(color)
        self.label = label
        self.position_ratio = 0.0
        self.playing = False
        self.bars = self._make_bars(label or "empty")
        self.setMinimumHeight(34 if compact else 46)
        self.setMaximumHeight(72 if compact else 90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _make_bars(self, seed_text: str):
        seed = abs(hash(seed_text)) % 100000
        values = []
        for i in range(180):
            x = (seed * (i + 3) + i * i * 17) % 97
            smooth = (math.sin(i / 5.0 + seed / 9000.0) + 1) / 2
            values.append(0.18 + 0.78 * ((x / 96.0) * 0.55 + smooth * 0.45))
        return values

    def load_media(self, path: Optional[str]):
        self.bars = self._make_bars(path or self.label or "empty")
        self.position_ratio = 0.0
        self.update()

    def set_position(self, ratio: float):
        self.position_ratio = clamp(ratio)
        self.update()

    def set_playing(self, playing: bool):
        self.playing = playing
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(QColor("#05070b"))
        painter.setPen(QPen(QColor("#1f2937"), 1))
        painter.drawRoundedRect(rect, 4, 4)

        mid = rect.center().y()
        w = max(1, rect.width())
        h = rect.height()
        count = len(self.bars)
        step = max(1.0, w / count)
        color = QColor(self.color)
        color.setAlpha(210 if self.playing else 150)
        painter.setPen(QPen(color, max(1, int(step * 0.55))))
        for i, value in enumerate(self.bars):
            x = rect.left() + i * step
            amp = value * h * 0.42
            painter.drawLine(int(x), int(mid - amp), int(x), int(mid + amp))

        # Secciones tipo beatgrid
        painter.setPen(QPen(QColor("#334155"), 1))
        for i in range(0, 16):
            x = rect.left() + int(w * i / 16)
            painter.drawLine(x, rect.top(), x, rect.bottom())

        # Parte ya reproducida
        pos_x = rect.left() + int(w * self.position_ratio)
        overlay = QColor("#ffffff")
        overlay.setAlpha(24)
        painter.fillRect(rect.left(), rect.top(), max(0, pos_x - rect.left()), rect.height(), overlay)
        painter.setPen(QPen(QColor("#f8fafc"), 2))
        painter.drawLine(pos_x, rect.top(), pos_x, rect.bottom())

        if self.label:
            painter.setPen(QColor("#cbd5e1"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(rect.adjusted(6, 2, -6, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.label)


class DualWaveformDisplay(QWidget):
    """Waveform superior estilo DJ: deck A arriba y deck B abajo."""

    def __init__(self, compact: bool = False):
        super().__init__()
        self.compact = compact
        self.a_bars = self._make_bars("A")
        self.b_bars = self._make_bars("B")
        self.a_ratio = 0.0
        self.b_ratio = 0.0
        self.a_playing = False
        self.b_playing = False
        self.setMinimumHeight(82 if compact else 110)
        self.setMaximumHeight(128 if compact else 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _make_bars(self, seed_text: str):
        seed = abs(hash(seed_text)) % 100000
        values = []
        for i in range(260):
            wave = (math.sin(i / 4.8 + seed / 7000.0) + math.sin(i / 13.0 + seed / 3000.0) + 2) / 4
            spike = ((seed + i * 37) % 113) / 112
            values.append(0.14 + 0.84 * (wave * 0.65 + spike * 0.35))
        return values

    def load_deck(self, deck_number: int, path: Optional[str]):
        bars = self._make_bars(path or ("A" if deck_number == 1 else "B"))
        if deck_number == 1:
            self.a_bars = bars
            self.a_ratio = 0.0
        else:
            self.b_bars = bars
            self.b_ratio = 0.0
        self.update()

    def set_status(self, a_ratio: float, b_ratio: float, a_playing: bool, b_playing: bool):
        self.a_ratio = clamp(a_ratio)
        self.b_ratio = clamp(b_ratio)
        self.a_playing = a_playing
        self.b_playing = b_playing
        self.update()

    def _draw_wave(self, painter: QPainter, rect, bars, color: QColor, ratio: float, label: str):
        painter.setBrush(QColor("#080b10"))
        painter.setPen(QPen(QColor("#232b36"), 1))
        painter.drawRect(rect)
        mid = rect.center().y()
        w = max(1, rect.width())
        h = rect.height()
        step = max(1.0, w / len(bars))
        painter.setPen(QPen(color, max(1, int(step * 0.7))))
        for i, value in enumerate(bars):
            x = rect.left() + i * step
            amp = value * h * 0.43
            painter.drawLine(int(x), int(mid - amp), int(x), int(mid + amp))
        painter.setPen(QPen(QColor("#334155"), 1))
        for i in range(0, 32):
            x = rect.left() + int(w * i / 32)
            painter.drawLine(x, rect.top(), x, rect.bottom())
        pos_x = rect.left() + int(w * ratio)
        painter.setPen(QPen(QColor("#f8fafc"), 2))
        painter.drawLine(pos_x, rect.top(), pos_x, rect.bottom())
        painter.setPen(QColor("#dbeafe"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(rect.adjusted(8, 2, -8, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(outer, QColor("#05070b"))
        gap = 2
        half_h = (outer.height() - gap) // 2
        top = outer.adjusted(0, 0, 0, -(outer.height() - half_h))
        bottom = QRectF(outer.left(), outer.top() + half_h + gap, outer.width(), half_h)
        blue = QColor("#00bde3")
        blue.setAlpha(235 if self.a_playing else 185)
        red = QColor("#e63757")
        red.setAlpha(235 if self.b_playing else 185)
        self._draw_wave(painter, top, self.a_bars, blue, self.a_ratio, "DECK A")
        self._draw_wave(painter, bottom, self.b_bars, red, self.b_ratio, "DECK B")



class PygameMidiMessage:
    def __init__(self, status: int, data1: int, data2: int, data3: int = 0):
        self.status = status
        self.data1 = data1
        self.data2 = data2
        self.data3 = data3
        self.channel = status & 0x0F
        command = status & 0xF0

        if command == 0x80:
            self.type = "note_off"
            self.note = data1
            self.velocity = data2
        elif command == 0x90:
            self.note = data1
            self.velocity = data2
            self.type = "note_on" if data2 > 0 else "note_off"
        elif command == 0xB0:
            self.type = "control_change"
            self.control = data1
            self.value = data2
        elif command == 0xE0:
            self.type = "pitchwheel"
            self.pitch = ((data2 << 7) | data1) - 8192
        else:
            self.type = f"midi_{hex(command)}"

    def __repr__(self):
        attrs = [f"type={self.type}", f"channel={self.channel}"]
        if hasattr(self, "note"):
            attrs.extend([f"note={self.note}", f"velocity={self.velocity}"])
        if hasattr(self, "control"):
            attrs.extend([f"control={self.control}", f"value={self.value}"])
        if hasattr(self, "pitch"):
            attrs.append(f"pitch={self.pitch}")
        return "PygameMidiMessage(" + ", ".join(attrs) + ")"


class MidiBus(QObject):
    message_received = Signal(str, object)
    status_changed = Signal(str)


class MediaDeck(QObject):
    def __init__(self, name: str, deck_id: int, compact: bool = False):
        super().__init__()
        self.name = name
        self.deck_id = deck_id
        self.file_path: Optional[str] = None
        self.deck_volume = 1.0
        self.effective_volume = 1.0
        self.duration_ms = 0
        self.user_is_dragging = False
        self.bpm_manual = 0

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(105 if compact else 170)
        self.video_widget.setMaximumHeight(180 if compact else 360)
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_widget.setStyleSheet(
            "background:#020617; border:1px solid #334155; border-radius:18px;"
        )

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

    def has_media(self) -> bool:
        return self.file_path is not None

    def is_video(self) -> bool:
        return bool(self.file_path and Path(self.file_path).suffix.lower() in VIDEO_EXTENSIONS)

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def is_paused(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState

    def load(self, file_path: str):
        self.file_path = file_path
        self.duration_ms = 0
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(file_path))

    def toggle_play(self):
        if not self.has_media():
            return
        if self.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def cue_start(self):
        if not self.has_media():
            return
        self.player.setPosition(0)
        self.player.play()

    def stop(self):
        self.player.stop()
        self.player.setPosition(0)

    def set_position_ratio(self, ratio: float):
        if self.duration_ms > 0:
            self.player.setPosition(int(self.duration_ms * clamp(ratio)))

    def apply_volume(self, value: float):
        self.effective_volume = clamp(value)
        self.audio_output.setVolume(self.effective_volume)


class MiniDJ(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MiniDJ Controller Lab - v1.0")

        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        available_width = available.width() if available else 1366
        available_height = available.height() if available else 768
        self.compact_mode = available_width < 1400 or available_height < 900
        self.stack_decks = available_width < 1180
        target_width = min(1540, max(980, int(available_width * 0.96)))
        target_height = min(960, max(650, int(available_height * 0.92)))
        self.resize(target_width, target_height)
        self.setMinimumSize(900, 600)

        self.deck1 = MediaDeck("DECK A", 1, self.compact_mode)
        self.deck2 = MediaDeck("DECK B", 2, self.compact_mode)
        self.master_volume = 1.0
        self.crossfader = 0.5

        self.mapping: Dict[str, str] = safe_read_json(MAPPING_FILE, {})
        self.hotcues: Dict[str, Dict[str, int]] = safe_read_json(HOTCUES_FILE, {})
        self.library_items: List[Dict[str, str]] = safe_read_json(LIBRARY_FILE, [])
        self.learning_action: Optional[str] = None

        pygame.midi.init()
        self.midi_bus = MidiBus()
        self.midi_bus.message_received.connect(self.on_midi_message)
        self.midi_bus.status_changed.connect(self.log)
        self.midi_in = None
        self.midi_input_id: Optional[int] = None

        self.program_video = QVideoWidget()
        self.program_video.setMinimumHeight(165 if self.compact_mode else 260)
        self.program_video.setMaximumHeight(260 if self.compact_mode else 520)
        self.program_video.setStyleSheet(
            "background:#000000; border:1px solid #334155; border-radius:22px;"
        )
        self.program_audio = QAudioOutput()
        self.program_audio.setVolume(0.0)  # la salida central no duplica audio
        self.program_player = QMediaPlayer()
        self.program_player.setAudioOutput(self.program_audio)
        self.program_player.setVideoOutput(self.program_video)
        self.program_source_deck: Optional[int] = None
        self.program_source_path: Optional[str] = None
        self.sample_paths = ensure_default_samples()
        self.sample_effects: Dict[str, QSoundEffect] = {}

        self.build_ui()
        self.connect_deck_signals(self.deck1, 1)
        self.connect_deck_signals(self.deck2, 2)
        self.refresh_midi_ports()
        self.refresh_library_table()
        self.refresh_mapping_table()
        self.apply_mixer()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(120)

        self.program_timer = QTimer(self)
        self.program_timer.timeout.connect(self.sync_program_video)
        self.program_timer.start(260)

        self.midi_timer = QTimer(self)
        self.midi_timer.timeout.connect(self.poll_midi)
        self.midi_timer.start(25)

    # ---------- UI ----------
    def build_ui(self):
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self.top_toolbar())

        self.top_waveform = DualWaveformDisplay(self.compact_mode)
        main.addWidget(self.top_waveform)

        # Zona superior estilo controlador: Deck A | Mixer | Deck B
        upper = QFrame()
        upper.setObjectName("DecksArea")
        upper_layout = QVBoxLayout(upper) if self.stack_decks else QHBoxLayout(upper)
        upper_layout.setContentsMargins(8, 8, 8, 8)
        upper_layout.setSpacing(8)
        upper_layout.addWidget(self.skin_deck_widget(self.deck1, 1), stretch=5)
        upper_layout.addWidget(self.skin_mixer_panel(), stretch=2)
        upper_layout.addWidget(self.skin_deck_widget(self.deck2, 2), stretch=5)
        main.addWidget(upper, stretch=4)

        # Zona inferior estilo explorador/sampler/logs
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setObjectName("BottomSplitter")
        bottom_splitter.addWidget(self.skin_browser_tree())
        bottom_splitter.addWidget(self.skin_library_panel())
        bottom_splitter.addWidget(self.skin_right_panel())
        bottom_splitter.setSizes([180, 760, 260])
        main.addWidget(bottom_splitter, stretch=3)

        self.setCentralWidget(root)
        self.apply_connections()

    def top_toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopToolbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        logo = QLabel("MINI DJ")
        logo.setObjectName("LogoLabel")
        layout.addWidget(logo)

        user = QLabel("RUN: PEPITO")
        user.setObjectName("TinyInfo")
        layout.addWidget(user)

        layout.addWidget(QLabel("LAYOUT"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["PRO", "VIDEO", "COMPACTO"])
        self.layout_combo.setMaximumWidth(120)
        layout.addWidget(self.layout_combo)

        mode = QLabel("  AUDIO  •  VIDEO  •  SCRATCH  •  BROWSER")
        mode.setObjectName("MutedLabel")
        layout.addWidget(mode, stretch=1)

        self.master_meter = QProgressBar()
        self.master_meter.setObjectName("MasterMeter")
        self.master_meter.setRange(0, 100)
        self.master_meter.setValue(0)
        self.master_meter.setTextVisible(False)
        self.master_meter.setMaximumWidth(110)
        layout.addWidget(QLabel("MASTER"))
        layout.addWidget(self.master_meter)

        self.global_status = QLabel("Sistema listo")
        self.global_status.setObjectName("TopPill")
        layout.addWidget(self.global_status)

        self.clock_label = QLabel(time.strftime("%H:%M:%S"))
        self.clock_label.setObjectName("ClockLabel")
        layout.addWidget(self.clock_label)
        return bar

    def skin_browser_tree(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("BrowserPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        title = QLabel("LOCAL MUSIC")
        title.setObjectName("SmallSectionTitle")
        layout.addWidget(title)
        tree = QTreeWidget()
        self.browser_tree = tree
        tree.setHeaderHidden(True)
        roots = {
            "Música": ["Carpetas", "Crates", "Playlist", "Favoritos"],
            "Video": ["Clips MP4", "Visuales", "Karaoke"],
            "Controlador": ["MIDI USB", "Mapeo MIDI", "Hot cues"],
            "Online": ["SoundCloud", "Beatport Link", "iDJPool"],
        }
        for name, children in roots.items():
            item = QTreeWidgetItem([name])
            for child in children:
                item.addChild(QTreeWidgetItem([child]))
            tree.addTopLevelItem(item)
            item.setExpanded(True)
        tree.itemClicked.connect(self.on_browser_item_clicked)
        layout.addWidget(tree, stretch=1)
        return frame

    def skin_library_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LibraryPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar en biblioteca...")
        top.addWidget(self.search_box, stretch=1)
        self.btn_add_files = QPushButton("+ Archivos")
        self.btn_add_folder = QPushButton("+ Carpeta")
        self.btn_remove_item = QPushButton("Quitar")
        self.btn_clear_library = QPushButton("Limpiar")
        top.addWidget(self.btn_add_files)
        top.addWidget(self.btn_add_folder)
        top.addWidget(self.btn_remove_item)
        top.addWidget(self.btn_clear_library)
        layout.addLayout(top)

        self.library_table = QTableWidget(0, 7)
        self.library_table.setHorizontalHeaderLabels(["Title", "Artist", "Remix", "BPM", "Type", "Length", "Path"])
        self.library_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.library_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.library_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.setColumnHidden(6, True)
        self.library_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.library_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.library_table, stretch=1)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Doble clic carga en:"))
        self.library_target = QComboBox()
        self.library_target.addItems(["Deck A", "Deck B"])
        bottom.addWidget(self.library_target)
        self.btn_load_a = QPushButton("LOAD A")
        self.btn_load_b = QPushButton("LOAD B")
        bottom.addWidget(self.btn_load_a)
        bottom.addWidget(self.btn_load_b)
        bottom.addStretch(1)
        note = QLabel("Visual skin inspirado en software DJ profesional · MP4 recomendado: H.264 + AAC")
        note.setObjectName("MutedLabel")
        bottom.addWidget(note)
        layout.addLayout(bottom)
        return panel

    def skin_right_panel(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setObjectName("RightTabs")
        tabs.addTab(self.sampler_panel(), "Sampler")
        tabs.addTab(self.video_output_panel(), "Video")
        tabs.addTab(self.midi_panel(), "MIDI")
        tabs.addTab(self.log_panel(), "Log")
        return tabs

    def sampler_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SamplerPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("SAMPLER FUNCIONAL")
        title.setObjectName("SmallSectionTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)
        pads = ["AIR HORN", "SIREN", "EXPLOSION", "APPLAUSE", "LAUGH", "DROP", "KICK", "FX"]
        for i, text in enumerate(pads):
            btn = QPushButton(text)
            btn.setObjectName("SamplerPad")
            btn.clicked.connect(lambda checked=False, name=text: self.play_sample(name))
            grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(grid)

        self.btn_stop_samples = QPushButton("STOP SAMPLES")
        self.btn_stop_samples.clicked.connect(self.stop_samples)
        layout.addWidget(self.btn_stop_samples)

        info = QLabel("Cada pad reproduce un sample WAV interno. Puedes reemplazar los archivos en la carpeta samples.")
        info.setObjectName("MutedLabel")
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch(1)
        return panel

    def video_output_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("VideoPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        self.program_label = QLabel("Mostrando: --")
        self.program_label.setObjectName("DeckStatus")
        layout.addWidget(self.program_label)
        layout.addWidget(self.program_video, stretch=1)
        info = QLabel("Salida visual central: sigue el deck dominante según el crossfader.")
        info.setObjectName("MutedLabel")
        info.setWordWrap(True)
        layout.addWidget(info)
        return panel

    def log_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LogPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Eventos, MIDI, errores y estado del reproductor.")
        layout.addWidget(self.log_view)
        return panel

    def skin_deck_widget(self, deck: MediaDeck, number: int) -> QWidget:
        card = QFrame()
        card.setObjectName("DeckSkin")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        # Cabecera compacta: título, track, BPM, estado
        header = QHBoxLayout()
        deck_name = QLabel("A" if number == 1 else "B")
        deck_name.setObjectName("SideDeckLetter")
        title_box = QVBoxLayout()
        file_label = QLabel("Sweet Dreams / Carga un medio")
        file_label.setObjectName("TrackTitle")
        file_label.setWordWrap(True)
        sub = QLabel("Artist · Remix · Key · Length")
        sub.setObjectName("MutedLabel")
        title_box.addWidget(file_label)
        title_box.addWidget(sub)
        bpm_big = QLabel("126.01")
        bpm_big.setObjectName("BpmBigBlue" if number == 1 else "BpmBigRed")
        status = QLabel("SIN ARCHIVO")
        status.setObjectName("DeckStatus")
        header.addWidget(deck_name)
        header.addLayout(title_box, stretch=1)
        header.addWidget(bpm_big)
        header.addWidget(status)
        layout.addLayout(header)

        wave = WaveformDisplay("#00bde3" if number == 1 else "#e63757", self.compact_mode, f"DECK {'A' if number == 1 else 'B'}")
        layout.addWidget(wave)

        center = QHBoxLayout()
        left_fx = QVBoxLayout()
        for slot, name in enumerate(["FLANGER", "REVERB", "WAHWAH"], start=1):
            combo = QComboBox()
            combo.addItems([name, "FILTER", "ECHO", "PHASER", "OFF"])
            combo.setMaximumHeight(28)
            combo.currentTextChanged.connect(lambda value, d=deck, s=slot: self.handle_fx_change(d, s, value))
            left_fx.addWidget(combo)
        center.addLayout(left_fx, stretch=1)

        jog = JogDisplay("A" if number == 1 else "B", self.compact_mode)
        jog.accent = QColor("#00bde3") if number == 1 else QColor("#e63757")
        center.addWidget(jog, stretch=2)

        video_box = QFrame()
        video_box.setObjectName("DeckVideoBox")
        video_layout = QVBoxLayout(video_box)
        video_layout.setContentsMargins(3, 3, 3, 3)
        deck.video_widget.setMinimumHeight(86 if self.compact_mode else 110)
        deck.video_widget.setMaximumHeight(140 if self.compact_mode else 170)
        video_layout.addWidget(deck.video_widget)
        center.addWidget(video_box, stretch=3)
        layout.addLayout(center, stretch=1)

        position_row = QHBoxLayout()
        time_label = QLabel("00:00 / 00:00 · Restante 00:00")
        time_label.setObjectName("TimeLabel")
        pos_slider = QSlider(Qt.Orientation.Horizontal)
        pos_slider.setRange(0, 1000)
        pos_slider.setValue(0)
        position_row.addWidget(time_label)
        position_row.addWidget(pos_slider, stretch=1)
        layout.addLayout(position_row)

        transport = QHBoxLayout()
        load_btn = QPushButton("LOAD")
        play_btn = QPushButton("▶")
        play_btn.setObjectName("PlayButtonBlue" if number == 1 else "PlayButtonRed")
        cue_btn = QPushButton("CUE")
        stop_btn = QPushButton("STOP")
        sync_btn = QPushButton("SYNC")
        transport.addWidget(load_btn)
        transport.addWidget(cue_btn)
        transport.addWidget(play_btn)
        transport.addWidget(sync_btn)
        transport.addWidget(stop_btn)
        layout.addLayout(transport)

        cue_grid = QGridLayout()
        cue_grid.setHorizontalSpacing(5)
        cue_grid.setVerticalSpacing(5)
        cue_buttons = {}
        for cue_id in range(1, 5):
            btn = QPushButton(f"{cue_id}\n--:--")
            btn.setObjectName("CueButton")
            cue_buttons[cue_id] = btn
            cue_grid.addWidget(btn, 0, cue_id - 1)
        clear_btn = QPushButton("CLR")
        cue_grid.addWidget(clear_btn, 0, 4)
        layout.addLayout(cue_grid)

        control_grid = QGridLayout()
        vol_text = QLabel("VOL")
        vol_value = QLabel("100%")
        vol_value.setObjectName("ValueLabel")
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(100)
        bpm_label = QLabel("BPM")
        bpm_spin = QSpinBox()
        bpm_spin.setRange(0, 300)
        bpm_spin.setValue(0)
        bpm_spin.setSuffix(" BPM")
        vu = QProgressBar()
        vu.setRange(0, 100)
        vu.setValue(0)
        vu.setTextVisible(False)
        vu.setObjectName("VuBar")
        control_grid.addWidget(vol_text, 0, 0)
        control_grid.addWidget(volume, 0, 1, 1, 3)
        control_grid.addWidget(vol_value, 0, 4)
        control_grid.addWidget(bpm_label, 1, 0)
        control_grid.addWidget(bpm_spin, 1, 1)
        control_grid.addWidget(QLabel("LEVEL"), 1, 2)
        control_grid.addWidget(vu, 1, 3, 1, 2)
        layout.addLayout(control_grid)

        setattr(self, f"deck{number}_file_label", file_label)
        setattr(self, f"deck{number}_status", status)
        setattr(self, f"deck{number}_volume", volume)
        setattr(self, f"deck{number}_volume_value", vol_value)
        setattr(self, f"deck{number}_time", time_label)
        setattr(self, f"deck{number}_seek", pos_slider)
        setattr(self, f"deck{number}_vu", vu)
        setattr(self, f"deck{number}_jog", jog)
        setattr(self, f"deck{number}_wave", wave)
        setattr(self, f"deck{number}_bpm", bpm_spin)
        setattr(self, f"deck{number}_cue_buttons", cue_buttons)

        load_btn.clicked.connect(lambda: self.load_media_dialog(deck, number))
        play_btn.clicked.connect(deck.toggle_play)
        cue_btn.clicked.connect(deck.cue_start)
        stop_btn.clicked.connect(deck.stop)
        sync_btn.clicked.connect(lambda checked=False, n=number: self.sync_deck(n))
        volume.valueChanged.connect(lambda v, d=deck, n=number: self.set_deck_volume(d, n, v / 100))
        bpm_spin.valueChanged.connect(lambda v, d=deck: setattr(d, "bpm_manual", v))
        pos_slider.sliderPressed.connect(lambda d=deck: setattr(d, "user_is_dragging", True))
        pos_slider.sliderReleased.connect(lambda d=deck, s=pos_slider: self.finish_seek(d, s.value() / 1000))
        for cue_id, btn in cue_buttons.items():
            btn.clicked.connect(lambda checked=False, d=deck, n=number, c=cue_id: self.trigger_hotcue(d, n, c))
        clear_btn.clicked.connect(lambda checked=False, d=deck, n=number: self.clear_hotcues_for_deck(d, n))
        return card

    def skin_mixer_panel(self) -> QWidget:
        mixer = QFrame()
        mixer.setObjectName("CenterMixer")
        layout = QVBoxLayout(mixer)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        title = QLabel("MIXER")
        title.setObjectName("MixerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Knobs visuales simplificados por EQ
        eq_grid = QGridLayout()
        for col, deck_label in enumerate(["A", "B"]):
            eq_grid.addWidget(QLabel(deck_label), 0, col)
            for row, name in enumerate(["HI", "MID", "LOW", "FILTER"], start=1):
                knob = QSlider(Qt.Orientation.Vertical)
                knob.setRange(0, 100)
                knob.setValue(50)
                knob.setMaximumHeight(72)
                eq_grid.addWidget(knob, row, col)
                lab = QLabel(name)
                lab.setObjectName("MutedLabel")
                eq_grid.addWidget(lab, row, col + 2)
        layout.addLayout(eq_grid)

        self.cross_slider = QSlider(Qt.Orientation.Horizontal)
        self.cross_slider.setRange(0, 100)
        self.cross_slider.setValue(50)
        self.cross_value = QLabel("A 50 / 50 B")
        self.cross_value.setObjectName("ValueLabel")
        self.cross_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("CROSSFADER"))
        layout.addWidget(self.cross_slider)
        layout.addWidget(self.cross_value)

        self.master_slider = QSlider(Qt.Orientation.Vertical)
        self.master_slider.setRange(0, 100)
        self.master_slider.setValue(100)
        self.master_value = QLabel("100%")
        self.master_value.setObjectName("ValueLabel")
        master_row = QHBoxLayout()
        master_row.addWidget(QLabel("MASTER"))
        master_row.addWidget(self.master_slider)
        master_row.addWidget(self.master_value)
        layout.addLayout(master_row)
        layout.addStretch(1)
        return mixer

    def library_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10 if self.compact_mode else 14, 10 if self.compact_mode else 14, 10 if self.compact_mode else 14, 10 if self.compact_mode else 14)
        layout.setSpacing(7 if self.compact_mode else 10)

        title = QLabel("BIBLIOTECA")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar música o video...")
        layout.addWidget(self.search_box)

        buttons = QGridLayout()
        self.btn_add_files = QPushButton("+ Archivos")
        self.btn_add_folder = QPushButton("+ Carpeta")
        self.btn_remove_item = QPushButton("Quitar")
        self.btn_clear_library = QPushButton("Limpiar")
        buttons.addWidget(self.btn_add_files, 0, 0)
        buttons.addWidget(self.btn_add_folder, 0, 1)
        buttons.addWidget(self.btn_remove_item, 1, 0)
        buttons.addWidget(self.btn_clear_library, 1, 1)
        layout.addLayout(buttons)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Doble clic carga en:"))
        self.library_target = QComboBox()
        self.library_target.addItems(["Deck A", "Deck B"])
        target_row.addWidget(self.library_target)
        layout.addLayout(target_row)

        self.library_table = QTableWidget(0, 3)
        self.library_table.setHorizontalHeaderLabels(["Título", "Tipo", "Ruta"])
        self.library_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.library_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.library_table.setColumnHidden(2, True)
        self.library_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.library_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.library_table, stretch=1)

        send_row = QHBoxLayout()
        self.btn_load_a = QPushButton("Enviar a A")
        self.btn_load_b = QPushButton("Enviar a B")
        send_row.addWidget(self.btn_load_a)
        send_row.addWidget(self.btn_load_b)
        layout.addLayout(send_row)

        note = QLabel("Consejo: usa MP4 H.264 + AAC para mejor compatibilidad.")
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        return panel

    def performance_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7 if self.compact_mode else 10)

        if self.compact_mode:
            top = QVBoxLayout()
            top.addWidget(self.program_panel())
            top.addWidget(self.midi_panel())
            layout.addLayout(top, stretch=1)
        else:
            top = QHBoxLayout()
            top.addWidget(self.program_panel(), stretch=2)
            top.addWidget(self.midi_panel(), stretch=1)
            layout.addLayout(top, stretch=2)

        decks_layout = QVBoxLayout() if self.stack_decks else QHBoxLayout()
        decks_layout.setSpacing(8 if self.compact_mode else 12)
        decks_layout.addWidget(self.deck_widget(self.deck1, 1), stretch=1)
        decks_layout.addWidget(self.deck_widget(self.deck2, 2), stretch=1)
        layout.addLayout(decks_layout, stretch=5)

        layout.addWidget(self.mixer_panel())

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(85 if self.compact_mode else 125)
        self.log_view.setPlaceholderText("Eventos, mensajes MIDI y errores aparecerán aquí.")
        layout.addWidget(self.log_view)
        return panel

    def program_panel(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ProgramPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("SALIDA PRINCIPAL DE VIDEO")
        title.setObjectName("SectionTitle")
        self.program_label = QLabel("Mostrando: --")
        self.program_label.setObjectName("StatusPill")
        self.program_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title, stretch=1)
        header.addWidget(self.program_label)
        layout.addLayout(header)
        layout.addWidget(self.program_video, stretch=1)
        small = QLabel("La salida central sigue el deck dominante según el crossfader. El audio real se mezcla con el mixer.")
        small.setObjectName("MutedLabel")
        small.setWordWrap(True)
        layout.addWidget(small)
        return card

    def midi_panel(self) -> QWidget:
        midi_box = QFrame()
        midi_box.setObjectName("Panel")
        midi_layout = QGridLayout(midi_box)
        midi_layout.setContentsMargins(14, 12, 14, 12)
        midi_layout.setHorizontalSpacing(8)
        midi_layout.setVerticalSpacing(8)

        title = QLabel("CONTROLADOR MIDI")
        title.setObjectName("SectionTitle")
        self.midi_ports = QComboBox()
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_connect = QPushButton("Conectar")
        self.btn_disconnect = QPushButton("Desconectar")
        self.action_combo = QComboBox()
        self.action_combo.addItems(ACTIONS)
        self.btn_learn = QPushButton("Aprender")
        self.btn_unmap = QPushButton("Borrar acción")
        self.learn_label = QLabel("Modo aprendizaje: desactivado")
        self.learn_label.setObjectName("MutedLabel")

        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["Acción", "Control asignado"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.mapping_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mapping_table.setMaximumHeight(120)

        midi_layout.addWidget(title, 0, 0, 1, 3)
        midi_layout.addWidget(QLabel("Puerto"), 1, 0)
        midi_layout.addWidget(self.midi_ports, 1, 1, 1, 2)
        midi_layout.addWidget(self.btn_refresh, 2, 0)
        midi_layout.addWidget(self.btn_connect, 2, 1)
        midi_layout.addWidget(self.btn_disconnect, 2, 2)
        midi_layout.addWidget(QLabel("Acción"), 3, 0)
        midi_layout.addWidget(self.action_combo, 3, 1, 1, 2)
        midi_layout.addWidget(self.btn_learn, 4, 0)
        midi_layout.addWidget(self.btn_unmap, 4, 1, 1, 2)
        midi_layout.addWidget(self.learn_label, 5, 0, 1, 3)
        midi_layout.addWidget(self.mapping_table, 6, 0, 1, 3)
        return midi_box

    def deck_widget(self, deck: MediaDeck, number: int) -> QWidget:
        card = QFrame()
        card.setObjectName("DeckCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10 if self.compact_mode else 16, 9 if self.compact_mode else 14, 10 if self.compact_mode else 16, 9 if self.compact_mode else 14)
        layout.setSpacing(5 if self.compact_mode else 9)

        top = QHBoxLayout()
        deck_name = QLabel(deck.name)
        deck_name.setObjectName("DeckTitle")
        status = QLabel("SIN ARCHIVO")
        status.setObjectName("DeckStatus")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(deck_name, stretch=1)
        top.addWidget(status)
        layout.addLayout(top)

        file_label = QLabel("Carga un medio desde la biblioteca o desde el botón Cargar")
        file_label.setWordWrap(True)
        file_label.setObjectName("FileLabel")
        layout.addWidget(file_label)

        layout.addWidget(deck.video_widget, stretch=3)

        visual_row = QHBoxLayout()
        jog = JogDisplay("A" if number == 1 else "B", self.compact_mode)
        jog.accent = QColor("#38bdf8") if number == 1 else QColor("#a78bfa")
        visual_row.addWidget(jog, stretch=2)

        meters = QVBoxLayout()
        vu_label = QLabel("Nivel / posición")
        vu_label.setObjectName("MutedLabel")
        vu = QProgressBar()
        vu.setRange(0, 100)
        vu.setValue(0)
        vu.setTextVisible(False)
        vu.setObjectName("VuBar")
        time_label = QLabel("00:00 / 00:00 · Restante 00:00")
        time_label.setObjectName("TimeLabel")
        pos_slider = QSlider(Qt.Orientation.Horizontal)
        pos_slider.setRange(0, 1000)
        pos_slider.setValue(0)
        pos_slider.setObjectName("SeekSlider")
        meters.addWidget(vu_label)
        meters.addWidget(vu)
        meters.addWidget(time_label)
        meters.addWidget(pos_slider)
        visual_row.addLayout(meters, stretch=4)
        layout.addLayout(visual_row)

        load_btn = QPushButton("Cargar")
        play_btn = QPushButton("▶ Play/Pausa")
        cue_btn = QPushButton("⏮ Cue")
        stop_btn = QPushButton("■ Stop")
        if self.compact_mode:
            button_grid = QGridLayout()
            button_grid.setHorizontalSpacing(6)
            button_grid.setVerticalSpacing(6)
            button_grid.addWidget(play_btn, 0, 0, 1, 2)
            button_grid.addWidget(load_btn, 1, 0)
            button_grid.addWidget(cue_btn, 1, 1)
            button_grid.addWidget(stop_btn, 2, 0, 1, 2)
            layout.addLayout(button_grid)
        else:
            button_row = QHBoxLayout()
            button_row.addWidget(load_btn)
            button_row.addWidget(play_btn)
            button_row.addWidget(cue_btn)
            button_row.addWidget(stop_btn)
            layout.addLayout(button_row)

        cue_grid = QGridLayout()
        cue_grid.setHorizontalSpacing(6)
        cue_grid.setVerticalSpacing(6)
        cue_buttons = {}
        for cue_id in range(1, 5):
            btn = QPushButton(f"HOT CUE {cue_id}\n--:--")
            btn.setObjectName("CueButton")
            cue_buttons[cue_id] = btn
            if self.compact_mode:
                cue_grid.addWidget(btn, (cue_id - 1) // 2, (cue_id - 1) % 2)
            else:
                cue_grid.addWidget(btn, 0, cue_id - 1)
        clear_btn = QPushButton("Limpiar hot cues")
        clear_row = 2 if self.compact_mode else 1
        clear_span = 2 if self.compact_mode else 4
        cue_grid.addWidget(clear_btn, clear_row, 0, 1, clear_span)
        layout.addLayout(cue_grid)

        control_grid = QGridLayout()
        vol_text = QLabel("Volumen deck")
        vol_value = QLabel("100%")
        vol_value.setObjectName("ValueLabel")
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(100)

        bpm_label = QLabel("BPM manual")
        bpm_spin = QSpinBox()
        bpm_spin.setRange(0, 300)
        bpm_spin.setValue(0)
        bpm_spin.setSuffix(" BPM")

        control_grid.addWidget(vol_text, 0, 0)
        control_grid.addWidget(vol_value, 0, 1)
        control_grid.addWidget(volume, 1, 0, 1, 2)
        control_grid.addWidget(bpm_label, 0, 2)
        control_grid.addWidget(bpm_spin, 1, 2)
        layout.addLayout(control_grid)

        setattr(self, f"deck{number}_file_label", file_label)
        setattr(self, f"deck{number}_status", status)
        setattr(self, f"deck{number}_volume", volume)
        setattr(self, f"deck{number}_volume_value", vol_value)
        setattr(self, f"deck{number}_time", time_label)
        setattr(self, f"deck{number}_seek", pos_slider)
        setattr(self, f"deck{number}_vu", vu)
        setattr(self, f"deck{number}_jog", jog)
        setattr(self, f"deck{number}_bpm", bpm_spin)
        setattr(self, f"deck{number}_cue_buttons", cue_buttons)

        load_btn.clicked.connect(lambda: self.load_media_dialog(deck, number))
        play_btn.clicked.connect(deck.toggle_play)
        cue_btn.clicked.connect(deck.cue_start)
        stop_btn.clicked.connect(deck.stop)
        volume.valueChanged.connect(lambda v, d=deck, n=number: self.set_deck_volume(d, n, v / 100))
        bpm_spin.valueChanged.connect(lambda v, d=deck: setattr(d, "bpm_manual", v))
        pos_slider.sliderPressed.connect(lambda d=deck: setattr(d, "user_is_dragging", True))
        pos_slider.sliderReleased.connect(lambda d=deck, s=pos_slider: self.finish_seek(d, s.value() / 1000))
        for cue_id, btn in cue_buttons.items():
            btn.clicked.connect(lambda checked=False, d=deck, n=number, c=cue_id: self.trigger_hotcue(d, n, c))
        clear_btn.clicked.connect(lambda checked=False, d=deck, n=number: self.clear_hotcues_for_deck(d, n))
        return card

    def mixer_panel(self) -> QWidget:
        mixer = QFrame()
        mixer.setObjectName("MixerPanel")
        mixer_layout = QGridLayout(mixer)
        mixer_layout.setContentsMargins(16, 12, 16, 12)
        mixer_layout.setHorizontalSpacing(12)

        mixer_title = QLabel("MIXER")
        mixer_title.setObjectName("SectionTitle")
        self.cross_slider = QSlider(Qt.Orientation.Horizontal)
        self.cross_slider.setRange(0, 100)
        self.cross_slider.setValue(50)
        self.cross_value = QLabel("A 50 / 50 B")
        self.cross_value.setObjectName("ValueLabel")
        self.master_slider = QSlider(Qt.Orientation.Horizontal)
        self.master_slider.setRange(0, 100)
        self.master_slider.setValue(100)
        self.master_value = QLabel("100%")
        self.master_value.setObjectName("ValueLabel")

        mixer_layout.addWidget(mixer_title, 0, 0, 1, 5)
        mixer_layout.addWidget(QLabel("A"), 1, 0)
        mixer_layout.addWidget(QLabel("Crossfader"), 1, 1)
        mixer_layout.addWidget(self.cross_slider, 1, 2)
        mixer_layout.addWidget(QLabel("B"), 1, 3)
        mixer_layout.addWidget(self.cross_value, 1, 4)
        mixer_layout.addWidget(QLabel("Master"), 2, 1)
        mixer_layout.addWidget(self.master_slider, 2, 2)
        mixer_layout.addWidget(self.master_value, 2, 4)
        return mixer

    def apply_connections(self):
        self.btn_add_files.clicked.connect(self.add_files_to_library)
        self.btn_add_folder.clicked.connect(self.add_folder_to_library)
        self.btn_remove_item.clicked.connect(self.remove_selected_library_item)
        self.btn_clear_library.clicked.connect(self.clear_library)
        self.btn_load_a.clicked.connect(lambda: self.load_selected_library_to_deck(1))
        self.btn_load_b.clicked.connect(lambda: self.load_selected_library_to_deck(2))
        self.search_box.textChanged.connect(self.filter_library)
        self.library_table.cellDoubleClicked.connect(self.on_library_double_click)

        self.btn_refresh.clicked.connect(self.refresh_midi_ports)
        self.btn_connect.clicked.connect(self.connect_midi)
        self.btn_disconnect.clicked.connect(self.disconnect_midi)
        self.btn_learn.clicked.connect(self.start_learning)
        self.btn_unmap.clicked.connect(self.unmap_selected_action)
        self.layout_combo.currentTextChanged.connect(self.apply_layout_mode)
        self.cross_slider.valueChanged.connect(lambda v: self.set_crossfader(v / 100))
        self.master_slider.valueChanged.connect(lambda v: self.set_master_volume(v / 100))

    # ---------- Botones funcionales / Layout / Sampler ----------
    def apply_layout_mode(self, mode: str):
        mode = mode.upper()
        if mode == "VIDEO":
            if hasattr(self, "program_video"):
                self.program_video.setMinimumHeight(230 if self.compact_mode else 360)
            if hasattr(self, "program_label"):
                self.program_label.setText("Mostrando: modo VIDEO")
            tabs = self.findChildren(QTabWidget)
            if tabs:
                tabs[0].setCurrentIndex(1)
            self.log("Layout VIDEO activado: prioriza la salida visual central.")
        elif mode == "COMPACTO":
            if hasattr(self, "program_video"):
                self.program_video.setMinimumHeight(130)
            self.resize(min(self.width(), 1180), min(self.height(), 720))
            self.log("Layout COMPACTO activado: ventana reducida para pantallas pequeñas.")
        else:
            if hasattr(self, "program_video"):
                self.program_video.setMinimumHeight(165 if self.compact_mode else 260)
            self.log("Layout PRO activado.")

    def on_browser_item_clicked(self, item: QTreeWidgetItem, column: int):
        text = item.text(0).lower()
        if "video" in text or "mp4" in text or "karaoke" in text or "visuales" in text:
            self.search_box.setText("Video")
            self.log("Navegador: filtro Video aplicado.")
        elif "música" in text or "playlist" in text or "carpetas" in text or "crates" in text:
            self.search_box.clear()
            self.log("Navegador: mostrando biblioteca completa.")
        elif "midi" in text or "pioneer" in text or "controlador" in text or "mapeo" in text:
            tabs = self.findChildren(QTabWidget)
            if tabs:
                tabs[0].setCurrentIndex(2)
            self.log("Navegador: panel MIDI abierto.")
        elif "hot cues" in text:
            self.log("Navegador: los hot cues se gestionan desde cada deck.")
        else:
            self.log(f"Navegador: {item.text(0)}")

    def play_sample(self, name: str):
        path = self.sample_paths.get(name)
        if not path or not Path(path).exists():
            self.log(f"Sampler: no existe el sample {name}.")
            return
        effect = self.sample_effects.get(name)
        if effect is None:
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setLoopCount(1)
            self.sample_effects[name] = effect
        effect.stop()
        effect.setVolume(clamp(self.master_volume))
        effect.play()
        self.log(f"Sampler: reproduciendo {name}.")

    def stop_samples(self):
        for effect in self.sample_effects.values():
            effect.stop()
        self.log("Sampler: samples detenidos.")

    def sync_deck(self, number: int):
        target = self.deck1 if number == 1 else self.deck2
        source = self.deck2 if number == 1 else self.deck1
        target_bpm = getattr(self, f"deck{number}_bpm")
        source_bpm = getattr(self, f"deck{2 if number == 1 else 1}_bpm")

        if not target.has_media():
            self.log(f"{target.name}: carga un archivo antes de usar SYNC.")
            return
        if not source.has_media():
            self.log(f"{target.name}: no hay otro deck cargado para sincronizar.")
            return

        if source.bpm_manual > 0:
            target_bpm.setValue(source.bpm_manual)
            target.bpm_manual = source.bpm_manual
        elif target.bpm_manual == 0:
            target_bpm.setValue(126)
            target.bpm_manual = 126

        if source.duration_ms > 0 and target.duration_ms > 0:
            source_ratio = clamp(source.player.position() / source.duration_ms)
            target.set_position_ratio(source_ratio)

        if source.is_playing() and not target.is_playing():
            target.player.play()
        self.log(f"{target.name}: sincronizado con {source.name} usando BPM manual y posición relativa.")

    def handle_fx_change(self, deck: MediaDeck, slot: int, value: str):
        # QMediaPlayer no permite aplicar efectos DJ reales directamente; este control deja
        # registrado el efecto seleccionado para usarlo en la capa visual/MIDI.
        if value == "OFF":
            self.log(f"{deck.name}: FX {slot} desactivado.")
        else:
            self.log(f"{deck.name}: FX {slot} seleccionado: {value}.")

    # ---------- Library ----------
    def add_files_to_library(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Agregar medios", str(Path.home()), SUPPORTED_FILTER)
        self.add_paths_to_library(files)

    def add_folder_to_library(self):
        folder = QFileDialog.getExistingDirectory(self, "Agregar carpeta de medios", str(Path.home()))
        if not folder:
            return
        paths = []
        for path in Path(folder).rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                paths.append(str(path))
        self.add_paths_to_library(paths)

    def add_paths_to_library(self, paths: List[str]):
        known = {item["path"] for item in self.library_items}
        added = 0
        for p in paths:
            path = str(Path(p))
            if Path(path).suffix.lower() not in SUPPORTED_EXTENSIONS or path in known:
                continue
            self.library_items.append({
                "title": Path(path).name,
                "type": media_type_for(path),
                "path": path,
            })
            known.add(path)
            added += 1
        if added:
            self.save_library()
            self.refresh_library_table()
            self.log(f"Biblioteca: {added} medios agregados.")
        else:
            self.log("Biblioteca: no se agregaron medios nuevos.")

    def save_library(self):
        safe_write_json(LIBRARY_FILE, self.library_items)

    def refresh_library_table(self):
        self.library_table.setRowCount(0)
        for item in self.library_items:
            path = item.get("path", "")
            title = item.get("title", Path(path).name if path else "")
            row = self.library_table.rowCount()
            self.library_table.insertRow(row)
            self.library_table.setItem(row, 0, QTableWidgetItem(title))
            self.library_table.setItem(row, 1, QTableWidgetItem("--"))
            self.library_table.setItem(row, 2, QTableWidgetItem("Original Mix" if item.get("type") == "Audio" else "Video Mix"))
            self.library_table.setItem(row, 3, QTableWidgetItem("--"))
            self.library_table.setItem(row, 4, QTableWidgetItem(item.get("type", "")))
            self.library_table.setItem(row, 5, QTableWidgetItem("--:--"))
            self.library_table.setItem(row, 6, QTableWidgetItem(path))
        self.filter_library(self.search_box.text() if hasattr(self, "search_box") else "")

    def selected_library_path(self) -> Optional[str]:
        rows = self.library_table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self.library_table.item(row, 6)
        return item.text() if item else None

    def load_selected_library_to_deck(self, number: int):
        path = self.selected_library_path()
        if not path:
            self.log("Selecciona un medio en la biblioteca.")
            return
        self.load_path_to_deck(path, number)

    def on_library_double_click(self, row: int, col: int):
        deck_number = 1 if self.library_target.currentText() == "Deck A" else 2
        item = self.library_table.item(row, 6)
        if item:
            self.load_path_to_deck(item.text(), deck_number)

    def remove_selected_library_item(self):
        path = self.selected_library_path()
        if not path:
            return
        self.library_items = [i for i in self.library_items if i.get("path") != path]
        self.save_library()
        self.refresh_library_table()
        self.log(f"Biblioteca: quitado {Path(path).name}")

    def clear_library(self):
        self.library_items = []
        self.save_library()
        self.refresh_library_table()
        self.log("Biblioteca limpiada.")

    def filter_library(self, text: str):
        text = text.lower().strip()
        for row in range(self.library_table.rowCount()):
            title = self.library_table.item(row, 0).text().lower()
            artist = self.library_table.item(row, 1).text().lower()
            path = self.library_table.item(row, 6).text().lower()
            show = text in title or text in artist or text in path
            self.library_table.setRowHidden(row, not show)

    # ---------- Decks / Media ----------
    def connect_deck_signals(self, deck: MediaDeck, number: int):
        deck.player.durationChanged.connect(lambda duration, d=deck, n=number: self.on_duration_changed(d, n, duration))
        deck.player.positionChanged.connect(lambda position, d=deck, n=number: self.on_position_changed(d, n, position))
        deck.player.errorOccurred.connect(lambda error, error_string, d=deck: self.on_player_error(d, error_string))
        deck.player.mediaStatusChanged.connect(lambda status, d=deck, n=number: self.on_media_status(d, n, status))

    def load_media_dialog(self, deck: MediaDeck, number: int):
        file_path, _ = QFileDialog.getOpenFileName(self, f"Cargar medio en {deck.name}", str(Path.home()), SUPPORTED_FILTER)
        if file_path:
            self.load_path_to_deck(file_path, number)

    def load_path_to_deck(self, file_path: str, number: int):
        deck = self.deck1 if number == 1 else self.deck2
        if not Path(file_path).exists():
            QMessageBox.warning(self, "Archivo no encontrado", f"No existe el archivo:\n{file_path}")
            return
        try:
            deck.load(file_path)
            label = getattr(self, f"deck{number}_file_label")
            label.setText(Path(file_path).name)
            if hasattr(self, f"deck{number}_wave"):
                getattr(self, f"deck{number}_wave").load_media(file_path)
            if hasattr(self, "top_waveform"):
                self.top_waveform.load_deck(number, file_path)
            self.update_cue_buttons(deck, number)
            self.log(f"{deck.name}: cargado {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al cargar medio", f"No se pudo cargar el archivo:\n{exc}")

    def set_deck_volume(self, deck: MediaDeck, number: int, value: float):
        deck.deck_volume = clamp(value)
        getattr(self, f"deck{number}_volume_value").setText(f"{int(deck.deck_volume * 100)}%")
        self.apply_mixer()

    def set_crossfader(self, value: float):
        self.crossfader = clamp(value)
        left = int((1 - self.crossfader) * 100)
        right = int(self.crossfader * 100)
        self.cross_value.setText(f"A {left} / {right} B")
        self.apply_mixer()

    def set_master_volume(self, value: float):
        self.master_volume = clamp(value)
        self.master_value.setText(f"{int(self.master_volume * 100)}%")
        self.apply_mixer()

    def apply_mixer(self):
        deck1_cross = 1.0 if self.crossfader <= 0.5 else 1.0 - ((self.crossfader - 0.5) * 2)
        deck2_cross = 1.0 if self.crossfader >= 0.5 else self.crossfader * 2
        self.deck1.apply_volume(self.deck1.deck_volume * deck1_cross * self.master_volume)
        self.deck2.apply_volume(self.deck2.deck_volume * deck2_cross * self.master_volume)

    def finish_seek(self, deck: MediaDeck, ratio: float):
        deck.user_is_dragging = False
        deck.set_position_ratio(ratio)

    def on_duration_changed(self, deck: MediaDeck, number: int, duration: int):
        deck.duration_ms = duration
        self.update_time_label(deck, number, deck.player.position())

    def on_position_changed(self, deck: MediaDeck, number: int, position: int):
        if deck.duration_ms > 0 and not deck.user_is_dragging:
            slider = getattr(self, f"deck{number}_seek")
            self.set_slider_silent(slider, int((position / deck.duration_ms) * 1000))
        self.update_time_label(deck, number, position)

    def update_time_label(self, deck: MediaDeck, number: int, position: int):
        label = getattr(self, f"deck{number}_time")
        remaining = max(0, deck.duration_ms - position)
        label.setText(f"{ms_to_time(position)} / {ms_to_time(deck.duration_ms)} · Restante {ms_to_time(remaining)}")

    def on_media_status(self, deck: MediaDeck, number: int, status):
        status_label = getattr(self, f"deck{number}_status")
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            status_label.setText("CARGADO")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            status_label.setText("ERROR")
            self.log(f"{deck.name}: medio inválido o códec no compatible.")

    def on_player_error(self, deck: MediaDeck, error_string: str):
        if error_string:
            self.log(f"{deck.name}: error del reproductor: {error_string}")

    # ---------- Hot cues ----------
    def cues_for_path(self, file_path: Optional[str]) -> Dict[str, int]:
        if not file_path:
            return {}
        return self.hotcues.setdefault(file_path, {})

    def trigger_hotcue(self, deck: MediaDeck, number: int, cue_id: int):
        if not deck.has_media():
            self.log(f"{deck.name}: carga un archivo antes de usar hot cues.")
            return
        cues = self.cues_for_path(deck.file_path)
        key = str(cue_id)
        current = deck.player.position()
        if key not in cues:
            cues[key] = current
            self.save_hotcues()
            self.log(f"{deck.name}: HOT CUE {cue_id} guardado en {ms_to_time(current)}")
        else:
            deck.player.setPosition(int(cues[key]))
            self.log(f"{deck.name}: saltando a HOT CUE {cue_id} ({ms_to_time(cues[key])})")
        self.update_cue_buttons(deck, number)

    def clear_hotcues_for_deck(self, deck: MediaDeck, number: int):
        if deck.file_path and deck.file_path in self.hotcues:
            self.hotcues[deck.file_path] = {}
            self.save_hotcues()
        self.update_cue_buttons(deck, number)
        self.log(f"{deck.name}: hot cues limpiados.")

    def update_cue_buttons(self, deck: MediaDeck, number: int):
        buttons = getattr(self, f"deck{number}_cue_buttons")
        cues = self.cues_for_path(deck.file_path) if deck.file_path else {}
        for cue_id, btn in buttons.items():
            value = cues.get(str(cue_id))
            text = f"HOT CUE {cue_id}\n{ms_to_time(value)}" if value is not None else f"HOT CUE {cue_id}\n--:--"
            btn.setText(text)

    def save_hotcues(self):
        safe_write_json(HOTCUES_FILE, self.hotcues)

    # ---------- Program video ----------
    def dominant_deck_for_video(self) -> Optional[MediaDeck]:
        # Si el crossfader está al centro, prioriza el deck que esté reproduciendo.
        if self.crossfader < 0.45:
            return self.deck1
        if self.crossfader > 0.55:
            return self.deck2
        if self.deck1.is_playing() and not self.deck2.is_playing():
            return self.deck1
        if self.deck2.is_playing() and not self.deck1.is_playing():
            return self.deck2
        return self.deck1 if self.deck1.has_media() else self.deck2 if self.deck2.has_media() else None

    def sync_program_video(self):
        deck = self.dominant_deck_for_video()
        if not deck or not deck.has_media() or not deck.is_video():
            self.program_label.setText("Mostrando: --")
            return

        if self.program_source_deck != deck.deck_id or self.program_source_path != deck.file_path:
            self.program_source_deck = deck.deck_id
            self.program_source_path = deck.file_path
            self.program_player.stop()
            self.program_player.setSource(QUrl.fromLocalFile(deck.file_path))
            self.program_player.setPosition(deck.player.position())
            self.program_label.setText(f"Mostrando: {deck.name}")

        diff = abs(self.program_player.position() - deck.player.position())
        if diff > 650:
            self.program_player.setPosition(deck.player.position())

        if deck.is_playing():
            if self.program_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.program_player.play()
        elif deck.is_paused():
            if self.program_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.program_player.pause()
        else:
            self.program_player.pause()

    # ---------- MIDI ----------
    def refresh_midi_ports(self):
        self.midi_ports.clear()
        ports = []
        preferred_index = 0
        try:
            pygame.midi.quit()
            pygame.midi.init()
            for device_id in range(pygame.midi.get_count()):
                interface, name, is_input, is_output, opened = pygame.midi.get_device_info(device_id)
                if not is_input:
                    continue
                interface_text = interface.decode(errors="ignore") if isinstance(interface, bytes) else str(interface)
                name_text = name.decode(errors="ignore") if isinstance(name, bytes) else str(name)
                display_name = f"{device_id}: {name_text} ({interface_text})"
                ports.append(display_name)
                if any(keyword in name_text.lower() for keyword in ["ddj", "pioneer", "alphatheta"]):
                    preferred_index = len(ports) - 1
        except Exception as exc:
            self.log(f"Error al leer puertos MIDI: {exc}")

        self.midi_ports.addItems(ports)
        if ports:
            self.midi_ports.setCurrentIndex(preferred_index)
            self.global_status.setText("MIDI detectado")
            self.log(f"Puertos MIDI detectados: {', '.join(ports)}")
        else:
            self.global_status.setText("Sin controlador MIDI")
            self.log("No se detectaron puertos MIDI. Conecta el controlador y pulsa Actualizar.")

    def connect_midi(self):
        self.disconnect_midi()
        port_name = self.midi_ports.currentText().strip()
        if not port_name:
            self.log("No hay puerto MIDI seleccionado.")
            return
        try:
            device_id = int(port_name.split(":", 1)[0])
            self.midi_in = pygame.midi.Input(device_id)
            self.midi_input_id = device_id
            self.global_status.setText("MIDI conectado")
            self.log(f"Conectado a MIDI: {port_name}")
        except Exception as exc:
            QMessageBox.critical(self, "Error MIDI", f"No se pudo abrir el puerto MIDI:\n{exc}")

    def disconnect_midi(self):
        if self.midi_in is not None:
            try:
                self.midi_in.close()
            except Exception:
                pass
            self.midi_in = None
            self.midi_input_id = None
            self.global_status.setText("MIDI desconectado")
            self.log("MIDI desconectado.")

    def poll_midi(self):
        if self.midi_in is None:
            return
        try:
            while self.midi_in.poll():
                events = self.midi_in.read(32)
                for raw_event, _timestamp in events:
                    status, data1, data2, data3 = raw_event
                    msg = PygameMidiMessage(status, data1, data2, data3)
                    signature = self.signature_from_msg(msg)
                    self.midi_bus.message_received.emit(signature, msg)
        except Exception as exc:
            self.log(f"Error leyendo MIDI: {exc}")
            self.disconnect_midi()

    def signature_from_msg(self, msg) -> str:
        channel = getattr(msg, "channel", "x")
        if msg.type == "control_change":
            return f"control_change:{channel}:{msg.control}"
        if msg.type in ["note_on", "note_off"]:
            return f"note:{channel}:{msg.note}"
        if msg.type == "pitchwheel":
            return f"pitchwheel:{channel}:pitch"
        return f"{msg.type}:{channel}:unknown"

    def on_midi_message(self, signature: str, msg):
        if self.learning_action:
            self.mapping[self.learning_action] = signature
            self.save_mapping()
            self.refresh_mapping_table()
            self.log(f"Asignado {self.learning_action} a {signature}")
            self.learning_action = None
            self.learn_label.setText("Modo aprendizaje: desactivado")
            return

        action = self.action_for_signature(signature)
        if not action:
            return

        value = self.value_from_msg(msg)
        self.execute_action(action, value, msg)

    def value_from_msg(self, msg) -> float:
        if msg.type == "control_change":
            return clamp(msg.value / 127)
        if msg.type == "pitchwheel":
            return clamp((msg.pitch + 8192) / 16383)
        if msg.type == "note_on":
            return 1.0 if getattr(msg, "velocity", 0) > 0 else 0.0
        if msg.type == "note_off":
            return 0.0
        return 0.0

    def action_for_signature(self, signature: str) -> Optional[str]:
        for action, mapped_signature in self.mapping.items():
            if mapped_signature == signature:
                return action
        return None

    def execute_action(self, action: str, value: float, msg):
        is_button = msg.type in ["note_on", "note_off"]
        is_press = value > 0.5
        if is_button and not is_press:
            return

        if action == "deck1_play":
            self.deck1.toggle_play()
        elif action == "deck2_play":
            self.deck2.toggle_play()
        elif action == "deck1_cue":
            self.deck1.cue_start()
        elif action == "deck2_cue":
            self.deck2.cue_start()
        elif action == "deck1_stop":
            self.deck1.stop()
        elif action == "deck2_stop":
            self.deck2.stop()
        elif action == "deck1_sync":
            self.sync_deck(1)
        elif action == "deck2_sync":
            self.sync_deck(2)
        elif action == "deck1_volume":
            self.set_deck_volume(self.deck1, 1, value)
            self.set_slider_silent(self.deck1_volume, int(value * 100))
        elif action == "deck2_volume":
            self.set_deck_volume(self.deck2, 2, value)
            self.set_slider_silent(self.deck2_volume, int(value * 100))
        elif action == "deck1_seek":
            self.deck1.set_position_ratio(value)
        elif action == "deck2_seek":
            self.deck2.set_position_ratio(value)
        elif action == "crossfader":
            self.set_crossfader(value)
            self.set_slider_silent(self.cross_slider, int(value * 100))
        elif action == "master_volume":
            self.set_master_volume(value)
            self.set_slider_silent(self.master_slider, int(value * 100))
        elif action.startswith("deck1_hotcue_"):
            self.trigger_hotcue(self.deck1, 1, int(action.rsplit("_", 1)[1]))
        elif action.startswith("deck2_hotcue_"):
            self.trigger_hotcue(self.deck2, 2, int(action.rsplit("_", 1)[1]))
        elif action.startswith("sample_"):
            sample_map = {
                "sample_air_horn": "AIR HORN",
                "sample_siren": "SIREN",
                "sample_explosion": "EXPLOSION",
                "sample_applause": "APPLAUSE",
                "sample_laugh": "LAUGH",
                "sample_drop": "DROP",
                "sample_kick": "KICK",
                "sample_fx": "FX",
            }
            if action == "sample_stop_all":
                self.stop_samples()
            elif action in sample_map:
                self.play_sample(sample_map[action])

    def start_learning(self):
        self.learning_action = self.action_combo.currentText()
        self.learn_label.setText(f"Mueve/presiona el control para: {self.learning_action}")
        self.log(f"Modo aprendizaje activo para {self.learning_action}")

    def unmap_selected_action(self):
        action = self.action_combo.currentText()
        if action in self.mapping:
            del self.mapping[action]
            self.save_mapping()
            self.refresh_mapping_table()
            self.log(f"Mapeo eliminado: {action}")

    def refresh_mapping_table(self):
        self.mapping_table.setRowCount(0)
        for action in ACTIONS:
            row = self.mapping_table.rowCount()
            self.mapping_table.insertRow(row)
            self.mapping_table.setItem(row, 0, QTableWidgetItem(action))
            self.mapping_table.setItem(row, 1, QTableWidgetItem(self.mapping.get(action, "--")))

    def save_mapping(self):
        safe_write_json(MAPPING_FILE, self.mapping)

    # ---------- Shared ----------
    def set_slider_silent(self, slider: QSlider, value: int):
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)

    def refresh_status(self):
        if hasattr(self, "clock_label"):
            self.clock_label.setText(time.strftime("%H:%M:%S"))
        master_level = 0
        ratios = []
        playing_flags = []
        for number, deck in [(1, self.deck1), (2, self.deck2)]:
            status = getattr(self, f"deck{number}_status")
            vu = getattr(self, f"deck{number}_vu")
            jog = getattr(self, f"deck{number}_jog")
            wave = getattr(self, f"deck{number}_wave", None)
            ratio = (deck.player.position() / deck.duration_ms) if deck.duration_ms > 0 else 0.0
            ratios.append(ratio)
            playing_flags.append(deck.is_playing())

            if wave:
                wave.set_position(ratio)
                wave.set_playing(deck.is_playing())

            if not deck.has_media():
                status.setText("SIN ARCHIVO")
                vu.setValue(0)
                jog.set_active(False)
            elif deck.is_playing():
                status.setText("REPRODUCIENDO")
                pulse = 0.78 + 0.22 * math.sin(time.time() * 8)
                level = int(deck.effective_volume * 100 * pulse)
                vu.setValue(level)
                master_level = max(master_level, level)
                jog.set_active(True)
                jog.spin(deck.bpm_manual)
            elif deck.is_paused():
                status.setText("PAUSA")
                vu.setValue(int(deck.effective_volume * 35))
                jog.set_active(False)
            else:
                status.setText("DETENIDO")
                vu.setValue(0)
                jog.set_active(False)

        if hasattr(self, "top_waveform"):
            a_ratio = ratios[0] if len(ratios) > 0 else 0.0
            b_ratio = ratios[1] if len(ratios) > 1 else 0.0
            a_play = playing_flags[0] if len(playing_flags) > 0 else False
            b_play = playing_flags[1] if len(playing_flags) > 1 else False
            self.top_waveform.set_status(a_ratio, b_ratio, a_play, b_play)
        if hasattr(self, "master_meter"):
            self.master_meter.setValue(master_level)

    def log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        if hasattr(self, "log_view"):
            self.log_view.append(f"[{timestamp}] {text}")

    def closeEvent(self, event):
        self.disconnect_midi()
        self.deck1.player.stop()
        self.deck2.player.stop()
        self.program_player.stop()
        self.stop_samples()
        pygame.midi.quit()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLES)
    window = MiniDJ()
    window.show()
    sys.exit(app.exec())


STYLES = """
QMainWindow, QWidget {
    background: #0b0d10;
    color: #cfd4dc;
    font-family: Segoe UI, Arial;
    font-size: 12px;
}
QFrame#TopToolbar {
    background: #2b2f35;
    border-bottom: 1px solid #15181d;
}
QLabel#LogoLabel {
    background: #d7dbe0;
    color: #2b2f35;
    font-size: 18px;
    font-weight: 900;
    padding: 1px 7px;
    border-radius: 2px;
}
QLabel#TinyInfo, QLabel#ClockLabel {
    color: #d7dbe0;
    font-weight: 700;
    font-size: 11px;
}
QLabel#MutedLabel, QLabel#FileLabel {
    color: #8d98a7;
}
QLabel#TopPill, QLabel#DeckStatus {
    background: #222831;
    color: #dce3ec;
    border: 1px solid #3a424e;
    border-radius: 3px;
    padding: 4px 7px;
    font-weight: 800;
}
QFrame#DecksArea {
    background: #1a1e24;
    border-top: 1px solid #2f3742;
    border-bottom: 1px solid #0a0c0f;
}
QFrame#DeckSkin, QFrame#CenterMixer, QFrame#BrowserPanel, QFrame#LibraryPanel, QFrame#SamplerPanel, QFrame#VideoPanel, QFrame#LogPanel {
    background: #15191f;
    border: 1px solid #2b333d;
    border-radius: 3px;
}
QFrame#CenterMixer {
    background: #1d222a;
}
QFrame#DeckVideoBox {
    background: #050607;
    border: 1px solid #2a323c;
    border-radius: 3px;
}
QVideoWidget {
    background: #000000;
    border: 1px solid #26313d;
    border-radius: 2px;
}
QLabel#SideDeckLetter {
    background: #1f8ca6;
    color: #e9fbff;
    font-size: 18px;
    font-weight: 900;
    padding: 10px 8px;
    border-radius: 2px;
}
QLabel#TrackTitle {
    color: #e6e9ee;
    font-weight: 900;
    font-size: 13px;
}
QLabel#BpmBigBlue {
    color: #00bde3;
    font-size: 27px;
    font-weight: 900;
}
QLabel#BpmBigRed {
    color: #ff3b5e;
    font-size: 27px;
    font-weight: 900;
}
QLabel#MixerTitle, QLabel#SmallSectionTitle, QLabel#SectionTitle {
    color: #dbe5ee;
    font-weight: 900;
    letter-spacing: 1px;
}
QLabel#ValueLabel, QLabel#TimeLabel {
    color: #e5e7eb;
    font-weight: 800;
}
QPushButton {
    background: #2a3038;
    color: #dfe6ee;
    border: 1px solid #47515e;
    border-radius: 2px;
    padding: 5px 8px;
    font-weight: 800;
}
QPushButton:hover { background: #374151; }
QPushButton:pressed { background: #111827; }
QPushButton#PlayButtonBlue {
    background: #168db0;
    border-color: #18b4d6;
    color: #effcff;
    font-size: 16px;
}
QPushButton#PlayButtonRed {
    background: #ad2740;
    border-color: #e63757;
    color: #fff5f7;
    font-size: 16px;
}
QPushButton#CueButton {
    background: #232a33;
    color: #d9e1ea;
    min-height: 36px;
}
QPushButton#SamplerPad {
    background: #2a3038;
    min-height: 58px;
    font-size: 13px;
}
QComboBox, QTextEdit, QLineEdit, QSpinBox, QTableWidget, QTreeWidget, QTabWidget::pane {
    background: #0d1116;
    color: #e2e8f0;
    border: 1px solid #303946;
    border-radius: 2px;
    padding: 4px;
    selection-background-color: #1397b7;
    selection-color: #ffffff;
}
QTabBar::tab {
    background: #1e242c;
    color: #cbd5e1;
    border: 1px solid #303946;
    padding: 6px 9px;
}
QTabBar::tab:selected {
    background: #2b333d;
    color: #ffffff;
}
QHeaderView::section {
    background: #222831;
    color: #cbd5e1;
    border: 0;
    border-right: 1px solid #303946;
    padding: 6px;
    font-weight: 800;
}
QTableWidget::item {
    border-bottom: 1px solid #171c22;
    padding: 4px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #303946;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #0ea5c6;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #dfe6ee;
    width: 15px;
    margin: -5px 0;
    border-radius: 2px;
}
QSlider::groove:vertical {
    width: 6px;
    background: #303946;
    border-radius: 2px;
}
QSlider::sub-page:vertical {
    background: #0ea5c6;
    border-radius: 2px;
}
QSlider::handle:vertical {
    background: #dfe6ee;
    height: 14px;
    margin: 0 -5px;
    border-radius: 2px;
}
QProgressBar#VuBar, QProgressBar#MasterMeter {
    background: #07090d;
    border: 1px solid #303946;
    border-radius: 2px;
    min-height: 12px;
}
QProgressBar#VuBar::chunk, QProgressBar#MasterMeter::chunk {
    background: #20e37b;
    border-radius: 2px;
}
QSplitter::handle {
    background: #12171d;
}
"""


if __name__ == "__main__":
    main()
