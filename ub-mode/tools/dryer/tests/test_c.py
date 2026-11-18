from dryer.cli import run


def test_cli_finds_c_duplicates_in_source_and_headers(tmp_path, capsys):
    (tmp_path / "a.c").write_text(
        "int declared(int value);\n"
        "int alpha(int value) {\n"
        "    int total = adjust(value, 10);\n"
        "    return total + 1;\n"
        "}\n",
        encoding="utf-8",
    )
    header = (
        "int declared(int input);\n"
        "int beta(int input) {\n"
        "    int result = adjust(input, 0x20);\n"
        "    return result + 2;\n"
        "}\n"
    )
    (tmp_path / "b.h").write_text(header, encoding="utf-8")
    (tmp_path / "ignored.cpp").write_text(header, encoding="utf-8")

    assert run([
        "--root", str(tmp_path), "--edn", "--threshold", "0.99",
        "--min-lines", "1", "--min-nodes", "1",
    ]) == 0
    report = capsys.readouterr().out
    assert report.count(':language "c"') == 1
    assert ':score 1.0' in report
    assert ':file "a.c", :start-line 2, :end-line 5' in report
    assert ':file "b.h", :start-line 2, :end-line 5' in report
    assert "ignored.cpp" not in report
    assert (tmp_path / ".metrics" / "dry.edn").read_text(encoding="utf-8") == report


def test_cli_compares_file_scope_c_functions_inside_conditionals(tmp_path, capsys):
    (tmp_path / "a.h").write_text(
        "#ifndef A_H\n"
        "#define A_H\n"
        "int first(int value) {\n"
        "    int nested(int arg) { return adjust(arg); }\n"
        "    return adjust(value);\n"
        "}\n"
        "#else\n"
        "int second(int arg) { return select(arg); }\n"
        "#endif\n",
        encoding="utf-8",
    )

    assert run([
        "--root", str(tmp_path), "--edn", "--threshold", "0",
        "--min-lines", "1", "--min-nodes", "1",
    ]) == 0
    report = capsys.readouterr().out
    assert report.count(':language "c"') == 1
    assert ':file "a.h", :start-line 3, :end-line 6' in report
    assert ':file "a.h", :start-line 8, :end-line 8' in report
