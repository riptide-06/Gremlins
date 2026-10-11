import json, pathlib
AUDIO = json.load(open('assets/audio-data-25s.json'))
bass = [round(f['bands'][0], 3) for f in AUDIO['frames']]
rms = [round(f['rms'], 3) for f in AUDIO['frames']]
MASCOT = open('assets/mascot.svg').read().replace('role="img" ', '').replace('\n', '')
def mascot(cls):
    return MASCOT.replace('<svg ', f'<svg class="{cls}" ', 1)

HONEST = '<div class="honest">JUDGE MODE · synthetic student (Asha Rao) · prototype</div>'
SFX = [  # (id, time, file, volume)
    ('sx1', 0.15, 'impact/impactSoft_medium_001', 0.7), ('sx2', 1.15, 'impact/impactSoft_medium_004', 0.7),
    ('sx3', 3.02, 'interface/bong_001', 0.8), ('sx4', 3.02, 'impact/impactSoft_medium_004', 0.6),
    ('sx5', 5.52, 'impact/impactSoft_medium_001', 0.55),
    ('sx6', 5.77, 'casino/card-slide-1', 0.5), ('sx7', 6.02, 'casino/card-slide-1', 0.5), ('sx8', 6.27, 'casino/card-slide-1', 0.5), ('sx9', 6.52, 'casino/card-slide-1', 0.5),
    ('sx10', 7.02, 'interface/drop_001', 0.7), ('sx11', 7.52, 'interface/drop_002', 0.7),
    ('sx12', 8.02, 'impact/impactSoft_medium_001', 0.55), ('sx13', 8.52, 'casino/card-slide-1', 0.5),
    ('sx14', 10.1, 'interface/click_003', 0.9), ('sx15', 10.45, 'impact/impactSoft_medium_004', 0.6),
    ('sx16', 11.02, 'impact/impactSoft_medium_001', 0.55), ('sx17', 12.3, 'casino/card-slide-1', 0.5),
    ('sx18', 13.52, 'impact/impactSoft_medium_001', 0.55), ('sx19', 14.02, 'interface/drop_001', 0.6), ('sx20', 14.52, 'interface/drop_002', 0.6), ('sx21', 15.02, 'interface/drop_001', 0.6),
    ('sx22', 16.02, 'impact/impactSoft_medium_001', 0.7), ('sx23', 17.02, 'casino/card-slide-1', 0.5),
    ('sx24', 18.52, 'impact/impactSoft_medium_001', 0.6), ('sx25', 19.62, 'interface/drop_001', 0.6), ('sx26', 20.12, 'interface/drop_002', 0.6),
    ('sx27', 20.52, 'impact/impactSoft_medium_004', 0.6), ('sx28', 20.6, 'casino/chips-stack-1', 0.4), ('sx29', 21.52, 'impact/impactBell_heavy_000', 0.7),
    ('sx30', 22.52, 'impact/impactSoft_medium_001', 0.55), ('sx31', 23.02, 'impact/impactBell_heavy_003', 0.7),
]
DUR = {'impactSoft': 0.2, 'bong': 0.13, 'drop': 0.2, 'click': 0.05, 'card-slide': 0.6, 'chips-stack': 0.3, 'impactBell': 0.7}
def dur(f):
    return next(v for k, v in DUR.items() if k in f)
sfx_html = '\n'.join(f'<audio id="{i}" data-start="{t}" data-duration="{dur(f)}" data-track-index="{11+n}" data-volume="{v}" src="assets/sfx/{f}.ogg"></audio>' for n, (i, t, f, v) in enumerate(SFX))

html = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<title>Gremlins — brag</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face{font-family:'Sora';src:url('assets/fonts/Sora.ttf') format('truetype');font-weight:100 900;font-style:normal}
@font-face{font-family:'JetBrains Mono';src:url('assets/fonts/JetBrainsMono.ttf') format('truetype');font-weight:100 800;font-style:normal}
body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#EEEFE9;font-family:'Sora',system-ui,sans-serif;color:#151515}
#root{position:relative;width:1920px;height:1080px;overflow:hidden}
#bg{position:absolute;inset:0;background:#EEEFE9}
.scene{position:absolute;top:0;left:0;width:1920px;height:1080px;overflow:hidden;background:#EEEFE9}
#s2,#s3,#s4,#s5,#s6,#s7,#s8,#s9,#s10{opacity:0}
#s1{z-index:1}#s2{z-index:2}#s3{z-index:3}#s4{z-index:4}#s5{z-index:5}#s6{z-index:6}#s7{z-index:7}#s8{z-index:8}#s9{z-index:9}#s10{z-index:10}
.glow{position:absolute;width:1100px;height:1100px;border-radius:50%;background:radial-gradient(circle,rgba(245,78,0,.30) 0%,rgba(245,78,0,.12) 38%,rgba(245,78,0,0) 66%);pointer-events:none;will-change:transform}
.grain{position:absolute;inset:0;opacity:.18;background-image:radial-gradient(rgba(21,21,21,.35) .8px,transparent 1px);background-size:14px 14px;pointer-events:none}
.ghost{position:absolute;font-weight:800;color:#151515;opacity:.07;line-height:1;pointer-events:none;will-change:transform}
.rule{position:absolute;height:6px;background:#151515;transform-origin:left center;will-change:transform}
.h{position:absolute;font-weight:800;letter-spacing:-0.025em;line-height:1.04;will-change:transform}
.h .o{color:#D94500}
.cap{position:absolute;font-weight:500;font-size:36px;line-height:1.3;color:#151515;will-change:transform}
.mono{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace}
.chip{position:absolute;display:inline-block;font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-size:24px;font-weight:600;padding:10px 18px;border:3px solid #151515;border-radius:12px;background:#FFFFFF;color:#151515;box-shadow:5px 5px 0 #151515;will-change:transform;white-space:nowrap}
.chip.y{background:#F7A501}.chip.g{background:#B9E5A6}.chip.s{background:#DCE6FF}
.honest{position:absolute;left:60px;bottom:44px;font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-size:21px;font-weight:600;padding:10px 16px;border:3px solid #151515;border-radius:999px;background:#F7A501;color:#151515;white-space:nowrap}
.shot{position:absolute;overflow:hidden;border:3px solid #151515;border-radius:18px;box-shadow:12px 12px 0 #151515;background:#FFFFFF;will-change:transform}
.shot img{position:absolute;left:0;top:0;display:block}
.pill{position:absolute;font-weight:800;font-size:26px;letter-spacing:.04em;padding:10px 22px;border:3px solid #151515;border-radius:999px;color:#151515;white-space:nowrap;will-change:transform}
.wm{position:absolute;font-weight:800;font-size:180px;letter-spacing:-0.04em;line-height:1;will-change:transform}
.mascot{position:absolute;will-change:transform}
.cursor{position:absolute;width:46px;height:60px;z-index:50;pointer-events:none;will-change:transform}
.ripple{position:absolute;width:140px;height:140px;border-radius:50%;border:4px solid #F54E00;transform:translate(-50%,-50%) scale(0);opacity:0;pointer-events:none}
.sweep{position:absolute;height:22px;background:rgba(245,78,0,.42);border-radius:6px;transform-origin:left center;will-change:transform}
.dot{position:absolute;width:22px;height:22px;border-radius:50%;background:#F54E00;border:3px solid #151515;will-change:transform}
.num{position:absolute;font-weight:800;font-size:200px;letter-spacing:-0.04em;line-height:1;font-variant-numeric:tabular-nums;will-change:transform;transform-origin:left bottom}
.lab{position:absolute;font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-weight:600;font-size:26px;letter-spacing:.06em;text-transform:uppercase;color:#151515;will-change:transform}
.sub{position:absolute;font-weight:500;font-size:28px;color:#5A5A55;will-change:transform}
.credit{position:absolute;font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-size:21px;color:#5A5A55;line-height:1.5;will-change:transform}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-width="1920" data-height="1080" data-start="0" data-duration="25">
  <div id="bg"></div>

  <!-- 1 HOOK -->
  <div id="s1" class="scene">
    <div class="glow" style="left:-300px;top:-420px"></div>
    <div class="grain"></div>
    <div id="s1-ghost" class="ghost" data-layout-ignore style="right:60px;bottom:-140px;font-size:900px">?</div>
    <div id="s1-l1" class="h" style="left:140px;top:300px;font-size:108px;width:1700px;white-space:nowrap"><span class="o">Three</span> offices. <span class="o">Three</span> answers.</div>
    <div id="s1-l2" class="h" style="left:140px;top:520px;font-size:108px;width:1700px;white-space:nowrap">Who's actually right?</div>
    <div id="s1-rule" class="rule" style="left:140px;top:460px;width:420px"></div>
  </div>

  <!-- 2 REVEAL -->
  <div id="s2" class="scene">
    <div class="glow" style="left:-200px;top:-150px"></div>
    <div class="grain"></div>
    <div id="s2-mascot" class="mascot" style="left:150px;top:270px;width:520px;height:560px">''' + mascot('msvg') + r'''</div>
    <div id="s2-wm" class="wm" style="left:760px;top:300px">Gremlins</div>
    <svg id="s2-under" viewBox="0 0 160 14" width="860" height="70" style="position:absolute;left:770px;top:480px;overflow:visible" aria-hidden="true"><path id="s2-underpath" d="M2 9 C30 2, 50 12, 80 6 S130 2, 158 8" fill="none" stroke="#F54E00" stroke-width="4" stroke-linecap="round" vector-effect="non-scaling-stroke"></path></svg>
    <div id="s2-line" class="h" style="left:770px;top:600px;font-size:60px;font-weight:600;width:1050px;letter-spacing:-0.01em">asks all of them. <span class="o">At once.</span> With receipts.</div>
    <div id="s2-chip" class="chip" style="left:770px;top:800px;font-size:22px">hack.dev UCSC AI Hackathon · Cisco Outshift / AGNTCY · Level 3</div>
  </div>

  <!-- 3 ONE QUESTION, EVERY OFFICE -->
  <div id="s3" class="scene">
    <div class="glow" style="left:900px;top:-300px"></div>
    <div class="grain"></div>
    <div id="s3-h" class="h" style="left:90px;top:130px;font-size:76px;width:720px">One question. <span class="o">Every office.</span> At once.</div>
    <div id="s3-cap" class="cap" style="left:90px;top:520px;width:700px">Uncited claims get deleted by code before you see them.</div>
    <div id="s3-c1" class="chip" style="left:90px;top:700px">ISO</div>
    <div id="s3-c2" class="chip" style="left:206px;top:700px">CMPM</div>
    <div id="s3-c3" class="chip" style="left:352px;top:700px">COLLEGE</div>
    <div id="s3-c4" class="chip" style="left:544px;top:700px">FINAID</div>
    <div id="s3-f1" class="chip" style="left:90px;top:790px;background:#EEEFE9">F-01</div>
    <div id="s3-f2" class="chip" style="left:216px;top:790px;background:#EEEFE9">F-13</div>
    <div id="s3-shot" class="shot" data-layout-allow-overflow style="left:860px;top:110px;width:980px;height:830px"><img src="assets/shots/c1-thread.png" alt="" style="width:980px;transform:translate(0,-20px)"></div>
    ''' + HONEST + r'''
  </div>

  <!-- 4 YOUR DATA STAYS YOURS -->
  <div id="s4" class="scene">
    <div class="glow" style="left:1100px;top:400px"></div>
    <div class="grain"></div>
    <div id="s4-h" class="h" style="left:740px;top:100px;font-size:72px;width:1100px">Your data <span class="o">stays yours.</span></div>
    <div id="s4-cap" class="cap" style="left:740px;top:200px;width:1080px">Name and email never leave. It asks you first, one field, one office.</div>
    <div id="s4-grid" class="shot" data-layout-allow-overflow style="left:80px;top:100px;width:560px;height:820px"><img src="assets/shots/perm-table.png" alt="" style="width:560px;transform:translate(0,0)"></div>
    <div id="s4-ask" class="shot" data-layout-allow-overflow style="left:740px;top:330px;width:1100px;height:560px"><img src="assets/shots/a1-ask-thread.png" alt="" style="width:1100px;transform:translate(0,-100px)"></div>
    <div id="s4-ans" class="shot" data-layout-allow-overflow style="left:740px;top:330px;width:1100px;height:560px;opacity:0"><img src="assets/shots/a1-thread.png" alt="" style="width:1100px;transform:translate(0,-520px)"></div>
    <div id="s4-rip" class="ripple" style="left:1000px;top:625px"></div>
    <svg id="s4-cursor" class="cursor" viewBox="0 0 24 32" style="left:1000px;top:625px"><path d="M2 2 L2 26 L8 20 L12 30 L16 28 L12 18 L20 18 Z" fill="#151515" stroke="#EEEFE9" stroke-width="1.5" stroke-linejoin="round"/></svg>
    ''' + HONEST + r'''
  </div>

  <!-- 5 WHEN THEY DISAGREE -->
  <div id="s5" class="scene">
    <div class="glow" style="left:400px;top:-500px"></div>
    <div class="grain"></div>
    <div id="s5-h" class="h" style="left:90px;top:80px;font-size:66px;width:1760px">When they disagree, <span class="o">nobody flips a coin.</span></div>
    <div id="s5-cap" class="cap" style="left:90px;top:175px;width:1700px;font-size:34px">Federal beats campus, and the override is written down. Equal rank? The disagreement is kept, not averaged.</div>
    <div id="s5-left" class="shot" data-layout-allow-overflow style="left:90px;top:290px;width:880px;height:640px"><img src="assets/shots/d1-thread.png" alt="" style="width:880px;transform:translate(0,-70px)"></div>
    <div id="s5-sweep" class="sweep" style="left:184px;top:704px;width:748px;height:132px;background:rgba(245,78,0,.14);border:4px solid #D94500;border-radius:12px;box-sizing:border-box"></div>
    <div id="s5-right" class="shot" data-layout-allow-overflow style="left:1010px;top:290px;width:820px;height:640px"><img src="assets/shots/p1-thread.png" alt="" style="width:820px;transform:translate(0,-120px)"></div>
    ''' + HONEST + r'''
  </div>

  <!-- 6 WATCH THEM ARGUE -->
  <div id="s6" class="scene">
    <div class="glow" style="left:-350px;top:300px"></div>
    <div class="grain"></div>
    <div id="s6-h" class="h" style="left:90px;top:70px;font-size:72px;width:1700px">Watch them argue. <span class="o">Live.</span></div>
    <div id="s6-cap" class="cap" style="left:90px;top:170px;width:1700px;font-size:34px">Type demo: and every office answers in the open. Only cited policy crosses between them, never your fields.</div>
    <div id="s6-shot" class="shot" data-layout-allow-overflow style="left:300px;top:290px;width:1320px;height:640px"><img src="assets/shots/room-thread.png" alt="" style="width:1320px;transform:translate(0,-20px)"></div>
    ''' + HONEST + r'''
  </div>

  <!-- 7 A HUMAN WHEN IT MATTERS -->
  <div id="s7" class="scene">
    <div class="glow" style="left:1000px;top:-200px"></div>
    <div class="grain"></div>
    <div id="s7-h" class="h" style="left:90px;top:70px;font-size:72px;width:1700px">A human <span class="o">when it matters.</span></div>
    <div id="s7-cap" class="cap" style="left:90px;top:170px;width:1700px;font-size:34px">Deadline in 2 days? A trigger in code, not the model, escalates it with a one-page brief.</div>
    <div id="s7-brief" class="shot" data-layout-allow-overflow style="left:1180px;top:300px;width:660px;height:620px"><img src="assets/shots/brief.png" alt="" style="width:1320px;transform:translate(-300px,-110px)"></div>
    <div id="s7-card" class="shot" data-layout-allow-overflow style="left:90px;top:290px;width:1020px;height:640px"><img src="assets/shots/e2-thread.png" alt="" style="width:1020px;transform:translate(0,-70px)"></div>
    ''' + HONEST + r'''
  </div>

  <!-- 8 BRING YOUR OWN AGENT -->
  <div id="s8" class="scene">
    <div class="glow" style="left:-300px;top:-300px"></div>
    <div class="grain"></div>
    <div id="s8-h" class="h" style="left:90px;top:70px;font-size:72px;width:1700px">Bring <span class="o">your own</span> agent.</div>
    <div id="s8-cap" class="cap" style="left:90px;top:170px;width:1400px;font-size:34px">Claude, a local model, any MCP client. Same gremlin, same wall.</div>
    <div id="s8-k1" class="chip g" style="left:1480px;top:168px">A2A</div>
    <div id="s8-k2" class="chip y" style="left:1590px;top:168px">SLIM</div>
    <div id="s8-k3" class="chip s" style="left:1710px;top:168px">MCP</div>
    <div id="s8-page" class="shot" data-layout-allow-overflow style="left:160px;top:280px;width:1600px;height:660px"><img id="s8-img" src="assets/shots/byoa.png" alt="" style="width:1600px;transform:translate(0,-215px)"></div>
    ''' + HONEST + r'''
  </div>

  <!-- 9 NUMBERS -->
  <div id="s9" class="scene">
    <div class="glow" style="left:400px;top:-350px"></div>
    <div class="grain"></div>
    <div id="s9-n1" class="num" style="left:150px;top:250px;color:#D94500">0</div>
    <div id="s9-l1" class="lab" style="left:150px;top:490px;width:520px">of 10 correct verdicts</div>
    <div id="s9-s1" class="sub" style="left:150px;top:540px;width:520px">vs 2 of 10 for one big prompt</div>
    <div id="s9-n2" class="num" style="left:760px;top:250px;color:#3E7A3A">120</div>
    <div id="s9-l2" class="lab" style="left:760px;top:490px;width:520px">protected fields leaked</div>
    <div id="s9-s2" class="sub" style="left:760px;top:540px;width:520px">vs 120 for one big prompt</div>
    <div id="s9-n3" class="num" style="left:1370px;top:250px">0</div>
    <div id="s9-l3" class="lab" style="left:1370px;top:490px;width:520px">tests</div>
    <div id="s9-s3" class="sub" style="left:1370px;top:540px;width:520px">no network, about 3 seconds</div>
    <div id="s9-rule" class="rule" style="left:150px;top:700px;width:1620px"></div>
    <div id="s9-foot" class="credit" style="left:150px;top:740px;width:1620px;font-size:26px;color:#151515">integration-tested against Campus Cubbies' own server code · every claim on screen was made by the running app, synthetic student, prototype</div>
  </div>

  <!-- 10 END CARD -->
  <div id="s10" class="scene">
    <div class="glow" style="left:-250px;top:-100px"></div>
    <div class="grain"></div>
    <div id="s10-mascot" class="mascot" style="left:120px;top:250px;width:470px;height:510px">''' + mascot('msvg2') + r'''</div>
    <div id="s10-wm" class="wm" style="left:680px;top:150px;font-size:150px">Gremlins</div>
    <div id="s10-line" class="h" style="left:690px;top:360px;font-size:54px;font-weight:600;width:1150px;letter-spacing:-0.01em">Cubbies is the <span class="o">boundary.</span> The gremlins argue inside it.</div>
    <div id="s10-c1" class="chip g" style="left:690px;top:560px">github.com/riptide-06/Gremlins</div>
    <div id="s10-c2" class="chip y" style="left:690px;top:640px">Built on AGNTCY + Campus Cubbies, UCSC, one weekend.</div>
    <div id="s10-c3" class="chip s" style="left:690px;top:720px">judge link: ask the team</div>
    <div id="s10-credit" class="credit" style="left:690px;top:830px;width:1150px">Campus Cubbies is an A2A service by Adam Smith · one department reachable over Cisco SLIM · prototype, synthetic student, not an official UCSC service</div>
  </div>

  <audio id="bgm" data-start="0" data-duration="25" data-track-index="10" data-volume="0.36" src="assets/music/happy-beats-business-moves-vol-1-by-ende-dot-app.mp3"></audio>
''' + sfx_html + r'''
</div>

<script>
window.__timelines = window.__timelines || {};
const BASS = ''' + json.dumps(bass) + r''';
const RMS = ''' + json.dumps(rms) + r''';
const FPS = 30;
const tl = gsap.timeline({ paused: true });
const S = { s1: 0, s2: 2.52, s3: 5.52, s4: 8.02, s5: 11.02, s6: 13.52, s7: 16.02, s8: 18.52, s9: 20.52, s10: 22.52 };

// ---- transitions (catalog: push slide / vertical push / zoom through) ----
function push(oldId, newId, T, dur) {
  tl.to(oldId, { x: -1920, duration: dur, ease: "power3.inOut" }, T);
  tl.fromTo(newId, { x: 1920, opacity: 1 }, { x: 0, duration: dur, ease: "power3.inOut" }, T);
}
function pushUp(oldId, newId, T, dur) {
  tl.to(oldId, { y: -1080, duration: dur, ease: "power3.inOut" }, T);
  tl.fromTo(newId, { y: 1080, opacity: 1 }, { y: 0, duration: dur, ease: "power3.inOut" }, T);
}
function zoomThrough(oldId, newId, T) {
  tl.to(oldId, { scale: 2.4, opacity: 0, filter: "blur(10px)", duration: 0.38, ease: "power3.in" }, T);
  tl.fromTo(newId, { scale: 0.6, opacity: 0, filter: "blur(10px)" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.38, ease: "power3.out" }, T + 0.12);
}

// ---- scene 1: hook ----
tl.fromTo("#s1-ghost", { scale: 0.9, rotation: -6 }, { scale: 1.05, rotation: 4, duration: 2.5, ease: "sine.inOut" }, 0);
tl.fromTo("#s1-l1", { scale: 1.45, opacity: 0, filter: "blur(16px)" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.5, ease: "power4.out" }, 0.15);
tl.fromTo("#s1-rule", { scaleX: 0 }, { scaleX: 1, duration: 0.45, ease: "expo.out" }, 0.75);
tl.fromTo("#s1-l2", { x: -360, opacity: 0 }, { x: 0, opacity: 1, duration: 0.45, ease: "expo.out" }, 1.15);
zoomThrough("#s1", "#s2", S.s2);

// ---- scene 2: reveal ----
tl.fromTo("#s2-mascot", { scale: 0, opacity: 0, y: 40 }, { scale: 1, opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, S.s2 + 0.1);
tl.fromTo("#s2-wm", { scale: 1.6, opacity: 0, filter: "blur(14px)" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.5, ease: "power4.out" }, 3.02); // beat-locked: 3.02s (first downbeat)
tl.fromTo("#s2-underpath", { strokeDasharray: 400, strokeDashoffset: 400 }, { strokeDashoffset: 0, duration: 0.5, ease: "power2.out" }, 3.52); // beat-grid: 3.52s
tl.fromTo("#s2-line", { y: 70, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "circ.out" }, 3.62);
tl.fromTo("#s2-chip", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, ease: "power2.out" }, 4.12);
tl.to("#s2 .g-arm", { rotation: 9, svgOrigin: "182 134", duration: 0.3, ease: "sine.inOut", yoyo: true, repeat: 7 }, S.s2 + 0.5);
push("#s2", "#s3", S.s3, 0.32);

// ---- scene 3: one question, every office ----
tl.fromTo("#s3-shot", { y: 60, opacity: 0, rotation: 1.5 }, { y: 0, opacity: 1, rotation: 0, duration: 0.55, ease: "power3.out" }, S.s3 + 0.08);
tl.fromTo("#s3-h", { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, S.s3 + 0.1);
tl.fromTo("#s3-cap", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "power2.out" }, S.s3 + 0.95);
[["#s3-c1", 5.77], ["#s3-c2", 6.02], ["#s3-c3", 6.27], ["#s3-c4", 6.52]].forEach(([id, t]) => // beat-grid: office chips on half beats
  tl.fromTo(id, { scale: 0, opacity: 0, y: 24 }, { scale: 1, opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }, t));
tl.fromTo("#s3-f1", { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "power3.out" }, 7.02); // beat-grid: 7.02
tl.fromTo("#s3-f2", { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "power3.out" }, 7.52); // beat-grid: 7.52
tl.to("#s3-shot img", { y: -110, duration: 2.2, ease: "sine.inOut" }, S.s3 + 0.3);
push("#s3", "#s4", S.s4, 0.32);

// ---- scene 4: your data stays yours ----
tl.fromTo("#s4-h", { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, S.s4 + 0.1);
tl.fromTo("#s4-grid", { x: -90, opacity: 0 }, { x: 0, opacity: 1, duration: 0.55, ease: "power3.out" }, S.s4 + 0.15);
tl.fromTo("#s4-ask", { y: 80, opacity: 0, rotation: -1.5 }, { y: 0, opacity: 1, rotation: 0, duration: 0.55, ease: "power3.out" }, S.s4 + 0.5);
tl.fromTo("#s4-cap", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "power2.out" }, S.s4 + 0.9);
tl.to("#s4-grid img", { y: -60, duration: 2.6, ease: "sine.inOut" }, S.s4 + 0.3);
// cursor: move, press, ripple, then the real answered card replaces the ask card
tl.fromTo("#s4-cursor", { x: 560, y: 330, opacity: 0 }, { x: 560, y: 330, opacity: 1, duration: 0.2 }, 9.3);
tl.to("#s4-cursor", { x: 0, y: 0, duration: 0.55, ease: "back.out(1.3)" }, 9.5);
tl.to("#s4-cursor", { scale: 0.84, duration: 0.08, ease: "power2.in", yoyo: true, repeat: 1 }, 10.1);
tl.to("#s4-ask", { scale: 0.985, duration: 0.08, ease: "power2.in", yoyo: true, repeat: 1 }, 10.1);
tl.set("#s4-rip", { opacity: 1 }, 10.14);
tl.to("#s4-rip", { scale: 4.2, opacity: 0, duration: 0.6, ease: "power2.out", immediateRender: false }, 10.14);
tl.to("#s4-ask", { opacity: 0, duration: 0.22, ease: "power2.inOut" }, 10.45);
tl.fromTo("#s4-ans", { opacity: 0, scale: 0.97 }, { opacity: 1, scale: 1, duration: 0.3, ease: "power3.out" }, 10.45);
tl.to("#s4-cursor", { opacity: 0, duration: 0.2 }, 10.55);
push("#s4", "#s5", S.s5, 0.32);

// ---- scene 5: when they disagree ----
tl.fromTo("#s5-h", { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, S.s5 + 0.1);
tl.fromTo("#s5-left", { x: -70, opacity: 0 }, { x: 0, opacity: 1, duration: 0.55, ease: "power3.out" }, S.s5 + 0.2);
tl.fromTo("#s5-cap", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "power2.out" }, S.s5 + 0.9);
tl.fromTo("#s5-sweep", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.out" }, 11.8);
tl.fromTo("#s5-right", { y: 90, opacity: 0, rotation: 1.5 }, { y: 0, opacity: 1, rotation: 0, duration: 0.55, ease: "power3.out" }, 12.3);
push("#s5", "#s6", S.s6, 0.32);

// ---- scene 6: watch them argue ----
tl.fromTo("#s6-h", { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, S.s6 + 0.1);
tl.fromTo("#s6-shot", { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }, S.s6 + 0.1);
tl.fromTo("#s6-shot img", { clipPath: "inset(0 0 100% 0)" }, { clipPath: "inset(0 0 0% 0)", duration: 1.3, ease: "power2.inOut" }, S.s6 + 0.3);
tl.fromTo("#s6-cap", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "power2.out" }, S.s6 + 0.9);
tl.to("#s6-shot img", { y: -120, duration: 1.0, ease: "sine.inOut" }, 14.9);
pushUp("#s6", "#s7", S.s7, 0.32);

// ---- scene 7: a human when it matters ----
tl.fromTo("#s7-card", { scale: 1.18, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.45, ease: "power4.out" }, 16.02); // beat-locked: 16.02s strong cue
tl.fromTo("#s7-h", { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, S.s7 + 0.1);
tl.fromTo("#s7-cap", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "power2.out" }, S.s7 + 0.85);
tl.fromTo("#s7-brief", { x: 160, opacity: 0, rotation: 2.5 }, { x: 0, opacity: 1, rotation: 0, duration: 0.55, ease: "power3.out" }, 17.02); // beat-grid: 17.02
tl.to("#s7-card img", { y: -90, duration: 1.8, ease: "sine.inOut" }, 16.6);
push("#s7", "#s8", S.s8, 0.32);

// ---- scene 8: bring your own agent ----
tl.fromTo("#s8-page", { y: 70, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, 18.52); // beat-locked: 18.52s strong cue
tl.fromTo("#s8-h", { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, S.s8 + 0.1);
tl.fromTo("#s8-cap", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "power2.out" }, S.s8 + 0.65);
tl.fromTo("#s8-img", { scale: 1, transformOrigin: "25% 85%" }, { scale: 1.12, duration: 1.8, ease: "sine.inOut" }, 18.75);
[["#s8-k1", 19.62], ["#s8-k2", 19.87], ["#s8-k3", 20.12]].forEach(([id, t]) =>
  tl.fromTo(id, { scale: 0, opacity: 0, y: 20 }, { scale: 1, opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, t));
zoomThrough("#s8", "#s9", S.s9);

// ---- scene 9: numbers (counting-dynamic-scale, three as a chord) ----
const C = { a: 0, b: 120, c: 0 };
const n1 = document.getElementById("s9-n1"), n2 = document.getElementById("s9-n2"), n3 = document.getElementById("s9-n3");
tl.to(C, { a: 9, b: 0, c: 152, duration: 0.95, ease: "power3.out", onUpdate: () => {
  n1.textContent = String(Math.round(C.a)); n2.textContent = String(Math.round(C.b)); n3.textContent = String(Math.round(C.c));
} }, 20.6);
tl.fromTo(["#s9-n1", "#s9-n2", "#s9-n3"], { scale: 0.55, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.95, ease: "power3.out" }, 20.6);
tl.fromTo(["#s9-l1", "#s9-l2", "#s9-l3"], { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, ease: "power2.out", stagger: 0.08 }, 21.5); // beat-locked: 21.52s
tl.fromTo(["#s9-s1", "#s9-s2", "#s9-s3"], { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, ease: "power2.out", stagger: 0.08 }, 21.75);
tl.fromTo("#s9-rule", { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "expo.out" }, 21.95);
tl.fromTo("#s9-foot", { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, ease: "power2.out" }, 22.05);
zoomThrough("#s9", "#s10", S.s10);

// ---- scene 10: end card ----
tl.fromTo("#s10-mascot", { scale: 0, opacity: 0, y: 40 }, { scale: 1, opacity: 1, y: 0, duration: 0.55, ease: "power3.out" }, S.s10 + 0.08);
tl.fromTo("#s10-wm", { y: -60, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, S.s10 + 0.15);
tl.fromTo("#s10-line", { scale: 1.3, opacity: 0, filter: "blur(10px)" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.5, ease: "power4.out" }, 23.02); // beat-locked: 23.02s strong cue
[["#s10-c1", 23.62], ["#s10-c2", 23.82], ["#s10-c3", 24.02]].forEach(([id, t]) =>
  tl.fromTo(id, { x: -40, opacity: 0 }, { x: 0, opacity: 1, duration: 0.4, ease: "power3.out" }, t));
tl.fromTo("#s10-credit", { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power2.out" }, 24.12);
tl.to("#s10 .g-arm", { rotation: 9, svgOrigin: "182 134", duration: 0.3, ease: "sine.inOut", yoyo: true, repeat: 5 }, S.s10 + 0.6);
tl.to("#s10 .glow", { opacity: 0.4, duration: 0.6, ease: "sine.inOut" }, 24.4);

// ---- music: duck under the numbers, fade under the links ----
tl.to("#bgm", { volume: 0.26, duration: 0.3, ease: "none" }, 20.52);
tl.to("#bgm", { volume: 0.0, duration: 0.9, ease: "none" }, 24.1);

// ---- audio-reactive: bass breathes the glows (pre-extracted, sampled per frame) ----
const glows = gsap.utils.toArray(".glow");
for (let f = 0; f < BASS.length; f++) {
  tl.call(((b, r) => () => { gsap.set(glows, { scale: 1 + b * 0.16 + r * 0.04 }); })(BASS[f], RMS[f]), [], f / FPS);
}
tl.to({}, { duration: 0.001 }, 25); // hold the tail
window.__timelines["main"] = tl;
</script>
</body>
</html>
'''
pathlib.Path('index.html').write_text(html)
print('index.html', len(html), 'bytes; sfx', len(SFX))
