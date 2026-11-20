# texture-atlas-anim

## 题面

角色待机动画换成分帧图集后，帧序列行列颠倒、循环还会闪一下：frame_rect 按行优先取矩形却把列数用成 rows，行列颠倒；frame_at 对未累计的时长数组做二分，永远返回第 0 帧；pingpong 在折返点和接缝处把末尾与开头重复两帧，画面闪一下；total_duration 漏掉最后一帧，循环提前跳回；event_frames 在事件时间恰好落在帧边界时取前一帧，音效晚一帧；sync_to_fps 用浮点累加渲染时间，长动画到尾部漂移 2 帧；validate_clip 不检查时长为 0 的帧，播放卡住；scale_durations 缩放后最短时长允许 0 ms，出现零时长帧；clip_batch 让所有动画共用同一个帧序列缓冲，动画之间串帧；loop 遇到未知值静默当成 once，不报错。anim/clip.py 是核心，tests/test_clip.py 15个红。要修的是：frame_rect 按 cols 做行主序矩形，frame_at 用累计时长定位并支持 once/loop/pingpong，total_duration 计入最后一帧，event_frames 边界取后一帧，sync_to_fps 全程整数展开，validate_clip 完整上报零时长/越界/未知 loop，scale_durations 保证最短 1 ms，clip_batch 隔离缓冲并在任一动画非法时整体回滚。

## 运行方式

```bash
cd D:\gsb-20261119\texture-atlas-anim
python -m pytest tests -q
```

初始状态应恰好输出：

```text
15 failed
```

15 条测试全部因桩函数 `raise NotImplementedError` 而失败；收集、导入和语法检查必须通过，不能出现 `error`。实现后测试应全部通过。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 图形渲染 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 测试约束

`tests/` 是验收测试，不得修改、删除或新增；修复只能落在 `anim/clip.py`。实现只允许使用 Python 标准库（`math`、`bisect`）与 pytest；测试离线运行，不使用随机数、不 sleep。所有时间单位为毫秒（ms），断言允许 1 ms 容差。
