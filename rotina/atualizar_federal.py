"""Atualiza os dados de "Meu parlamentar" (#federal) direto das fontes públicas.

Uso: python atualizar_federal.py <index.html> <pasta de saída>

Gera na pasta de saída:
  camara.b64   proposições da Câmara (bloco <script id="dados-camara">)
  federal.b64  cota parlamentar e notícias (bloco <script id="dados-federal">)
  status.json  resumo da execução

Fontes, baixadas a cada execução:
  Câmara  dadosabertos.camara.leg.br: proposições, autores e temas; API de deputados
  Câmara  camara.leg.br/cotas: cota parlamentar (CEAP)
  Senado  senado.leg.br/transparencia: cota parlamentar (CEAPS)
  Google Notícias: feed público por parlamentar, últimos 60 dias

Se a pasta de saída já tem uma execução anterior, ela serve de base de comparação:
quedas grandes nos totais abortam sem gravar nada, e notícias que falharem ficam
com as da execução anterior. Sem execução anterior, a base é o próprio index.html.
"""
import base64, csv, gzip, io, json, os, re, sys, tempfile, time, unicodedata, urllib.parse, urllib.request, zipfile
import collections, concurrent.futures as cf, xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

csv.field_size_limit(10**9)
IDX, OUT = sys.argv[1], sys.argv[2]
HOJE = date.today()
ANO = HOJE.year
ACOMP = ['156190', '220705']  # parlamentares acompanhados com passagem pela Câmara (lista completa de proposições)
CAMARA = 'https://dadosabertos.camara.leg.br'
UA = {'User-Agent': 'Mozilla/5.0 (gestao-de-mandato; rotina diaria)'}
TMP = tempfile.mkdtemp(prefix='federal-')
os.makedirs(OUT, exist_ok=True)


def baixar(url, tentativas=4):
    for t in range(tentativas):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()
        except Exception as e:
            if t == tentativas - 1: raise RuntimeError(f'falhou: {url} ({e})')
            time.sleep(5 * (t + 1))


def arquivo(url, nome):
    """Baixa para o disco (os CSVs anuais passam de 40 MB) e devolve o caminho."""
    p = os.path.join(TMP, nome)
    with open(p, 'wb') as f: f.write(baixar(url))
    return p


def anual(url, nome, y):
    """Arquivo de um ano. O do ano corrente pode ainda não existir (início de janeiro): fica sem ele, com aviso."""
    try:
        return arquivo(url, nome)
    except RuntimeError as e:
        if y != ANO: raise
        status['avisos'].append(f'{url.rsplit("/", 1)[-1]} ainda não está disponível: o ano {y} ficou sem esse arquivo')
        return None


def ler_csv(caminho, enc='utf-8-sig'):
    with open(caminho, encoding=enc, newline='') as f:
        yield from csv.DictReader(f, delimiter=';')


def bloco(html, id_):
    m = re.search(rf'<script type="[^"]+" id="{id_}">(.*?)</script>', html, re.S)
    return m.group(1).strip() if m else ''


def de_b64(s):
    return json.loads(gzip.decompress(base64.b64decode(s))) if s else None


def para_b64(o):
    raw = json.dumps(o, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(gzip.compress(raw, 9, mtime=0)).decode(), len(raw)


def anterior(nome, id_):
    p = os.path.join(OUT, nome)
    if os.path.exists(p): return de_b64(open(p, encoding='ascii').read().strip())
    return de_b64(bloco(html, id_))


def norm(s):
    s = unicodedata.normalize('NFD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.upper()).strip()


html = open(IDX, encoding='utf-8').read()
PARL = json.loads(bloco(html, 'dados-parl'))
PESSOAS = PARL['pessoas']
DEPS = sorted({p['camara']['id'] for p in PESSOAS if p.get('camara')})
DSET = set(DEPS)
CAM_ANT, FED_ANT = anterior('camara.b64', 'dados-camara'), anterior('federal.b64', 'dados-federal')
status = {'execucao': HOJE.isoformat(), 'avisos': []}

# ---------- proposições da Câmara ----------
# a mesma proposição aparece em vários arquivos anuais; fica a de status mais recente
props = {}
for y in range(2019, ANO + 1):
    c = anual(f'{CAMARA}/arquivos/proposicoes/csv/proposicoes-{y}.csv', f'p{y}.csv', y)
    if not c: continue
    for r in ler_csv(c):
        i = r['id']; d = r['ultimoStatus_dataHora'] or ''
        if i in props and props[i]['ud'] >= d: continue
        props[i] = {'t': r['siglaTipo'], 'n': r['numero'], 'a': r['ano'], 'e': r['ementa'].strip(), 'ap': (r['dataApresentacao'] or '')[:10], 'ud': d,
                    's': r['ultimoStatus_descricaoSituacao'].strip(), 'o': r['ultimoStatus_siglaOrgao'].strip(), 'rg': r['ultimoStatus_regime'].strip(),
                    'tr': r['ultimoStatus_descricaoTramitacao'].strip()}
    os.remove(c)
print('proposições:', len(props), flush=True)
aut = collections.defaultdict(dict)  # deputado -> {proposição: ordem de assinatura}
for y in range(2019, ANO + 1):
    c = anual(f'{CAMARA}/arquivos/proposicoesAutores/csv/proposicoesAutores-{y}.csv', f'a{y}.csv', y)
    if not c: continue
    for r in ler_csv(c):
        d = r['idDeputadoAutor']
        if d in DSET and r['idProposicao'] in props:
            o = int(r['ordemAssinatura'] or 99); aut[d][r['idProposicao']] = min(o, aut[d].get(r['idProposicao'], 99))
    os.remove(c)
temas = collections.defaultdict(set)
for y in range(2023, ANO + 1):
    c = anual(f'{CAMARA}/arquivos/proposicoesTemas/csv/proposicoesTemas-{y}.csv', f't{y}.csv', y)
    if not c: continue
    for r in ler_csv(c):
        temas[r['uriProposicao'].rsplit('/', 1)[-1]].add(r['tema'].strip())
    os.remove(c)

# a base tem tramitações agendadas para depois de hoje: a referência nunca passa da data de geração
REF = min(max(p['ud'] for p in props.values() if p['ud'])[:10], HOJE.isoformat())
ref = date.fromisoformat(REF)
FIM = {'Arquivada', 'Aguardando Remessa ao Arquivo', 'Tramitação Finalizada', 'Transformado em Norma Jurídica', 'Transformado em nova proposição', 'Retirado pelo(a) Autor(a)', 'Devolvida ao(à) Autor(a)', 'Perdeu a Eficácia'}
APROV = {'Aguardando Envio ao Senado Federal', 'Aguardando Apreciação pelo Senado Federal', 'Aguardando Envio ao Executivo', 'Aguardando Sanção', 'Aguardando Autógrafos na Mesa', 'Enviada ao Congresso Nacional'}
def dias(d): return (ref - date.fromisoformat(d[:10])).days if d else 9999
def tram(p): return bool(p['s']) and p['s'] not in FIM and p['s'] != '<Não Definido>'

dic = {k: [] for k in ('s', 'rg', 'tema', 'o', 'tr')}; pos = {k: {} for k in dic}
def ix(k, v):
    if v not in pos[k]: pos[k][v] = len(dic[k]); dic[k].append(v)
    return pos[k][v]

ag, lista = {}, {}
for d in DEPS:
    A = aut.get(d, {}); L = [(i, props[i], o) for i, o in A.items()]
    if not L: continue
    T = [p for _, p, _ in L if tram(p)]
    ctipo = collections.Counter(p['t'] for _, p, _ in L)
    cano = collections.Counter(('sem' if p['a'] in ('', '0') else 'antes' if p['a'] < '2019' else p['a']) for _, p, _ in L)
    csit = collections.Counter(p['s'] for _, p, _ in L if p['s'] and p['s'] != '<Não Definido>')
    ctema = collections.Counter(t for i, _, _ in L for t in temas.get(i, ()))
    ult = sorted(L, key=lambda x: x[1]['ud'], reverse=True)[:10]
    ag[d] = {
        'k': {'total': len(L), 'tram': len(T), 'aprov': sum(p['s'] in APROV for _, p, _ in L), 'norma': sum(p['s'] == 'Transformado em Norma Jurídica' for _, p, _ in L),
              'arq': sum(p['s'] in ('Arquivada', 'Aguardando Remessa ao Arquivo') for _, p, _ in L), 'mov30': sum(dias(p['ud']) <= 30 for _, p, _ in L),
              'p180': sum(dias(p['ud']) > 180 for p in T), 'p365': sum(dias(p['ud']) > 365 for p in T), 'urg': sum(p['rg'].startswith('Urgência') for p in T),
              'ano': sum(p['a'] == str(ref.year) for _, p, _ in L), 'princ': sum(o == 1 for *_, o in L), 'coaut': sum(o > 1 for *_, o in L)},
        'tipo': ctipo.most_common(12), 'ano': sorted(cano.items(), key=lambda kv: {'sem': '0', 'antes': '1'}.get(kv[0], kv[0])), 'sit': csit.most_common(12), 'tema': ctema.most_common(15),
        'ult': [[f"{p['t']} {p['n']}/{p['a']}", p['ud'][:10], p['tr'] or p['s'] or '—', i] for i, p, _ in ult],
    }
    if d in ACOMP:
        lista[d] = [[int(i), p['t'], p['n'], int(p['a'] or 0), (p['e'] if len(p['e']) <= 240 else p['e'][:239].rstrip() + '…'), p['ap'], p['ud'][:10], ix('s', p['s']), ix('o', p['o']), ix('rg', p['rg']), ix('tr', p['tr']),
                     sorted(ix('tema', t) for t in temas.get(i, ())), 1 if o == 1 else 0] for i, p, o in sorted(L, key=lambda x: x[1]['ud'], reverse=True)]

info = {}  # cadastro e gabinete dos acompanhados, sem CPF; se a API falhar fica o da execução anterior
for d in ACOMP:
    try:
        j = json.loads(baixar(f'{CAMARA}/api/v2/deputados/{d}'))['dados']; u = j['ultimoStatus']; g = u.get('gabinete') or {}
        info[d] = {'nome': u['nome'], 'civil': j['nomeCivil'], 'partido': u['siglaPartido'], 'uf': u['siglaUf'], 'leg': u['idLegislatura'], 'situacao': u.get('situacao'), 'condicao': u.get('condicaoEleitoral'),
                   'foto': u.get('urlFoto'), 'gabinete': g.get('nome'), 'predio': g.get('predio'), 'andar': g.get('andar'), 'telefone': g.get('telefone'), 'email': g.get('email'),
                   'redes': j.get('redeSocial') or [], 'site': j.get('urlWebsite'), 'nasc': j.get('dataNascimento'), 'municipio': j.get('municipioNascimento'), 'ufNasc': j.get('ufNascimento'), 'escolaridade': j.get('escolaridade')}
    except Exception as e:
        if CAM_ANT and d in CAM_ANT.get('info', {}): info[d] = CAM_ANT['info'][d]
        status['avisos'].append(f'API da Câmara falhou para o deputado {d}: {e}')

cam = {'ref': REF, 'geradoEm': HOJE.isoformat(), 'dic': dic, 'ag': ag, 'lista': lista, 'info': info}

# ---------- cota parlamentar ----------
cota, cota_cat = collections.defaultdict(lambda: collections.defaultdict(float)), collections.defaultdict(collections.Counter)
for y in range(2023, ANO + 1):
    c = anual(f'https://www.camara.leg.br/cotas/Ano-{y}.csv.zip', f'c{y}.zip', y)
    if not c: continue
    z = zipfile.ZipFile(c)
    with z.open(f'Ano-{y}.csv') as fb:
        for r in csv.DictReader(io.TextIOWrapper(fb, encoding='utf-8-sig'), delimiter=';'):
            did = r['ideCadastro']
            if did not in DSET: continue
            v = float((r['vlrLiquido'] or '0').replace(',', '.'))
            cota[did][y] += v; cota_cat[did][r['txtDescricao'].capitalize()] += v
    z.close(); os.remove(c)
sen_nomes = {norm(p['senado']['nome']): p['sq'] for p in PESSOAS if p.get('senado')}
cota_sen = collections.defaultdict(lambda: collections.defaultdict(float))
for y in range(2023, ANO + 1):
    c = anual(f'https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{y}.csv', f's{y}.csv', y)
    if not c: continue
    with open(c, encoding='latin-1', newline='') as f:
        next(f)  # primeira linha é a data de atualização
        for r in csv.DictReader(f, delimiter=';'):
            k = sen_nomes.get(norm(r['SENADOR']))
            if k: cota_sen[k][y] += float((r['VALOR_REEMBOLSADO'] or '0').replace(',', '.'))
    os.remove(c)
fcota = {}
for p in PESSOAS:
    o = {}
    if p.get('camara'):
        did = p['camara']['id']
        o['c'] = {'cota': {str(y): round(v) for y, v in sorted(cota[did].items())}, 'cotaCat': [[c, round(v)] for c, v in cota_cat[did].most_common(3)]}
    if p.get('senado'):
        o['s'] = {str(y): round(v) for y, v in sorted(cota_sen[p['sq']].items())}
    if o: fcota[p['sq']] = o

# Os arquivos anuais às vezes voltam sem parte das despesas (em 22/10/2026 a Câmara republicou
# 2023 a 2025 sem as passagens aéreas do SIGEPA). Um ano cujo total encolhe mais de 2% fica com
# os valores da execução anterior; os demais anos seguem atualizados.
def cota_ant(p):
    o = (FED_ANT or {}).get('cota', {}).get(p['sq'])
    if o: return o
    return {**({'c': {'cota': p['camara'].get('cota', {}), 'cotaCat': p['camara'].get('cotaCat', [])}} if p.get('camara') else {}),
            **({'s': p['senado'].get('cota', {})} if p.get('senado') else {})}
ANT = {p['sq']: cota_ant(p) for p in PESSOAS}
pega = {'c': lambda o: (o.get('c') or {}).get('cota', {}), 's': lambda o: o.get('s') or {}}
for fonte, nome in (('c', 'Câmara'), ('s', 'Senado')):
    mantidos = []
    for y in map(str, range(2023, ANO + 1)):
        novo = sum(pega[fonte](o).get(y, 0) for o in fcota.values())
        velho = sum(pega[fonte](o).get(y, 0) for o in ANT.values())
        if velho > 0 and novo < velho * 0.98:
            mantidos.append(y)
            status['avisos'].append(f'cota da {nome} {y}: fonte trouxe R$ {novo:,.0f} contra R$ {velho:,.0f} antes; ficaram os valores anteriores')
            for sq, o in fcota.items():
                if fonte in o:
                    v = pega[fonte](ANT.get(sq, {})).get(y)
                    alvo = o['c']['cota'] if fonte == 'c' else o['s']
                    if v is None: alvo.pop(y, None)
                    else: alvo[y] = v
    for o in fcota.values():
        if fonte in o:
            if fonte == 'c': o['c']['cota'] = dict(sorted(o['c']['cota'].items()))
            else: o['s'] = dict(sorted(o['s'].items()))
    if fonte == 'c' and mantidos:  # as categorias somam todos os anos: com um ano incompleto, ficam as anteriores
        for sq, o in fcota.items():
            if 'c' in o: o['c']['cotaCat'] = (ANT.get(sq, {}).get('c') or {}).get('cotaCat', o['c']['cotaCat'])

# ---------- notícias ----------
CORTE = (HOJE - timedelta(days=60)).isoformat()
NOT_ANT = (FED_ANT or {}).get('noticias') or PARL.get('noticias') or {}

def nome_busca(p):
    for k in ('camara', 'senado'):
        if p.get(k) and p[k].get('nome'): return p[k]['nome']
    return p['urna'].title()

def buscar(p):
    q = urllib.parse.quote(f'"{nome_busca(p)}" when:60d')
    try:
        xml = baixar(f'https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419', tentativas=3)
    except Exception:
        return p['sq'], None
    try: raiz = ET.fromstring(xml)
    except ET.ParseError: return p['sq'], None  # página de bloqueio ou erro em vez do feed
    itens = []
    for it in raiz.iter('item'):
        fonte, titulo = it.findtext('source') or '', it.findtext('title') or ''
        if fonte and titulo.endswith(' - ' + fonte): titulo = titulo[: -len(fonte) - 3]
        try: data = parsedate_to_datetime(it.findtext('pubDate')).strftime('%Y-%m-%d')
        except Exception: data = ''
        itens.append({'t': titulo, 'f': fonte, 'd': data, 'u': it.findtext('link')})
    itens.sort(key=lambda x: x['d'], reverse=True)
    vistos, saida = set(), []
    for x in itens:  # tira manchetes repetidas em veículos diferentes
        k = x['t'].lower()[:60]
        if k in vistos: continue
        vistos.add(k); saida.append(x)
        if len(saida) == 6: break
    return p['sq'], saida

noticias, falhas = {}, 0
with cf.ThreadPoolExecutor(6) as ex:
    for sq, itens in ex.map(buscar, PESSOAS):
        if itens is None:  # falhou: fica com as anteriores que ainda estão na janela de 60 dias
            falhas += 1; itens = [x for x in NOT_ANT.get(sq, []) if x.get('d', '') >= CORTE]
        noticias[sq] = itens
if falhas: status['avisos'].append(f'notícias: {falhas} de {len(PESSOAS)} buscas falharam e ficaram com as anteriores')

fed = {'geradoEm': HOJE.isoformat(), 'cota': fcota, 'noticias': noticias}

# ---------- conferência antes de gravar ----------
# uma fonte que veio pela metade derruba os totais; nesse caso nada é gravado e o site fica como estava
erros = []
def queda(nome, novo, velho, limite=0.9):
    if velho and novo < velho * limite: erros.append(f'{nome}: {novo} contra {velho} na execução anterior')
ST_ANT = json.load(open(os.path.join(OUT, 'status.json'), encoding='utf-8')) if os.path.exists(os.path.join(OUT, 'status.json')) else {}
queda('proposições da Câmara', len(props), ST_ANT.get('proposicoes', 0))
if CAM_ANT:
    queda('deputados com proposições', len(ag), len(CAM_ANT['ag']))
    queda('autorias somadas dos deputados', sum(a['k']['total'] for a in ag.values()), sum(a['k']['total'] for a in CAM_ANT['ag'].values()))
    for d in ACOMP:
        queda(f'proposições do deputado {d}', len(lista.get(d, [])), len(CAM_ANT['lista'].get(d, [])), 0.98)
if FED_ANT:
    queda('parlamentares com cota', sum(1 for o in fcota.values() if sum(o.get('c', {}).get('cota', {}).values()) or sum(o.get('s', {}).values())),
          sum(1 for o in FED_ANT['cota'].values() if sum(o.get('c', {}).get('cota', {}).values()) or sum(o.get('s', {}).values())))
if falhas > len(PESSOAS) * 0.5:
    status['avisos'].append('mais da metade das buscas de notícias falhou')
if erros:
    print('ABORTADO, nada foi gravado:', *erros, sep='\n  ', flush=True)
    sys.exit(1)

b_cam, n_cam = para_b64(cam)
b_fed, n_fed = para_b64(fed)
open(os.path.join(OUT, 'camara.b64'), 'w', encoding='ascii').write(b_cam)
open(os.path.join(OUT, 'federal.b64'), 'w', encoding='ascii').write(b_fed)
status.update({'camaraAte': REF, 'proposicoes': len(props), 'deputadosComProposicoes': len(ag), 'listas': {k: len(v) for k, v in lista.items()},
               'parlamentaresComCota': len(fcota), 'pessoasComNoticias': sum(1 for v in noticias.values() if v), 'falhasNoticias': falhas,
               'kb': {'camara': len(b_cam) // 1024, 'federal': len(b_fed) // 1024}})
json.dump(status, open(os.path.join(OUT, 'status.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(status, ensure_ascii=False, indent=1), flush=True)
if os.environ.get('GITHUB_ACTIONS'):  # avisos aparecem no resumo da execução no GitHub
    for a in status['avisos']: print(f'::warning::{a}')
