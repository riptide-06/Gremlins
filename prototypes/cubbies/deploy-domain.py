# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Deploy only the cubby domain Worker with the explicitly verified BayLeaf profile."""
import json
import os
from pathlib import Path
import subprocess

ACCOUNT = "1a49fb69291d42e23c4ed4dcffce5bbc"
ZONE = "2cdc9d687b938704965a00188f8877ad"

if __name__ == "__main__":
    env = dict(os.environ, CLOUDFLARE_ACCOUNT_ID=ACCOUNT)
    env.pop("CLOUDFLARE_API_TOKEN", None)
    # A real API call refreshes cf OAuth; cached whoami alone is insufficient.
    zones = json.loads(subprocess.check_output(
        ["cf", "zones", "list", "--profile", "ucsc", "--name", "bayleaf.dev"], env=env, text=True))
    assert any(z["id"] == ZONE and z["account"]["id"] == ACCOUNT and z["status"] == "active" for z in zones)
    profile = Path.home() / "Library/Preferences/cloudflare/config/ucsc.json"
    env["CLOUDFLARE_API_TOKEN"] = json.loads(profile.read_text())["oauth_token"]
    subprocess.run(["npx", "--yes", "wrangler@4.64.0", "deploy", "--config",
                    str(Path(__file__).with_name("wrangler.jsonc").resolve())], env=env, check=True)
