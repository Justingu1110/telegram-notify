import pytest
from git_helpers import git, make_checkout, make_remote
from telegram_notify.statestore import GitStateStore, StateStoreError

RECORD = {"丸久小山園 抹茶": {"failures": 0, "products": {"8835": {"name": "永寿 四十克 罐", "stock_text": "8有库存"}}}}


def test_loading_before_anything_was_saved_gives_an_empty_record(tmp_path):
    remote = make_remote(tmp_path)

    assert GitStateStore(make_checkout(tmp_path, remote, "run1")).load() == {}


def test_what_one_run_saves_the_next_run_reads_back_identically(tmp_path):
    remote = make_remote(tmp_path)
    first_run = GitStateStore(make_checkout(tmp_path, remote, "run1"))
    first_run.load()
    first_run.save(RECORD)

    next_run = GitStateStore(make_checkout(tmp_path, remote, "run2"))

    assert next_run.load() == RECORD


def commits_on_state_branch(remote):
    return int(git("rev-list", "--count", "refs/heads/state", cwd=remote))


def saved_once(tmp_path):
    remote = make_remote(tmp_path)
    store = GitStateStore(make_checkout(tmp_path, remote, "run1"))
    store.load()
    store.save(RECORD)
    return remote, store


def test_saving_an_unchanged_record_creates_no_new_commit(tmp_path):
    remote = make_remote(tmp_path)
    run2 = GitStateStore(make_checkout(tmp_path, remote, "run2"))
    first = GitStateStore(make_checkout(tmp_path, remote, "run1"))
    first.load()
    first.save(RECORD)

    run2.load()
    run2.save(RECORD)

    assert commits_on_state_branch(remote) == 1


def test_a_changed_record_adds_exactly_one_commit_on_top(tmp_path):
    remote = make_remote(tmp_path)
    first = GitStateStore(make_checkout(tmp_path, remote, "run1"))
    first.load()
    first.save(RECORD)
    second = GitStateStore(make_checkout(tmp_path, remote, "run2"))
    second.load()

    second.save({**RECORD, "第二個監控項目": {"failures": 1}})

    assert commits_on_state_branch(remote) == 2
    assert GitStateStore(make_checkout(tmp_path, remote, "run3")).load()["第二個監控項目"] == {"failures": 1}


def test_the_state_branch_holds_only_the_record_and_other_branches_are_untouched(tmp_path):
    remote = make_remote(tmp_path)
    work = make_checkout(tmp_path, remote, "dev")
    (work / "README.md").write_text("code lives here\n", encoding="utf-8")
    git("add", "README.md", cwd=work)
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "code", cwd=work)
    git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=work)
    main_before = git("rev-parse", "refs/heads/main", cwd=remote)
    store = GitStateStore(make_checkout(tmp_path, remote, "run1"))
    store.load()

    store.save(RECORD)

    assert git("ls-tree", "--name-only", "refs/heads/state", cwd=remote).split() == ["state.json"]
    assert git("rev-parse", "refs/heads/main", cwd=remote) == main_before


def test_the_record_file_is_readable_json_that_keeps_the_original_characters(tmp_path):
    remote, _store = saved_once(tmp_path)

    text = git("show", "refs/heads/state:state.json", cwd=remote)

    assert "丸久小山園 抹茶" in text
    assert "8有库存" in text
    assert text.endswith("\n")
    assert "\n  " in text


def test_saving_over_a_record_that_changed_in_the_meantime_fails_instead_of_overwriting(tmp_path):
    remote, _store = saved_once(tmp_path)
    slow = GitStateStore(make_checkout(tmp_path, remote, "slow"))
    slow.load()
    fast = GitStateStore(make_checkout(tmp_path, remote, "fast"))
    fast.load()
    fast.save({**RECORD, "快的": {"failures": 0}})

    with pytest.raises(StateStoreError):
        slow.save({**RECORD, "慢的": {"failures": 0}})

    assert "快的" in GitStateStore(make_checkout(tmp_path, remote, "check")).load()


def test_an_unreachable_remote_is_an_error_and_not_an_empty_record(tmp_path):
    checkout = make_checkout(tmp_path, tmp_path / "does-not-exist.git", "run1")

    with pytest.raises(StateStoreError):
        GitStateStore(checkout).load()
