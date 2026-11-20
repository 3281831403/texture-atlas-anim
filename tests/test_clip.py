"""texture-atlas-anim 的红灯测试。

所有时间单位均为毫秒（ms）。图集为
``{"cols", "rows", "frame_w", "frame_h"}``，动画为
``{"frames": [{"duration"}], "loop"}``。不联网、不随机、不 sleep。
"""

import pytest

from anim.clip import (
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


ATLAS = {"cols": 3, "rows": 2, "frame_w": 16, "frame_h": 16}
CLIP = {
    "frames": [
        {"duration": 100},
        {"duration": 200},
        {"duration": 100},
        {"duration": 100},
    ],
    "loop": "loop",
}


def test_frame_rect_uses_columns_for_row_major_layout():
    atlas = {"cols": 3, "rows": 2, "frame_w": 16, "frame_h": 16}

    assert frame_rect(0, atlas) == (0, 0, 16, 16)
    assert frame_rect(1, atlas) == (16, 0, 16, 16)
    assert frame_rect(2, atlas) == (32, 0, 16, 16)
    assert frame_rect(3, atlas) == (0, 16, 16, 16)
    assert frame_rect(5, atlas) == (32, 16, 16, 16)
    with pytest.raises(ClipError):
        frame_rect(6, atlas)
    with pytest.raises(ClipError):
        frame_rect(-1, atlas)


def test_frame_at_uses_cumulative_durations():
    assert frame_at(CLIP, 0) == 0
    assert frame_at(CLIP, 99) == 0
    assert frame_at(CLIP, 100) == 1
    assert frame_at(CLIP, 299) == 1
    assert frame_at(CLIP, 300) == 2
    assert frame_at(CLIP, 499) == 3
    assert frame_at(CLIP, 500) == 0
    assert frame_at(CLIP, 1100) == 1
    assert frame_at(CLIP, 1300) == 2


def test_pingpong_does_not_repeat_frames_at_turns():
    clip = {"frames": [{"duration": 100} for _ in range(3)], "loop": "pingpong"}
    times = [0, 100, 200, 299, 300, 399, 400, 450, 500, 699, 700]

    assert [frame_at(clip, t) for t in times] == [
        0,
        1,
        2,
        2,
        1,
        1,
        0,
        0,
        1,
        2,
        1,
    ]


def test_total_duration_includes_every_frame():
    assert total_duration(CLIP) == 500
    assert total_duration({"frames": [{"duration": 250}], "loop": "once"}) == 250


def test_event_frames_boundary_uses_following_frame():
    events = [0, 99, 100, 299, 300, 399, 400, 499, 500, 900, -10]

    assert event_frames(CLIP, events) == [0, 0, 1, 1, 2, 2, 3, 3, 3, 3, 0]


def test_sync_to_fps_uses_integer_time_without_drift():
    clip = {"frames": [{"duration": 1000} for _ in range(20)], "loop": "loop"}

    frames = sync_to_fps(clip, 60)

    assert len(frames) == 1200
    assert frames == [index for index in range(20) for _ in range(60)]
    assert frames[59] == 0 and frames[60] == 1


def test_validate_clip_reports_zero_duration_frames():
    assert validate_clip(CLIP, ATLAS) == []

    zero = {
        "frames": [{"duration": 100}, {"duration": 0}, {"duration": 100}],
        "loop": "loop",
    }
    assert validate_clip(zero, ATLAS) == ["frame 1 has non-positive duration"]

    negative = {"frames": [{"duration": 100}, {"duration": -5}], "loop": "loop"}
    assert validate_clip(negative, ATLAS) == ["frame 1 has non-positive duration"]


def test_scale_durations_keeps_at_least_one_ms():
    clip = {
        "frames": [{"duration": 100}, {"duration": 200}, {"duration": 1}],
        "loop": "loop",
    }

    scaled = scale_durations(clip, 0.001)

    assert [frame["duration"] for frame in scaled["frames"]] == [1, 1, 1]
    assert [frame["duration"] for frame in clip["frames"]] == [100, 200, 1]
    assert scaled is not clip


def test_clip_batch_does_not_share_frame_buffers():
    first = {"frames": [{"duration": 100}, {"duration": 100}], "loop": "once"}
    second = {"frames": [{"duration": 50}], "loop": "once"}

    result = clip_batch({"first": first, "second": second}, ATLAS, 10)

    assert result["first"] == sync_to_fps(first, 10)
    assert result["second"] == sync_to_fps(second, 10)
    assert result["first"] is not result["second"]

    result["first"].append(999)
    assert result["second"] == sync_to_fps(second, 10)

    broken = {"frames": [{"duration": 0}], "loop": "once"}
    with pytest.raises(ClipError):
        clip_batch({"ok": first, "broken": broken}, ATLAS, 10)


def test_unknown_loop_is_reported_and_raises():
    clip = {"frames": [{"duration": 100}], "loop": "reverse"}

    with pytest.raises(ClipError):
        frame_at(clip, 0)
    assert validate_clip(clip, ATLAS) == ["unknown loop: reverse"]


def test_frame_at_zero_returns_first_frame():
    once = {"frames": [{"duration": 100}, {"duration": 100}], "loop": "once"}
    pingpong = {"frames": [{"duration": 100}, {"duration": 100}], "loop": "pingpong"}

    assert frame_at(CLIP, 0) == 0
    assert frame_at(once, 0) == 0
    assert frame_at(pingpong, 0) == 0


def test_once_past_end_clamps_to_last_frame():
    clip = {
        "frames": [
            {"duration": 100},
            {"duration": 200},
            {"duration": 100},
            {"duration": 100},
        ],
        "loop": "once",
    }

    assert frame_at(clip, 499) == 3
    assert frame_at(clip, 500) == 3
    assert frame_at(clip, 1_000_000) == 3


def test_empty_clip_raises_clip_error():
    clip = {"frames": [], "loop": "loop"}

    with pytest.raises(ClipError):
        frame_at(clip, 0)

    assert validate_clip(clip, ATLAS) == ["frames must not be empty"]


def test_single_frame_clip_always_returns_zero():
    for loop in ("once", "loop", "pingpong"):
        clip = {"frames": [{"duration": 250}], "loop": loop}
        for elapsed_ms in (0, 1, 249, 250, 10_000):
            assert frame_at(clip, elapsed_ms) == 0


def test_clip_batch_success_keeps_input_order():
    clips = {
        "idle": {"frames": [{"duration": 100}, {"duration": 100}], "loop": "loop"},
        "walk": {
            "frames": [{"duration": 50}, {"duration": 50}, {"duration": 50}],
            "loop": "once",
        },
        "run": {"frames": [{"duration": 25}], "loop": "once"},
    }

    result = clip_batch(clips, ATLAS, 20)

    assert list(result) == ["idle", "walk", "run"]
    for name, clip in clips.items():
        assert result[name] == sync_to_fps(clip, 20)
