"""Figures and LaTeX tables for paper/main.tex, generated from
results/study/*.csv (produced by `python -m experiments.study`).

    python -m experiments.paper_figures
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDY = os.path.join(ROOT, "results", "study")
FIG = os.path.join(ROOT, "paper", "figures")

ORDER = ["no_coordination", "claim", "mas", "mas_iterative", "hungarian", "cbba"]
LABEL = {"no_coordination": "Independent", "claim": "Claim-only", "mas": "Propose-resolve (1-round)",
         "mas_iterative": "Iterative propose-resolve", "hungarian": "Centralized Hungarian", "cbba": "CBBA"}
SHORT = {"no_coordination": "IND", "claim": "CLM", "mas": "PR-1", "mas_iterative": "PR-k", "hungarian": "HUN",
         "cbba": "CBBA"}
# Validated categorical slots 1-5 (fixed order, never cycled); markers and
# dashes are the secondary encoding so the figures survive grayscale print.
COLOR = dict(zip(ORDER, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]))
MARKER = dict(zip(ORDER, ["o", "s", "^", "D", "v", "P"]))
DASH = dict(zip(ORDER, ["-", "--", "-", "-.", ":", (0, (4, 1, 1, 1))]))

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#e4e4e0", "grid.linewidth": 0.5, "lines.linewidth": 1.4, "lines.markersize": 4,
    "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def load(exp: str) -> list[dict]:
    with open(os.path.join(STUDY, f"{exp}_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            try:
                r[k] = float(v)
            except ValueError:
                pass
    return rows


def ci95(values: list[float]) -> tuple[float, float]:
    m = statistics.fmean(values)
    h = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return m, h


def group(rows, keys, metric):
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in keys)].append(r[metric])
    return g


# -- figures ------------------------------------------------------------------
def fig_scaling(e2):
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.05), sharey=False)
    g = group(e2, ["victims", "rescue_agents", "policy"], "completion_time")
    for ax, m in zip(axes, (10, 20, 30)):
        for p in ORDER:
            ns = sorted({k[1] for k in g if k[0] == m and k[2] == p})
            if p != "no_coordination":
                ns = [1.0] + ns  # N=1 is identical for every protocol (nobody to coordinate with)
            ys, es = [], []
            for n in ns:
                key = (m, n, p) if n != 1 else (m, 1.0, "no_coordination")
                mu, h = ci95(g[key])
                ys.append(mu)
                es.append(h)
            ax.errorbar(ns, ys, yerr=es, color=COLOR[p], marker=MARKER[p], linestyle=DASH[p], capsize=1.5,
                        elinewidth=0.6, label=LABEL[p], zorder=3 if p == "no_coordination" else 2)
        t1 = statistics.fmean(g[(m, 1.0, "no_coordination")])
        grid_n = [1, 2, 3, 4, 6, 8]
        ax.plot(grid_n, [t1 / n for n in grid_n], color="#9a9a95", linestyle=(0, (1, 1.5)), linewidth=0.9,
                label="Ideal $T_1/N$", zorder=1)
        ax.set_title(f"M = {m} victims")
        ax.set_xlabel("Rescue agents N")
        ax.set_xticks([1, 2, 3, 4, 6, 8])
    axes[0].set_ylabel("Completion time (sim. min)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=7, frameon=False, bbox_to_anchor=(0.5, 1.10))
    fig.tight_layout(w_pad=1.0)
    fig.savefig(os.path.join(FIG, "fig_scaling.pdf"))
    plt.close(fig)


def fig_waste(e2):
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.9))
    m = 20.0
    gw = group([r for r in e2 if r["victims"] == m], ["rescue_agents", "policy"], "wasted_ticks")
    gi = group([r for r in e2 if r["victims"] == m], ["rescue_agents", "policy"], "idle_ticks")
    ns = [2.0, 3.0, 4.0, 6.0, 8.0]
    for p in ORDER:
        for ax, g in ((axes[0], gw), (axes[1], gi)):
            ys = [statistics.fmean(g[(n, p)]) for n in ns]
            ax.plot(ns, ys, color=COLOR[p], marker=MARKER[p], linestyle=DASH[p], label=SHORT[p])
    axes[0].set_title("(a) Wasted agent-min")
    axes[1].set_title("(b) Idle agent-min")
    for ax in axes:
        ax.set_xlabel("Rescue agents N")
        ax.set_xticks([2, 4, 6, 8])
    axes[0].legend(frameon=False, loc="upper left", handlelength=1.6)
    fig.tight_layout(w_pad=0.6)
    fig.savefig(os.path.join(FIG, "fig_waste.pdf"))
    plt.close(fig)


def fig_loss(e3, e2):
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.95))
    gt = group(e3, ["comm_loss", "policy"], "completion_time")
    gd = group(e3, ["comm_loss", "policy"], "duplicate_conflicts")
    ps = sorted({k[0] for k in gt})
    for p in ("claim", "mas", "mas_iterative", "cbba"):
        ys = [ci95(gt[(q, p)]) for q in ps]
        axes[0].errorbar(ps, [y[0] for y in ys], yerr=[y[1] for y in ys], color=COLOR[p], marker=MARKER[p],
                         linestyle=DASH[p], capsize=1.5, elinewidth=0.6, label=SHORT[p])
        axes[1].plot(ps, [statistics.fmean(gd[(q, p)]) for q in ps], color=COLOR[p], marker=MARKER[p],
                     linestyle=DASH[p], label=SHORT[p])
    ref = [r for r in e2 if r["rescue_agents"] == 4 and r["victims"] == 20]
    for p in ("no_coordination", "hungarian"):
        mu = statistics.fmean(r["completion_time"] for r in ref if r["policy"] == p)
        axes[0].axhline(mu, color=COLOR[p], linestyle=DASH[p], linewidth=0.9)
        below = p == "hungarian"
        axes[0].annotate(f"{SHORT[p]} (reference)", (0.42 if below else 0.0, mu), xytext=(0, -1.5 if below else 1.5),
                         textcoords="offset points", fontsize=6.5, color="#3d3d3a",
                         va="top" if below else "bottom", ha="left")
    axes[0].set_title("(a) Completion time")
    axes[1].set_title("(b) Duplicate commitments")
    for ax in axes:
        ax.set_xlabel("Loss probability $p$")
    axes[0].set_ylabel("Sim. minutes")
    axes[1].legend(frameon=False, loc="lower right", handlelength=1.6)
    fig.tight_layout(w_pad=0.6)
    fig.savefig(os.path.join(FIG, "fig_loss.pdf"))
    plt.close(fig)


def fig_dynamic(e5):
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.95))
    g = group(e5, ["arrival_window", "policy"], "avg_waiting_time")
    ws = sorted({k[0] for k in g})
    for p in ORDER:
        ys = [ci95(g[(w, p)]) for w in ws]
        axes[0].errorbar(ws, [y[0] for y in ys], yerr=[y[1] for y in ys], color=COLOR[p], marker=MARKER[p],
                         linestyle=DASH[p], capsize=1.5, elinewidth=0.6, label=SHORT[p])
    eta = [100 * (statistics.fmean(g[(w, "claim")]) - statistics.fmean(g[(w, "mas")])) /
           (statistics.fmean(g[(w, "no_coordination")]) - statistics.fmean(g[(w, "mas")])) for w in ws]
    axes[1].plot(ws, eta, color="#3d3d3a", marker="o")
    for w, e in zip(ws, eta):
        axes[1].annotate(f"{e:.0f}%", (w, e), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=6.5)
    axes[0].set_title("(a) Mean victim wait")
    axes[1].set_title("(b) Negotiation share $\\eta$")
    axes[0].set_ylabel("Sim. minutes")
    axes[1].set_ylabel("% of IND$\\rightarrow$PR-1 gain")
    axes[1].set_ylim(0, 100)
    for ax in axes:
        ax.set_xlabel("Arrival window (min)")
        ax.set_xticks(ws)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=6, frameon=False, bbox_to_anchor=(0.5, 1.09),
               handlelength=1.5, columnspacing=0.8, fontsize=6.5)
    fig.tight_layout(w_pad=0.6)
    fig.savefig(os.path.join(FIG, "fig_dynamic.pdf"))
    plt.close(fig)


def fig_e1(e1):
    fig, ax = plt.subplots(figsize=(3.5, 1.7))
    width = 0.36
    for j, bl in enumerate((0.0, 0.1)):
        g = group([r for r in e1 if r["blockage"] == bl], ["policy"], "completion_time")
        for i, p in enumerate(ORDER):
            mu, h = ci95(g[(p,)])
            x = i + (j - 0.5) * (width + 0.04)
            ax.bar(x, mu, width, yerr=h, color=COLOR[p], edgecolor="white", linewidth=0.8,
                   hatch="////" if bl else None, capsize=1.5, error_kw={"elinewidth": 0.6})
            ax.text(x, mu + h + 1.5, f"{mu:.0f}", ha="center", va="bottom", fontsize=6, color="#3d3d3a")
    ax.set_xticks(range(len(ORDER)), [SHORT[p] for p in ORDER])
    ax.set_ylabel("Completion time (sim. min)")
    ax.grid(axis="x", visible=False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor="#9a9a95", label="no blockage"),
                       Patch(facecolor="#9a9a95", hatch="////", edgecolor="white", label="10% blockage")],
              frameon=False, loc="upper right", ncol=2)
    ax.set_ylim(0, 128)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_e1.pdf"))
    plt.close(fig)


# -- tables -------------------------------------------------------------------
def fmt_p(p):
    if p is None:
        return "--"
    if p < 1e-4:
        return r"$<\!10^{-4}$"
    return f"{p:.3f}"


def table_e1(e1, stats):
    # b=0 only: 10% blockage changes no mean by more than 1.4 min (reported in the text).
    lines = []
    for bl in (0.0,):
        sub = [r for r in e1 if r["blockage"] == bl]
        for p in ORDER:
            rs = [r for r in sub if r["policy"] == p]
            f = lambda k: statistics.fmean(r[k] for r in rs)  # noqa: E731
            crit = [r["critical_wait"] for r in rs if not math.isnan(r["critical_wait"])]
            lines.append(
                f"{int(bl * 100)}\\% & {SHORT[p]} & {f('completion_time'):.1f} & {f('avg_waiting_time'):.1f} & "
                f"{f('weighted_wait'):.1f} & {statistics.fmean(crit):.1f} & {f('duplicate_conflicts'):.2f} & "
                f"{f('wasted_ticks'):.1f} & {f('message_payload'):.1f} \\\\")
    return "\n".join(lines)


def table_e1_tests(stats):
    rows = []
    pairs = [("no_coordination", "claim"), ("claim", "mas"), ("no_coordination", "mas"),
             ("mas", "mas_iterative"), ("mas", "hungarian"), ("mas_iterative", "hungarian")]
    for base, treat in pairs:
        s = stats["E1"][f"bl=0.0|completion_time|{base}->{treat}"]
        w = stats["E1"][f"bl=0.0|weighted_wait|{base}->{treat}"]
        rows.append(
            f"{SHORT[base]}$\\rightarrow${SHORT[treat]} & {s['mean_diff']:.1f} [{s['ci95'][0]:.1f}, {s['ci95'][1]:.1f}] & "
            f"{s['pct_improvement']:.1f} & {s['wins']}/{s['ties']}/{s['losses']} & {s['rank_biserial']:.2f} & "
            f"{fmt_p(s['p_holm'])} & {w['pct_improvement']:.1f} \\\\")
    return "\n".join(rows)


def table_scaling(e2, stats):
    g = group(e2, ["victims", "rescue_agents", "policy"], "completion_time")
    gm = group(e2, ["victims", "rescue_agents", "policy"], "message_payload")
    lines = []
    for m in (10.0, 20.0, 30.0):
        t1 = statistics.fmean(g[(m, 1.0, "no_coordination")])
        for n in (2.0, 4.0, 8.0):
            T = {p: statistics.fmean(g[(m, n, p)]) for p in ORDER}
            poa = T["no_coordination"] / T["hungarian"]
            gap1 = 100 * (T["mas"] - T["hungarian"]) / T["hungarian"]
            gapk = 100 * (T["mas_iterative"] - T["hungarian"]) / T["hungarian"]
            gapc = 100 * (T["cbba"] - T["hungarian"]) / T["hungarian"]
            sc = stats["E2"][f"N={int(n)}|M={int(m)}|completion_time|cbba->hungarian"]["p_holm"]
            neg = 100 * (T["claim"] - T["mas"]) / (T["no_coordination"] - T["mas"])
            s1 = stats["E2"][f"N={int(n)}|M={int(m)}|completion_time|mas->hungarian"]["p_holm"]
            sk = stats["E2"][f"N={int(n)}|M={int(m)}|completion_time|mas_iterative->hungarian"]["p_holm"]
            star = lambda p: "$^{*}$" if p < 0.05 else ""  # noqa: E731
            lines.append(
                f"{int(m)} & {int(n)} & {T['no_coordination']:.0f} & {T['claim']:.0f} & {T['mas']:.0f} & "
                f"{T['hungarian']:.0f} & {poa:.2f} & {gap1:+.1f}{star(s1)} & {gapk:+.1f}{star(sk)} & "
                f"{gapc:+.1f}{star(sc)} & {neg:.0f} & "
                f"{t1 / T['no_coordination']:.2f} & {t1 / T['mas']:.2f} & "
                f"{statistics.fmean(gm[(m, n, 'mas')]):.0f} & {statistics.fmean(gm[(m, n, 'hungarian')]):.0f} & "
                f"{statistics.fmean(gm[(m, n, 'cbba')]):.0f} \\\\")
        if m != 30.0:
            lines.append(r"\midrule")
    return "\n".join(lines)


def table_blockage(e4):
    g = group(e4, ["blockage", "policy"], "completion_time")
    lines = []
    for bl in (0.0, 0.1, 0.2, 0.3):
        T = {p: statistics.fmean(g[(bl, p)]) for p in ORDER}
        lines.append(f"{int(bl * 100)}\\% & " + " & ".join(f"{T[p]:.1f}" for p in ORDER) +
                     f" & {100 * (T['no_coordination'] - T['mas']) / T['no_coordination']:.1f} \\\\")
    return "\n".join(lines)


def table_dynamic(e5):
    g = group(e5, ["arrival_window", "policy"], "avg_waiting_time")
    gw = group(e5, ["arrival_window", "policy"], "weighted_wait")
    gd = group(e5, ["arrival_window", "policy"], "duplicate_conflicts")
    lines = []
    for w in sorted({k[0] for k in g}):
        cells = " & ".join(f"{statistics.fmean(g[(w, p)]):.1f}" for p in ORDER)
        red = 100 * (1 - statistics.fmean(g[(w, "mas")]) / statistics.fmean(g[(w, "no_coordination")]))
        lines.append(f"{int(w)} & {cells} & {red:.0f} & {statistics.fmean(gd[(w, 'claim')]):.1f} \\\\")
    return "\n".join(lines)


def table_bursty(e6, e3):
    g = group(e6, ["comm_loss", "burst_length", "policy"], "completion_time")
    g3 = group(e3, ["comm_loss", "policy"], "completion_time")
    pols = ["claim", "mas", "mas_iterative", "cbba"]
    lines = []
    for loss in (0.1, 0.3, 0.5):
        rows = [("Bern.", {p: statistics.fmean(g3[(loss, p)]) for p in pols})]
        for burst in (1.0, 5.0, 20.0):
            rows.append((f"{int(burst)}", {p: statistics.fmean(g[(loss, burst, p)]) for p in pols}))
        for i, (lab, T) in enumerate(rows):
            best = min(T.values())
            cells = " & ".join((f"\\textbf{{{T[p]:.1f}}}" if abs(T[p] - best) < 0.05 else f"{T[p]:.1f}") for p in pols)
            lines.append(f"{('%.1f' % loss) if i == 0 else ''} & {lab} & {cells} \\\\")
        if loss != 0.5:
            lines.append(r"\midrule")
    return "\n".join(lines)


def main() -> None:
    os.makedirs(FIG, exist_ok=True)
    e1, e2, e3, e4, e5, e6 = (load(x) for x in ("E1", "E2", "E3", "E4", "E5", "E6"))
    with open(os.path.join(STUDY, "stats.json")) as f:
        stats = json.load(f)
    fig_scaling(e2)
    fig_waste(e2)
    fig_loss(e3, e2)
    fig_e1(e1)
    fig_dynamic(e5)
    tables = {"tab_e1.tex": table_e1(e1, stats), "tab_e1_tests.tex": table_e1_tests(stats),
              "tab_scaling.tex": table_scaling(e2, stats), "tab_blockage.tex": table_blockage(e4),
              "tab_dynamic.tex": table_dynamic(e5), "tab_bursty.tex": table_bursty(e6, e3)}
    tab_dir = os.path.join(ROOT, "paper", "tables")
    os.makedirs(tab_dir, exist_ok=True)
    for name, body in tables.items():
        with open(os.path.join(tab_dir, name), "w") as f:
            # \bottomrule lives in the fragment: booktabs rules cannot follow
            # an \input inside a tabular.
            f.write(body + "\n\\bottomrule\n")
        print(f"--- {name}\n{body}")


if __name__ == "__main__":
    main()
