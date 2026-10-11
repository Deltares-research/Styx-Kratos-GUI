"""The files a Kratos deck is made of (`core.kratos.files`): one name for each, shared by
everything that writes, stages, starts or reads a deck, and one writer that keeps the
bytes it is given."""

from core.kratos import files, processes
from core.run import calculate


def test_each_deck_file_has_one_name_shared_by_its_writers_and_readers():
    """The same objects, not equal copies: a copy is what drifts. `processes` and
    `export` write the materials names into ProjectParameters.json and `calculate`
    writes the files under them, so a rename in one alone would leave Kratos looking for
    a file that is not there; and the runner is started on the parameters file
    `write_deck` wrote."""
    assert files.PARAMETERS_NAME == "ProjectParameters.json"
    assert files.MATERIALS_NAME == "MaterialParameters.json"
    assert files.INITIAL_MATERIALS_NAME == "initial_materials.json"
    assert files.UNITS_NAME == "kratos_gui_units.json"
    for name in ("PARAMETERS_NAME", "MATERIALS_NAME", "INITIAL_MATERIALS_NAME", "UNITS_NAME"):
        assert getattr(calculate, name) is getattr(files, name), name
    assert processes.MATERIALS_NAME is files.MATERIALS_NAME
    assert calculate.COMMAND[-1] is files.PARAMETERS_NAME


def test_write_text_keeps_crlf_line_endings(tmp_path):
    files.write_text(tmp_path / "deck.mdpa", "Begin\r\nEnd\r\n")
    assert (tmp_path / "deck.mdpa").read_bytes() == b"Begin\r\nEnd\r\n"
