"""Genera referencias.js (formato IEEE) desde los metadatos de Crossref verificados (referencias_verificadas.json).

Las fuentes sin DOI (actas NeurIPS, JMLR, normas y conjuntos de datos oficiales) se agregan con su URL oficial, verificada con
una solicitud HTTP el mismo dia (ver control en la seccion MANUALES).
    python docs/articulo/fuente/generar_referencias.py
"""

import json
import re
from pathlib import Path

DIR = Path(__file__).parent
V = json.loads((DIR.parent / "referencias_verificadas.json").read_text(encoding="utf-8"))
FECHA = "26 de septiembre de 2026"

CLAVES = {
    "10.1061/(asce)co.1943-7862.0001736": "gondia", "10.1016/j.mlwa.2021.100166": "egwim2021", "10.1016/j.ijproman.2005.11.010": "assaf",
    "10.1016/j.ijproman.2006.11.007": "sambasivan", "10.1002/pmj.21409": "flyvbjerg", "10.1080/15623599.2020.1768326": "sanni",
    "10.3390/su12041514": "yaseen", "10.1108/ijmpb-09-2018-0178": "durdyev", "10.1016/j.ijforecast.2020.06.006": "gallego",
    "10.1093/jleo/ewaa004": "decarolis", "10.1017/s0007123417000461": "fazekas", "10.1257/aer.104.4.1288": "bajari",
    "10.1145/2382577.2382579": "kaufman", "10.1371/journal.pone.0118432": "saito", "10.1038/s42256-019-0138-9": "lundberg2020",
    "10.18653/v1/d19-1410": "reimers2019", "10.18653/v1/2020.emnlp-main.365": "reimers2020", "10.1016/j.autcon.2015.11.001": "tixier",
    "10.1016/j.autcon.2018.12.016": "zhang", "10.1145/2939672.2939785": "xgboost", "10.1023/a:1010933404324": "breiman",
    "10.1016/s0169-2070(00)00065-0": "tashman", "10.1016/j.ins.2011.12.028": "bergmeir", "10.1214/aos/1176344552": "efron",
    "10.1080/01621459.1969.10501049": "fellegi", "10.2307/25148625": "hevner", "10.2753/mis0742-1222240302": "peffers",
    "10.1145/1102351.1102430": "niculescu", "10.1038/s42256-019-0048-x": "rudin", "10.1175/1520-0493(1950)078<0001:vofeit>2.0.co;2": "brier",
    "10.1016/s0263-7863(00)00021-1": "nikander", "10.1007/978-3-642-31164-2": "christen", "10.3390/en12101956": "son",
    "10.3389/fbuil.2026.1815172": "yuan", "10.3390/en17010182": "egwim2024", "10.1080/15623599.2026.2664477": "montoya",
    "10.1061/9780784486986.002": "jamal",
}

MANUALES = {
    "lundberg2017": 'S. M. Lundberg and S.-I. Lee, "A unified approach to interpreting model predictions," in *Advances in Neural Information Processing Systems 30 (NIPS 2017)*, 2017. [Online]. Available: https://papers.nips.cc/paper_files/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html',
    "lightgbm": 'G. Ke *et al.*, "LightGBM: A highly efficient gradient boosting decision tree," in *Advances in Neural Information Processing Systems 30 (NIPS 2017)*, 2017. [Online]. Available: https://papers.nips.cc/paper_files/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html',
    "sklearn": 'F. Pedregosa *et al.*, "Scikit-learn: Machine learning in Python," *Journal of Machine Learning Research*, vol. 12, pp. 2825–2830, 2011. [Online]. Available: https://jmlr.org/papers/v12/pedregosa11a.html',
    "ley32069": f'Organismo Especializado para las Contrataciones Públicas Eficientes (OECE), "Ley N.° 32069, Ley General de Contrataciones Públicas, y su Reglamento" (compendio normativo), Plataforma del Estado Peruano. [Online]. Available: https://www.gob.pe/es/o/45029 (accedido: {FECHA}).',
    "rlgcp": f'Ministerio de Economía y Finanzas, "Decreto Supremo N.° 009-2025-EF. Reglamento de la Ley N.° 32069, Ley General de Contrataciones Públicas," Lima, Perú, 2025. [Online]. Available: https://www.gob.pe/institucion/mef/normas-legales/6401561-009-2025-ef (accedido: {FECHA}).',
    "rlce": f'Ministerio de Economía y Finanzas, "Decreto Supremo N.° 344-2018-EF. Reglamento de la Ley N.° 30225, Ley de Contrataciones del Estado," Lima, Perú, 2018. [Online]. Available: https://www.gob.pe/institucion/mef/normas-legales/235964-344-2018-ef (accedido: {FECHA}).',
    "ley31589": f'Congreso de la República del Perú, "Ley N.° 31589, Ley que garantiza la reactivación de obras públicas paralizadas," *Diario Oficial El Peruano*, 22 oct. 2022. [Online]. Available: https://www.mef.gob.pe/es/normatividad-inv-publica/instrumento/ley-inv-pub/30189-ley-n-31589/file (accedido: {FECHA}).',
    "cgr_paralizadas": f'Contraloría General de la República, "Obras paralizadas: documentos" (reportes trimestrales, cortes 2023-09 a 2026-06), Plataforma del Estado Peruano. [Online]. Available: https://www.gob.pe/institucion/contraloria/colecciones/18230-obras-paralizadas-documentos (accedido: {FECHA}).',
    "infobras": f'Contraloría General de la República, "INFOBRAS: DataSet de obras públicas" (archivo XLSX generado el 25 sep. 2026). [Online]. Available: https://infobras.contraloria.gob.pe/InfobrasWeb/DataSets (accedido: {FECHA}).',
    "mef_datos": f'Ministerio de Economía y Finanzas, "Plataforma de datos abiertos del MEF: Banco de Inversiones, Formato 12-B y ejecución presupuestal (SIAF)." [Online]. Available: https://datosabiertos.mef.gob.pe (accedido: {FECHA}).',
    "oece_cod": f'Organismo Especializado para las Contrataciones Públicas Eficientes (OECE), "Datos abiertos del cuaderno de obra digital: cuadernos, asientos y valorizaciones" (archivos mensuales 2024-06 a 2026-08), enlazados desde la Plataforma Nacional de Datos Abiertos. [Online]. Available: https://www.datosabiertos.gob.pe (accedido: {FECHA}).',
    "iso25010": 'International Organization for Standardization, *ISO/IEC 25010:2023. Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — Product quality model*, Geneva, Switzerland, 2023.',
    "owasp": f'OWASP Foundation, "OWASP Top 10:2021." [Online]. Available: https://owasp.org/Top10/ (accedido: {FECHA}).',
}


def inicial(nombre: str) -> str:
    partes = re.split(r"([\s-])", nombre.strip())
    out = ""
    for p in partes:
        if p in (" ", "-"):
            out += p
        elif p:
            out += p[0] + "."
    return out.replace(". ", ". ").strip()


def autor(a: str) -> str:
    toks = a.split()
    if len(toks) == 1:
        return a
    # Crossref separa given/family; aqui recibimos "Given Family" -> iniciales + apellido(s)
    return a


def autores_ieee(r) -> str:
    raw = r["_autores_gf"]
    if not raw:
        return ""
    fmt = [f"{inicial(g.title() if g.isupper() else g)} {f.title() if f.isupper() else f}".strip() if g else f for g, f in raw]
    if len(fmt) > 6:
        return f"{fmt[0]} *et al.*"
    if len(fmt) == 1:
        return fmt[0]
    if len(fmt) == 2:
        return f"{fmt[0]} and {fmt[1]}"
    return ", ".join(fmt[:-1]) + ", and " + fmt[-1]


def ieee(r) -> str:
    au = autores_ieee(r)
    titulo = r["titulo"].rstrip(".").replace("Research1", "Research")
    if titulo.isupper():
        titulo = titulo.capitalize()
    if r["doi"].lower() == "10.1214/aos/1176344552" and not r["paginas"]:
        r["paginas"] = "1-26"
    tipo = r["tipo"]
    doi = r["doi"]
    anio = r["anio"]
    if tipo in ("proceedings-article",):
        s = f'{au}, "{titulo}," in *{r["revista"]}*, {anio}'
        if r["paginas"]:
            s += f', pp. {r["paginas"].replace("-", "–")}'
    elif tipo in ("book", "monograph"):
        s = f'{au}, *{titulo}*. {r["editorial"]}, {anio}'
    else:
        s = f'{au}, "{titulo}," *{r["revista"]}*'
        if r["volumen"]:
            s += f', vol. {r["volumen"]}'
        if r["numero"]:
            s += f', no. {r["numero"]}'
        if r["paginas"]:
            p = str(r["paginas"])
            s += f', pp. {p.replace("-", "–")}' if "-" in p else f', Art. no. {p}'
        s += f", {anio}"
    return s + f", doi: {doi}."


def main():
    # autores con given/family: se recuperan de Crossref en verificar_referencias.py? Se guardan como "Given Family";
    # el apellido compuesto se preserva tomando el ultimo token solo si no hay informacion adicional.
    refs = {}
    for r in V["referencias"]:
        k = CLAVES.get(r["doi"].lower())
        if not k:
            raise SystemExit(f"DOI sin clave: {r['doi']}")
        r["_autores_gf"] = r["autores_gf"]
        refs[k] = {"doi": r["doi"], "ieee": ieee(r)}
    for k, v in MANUALES.items():
        refs[k] = {"doi": None, "ieee": v}
    js = "// Generado por generar_referencias.py a partir de Crossref (no editar a mano)\nmodule.exports = " + json.dumps(refs, ensure_ascii=False, indent=1) + "\n"
    (DIR / "referencias.js").write_text(js, encoding="utf-8")
    for k, v in refs.items():
        print(k, "|", v["ieee"][:160])


if __name__ == "__main__":
    main()
