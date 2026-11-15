import json, os, wave, numpy as np
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR = 48000; tl = json.load(open('timeline.json')); D = tl['dur']; n = int(SR * D)
L = np.zeros(n, np.float32); rng = np.random.default_rng(3)
def add(sig, t, g):
    i = int(t * SR); j = min(n, i + len(sig))
    if 0 <= i < n: L[i:j] += sig[:j - i] * g
x = lambda s: np.arange(int(SR * s)) / SR
def kick(): t = x(.25); f = 110 * np.exp(-t * 18) + 42; return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
def hat(): t = x(.05); nz = rng.standard_normal(len(t)); nz = nz - np.convolve(nz, np.ones(6) / 6, 'same'); return nz * np.exp(-t * 70)
def bass(f, d=.24): t = x(d); s = np.sign(np.sin(2 * np.pi * f * t)) * .5 + np.sin(2 * np.pi * f * t); s = np.convolve(s, np.ones(30) / 30, 'same'); return s * np.minimum(1, (d - t) * 30) * np.exp(-t * 3)
def pluck(f, d=.5): t = x(d); return (np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 7)
def click(): t = x(.07); return rng.standard_normal(len(t)) * np.exp(-t * 300) * .6 + np.sin(2 * np.pi * 80 * t) * np.exp(-t * 50)
def whoosh(d=.3): m = int(SR * d); nz = np.convolve(rng.standard_normal(m), np.ones(30) / 30, 'same'); return nz * np.sin(np.linspace(0, np.pi, m)) ** 2 * 3
def hit(): t = x(.6); return np.sin(2 * np.pi * 55 * t) * np.exp(-t * 6) + rng.standard_normal(len(t)) * np.exp(-t * 25) * .3
beat = .5; roots = [55, 55, 65.4, 49]   # A, A, C, G (저음)
t = 1.6
while t < tl['end'][0] + 1.0:
    k = int((t - 1.6) / beat)
    add(kick(), t, .5); add(hat(), t + beat / 2, .12)
    r = roots[(k // 8) % 4]; add(bass(r), t, .22); add(bass(r), t + beat / 2, .16)
    if k % 2 == 0: add(pluck(r * 4 * (1.5 if k % 4 == 2 else 1)), t + beat * .75, .07)
    t += beat
add(hit(), .16, .6); add(whoosh(.25), .02, .3)                 # 표지 판이 박힐 때
for c in [tl['rundown_in'][0]] + [s['t0'] for s in tl['stories']] + [tl['recap'][0], tl['end'][0]]:
    add(whoosh(.3), c - .15, .25)                                 # 띠 지우개
for a in (tl['rundown_in'][0], tl['recap'][0]):
    for i in range(4): add(click(), a + .35 + .28 * i, .25)      # 순서 줄이 뒤집혀 들어올 때
for i in range(4): add(click(), tl['recap'][0] + 1.3 + .4 * i, .3)
for s in tl['stories']:
    add(click(), s['t0'], .25)
    if s.get('stamp'): add(hit(), s['t0'] + 2.6, .45)
    if s['kind'] == 'checks':
        for i in range(3): add(click(), s['t0'] + 2.2 + .7 * i, .3)
add(hit(), tl['end'][0], .5)
fade = np.ones(n); fe = int(SR * 1.0); fade[-fe:] = np.linspace(1, 0, fe); L *= fade
L = L / (np.abs(L).max() / .9)
st = np.stack([L, L], 1)
o = wave.open('mix.wav', 'w'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR); o.writeframes((st * 32767).astype(np.int16).tobytes()); o.close(); print('ok')
