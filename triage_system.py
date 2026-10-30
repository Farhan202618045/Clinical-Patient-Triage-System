"""Core logic for the Clinical Patient Triage System academic demo.

This module contains the data structures and business rules. It deliberately
keeps the Streamlit UI separate so the logic can be unit-tested independently.

IMPORTANT: This is a classroom simulation, not a medical device or clinical
triage recommendation system. Severity is entered by the user/staff member.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import heapq
import json
from pathlib import Path
from typing import Any, Iterable

SEVERITY_RANK = {"Critical": 1, "High": 2, "Moderate": 3, "Low": 4}
SEVERITIES = tuple(SEVERITY_RANK.keys())
ROOM_FOR_SEVERITY = {
    "Critical": "Resuscitation",
    "High": "Emergency",
    "Moderate": "General",
    "Low": "General",
}
ROOMS = ("Resuscitation", "Emergency", "General")
VALID_STATUSES = ("Waiting", "In Treatment", "Discharged")


def now_iso() -> str:
    """Return a readable, timezone-aware local timestamp."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Patient:
    patient_id: str
    name: str
    age: int
    sex: str
    chief_complaint: str
    severity: str
    arrival_time: str
    assigned_room: str
    status: str = "Waiting"
    queue_order: int = 0
    queue_version: int = 0
    # A Python list used as a stack: append = push, history[-1] = top.
    action_history: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Patient":
        allowed = {key: raw[key] for key in cls.__dataclass_fields__ if key in raw}
        allowed.setdefault("action_history", [])
        allowed["action_history"] = list(allowed["action_history"] or [])
        return cls(**allowed)


class TriageError(ValueError):
    """Raised when an operation would violate the application's rules."""


class TriageManager:
    """Manage patient records and queue workflows using explicit data structures.

    Core data structures:
      * patients: dict for expected O(1) patient ID lookups.
      * triage_heap: min-heap keyed by severity rank and arrival order.
      * room_queues: dict[str, deque[str]] for FIFO room-specific waiting lists.
      * patients_by_severity: inverted index for fast severity filtering.
      * each Patient.action_history: list used as a LIFO action-history stack.

    Queue entries use a version number. Outdated entries are lazily ignored in
    the heap; this avoids expensive arbitrary deletion from a heap and makes
    re-triage/status updates safe.
    """

    def __init__(self, storage_path: str | Path = "data/patients.json") -> None:
        self.storage_path = Path(storage_path)
        self.patients: dict[str, Patient] = {}
        self.triage_heap: list[tuple[int, int, str, int]] = []
        self.room_queues: dict[str, deque[str]] = {room: deque() for room in ROOMS}
        self.patients_by_severity: dict[str, set[str]] = {s: set() for s in SEVERITIES}
        self.next_patient_number = 1
        self.next_queue_order = 1
        self.load()

    # ---------- Persistence ----------
    def load(self) -> None:
        """Load records from JSON, then rebuild in-memory indexes and queues."""
        if not self.storage_path.exists():
            self._rebuild_indexes_and_queues()
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
            records = payload.get("patients", [])
            self.patients = {}
            for raw in records:
                patient = Patient.from_dict(raw)
                self.patients[patient.patient_id] = patient
            self.next_patient_number = max(
                int(payload.get("next_patient_number", 1)),
                self._max_patient_number() + 1,
            )
            self.next_queue_order = max(
                int(payload.get("next_queue_order", 1)),
                max((p.queue_order for p in self.patients.values()), default=0) + 1,
            )
            self._rebuild_indexes_and_queues()
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            # Do not silently discard a bad file. The UI can show this as an error.
            raise TriageError(f"Could not load saved patient data: {exc}") from exc

    def save(self) -> None:
        """Persist a compact snapshot; the running app continues using RAM indexes."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "next_patient_number": self.next_patient_number,
            "next_queue_order": self.next_queue_order,
            "patients": [p.to_dict() for p in self.patients.values()],
        }
        temp_path = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self.storage_path)

    def _max_patient_number(self) -> int:
        numbers: list[int] = []
        for patient_id in self.patients:
            if patient_id.startswith("P") and patient_id[1:].isdigit():
                numbers.append(int(patient_id[1:]))
        return max(numbers, default=0)

    def _rebuild_indexes_and_queues(self) -> None:
        self.triage_heap = []
        self.room_queues = {room: deque() for room in ROOMS}
        self.patients_by_severity = {s: set() for s in SEVERITIES}
        waiting = sorted(
            (p for p in self.patients.values() if p.status == "Waiting"),
            key=lambda p: p.queue_order,
        )
        for patient in self.patients.values():
            if patient.severity in self.patients_by_severity:
                self.patients_by_severity[patient.severity].add(patient.patient_id)
        for patient in waiting:
            self.room_queues.setdefault(patient.assigned_room, deque()).append(patient.patient_id)
            heapq.heappush(
                self.triage_heap,
                (SEVERITY_RANK[patient.severity], patient.queue_order,
                 patient.patient_id, patient.queue_version),
            )

    # ---------- Registration and indexes ----------
    def register_patient(
        self,
        name: str,
        age: int,
        sex: str,
        chief_complaint: str,
        severity: str,
    ) -> Patient:
        name = " ".join((name or "").split())
        complaint = " ".join((chief_complaint or "").split())
        if not name:
            raise TriageError("Patient name is required.")
        if not isinstance(age, int) or not 0 <= age <= 120:
            raise TriageError("Age must be a whole number between 0 and 120.")
        if sex not in {"Female", "Male", "Other", "Prefer not to say"}:
            raise TriageError("Select a valid demographic option.")
        if not complaint:
            raise TriageError("Chief complaint is required.")
        if severity not in SEVERITY_RANK:
            raise TriageError("Select a valid severity level.")

        patient_id = f"P{self.next_patient_number:06d}"
        self.next_patient_number += 1
        patient = Patient(
            patient_id=patient_id,
            name=name,
            age=age,
            sex=sex,
            chief_complaint=complaint,
            severity=severity,
            arrival_time=now_iso(),
            assigned_room=ROOM_FOR_SEVERITY[severity],
            queue_order=self.next_queue_order,
            queue_version=0,
        )
        self.next_queue_order += 1
        patient.action_history.append(self._action("Registered", f"Severity set to {severity}; routed to {patient.assigned_room}."))
        self.patients[patient_id] = patient
        self.patients_by_severity[severity].add(patient_id)
        self.room_queues[patient.assigned_room].append(patient_id)
        heapq.heappush(
            self.triage_heap,
            (SEVERITY_RANK[severity], patient.queue_order, patient_id, patient.queue_version),
        )
        self.save()
        return patient

    def get_patient(self, patient_id: str) -> Patient | None:
        """Expected O(1) dictionary lookup by ID."""
        return self.patients.get((patient_id or "").strip().upper())

    def find_by_severity(self, severity: str, include_discharged: bool = True) -> list[Patient]:
        """Use the inverted severity index instead of scanning every patient."""
        if severity not in self.patients_by_severity:
            return []
        records = [self.patients[pid] for pid in self.patients_by_severity[severity] if pid in self.patients]
        if not include_discharged:
            records = [p for p in records if p.status != "Discharged"]
        return sorted(records, key=lambda p: (p.queue_order, p.patient_id))

    def search(self, query: str = "", severity: str = "All", status: str = "All") -> list[Patient]:
        query = (query or "").strip().casefold()
        if severity != "All" and severity in self.patients_by_severity:
            candidates = (self.patients[pid] for pid in self.patients_by_severity[severity] if pid in self.patients)
        else:
            candidates = iter(self.patients.values())
        results = []
        for patient in candidates:
            if status != "All" and patient.status != status:
                continue
            if query and query not in patient.patient_id.casefold() and query not in patient.name.casefold():
                continue
            results.append(patient)
        return sorted(results, key=lambda p: (SEVERITY_RANK[p.severity], p.queue_order))

    # ---------- Queue operations ----------
    def waiting_count(self, room: str | None = None) -> int:
        if room is not None:
            return sum(1 for p in self.room_waiting(room))
        return sum(p.status == "Waiting" for p in self.patients.values())

    def room_waiting(self, room: str) -> list[Patient]:
        """Return live valid entries for a room's FIFO deque; remove stale IDs."""
        if room not in self.room_queues:
            return []
        queue = self.room_queues[room]
        live: list[Patient] = []
        for patient_id in list(queue):
            patient = self.patients.get(patient_id)
            if patient is None or patient.status != "Waiting" or patient.assigned_room != room:
                try:
                    queue.remove(patient_id)
                except ValueError:
                    pass
                continue
            live.append(patient)
        return live

    def priority_waiting(self) -> list[Patient]:
        """Return valid heap entries in priority order without mutating the heap."""
        valid: list[tuple[int, int, str, int]] = []
        for entry in self.triage_heap:
            rank, order, patient_id, version = entry
            patient = self.patients.get(patient_id)
            if (
                patient is not None and patient.status == "Waiting"
                and patient.queue_version == version
                and SEVERITY_RANK[patient.severity] == rank
            ):
                valid.append(entry)
        valid.sort()
        return [self.patients[entry[2]] for entry in valid]

    def call_next_urgent(self) -> Patient | None:
        """Pop the highest-priority live patient from the min-heap."""
        while self.triage_heap:
            rank, order, patient_id, version = heapq.heappop(self.triage_heap)
            patient = self.patients.get(patient_id)
            if (
                patient is None or patient.status != "Waiting"
                or patient.queue_version != version
                or SEVERITY_RANK[patient.severity] != rank
            ):
                continue  # lazy deletion: stale queue record
            self._remove_from_room_queue(patient.assigned_room, patient_id)
            patient.status = "In Treatment"
            patient.queue_version += 1
            self.add_action(patient_id, "Called for treatment", f"Called from triage priority queue to {patient.assigned_room}.", save=False)
            self.save()
            return patient
        return None

    def call_next_from_room(self, room: str) -> Patient | None:
        """Serve the front of a room's deque (FIFO within that room)."""
        if room not in self.room_queues:
            raise TriageError("Unknown room.")
        queue = self.room_queues[room]
        while queue:
            patient_id = queue.popleft()
            patient = self.patients.get(patient_id)
            if patient is None or patient.status != "Waiting" or patient.assigned_room != room:
                continue
            patient.status = "In Treatment"
            patient.queue_version += 1
            self.add_action(patient_id, "Called for treatment", f"Called from {room} room queue (FIFO).", save=False)
            self.save()
            return patient
        return None

    def update_severity(self, patient_id: str, new_severity: str) -> Patient:
        patient = self._require_patient(patient_id)
        if patient.status != "Waiting":
            raise TriageError("Severity can only be changed while the patient is waiting.")
        if new_severity not in SEVERITY_RANK:
            raise TriageError("Select a valid severity level.")
        if patient.severity == new_severity:
            return patient
        old_severity = patient.severity
        old_room = patient.assigned_room
        self.patients_by_severity[old_severity].discard(patient.patient_id)
        self._remove_from_room_queue(old_room, patient.patient_id)
        patient.severity = new_severity
        patient.assigned_room = ROOM_FOR_SEVERITY[new_severity]
        patient.queue_order = self.next_queue_order
        self.next_queue_order += 1
        patient.queue_version += 1
        self.patients_by_severity[new_severity].add(patient.patient_id)
        self.room_queues[patient.assigned_room].append(patient.patient_id)
        heapq.heappush(
            self.triage_heap,
            (SEVERITY_RANK[new_severity], patient.queue_order, patient.patient_id, patient.queue_version),
        )
        self.add_action(
            patient.patient_id,
            "Severity updated",
            f"Changed from {old_severity} to {new_severity}; routed to {patient.assigned_room}.",
            save=False,
        )
        self.save()
        return patient

    def add_action(self, patient_id: str, action: str, details: str = "", save: bool = True) -> Patient:
        patient = self._require_patient(patient_id)
        action = " ".join((action or "").split())
        if not action:
            raise TriageError("Action description is required.")
        patient.action_history.append(self._action(action, details))  # push onto stack
        if save:
            self.save()
        return patient

    def mark_discharged(self, patient_id: str, discharge_note: str = "") -> Patient:
        patient = self._require_patient(patient_id)
        if patient.status == "Discharged":
            raise TriageError("This patient is already discharged.")
        if patient.status == "Waiting":
            self._remove_from_room_queue(patient.assigned_room, patient.patient_id)
        patient.status = "Discharged"
        patient.queue_version += 1
        details = discharge_note.strip() or "Patient marked as discharged in the academic demo."
        self.add_action(patient_id, "Discharged", details, save=False)
        self.save()
        return patient

    def _remove_from_room_queue(self, room: str, patient_id: str) -> None:
        queue = self.room_queues.get(room)
        if queue is None:
            return
        try:
            queue.remove(patient_id)
        except ValueError:
            pass

    def _require_patient(self, patient_id: str) -> Patient:
        patient = self.get_patient(patient_id)
        if patient is None:
            raise TriageError(f"No patient found with ID {patient_id!r}.")
        return patient

    @staticmethod
    def _action(action: str, details: str = "") -> dict[str, str]:
        return {"timestamp": now_iso(), "action": action, "details": details}

    # ---------- Demonstration / reporting helpers ----------
    def add_demo_patients(self) -> list[Patient]:
        """Insert clearly fictional cases to help demonstrate the application."""
        examples = [
            ("Demo Patient A", 34, "Prefer not to say", "Sample complaint A", "Critical"),
            ("Demo Patient B", 52, "Female", "Sample complaint B", "High"),
            ("Demo Patient C", 21, "Male", "Sample complaint C", "Moderate"),
            ("Demo Patient D", 67, "Female", "Sample complaint D", "Low"),
            ("Demo Patient E", 9, "Prefer not to say", "Sample complaint E", "Moderate"),
        ]
        created = []
        for name, age, sex, complaint, severity in examples:
            created.append(self.register_patient(name, age, sex, complaint, severity))
        return created

    def clear_all(self) -> None:
        """Clear in-memory demo records and the local JSON data file."""
        self.patients.clear()
        self.next_patient_number = 1
        self.next_queue_order = 1
        self._rebuild_indexes_and_queues()
        self.save()

    def summary(self) -> dict[str, int]:
        return {
            "Total patients": len(self.patients),
            "Waiting": sum(p.status == "Waiting" for p in self.patients.values()),
            "In treatment": sum(p.status == "In Treatment" for p in self.patients.values()),
            "Discharged": sum(p.status == "Discharged" for p in self.patients.values()),
            "Critical waiting": sum(p.status == "Waiting" and p.severity == "Critical" for p in self.patients.values()),
        }

    def export_dict(self) -> dict[str, Any]:
        return {
            "generated_at": now_iso(),
            "patients": [p.to_dict() for p in self.patients.values()],
        }
