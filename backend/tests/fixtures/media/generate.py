"""Regenerate privacy-safe MP4 fixtures; FFmpeg is needed only for this script."""

import struct
import subprocess
from pathlib import Path

folder = Path(__file__).parent
subprocess.run([
    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
    "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", "0.25", "-c:a", "aac",
    "-brand", "3gp4", str(folder / "aac-3gp4.m4a"),
], check=True)
subprocess.run([
    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
    "-f", "lavfi", "-i", "color=c=black:s=16x16:r=4", "-frames:v", "1",
    "-c:v", "mpeg4", "-an", "-brand", "3gp4", str(folder / "video-only.mp4"),
], check=True)

# The native dialer puts an unversioned metadata atom directly before the audio
# track. mdat precedes moov, so inserting metadata leaves sample offsets intact.
raw = (folder / "aac-3gp4.m4a").read_bytes()
position = 0
while raw[position + 4:position + 8] != b"moov":
    position += int.from_bytes(raw[position:position + 4], "big")
moov_size = int.from_bytes(raw[position:position + 4], "big")
assert position + moov_size == len(raw)
mvhd_size = int.from_bytes(raw[position + 8:position + 12], "big")
insert_at = position + 8 + mvhd_size
handler_payload = b"\x00" * 8 + b"mdta" + b"\x00" * 13
handler = struct.pack(">I4s", 8 + len(handler_payload), b"hdlr") + handler_payload
metadata = struct.pack(">I4s", 8 + len(handler), b"meta") + handler
native = bytearray(raw[:insert_at] + metadata + raw[insert_at:])
native[position:position + 4] = (moov_size + len(metadata)).to_bytes(4, "big")
(folder / "aac-3gp4-native-meta.m4a").write_bytes(native)
