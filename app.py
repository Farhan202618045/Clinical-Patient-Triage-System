from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from triage_system import (
    ROOMS,
    SEVERITIES,
    VALID_STATUSES,
    TriageError,
    TriageManager,
)

APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "data" / "patients.json"

st.set_page_config(
    page_title="Clinical Patient Triage System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_manager() -> TriageManager:
    if "triage_manager" not in st.session_state:
        st.session_state.triage_manager = TriageManager(DATA_FILE)
    return st.session_state.triage_manager


manager = get_manager()

st.title("Clinical Patient Triage System")
st.caption("Academic demonstration app · fictional/sample data only · not for clinical use")

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Select a page",
        ["Dashboard", "Register Patient", "Room Queues", "Patient Search", "Treatment & History", "About & Data Structures"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Severity is selected by the staff user. The app does not diagnose or recommend clinical severity.")


def patient_row(p):
    return {
        "Patient ID": p.patient_id,
        "Name": p.name,
        "Age": p.age,
        "Severity": p.severity,
        "Room": p.assigned_room,
        "Status": p.status,
        "Arrival": p.arrival_time.replace("T", " "),
        "Chief complaint": p.chief_complaint,
    }


def show_error(message: str) -> None:
    st.error(message)


def show_patient_card(p) -> None:
    st.subheader(f"{p.patient_id} — {p.name}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Severity", p.severity)
    c2.metric("Status", p.status)
    c3.metric("Assigned room", p.assigned_room)
    c4.metric("Age", p.age)
    st.write(f"**Chief complaint:** {p.chief_complaint}")
    st.write(f"**Registered:** {p.arrival_time}")


if page == "Dashboard":
    st.header("Emergency Department Overview")
    summary = manager.summary()
    metric_columns = st.columns(5)
    for col, label in zip(metric_columns, summary):
        col.metric(label, summary[label])

    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Waiting list — severity priority")
        waiting = manager.priority_waiting()
        if waiting:
            st.dataframe([patient_row(p) for p in waiting], use_container_width=True, hide_index=True)
        else:
            st.info("No patients are currently waiting. Register a patient or load fictional demo data.")
        if st.button("Call next highest-priority patient", type="primary", disabled=not waiting, use_container_width=True):
            try:
                called = manager.call_next_urgent()
                if called:
                    st.success(f"Called {called.patient_id} ({called.severity}) to {called.assigned_room}.")
                    st.rerun()
                else:
                    st.info("There are no waiting patients.")
            except TriageError as exc:
                show_error(str(exc))

    with right:
        st.subheader("Room status")
        room_data = []
        for room in ROOMS:
            room_data.append({"Room": room, "Waiting": len(manager.room_waiting(room))})
        st.dataframe(room_data, use_container_width=True, hide_index=True)
        st.subheader("Quick actions")
        if st.button("Load fictional demo patients", use_container_width=True, disabled=bool(manager.patients)):
            try:
                new_patients = manager.add_demo_patients()
                st.success(f"Added {len(new_patients)} fictional demo patients.")
                st.rerun()
            except TriageError as exc:
                show_error(str(exc))
        if manager.patients:
            st.download_button(
                "Export all records as JSON",
                data=json.dumps(manager.export_dict(), indent=2, ensure_ascii=False),
                file_name="triage_records_export.json",
                mime="application/json",
                use_container_width=True,
            )
            with st.expander("Danger zone — clear local demo records"):
                st.warning("This deletes all saved patient records from this project's local JSON file.")
                confirm_clear = st.checkbox("I understand this permanently clears the local demo dataset.", key="confirm_clear")
                if st.button("Clear all records", disabled=not confirm_clear, use_container_width=True):
                    manager.clear_all()
                    st.success("All records cleared.")
                    st.rerun()

    st.divider()
    st.caption("Priority order: Critical → High → Moderate → Low. Patients at the same severity are ordered by registration time.")

elif page == "Register Patient":
    st.header("Register a Patient")
    st.write("Registration creates a unique ID, appends a registration action to the history stack, and routes the patient to a room based on the staff-entered severity.")
    with st.form("register_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Patient name *", placeholder="Use fictional data for demos")
            age = st.number_input("Age *", min_value=0, max_value=120, step=1, value=30)
            sex = st.selectbox("Sex / demographic option", ["Prefer not to say", "Female", "Male", "Other"])
        with col2:
            severity = st.selectbox("Severity assigned by staff *", list(SEVERITIES))
            complaint = st.text_area("Chief complaint *", placeholder="Brief note (avoid real sensitive information)", height=100)
            st.info("Automatic room route: Critical → Resuscitation; High → Emergency; Moderate/Low → General.")
        submitted = st.form_submit_button("Register patient", type="primary", use_container_width=True)
    if submitted:
        try:
            patient = manager.register_patient(name, int(age), sex, complaint, severity)
            st.success(f"Patient registered. New patient ID: {patient.patient_id}. Assigned room: {patient.assigned_room}.")
            st.info("Save the patient ID for instant lookup on the Patient Search page.")
        except TriageError as exc:
            show_error(str(exc))

elif page == "Room Queues":
    st.header("Live Room Queues")
    st.write("Each room uses a deque (double-ended queue) to serve patients in first-in, first-out order within that room.")
    room_tabs = st.tabs(list(ROOMS))
    for room, tab in zip(ROOMS, room_tabs):
        with tab:
            waiting = manager.room_waiting(room)
            st.metric("Patients waiting", len(waiting))
            if waiting:
                st.dataframe([patient_row(p) for p in waiting], use_container_width=True, hide_index=True)
            else:
                st.info(f"No patients are waiting for the {room} room.")
            if st.button(f"Call next from {room}", key=f"call_{room}", type="primary", disabled=not waiting):
                try:
                    called = manager.call_next_from_room(room)
                    if called:
                        st.success(f"Called {called.patient_id} — {called.name}.")
                        st.rerun()
                except TriageError as exc:
                    show_error(str(exc))

elif page == "Patient Search":
    st.header("Patient Search")
    st.write("Search by patient ID or name, or filter by severity and status. Patient ID lookup uses a dictionary keyed by ID (expected O(1) average lookup).")
    search_col, severity_col, status_col = st.columns([2, 1, 1])
    with search_col:
        query = st.text_input("Patient ID or name", placeholder="For example: P000001 or Demo Patient A")
    with severity_col:
        severity_filter = st.selectbox("Severity filter", ["All", *SEVERITIES])
    with status_col:
        status_filter = st.selectbox("Status filter", ["All", *VALID_STATUSES])
    results = manager.search(query, severity_filter, status_filter)
    st.caption(f"{len(results)} matching record(s)")
    if results:
        st.dataframe([patient_row(p) for p in results], use_container_width=True, hide_index=True)
    else:
        st.info("No matching records. Check the ID, name, or filters.")

    st.divider()
    st.subheader("Direct lookup by patient ID")
    direct_id = st.text_input("Enter exact patient ID", placeholder="P000001", key="direct_patient_id")
    if st.button("Find patient", type="primary"):
        found = manager.get_patient(direct_id)
        if found:
            st.session_state["selected_patient_id"] = found.patient_id
            st.success("Patient record found.")
            show_patient_card(found)
            st.write("Use the Treatment & History page to add an action, update severity (while waiting), or discharge the patient.")
        else:
            show_error("Patient ID was not found.")

elif page == "Treatment & History":
    st.header("Treatment Actions and Medical History")
    patient_id_input = st.text_input("Patient ID", value=st.session_state.get("selected_patient_id", ""), placeholder="P000001")
    patient = manager.get_patient(patient_id_input)
    if patient:
        show_patient_card(patient)
        st.divider()
        action_tab, triage_tab, discharge_tab, history_tab = st.tabs(["Add action", "Update severity", "Discharge", "Action history stack"])
        with action_tab:
            with st.form("action_form", clear_on_submit=True):
                action = st.selectbox("Action type", ["Initial assessment", "Vitals recorded", "Doctor review", "Investigation ordered", "Treatment started", "Treatment updated", "Observation note", "Other"])
                details = st.text_area("Details", placeholder="Use fictional, non-identifying demo details")
                submitted = st.form_submit_button("Push action onto history stack", type="primary")
            if submitted:
                try:
                    manager.add_action(patient.patient_id, action, details)
                    st.success("Action added to the top of the patient's history stack.")
                    st.rerun()
                except TriageError as exc:
                    show_error(str(exc))
        with triage_tab:
            if patient.status != "Waiting":
                st.info("Severity can only be updated while the patient is waiting.")
            else:
                with st.form("severity_update_form"):
                    new_severity = st.selectbox("New staff-assigned severity", list(SEVERITIES), index=list(SEVERITIES).index(patient.severity))
                    update_submitted = st.form_submit_button("Update severity and room route")
                if update_submitted:
                    try:
                        old_severity = patient.severity
                        updated = manager.update_severity(patient.patient_id, new_severity)
                        st.success(f"Severity is now {updated.severity}; room route: {updated.assigned_room}.")
                        st.rerun()
                    except TriageError as exc:
                        show_error(str(exc))
        with discharge_tab:
            if patient.status == "Discharged":
                st.info("This patient is already marked as discharged.")
            else:
                with st.form("discharge_form"):
                    note = st.text_area("Discharge note", placeholder="Optional academic demo note")
                    discharge_submitted = st.form_submit_button("Mark as discharged", type="primary")
                if discharge_submitted:
                    try:
                        manager.mark_discharged(patient.patient_id, note)
                        st.success("Patient marked as discharged and discharge action recorded.")
                        st.rerun()
                    except TriageError as exc:
                        show_error(str(exc))
        with history_tab:
            st.write("The history is stored as a list-backed stack: new actions are pushed with `append()`, and the top/latest action is the last item.")
            history = list(reversed(patient.action_history))
            if history:
                st.dataframe(history, use_container_width=True, hide_index=True)
            else:
                st.info("No actions have been recorded.")
            if patient.action_history:
                st.info(f"Current stack top: {patient.action_history[-1]['action']} at {patient.action_history[-1]['timestamp']}.")
    elif patient_id_input.strip():
        st.warning("No patient found with that ID.")
    else:
        st.info("Enter a patient ID. You can also select a patient from the Patient Search page first.")

elif page == "About & Data Structures":
    st.header("Design and Data-Structure Justification")
    st.write("The structures below are integrated into the workflows rather than added only to satisfy a requirement.")
    st.subheader("1. Dictionary — patient records")
    st.code("patients: dict[str, Patient]\npatient = patients.get(patient_id)", language="python")
    st.write("Each unique patient ID maps directly to a patient object. This supports expected O(1) average exact-ID lookup and avoids repeatedly scanning every record.")
    st.subheader("2. Min-heap / priority queue — severity-first triage")
    st.code("(severity_rank, arrival_order, patient_id, queue_version)", language="python")
    st.write("The smallest severity rank is served first: Critical, High, Moderate, Low. Arrival order breaks ties fairly. Insertions and removals take O(log n) time; retrieving the top valid item is O(1) before stale-entry cleanup.")
    st.subheader("3. Deque — room-specific FIFO waiting queues")
    st.code("room_queues['General'] = deque([...])\nnext_id = room_queues['General'].popleft()", language="python")
    st.write("Each room has its own deque. Appending a new arrival and removing the front of the queue are O(1). The general room can contain Moderate and Low cases, following FIFO after routing.")
    st.subheader("4. Dictionary of sets — severity index")
    st.code("patients_by_severity['Critical'] = {'P000001', ...}", language="python")
    st.write("This inverted index allows the app to identify records for a severity without scanning the entire patient dictionary. The index is updated when severity changes.")
    st.subheader("5. List-backed stack — treatment action history")
    st.code("patient.action_history.append(action)  # push\nlatest = patient.action_history[-1]  # peek", language="python")
    st.write("Actions are appended chronologically. The most recent action is at the top of the stack and can be shown first. This provides a simple auditable history of workflow events.")
    st.subheader("Memory and persistence")
    st.write("Patient objects and indexes are held in memory while the app runs. A compact JSON snapshot is written to `data/patients.json` after changes so local records persist across restarts. Queue indexes are rebuilt from saved patient records at startup rather than duplicated in the file.")
    st.subheader("Important limitation")
    st.warning("This project is an academic workflow simulation. It does not implement a validated clinical triage protocol, clinical decision support, authentication, encryption, or regulatory compliance. Do not enter real patient data or use it for care decisions.")
