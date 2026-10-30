
# Clinical Patient Triage System

A local Python web application for a Data Structures and Algorithms project. It simulates fictional patient registration, staff-assigned severity routing, global priority selection, room-specific FIFO queues, patient search, treatment/workflow action histories, severity updates, discharge tracking, and local JSON persistence.

> **Academic demo only:** use fictional/sample records. This is not a validated clinical triage protocol, medical device, or tool for real patient-care decisions. Severity is selected by the staff user; the software does not diagnose patients.

## Main features

- Register patients and generate IDs such as `P000001`.
- Route staff-assigned severity: Critical → Resuscitation, High → Emergency, Moderate/Low → General.
- Show the global waiting list in severity order: Critical, High, Moderate, Low; earlier queue order breaks ties.
- Call the next patient by global priority or by room FIFO order.
- Search by ID or name; filter by severity and status.
- Update severity while the patient is Waiting; move the room queue and indexes.
- Add action-history entries, view the latest action first, and mark patients as Discharged.
- Save records locally in `data/patients.json`; rebuild in-memory indexes and waiting queues at startup.
- Export all records as JSON.

## Data structures and why they fit

| Data structure | Implementation | Purpose | Complexity / important detail |
|---|---|---|---|
| Dictionary | `patients: dict[str, Patient]` | Exact patient-ID lookup | Expected O(1) average lookup. |
| Min-heap | `triage_heap` via `heapq` | Select the most severe waiting patient; arrival order breaks ties | O(log H) push/pop; O(1) raw root access. |
| Deque | `room_queues[room]` | FIFO waiting line for each room | O(1) append/popleft; arbitrary `remove(value)` is O(n). |
| Dictionary of sets | `patients_by_severity` | Find patient IDs for a severity filter | Expected O(1) set updates; returning/sorting k matches takes O(k log k). |
| List-backed stack | `Patient.action_history` | Push actions and inspect latest action | Amortized O(1) append and O(1) top lookup. |

The heap tuple is `(severity_rank, queue_order, patient_id, queue_version)`. Queue-version checks implement lazy deletion: outdated entries are skipped when encountered rather than being searched for and removed from the middle of the heap. The Dashboard priority list scans and sorts valid heap entries; it is not an O(1) heap peek. Name/partial-text search scans candidate records; exact ID lookup uses the dictionary.

## Run locally on Windows / VS Code

1. Install Python 3.10 or later.
2. Extract the ZIP and open the `clinical_patient_triage_system` folder in VS Code.
3. Open **Terminal → New Terminal**. Confirm the terminal is inside the project folder.
4. Create a virtual environment if one does not already exist:

   ```powershell
   py -m venv .venv
   ```

5. Install the project dependencies inside that environment:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

6. Run Streamlit using the environment's Python executable:

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

7. Open the Local URL printed in the terminal, usually `http://localhost:8501`. If no browser opens automatically, copy the URL into Chrome. Keep the terminal open while using the app; stop it with `Ctrl+C`.

**PowerShell note:** activation is optional. These commands avoid the PowerShell execution-policy problem that can block `.venv\Scripts\Activate.ps1`. If the virtual environment and packages are already set up, run only the Streamlit command.

## Test the core logic

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The included test suite contains seven tests covering registration/routing, priority and tie-breaking, room FIFO, severity updates, history persistence, invalid inputs, and discharge.

## Suggested demonstration flow

1. Open **Dashboard** and load fictional demo patients.
2. Show the global priority list and explain severity rank plus arrival-order tie-breaking.
3. Open **Room Queues** and call the next person from a room to demonstrate FIFO.
4. Register a fictional patient and show its generated ID and room route.
5. Use **Patient Search** to find the patient by ID.
6. Open **Treatment & History**, add two actions and show the newest action first.
7. Update severity for a patient still waiting and show the new room/index membership.
8. Discharge a patient and show that the record remains searchable but is no longer waiting.
9. Restart the app and confirm local records reload.
10. Open **About & Data Structures** to explain the implementation and limitations.

## Project files

```text
clinical_patient_triage_system/
├── app.py
├── triage_system.py
├── requirements.txt
├── README.md
├── START_HERE.txt
├── TEST_RESULTS.txt
├── data/
│   └── .gitkeep
├── tests/
│   └── test_triage_system.py
├── Clinical_Patient_Triage_System_Complete_Report_and_Viva_Guide.docx
└── Clinical_Patient_Triage_System_Complete_Report_and_Viva_Guide.pdf
```

## Limitations and possible future work

This demonstrator has no authentication, role-based access, encryption, tamper-proof audit storage, multi-user concurrency control, database server, or clinically validated triage rules. The JSON file is simple local persistence, not a transactional database. For coursework extensions, consider SQLite, stronger validation, test coverage, login/roles and backups. Any healthcare deployment would require qualified clinical governance, privacy/security engineering, and applicable regulatory review.
=======
# Clinical-Patient-Triage-System
An emergency department platform that manages daily patient registrations, live room queues, patient search records, and medical treatment action histories. The system will allow staff to route incoming patients seamlessly, track medical history steps, and look up individual records instantly based on severity or patient ID. 

