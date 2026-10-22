"""Gera a base dos eleitos do NOVO (2024 e 2026) para escolher o gabinete e o Meu parlamentar.

Uso: python gerar_eleitos.py <index.html> [<pasta do TSE>]

Lê as candidaturas e a votação do TSE da pasta (padrão: D:\\Macros\\CIE\\data\\raw\\tse, a base da
CIE); o que não estiver lá é baixado do TSE. As fotos de 2026 vêm dos zips por UF da CIE; as de
2024 são tiradas dos zips do TSE (cerca de 2 GB por UF) com leituras parciais (HTTP Range), só
dos eleitos. Grava o bloco JSON <script id="dados-eleitos"> logo depois de dados-parl, para a página
juntar as duas bases antes da primeira tela. Vices e suplentes recebem os votos da chapa do titular.

Sem CPF, e-mail, título de eleitor ou outro dado pessoal além do que a ficha pública já mostra
(nome civil, nome de urna, cargo, município, número, votos, situação, ocupação e foto).
"""
import base64, csv, gzip, io, json, os, re, sys, urllib.request, zipfile, collections
from PIL import Image

IDX = sys.argv[1]
TSE = sys.argv[2] if len(sys.argv) > 2 else r'D:\Macros\CIE\data\raw\tse'
CDN = 'https://cdn.tse.jus.br/estatistica/sead'
ELEITO = {'ELEITO': 'Eleito', 'ELEITO POR QP': 'Eleito por QP', 'ELEITO POR MÉDIA': 'Eleito por média'}
CARGO = {'VEREADOR': ('Vereador', 'Vereadora'), 'PREFEITO': ('Prefeito', 'Prefeita'), 'VICE-PREFEITO': ('Vice-prefeito', 'Vice-prefeita'),
         'DEPUTADO ESTADUAL': ('Deputado estadual', 'Deputada estadual'), 'DEPUTADO DISTRITAL': ('Deputado distrital', 'Deputada distrital'),
         'DEPUTADO FEDERAL': ('Deputado federal', 'Deputada federal'), 'SENADOR': ('Senador', 'Senadora'), 'GOVERNADOR': ('Governador', 'Governadora'),
         'VICE-GOVERNADOR': ('Vice-governador', 'Vice-governadora'), '1º SUPLENTE': ('1º suplente de senador', '1ª suplente de senador'),
         '2º SUPLENTE': ('2º suplente de senador', '2ª suplente de senador')}
MINUSC = {'da', 'de', 'do', 'das', 'dos', 'e', "d'"}


def tc(s):
    """Nome próprio: 'SANTA BÁRBARA D'OESTE' -> 'Santa Bárbara d'Oeste', 'PAU-BRASIL' -> 'Pau-Brasil'."""
    def palavra(w, i):
        if w in MINUSC and i: return w
        if re.match(r"d['’]\w", w): return w[:2] + palavra(w[2:], 1)
        return '-'.join(x if (x in MINUSC and j) else x[:1].upper() + x[1:] for j, x in enumerate(w.split('-')))
    return ' '.join(palavra(w, i) for i, w in enumerate((s or '').lower().split()))


def local_ou_baixa(rel, url):
    p = os.path.join(TSE, rel)
    if os.path.exists(p): return p
    os.makedirs(os.path.dirname(p), exist_ok=True)
    print('baixando', url, flush=True)
    urllib.request.urlretrieve(url, p)
    return p


def linhas_brasil(zip_path, prefixo):
    z = zipfile.ZipFile(zip_path)
    nome = next(n for n in z.namelist() if n.startswith(prefixo) and n.endswith('BRASIL.csv'))
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding='latin-1'), delimiter=';')


class RemotoRange(io.RawIOBase):
    """Arquivo remoto lido por partes (HTTP Range), para o zipfile abrir só o índice e as fotos pedidas."""
    def __init__(self, url):
        self.url, self.pos = url, 0
        self.tam = int(urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=60).headers['Content-Length'])
        self.cache = {}
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.tam + off
        return self.pos
    def readinto(self, b):
        n = min(len(b), self.tam - self.pos)
        if n <= 0: return 0
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{self.pos + n - 1}'})
        dados = urllib.request.urlopen(req, timeout=120).read()
        b[:len(dados)] = dados; self.pos += len(dados)
        return len(dados)


def foto_uri(raw):
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    im.thumbnail((92, 128))
    out = io.BytesIO(); im.save(out, 'JPEG', quality=72, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()


html = open(IDX, encoding='utf-8', newline='').read()
ja = {p['sq'] for p in json.loads(re.search(r'<script type="application/json" id="dados-parl">(.*?)</script>', html, re.S).group(1))['pessoas']}

pessoas = {}
for ano in (2024, 2026):
    cand = local_ou_baixa(f'candidatos/{ano}/consulta_cand_{ano}.zip', f'{CDN}/odsele/consulta_cand/consulta_cand_{ano}.zip')
    sel, titulares = {}, {}
    for r in linhas_brasil(cand, f'consulta_cand_{ano}'):
        if r['DS_CARGO'] in ('PREFEITO', 'GOVERNADOR', 'SENADOR') and r['DS_SIT_TOT_TURNO'] in ELEITO:
            titulares[(r['SG_UE'], r['DS_CARGO'], r['NR_CANDIDATO'])] = r  # cabeça de chapa eleito, de qualquer partido
        if r['SG_PARTIDO'] != 'NOVO' or r['DS_SIT_TOT_TURNO'] not in ELEITO: continue
        sq = r['SQ_CANDIDATO']
        if sq in sel and int(sel[sq]['NR_TURNO']) >= int(r['NR_TURNO']): continue
        sel[sq] = r
    TIT = {'VICE-PREFEITO': 'PREFEITO', 'VICE-GOVERNADOR': 'GOVERNADOR', '1º SUPLENTE': 'SENADOR', '2º SUPLENTE': 'SENADOR'}
    chapa = {sq: titulares.get((r['SG_UE'], TIT[r['DS_CARGO']], r['NR_CANDIDATO'])) for sq, r in sel.items() if r['DS_CARGO'] in TIT}
    chapa = {k: v for k, v in chapa.items() if v}
    tit_turno = {t['SQ_CANDIDATO']: t['NR_TURNO'] for t in chapa.values()}
    vot = collections.Counter()
    tz = local_ou_baixa(f'votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip', f'{CDN}/odsele/votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip')
    for r in linhas_brasil(tz, f'votacao_candidato_munzona_{ano}'):
        sq = r['SQ_CANDIDATO']; c = sel.get(sq)
        if (c and r['NR_TURNO'] == c['NR_TURNO']) or tit_turno.get(sq) == r['NR_TURNO']: vot[sq] += int(r['QT_VOTOS_NOMINAIS'] or 0)
    for sq, r in sel.items():
        f = r['DS_GENERO'] == 'FEMININO'
        cargo = CARGO.get(r['DS_CARGO'], (tc(r['DS_CARGO']),) * 2)[1 if f else 0]
        municipal = ano == 2024
        pessoas[sq] = {'sq': sq, 'urna': r['NM_URNA_CANDIDATO'], 'civil': r['NM_CANDIDATO'], 'cargo': cargo, 'uf': r['SG_UF'],
                       'mun': tc(r['NM_UE']) if municipal else '', 'partido': 'NOVO', 'numero': r['NR_CANDIDATO'],
                       'sit': ELEITO[r['DS_SIT_TOT_TURNO']], 'votos': vot.get(sq, 0), 'ocupacao': tc(r['DS_OCUPACAO']), 'ano': ano,
                       'turno': int(r['NR_TURNO']), 'g': 'F' if f else 'M', 'ja': sq in ja}
        if r['DS_CARGO'] in TIT:  # vice ou suplente: os votos são da chapa do titular
            pessoas[sq]['votos'] = None
            t = chapa.get(sq)
            if t: pessoas[sq]['chapa'] = {'nome': tc(t['NM_URNA_CANDIDATO']), 'partido': t['SG_PARTIDO'], 'votos': vot.get(t['SQ_CANDIDATO'], 0)}
    print(ano, collections.Counter(p['cargo'] for p in pessoas.values() if p['ano'] == ano), flush=True)

# fotos
faltam = collections.defaultdict(list)
for p in pessoas.values(): faltam[(p['ano'], p['uf'])].append(p)
for (ano, uf), L in sorted(faltam.items()):
    if ano == 2026:
        z = zipfile.ZipFile(local_ou_baixa(f'candidatos/2026/fotos_zip/foto_cand2026_{uf}_div.zip', f'{CDN}/eleicoes/eleicoes2026/fotos/foto_cand2026_{uf}_div.zip'))
    else:
        z = zipfile.ZipFile(io.BufferedReader(RemotoRange(f'{CDN}/eleicoes/eleicoes2024/fotos/foto_cand2024_{uf}_div.zip'), buffer_size=1 << 16))
    nomes = {re.sub(r'\D', '', n.rsplit('/', 1)[-1].split('_')[0]): n for n in z.namelist()}
    ok = 0
    for p in L:
        n = nomes.get(p['sq'])
        if n:
            try: p['foto'] = foto_uri(z.read(n)); ok += 1
            except Exception as e: print('foto com erro', p['sq'], e)
    print(f'fotos {ano} {uf}: {ok}/{len(L)}', flush=True)

out = {'geradoEm': __import__('datetime').date.today().isoformat(), 'fonte': 'TSE: candidaturas, votação por município e zona e fotos de 2024 e 2026',
       'pessoas': sorted(pessoas.values(), key=lambda p: (-p['ano'], p['cargo'], p['uf'], p.get('mun', ''), p['urna']))}
js = json.dumps(out, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
html = re.sub(r'\n?<script type="[^"]+" id="dados-eleitos">.*?</script>', '', html, count=1, flags=re.S)  # versão anterior, onde estiver
i = html.index('</script>', html.index('<script type="application/json" id="dados-parl">')) + len('</script>')
html = html[:i] + '\n<script type="application/json" id="dados-eleitos">' + js + '</script>' + html[i:]
open(IDX, 'w', encoding='utf-8', newline='').write(html)
print('eleitos:', len(pessoas), '| já na base:', sum(p['ja'] for p in pessoas.values()), '| com foto:', sum('foto' in p for p in pessoas.values()),
      '| embutido', len(js) // 1024, 'KB')
