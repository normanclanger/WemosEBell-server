
#!/usr/bin/env python3
"""Real-time eBell audio mixer and standalone test driver."""

import argparse
import subprocess
import threading
import time
import wave
from pathlib import Path
import time
import librosa

import numpy as np

SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_FRAMES = 441       # 10 ms of audio
MAX_BELLS = 8
AUDIO_DEVICE = "hdmi:CARD=vc4hdmi0,DEV=0"



import re

DEFAULT_TONIC = "G4"

# MIDI note numbers for C major, relative to the tonic.
MAJOR_SCALE_INTERVALS = (0, 2, 4, 5, 7, 9, 11, 12)

# Source WAV limits and base pitches.
HBELL_BASE = 61       # C#4
HBELL_MIN = 45
HBELL_MAX = 72

HBELL8_BASE = 73      # C#5
HBELL8_MAX = 90


def note_to_midi(note):
    """Convert a note name such as G4 or F#4 to a MIDI number."""
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d+)", note.strip())
    if not match:
        raise ValueError(f"Invalid note name: {note!r}")

    letter, accidental, octave_text = match.groups()
    semitones = {
        "C": 0, "D": 2, "E": 4, "F": 5,
        "G": 7, "A": 9, "B": 11,
    }
    midi = (int(octave_text) + 1) * 12 + semitones[letter.upper()]

    if accidental == "#":
        midi += 1
    elif accidental == "b":
        midi -= 1

    if not 0 <= midi <= 127:
        raise ValueError(f"Note outside MIDI range: {note!r}")

    return midi


def major_scale(tonic=DEFAULT_TONIC, bells=8):
    """Return MIDI notes for a diatonic major scale."""
    if bells < 1:
        raise ValueError("Number of bells must be at least 1")

    root = note_to_midi(tonic)
    return [root + MAJOR_SCALE_INTERVALS[i % 8] + 12 * (i // 8)
            for i in range(bells)]


def select_source(target_midi):
    """Return (source filename, semitone shift) for a target note."""
    if HBELL_MIN <= target_midi <= HBELL_MAX:
        return "hbell.wav", target_midi - HBELL_BASE

    if HBELL8_BASE <= target_midi <= HBELL8_MAX:
        return "hbell8.wav", target_midi - HBELL8_BASE

    raise ValueError(
        f"MIDI note {target_midi} is outside the supported range "
        f"({HBELL_MIN}-{HBELL_MAX} or "
        f"{HBELL8_BASE}-{HBELL8_MAX})"
    )



class BellSound:
    def __init__(self, directory=".", tonic=DEFAULT_TONIC):
        self.directory = Path(directory)
        self.samples = {}
        self.lock = threading.Lock()
        self.events = []
        self.active = []
        self.stop_event = threading.Event()
        self.process = None
        self.thread = None
        self.start_time = None
        self.frame_position = 0
        self.bell_count = MAX_BELLS


        # Prepare the required scale sounds before ringing starts.
        notes = major_scale(tonic, MAX_BELLS)

        for number, target_midi in enumerate(notes, start=1):
            source_name, shift = select_source(target_midi)
            filename = self.directory / source_name

            with wave.open(str(filename), "rb") as wav:
                if (wav.getnchannels() != CHANNELS
                        or wav.getsampwidth() != 2
                        or wav.getframerate() != SAMPLE_RATE):
                    raise ValueError(
                        f"{filename} must be stereo, 16-bit, 44100 Hz"
                    )

                raw = wav.readframes(wav.getnframes())

            samples = np.frombuffer(
                raw, dtype="<i2"
            ).reshape(-1, CHANNELS).copy()

            if shift:

                # librosa expects time along the last axis.
                audio = samples.T.astype(np.float32) / 32768.0
                shifted = librosa.effects.pitch_shift(
                    y=audio,
                    sr=SAMPLE_RATE,
                    n_steps=shift,
                )

                samples = np.clip(
                    shifted.T * 32768.0, -32768, 32767
                ).astype("<i2")

            self.samples[number] = samples

            print(
                f"Bell {number}: MIDI {target_midi}, "
                f"{source_name}, shift {shift:+d}, "
                f"{len(samples) / SAMPLE_RATE:.2f}s"
            )

        print(f"Prepared {len(self.samples)} bell sounds.")

        print(f"Loaded {len(self.samples)} bell recordings.")

    def initialise_sound(self, bell_count=MAX_BELLS):
        """Open one persistent audio stream and start the mixer."""
        self.set_bell_count(bell_count)

        self.process = subprocess.Popen(
            [
                "aplay", "-q",
                "--period-time=5000",
                "--buffer-time=20000",
                "-D", AUDIO_DEVICE,
                "-t", "raw",
                "-f", "S16_LE",
                "-c", str(CHANNELS),
                "-r", str(SAMPLE_RATE),
            ],
            stdin=subprocess.PIPE,
            bufsize=0,
        )

        self.start_time = time.monotonic()
        self.thread = threading.Thread(
            target=self._mixer_loop, daemon=True
        )
        self.thread.start()
        print(f"Audio output ready: {AUDIO_DEVICE}")


    def set_bell_count(self, count):
        if not 1 <= count <= MAX_BELLS:
            raise ValueError(f"Bell count must be between 1 and {MAX_BELLS}")
        with self.lock:
            self.bell_count = count

    def play_wav(self, wav_number, delay=0.0):
        """Schedule playback of a WAV recording."""
        if wav_number not in self.samples:
            raise ValueError(f"Invalid WAV number: {wav_number}")

        start_frame = int(
            (time.monotonic() + max(0.0, delay) - self.start_time)
            * SAMPLE_RATE
        )
        with self.lock:
            self.events.append((start_frame, wav_number))



    def _mixer_loop(self):
        while not self.stop_event.is_set():
            start = self.frame_position
            end = start + CHUNK_FRAMES

            # Keep the mixer in step with real time.
            target_time = self.start_time + start / SAMPLE_RATE
            wait = target_time - time.monotonic()-0.05
            if wait > 0:
                time.sleep(wait)

            mix = np.zeros((CHUNK_FRAMES, CHANNELS), dtype=np.int32)

            with self.lock:
                # Move events that start in this chunk into active voices.
                ready = [e for e in self.events if e[0] < end]
                self.events = [e for e in self.events if e[0] >= end]

                for event_frame, wav_number in ready:
                    self.active.append((event_frame, wav_number, 0))

                remaining = []

                for event_frame, wav_number, offset in self.active:
                    samples = self.samples[wav_number]
                    chunk_offset = max(0, event_frame - start)
                    source_offset = offset

                    if event_frame < start:
                        chunk_offset = 0

                    count = min(
                        CHUNK_FRAMES - chunk_offset,
                        len(samples) - source_offset,
                    )

                    if count > 0:
                        mix[chunk_offset:chunk_offset + count] += (
                            samples[source_offset:source_offset + count]
                            .astype(np.int32)
                        )
                        source_offset += count

                    if source_offset < len(samples):
                        remaining.append(
                            (event_frame, wav_number, source_offset)
                        )

                self.active = remaining

            pcm = np.clip(mix, -32768, 32767).astype("<i2").tobytes()

            try:
                self.process.stdin.write(pcm)
            except (BrokenPipeError, OSError):
                self.stop_event.set()
                break

            self.frame_position = end

    def shutdown_sound(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

        if self.process:
            try:
                self.process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait()

        print("Audio stopped.")





def plain_hunt_rows(bells=8):
    """Generate Plain Hunt by alternating two pair-swapping operations."""
    row = list(range(1, bells + 1))
    yield row.copy()

    for change in range(2 * bells):
        if change % 2 == 0:
            # Swap all adjacent pairs: 12, 34, 56, 78.
            start = 0
            stop = bells
        else:
            # Keep the end positions; swap 23, 45, 67.
            start = 1
            stop = bells - 1

        for i in range(start, stop, 2):
            row[i], row[i + 1] = row[i + 1], row[i]

        yield row.copy()



def run_test(args):
    sound = BellSound(tonic=args.tonic)
    sound.initialise_sound(args.bells)
    
    sound.play_wav(
        8,
        delay=0
    )    
        
    try:
        print(f"Test mode: {args.mode}; bells: {args.bells}")

        if args.mode == "scale":
            for bell in range(1, args.bells + 1):
                file_number = args.bells + 1 - bell
                sound.play_wav(
                    file_number,
                    delay=(bell - 1) * args.interval
                )
                print(f"Bell {bell} -> {file_number}.wav")

        elif args.mode == "overlap":
            for bell in range(1, args.bells + 1):
                file_number = 8 - args.bells + bell
                sound.play_wav(
                    file_number,
                    delay=(bell - 1) * args.interval
                )
                print(f"Bell {bell} -> {file_number}.wav")

        elif args.mode == "crunch":
            # Two pairs, followed by a larger near-simultaneous chord.
            pairs = [(1, 2), (args.bells - 1, args.bells)]
            for index, pair in enumerate(pairs):
                delay = index * 2.5
                for bell in pair:
                    if 1 <= bell <= args.bells:
                        sound.play_wav(8 - args.bells + bell, delay=delay)

            delay = 5.0
            for bell in range(1, args.bells + 1):
                sound.play_wav(bell, delay=delay)

     

        elif args.mode == "plainhunt":
            interval = args.interval
            strike_number = 0

            for row_number, row in enumerate(plain_hunt_rows(args.bells)):
                # Add one extra bell interval before each handstroke row.
                if row_number % 2 == 1:
                    strike_number += 1

                print("".join(map(str, row)))

                for bell in row:
                    sound.play_wav(
                        args.bells + 1 - bell,
                        delay=strike_number * interval,
                    )
                    strike_number += 1        

        # Allow the last recordings to finish.
        if args.mode == "plainhunt":
            row_count = 2 * (args.bells - 1) + 1
            gap_count = (row_count - 1) // 2
            duration = (
                row_count * args.bells
                + gap_count
            ) * args.interval + 6
        elif args.mode in ("scale", "overlap"):
            duration = 1.8 + (args.bells - 1) * args.interval
        else:
            duration = 6.8

        time.sleep(duration)
        


    except KeyboardInterrupt:
        print("\nTest interrupted.")
    finally:
        sound.shutdown_sound()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("scale", "overlap", "crunch", "plainhunt"),
        default="scale",
    )
    parser.add_argument("--bells", type=int, default=8)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument(
        "--tonic",
        default=DEFAULT_TONIC,
        help="Lowest bell / major-scale tonic (default: G4)",
    )
    args = parser.parse_args()

    if not 1 <= args.bells <= MAX_BELLS:
        parser.error("--bells must be between 1 and 8")
    if args.interval < 0:
        parser.error("--interval cannot be negative")
        
    notes = major_scale(args.tonic, args.bells)

    for bell, midi_note in enumerate(notes, start=1):
        source, shift = select_source(midi_note)
        print(
            f"Bell {bell}: MIDI {midi_note}, "
            f"{source}, shift {shift:+d} semitones"
        )

    run_test(args)


if __name__ == "__main__":
    main()