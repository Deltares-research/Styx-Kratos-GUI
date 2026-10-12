"""`js_coverage.summarise`: Chrome's precise coverage, reduced to functions per live module."""

from tests.browser import js_coverage

LIVE = "file:///D:/Checkouts/Private/Kratos-GUI/frontend/js/"


def script(url, *functions):
    return {"url": url, "functions": [
        {"functionName": name, "ranges": [{"startOffset": start, "endOffset": start + 10,
                                           "count": count}]}
        for name, start, count in functions]}


def test_a_function_is_covered_when_it_ran_at_least_once():
    summary = js_coverage.summarise([script(LIVE + "zip.js", ("", 0, 1),
                                            ("create", 5, 3), ("crc", 20, 0))])
    assert summary == {"zip.js": {"functions": 2, "covered": 1, "percent": 50.0,
                                  "missed": ["crc"]}}


def test_the_script_body_itself_is_not_counted_as_a_function():
    summary = js_coverage.summarise([script(LIVE + "ruler.js", ("", 0, 1), ("plan", 30, 1))])
    assert summary["ruler.js"]["functions"] == 1


def test_an_anonymous_function_inside_the_script_is_counted_and_named_by_offset():
    summary = js_coverage.summarise([script(LIVE + "api.js", ("", 0, 1), ("", 40, 0))])
    assert summary["api.js"]["missed"] == ["(anonymous @40)"]


def test_only_live_modules_are_summarised():
    summary = js_coverage.summarise([
        script("file:///D:/Checkouts/Private/Kratos-GUI/js/ui.js", ("el", 5, 1)),
        script("file:///D:/Checkouts/Private/Kratos-GUI/frontend/tests/test-zip.js", ("t", 5, 1)),
        script(LIVE + "zip.js", ("create", 5, 1)),
    ])
    assert list(summary) == ["zip.js"]


def test_a_script_reported_twice_is_merged_not_double_counted():
    summary = js_coverage.summarise([script(LIVE + "zip.js", ("create", 5, 0)),
                                     script(LIVE + "zip.js", ("create", 5, 2))])
    assert summary["zip.js"] == {"functions": 1, "covered": 1, "percent": 100.0, "missed": []}


def test_a_module_with_no_functions_is_fully_covered():
    summary = js_coverage.summarise([script(LIVE + "data.js", ("", 0, 1))])
    assert summary["data.js"]["percent"] == 100.0


def test_below_names_every_module_under_the_target_lowest_first():
    summary = {"a.js": {"percent": 90.0}, "b.js": {"percent": 40.0}, "c.js": {"percent": 74.9}}
    assert js_coverage.below(summary, 75.0) == ["b.js", "c.js"]


def test_the_table_is_markdown_with_one_row_per_module_and_a_total():
    summary = js_coverage.summarise([script(LIVE + "zip.js", ("a", 5, 1), ("b", 20, 0)),
                                     script(LIVE + "api.js", ("c", 5, 1))])
    lines = js_coverage.table(summary).splitlines()
    assert lines[0].startswith("| Module")
    assert any(line.startswith("| `zip.js` | 2 | 1 | 50.0 %") for line in lines)
    assert lines[-1] == "| **total** | 3 | 2 | 66.7 % |"
