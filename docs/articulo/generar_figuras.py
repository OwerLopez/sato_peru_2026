"""Genera las figuras del articulo a partir de los artefactos reales del proyecto (sin valores escritos a mano).

    python docs/articulo/generar_figuras.py
Salida: docs/articulo/figuras/*.png (300 dpi)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"
OUT = Path(__file__).with_name("figuras")
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9, "legend.fontsize": 8,
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight"})
AZUL, NARANJA, GRIS = "#1f4e79", "#c55a11", "#7f7f7f"


def dec(v: float, n: int = 3) -> str:
    """Numero con coma decimal (convencion del articulo en espanol)."""
    return f"{v:.{n}f}".replace(".", ",")


def comas(fig, x: bool = False):
    from matplotlib.ticker import FuncFormatter

    fmt = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
    for ax in fig.axes:
        ax.yaxis.set_major_formatter(fmt)
        if x:
            ax.xaxis.set_major_formatter(fmt)


def fig_arquitectura():
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 50)
    ax.axis("off")

    def caja(x, y, w, h, titulo, cuerpo, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=color, ec="#404040", lw=0.7))
        ax.text(x + w / 2, y + h - 2.2, titulo, ha="center", va="top", fontsize=8.2, weight="bold")
        ax.text(x + w / 2, y + h - 6.2, cuerpo, ha="center", va="top", fontsize=6.8, linespacing=1.35)

    def flecha(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, lw=0.8, color="#404040"))

    caja(1, 4, 20, 42, "Fuentes oficiales", "OECE: cuaderno de obra\ndigital (asientos,\nvalorizaciones),\nSEACE/CONOSCE\n\nMEF: Invierte.pe,\nFormato 12-B, SIAF\n\nContraloría: INFOBRAS,\nobras paralizadas", "#e8eef7")
    caja(26, 4, 22, 42, "Pipeline de datos", "ingest (SHA-256)\nstaging (Parquet)\nintegración: resolución\nde entidades (CUI, RUC)\nfeatures as-of obra-mes\nNLP: léxico, TF-IDF,\nSentence-BERT\n(DuckDB, Python)", "#eef5ea")
    caja(53, 26, 21, 20, "Modelado", "LightGBM A vs B\nvalidación temporal,\nrolling-origin, bootstrap\nTreeSHAP + evidencia", "#fdf1e6")
    caja(53, 4, 21, 18, "Persistencia", "PostgreSQL 16\n(texto completo en\nespañol, pg_trgm)\nauditoría", "#f3eef8")
    caja(79, 26, 20, 20, "Servicio", "API REST FastAPI\nJWT, CSP, límites\nde tasa, informe PDF,\nsuscripciones", "#e8eef7")
    caja(79, 4, 20, 18, "Interfaz", "React + TypeScript\nradar, mapa, ficha,\nsimulador, auditoría\n(nginx, Docker)", "#eef5ea")
    flecha(21.5, 25, 25.5, 25)
    flecha(48.5, 36, 52.5, 36)
    flecha(48.5, 13, 52.5, 13)
    flecha(63.5, 25.6, 63.5, 22.6)
    flecha(74.5, 13, 78.5, 30)
    flecha(89, 25.6, 89, 22.6)
    ax.text(50, 0.3, "Worker programado: sincronización mensual con las fuentes y resumen semanal por correo", ha="center", fontsize=6.8, style="italic")
    fig.savefig(OUT / "fig1_arquitectura.png")
    plt.close(fig)


def fig_roc_pr():
    exp = ART / "experiments"
    A = pd.read_parquet(exp / "atraso_H60_A_train-nacional" / "predicciones_test.parquet")
    B = pd.read_parquet(exp / "atraso_H60_B_full_train-nacional" / "predicciones_test.parquet")
    k = ["cuaderno_id", "T"]
    m = A[k + ["y", "s_lgbm"]].merge(B[k + ["s_lgbm"]], on=k, suffixes=("_A", "_B"))
    assert len(m) == len(A) == len(B)
    y = m["y"].to_numpy()
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.0))
    for col, lab, c in (("s_lgbm_A", "Modelo A (estructurado)", GRIS), ("s_lgbm_B", "Modelo B (+ texto de asientos)", AZUL)):
        f, t, _ = roc_curve(y, m[col])
        axs[0].plot(f, t, color=c, lw=1.3, label=f"{lab}: AUC = {dec(roc_auc_score(y, m[col]))}")
        p, r, _ = precision_recall_curve(y, m[col])
        axs[1].plot(r, p, color=c, lw=1.3, label=f"{lab}: AP = {dec(average_precision_score(y, m[col]))}")
    axs[0].plot([0, 1], [0, 1], ls=":", color="#aaaaaa", lw=0.8)
    axs[1].axhline(y.mean(), ls=":", color="#aaaaaa", lw=0.8, label=f"Prevalencia = {dec(y.mean())}")
    axs[0].set(xlabel="Tasa de falsos positivos", ylabel="Tasa de verdaderos positivos", title="(a) Curva ROC")
    axs[1].set(xlabel="Exhaustividad (recall)", ylabel="Precisión", title="(b) Curva precisión-exhaustividad")
    for a in axs:
        a.legend(loc="lower right" if a is axs[0] else "upper right", frameon=False)
    fig.tight_layout()
    comas(fig, x=True)
    fig.savefig(OUT / "fig2_roc_pr_h60.png")
    plt.close(fig)
    return {"filas": int(len(m)), "positivos": int(y.sum()), "obras": int(m["cuaderno_id"].nunique())}


def fig_rolling():
    r = pd.read_csv(ART / "experiments" / "rolling_resultados.csv")
    r = r[(r["H"] == 60) & (r["test_scope"] == "nacional")]
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    for met, ax, tit in (("pr_auc", axs[0], "(a) PR-AUC"), ("roc_auc", axs[1], "(b) ROC-AUC")):
        for fs, c, lab in (("A", GRIS, "Modelo A"), ("B_full", AZUL, "Modelo B")):
            d = r[r["feature_set"] == fs].sort_values("origen")
            ax.plot(d["origen"], d[met], marker="o", color=c, lw=1.2, ms=4, label=lab)
        ax.set(title=tit, xlabel="Origen de entrenamiento (test de 3 meses posterior)")
        ax.tick_params(axis="x", labelsize=7.5)
        ax.legend(frameon=False)
    fig.tight_layout()
    comas(fig)
    fig.savefig(OUT / "fig3_rolling_origin.png")
    plt.close(fig)


def fig_importancia():
    g = pd.read_csv(ROOT / "docs" / "research" / "importancia_grupos.csv").sort_values("nacional")
    g["grupo"] = g["grupo"].replace({"Caracteristicas de la obra": "Características de la obra", "Ejecucion financiera (SIAF)": "Ejecución financiera (SIAF)"})
    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    ax.barh(g["grupo"], 100 * g["nacional"], color=AZUL)
    for i, v in enumerate(100 * g["nacional"]):
        ax.text(v + 0.5, i, f"{dec(v, 1)} %", va="center", fontsize=7.5)
    ax.set(xlabel="Participación en la importancia TreeSHAP media absoluta (%)", xlim=(0, 55))
    fig.savefig(OUT / "fig4_importancia_grupos.png")
    plt.close(fig)


def fig_calibracion():
    card = json.loads((ART / "cartera" / "cartera_card.json").read_text(encoding="utf-8"))
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7), sharey=True)
    for ax, tipo, tit in ((axs[0], "inicio", "(a) Modelo al inicio de la obra"), (axs[1], "seguimiento", "(b) Modelo de seguimiento mensual (SIAF)")):
        u = card["umbrales"][tipo]
        niv = ["BAJO", "MEDIO", "ALTO"]
        v = [100 * u["tasa_por_nivel_test"][n]["tasa_retraso_observada"] for n in niv]
        f = [u["tasa_por_nivel_test"][n]["filas"] for n in niv]
        bars = ax.bar(niv, v, color=["#70ad47", "#ffc000", "#c00000"])
        ax.axhline(100 * u["tasa_base_test"], ls="--", color="#404040", lw=0.8, label=f"Tasa base = {dec(100 * u['tasa_base_test'], 1)} %")
        for b, val, n in zip(bars, v, f, strict=True):
            ax.text(b.get_x() + b.get_width() / 2, val + 1.5, f"{val:.1f} %\n(n = {n:,})".replace(",", " "), ha="center", fontsize=7.3)
        ax.set(title=tit, ylim=(0, 110), xlabel=f"Nivel de riesgo (test desde {u['periodo_test_desde']})")
        ax.legend(frameon=False, loc="upper left")
    axs[0].set_ylabel("Obras con retraso significativo observado (%)")
    fig.tight_layout()
    comas(fig)
    fig.savefig(OUT / "fig5_calibracion_cartera.png")
    plt.close(fig)


def fig_sensibilidad():
    rows = []
    for t, u in (("y_10", 10), ("y_30", 30), ("y_50", 50), ("y_100", 100)):
        s = json.loads((ART / "exante" / f"resultados_{t}.json").read_text(encoding="utf-8"))
        for mdl in ("regla", "logreg", "lgbm"):
            rows.append({"umbral": u, "modelo": mdl, "roc": s["modelos"][mdl]["nacional"]["roc_auc"], "pr": s["modelos"][mdl]["nacional"]["pr_auc"],
                         "prev": s["modelos"][mdl]["nacional"]["prevalencia"]})
    d = pd.DataFrame(rows)
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    nombres = {"regla": ("Regla: historial de la entidad", GRIS, "s"), "logreg": ("Regresión logística", NARANJA, "^"), "lgbm": ("LightGBM", AZUL, "o")}
    for mdl, (lab, c, mk) in nombres.items():
        x = d[d["modelo"] == mdl]
        axs[0].plot(x["umbral"], x["roc"], marker=mk, color=c, lw=1.2, ms=4, label=lab)
        axs[1].plot(x["umbral"], x["pr"], marker=mk, color=c, lw=1.2, ms=4, label=lab)
    p = d[d["modelo"] == "lgbm"]
    axs[1].plot(p["umbral"], p["prev"], ls=":", color="#aaaaaa", label="Prevalencia")
    for ax, tit in ((axs[0], "(a) ROC-AUC"), (axs[1], "(b) PR-AUC")):
        ax.set(xticks=[10, 30, 50, 100], xlabel="Umbral de retraso (% del plazo original)", title=tit)
    h, lab = axs[1].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=4, frameon=False, fontsize=7.5)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    comas(fig)
    fig.savefig(OUT / "fig6_sensibilidad_umbral.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_arquitectura()
    print("roc/pr", fig_roc_pr())
    fig_rolling()
    fig_importancia()
    fig_calibracion()
    fig_sensibilidad()
    print(sorted(p.name for p in OUT.glob("*.png")))
