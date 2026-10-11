# Campus Cubbies

An **A2A 1.0** service for permissioned campus correspondence and personal Google
Drive tools for people's agents. The server is mechanical: the caller supplies
reasoning. A2A is the showcased interface for this Cisco-sponsored hackathon.
Hackathon teammates: Adam Smith and Tarun Nagaraju, October 2026.

## Prototype index

| Folder | Prototype | Status |
| --- | --- | --- |
| [cubbies](prototypes/cubbies/) | Campus Cubbies, with Google Drive integration | Active pilot at https://cubby.bayleaf.dev |
| [a2a-echo](prototypes/a2a-echo/) | Original no-memory A2A echo | Historical |
| [markdown-memory](prototypes/markdown-memory/) | Permissioned local Markdown memory | Historical |
| [firestore](prototypes/firestore/) | Google login and Firestore-backed memory | Historical |
| [slim](prototypes/slim/) | Isolated A2A-over-SLIM gateway and client | Historical |

Historical source and documentation are retained as development records;
their original commands, deployment claims, and sibling-file assumptions may
no longer apply. Only Campus Cubbies is the active runnable target.

## Campus Cubbies development

Use the shared root `pyproject.toml` and `uv.lock`:

```sh
uv sync
uv run pytest -q
LOCAL_HTTP=1 uv run uvicorn cloud_app:app --app-dir prototypes/cubbies --port 8080 --no-access-log
```

The root Dockerfile and upload allowlists package `prototypes/cubbies/`.
See [current configuration, security boundaries, and deployment setup](prototypes/cubbies/README.md).
Agent connection instructions are canonical in [SKILL.md](prototypes/cubbies/SKILL.md);
current live evidence is in [DEPLOYMENT.md](prototypes/cubbies/DEPLOYMENT.md).
Earlier deployment records in `prototypes/firestore/` are historical, not current setup instructions.
