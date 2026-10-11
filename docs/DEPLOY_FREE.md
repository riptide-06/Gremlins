# Putting it on the internet for free (judging day)

Two ways, both free, both keep the real sign-in and the judge link working.

## A. Right now, from your laptop (30 seconds): a Cloudflare quick tunnel

The server already runs on your Mac. A quick tunnel gives it a public https address with no
account and no card. It lives as long as your laptop and the tunnel do.

```sh
brew install cloudflared                                  # once
cloudflared tunnel --url http://127.0.0.1:8080            # prints https://<random>.trycloudflare.com, keep it running
```

Then restart the server with that address as its public URL (the site's same-origin checks
and the Campus Cubbies pairing need the real one):

```sh
DEMO_TOKEN=judge LOCAL_HTTP=1 PUBLIC_URL=https://<random>.trycloudflare.com \
  uv run uvicorn gremlin_app:app --port 8080 --no-access-log
```

Share `https://<random>.trycloudflare.com/demo?token=judge` with the judges. Pick a longer
`DEMO_TOKEN` if the link will be on a slide.

## B. Durable, still free: a Hugging Face Docker Space (10 minutes)

No card. Hugging Face builds `Dockerfile.gremlins` and hosts it at a direct URL; secrets stay in
the Space. You need a Hugging Face account and a write token (https://huggingface.co/settings/tokens).

```sh
HF_SPACE=<your-hf-username>/gremlins HF_TOKEN=hf_... deploy/hf-space.sh
```

The script creates the Space, copies your model keys from `.env` into Space secrets (never
printed), generates `SESSION_SECRET` and a judge `DEMO_TOKEN`, sets `PUBLIC_URL` and
`CUBBY_URL`, and pushes the files. It prints the site URL and the judge link. Open the direct
`https://<user>-gremlins.hf.space` URL: the Space page embeds it in a frame, which the site
refuses on purpose (`frame-ancestors 'none'`).

Limits worth knowing: the filesystem is ephemeral (judge-mode boxes reset when the Space
restarts; a signed-in student's box lives in their own Drive, so nothing of theirs is lost),
and a free Space goes to sleep after a long idle stretch and takes about a minute to wake.
Re-run the script to redeploy after a commit.

## Later, when a few dollars are fine: Cloud Run

`docs/DEPLOY_GREMLINS.md`. Same image, one warm instance, no sleeping.
