# Frontend Interview Knowledge Base

一个可持续维护的前端面试知识库，包含面试题归档、模拟面试、两轮评分、知识讲解、缺陷跟踪和随机复习流程。

## 仓库内容

- `knowledge-base/state.json`：题库、作答、评分和复习状态的唯一结构化数据源。
- `knowledge-base/QUESTION_BANK.md`：按录入顺序生成的完整题库。
- `knowledge-base/INDEX.md`：学习进度、分类分布和复习入口。
- `knowledge-base/WEAKNESSES.md`：根据历次作答生成的缺陷清单。
- `knowledge-base/questions/`：每道题的知识讲解与作答点评。
- `knowledge-base/sessions/`：每次模拟面试记录。
- `knowledge-base/sources/`：面经来源、岗位背景和反问记录。
- `skills/interview-coach/`：供 Codex 执行面试流程的项目级技能与维护脚本。

## 在另一台电脑上使用

```bash
git clone git@github.com:lia-loveCode/Frontend-Interview.git
cd Frontend-Interview
python3 skills/interview-coach/scripts/kb.py init
```

用 Codex 打开仓库根目录后，可以直接使用自然语言：

- `记录以下题目：……`
- `从第一题开始面试`
- `请随机出题`
- `只练 Agent 架构类题目`
- `查看我的薄弱点`
- `继续上次的题`

根目录的 `AGENTS.md` 会让 Codex 自动遵循 `interview-coach` 工作流。

## 多设备同步

开始练习前先同步远端：

```bash
git pull --rebase
```

练习结束后提交并推送本次变化：

```bash
git add AGENTS.md README.md knowledge-base skills
git commit -m "Update interview practice records"
git push
```

`state.json` 是核心状态文件。避免在两台电脑上同时练习和修改题库，否则可能产生需要人工合并的冲突。

## 本地维护命令

刷新所有 Markdown 视图：

```bash
python3 skills/interview-coach/scripts/kb.py init
```

维护脚本还支持 `add`、`start-session`、`record`、`random` 和 `variant` 子命令；日常使用时通常由 Codex 自动调用，无需手工操作。
