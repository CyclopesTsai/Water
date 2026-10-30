#!/usr/bin/env python3
"""烘焙 textures/ 裡的所有紋理。需要 numpy、scipy、pillow。

    python3 tools/bake.py            # 全部重新產生
    python3 tools/bake.py clouds     # 只產生指定的紋理

波浪：用海洋波譜（k^-2 的振幅）在頻域產生隨機波，FFT 回空間域，天生無縫。
每張紋理只含朝同一方向前進的波，所以 CSS 把它往該方向平移就是正確的波動；
多張紋理線性疊加，就是不同方向的波互相干涉。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

OUT = Path(__file__).resolve().parent.parent / 'textures'
N = 1024


def modes(n=N):
    f = np.fft.fftfreq(n, 1 / n)
    kx, ky = np.meshgrid(f, f)
    return kx, ky, np.hypot(kx, ky)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def field(spectrum):
    return np.fft.ifft2(spectrum).real * spectrum.size


def spectrum(seed, heading, spread, lo, hi, power=2.0, n=N):
    """heading 是前進方向（度），0 為 +y（朝鏡頭）；lo、hi 是每張紋理的週期數。"""
    rng = np.random.default_rng(seed)
    kx, ky, k = modes(n)
    k = np.where(k == 0, 1, k)
    delta = (np.arctan2(kx, ky) - np.radians(heading) + np.pi) % (2 * np.pi) - np.pi
    directional = np.clip(np.cos(delta), 0, None) ** spread
    band = smoothstep(lo * .7, lo * 1.3, k) * (1 - smoothstep(hi * .7, hi * 1.3, k))
    noise = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    return noise * directional * band * k ** -power


def chop(H, strength):
    """Gerstner 式的水平位移：波峰變尖、波谷變寬。回傳位移場與變形後的高度。"""
    n = H.shape[0]
    kx, ky, k = modes(n)
    k = np.where(k == 0, 1, k)
    dx = field(-1j * kx / k * H)
    dy = field(-1j * ky / k * H)
    h = field(H)
    amount = strength / np.hypot(dx, dy).std()
    dx, dy = dx * amount, dy * amount
    y, x = np.mgrid[0:n, 0:n].astype(float)
    warped = map_coordinates(h, [y - dy, x - dx], order=1, mode='grid-wrap')
    return dx, dy, warped


def slope(h):
    hx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / 2
    hy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / 2
    return hx, hy


def save_gray(name, a, quality=82):
    Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)).save(
        OUT / f'{name}.webp', quality=quality, method=6)


def wave(name, seed, heading, lo=3, hi=48, sharp=4.5):
    """面向鏡頭的斜面看進深水偏暗，背向鏡頭的斜面反射低空偏亮：灰階就是沿視線的斜率。"""
    H = spectrum(seed, heading, spread=4, lo=lo, hi=hi)
    _, _, h = chop(H, strength=sharp)
    hx, hy = slope(h)
    shade = hy + .25 * hx
    save_gray(name, .5 + shade / shade.std() * .17)


def foam():
    """波面被水平位移擠到折疊（Jacobian 變小）的地方才會碎浪，白沫再往波後拖曳。"""
    H = spectrum(71, 0, spread=5, lo=3, hi=40)
    dx, dy, _ = chop(H, strength=11)
    xx = (np.roll(dx, -1, 1) - np.roll(dx, 1, 1)) / 2
    yy = (np.roll(dy, -1, 0) - np.roll(dy, 1, 0)) / 2
    xy = (np.roll(dx, -1, 0) - np.roll(dx, 1, 0)) / 2
    yx = (np.roll(dy, -1, 1) - np.roll(dy, 1, 1)) / 2
    jacobian = (1 + xx) * (1 + yy) - xy * yx
    edge = np.percentile(jacobian, 5.5)
    crest = smoothstep(edge + .1, edge - .12, jacobian)
    broken = field(spectrum(73, 0, spread=0, lo=8, hi=70, power=1.3))
    crest = crest * smoothstep(-.7, .9, broken / broken.std())

    # 波往 +y 走，白沫留在波峰後方（-y），用週期邊界的單邊指數模糊拖出尾巴
    kernel = np.zeros((N, N))
    kernel[-np.arange(90), 0] = np.exp(-np.arange(90) / 26.)
    trail = np.fft.ifft2(np.fft.fft2(crest) * np.fft.fft2(kernel / kernel.sum())).real
    trail = gaussian_filter(trail, (2, 7), mode='wrap')

    # 密度決定門檻：波峰處是整片白沫，拖尾則碎成網狀
    lace = field(spectrum(72, 0, spread=0, lo=16, hi=240, power=1.5))
    lace = 1 - np.abs(lace) / lace.std() / 2
    density = np.clip(gaussian_filter(crest, 1, mode='wrap') * 1.2 + trail * 3.6, 0, 1.15)
    foam = smoothstep(1.02 - density, 1.3 - density, lace) * smoothstep(.02, .22, density)
    save_gray('foam', foam)

    # 遠處的白沫不走濾鏡：斑塊先烘進透明度，CSS 只要平移一張圖
    gate = field(spectrum(74, 0, spread=0, lo=1, hi=5, power=1.5))
    alpha = foam * smoothstep(.1, .9, gate / gate.std())
    Image.fromarray((np.dstack([np.ones((N, N, 3)), alpha]) * 255 + .5).astype(np.uint8)).save(
        OUT / 'foam-far.webp', quality=70, alpha_quality=70, method=6)


def patch():
    """大尺度的斑塊：讓浪花在不同地方生滅，而不是整片同時出現。"""
    a = field(spectrum(81, 0, spread=0, lo=1, hi=6, power=1.5, n=256))
    save_gray('patch', smoothstep(.2, 1.5, a / a.std()), quality=70)


def glint():
    """太陽的鏡面反射：只有斜率剛好的小面才亮，所以是極小的亮點。"""
    H = spectrum(91, 0, spread=1, lo=10, hi=180, power=1.5)
    _, _, h = chop(H, strength=2.5)
    hx, hy = slope(h)
    hx, hy = hx / hx.std(), hy / hy.std()
    spark = np.exp(-((hy - 1.5) ** 2 + (hx * .7) ** 2) / (2 * .36 ** 2))
    save_gray('glint', spark ** 1.1, quality=80)


def volume(n, beta, seed):
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(n, 1 / n)
    fx, fy, fz = np.meshgrid(f, f, f, indexing='ij')
    k = np.sqrt(fx ** 2 + fy ** 2 + fz ** 2)
    k[0, 0, 0] = 1
    a = np.fft.ifftn(np.fft.fftn(rng.normal(size=(n, n, n))) * k ** (-beta / 2)).real
    return a / a.std()


def clouds():
    """體積雲：對雲層光線步進，往太陽再走幾步算自陰影，遠處融進大氣。"""
    width, height = 2600, 460
    focal, span_x, span_y = 200, 115.5, 40
    u = (np.arange(width) + .5) / width * 2 - 1
    v = 1 - (np.arange(height) + .5) / height
    ux, vy = np.meshgrid(u * span_x, v * span_y)
    d = np.stack([ux, np.full_like(ux, focal), vy + .35], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)

    n = 160
    shape = volume(n, 3.1, 5)
    detail = volume(n, 2.2, 6)
    period = 34.
    base, top = 2.6, 3.9

    def density(p):
        c = p / period * n
        sample = lambda vol: map_coordinates(vol, c.T, order=1, mode='grid-wrap')
        rel = (p[:, 2] - base) / (top - base)
        profile = smoothstep(0, .1, rel) * (1 - smoothstep(.45, 1, rel))
        value = sample(shape) * .82 + (1 - np.abs(sample(detail))) * .34 - .34
        return smoothstep(.66, 1.2, value * (.35 + .65 * profile) + (profile - 1) * .55)

    sun = np.array([-.45, .35, .82])
    sun /= np.linalg.norm(sun)
    sun_color = np.array([1.12, 1.08, 1.0])
    shade_low = np.array([.56, .64, .76])
    shade_high = np.array([.82, .88, .95])
    haze = np.array([.80, .885, .95])

    t0 = base / np.maximum(d[..., 2], 1e-3)
    t1 = np.minimum(top / np.maximum(d[..., 2], 1e-3), 120.)
    t0 = np.minimum(t0, 120.)
    steps = 96
    dt = (t1 - t0) / steps
    sigma = 6.5
    jitter = np.random.default_rng(7).random((height, width))  # 抖動起點，消除步進條紋

    transmit = np.ones((height, width))
    light = np.zeros((height, width, 3))
    distance = np.zeros((height, width))
    for i in range(steps):
        active = (transmit > .012) & (dt > 0)
        if not active.any():
            break
        t = t0[active] + (i + jitter[active]) * dt[active]
        p = d[active] * t[:, None]
        rho = density(p)
        hit = rho > .004
        if not hit.any():
            continue
        tau = np.zeros(hit.sum())
        q = p[hit]
        for j in range(1, 6):
            tau += density(q + sun * j * .16) * .16 * sigma
        rel = np.clip((q[:, 2] - base) / (top - base), 0, 1)[:, None]
        direct = np.exp(-tau)[:, None] * .62 + np.exp(-tau * .22)[:, None] * .38
        ambient = shade_low * (1 - rel) + shade_high * rel
        color = sun_color * direct * .86 + ambient * .78
        step = 1 - np.exp(-rho[hit] * sigma * dt[active][hit])
        gain = transmit[active][hit] * step

        index = np.flatnonzero(active.ravel())[hit]
        light.reshape(-1, 3)[index] += color * gain[:, None]
        distance.ravel()[index] += t[hit] * gain
        transmit.ravel()[index] *= 1 - step

    alpha = 1 - transmit
    safe = np.maximum(alpha, 1e-4)
    color = light / safe[..., None]
    far = np.clip(distance / safe / 110, 0, 1)[..., None]
    color = color * (1 - far ** 1.3) + haze * far ** 1.3
    alpha = alpha * (1 - far[..., 0] ** 2.4 * .75)
    rgba = np.dstack([np.clip(color, 0, 1), alpha])
    rgba = gaussian_filter(rgba, (.9, .9, 0))
    Image.fromarray((rgba * 255 + .5).astype(np.uint8)).save(
        OUT / 'clouds.webp', quality=88, alpha_quality=90, method=6)


JOBS = {
    # 方向是 CSS 位移向量的角度：(0,1)、(1,2)、(-1,2)、(1,1)、(-1,3)，循環才能剛好接回
    'wave-a': lambda: wave('wave-a', 11, 0),
    'wave-b': lambda: wave('wave-b', 12, 26.57),
    'wave-c': lambda: wave('wave-c', 13, -26.57),
    'wave-d': lambda: wave('wave-d', 14, 45, sharp=3),
    'wave-e': lambda: wave('wave-e', 15, -18.43, sharp=3),
    'foam': foam,
    'patch': patch,
    'glint': glint,
    'clouds': clouds,
}

if __name__ == '__main__':
    for name in sys.argv[1:] or JOBS:
        JOBS[name]()
        print(name, (OUT / f'{name}.webp').stat().st_size // 1024, 'KB')
