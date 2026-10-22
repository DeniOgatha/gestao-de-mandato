"""Confere se cada local de votação (l-UF.json) cai dentro do próprio município.

Uso: python locais_geo.py <pasta mapa-eleitoral> [--corrigir]
Sem --corrigir só relata. Com --corrigir, o local fora do município (além da
tolerância) é levado para um ponto dentro do município e ganha o 9º campo = 1
("posição aproximada"), que o mapa mostra no tooltip.
"""
import json, math, os, sys, glob

TOL_KM = 1.5   # contorno do IBGE é simplificado: borda de rio/litoral pode deixar a escola um pouco de fora

pasta = sys.argv[1]
corrigir = "--corrigir" in sys.argv
G = json.load(open(os.path.join(pasta, "geo.json"), encoding="utf-8"))
ESC = G.get("esc", 10000)

def anel(d):
    out, a, b = [], 0, 0
    for k in range(0, len(d), 2):
        a += d[k]; b += d[k + 1]; out.append((a / ESC, b / ESC))
    return out

MP = [[[anel(r) for r in poly] for poly in (m or [])] for m in G["mp"]]
BOX = []
for polys in MP:
    pts = [p for poly in polys for p in poly[0]]
    BOX.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)) if pts else None)

def dentro_anel(lat, lng, r):
    ok = False
    for i in range(len(r)):
        (y1, x1), (y2, x2) = r[i], r[i - 1]
        if (y1 > lat) != (y2 > lat) and lng < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            ok = not ok
    return ok

def dentro(lat, lng, mi):
    b = BOX[mi]
    if not b or not (b[0] <= lat <= b[2] and b[1] <= lng <= b[3]): return False
    for poly in MP[mi]:
        if dentro_anel(lat, lng, poly[0]) and not any(dentro_anel(lat, lng, h) for h in poly[1:]):
            return True
    return False

def dist_km(lat, lng, mi):
    """distância do ponto à borda do município (aprox. plana, boa para poucos km)"""
    kx = 111.32 * math.cos(math.radians(lat)); ky = 110.57
    best = 1e9
    for poly in MP[mi]:
        r = poly[0]
        for i in range(len(r)):
            (ay, ax), (by, bx) = r[i - 1], r[i]
            px, py = (lng - ax) * kx, (lat - ay) * ky
            vx, vy = (bx - ax) * kx, (by - ay) * ky
            t = max(0, min(1, (px * vx + py * vy) / (vx * vx + vy * vy or 1)))
            best = min(best, math.hypot(px - t * vx, py - t * vy))
    return best

def centro(mi):
    """centroide do maior polígono; se cair fora (município côncavo), o ponto interno mais central de uma grade"""
    melhor = None
    for poly in MP[mi]:
        r = poly[0]; a = x = y = 0
        for i in range(len(r)):
            (y1, x1), (y2, x2) = r[i], r[(i + 1) % len(r)]
            f = x1 * y2 - x2 * y1; a += f; x += (x1 + x2) * f; y += (y1 + y2) * f
        if a and (not melhor or abs(a) > melhor[0]): melhor = (abs(a), y / (3 * a), x / (3 * a))
    lat, lng = melhor[1], melhor[2]
    if dentro(lat, lng, mi): return lat, lng
    b = BOX[mi]; cand = []
    for i in range(1, 30):
        for j in range(1, 30):
            la, lo = b[0] + (b[2] - b[0]) * i / 30, b[1] + (b[3] - b[1]) * j / 30
            if dentro(la, lo, mi): cand.append((dist_km(la, lo, mi), la, lo))
    _, la, lo = max(cand)
    return la, lo

def espalhar(lat, lng, k, mi):
    """vários locais realocados no mesmo município: espiral pequena em volta do centro, sempre dentro"""
    for raio in (0.004, 0.003, 0.002, 0.001, 0):
        ang = k * 2.39996   # ângulo de ouro
        r = raio * math.sqrt(k + 1) if raio else 0
        la, lo = lat + r * math.sin(ang), lng + r * math.cos(ang)
        if dentro(la, lo, mi): return la, lo
    return lat, lng

total = fora = movidos = 0
sem_contorno = set()
exemplos = []
for arq in sorted(glob.glob(os.path.join(pasta, "20*", "l-*.json"))):
    L = json.load(open(arq, encoding="utf-8"))
    n_mov = 0; por_mun = {}
    for l in L["locais"]:
        total += 1
        lat, lng, mi = l[0] / ESC, l[1] / ESC, l[4]
        if len(l) > 8 and l[8]: continue   # já realocado numa rodada anterior
        if not BOX[mi]: sem_contorno.add(G["mun"][mi][2] + "/" + G["mun"][mi][3]); continue   # município sem contorno: não há como conferir
        if dentro(lat, lng, mi): continue
        d = dist_km(lat, lng, mi)
        if d <= TOL_KM: continue
        fora += 1
        if len(exemplos) < 15: exemplos.append(f"{os.path.basename(os.path.dirname(arq))} {L['uf']} {G['mun'][mi][2]}: {l[2]} a {d:.0f} km do município")
        if corrigir:
            k = por_mun.get(mi, 0); por_mun[mi] = k + 1
            la, lo = espalhar(*centro(mi), k, mi)
            l[0], l[1] = round(la * ESC), round(lo * ESC)
            while len(l) < 8: l.append(0)
            if len(l) == 8: l.append(1)
            else: l[8] = 1
            n_mov += 1
    if corrigir and n_mov:
        movidos += n_mov
        with open(arq, "w", encoding="utf-8") as f:
            json.dump(L, f, ensure_ascii=False, separators=(",", ":"))
print(f"{total} locais conferidos; {fora} fora do próprio município (além de {TOL_KM} km); {movidos} realocados")
print("\n".join(exemplos))
