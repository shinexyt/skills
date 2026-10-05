# ai-novel-writer

从空文件夹开始的长篇小说 AI 协作创作技能。只负责把作品带到「可以开始写」的状态：

1. **确认设定** — 标题、前提、题材、叙事结构、视角、文风、目标章节数
2. **生成蓝图** — 主题/冲突/主角弧/节拍 + 人物 / 伏笔 / 时间线（稳定 ID），请用户确认
3. **规划章节路线** — 每章的戏剧目标、须成立的新事实、所需状态

阶段 2 到此结束，之后由 agent 自主写作：按需读取工作区文件、自定上下文组织方式、按静态规则自检与修订，没有定稿、归档、完结、恢复等固定环节。

另有可选的**本地阅读器**：把工作区的 JSON 与章节渲染成一个自带全部数据的单文件网页（概览 / 章节 / 蓝图 / 路线 / 状态五个视图，明暗主题、全书搜索、章节大纲侧栏），双击即可离线打开。它不参与创作流程，只读，不修改任何工作区数据。

## 包内容

```
ai-novel-writer/
├── SKILL.md                    # 主流程（阶段 0–2 引导 + 阶段 3 交还控制权）
├── README.md                   # 本文件
├── references/
│   ├── schemas.md              # blueprint / outline 契约与生成要点
│   └── writing-guide.md        # 写作与审阅的静态规则
└── scripts/
    ├── novel_tools.py          # init / validate（可选，Python 3.10+ 标准库）
    ├── build_viewer.py         # 生成本地阅读器（可选，标准库）
    ├── build_viewer.ps1        # 同上，无 Python 时的 PowerShell 版
    └── viewer_template.html    # 阅读器模板（CSS/JS 内联，含数据占位符）
```

## 安装

| 工具 | 位置 |
| --- | --- |
| WorkBuddy | `~/.workbuddy/skills/ai-novel-writer/`（跨项目）或项目内 `.workbuddy/skills/` |
| Codex CLI | `~/.codex/skills/ai-novel-writer/`；或在工作区 `AGENTS.md` 中写「遵循 <路径>/SKILL.md 完成小说创作」 |
| Claude Code | `~/.claude/skills/ai-novel-writer/` 或项目 `.claude/skills/` |
| 其他 AI 工具 | 把目录放进模型可读的文件系统，让它先读 `SKILL.md` |

## 使用

对 AI 说「帮我写一部小说」并指定一个文件夹即可。也可手动调用脚本：

```bash
python scripts/novel_tools.py init <工作区> --title ... --premise ... --chapters 30
python scripts/novel_tools.py validate <工作区>/blueprint.json --type blueprint
python scripts/novel_tools.py validate <工作区>/outline.json  --type outline
```

### 阅读器

生成一个**自带全部数据的单文件网页**：双击 `<工作区>/viewer.html` 即可离线阅读，不起服务器、不联网、无外部依赖。

```bash
python scripts/build_viewer.py <工作区>          # 生成
python scripts/build_viewer.py <工作区> --open   # 生成并立即用浏览器打开
```

数据是**生成时固定下来的**：写了新章节后重新运行一次命令，再刷新浏览器页面即可看到新内容——单纯刷新不会带来新数据。右上角徽标显示数据来源（`快照`；把模板直接复制使用时为 `数据文件`）。

没有 Python 时用等效的 PowerShell 版（Windows 自带），或把 `viewer_template.html` 复制成 `<工作区>/viewer.html` 再自行写一个 `viewer-data.js`：

```powershell
powershell -File scripts/build_viewer.ps1 -Dir <工作区> -Open
```

脚本都只是辅助：没有 Python 环境时，直接按 `references/schemas.md` 写文件、人工核对同样可行；阅读器同样只是一个可选的只读视图。

## 工作区

```
<工作区>/
├── project.json     # 小说设定
├── blueprint.json   # 叙事蓝图
├── outline.json     # 章节路线
├── state.json       # 可选：一致性备忘（人物现状/伏笔进展/时间线）
├── chapters/        # 正文 001.md, 002.md, ...
└── viewer.html      # 可选：本地阅读器（由 build_viewer.py 生成）
```
