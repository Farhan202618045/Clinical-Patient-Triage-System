from pathlib import Path

import pytest

from triage_system import TriageError, TriageManager


def make_manager(tmp_path: Path) -> TriageManager:
    return TriageManager(tmp_path / "patients.json")


def register(manager, name, severity, age=30):
    return manager.register_patient(
        name=name,
        age=age,
        sex="Prefer not to say",
        chief_complaint=f"Fictional complaint for {name}",
        severity=severity,
    )


def test_register_assigns_unique_id_and_room(tmp_path):
    manager = make_manager(tmp_path)
    critical = register(manager, "Sample A", "Critical")
    low = register(manager, "Sample B", "Low")

    assert critical.patient_id == "P000001"
    assert low.patient_id == "P000002"
    assert critical.assigned_room == "Resuscitation"
    assert low.assigned_room == "General"
    assert manager.get_patient("p000001") is critical


def test_priority_queue_selects_severity_then_arrival(tmp_path):
    manager = make_manager(tmp_path)
    low_first = register(manager, "Low first", "Low")
    high = register(manager, "High", "High")
    critical = register(manager, "Critical", "Critical")
    critical_2 = register(manager, "Critical second", "Critical")

    assert [p.patient_id for p in manager.priority_waiting()] == [
        critical.patient_id, critical_2.patient_id, high.patient_id, low_first.patient_id
    ]
    assert manager.call_next_urgent().patient_id == critical.patient_id
    assert manager.call_next_urgent().patient_id == critical_2.patient_id


def test_room_queue_is_fifo(tmp_path):
    manager = make_manager(tmp_path)
    first = register(manager, "Moderate first", "Moderate")
    second = register(manager, "Low second", "Low")

    called = manager.call_next_from_room("General")
    assert called.patient_id == first.patient_id
    remaining = manager.room_waiting("General")
    assert [p.patient_id for p in remaining] == [second.patient_id]


def test_severity_update_moves_indexes_and_room(tmp_path):
    manager = make_manager(tmp_path)
    patient = register(manager, "Changing severity", "Low")

    manager.update_severity(patient.patient_id, "High")

    assert patient.assigned_room == "Emergency"
    assert patient.patient_id in {p.patient_id for p in manager.find_by_severity("High")}
    assert patient.patient_id not in {p.patient_id for p in manager.find_by_severity("Low")}
    assert patient.patient_id not in {p.patient_id for p in manager.room_waiting("General")}
    assert patient.patient_id in {p.patient_id for p in manager.room_waiting("Emergency")}
    assert "Changed from Low to High" in patient.action_history[-1]["details"]


def test_history_stack_and_persistence(tmp_path):
    path = tmp_path / "patients.json"
    manager = TriageManager(path)
    patient = register(manager, "History test", "Moderate")
    manager.add_action(patient.patient_id, "Vitals recorded", "Fictional data")

    loaded = TriageManager(path)
    loaded_patient = loaded.get_patient(patient.patient_id)
    assert loaded_patient is not None
    assert loaded_patient.action_history[-1]["action"] == "Vitals recorded"
    assert len(loaded_patient.action_history) == 2


def test_invalid_registration_and_unknown_patient_raise(tmp_path):
    manager = make_manager(tmp_path)
    with pytest.raises(TriageError):
        manager.register_patient("", 20, "Other", "Something", "Low")
    with pytest.raises(TriageError):
        manager.add_action("P999999", "Vitals recorded", "")


def test_discharge_removes_patient_from_waiting_views(tmp_path):
    manager = make_manager(tmp_path)
    patient = register(manager, "Discharge test", "Critical")
    manager.mark_discharged(patient.patient_id, "Demo discharge")

    assert patient.status == "Discharged"
    assert manager.waiting_count() == 0
    assert manager.priority_waiting() == []
    assert manager.room_waiting("Resuscitation") == []
