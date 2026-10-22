"""Troca os dados embutidos do index.html pelos da rotina diária, na hora de publicar.

Uso: python embutir.py <pasta com camara.b64 e federal.b64> <index.html> [<index.html> ...]

Só troca o conteúdo dos blocos <script id="dados-camara"> e <script id="dados-federal">.
Um ambiente sem o bloco fica como está.
"""
import os, re, sys

pasta, paginas = sys.argv[1], sys.argv[2:]
blocos = {'dados-camara': 'camara.b64', 'dados-federal': 'federal.b64'}
dados = {}
for id_, nome in blocos.items():
    p = os.path.join(pasta, nome)
    if os.path.exists(p): dados[id_] = open(p, encoding='ascii').read().strip()

for pagina in paginas:
    html = open(pagina, encoding='utf-8', newline='').read()
    for id_, b64 in dados.items():
        html, n = re.subn(rf'(<script type="application/octet-stream" id="{id_}">)(.*?)(</script>)', lambda m: m.group(1) + b64 + m.group(3), html, count=1, flags=re.S)
        print(f'{pagina}: {id_} {"atualizado" if n else "sem o bloco, ficou como estava"}')
    open(pagina, 'w', encoding='utf-8', newline='').write(html)
