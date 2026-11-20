"""分帧图集动画的核心逻辑。

约定
----
* 所有时间单位均为毫秒（ms），所有帧索引都是 0 起算的整数。
* 动画结构::

      {"frames": [{"duration": 100}, ...], "loop": "once" | "loop" | "pingpong"}

* 图集结构::

      {"cols": 4, "rows": 2, "frame_w": 32, "frame_h": 32}

  共有 ``cols * rows`` 帧，按行主序排列（先填满一行再换下一行）。
* 第 ``i`` 帧覆盖 ``[start_i, start_i + duration_i)``；恰好落在帧起点的
  时间归入后一帧。时长换算与按帧率展开的误差容限为 1 个渲染帧，返回的
  时间与时长都是整数毫秒。
* 参数非法时抛出 :class:`ClipError`。
"""

import bisect
import math


class ClipError(ValueError):
    """动画或图集参数非法时抛出。"""


_LOOP_MODES = ("once", "loop", "pingpong")


def frame_rect(index, atlas) -> tuple:
    """返回帧 ``index`` 在图集中的像素矩形 ``(x, y, frame_w, frame_h)``。

    图集按行主序排列：``row, col = divmod(index, cols)``，
    ``x = col * frame_w``，``y = row * frame_h``，宽高直接取图集的
    ``frame_w`` / ``frame_h``。列数必须使用 ``cols`` 而不是 ``rows``。

    ``index`` 必须满足 ``0 <= index < cols * rows``；越界（含负数）抛
    :class:`ClipError`。
    """
    cols = atlas["cols"]
    rows = atlas["rows"]
    capacity = cols * rows
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < capacity:
        raise ClipError(f"frame index {index!r} out of range [0, {capacity})")
    row, col = divmod(index, cols)
    return (col * atlas["frame_w"], row * atlas["frame_h"],
            atlas["frame_w"], atlas["frame_h"])


def _durations(clip):
    return [frame["duration"] for frame in clip["frames"]]


def _cumulative_starts(durations):
    """各帧的起始时刻（累计时长），长度与 ``durations`` 相同。"""
    starts = []
    acc = 0
    for d in durations:
        starts.append(acc)
        acc += d
    return starts


def _locate(starts, t):
    """在累计起始时刻中定位 ``t`` 所属的帧；落在帧起点取后一帧。"""
    return bisect.bisect_right(starts, t) - 1


def _check_clip(clip):
    frames = clip.get("frames") or []
    if not frames:
        raise ClipError("frames must not be empty")
    durations = _durations(clip)
    total = sum(durations)
    if total <= 0:
        raise ClipError("total duration must be positive")
    loop = clip.get("loop")
    if loop not in _LOOP_MODES:
        raise ClipError(f"unknown loop: {loop}")
    return durations, total, loop


def frame_at(clip, elapsed_ms) -> int:
    """返回 ``elapsed_ms`` 时刻应显示的帧索引（0 起算）。

    ``elapsed_ms`` 是整数毫秒，负值按 0 处理。第 ``i`` 帧覆盖
    ``[start_i, start_i + duration_i)``，恰好落在帧起点时取后一帧。
    三种循环模式：

    * ``"once"``：只播放一遍；``elapsed_ms >= total_duration`` 时停在最后一帧。
    * ``"loop"``：``elapsed_ms`` 先对 ``total_duration`` 取模，再按各帧的
      累计时长定位（必须用累计值做二分，不能直接对原始时长数组二分）。
    * ``"pingpong"``：一次往返展开为 ``[0, 1, ..., n-1, n-2, ..., 1]``，
      折返点与接缝处都不重复帧，展开后的总时长为周期；``elapsed_ms``
      先对周期取模，再按展开后的累计时长定位。

    帧为空、总时长不为正或 ``loop`` 为未知值时抛 :class:`ClipError`。
    """
    durations, total, loop = _check_clip(clip)
    t = max(0, elapsed_ms)

    if loop == "once":
        if t >= total:
            return len(durations) - 1
        return _locate(_cumulative_starts(durations), t)

    if loop == "loop":
        return _locate(_cumulative_starts(durations), t % total)

    # pingpong：展开为 [0..n-1, n-2..1]，折返点与接缝均不重复帧。
    n = len(durations)
    if n == 1:
        return 0
    expanded = list(range(n)) + list(range(n - 2, 0, -1))
    expanded_durations = [durations[i] for i in expanded]
    period = sum(expanded_durations)
    idx = _locate(_cumulative_starts(expanded_durations), t % period)
    return expanded[idx]


def total_duration(clip) -> int:
    """返回一个完整播放周期的总时长（毫秒）。

    即所有帧 ``duration`` 之和，必须包含最后一帧；空动画返回 0（其非法性
    由 :func:`validate_clip` 报告）。返回值是非负整数毫秒。
    """
    return sum(_durations(clip))


def event_frames(clip, event_ms) -> list[int]:
    """把事件时间点映射为帧号，边界取后一帧。

    ``event_ms`` 是单个整数毫秒或整数毫秒序列。返回与事件一一对应的帧号
    列表（单值时长度为 1）。事件恰好落在某帧起点时归入后一帧，这正是
    触发该帧音效/特效的时机；事件早于 0 归入第 0 帧，大于等于
    ``total_duration`` 归入最后一帧。

    帧为空、总时长不为正或事件时间不是整数时抛 :class:`ClipError`。
    ``loop`` 不参与映射：事件时间按一遍播放的时间轴解释。
    """
    frames = clip.get("frames") or []
    if not frames:
        raise ClipError("frames must not be empty")
    durations = _durations(clip)
    total = sum(durations)
    if total <= 0:
        raise ClipError("total duration must be positive")
    starts = _cumulative_starts(durations)
    last = len(durations) - 1

    if isinstance(event_ms, (int, bool)) or not hasattr(event_ms, "__iter__"):
        events = [event_ms]
    else:
        events = list(event_ms)

    result = []
    for t in events:
        if not isinstance(t, int) or isinstance(t, bool):
            raise ClipError(f"event time must be an integer, got {t!r}")
        if t < 0:
            result.append(0)
        elif t >= total:
            result.append(last)
        else:
            result.append(_locate(starts, t))
    return result


def sync_to_fps(clip, fps) -> list[int]:
    """按渲染帧率 ``fps`` 把动画展开成一个播放周期的帧号序列。

    第 ``k`` 个渲染帧（``k`` 从 0 起）对应时间 ``k * 1000 // fps`` 毫秒，
    渲染帧数为 ``ceil(total * fps / 1000)``，即
    ``(total * fps + 999) // 1000``。帧号定位与 ``frame_at`` 的 ``once``
    模式相同：恰好落在帧起点取后一帧。全程使用整数运算，不做浮点累加，
    因此长动画的帧序列也不会漂移（总时长误差不超过 1 个渲染帧）。

    帧为空、总时长不为正或 ``fps`` 不为正整数时抛 :class:`ClipError`。
    """
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise ClipError(f"fps must be a positive integer, got {fps!r}")
    frames = clip.get("frames") or []
    if not frames:
        raise ClipError("frames must not be empty")
    durations = _durations(clip)
    total = sum(durations)
    if total <= 0:
        raise ClipError("total duration must be positive")
    starts = _cumulative_starts(durations)

    count = (total * fps + 999) // 1000
    return [_locate(starts, (k * 1000) // fps) for k in range(count)]


def validate_clip(clip, atlas) -> list[str]:
    """检查动画与图集是否匹配，返回问题描述列表（合法时为空列表）。

    按以下顺序收集问题，本身不抛异常：

    * 帧数为 0：``"frames must not be empty"``；
    * 某帧 ``duration`` 不是正整数：``"frame <i> has non-positive duration"``，
      ``i`` 为 0 起算帧号，逐帧收集；
    * 帧数超过图集容量 ``cols * rows``：
      ``"frame count <n> exceeds atlas capacity <cap>"``；
    * ``loop`` 不在 ``once`` / ``loop`` / ``pingpong`` 中：
      ``"unknown loop: <loop>"``。

    时长为 0（或负数）的帧会让播放卡在同一帧，必须作为问题上报。
    """
    problems = []
    frames = clip.get("frames") or []
    if not frames:
        problems.append("frames must not be empty")
    for i, frame in enumerate(frames):
        duration = frame.get("duration")
        if (not isinstance(duration, int) or isinstance(duration, bool)
                or duration <= 0):
            problems.append(f"frame {i} has non-positive duration")
    capacity = atlas["cols"] * atlas["rows"]
    if len(frames) > capacity:
        problems.append(
            f"frame count {len(frames)} exceeds atlas capacity {capacity}")
    loop = clip.get("loop")
    if loop not in _LOOP_MODES:
        problems.append(f"unknown loop: {loop}")
    return problems


def scale_durations(clip, ratio) -> dict:
    """按 ``ratio`` 缩放所有帧的时长，返回新的动画 dict。

    新时长 = ``max(1, floor(duration * ratio + 0.5))``（四舍五入、至少 1 ms，
    绝不产生零时长帧）。返回的是浅拷贝：``frames`` 为新列表且每项为新
    dict，入参不被修改，``loop`` 等其它键原样保留。

    ``ratio`` 必须为正数、``frames`` 不能为空，否则抛 :class:`ClipError`。
    """
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) \
            or not ratio > 0 or math.isnan(ratio):
        raise ClipError(f"ratio must be a positive number, got {ratio!r}")
    frames = clip.get("frames") or []
    if not frames:
        raise ClipError("frames must not be empty")
    scaled = dict(clip)
    scaled["frames"] = [
        {**frame, "duration": max(1, math.floor(frame["duration"] * ratio + 0.5))}
        for frame in frames
    ]
    return scaled


def clip_batch(clips, atlas, fps) -> dict:
    """按 ``fps`` 批量展开多个动画，返回 ``{名称: 帧号序列}``。

    ``clips`` 是 ``{名称: clip}`` 映射，结果保持输入的插入顺序。每个动画
    先用 :func:`validate_clip` 校验；只要有一个动画存在问题，立即抛
    :class:`ClipError` 并且不返回任何部分结果（整体回滚）。每个结果都是
    独立的新列表，某个动画的帧序列缓冲不会与其它动画共享。

    ``atlas`` 用于容量校验，``fps`` 必须为正整数；非法时抛
    :class:`ClipError`。
    """
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise ClipError(f"fps must be a positive integer, got {fps!r}")
    # 先整体校验：任一动画非法则整体回滚，不产生部分结果。
    for name, clip in clips.items():
        problems = validate_clip(clip, atlas)
        if problems:
            raise ClipError(f"clip {name!r} is invalid: {'; '.join(problems)}")
    return {name: sync_to_fps(clip, fps) for name, clip in clips.items()}
