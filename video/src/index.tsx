import React, { type CSSProperties, type ReactNode, useEffect, useState } from 'react';
import { AbsoluteFill, Composition, Img, Sequence, cancelRender, continueRender, delayRender, interpolate, registerRoot, staticFile, useCurrentFrame } from 'remotion';

// Fixed editorial timeline. Audio can be added alongside <Visuals /> below.
export const FPS = 30;
export const DURATION = 2700;
export const SCENES = [
  { name: 'We present', from: 0, duration: 240 },
  { name: 'The question', from: 240, duration: 270 },
  { name: 'Earlier', from: 510, duration: 300 },
  { name: 'Catch up', from: 810, duration: 330 },
  { name: 'No magic', from: 1140, duration: 420 },
  { name: 'A shared interface', from: 1560, duration: 360 },
  { name: 'Why it works', from: 1920, duration: 300 },
  { name: 'Integrated and active', from: 2220, duration: 300 },
  { name: 'Payoff', from: 2520, duration: 180 },
] as const;

const C = { paper: '#F3EFE3', white: '#FFFCF4', green: '#183F35', folder: '#34A853', deep: '#102D27', mint: '#C2D4BF', yellow: '#E9BB62', rust: '#AA5038', line: '#C6CABB', muted: '#5F7164' };
const serif = 'Newsreader, Georgia, serif';
const sans = 'DM Sans, Arial, sans-serif';
const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const ramp = (f: number, start: number, end: number, a = 0, b = 1) => interpolate(f, [start, end], [a, b], clamp);
const ease = (f: number, start = 0, duration = 28) => {
  const t = ramp(f, start, start + duration);
  return 1 - Math.pow(1 - t, 3);
};
const reveal = (f: number, delay = 0): CSSProperties => ({ opacity: ramp(f, delay, delay + 16), transform: `translateY(${(1 - ease(f, delay, 28)) * 34}px)` });

const Box = ({ children, style }: { children?: ReactNode; style?: CSSProperties }) => <div style={{ position: 'absolute', ...style }}>{children}</div>;
const Kicker = ({ children, light = false, style }: { children: ReactNode; light?: boolean; style?: CSSProperties }) => <div style={{ color: light ? C.mint : C.muted, fontSize: 24, fontWeight: 650, letterSpacing: 3, textTransform: 'uppercase', ...style }}>{children}</div>;
const Chip = ({ children, dark = false, style }: { children: ReactNode; dark?: boolean; style?: CSSProperties }) => <span style={{ display: 'inline-flex', alignItems: 'center', padding: '11px 20px', border: `1px solid ${dark ? '#7E9A87' : C.line}`, borderRadius: 30, fontSize: 25, color: dark ? C.paper : C.green, background: dark ? '#244B3D' : C.white, ...style }}>{children}</span>;
const Heading = ({ children, style }: { children: ReactNode; style?: CSSProperties }) => <div style={{ fontFamily: serif, fontSize: 100, lineHeight: 0.98, fontWeight: 450, letterSpacing: -3, ...style }}>{children}</div>;

function Agent({ size = 120, color = C.green, fill = C.paper }: { size?: number; color?: string; fill?: string }) {
  return <svg width={size} height={size} viewBox="0 0 120 120" fill="none">
    <rect x="13" y="22" width="94" height="76" rx="28" fill={fill} stroke={color} strokeWidth="3" />
    <path d="M60 22V10M54 9h12M13 52H5v22h8M107 52h8v22h-8" stroke={color} strokeWidth="3" strokeLinecap="round" />
    <circle cx="43" cy="57" r="6" fill={color}/><circle cx="77" cy="57" r="6" fill={color}/>
    <path d="M43 78h34" stroke={color} strokeWidth="3" strokeLinecap="round"/>
  </svg>;
}

function Cubby({ size = 410, color = C.green, fill = C.mint, slot = C.deep }: { size?: number; color?: string; fill?: string; slot?: string }) {
  return <svg width={size} height={size} viewBox="0 0 400 400" fill="none">
    <path d="M65 85 304 55 355 98 116 130Z" fill={fill} stroke={color} strokeWidth="3"/>
    <path d="M304 55 355 98v232l-51-36Z" fill={color} stroke={color} strokeWidth="3"/>
    <path d="M65 85 304 55v239L65 328Z" fill={fill} stroke={color} strokeWidth="3"/>
    <path d="M87 107 282 83v158L87 266Z" fill={slot} stroke={color} strokeWidth="3"/>
    <path d="m87 266 34-47 161-20v42Z" fill={color}/>
    <path d="m115 227 133-17 20 24-134 16Z" fill={C.paper}/>
    <path d="m130 220 119-15 10 11-118 15Z" fill={C.folder}/>
    <path d="m151 284 64-8" stroke={color} strokeWidth="5" strokeLinecap="round"/>
  </svg>;
}

function Folder({ size = 300, label = false }: { size?: number; label?: boolean }) {
  return <svg width={size} height={size * 0.75} viewBox="0 0 400 300" fill="none">
    {/* Matches the real project's Drive folderColorRgb: #34a853. */}
    <path d="M28 56q0-18 18-18h113l37 38h158q18 0 18 18v162q0 18-18 18H46q-18 0-18-18Z" fill={C.folder}/>
    <path d="M28 100h344" stroke="#218B3E" strokeWidth="3"/>
    <path d="M72 141h83" stroke="#DFF3E0" strokeWidth="4" strokeLinecap="round"/>
    {label && <text x="70" y="219" fontFamily={sans} fontSize="39" fontWeight="600" fill={C.white}>My Cubby</text>}
  </svg>;
}

function FileIcon({ color = C.green, size = 50 }: { color?: string; size?: number }) {
  return <svg width={size} height={size * 1.2} viewBox="0 0 50 60" fill="none"><path d="M8 3h23l12 13v40H8Z" stroke={color} strokeWidth="2.5"/><path d="M31 3v14h12M17 28h17M17 37h17M17 46h11" stroke={color} strokeWidth="2.5"/></svg>;
}

function Office({ size = 130, color = C.green }: { size?: number; color?: string }) {
  return <svg width={size} height={size} viewBox="0 0 140 140" fill="none"><path d="m17 48 53-29 53 29ZM27 54v55m28-55v55m30-55v55m28-55v55M17 112h106M13 122h114" stroke={color} strokeWidth="4" strokeLinejoin="round"/><circle cx="70" cy="38" r="5" fill={color}/></svg>;
}

function Arrow({ x1, x2, y, color = C.green, progress = 1 }: { x1: number; x2: number; y: number; color?: string; progress?: number }) {
  return <svg style={{ position: 'absolute', inset: 0 }} width="1920" height="1080"><path d={`M${x1} ${y}H${x1 + (x2 - x1) * progress}`} stroke={color} strokeWidth="3" fill="none"/><path d={`m${x2 - 12} ${y - 8} 12 8-12 8`} stroke={color} strokeWidth="3" fill="none" opacity={progress}/></svg>;
}

function ChatRail({ height = 560 }: { height?: number }) {
  return <div style={{ width: 78, height, borderRight: `1px solid ${C.line}`, background: '#E9E6D9', borderRadius: '17px 0 0 17px', paddingTop: 27, textAlign: 'center' }}>
    <svg width="32" height="32" viewBox="0 0 32 32"><path d="M8 7h17v13H14l-6 5Z" fill="none" stroke={C.green} strokeWidth="2"/></svg>
    {[0, 1, 2].map(i => <div key={i} style={{ width: 36, height: 5, background: i ? C.line : C.green, borderRadius: 4, margin: '32px auto' }}/>)}</div>;
}

function Frame({ children, dark = false, chapter, story = true }: { children: ReactNode; dark?: boolean; chapter: number; story?: boolean }) {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: dark ? C.green : C.paper, color: dark ? C.paper : C.green, fontFamily: sans }}>
    <AbsoluteFill style={{ opacity: dark ? 0.06 : 0.2, backgroundImage: `radial-gradient(${dark ? C.paper : '#8F9A80'} 0.7px, transparent 0.7px)`, backgroundSize: '7px 7px' }}/>
    <Box style={{ left: 82, top: 48, display: 'flex', alignItems: 'center', gap: 17 }}><svg width="35" height="35" viewBox="0 0 35 35"><path d="M4 5h27v25H4zM10 11h15v12H10z" fill="none" stroke={dark ? C.mint : C.green} strokeWidth="2"/></svg><span style={{ fontWeight: 650, fontSize: 25, letterSpacing: -0.5 }}>Campus Cubbies</span></Box>
    <Box style={{ right: 84, top: 53, fontSize: 21, letterSpacing: 1.5, color: dark ? C.mint : C.muted }}>{story ? 'ILLUSTRATIVE SCENARIO' : 'A2A 1.0 · ACTIVE SERVICE'}</Box>
    {children}
    <Box style={{ left: 84, right: 84, bottom: 43, display: 'flex', alignItems: 'center', gap: 20 }}>
      <span style={{ fontSize: 18, letterSpacing: 2, opacity: 0.75 }}>0{chapter}</span>
      <div style={{ height: 1, flex: 1, background: dark ? '#577664' : C.line }}/>
      <span style={{ fontSize: 18, letterSpacing: 2, opacity: 0.75 }}>{['WE PRESENT', 'THE QUESTION', 'EARLIER', 'CATCH UP', 'NO MAGIC', 'A SHARED INTERFACE', 'WHY IT WORKS', 'INTEGRATED AND ACTIVE', 'READY WHEN YOU ASK'][chapter - 1]}</span>
    </Box>
    {/* An editorial edge sweep keeps cuts moving without changing scene lengths. */}
    {chapter > 1 && f < 20 && <Box style={{ left: 1920 * ease(f, 0, 20), top: 0, height: 1080, width: 110, background: C.yellow, transform: 'skewX(-9deg)' }}/>}
  </AbsoluteFill>;
}

function Opening() {
  return <CreatorCard/>;
}

function CreatorCard({ closing = false }: { closing?: boolean }) {
  const f = useCurrentFrame();
  const navy = '#003c6c';
  return <AbsoluteFill style={{ background: '#FFFFFF', color: navy, fontFamily: 'Roboto, Arial, sans-serif' }}>
    {/* Official lockup, 100px high; at least 100px unobstructed clear space. */}
    <Img src={staticFile('brand/ucsc-baskin-engineering.png')} style={{ position: 'absolute', left: 130, top: 120, width: 652.23, height: 100 }}/>
    <Box style={{ left: 130, top: 330, width: 1190, ...reveal(f) }}>
      <div style={{ fontSize: 23, letterSpacing: 3, textTransform: 'uppercase' }}>{closing ? 'Ready when you ask' : 'We present'}</div>
      <div style={{ fontSize: 112, fontWeight: 750, letterSpacing: -4, marginTop: 17 }}>Campus Cubbies</div>
      <div style={{ fontSize: 32, marginTop: 17, fontWeight: 550 }}>{closing ? 'cubby.bayleaf.dev' : 'Personal agents. Campus connections.'}</div>
      <div style={{ width: 82, height: 6, background: '#f29813', marginTop: 35 }}/>
      <div style={{ marginTop: 32, fontSize: 32, fontWeight: 650 }}>Tarun Nagaraju <span style={{ fontSize: 27, fontWeight: 400 }}>(tnagaraj@ucsc.edu)</span></div>
      <div style={{ marginTop: 9, fontSize: 27 }}>Student in Technology and Information Management</div>
      <div style={{ marginTop: 26, fontSize: 32, fontWeight: 650 }}>Adam Smith <span style={{ fontSize: 27, fontWeight: 400 }}>(amsmith@ucsc.edu)</span></div>
      <div style={{ marginTop: 9, fontSize: 27 }}>Faculty in Computational Media</div>
      <div style={{ marginTop: 27, fontSize: 27, fontWeight: 550 }}>Jack Baskin School of Engineering</div>
    </Box>
    <Box style={{ left: 1340, top: 330, width: 460, height: 470, transform: `scale(${closing ? 1.15 - ease(f, 0, 60) * 0.15 : 1})`, opacity: ramp(f, 0, 18) }}>
      <svg width="460" height="470" style={{ position: 'absolute' }}><circle cx="230" cy="220" r="188" fill="none" stroke="#D2DEE8"/>{[[67, 114], [396, 124], [230, 405]].map(([x, y], i) => { const t = ((f + i * 38) % 140) / 140; return <g key={i}><path d={`M${x} ${y}L230 220`} stroke="#A4BACA" strokeWidth="2"/><circle cx={x + (230 - x) * t} cy={y + (220 - y) * t} r="5" fill="#fdc700"/></g>; })}</svg>
      <Box style={{ left: 94, top: 116, transform: `translateY(${Math.sin(f / 40) * 4}px)` }}><Folder size={272} label/></Box>
      <Box style={{ left: 23, top: 70 }}><Agent size={88} color={navy} fill="#FFFFFF"/></Box><Box style={{ left: 352, top: 80 }}><Agent size={88} color={navy} fill="#FFFFFF"/></Box><Box style={{ left: 186, top: 361 }}><Office size={88} color={navy}/></Box>
    </Box>
    <Box style={{ left: 1410, top: 829, padding: '12px 23px', border: `1px solid ${navy}`, borderRadius: 30, fontSize: 22, fontWeight: 650 }}>A2A 1.0 · {closing ? 'Active service' : 'LIVE SERVICE'}</Box>
    <Box style={{ left: 130, right: 130, top: 934, borderTop: '2px solid #fdc700', paddingTop: 24, display: 'flex', justifyContent: 'space-between', fontSize: 26 }}><span style={{ fontWeight: 650 }}>Cloud AI track</span><span>SF Tech Week Hackathon @ UCSC SVC</span></Box>
  </AbsoluteFill>;
}

function Question() {
  const f = useCurrentFrame();
  const out = ease(f, 251, 19);
  return <Frame chapter={2}>
    <Box style={{ left: 86, top: 193, width: 1115, height: 653, border: `1px solid ${C.line}`, background: C.white, borderRadius: 18, transform: `translateX(${-out * 140}px)`, opacity: 1 - out * 0.65 }}>
      <ChatRail height={650}/>
      <Box style={{ left: 116, top: 34, ...reveal(f) }}><Kicker style={{ fontSize: 22 }}>Student · personal agent</Kicker></Box>
      <Box style={{ left: 116, top: 89, width: 953, height: 1, background: C.line }}/>
      <Box style={{ left: 171, top: 149, width: 899, padding: '34px 39px 29px', background: '#E9ECDf', borderRadius: '24px 24px 3px 24px', ...reveal(f, 12) }}>
        <div style={{ fontSize: 21, color: C.muted, marginBottom: 20 }}>YOU</div>
        <Heading style={{ fontSize: 79, letterSpacing: -2 }}>Anything to know<br/>before I enroll?</Heading>
        <svg width="755" height="22" style={{ marginTop: 8 }}><path d="M3 10Q355 0 705 12" pathLength="1" stroke={C.yellow} strokeWidth="8" fill="none" strokeDasharray="1" strokeDashoffset={1 - ease(f, 37, 38)}/></svg>
      </Box>
      <Box style={{ left: 116, top: 481, display: 'flex', alignItems: 'center', gap: 22, ...reveal(f, 70) }}><Agent size={77}/><div style={{ display: 'flex', gap: 10 }}>{[0, 1, 2].map(i => <span key={i} style={{ width: 9, height: 9, borderRadius: 9, background: C.muted, opacity: 0.3 + 0.7 * Math.max(0, Math.sin(f / 10 - i)), transform: `translateY(${-3 * Math.sin(f / 10 - i)}px)` }}/>)}</div></Box>
      <Box style={{ left: 116, bottom: 28, right: 41, height: 43, borderTop: `1px solid ${C.line}`, paddingTop: 16, fontSize: 19, color: C.muted }}>Next-quarter planning</Box>
    </Box>
    <Box style={{ right: 110, top: 228, width: 525, height: 570, transform: `translateY(${Math.sin(f / 65) * 5}px) rotate(${3 - ease(f, 15) * 4}deg)`, opacity: ramp(f, 8, 30) }}>
      <div style={{ position: 'absolute', inset: '-18px 12px 20px -18px', border: `1px solid ${C.line}`, borderRadius: 18, transform: 'rotate(-5deg)' }}/>
      <div style={{ position: 'absolute', inset: 0, background: C.white, border: `1.5px solid ${C.green}`, borderRadius: 18, padding: 38, boxShadow: '12px 18px 0 #183F350C' }}>
        <Kicker style={{ fontSize: 20 }}>Student workspace</Kicker>
        <Heading style={{ fontSize: 55, marginTop: 25 }}>Next-quarter<br/>plans</Heading>
        <div style={{ display: 'flex', gap: 9, marginTop: 32 }}>{['M', 'T', 'W', 'T', 'F'].map((d, i) => <div key={i} style={{ borderTop: `2px solid ${C.line}`, width: 79, paddingTop: 14, textAlign: 'center', fontSize: 20, color: C.muted }}>{d}<div style={{ marginTop: 20, height: 70 + (i % 2) * 27, background: i === 2 ? C.yellow : '#E5EADF', borderRadius: 7 }}/></div>)}</div>
        <div style={{ borderTop: `1px solid ${C.line}`, marginTop: 40, paddingTop: 25, display: 'flex', gap: 12, alignItems: 'center' }}><FileIcon size={25}/><span style={{ fontSize: 24 }}>My enrollment notes</span></div>
      </div>
    </Box>
    <Box style={{ left: 105, top: 880, ...reveal(f, 110) }}><Chip>International student</Chip></Box>
    {f > 247 && <Box style={{ right: 0, top: 150, fontFamily: serif, fontStyle: 'italic', fontSize: 250, color: C.rust, opacity: out * 0.2, transform: `translateX(${(1 - out) * 1100}px)` }}>Earlier</Box>}
  </Frame>;
}

function Earlier() {
  const f = useCurrentFrame();
  const rewind = 1 - ease(f, 0, 40);
  const travel = ease(f, 100, 80);
  return <Frame chapter={3} dark>
    <Box style={{ left: 86, top: 171, ...reveal(f, 0) }}><Kicker light>ISO · office agent</Kicker><Heading style={{ fontSize: 114, marginTop: 27 }}>Earlier.</Heading></Box>
    <Box style={{ left: 90 - rewind * 650, top: 335, width: 1740, height: 48, overflow: 'hidden', opacity: 0.7 }}>
      <svg width="2300" height="48" style={{ transform: `translateX(${-rewind * 900}px)` }}>{Array.from({ length: 70 }, (_, i) => <path key={i} d={`M${i * 39} 0v${i % 5 ? 9 : 22}`} stroke={C.mint} strokeWidth="1.5"/>)}<path d="M0 0h2300" stroke={C.mint}/></svg>
      <div style={{ position: 'absolute', right: 0, top: 16, background: C.green, paddingLeft: 20, fontSize: 19, letterSpacing: 3 }}>REWIND / EARLIER</div>
    </Box>
    <Box style={{ left: 86, top: 412, width: 1745, height: 539, border: '1px solid #71939A', background: '#112F37', borderRadius: 6, ...reveal(f, 10) }}>
      <div style={{ height: 49, borderBottom: '1px solid #52747C', display: 'flex', alignItems: 'center', padding: '0 23px', justifyContent: 'space-between', color: '#C5DEE0', fontSize: 19, letterSpacing: 2 }}><span>WORKBENCH / OUTBOUND</span><span>DELIVERY QUEUE · 01</span></div>
      <div style={{ position: 'absolute', left: 445, top: 49, bottom: 0, borderLeft: '1px solid #52747C' }}/><div style={{ position: 'absolute', left: 1165, top: 49, bottom: 0, borderLeft: '1px solid #52747C' }}/>
      <div style={{ position: 'absolute', left: 470, top: 74, color: '#A8C4CC', fontSize: 18, letterSpacing: 2 }}>SOURCE → DELIVERY</div>
    </Box>
    <Box style={{ left: 119, top: 501, width: 385, ...reveal(f, 20) }}>
      <Office size={103} color="#C5DEE0"/><div style={{ fontSize: 34, fontWeight: 500, marginTop: 20 }}>International<br/>Student Office</div><div style={{ marginTop: 24 }}><Chip dark style={{ background: '#1D424B', borderColor: '#52747C' }}>ISO agent</Chip></div>
    </Box>
    <Arrow x1={575} x2={1180} y={630} color="#6C9278" progress={ease(f, 65, 40)}/>
    <Box style={{ left: 570 + travel * 560, top: 534 + travel * 30, opacity: ramp(f, 70, 90) * (1 - ramp(f, 167, 190)), transform: `scale(${1 - travel * 0.65}) rotate(${-4 + travel * 8}deg)`, transformOrigin: 'center' }}>
      <div style={{ background: C.paper, color: C.green, padding: '25px 30px', width: 425, borderRadius: 9, boxShadow: '8px 14px 0 #0B251C66' }}><Kicker style={{ fontSize: 18 }}>Federal enrollment rules</Kicker><div style={{ fontSize: 40, marginTop: 20, lineHeight: 1.15 }}>ISO update</div><div style={{ marginTop: 22, borderTop: `1px solid ${C.line}`, paddingTop: 15, fontSize: 22 }}>Source attached</div></div>
    </Box>
    <Box style={{ right: 135, top: 465, width: 485, textAlign: 'center', ...reveal(f, 42) }}><Cubby size={397} color={C.mint} fill="#4C7260"/><div style={{ fontSize: 30, marginTop: -20 }}>Your cubby</div></Box>
    <Box style={{ left: 619, top: 822, ...reveal(f, 180) }}><Chip dark style={{ color: C.yellow, borderColor: '#6A835D' }}>Delivered</Chip></Box>
  </Frame>;
}

function CatchUp() {
  const f = useCurrentFrame();
  return <Frame chapter={4}>
    <Box style={{ left: 86, top: 171, ...reveal(f) }}><Kicker>Student · personal agent</Kicker><Heading style={{ marginTop: 25 }}>Now, catch up.</Heading></Box>
    <Box style={{ left: 86, top: 352, width: 1741, height: 594, border: `1px solid ${C.line}`, background: '#FFFCF480', borderRadius: 18 }}><ChatRail height={590}/></Box>
    <svg width="1920" height="1080" style={{ position: 'absolute', inset: 0 }}><path d="M628 477C780 477 723 667 843 667M628 787C780 787 723 667 843 667H977" fill="none" stroke={C.line} strokeWidth="3"/><path d="m957 657 15 10-15 10" fill="none" stroke={C.green} strokeWidth="3"/>
      <circle cx={628 + ease(f, 50, 50) * 212} cy={477 + ease(f, 50, 50) * 190} r="7" fill={C.rust} opacity={1 - ramp(f, 95, 115)}/><circle cx={628 + ease(f, 68, 50) * 212} cy={787 - ease(f, 68, 50) * 120} r="7" fill={C.green} opacity={1 - ramp(f, 113, 135)}/>
    </svg>
    <Box style={{ left: 190, top: 383, width: 425, ...reveal(f, 16) }}>
      <div style={{ border: `1px solid ${C.line}`, background: C.white, borderRadius: 12, padding: '29px 34px', transform: 'rotate(-2deg)' }}><Kicker style={{ color: C.rust, fontSize: 20 }}>Campus knowledge</Kicker><div style={{ display: 'flex', gap: 22, alignItems: 'center', marginTop: 28 }}><FileIcon size={43} color={C.rust}/><div style={{ fontSize: 43 }}>ISO update</div></div><div style={{ height: 2, width: 259, background: C.line, marginTop: 24 }}/></div>
    </Box>
    <Box style={{ left: 190, top: 687, width: 425, ...reveal(f, 35) }}><div style={{ border: `1px solid ${C.line}`, background: '#E4E9DC', borderRadius: 12, padding: '29px 34px', transform: 'rotate(2deg)' }}><Kicker style={{ fontSize: 20 }}>Private context</Kicker><div style={{ display: 'flex', gap: 22, alignItems: 'center', marginTop: 25 }}><FileIcon size={43}/><div style={{ fontSize: 43 }}>Your plan</div></div><div style={{ height: 2, width: 181, background: '#9AAA93', marginTop: 24 }}/></div></Box>
    <Box style={{ left: 755, top: 580, background: C.paper, borderRadius: 90, padding: 20, ...reveal(f, 63) }}><Agent size={112}/></Box>
    <Box style={{ left: 1000, top: 374, width: 818, height: 544, padding: '37px 44px', background: C.green, borderRadius: 17, boxShadow: '9px 12px 0 #183F3510', ...reveal(f, 83) }}>
      <Kicker light style={{ fontSize: 21 }}>Pre-registration briefing</Kicker>
      {[
        ['01', 'What changed'],
        ['02', 'Check your plan'],
        ['03', 'Ask the ISO'],
      ].map(([n, title], i) => <div key={n} style={{ marginTop: i ? 35 : 45, paddingTop: i ? 27 : 0, borderTop: i ? '1px solid #496653' : undefined, display: 'flex', gap: 26, ...reveal(f, 96 + i * 31) }}><span style={{ color: C.yellow, fontSize: 22, paddingTop: 13 }}>{n}</span><div style={{ color: C.paper, fontSize: 46, letterSpacing: -0.7 }}>{title}</div></div>)}
      <div style={{ marginTop: 28, ...reveal(f, 203) }}><Chip dark style={{ fontSize: 21, padding: '8px 16px' }}>Source: ISO update</Chip></div>
    </Box>
  </Frame>;
}

function NoMagic() {
  const f = useCurrentFrame();
  const morph = ease(f, 48, 68);
  const files = ease(f, 130, 50);
  return <Frame chapter={5}>
    <Box style={{ left: 86, top: 242, width: 715 }}><Kicker style={reveal(f)}>Under the hood</Kicker><Heading style={{ fontSize: 99, marginTop: 37, ...reveal(f, 14) }}>Ordinary files.<br/>Useful context.</Heading>
      <div style={{ marginTop: 78, ...reveal(f, 233) }}><Chip>On first connection</Chip></div>
    </Box>
    <Box style={{ left: 831, top: 176, width: 987, height: 740, background: '#E1E7D9', borderRadius: 24, overflow: 'hidden', border: `1px solid ${C.line}` }}>
      <svg width="987" height="740" style={{ position: 'absolute', opacity: 0.4 }}>{[160, 265, 370].map(r => <circle key={r} cx="493" cy="354" r={r} stroke="#9DAF97" fill="none" strokeWidth="1"/>)}</svg>
      <Box style={{ top: 36, left: 39, right: 39, display: 'flex', alignItems: 'center', gap: 13, opacity: morph }}><svg width="33" height="29" viewBox="0 0 33 29"><path d="m11 1 10 0 11 19-10 0Z" fill="#577A54"/><path d="m11 1 5 9L6 28 1 19Z" fill="#B4944E"/><path d="m6 28 5-9h21l-5 9Z" fill="#6E9292"/></svg><span style={{ fontSize: 26, fontWeight: 550 }}>UCSC Google Drive</span><span style={{ fontSize: 26, color: C.muted }}>/ My Cubby</span></Box>
      <Box style={{ left: 246, top: 120, opacity: 1 - morph, transform: `rotateY(${morph * 75}deg) scale(${1 - morph * 0.16})` }}><Cubby size={500}/></Box>
      <Box style={{ left: 269 - files * 269, top: 166 + files * 21, transform: `scale(${0.72 + morph * 0.28 - files * 0.32}) rotate(${-8 + morph * 8}deg)`, transformOrigin: 'center', opacity: morph }}><Folder size={445} label/></Box>
      <Box style={{ left: 356, top: 210, width: 568, opacity: files, transform: `translateX(${(1 - files) * 170}px)` }}>
        {['Start here.md', 'Notes.md', 'ISO enrollment update.txt'].map((name, i) => <div key={name} style={{ height: 113, background: C.white, marginBottom: 17, border: `1px solid ${C.line}`, borderRadius: 10, display: 'flex', alignItems: 'center', gap: 19, padding: '0 23px', ...reveal(f, 147 + i * 21) }}><FileIcon size={34} color={i === 2 ? C.rust : C.green}/><div style={{ fontSize: i === 2 ? 27 : 31, letterSpacing: -0.5 }}>{name}</div></div>)}
      </Box>
      <Box style={{ left: 44, right: 44, bottom: 58, paddingTop: 25, borderTop: `1px solid ${C.line}`, opacity: ramp(f, 211, 235), fontSize: 22, color: C.muted }}>Illustrated folder view</Box>
    </Box>
  </Frame>;
}

function SharedInterface() {
  const f = useCurrentFrame();
  const stage = Math.min(2, Math.floor(Math.max(0, f - 30) / 100));
  const cool = '#112F37';
  return <Frame chapter={6} story={false}>
    <Box style={{ left: 86, top: 151, ...reveal(f) }}><Kicker>Different harnesses</Kicker><Heading style={{ fontSize: 94, marginTop: 22 }}>One shared interface.</Heading></Box>
    <Box style={{ right: 87, top: 242, color: C.muted, fontSize: 19 }}>Protocol diagram</Box>
    <Box style={{ left: 86, top: 335, width: 562, height: 353, background: C.white, border: `1px solid ${C.line}`, borderRadius: 22, overflow: 'hidden', ...reveal(f, 12) }}>
      <ChatRail height={353}/><Box style={{ left: 105, top: 28 }}><Kicker style={{ fontSize: 19 }}>Student / chat</Kicker></Box>
      <Box style={{ left: 190, top: 88, width: 334, padding: '22px 25px', background: '#E9E6D9', borderRadius: '20px 20px 2px 20px', fontSize: 28 }}>Next-quarter plans</Box>
      <Box style={{ left: 104, top: 202, display: 'flex', gap: 19, alignItems: 'center' }}><Agent size={78}/><div style={{ fontSize: 23 }}>Personal agent<div style={{ width: 205, height: 5, background: C.line, marginTop: 17 }}/><div style={{ width: 145, height: 5, background: C.line, marginTop: 11 }}/></div></Box>
    </Box>
    <Box style={{ left: 1272, top: 335, width: 562, height: 353, background: cool, color: '#C5DEE0', border: '1px solid #71939A', borderRadius: 6, ...reveal(f, 24) }}>
      <div style={{ padding: '23px 27px', borderBottom: '1px solid #52747C', fontSize: 19, letterSpacing: 2 }}>ISO / WORKBENCH</div>
      <Box style={{ left: 0, top: 73, width: 157, bottom: 0, borderRight: '1px solid #52747C', padding: '27px 20px', fontSize: 18, lineHeight: 2.8 }}>OUTBOUND<br/><span style={{ color: '#71939A' }}>SOURCES<br/>DELIVERY</span></Box>
      <Box style={{ left: 181, top: 105 }}><div style={{ fontSize: 25 }}>ISO update</div><div style={{ marginTop: 26, border: '1px solid #52747C', padding: '16px 20px', fontSize: 20 }}>Source attached</div><div style={{ marginTop: 24, fontSize: 18, color: '#A8C4CC' }}>QUEUE / 01</div></Box>
    </Box>
    <Arrow x1={648} x2={813} y={484} progress={ease(f, 52, 42)}/>
    <svg width="1920" height="1080" style={{ position: 'absolute', opacity: ease(f, 64, 42) }}><path d="M1272 484H1110m12-8-12 8 12 8" fill="none" stroke="#52747C" strokeWidth="3"/><path d="M960 556V729m-8-12 8 12 8-12" fill="none" stroke={C.green} strokeWidth="3"/></svg>
    <Box style={{ left: 813, top: 414, width: 297, height: 143, borderRadius: 72, background: C.green, color: C.white, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', ...reveal(f, 35) }}><div style={{ fontSize: 47 }}>A2A 1.0</div><div style={{ fontSize: 18, color: C.mint, marginTop: 8 }}>SHARED PROTOCOL</div></Box>
    <Box style={{ left: 869, top: 588, padding: '10px 18px', background: C.white, border: `1px solid ${C.line}`, borderRadius: 6, display: 'flex', gap: 12, alignItems: 'center', ...reveal(f, 65) }}><FileIcon size={20}/><span style={{ fontSize: 20 }}>Agent Card</span></Box>
    <Box style={{ left: 690, top: 734, width: 540, height: 128, background: '#E1E7D9', border: `1px solid ${C.line}`, borderRadius: 18, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24, ...reveal(f, 112) }}><Folder size={126}/><div style={{ fontSize: 31 }}>Campus Cubbies<div style={{ fontSize: 20, color: C.muted, marginTop: 10 }}>Permissioned tools / My Cubby</div></div></Box>
    <Box style={{ left: 86, right: 86, top: 913, display: 'flex', justifyContent: 'center', gap: 24 }}>{['Discover', 'Connect', 'Use tools'].map((label, i) => <div key={label} style={{ width: 300, display: 'flex', gap: 17, alignItems: 'center', padding: '15px 25px', borderTop: `3px solid ${i <= stage ? C.folder : C.line}`, color: i <= stage ? C.green : C.muted, background: i === stage ? '#E1E7D9' : 'transparent' }}><span style={{ fontSize: 19 }}>0{i + 1}</span><span style={{ fontSize: 28, fontWeight: i === stage ? 650 : 400 }}>{label}</span></div>)}</Box>
  </Frame>;
}

function Integrated() {
  const f = useCurrentFrame();
  const systems = [
    { x: 86, title: 'Google sign-in', sub: 'Campus identity', icon: 'G' },
    { x: 677, title: 'UCSC Google Drive', sub: 'Your files', icon: 'folder' },
    { x: 1268, title: 'BayLeaf Chat', sub: 'Agent onboarding', icon: 'agent' },
  ];
  return <Frame chapter={8} dark story={false}>
    <Box style={{ left: 86, top: 156, ...reveal(f) }}><Kicker light>Campus integrations</Kicker><Heading style={{ fontSize: 99, marginTop: 25 }}>Integrated. Active today.</Heading></Box>
    <svg width="1920" height="1080" style={{ position: 'absolute', opacity: ramp(f, 45, 90) }}>{systems.map(({ x }, i) => <g key={x}><path d={`M${x + 280} 584V629H960V691`} fill="none" stroke="#75947B" strokeWidth="3"/><circle cx={x + 280 + (960 - x - 280) * ((f + i * 30) % 120) / 120} cy="629" r="6" fill={C.yellow}/></g>)}</svg>
    {systems.map(({ x, title, sub, icon }, i) => <Box key={title} style={{ left: x, top: 360, width: 562, height: 224, padding: '32px 31px', background: '#244B3D', border: '1px solid #75947B', borderRadius: 17, ...reveal(f, 18 + i * 20) }}><div style={{ display: 'flex', alignItems: 'center', gap: 25 }}><div style={{ width: 88, height: 90, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{icon === 'folder' ? <Folder size={88}/> : icon === 'agent' ? <Agent size={88} color={C.mint} fill="#244B3D"/> : <div style={{ fontSize: 61, color: C.yellow, fontWeight: 650 }}>G</div>}</div><div><div style={{ fontSize: 31, letterSpacing: -0.5 }}>{title}</div><div style={{ fontSize: 21, color: C.mint, marginTop: 15 }}>{sub}</div></div></div><div style={{ height: 1, background: '#577664', marginTop: 25 }}/></Box>)}
    <Box style={{ left: 613, top: 684, width: 694, height: 132, background: C.paper, color: C.green, borderRadius: 18, border: `1px solid ${C.mint}`, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 31, ...reveal(f, 75) }}><Folder size={108}/><div><div style={{ fontSize: 39, fontWeight: 550 }}>Campus Cubbies</div><div style={{ fontSize: 19, letterSpacing: 2, marginTop: 10, color: C.muted }}>ACTIVE SERVICE</div></div></Box>
    <Box style={{ top: 855, left: 0, width: 1920, display: 'flex', justifyContent: 'center', gap: 22 }}>{['Sign-in verified', 'Drive verified', 'A2A verified'].map((text, i) => <Chip key={text} dark style={{ ...reveal(f, 100 + i * 20), gap: 14 }}><span style={{ width: 9, height: 9, borderRadius: 9, background: '#83D398' }}/>{text}</Chip>)}</Box>
    <Box style={{ left: 86, right: 86, top: 949, display: 'flex', justifyContent: 'space-between', color: C.mint, fontSize: 20, ...reveal(f, 150) }}><span>Infrastructure / Google Cloud Run + Firestore</span><span>Integration diagram · Verified live operations</span></Box>
  </Frame>;
}

function WhyItWorks() {
  const f = useCurrentFrame();
  const flow = (f % 95) / 95;
  return <Frame chapter={7}>
    <Box style={{ left: 86, top: 171, ...reveal(f) }}><Kicker>Permissions / Delivery / Your Drive</Kicker><Heading style={{ marginTop: 25, fontSize: 105 }}>A useful handoff.</Heading></Box>
    <Box style={{ left: 790, top: 368, width: 1028, height: 555, border: '2px dashed #8BA184', borderRadius: 25, background: '#E4E9DC', opacity: ramp(f, 30, 55) }}/>
    <Box style={{ left: 824, top: 395, fontSize: 22, color: C.muted, letterSpacing: 2, ...reveal(f, 43) }}>YOUR DRIVE / YOUR CONTEXT</Box>
    <Arrow x1={352} x2={497} y={568} progress={ease(f, 20, 30)}/><Arrow x1={699} x2={888} y={568} progress={ease(f, 42, 30)}/><Arrow x1={1217} x2={1500} y={568} progress={ease(f, 76, 30)}/>
    <Box style={{ left: 364 + flow * 498, top: 561, width: 14, height: 14, borderRadius: 20, background: C.rust, opacity: ramp(f, 65, 90) }}/>
    <Box style={{ left: 1217 + flow * 263, top: 561, width: 14, height: 14, borderRadius: 20, background: C.green, opacity: ramp(f, 108, 125) }}/>
    <Box style={{ left: 107, top: 467, width: 245, textAlign: 'center', ...reveal(f, 12) }}><Agent size={137}/><div style={{ marginTop: 18, fontSize: 33, fontWeight: 550 }}>ISO agent</div></Box>
    <Box style={{ left: 499, top: 494, width: 200, height: 148, borderRadius: 24, border: `2px solid ${C.green}`, background: C.white, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 29, textAlign: 'center', fontWeight: 550, ...reveal(f, 32) }}>Contribution<br/>slot</Box>
    <Box style={{ left: 896, top: 441, width: 309, textAlign: 'center', ...reveal(f, 50) }}><Folder size={300}/><div style={{ marginTop: -6, fontSize: 34, fontWeight: 550 }}>My Cubby</div></Box>
    <Box style={{ left: 1515, top: 470, width: 240, textAlign: 'center', ...reveal(f, 80) }}><Agent size={137}/><div style={{ marginTop: 18, fontSize: 34, fontWeight: 550 }}>Your agent</div></Box>
    <Box style={{ left: 548, top: 674, ...reveal(f, 85) }}><div style={{ fontSize: 27, fontWeight: 600 }}>Contribute</div></Box>
    <svg width="1920" height="1080" style={{ position: 'absolute', inset: 0, opacity: ramp(f, 118, 145) }}><path d="M738 797H539" stroke={C.rust} strokeWidth="2" strokeDasharray="5 7"/><path d="M741 774v46" stroke={C.rust} strokeWidth="5"/><path d="m528 787-10 10 10 10" stroke={C.rust} strokeWidth="2" fill="none"/><path d="m758 783 27 27m0-27-27 27" stroke={C.rust} strokeWidth="3"/></svg>
    <Box style={{ left: 535, top: 833, fontSize: 25, color: C.rust, ...reveal(f, 140) }}>No read access</Box>
    <Box style={{ left: 860, top: 752, padding: '17px 23px', border: `1px solid #90A489`, background: C.paper, borderRadius: 10, width: 385, display: 'flex', alignItems: 'center', gap: 18, ...reveal(f, 126) }}><svg width="30" height="39" viewBox="0 0 30 39" fill="none"><path d="M7 17V10a8 8 0 0 1 16 0v7M3 17h24v19H3Z" stroke={C.green} strokeWidth="2.5"/><circle cx="15" cy="26" r="2.5" fill={C.green}/></svg><span style={{ fontSize: 27 }}>Private notes</span></Box>
    <svg width="1920" height="1080" style={{ position: 'absolute', inset: 0, opacity: ramp(f, 150, 170) }}><path d="M1265 797h335v-86" fill="none" stroke="#7D9572" strokeWidth="2" strokeDasharray="7 7"/><path d="m1592 723 8-12 8 12" stroke="#7D9572" strokeWidth="2" fill="none"/></svg>
    <Box style={{ left: 1540, top: 844, fontSize: 25, ...reveal(f, 176) }}>Reasoning</Box>
  </Frame>;
}

function Payoff() {
  return <CreatorCard closing/>;
}

const sceneComponents = [Opening, Question, Earlier, CatchUp, NoMagic, SharedInterface, WhyItWorks, Integrated, Payoff];

/** Visual-only layer: safe to compose with manifest-driven Audio sequences. */
export function Visuals() {
  const [fontHandle] = useState(() => delayRender('Loading local editorial fonts'));
  useEffect(() => {
    Promise.all([document.fonts.load('450 100px Newsreader'), document.fonts.load('400 30px "DM Sans"'), document.fonts.load('650 30px "DM Sans"'), document.fonts.load('400 30px Roboto'), document.fonts.load('750 112px Roboto')])
      .then(() => continueRender(fontHandle)).catch(cancelRender);
  }, [fontHandle]);
  return <AbsoluteFill style={{ background: C.paper }}>
    <style>{`
      @font-face { font-family: 'DM Sans'; src: url('${staticFile('fonts/DM-Sans.ttf')}') format('truetype'); font-weight: 100 1000; }
      @font-face { font-family: 'Newsreader'; src: url('${staticFile('fonts/Newsreader.ttf')}') format('truetype'); font-weight: 200 800; }
      @font-face { font-family: 'Roboto'; src: url('${staticFile('fonts/Roboto.ttf')}') format('truetype'); font-weight: 100 900; }
      * { box-sizing: border-box; }
    `}</style>
    {SCENES.map((s, i) => { const Scene = sceneComponents[i]; return <Sequence key={s.name} from={s.from} durationInFrames={s.duration} name={s.name}><Scene/></Sequence>; })}
  </AbsoluteFill>;
}

export function CampusCubbies() {
  return <AbsoluteFill><Visuals/>{/* Integrator: add the audio layer here. */}</AbsoluteFill>;
}

export function Root() {
  return <Composition id="CampusCubbies" component={CampusCubbies} durationInFrames={DURATION} fps={FPS} width={1920} height={1080}/>;
}

registerRoot(Root);
