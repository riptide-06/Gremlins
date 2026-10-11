# Sunday morning: from this checkout to the judges

Branch `night2-boxes-gremlins`. Nothing here touches `main`.

## 1. Get the overnight changes in (2 minutes)

If `git log -1` does not say "overnight" yet, the bundle is next to the repo:

```sh
cd ~/Documents/Hack.Dev/Gremlins
tar xzf ../night2-sync.tgz                                  # 18 files, see git status
uv run pytest -q                                            # expect 146 passed
git add -A && git commit -m "overnight: ..."                # or let Claude Code do it
rm ../night2-sync.tgz ../gremlins-snapshot.tgz
```

## 2. Live check with your keys (5 minutes, the replay cache is cold for the new prompt)

```sh
uv run preflight.py --live                                  # one call per model; a 404 means retire that model id
uv run demo.py                                              # c1 CONVERGED, p1 CONVERGED+override, e1 ESCALATED,
                                                            # a1 ASK -> CONVERGED, d1 ASK -> DISPUTED (or CONVERGED by precedence), e2 ESCALATED
uv run eval.py                                              # ten cases; copy the table into docs/EVAL.md and the README number if it moved
```

What changed in the mechanism overnight (so you can explain any shift): a department's position
is now the option it recommends (first in its list), its authority is the rule it names as
`basis` (read from the box), `units` means total load, and the college's working-student
practice (F-13) says "stay at or below 19". d1 is a dispute on purpose now, not by accident.

## 3. The real student flow (you, your UCSC account, 3 minutes)

```sh
DEMO_TOKEN=judge LOCAL_HTTP=1 PUBLIC_URL=http://127.0.0.1:8080 uv run uvicorn gremlin_app:app --port 8080 --no-access-log
```

Open http://127.0.0.1:8080, press *Continue with UCSC Google*, approve on the Campus Cubbies tab,
land on Welcome. Then: My Cubby shows "in your Drive · gremlin-student.md"; fill `units`, `hours`,
`visa`, `college`, `major`; ask c1; check Google Drive > My Cubby > `gremlin-student.md` has the
session lines. `/mcp` with the Campus Cubbies token works the same way (Bring your own agent page).

Judge link on the same server: http://127.0.0.1:8080/demo?token=judge

## 4. Put it on the internet (free: docs/DEPLOY_FREE.md; paid: docs/DEPLOY_GREMLINS.md), then push

```sh
git push -u origin night2-boxes-gremlins
```

## 5. Record

docs/VIDEO.md (90 s shot list, honesty rules), then docs/DEVPOST.md, then rehearse docs/PITCH.md.
