# claude-skills

我自己的 Claude Code skill 收藏，也是**開新專案用的範本 repo**。

目前內容：[mattpocock/skills](https://github.com/mattpocock/skills)（MIT，commit `49dd158`）的 27 個 skill，放在 `.claude/skills/`。授權檔見 `.claude/skills/LICENSE-mattpocock-skills`。

## 開新專案（每個新專案做一次）

1. 在 GitHub 網頁（用 Safari 開電腦版也可以）打開這個 repo，按綠色的 **Use this template → Create a new repository**，取新專案的名字。
2. 在 Claude Code 雲端選剛建好的 repo，開新 session。
3. 第一件事執行 `/setup-matt-pocock-skills`：選 issue 放哪（GitHub Issues）、triage 標籤用預設值。它會產生 `CLAUDE.md` 和 `docs/agents/`。
4. 之後照流程：`/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement-spec`。

> 新 repo 一建好就帶著 `.claude/skills/`，所以第一個 session 打 `/` 就看得到這些 skill。

## 更新已經存在的專案

範本只在「建立新 repo 的那一刻」複製一次，之後不會自動同步。要更新某個舊專案時，在那個專案的 session 裡請 Claude：

> 把 `justingu1110/claude-skills` 的 `.claude/skills/` 同步到這個 repo，開 PR。

## 新增或修改 skill

先改這個 repo，再用上面的方式同步到各專案。
