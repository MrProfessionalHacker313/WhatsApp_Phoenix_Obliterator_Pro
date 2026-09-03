# WhatsApp Phoenix Obliterator Pro

A government-approved, consent-based internal operations toolkit for case intake, incident triage, abuse investigation, and evidence handling in WhatsApp environments.

This repository is structured for a lawful agency workflow and is intentionally scoped to:

- authorized case intake
- message moderation workflows
- evidence collection and redaction
- internal operations dashboards
- safe integration points with approved messaging infrastructure

Important:
- This project does not provide unauthorized access to private WhatsApp accounts.
- Use only for approved governmental investigations and internal compliance workflows.
- Ensure all deployments comply with local law, agency policy, and data protection obligations.

## Project structure

```text
WhatsApp_Phoenix_Obliterator_Pro/
├── backend/
│   ├── python_core/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── ban_engine.py
│   │   │   ├── unban_engine.py
│   │   │   ├── detector.py
│   │   │   ├── anti_forensic.py
│   │   │   └── ai_router.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── proxy_rotator.py
│   │       ├── session_pool.py
│   │       ├── cryptor.py
│   │       └── logger.py
│   └── node_whatsapp/
│       ├── server.js
│       ├── package.json
│       ├── whatsapp_client.js
│       └── multi_device.js
├── mobile_app/
│   ├── App.js
│   ├── package.json
│   └── src/
│       ├── screens/
│       └── services/
├── web_interface/
│   ├── index.html
│   ├── dashboard.html
│   └── assets/
├── installer.sh
└── README.md
```

## Quick start

```bash
chmod +x installer.sh
./installer.sh
```

Then start the API:

```bash
cd backend/python_core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

And the Node WhatsApp bridge:

```bash
cd backend/node_whatsapp
npm install
node server.js
```

## Intended usage

- authorized incident intake
- case triage workflow
- policy-based rule matching
- internal monitoring and evidence preservation
- dashboard for law-enforcement staff with secure access controls

## Security note

This repository is a starting point for internal agency tooling. Administrative access must be restricted to authorized personnel only, and all data handling must follow your organization's legal and policy requirements.
