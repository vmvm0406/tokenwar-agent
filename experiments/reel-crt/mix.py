import json, os, wave, numpy as np
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
tl = json.load(open('timeline.json'))
w = wave.open('voice.wav'); v = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
n = len(v); fx = np.zeros(n, np.float32); rng = np.random.default_rng(7)
def add(sig, t, g):
    i = max(0, int(t * SR)); j = min(n, i + len(sig))
    if i < n: fx[i:j] += sig[:j - i] * g
def env(ms, k): x = np.arange(int(SR * ms / 1000)) / SR; return np.exp(-x * k)
def click():  # 짧고 단단한 클릭 + 낮은 쿵
    nz = rng.standard_normal(int(SR * .012)) * env(12, 400)
    x = np.arange(int(SR * .09)) / SR; th = np.sin(2 * np.pi * 70 * x) * np.exp(-x * 45)
    out = np.zeros(len(th)); out[:len(nz)] += nz * .5; return out + th * .9
def tick():
    x = np.arange(int(SR * .006)) / SR; return np.sin(2 * np.pi * 2400 * x) * np.exp(-x * 900)
def whoosh(dur=.35):
    m = int(SR * dur); nz = rng.standard_normal(m); f = np.convolve(nz, np.ones(40) / 40, 'same')
    e = np.sin(np.linspace(0, np.pi, m)) ** 2; return f * e * 3
def key():   # 기계식 키 소리: 짧은 플라스틱 딸깍
    t = np.arange(int(SR * .02)) / SR
    return rng.standard_normal(len(t)) * np.exp(-t * 600) * .5 + np.sin(2 * np.pi * 1900 * t) * np.exp(-t * 500) * .3
for b in tl['term']:
    at = b['t0'] + .05
    for L in b['lines']:
        k = L[0]
        if k in ('q', 'd', 'inv'):
            cps = 30 if k == "inv" else 38; nc = len(L[1])
            for i in range(nc):
                if L[1][i] != ' ': add(key(), at + i / cps, .10 if k != 'inv' else .16)
            at = at + nc / cps + (.15 if k == 'inv' else .12)
        elif k in ('bar', 'pbar'):
            st = b['t0'] + L[4]
            for t in np.arange(st, st + .7, .05): add(tick(), t, .10)
        elif k == 'stamp':
            for j in range(3): add(tick() * 2, b['t0'] + L[2] + j * .24, .25)
    if b.get('big'):
        st = b['t0'] + b['big']['t']
        for t in np.arange(st, st + .5, .045): add(tick(), t, .12)
mix = v + fx[:, None]
mix = mix / max(1.0, np.abs(mix).max() / .95)
o = wave.open('mix.wav', 'w'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR)
o.writeframes((mix * 32767).astype(np.int16).tobytes()); o.close(); print('mix ok', n / SR)
