"""The files a Kratos deck is made of (`core.kratos.deck_files`): one name for each, shared by
everything that writes, stages, starts or reads a deck, and one writer that keeps the
bytes it is given."""

from core.kratos import deck_files, parameters
from core.analysis import calculation


def test_each_deck_file_has_one_name_shared_by_its_writers_and_readers():
    """The same objects, not equal copies: a copy is what drifts. `parameters` and
    `writer` write the materials names into ProjectParameters.json and `calculation`
    writes the files under them, so a rename in one alone would leave Kratos looking for
    a file that is not there; and the runner is started on the parameters file
    `write_deck` wrote."""
    assert deck_files.PARAMETERS_NAME == "ProjectParameters.json"
    assert deck_files.MATERIALS_NAME == "MaterialParameters.json"
    assert deck_files.INITIAL_MATERIALS_NAME == "initial_materials.json"
    assert deck_files.UNITS_NAME == "kratos_gui_units.json"
    for name in ("PARAMETERS_NAME", "MATERIALS_NAME", "INITIAL_MATERIALS_NAME", "UNITS_NAME"):
        assert getattr(calculation, name) is getattr(deck_files, name), name
    assert parameters.MATERIALS_NAME is deck_files.MATERIALS_NAME
    assert calculation.COMMAND[-1] is deck_files.PARAMETERS_NAME


def test_write_text_keeps_crlf_line_endings(tmp_path):
    deck_files.write_text(tmp_path / "deck.mdpa", "Begin\r\nEnd\r\n")
    assert (tmp_path / "deck.mdpa").read_bytes() == b"Begin\r\nEnd\r\n"
