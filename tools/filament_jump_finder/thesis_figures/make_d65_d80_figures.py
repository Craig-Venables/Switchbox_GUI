"""Thesis figures for D65 and D80 forming jumps.

Run from the Switchbox_GUI repo:

    python tools/filament_jump_finder/thesis_figures/make_d65_d80_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.filament_jump_finder.core import (  # noqa: E402
    filter_jumps,
    filter_kwargs_from_state,
    get_first_and_all,
    jump_decision_key,
    load_folders,
)
from tools.filament_jump_finder.origin_export import (  # noqa: E402
    apply_review_to_decisions,
    load_session,
    session_folder_paths,
)

OUT = Path(__file__).resolve().parent / "d65_d80"
SESSIONS = {
    "D65": ROOT / "tools" / "D65_new.json",
    "D80": ROOT / "tools" / "D80.json",
}
PADS = (100, 200, 400)
DEVICE = "#8d8d8d"
JUMP = "#1f4e79"
FIRST = "#1f4e79"
LATER = "#b9b9b9"


def _abs_v(jump) -> float:
    return abs(float(jump.get("voltage", jump.get("voltage_mid"))))


def _load(name: str):
    session = load_session(SESSIONS[name])
    loaded = load_folders(session_folder_paths(session))
    kwargs = filter_kwargs_from_state(session.get("filter_state") or {})
    kwargs["decisions"] = apply_review_to_decisions(session)
    filtered = filter_jumps(loaded["jumps"], **kwargs)
    first, all_jumps = get_first_and_all(filtered)
    first_keys = {jump_decision_key(j) for j in first}
    return {
        "registry": loaded["device_registry"],
        "first": first,
        "all": all_jumps,
        "later": [j for j in all_jumps if jump_decision_key(j) not in first_keys],
    }


def _by_pad(rows, pad):
    return [row for row in rows if row.get("pad_um") == pad]


def _style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
    })


def _pct(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return f"{value:.0f}%"
    return f"{value:.1f}%"


def _save(fig, stem: str):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _fmt(value, spec: str) -> str:
    if value is None:
        return ""
    return format(float(value), spec)


def _write_tsv(path: Path, headers, rows) -> None:
    lines = ["\t".join(headers)]
    for row in rows:
        lines.append("\t".join("" if v is None else str(v) for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _jump_voltage(jump):
    value = jump.get("voltage", jump.get("voltage_mid"))
    if value is None:
        return None
    return float(value)


def write_origin(data) -> None:
    """Tab-separated worksheets. Import each file in Origin as tab-delimited text."""
    OUT.mkdir(parents=True, exist_ok=True)

    share_rows = []
    yield_rows = []
    for pad in PADS:
        row_share = [pad]
        row_yield = [pad]
        for name in ("D65", "D80"):
            devices = _by_pad(data[name]["registry"], pad)
            jumps = _by_pad(data[name]["all"], pad)
            formed = _by_pad(data[name]["first"], pad)
            n_dev = len(data[name]["registry"])
            n_jump = len(data[name]["all"])
            n_pad = len(devices)
            row_share.extend([
                n_pad,
                len(jumps),
                _fmt(100.0 * n_pad / n_dev if n_dev else 0.0, ".6f"),
                _fmt(100.0 * len(jumps) / n_jump if n_jump else 0.0, ".6f"),
            ])
            row_yield.extend([
                n_pad,
                len(formed),
                "" if n_pad == 0 else _fmt(100.0 * len(formed) / n_pad, ".6f"),
            ])
        share_rows.append(row_share)
        yield_rows.append(row_yield)

    _write_tsv(
        OUT / "device_vs_jump_share.txt",
        [
            "Pad_um",
            "D65_N_devices", "D65_N_jumps", "D65_device_share_pct", "D65_jump_share_pct",
            "D80_N_devices", "D80_N_jumps", "D80_device_share_pct", "D80_jump_share_pct",
        ],
        share_rows,
    )
    _write_tsv(
        OUT / "forming_yield.txt",
        [
            "Pad_um",
            "D65_N_devices", "D65_N_formed", "D65_yield_pct",
            "D80_N_devices", "D80_N_formed", "D80_yield_pct",
        ],
        yield_rows,
    )

    groups = [
        ("D65_100um_first_AbsV", _by_pad(data["D65"]["first"], 100)),
        ("D65_200um_first_AbsV", _by_pad(data["D65"]["first"], 200)),
        ("D65_200um_later_AbsV", _by_pad(data["D65"]["later"], 200)),
        ("D80_200um_first_AbsV", _by_pad(data["D80"]["first"], 200)),
        ("D80_200um_later_AbsV", _by_pad(data["D80"]["later"], 200)),
        ("D65_100um_later_AbsV", _by_pad(data["D65"]["later"], 100)),
        ("D65_400um_first_AbsV", _by_pad(data["D65"]["first"], 400)),
        ("D65_400um_later_AbsV", _by_pad(data["D65"]["later"], 400)),
        ("D80_100um_first_AbsV", _by_pad(data["D80"]["first"], 100)),
        ("D80_100um_later_AbsV", _by_pad(data["D80"]["later"], 100)),
        ("D80_400um_first_AbsV", _by_pad(data["D80"]["first"], 400)),
        ("D80_400um_later_AbsV", _by_pad(data["D80"]["later"], 400)),
    ]
    columns = []
    median_rows = []
    for header, jumps in groups:
        vals = sorted(abs(_jump_voltage(j)) for j in jumps if _jump_voltage(j) is not None)
        if not vals and header not in {
            "D65_100um_first_AbsV",
            "D65_200um_first_AbsV",
            "D65_200um_later_AbsV",
            "D80_200um_first_AbsV",
            "D80_200um_later_AbsV",
        }:
            continue
        columns.append((header, [_fmt(v, ".6g") for v in vals]))
        if vals:
            median_rows.append((
                header.replace("_AbsV", ""),
                len(vals),
                _fmt(float(np.median(vals)), ".6g"),
                _fmt(float(np.mean(vals)), ".6g"),
            ))
    height = max((len(vals) for _, vals in columns), default=0)
    _write_tsv(
        OUT / "jump_voltages_by_group.txt",
        [header for header, _vals in columns],
        [[vals[i] if i < len(vals) else "" for _header, vals in columns] for i in range(height)],
    )
    _write_tsv(
        OUT / "jump_voltage_medians.txt",
        ["Group", "N", "Median_AbsV", "Mean_AbsV"],
        median_rows,
    )

    raw_rows = []
    device_rows = []
    for name in ("D65", "D80"):
        formed_keys = {
            (j.get("section"), j.get("device_num")) for j in data[name]["first"]
        }
        for rec in data[name]["registry"]:
            device_rows.append((
                name,
                rec.get("section", ""),
                rec.get("pad_um") if rec.get("pad_um") is not None else "",
                rec.get("device_num", ""),
                1 if (rec.get("section"), rec.get("device_num")) in formed_keys else 0,
            ))
        for kind, jumps in (("first", data[name]["first"]), ("later", data[name]["later"])):
            for jump in jumps:
                voltage = _jump_voltage(jump)
                raw_rows.append((
                    name,
                    kind,
                    jump.get("source_folder", ""),
                    jump.get("section", ""),
                    jump.get("pad_um") if jump.get("pad_um") is not None else "",
                    jump.get("device_num", ""),
                    jump.get("filename", ""),
                    _fmt(voltage, ".6g"),
                    _fmt(abs(voltage), ".6g") if voltage is not None else "",
                    _fmt(jump.get("ratio", 0), ".6g"),
                    _fmt(jump.get("i_before", 0), ".6e"),
                    _fmt(jump.get("i_after", 0), ".6e"),
                ))
    _write_tsv(
        OUT / "jumps_raw.txt",
        [
            "Sample", "JumpKind", "SourceFolder", "Section", "Pad_um", "Device",
            "Filename", "Voltage_V", "AbsVoltage_V", "Ratio", "I_before_A", "I_after_A",
        ],
        raw_rows,
    )
    _write_tsv(
        OUT / "devices.txt",
        ["Sample", "Section", "Pad_um", "Device", "Formed"],
        device_rows,
    )


def figure_shares(data):
    """Share of devices versus share of accepted jumps, by pad width."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5), sharey=True)
    x = np.arange(len(PADS))
    width = 0.36
    for ax, name in zip(axes, ("D65", "D80")):
        devices = data[name]["registry"]
        jumps = data[name]["all"]
        n_dev = max(len(devices), 1)
        n_jump = max(len(jumps), 1)
        dev_pct = [100.0 * len(_by_pad(devices, pad)) / n_dev for pad in PADS]
        jump_pct = [100.0 * len(_by_pad(jumps, pad)) / n_jump for pad in PADS]
        dev_n = [len(_by_pad(devices, pad)) for pad in PADS]
        jump_n = [len(_by_pad(jumps, pad)) for pad in PADS]
        bars_d = ax.bar(x - width / 2, dev_pct, width, color=DEVICE, edgecolor="black", linewidth=0.6, label="Devices", zorder=2)
        bars_j = ax.bar(x + width / 2, jump_pct, width, color=JUMP, edgecolor="black", linewidth=0.6, label="Accepted jumps", zorder=2)
        for bar, pct, n in zip(bars_d, dev_pct, dev_n):
            if n == 0:
                continue
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.4, _pct(pct), ha="center", va="bottom", fontsize=8, color="#333333")
        for bar, pct, n in zip(bars_j, jump_pct, jump_n):
            if n == 0:
                continue
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.4, _pct(pct), ha="center", va="bottom", fontsize=8, color=JUMP)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{pad} µm" for pad in PADS])
        ax.set_ylim(0, 118)
        ax.set_title(name)
        ax.set_ylabel("Share of the sample (%)" if name == "D65" else "")
        ax.yaxis.grid(True, linestyle=":", linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout()
    _save(fig, "d65_d80_device_vs_jump_share")


def figure_forming(data):
    """How many devices form, and the voltage of the first jump versus later jumps."""
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.7), gridspec_kw={"width_ratios": [1.05, 1.35]})

    ax = axes[0]
    pads_shown = (100, 200)
    x = np.arange(len(pads_shown))
    width = 0.36
    for offset, name, color in ((-width / 2, "D65", "#6e6e6e"), (width / 2, "D80", JUMP)):
        heights = []
        labels = []
        for pad in pads_shown:
            n = len(_by_pad(data[name]["registry"], pad))
            k = len(_by_pad(data[name]["first"], pad))
            heights.append(0.0 if n == 0 else 100.0 * k / n)
            labels.append("—" if n == 0 else f"{k}/{n}")
        bars = ax.bar(x + offset, heights, width, color=color, edgecolor="black", linewidth=0.6, label=name, zorder=2)
        for bar, text in zip(bars, labels):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.6, text, ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{pad} µm" for pad in pads_shown])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Devices that form (%)")
    ax.set_title("Forming yield")
    ax.legend(frameon=False, loc="upper left")
    ax.yaxis.grid(True, linestyle=":", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    ax = axes[1]
    series = [
        ("D65\n100 µm\nfirst", _by_pad(data["D65"]["first"], 100), FIRST),
        ("D65\n200 µm\nfirst", _by_pad(data["D65"]["first"], 200), FIRST),
        ("D65\n200 µm\nlater", _by_pad(data["D65"]["later"], 200), LATER),
        ("D80\n200 µm\nfirst", _by_pad(data["D80"]["first"], 200), FIRST),
        ("D80\n200 µm\nlater", _by_pad(data["D80"]["later"], 200), LATER),
    ]
    rng = np.random.default_rng(7)
    for i, (_label, jumps, color) in enumerate(series):
        vals = np.array([_abs_v(j) for j in jumps], dtype=float)
        if vals.size == 0:
            continue
        jitter = rng.uniform(-0.12, 0.12, size=vals.size)
        edge = "black" if color == FIRST else "#666666"
        ax.scatter(
            np.full(vals.size, i) + jitter, vals,
            s=28, c=color, edgecolors=edge, linewidths=0.4, zorder=3,
        )
        med = float(np.median(vals))
        ax.plot([i - 0.28, i + 0.28], [med, med], color="black", lw=1.4, zorder=4)
        ax.annotate(
            f"{med:.2f} V",
            xy=(i, med),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9),
            zorder=5,
        )
    ax.set_xticks(range(len(series)))
    ax.set_xticklabels([label for label, _, _ in series], fontsize=8)
    ax.set_ylabel("|Voltage| (V)")
    ax.set_title("First jump and later jumps")
    ax.set_ylim(1.2, 4.0)
    ax.yaxis.grid(True, linestyle=":", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    _save(fig, "d65_d80_forming_yield_and_voltage")


def main():
    _style()
    data = {name: _load(name) for name in ("D65", "D80")}
    for name, block in data.items():
        print(name)
        for pad in PADS:
            n = len(_by_pad(block["registry"], pad))
            k = len(_by_pad(block["first"], pad))
            j = len(_by_pad(block["all"], pad))
            print(f"  {pad} µm  devices {n}  formed {k}  jumps {j}")
        print(f"  total devices {len(block['registry'])}  jumps {len(block['all'])}")
    figure_shares(data)
    figure_forming(data)
    write_origin(data)
    stale = Path(__file__).resolve().parent
    for name in (
        "d65_d80_device_vs_jump_share.png",
        "d65_d80_device_vs_jump_share.pdf",
        "d65_d80_forming_yield_and_voltage.png",
        "d65_d80_forming_yield_and_voltage.pdf",
    ):
        old = stale / name
        if old.exists():
            old.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
