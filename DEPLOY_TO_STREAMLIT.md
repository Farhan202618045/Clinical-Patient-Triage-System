# Deploy Clinical Patient Triage System to Streamlit Community Cloud

## Files to upload to the GitHub repository

Upload the contents of this folder to the **root** of a GitHub repository. The repository root must contain:

- `app.py`
- `triage_system.py`
- `requirements.txt`
- `.gitignore`
- `data/.gitkeep`
- `.streamlit/config.toml`
- `tests/test_triage_system.py` (optional for runtime, useful for coursework)

Do not upload `.venv/`, `data/patients.json`, real patient information, passwords, or secrets.

## Deploy

1. Push these files to the `main` branch of a GitHub repository. A public repository is easiest for a shareable class demonstration.
2. Sign in at https://share.streamlit.io/ using the GitHub account that owns or has admin access to the repository.
3. Choose **Create app** / **Yup, I have an app**.
4. Select your repository, branch `main`, and main file path `app.py`.
5. Optionally set a custom app subdomain, such as `clinical-triage-demo` if available.
6. Open **Advanced settings** and choose a supported Python 3.12 version if a version must be selected. No secrets are required by this project.
7. Click **Deploy** and monitor the build logs. Once ready, open the `*.streamlit.app` URL.

## Important data limitation

The app currently stores patient records in `data/patients.json` on the app's local filesystem. Streamlit Community Cloud is suitable for a fictional demonstration, but this local file is not a reliable persistent database for a hosted application and may be lost when the app is restarted, rebuilt, or moved. Multiple visitors may also share the same app instance/data. Use fictional test records only. Do not enter personal or real patient data. For durable hosted storage, integrate a database such as SQLite on persistent hosting or a managed database service, and add authentication and access controls first.

## Updating the app

Commit and push code changes to the configured branch. Community Cloud detects the repository update and redeploys the app.
