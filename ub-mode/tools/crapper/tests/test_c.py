from crapper.cli import run
from crapper.languages.c import functions_in_source
from crapper.runners import run_coverage


def test_c_counts_runtime_decisions_not_preprocessor_expressions():
    source = """int choose(int x, int y) {
#if defined(A) && (B ? C : D)
    if (x && y || x > 1) return x ? x : y;
#elif E || F
    for (; x; x--) { }
#endif
    while (y) y--;
    do { x++; } while (x < y);
    switch (x) {
    case 1: return y;
    default: return 0;
    }
}
"""
    (function,) = functions_in_source(source, "/proj/src/net/io.c", "/proj")
    assert (function.name, function.namespace) == ("choose", "net.io")
    assert function.complexity == 10
    assert (function.start_line, function.end_line) == (1, 13)


def test_c_names_definitions_through_declarators_and_header_guard():
    source = """#ifndef IO_H
#define IO_H
int declaration(int value);
int (*callback)(int value);
static inline int *address(int *value) { return value; }
static inline int (*factory(void))(int) { return callback; }
#endif
"""
    functions = functions_in_source(source, "include/net/io.h")
    assert [(fn.name, fn.namespace, fn.complexity) for fn in functions] == [
        ("address", "include.net.io", 1),
        ("factory", "include.net.io", 1),
    ]


def test_c_definitions_on_the_same_line_have_distinct_byte_ranges():
    first = "int one(void) { return 1; }"
    second = "int two(void) { return 2; }"
    functions = functions_in_source(f"{first} {second}", "names.c")
    assert [(fn.name, fn.start_line, fn.start_byte, fn.end_byte) for fn in functions] == [
        ("one", 1, 0, len(first)),
        ("two", 1, len(first) + 1, len(first) + 1 + len(second)),
    ]


def test_c_cli_scores_branches_and_lines_and_ignores_cpp(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("crapper.cli.run_coverage", run_coverage)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/io.c").write_text("int choose(int x) { if (x) return 1; return 0; }\n")
    (tmp_path / "src/api.h").write_text("static inline int count(void) { return 1; }\n")
    (tmp_path / "src/no.cpp").write_text("int ignored(void) { return 1; }\n")
    (tmp_path / "src/no.hpp").write_text("int ignored_header(void) { return 1; }\n")
    coverage = tmp_path / "target/coverage/c"
    coverage.mkdir(parents=True)
    (coverage / "lcov.info").write_text(
        "SF:/build/project/src/io.c\nDA:1,1\nBRDA:1,0,0,1\nBRDA:1,0,1,0\nend_of_record\n"
        "SF:src/api.h\nDA:1,1\nend_of_record\n"
    )

    assert run(["--threshold", "2.4"]) == 2
    assert "No default C coverage command" in capsys.readouterr().err
    assert run(["--use-existing-coverage", "--threshold", "2.5"]) == 0
    snapshot = (tmp_path / ".metrics/crap.edn").read_text()
    assert ':name "choose", :namespace "io", :complexity 2, :coverage 50.0, :crap 2.5' in snapshot
    assert ':name "count", :namespace "api", :complexity 1, :coverage 100.0, :crap 1.0' in snapshot
    assert "ignored" not in snapshot
