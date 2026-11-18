from mutator.cli import run
from mutator.runner import CommandResult, CommandRunner


def test_scan_discovers_c_definitions_in_sources_and_headers(tmp_path, capsys):
    (tmp_path / "demo.c").write_text(
        "int prototype(int x);\n"
        "int outside = 0;\n"
        "int demo(int x[static 1]) { return !*x || -*x > 0; } "
        "static int same_line(int x) { return x - 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "demo.h").write_text(
        "static inline int helper(int x) { return x + 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "demo.cpp").write_text("int cpp(int x) { return x + 1; }\n", encoding="utf-8")
    assert run(["--root", str(tmp_path), "--scan", "--no-coverage"]) == 0
    output = capsys.readouterr().out
    assert "demo.c" in output and "defn/demo" in output
    assert "demo.h" in output and "defn-/helper" in output
    assert "- -> +  [defn-/same_line]" in output
    assert "|| -> &&  [defn/demo]" in output
    assert "> -> >=  [defn/demo]" in output
    assert "delete !  [defn/demo]" in output
    assert "delete -  [defn/demo]" in output
    assert output.count("1 -> 0") == 2
    for excluded in ("prototype", "outside", "demo.cpp"):
        assert excluded not in output


def test_c_requires_an_explicit_rebuilding_test_command(tmp_path, capsys):
    (tmp_path / "demo.c").write_text("int demo(void) { return 0; }\n", encoding="utf-8")
    assert run(["--root", str(tmp_path), "--no-coverage"]) == 1
    assert "C mutation requires --test-command" in capsys.readouterr().err


def test_header_mutants_use_lcov_and_keep_kills_in_the_next_snapshot(tmp_path, monkeypatch, capsys):
    header = tmp_path / "include" / "demo.h"
    header.parent.mkdir()
    original = "static inline int classify(int x) { return (x > 0) + 2; }\n"
    header.write_text(original, encoding="utf-8")
    (tmp_path / "test").mkdir()
    calls = []

    def fake_command(_runner, command, cwd, timeout):
        calls.append(command)
        if command == "project coverage":
            assert cwd == tmp_path
            report = cwd / "coverage" / "lcov.info"
            report.parent.mkdir(exist_ok=True)
            report.write_text(f"SF:{header.as_posix()}\nDA:1,1\nend_of_record\n", encoding="utf-8")
            return CommandResult(0, False, 0.01, "")
        assert command == "project test"
        text = (cwd / "include" / "demo.h").read_text(encoding="utf-8")
        if timeout is not None:
            (cwd / "test" / "local.o").write_bytes(b"worker build output")
        return CommandResult(int("- 2" in text), False, 0.01, "")

    monkeypatch.setattr(CommandRunner, "run", fake_command)
    args = ["--root", str(tmp_path), "--test-command", "project test", "--max-workers", "1"]
    assert run([*args, "--coverage-command", "project coverage"]) == 3
    assert calls == ["project coverage", *["project test"] * 4]
    assert header.read_text(encoding="utf-8") == original
    assert not (tmp_path / "test" / "local.o").exists()
    assert (tmp_path / ".metrics" / "mutate" / "include.demo.edn").exists()
    assert "survived" in capsys.readouterr().out.lower()

    calls.clear()
    assert run([*args, "--use-existing-coverage"]) == 3
    assert calls == ["project test"] * 3
