#!/usr/bin/env python3
"""Coleta o PageSpeed Insights de conteiner10.com.br e acumula data/historico.json."""
import argparse, gzip, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

URL = "https://conteiner10.com.br"
API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
AQUI = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(AQUI, "data", "historico.json")
BRUTOS = "/home/agente/memory/projetos/pagespeed/brutos"
TZ = timezone(timedelta(hours=-3))  # America/Sao_Paulo (sem horario de verao desde 2019)

NOMES = {"nota": "a nota", "lcp_s": "o LCP", "fcp_s": "o FCP", "tbt_ms": "o TBT",
         "cls": "o CLS", "si_s": "o Speed Index"}


def agora():
    return datetime.now(TZ)


def fmt(v, dec=1):
    return f"{v:.{dec}f}".replace(".", ",")


def mascarar(txt, chave):
    return txt.replace(chave, "***") if chave else txt


def buscar(strategy, chave):
    q = urllib.parse.urlencode({"url": URL, "strategy": strategy, "category": "performance",
                                "locale": "pt", "key": chave})
    ultimo = None
    for t in range(3):  # 1 tentativa + 2 retries
        try:
            with urllib.request.urlopen(f"{API}?{q}", timeout=300) as r:
                return json.load(r)
        except Exception as e:
            ultimo = mascarar(str(e), chave)
            print(f"[{strategy}] tentativa {t+1} falhou: {type(e).__name__}", file=sys.stderr)
            time.sleep(10)
    raise RuntimeError(ultimo)


def extrair(js):
    lh = js["lighthouseResult"]
    a = lh["audits"]

    def num(k):
        v = a.get(k, {}).get("numericValue")
        return v

    sc = lh["categories"]["performance"]["score"]
    out = {
        "nota": round(sc * 100) if sc is not None else None,
        "fcp_s": round(num("first-contentful-paint") / 1000, 2),
        "lcp_s": round(num("largest-contentful-paint") / 1000, 2),
        "tbt_ms": round(num("total-blocking-time")),
        "cls": round(num("cumulative-layout-shift"), 3),
        "si_s": round(num("speed-index") / 1000, 2),
    }
    campo = None
    m = (js.get("loadingExperience") or {}).get("metrics")
    if m:
        def p75(k):
            return (m.get(k) or {}).get("percentile")
        lcp, cls, inp = p75("LARGEST_CONTENTFUL_PAINT_MS"), p75("CUMULATIVE_LAYOUT_SHIFT_SCORE"), p75("INTERACTION_TO_NEXT_PAINT")
        campo = {"categoria": js["loadingExperience"].get("overall_category"),
                 "lcp_s": round(lcp / 1000, 2) if lcp is not None else None,
                 "cls": round(cls / 100, 3) if cls is not None else None,  # PSI entrega CLS x100
                 "inp_ms": inp}
    out["campo"] = campo
    ops = []
    for k, v in a.items():
        d = v.get("details") or {}
        if d.get("type") == "opportunity" and d.get("overallSavingsMs"):
            ops.append({"titulo": v.get("title"), "economia_s": round(d["overallSavingsMs"] / 1000, 2)})
    ops.sort(key=lambda o: -o["economia_s"])
    out["oportunidades"] = ops[:5]
    return out


# (campo, limiar, menor e melhor, rotulo)
LIM = [("lcp_s", 0.3), ("fcp_s", 0.3), ("si_s", 0.3), ("tbt_ms", 50), ("cls", 0.02)]


def comparar(atual, ant, estrategia):
    """Retorna (frases, resumo) comparando com a medicao anterior."""
    onde = "No celular" if estrategia == "mobile" else "No computador"
    if not ant or ant.get("nota") is None:
        txt = f"{onde}, esta é a primeira medição: nota {atual['nota']}."
        return [txt], txt
    frases, mudancas = [], []
    dn = atual["nota"] - ant["nota"]
    if abs(dn) < 2:
        s = f"A nota ficou estável: {ant['nota']} para {atual['nota']}."
    else:
        s = f"A nota {'subiu' if dn > 0 else 'caiu'} de {ant['nota']} para {atual['nota']} ({dn:+d})."
    frases.append(s)
    for campo, lim in LIM:
        a, b = atual.get(campo), ant.get(campo)
        if a is None or b is None:
            continue
        d = a - b
        unid = {"lcp_s": " s", "fcp_s": " s", "si_s": " s", "tbt_ms": " ms", "cls": ""}[campo]
        dec = 3 if campo == "cls" else (0 if campo == "tbt_ms" else 1)
        rot = NOMES[campo].replace("a ", "o ", 1) if False else NOMES[campo]
        sigla = {"lcp_s": "LCP", "fcp_s": "FCP", "si_s": "Speed Index", "tbt_ms": "TBT", "cls": "CLS"}[campo]
        if abs(d) < lim:
            frases.append(f"O {sigla} ficou estável ({fmt(a, dec)}{unid}).")
        elif d < 0:
            frases.append(f"O {sigla} melhorou: de {fmt(b, dec)}{unid} para {fmt(a, dec)}{unid}.")
            mudancas.append((abs(d) / lim, sigla, d, unid, dec, True))
        else:
            frases.append(f"O {sigla} piorou: de {fmt(b, dec)}{unid} para {fmt(a, dec)}{unid}.")
            mudancas.append((abs(d) / lim, sigla, d, unid, dec, False))
    ganhos = sorted([m for m in mudancas if m[5]], reverse=True)
    perdas = sorted([m for m in mudancas if not m[5]], reverse=True)
    if ganhos:
        g = ganhos[0]
        frases.append(f"Maior ganho: {g[1]} ({fmt(-g[2], g[4])}{g[3]} a menos).")
    if perdas:
        p = perdas[0]
        frases.append(f"Maior perda: {p[1]} ({fmt(p[2], p[4])}{p[3]} a mais).")
    if abs(dn) < 2:
        res = f"{onde} a nota ficou estável em {atual['nota']}"
    else:
        res = f"{onde} a nota {'subiu' if dn > 0 else 'caiu'} de {ant['nota']} para {atual['nota']} ({dn:+d})"
    extras = []
    if ganhos:
        g = ganhos[0]
        extras.append(f"o {g[1]} caiu {fmt(-g[2], g[4])}{g[3]}" if g[1] in ("LCP", "FCP", "Speed Index", "TBT")
                      else f"o {g[1]} melhorou")
    if perdas:
        extras.append(f"o {perdas[0][1]} piorou")
    res += ". " + (extras[0][0].upper() + extras[0][1:] + (("; " + extras[1]) if len(extras) > 1 else "") + "." if extras else "")
    return frases, res.strip()


def anterior(medicoes, estrategia):
    for m in reversed(medicoes):
        e = m.get(estrategia)
        if e and not e.get("erro"):
            return e
    return None


def carregar():
    if os.path.exists(HIST):
        with open(HIST, encoding="utf-8") as f:
            return json.load(f)
    return {"url": URL, "atualizado": None, "medicoes": []}


def salvar(h):
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    tmp = HIST + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HIST)


def montar_analise(medicoes, entrada):
    an, partes = {}, []
    for est in ("mobile", "desktop"):
        e = entrada.get(est)
        if not e or e.get("erro"):
            an[est] = []
            continue
        fr, res = comparar(e, anterior(medicoes, est), est)
        an[est] = fr
        partes.append(res)
    an["resumo"] = " ".join(partes) if partes else "Medição sem dados."
    return an


def seed():
    if os.path.exists(HIST):
        print("historico.json já existe; seed ignorado.")
        return
    nulos = {"fcp_s": None, "lcp_s": None, "tbt_ms": None, "cls": None, "si_s": None,
             "campo": None, "oportunidades": []}
    e1 = {"data": "2026-10-07", "hora": None, "mobile": {"nota": 14, **nulos}}
    e1["analise"] = montar_analise([], e1)
    h = {"url": URL, "atualizado": "2026-10-20T17:15:00-03:00", "medicoes": [e1]}
    e2 = {"data": "2026-10-20", "hora": "17:15",
          "mobile": {"nota": 15, "fcp_s": None, "lcp_s": 14.7, "tbt_ms": 1730, "cls": 0.286, "si_s": 21.1,
                     "campo": None, "oportunidades": []},
          "desktop": {"nota": 37, "fcp_s": None, "lcp_s": 3.0, "tbt_ms": 370, "cls": 0.443, "si_s": 9.7,
                      "campo": None, "oportunidades": []}}
    e2["analise"] = montar_analise(h["medicoes"], e2)
    h["medicoes"].append(e2)
    salvar(h)
    print("historico.json criado com 2 medições.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    if args.seed:
        seed()
        return 0
    chave = os.environ.get("PAGESPEED_API_KEY")
    if not chave:
        print("PAGESPEED_API_KEY não definida.", file=sys.stderr)
        return 1
    t = agora()
    carimbo = t.strftime("%Y%m%d-%H%M")
    entrada = {"data": t.strftime("%Y-%m-%d"), "hora": t.strftime("%H:%M")}
    falhas = 0
    for est in ("mobile", "desktop"):
        try:
            js = buscar(est, chave)
            if not args.dry:
                os.makedirs(BRUTOS, exist_ok=True)
                with gzip.open(os.path.join(BRUTOS, f"{carimbo}-{est}.json.gz"), "wt", encoding="utf-8") as f:
                    json.dump(js, f, ensure_ascii=False)
            entrada[est] = extrair(js)
        except Exception as e:
            falhas += 1
            entrada[est] = {"erro": mascarar(str(e), chave)[:300]}
    if falhas == 2:
        print("As duas medições falharam: " + entrada["mobile"]["erro"], file=sys.stderr)
        return 1
    h = carregar()
    entrada["analise"] = montar_analise(h["medicoes"], entrada)
    if args.dry:
        print(json.dumps(entrada, ensure_ascii=False, indent=1))
        return 0
    h["medicoes"].append(entrada)
    h["atualizado"] = t.isoformat(timespec="seconds")
    salvar(h)
    print("Medição salva:", entrada["analise"]["resumo"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
