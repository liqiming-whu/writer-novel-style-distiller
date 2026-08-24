---
name: {{SKILL_NAME}}
description: {{PROFILE_NAME}}样本衍生文风 Skill。用于在全新人物与情节中复用已蒸馏的叙事距离、句段节奏、对白机制、情绪推进和修辞选择；当用户点名“{{PROFILE_NAME}}文风”“使用{{SKILL_NAME}}”“按这份蒸馏文风写作／改写”时使用。分析原作、复制原作剧情或普通未指定风格的正文任务不自动触发。
metadata:
  hermes:
    tags: [novel, style, sample-derived]
    requires_toolsets: [file]
---

# {{PROFILE_NAME}}样本衍生文风

## 加载顺序

1. 必须读取 [style-profile.md](references/style-profile.md)。
2. 写正文前读取 [application-card.md](references/application-card.md)。
3. 用户要求设计“可爱、迷人、令人着迷”的主角时，再读取 [protagonist-charm.md](references/protagonist-charm.md)。
4. 用户要求设计终卷、最终高潮、结局、尾声或番外时，再读取 [ending-design.md](references/ending-design.md)；其中标记为未触发或证据不足时，不得冒充成熟结局范式。
5. 需要解释规则或审计漂移时，读取 [evidence-ledger.md](references/evidence-ledger.md) 与 [source-manifest.json](references/source-manifest.json)。

## 任务边界

- 新写：只复用文风机制，不复用来源小说的角色、剧情、设定、专属名词和关系结构。
- 续写：当前正文事实、视角、结尾动作和人物状态优先；不能为了文风改写正史。
- 扩写：不越过用户给定事件边界。
- 改写：只修改用户指定的语言维度，未指定事实保持不变。
- 分析：用户只要分析时不生成大段正文。

## 反漂移

- 当前用户指令 > 项目事实与连续性 > 场景需求 > 文风档案 > 统计指标。
- 低置信规则不得升级为硬规则。
- 不把短句、笑点、金句、口癖、比喻或留白全部拉满。
- 不机械追逐句长、段长和标点比例；指标只用于写后复核。
- 角色声音依人物身份建立，不让所有角色共享来源主角的口吻。
- 不冒充原作者，不宣称官方续作。

## 正文输出

用户要求小说正文时，只返回纯净正文；不在正文前后解释文风、引用档案或输出检查表。正文结束方式服从当前项目上位规则。

## 诚实边界

本 Skill 只能近似复用样本文本中可观察的叙事机制，不能复制作者的全部创造力、经历和未写出的判断。来源范围与局限见 `references/source-manifest.json`。