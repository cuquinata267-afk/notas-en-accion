import pytest
from pydantic import ValidationError

from app.main import NewNote, progress


def test_title_trims_spaces():
    assert NewNote(folder_id=1, title="  Redes  ").title == "Redes"


def test_title_rejects_blank():
    with pytest.raises(ValidationError):
        NewNote(folder_id=1, title="   ")


def test_title_rejects_more_than_120_characters():
    with pytest.raises(ValidationError):
        NewNote(folder_id=1, title="a" * 121)


def test_progress_without_tasks():
    assert progress([]) == {"completed": 0, "total": 0}


def test_progress_with_pending_tasks():
    assert progress([{"done": True}, {"done": False}, {"done": True}]) == {"completed": 2, "total": 3}


def test_progress_when_all_tasks_are_done():
    assert progress([{"done": True}, {"done": True}]) == {"completed": 2, "total": 2}
