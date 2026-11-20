"""分帧图集动画工具包。"""

from .clip import (
    ClipError,
    clip_batch,
    event_frames,
    frame_at,
    frame_rect,
    scale_durations,
    sync_to_fps,
    total_duration,
    validate_clip,
)

__all__ = [
    "ClipError",
    "clip_batch",
    "event_frames",
    "frame_at",
    "frame_rect",
    "scale_durations",
    "sync_to_fps",
    "total_duration",
    "validate_clip",
]
