"""Box parsing, permissions, append, and trigger conditions. Synthetic data only."""
from pathlib import Path

import pytest

from box import MarkdownBoxStore, match_condition, parse_box, seed_student_box, log_line

ROOT = Path(__file__).resolve().parent.parent / "docs" / "boxes"


def test_parses_department_box(store):
    iso = store.load("iso")
    assert iso.meta["department"] == "iso"
    assert iso.authority_order == ["federal", "state", "campus", "department"]
    assert len(iso.facts) == 10 and iso.facts["F-01"].authority == "federal"
    assert iso.facts["F-10"].verified is False and iso.facts["F-01"].verified is True
    assert iso.precedence["P-01"].wins == "federal" and iso.precedence["P-01"].loses == "campus"
    assert "F-04" in iso.faq["Q-01"].answer
    assert iso.escalations["E-02"].when == "final_quarter == yes and units < 12"
    assert [s.number for s in iso.sections] == [1, 2, 3, 4, 5]
    assert iso.has("Q-03") and not iso.has("F-99")
    assert "FACTS" in iso.knowledge_text() and "F-07" in iso.knowledge_text()


def test_parses_student_box(store):
    s = store.load("student")
    assert s.fields["name"] == "Riya Example" and s.fields["units"] == "16"
    assert s.preferences == ["fewer units", "more hours", "sooner"]
    assert s.departments == ["ISO", "Registrar"]
    assert s.permission("name", "iso") == "never"
    assert s.permission("hours", "ISO") == "ask"
    assert s.permission("gpa", "iso") == "no"
    assert s.permission("units", "registrar") == "yes"
    assert s.permission("unknown_field", "iso") == "never"
    assert s.highest_authority([]) == ""


def test_bad_permission_values_become_never():
    box = parse_box("## 3. Sharing permissions\n\nField | ISO\n--- | ---\nunits | maybe\nhours | YES\n")
    assert box.permission("units", "iso") == "never"
    assert box.permission("hours", "iso") == "yes"


def test_append_goes_into_the_right_section_and_reparses(store):
    store.append("student", 5, log_line("CONVERGED", "q-1", "F-01,F-02"))
    store.append("student", 5, "second | line")
    store.append("student", 8, "open | item")
    s = store.load("student")
    five = [l for l in s.section(5).lines if l.strip()]
    assert len(five) == 2 and five[0].split(" | ")[1] == "CONVERGED" and five[1] == "second | line"
    assert [l for l in s.section(8).lines if l.strip()] == ["open | item"]
    assert [l for l in s.section(6).lines if l.strip()] == []
    assert len(s.facts) == 0 and s.fields["units"] == "16"  # untouched
    with pytest.raises(ValueError):
        store.append("student", 42, "nowhere")


def test_append_sanitizes_newlines_and_pipes(store):
    store.append("iso", 5, log_line("SESSION", "s1", "text with | pipe\nand newline"))
    iso = store.load("iso")
    line = [l for l in iso.section(5).lines if l.strip()][0]
    assert "\n" not in line and line.count("|") == 3
    assert len(iso.facts) == 10


def test_real_export_wins_over_example(store, tmp_path):
    (tmp_path / "iso.md").write_text("department: real\n\n## 1. Facts\n\nF-01 | only fact | campus | src | yes\n")
    assert store.load("iso").meta["department"] == "real"
    assert store.path("student").name == "student.example.md"


def test_set_field_flips_profile_value(store):
    store.set_field("student", "final_quarter", "yes")
    assert store.load("student").fields["final_quarter"] == "yes"
    with pytest.raises(KeyError):
        store.set_field("student", "nope", "x")


def test_seed_student_box(tmp_path):
    store = MarkdownBoxStore(tmp_path)
    assert seed_student_box(store, "student-abc", "abc", "Sam Synthetic\nx", "sam@ucsc.edu")
    assert not seed_student_box(store, "student-abc", "abc", "again", "again@ucsc.edu")
    box = store.load("student-abc")
    assert box.fields["name"] == "Sam Synthetic x" and box.fields["email"] == "sam@ucsc.edu"
    assert box.permission("name", "iso") == "never"
    assert [s.number for s in box.sections] == list(range(1, 9))


@pytest.mark.parametrize("when,scope,expected", [
    ("units < 12", {"units": "8"}, True),
    ("units < 12", {"units": "16"}, False),
    ("units < 12", {}, False),
    ("final_quarter == yes and units < 12", {"final_quarter": "yes", "units": 9}, True),
    ("final_quarter == yes and units < 12", {"final_quarter": "no", "units": 9}, False),
    ("question ~ medical|illness", {"question": "I have a MEDICAL issue"}, True),
    ("question ~ medical|illness", {"question": "drop a class"}, False),
    ("hours > 20 or units < 6", {"hours": 10, "units": 3}, True),
    ("rcl_on_file != yes", {"rcl_on_file": "no"}, True),
    ("", {"units": 1}, False),
    ("garbage", {"units": 1}, False),
    ("units < abc", {"units": 1}, False),
])
def test_match_condition(when, scope, expected):
    assert match_condition(when, scope) is expected


def test_matching_escalations(store):
    iso = store.load("iso")
    ids = lambda ctx, q="": sorted(e.id for e in iso.matching_escalations(ctx, q))
    assert ids({"units": "16", "final_quarter": "no", "rcl_on_file": "no"}) == []
    assert ids({"units": "9", "final_quarter": "yes", "rcl_on_file": "no"}) == ["E-02", "E-03"]
    assert ids({"units": "16"}, "I need a medical reduced load") == ["E-01"]
    assert ids({"hours": "25"}) == ["E-04"]


def test_field_names_normalize_onto_the_student_vocabulary():
    from box import STUDENT_FIELDS, normalize_field
    assert normalize_field("hours") == "hours"
    assert normalize_field("current_on_campus_hours") == "hours"
    assert normalize_field("Current On-Campus Hours") == "hours"
    assert normalize_field("f1_status") == "visa"
    assert normalize_field("issp_approval") == "rcl_on_file"
    assert normalize_field("part_time_program_approved") == "part_time_program"
    assert normalize_field("degree_audit_units") == "units"
    assert normalize_field("CMPM_120_modality") is None
    assert normalize_field("target_units") == "units"      # harmless: units is already shared, so no ask results
    assert normalize_field("desired_units") == "units"
    assert normalize_field("") is None and normalize_field("ramen_preference") is None
    assert all(normalize_field(f) == f for f in STUDENT_FIELDS)


def test_set_permission_edits_one_cell(store):
    store.set_permission("student", "hours", "iso", "yes")
    s = store.load("student")
    assert s.permission("hours", "iso") == "yes" and s.permission("hours", "registrar") == "no"
    import pytest
    with pytest.raises(KeyError):
        store.set_permission("student", "hours", "nobody", "yes")
    with pytest.raises(KeyError):
        store.set_permission("student", "no_such_field", "iso", "yes")
    with pytest.raises(ValueError):
        store.set_permission("student", "hours", "iso", "maybe")
