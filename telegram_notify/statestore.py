import json
import os
import subprocess

_IDENTITY = {
    "GIT_AUTHOR_NAME": "telegram-notify",
    "GIT_AUTHOR_EMAIL": "telegram-notify@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "telegram-notify",
    "GIT_COMMITTER_EMAIL": "telegram-notify@users.noreply.github.com",
}


class StateStoreError(Exception):
    pass


class GitStateStore:
    def __init__(self, repo_dir=".", remote="origin", branch="state", path="state.json"):
        self._repo_dir = repo_dir
        self._remote = remote
        self._branch = branch
        self._path = path
        self._parent = None
        self._loaded_text = None

    def load(self):
        self._parent = None
        self._loaded_text = None
        if not self._git("ls-remote", "--heads", self._remote, self._branch).strip():
            return {}
        self._git("fetch", "-q", self._remote, f"+refs/heads/{self._branch}:refs/remotes/{self._remote}/{self._branch}")
        self._parent = self._git("rev-parse", f"refs/remotes/{self._remote}/{self._branch}").strip()
        self._loaded_text = self._git("show", f"{self._parent}:{self._path}")
        return json.loads(self._loaded_text)

    def save(self, state):
        text = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if text == self._loaded_text:
            return
        blob = self._git("hash-object", "-w", "--stdin", input=text).strip()
        tree = self._git("mktree", input=f"100644 blob {blob}\t{self._path}\n").strip()
        commit_args = ["commit-tree", tree, "-m", "Update state"]
        if self._parent:
            commit_args += ["-p", self._parent]
        commit = self._git(*commit_args, env=_IDENTITY).strip()
        self._git("push", "-q", self._remote, f"{commit}:refs/heads/{self._branch}")
        self._parent = commit
        self._loaded_text = text

    def _git(self, *args, input=None, env=None):
        result = subprocess.run(
            ["git", *args],
            cwd=self._repo_dir,
            input=input,
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
        )
        if result.returncode != 0:
            raise StateStoreError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout
