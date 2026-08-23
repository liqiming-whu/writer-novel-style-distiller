# v1.1.0

本版本增加文笔量化审计，并加入第二个完整内置档案《寒山纪》。

## Highlights

- 所有完整 `style-profile.md` 在“一句话核心文风”后固定给出八项文笔审计。
- 评分覆盖语言控制、对白塑造、画面氛围、情绪感染、信息组织、关系亲密感、收笔与留白及综合文笔。
- 每项使用十分制并保留一位小数，同时写明证据摘要和主要扣分点。
- `001-youfei-priest` 已补入文笔审计。
- 新增 `002-hanshanji-kanchangtingwan`，含洛元秋魅力、第225章结局与第226章番外分析。
- 公开包不包含《有匪》《寒山纪》原文、清洗语料或私有分析中间产物。

## Verification

发布前通过：

```bash
python3 scripts/validate_builtin_profiles.py
python3 scripts/self_check.py
```

## Upgrade note

旧版生成档案若缺少“文笔审计与量化评分”，将在新版严格校验中报错；可按 `templates/style-profile.md` 补齐八项评分后重新验证。
