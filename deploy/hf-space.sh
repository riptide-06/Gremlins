#!/usr/bin/env sh
# Put the gremlin service on a free Hugging Face Docker Space: public URL, no card, secrets
# kept in the Space, the image built by Hugging Face from Dockerfile.gremlins.
#
#   HF_SPACE=<your-hf-username>/gremlins HF_TOKEN=hf_... deploy/hf-space.sh
#
# HF_TOKEN is a WRITE token from https://huggingface.co/settings/tokens. Model keys are read
# from .env in the repo root and sent straight to the Space's secrets; nothing is printed.
# Re-run to redeploy. The Space's direct URL is https://<user>-gremlins.hf.space (the Space
# page embeds it in a frame, which the site refuses on purpose: use the direct URL).
set -eu
: "${HF_SPACE:?set HF_SPACE=<user>/<space>}"
: "${HF_TOKEN:?set HF_TOKEN=hf_... (write token)}"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
API=https://huggingface.co/api
AUTH="Authorization: Bearer $HF_TOKEN"
OWNER=${HF_SPACE%%/*}; NAME=${HF_SPACE#*/}
HOST=$(printf '%s-%s' "$OWNER" "$NAME" | tr 'A-Z_.' 'a-z--')
PUBLIC_URL=${PUBLIC_URL:-https://$HOST.hf.space}

# 1. the Space (idempotent)
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/repos/create" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"type\":\"space\",\"name\":\"$NAME\",\"organization\":\"$OWNER\",\"sdk\":\"docker\",\"private\":false}")
case "$code" in 200|201|409) ;; *) echo "could not create the Space (HTTP $code); check HF_TOKEN is a write token and HF_SPACE is <your-username>/<name>" >&2; exit 1;; esac

# 2. secrets and variables: model keys from .env, a session secret, a judge token, the public URL
put() { # kind key value
  curl -s -o /dev/null -X POST "$API/spaces/$HF_SPACE/$1" -H "$AUTH" -H 'Content-Type: application/json' \
    -d "$(printf '{"key":"%s","value":"%s"}' "$2" "$3")"
}
for k in GROQ_API_KEY NVIDIA_NIM_API_KEY GEMINI_API_KEY; do
  v=$(grep "^$k=" "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
  [ -n "$v" ] && put secrets "$k" "$v" && echo "secret $k: set"
done
put secrets SESSION_SECRET "$(openssl rand -base64 48 | tr -d '\n=' )"
DEMO_TOKEN=${DEMO_TOKEN:-$(openssl rand -hex 12)}
put secrets DEMO_TOKEN "$DEMO_TOKEN"
put variables PUBLIC_URL "$PUBLIC_URL"
put variables CUBBY_URL "${CUBBY_URL:-https://cubby.bayleaf.dev}"
put variables GREMLIN_MODELS "${GREMLIN_MODELS:-}"

# 3. the files the image needs, Dockerfile.gremlins as the Space's Dockerfile, pushed to the Space repo
STAGE=$(mktemp -d)
cd "$ROOT"
cp gremlin_app.py box.py brain.py dept_gremlin.py wall.py advocate.py cubby_store.py mcp_server.py site.html pyproject.toml uv.lock "$STAGE/"
mkdir -p "$STAGE/docs/boxes"
cp docs/boxes/*.md "$STAGE/docs/boxes/"
rm -f "$STAGE"/docs/boxes/student-*.md "$STAGE"/docs/boxes/*.example.md
cp Dockerfile.gremlins "$STAGE/Dockerfile"
cat > "$STAGE/README.md" <<EOF
---
title: Gremlins
emoji: 👾
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 8080
pinned: false
---
Gremlins: a student-controlled advocate on Campus Cubbies. Department gremlins answer only
from their policy box and cite every claim; the student's gremlin shares the minimum, applies
precedence in code, and returns CONVERGED, DISPUTED, ESCALATED, ASK_STUDENT, or UNANSWERED.
Open the direct URL: $PUBLIC_URL
EOF
cd "$STAGE"
git init -q && git checkout -q -b main && git add -A
git -c user.name=gremlins -c user.email=gremlins@users.noreply.huggingface.co commit -qm "deploy gremlins"
git -c credential.helper= push -q -f "https://user:$HF_TOKEN@huggingface.co/spaces/$HF_SPACE" main
cd "$ROOT" && rm -rf "$STAGE"
echo
echo "pushed. Hugging Face is building the image now (3 to 6 minutes): https://huggingface.co/spaces/$HF_SPACE"
echo "site (direct URL):  $PUBLIC_URL"
echo "judge link:         $PUBLIC_URL/demo?token=$DEMO_TOKEN"
echo "if the direct URL differs from the one on the Space page (Embed this Space), set the PUBLIC_URL variable in the Space settings to the real one."
