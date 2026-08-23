# Writer Novel Style Distiller

面向中文小说的文风蒸馏、主角魅力分析与完结收束设计 Skill。

当前版本：`v1.3.0`

## 功能

- 全文读取与清洗：TXT、Markdown、HTML、DOCX、EPUB。
- 全量统计与早中晚漂移分析，不局限前若干章。
- 十六个常规文风维度、八项文笔量化审计、条件式幽默感审计，加一个完结作品条件维度。
- 主角“可爱、迷人、令人着迷”的依恋机制分析。
- 用户明确作品已完结时，强制分析主线结局、尾声／后日谈及已提供番外。
- 文笔审计覆盖语言控制、对白塑造、画面氛围、情绪感染、信息组织、关系亲密感、收笔与留白及综合文笔。
- 条件式幽默感审计：只在幽默系统证据充分时生成；无明显幽默感的作品整章省略。
- 证据账本、置信度、诚实边界、删除测试与反漫画化。
- 生成自包含、可复用、可打包和可安装的样本文风 Skill。
- 静态校验、指标回放、多场景测试和独立盲评协议。
- 内置经过公开边界审计的可复用档案库。

## 内置可复用档案

- [`profiles/001-youfei-priest/`](profiles/001-youfei-priest/README.md)：《有匪》样本衍生档案，含文笔量化审计、完整文风、谢允魅力、主线结局与源文件所含番外分析。
- [`profiles/002-hanshanji-kanchangtingwan/`](profiles/002-hanshanji-kanchangtingwan/README.md)：《寒山纪》样本衍生档案，含文笔量化审计、完整文风、洛元秋魅力、第225章结局与第226章番外分析。
- [`profiles/003-longzu-jiangnan/`](profiles/003-longzu-jiangnan/README.md)：《龙族1—4》样本衍生档案，含文笔与幽默审计、路明非代入机制、楚子航与绘梨衣角色魅力，以及四个卷级尾声分析。

完整目录见 [`profiles/CATALOG.md`](profiles/CATALOG.md)。内置档案不含来源小说全文、清洗语料或连续长段原文。

## 权威审计测试案例

- [`LUXUN_AUDIT_BENCHMARK.md`](LUXUN_AUDIT_BENCHMARK.md)：鲁迅精选集部分样本的文笔与幽默审计金标准，用于回归测试来源隔离、跨文体分析、条件式幽默触发、评分和任务边界。
- 该案例位于仓库根目录，**不是**内置文风档案，不进入 `profiles/`，不由 `SKILL.md` 自动加载，也不用于复制鲁迅思想、人格或历史身份。
- 静态校验：`python3 scripts/validate_audit_benchmark.py`。

## 主要触发语

- 文风蒸馏
- 分析这篇小说的文风并保存
- 生成可复用文风 Skill
- 分析主角为什么可爱／迷人／让人着迷
- 这部小说已完结，请分析结局和番外
- 使用 001／002／003 文风档案写作、改写或比较
- 从文笔角度审计并量化评分
- 审计作品的幽默机制（仅在明显存在时）
- 更新已有文风档案

## 安装到 Operit

将仓库目录放到：

```text
/sdcard/Download/Operit/skills/writer-novel-style-distiller/
```

并确保该目录内直接存在 `SKILL.md`。在 Operit 的 Skill 列表中启用后，即可通过 `use_package` 加载。

## 工具链

```bash
python3 scripts/ingest_novel.py novel.txt --output ./job/work

# 只有用户明确说明作品已完结，或来源有可靠完结信息时才设置 complete：
python3 scripts/ingest_novel.py novel.txt --output ./job/work \
  --completion-status complete --completion-basis user_explicit

python3 scripts/measure_style.py --workdir ./job/work
python3 scripts/init_profile.py --output ./job/deliverable \
  --skill-name writer-sample-style-demo --profile-name 示例文风 --protagonist 主角名
python3 scripts/validate_profile.py ./job/deliverable/writer-sample-style-demo
python3 scripts/package_skill.py ./job/deliverable/writer-sample-style-demo --output ./dist
```

`work/` 包含私有分析语料，不得打包。交付 Skill 仅包含抽象文风规则、魅力机制、结局设计机制、证据定位和来源清单。

## 自检

```bash
python3 scripts/validate_audit_benchmark.py
python3 scripts/self_check.py
python3 scripts/validate_builtin_profiles.py
```

## 公开与版权边界

- 仓库采用 MIT License，覆盖本项目原创代码与原创分析文档。
- 来源小说、角色、剧情、专属设定及原文表达的权利归相应作者和权利人所有。
- 内置档案仅用于研究和迁移抽象写作机制，不授予复制、传播或改编来源文学作品的权利。
- 不得使用本项目冒充原作者或生成所谓官方续作。

第三方项目与文学作品声明见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
