# 结构化契约：蓝图与章节路线

阶段 1、2 产出的两份 JSON 必须满足以下限制（`novel_tools.py validate` 按同一套规则校验）。

通用：UTF-8、合法 JSON、无注释无尾逗号；文本字段不能为 null；稳定 ID 正则 `^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$`。

## blueprint.json

```json
{
  "theme": "主题（2–2000）",
  "coreConflict": "核心冲突（2–4000）",
  "protagonistArc": "主角弧（2–4000）",
  "beats": "节拍（10–8000），覆盖开端、升级、转折、高潮、余波",
  "characters": [
    { "id": "chen-mo", "name": "（1–200）", "role": "（1–500）",
      "goal": "（1–2000）", "fear": "（1–2000）", "secret": "（1–2000）" }
  ],
  "plotThreads": [
    { "id": "thread-blackmarket", "name": "（1–200）",
      "setup": "埋设（1–2000）", "plannedPayoff": "计划回收（1–2000）" }
  ],
  "timeline": [
    { "id": "evt-001", "when": "（1–500）", "event": "（1–4000）", "consequence": "（1–4000）" }
  ]
}
```

数量：characters 3–50、plotThreads 3–50、timeline 6–200；同类内 ID 不得重复。

生成要点：
- 主题、核心冲突、主角弧、节拍相互支撑，节拍覆盖完整故事弧。
- 每个人物都要有目标 / 恐惧 / 秘密；每条伏笔都要有埋设与计划回收——这两组字段是后续跨章一致性的锚点。
- 时间线至少覆盖：故事开始前的关键前史、以及各幕的转折事件。

## outline.json

```json
{
  "chapters": [
    {
      "sequence": 1,
      "title": "（1–200）",
      "sceneGoal": "可观察的戏剧行动（5–2000）",
      "summaryTarget": "本章结束时必须成立的新事实（5–2000）",
      "requiredStateIds": ["chen-mo", "thread-blackmarket"]
    }
  ]
}
```

限制：chapters 数量**恰好等于** project.json 的 targetChapterCount；sequence 从 1 连续递增；requiredStateIds 每章 0–30 个且只能取自 blueprint.json 的稳定 ID。

生成要点：
- sceneGoal 写「谁做了什么、导致什么」，不写主题抽象。
- summaryTarget 要可校验：本章写完时读者应知道的新事实、角色状态变化。
- 每章承接前章后果、制造下一章条件；避免相邻章节职责重复。
- 全书覆盖：主角弧各阶段、每条伏笔的埋设与回收、冲突升级、唯一高潮、余波收束。

## 契约修复（校验失败时，最多一次）

> 仅修复 JSON 格式或违反所列契约的字段；只能依据原始设定，不增加新情节、不改变语义、不解释。若某条目没有足够依据满足契约，整条删除，不要用 null 或虚构内容补齐。

仍不通过就人工检查后修正，不把无效数据当成蓝图或路线使用。
