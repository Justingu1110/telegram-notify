import subprocess


def git(*args, cwd, input=None):
    result = subprocess.run(
        ["git", "-c", "init.defaultBranch=main", *args],
        cwd=cwd,
        input=input,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def make_remote(tmp_path):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    git("init", "--bare", "-q", cwd=remote)
    return remote


def make_checkout(tmp_path, remote, name):
    checkout = tmp_path / name
    checkout.mkdir()
    git("init", "-q", cwd=checkout)
    git("remote", "add", "origin", str(remote), cwd=checkout)
    return checkout
