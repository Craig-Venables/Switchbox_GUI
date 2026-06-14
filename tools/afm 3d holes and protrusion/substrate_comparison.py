"""
substrate_comparison.py — Substrate vs deposited-layer defect comparison
=======================================================================
Pairs bare-substrate scans with coated variants within one experiment folder,
computes density deltas, and exports comparison plots + CSV tables.

Called from main.py after replicate aggregation (Global_Averaged).
"""

import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from main import TEMPLATES, SAVE_PLOTS


def _origin_txt_path(out_dir: str, filename: str) -> str:
    origin_dir = os.path.join(out_dir, 'origin data')
    os.makedirs(origin_dir, exist_ok=True)
    return os.path.join(origin_dir, filename)


def _save_txt(path: str, df: pd.DataFrame) -> None:
    df.to_csv(path, sep='\t', index=False)


def _sample_label(row: pd.Series) -> str:
    name = row.get('base_sample_name') or row.get('filename', '')
    if not isinstance(name, str):
        return str(name)
    return name.strip()


def _num(row: pd.Series, col: str, default: float = float('nan')) -> float:
    if col not in row.index:
        return default
    try:
        v = float(row[col])
        return v if not np.isnan(v) else default
    except (TypeError, ValueError):
        return default


def parse_sample_stack(base_sample_name: str) -> Dict[str, Any]:
    """
    Parse a base_sample_name into substrate, deposited layers, and baseline flag.

    Examples
    --------
    Glass       -> substrate=Glass,  layers=[],       is_baseline=True
    Glass_ITO   -> substrate=Glass,  layers=[ITO],    is_baseline=False
    Si_PMMA     -> substrate=Si,     layers=[PMMA],   is_baseline=False
    """
    if not isinstance(base_sample_name, str) or not base_sample_name.strip():
        return {'substrate': 'unknown', 'layers': [], 'layer_label': '', 'is_baseline': False}

    name = base_sample_name.strip()
    parts = [p for p in name.split('_') if p]
    if not parts:
        return {'substrate': 'unknown', 'layers': [], 'layer_label': '', 'is_baseline': False}

    substrate = parts[0]
    layers = parts[1:]
    layer_label = '_'.join(layers) if layers else ''
    return {
        'substrate': substrate,
        'layers': layers,
        'layer_label': layer_label,
        'is_baseline': len(layers) == 0,
    }


def _read_baseline_override(experiment_data_dir: Optional[str]) -> Optional[str]:
    """Read optional one-line baseline.txt from the source Data experiment folder."""
    if not experiment_data_dir:
        return None
    path = os.path.join(experiment_data_dir, 'baseline.txt')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            line = fh.readline().strip()
        return line or None
    except OSError:
        return None


def build_substrate_pairs(
    summary_df: pd.DataFrame,
    experiment_data_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Match deposit samples to bare-substrate baselines within one comparison folder.

    Returns a list of dicts with keys: substrate, baseline_sample, deposit_sample,
    baseline_row, deposit_row, paired (bool).
    """
    if summary_df.empty or 'base_sample_name' not in summary_df.columns:
        return []

    baseline_override = _read_baseline_override(experiment_data_dir)

    rows_by_name: Dict[str, pd.Series] = {}
    for _, row in summary_df.iterrows():
        key = _sample_label(row)
        if key and key not in rows_by_name:
            rows_by_name[key] = row

    parsed: Dict[str, Dict[str, Any]] = {
        name: parse_sample_stack(name) for name in rows_by_name
    }

    if baseline_override and baseline_override in rows_by_name:
        for name in parsed:
            parsed[name]['is_baseline'] = (name == baseline_override)

    baselines_by_substrate: Dict[str, str] = {}
    for name, info in parsed.items():
        if info['is_baseline']:
            baselines_by_substrate.setdefault(info['substrate'], name)

    pairs: List[Dict[str, Any]] = []
    seen_deposits: set = set()

    for name, info in parsed.items():
        if info['is_baseline']:
            continue
        substrate = info['substrate']
        baseline_name = baselines_by_substrate.get(substrate)
        paired = baseline_name is not None and baseline_name in rows_by_name
        deposit_key = (substrate, name)
        if deposit_key in seen_deposits:
            continue
        seen_deposits.add(deposit_key)

        pairs.append({
            'substrate': substrate,
            'baseline_sample': baseline_name if paired else None,
            'deposit_sample': name,
            'baseline_row': rows_by_name.get(baseline_name) if paired else None,
            'deposit_row': rows_by_name[name],
            'paired': paired,
            'layer_label': info['layer_label'],
        })

    for substrate, baseline_name in baselines_by_substrate.items():
        has_deposit = any(p['substrate'] == substrate and p['paired'] for p in pairs)
        if not has_deposit:
            pairs.append({
                'substrate': substrate,
                'baseline_sample': baseline_name,
                'deposit_sample': None,
                'baseline_row': rows_by_name[baseline_name],
                'deposit_row': None,
                'paired': False,
                'layer_label': '',
            })

    return pairs


def _safe_delta(deposit: float, baseline: float) -> float:
    if np.isnan(deposit) or np.isnan(baseline):
        return float('nan')
    return deposit - baseline


def _safe_fold_change(deposit: float, baseline: float) -> float:
    if np.isnan(deposit) or np.isnan(baseline) or baseline == 0:
        return float('nan')
    return deposit / baseline


def compute_deltas(pairs: List[Dict[str, Any]]) -> pd.DataFrame:
    """Build a delta table from substrate/deposit pairs."""
    rows = []
    metric_cols = [
        ('holes_per_um2', 'delta_holes_per_um2'),
        ('prots_per_um2', 'delta_prots_per_um2'),
        ('defects_per_um2', 'delta_defects_per_um2'),
        ('pct_surface_total', 'delta_pct_surface_total'),
        ('Ra_nm', 'delta_Ra_nm'),
        ('avg_hole_depth_nm', 'delta_avg_hole_depth_nm'),
    ]

    for pair in pairs:
        deposit_row = pair.get('deposit_row')
        baseline_row = pair.get('baseline_row')
        if deposit_row is None and baseline_row is not None:
            row = {
                'substrate': pair['substrate'],
                'baseline_sample': pair['baseline_sample'],
                'deposit_sample': None,
                'layer_label': pair.get('layer_label', ''),
                'paired': False,
                'note': 'baseline_only',
            }
            for src, _ in metric_cols:
                row[f'baseline_{src}'] = _num(baseline_row, src)
                row[f'deposit_{src}'] = float('nan')
            row['fold_change_defects'] = float('nan')
            rows.append(row)
            continue

        if deposit_row is None:
            continue

        row = {
            'substrate': pair['substrate'],
            'baseline_sample': pair.get('baseline_sample'),
            'deposit_sample': pair['deposit_sample'],
            'layer_label': pair.get('layer_label', ''),
            'paired': pair.get('paired', False),
            'note': 'paired' if pair.get('paired') else 'unpaired_no_baseline',
        }

        for src, delta_col in metric_cols:
            b_val = _num(baseline_row, src) if baseline_row is not None else float('nan')
            d_val = _num(deposit_row, src)
            row[f'baseline_{src}'] = b_val
            row[f'deposit_{src}'] = d_val
            row[delta_col] = _safe_delta(d_val, b_val) if pair.get('paired') else float('nan')

        row['fold_change_defects'] = (
            _safe_fold_change(
                _num(deposit_row, 'defects_per_um2'),
                _num(baseline_row, 'defects_per_um2') if baseline_row is not None else float('nan'),
            )
            if pair.get('paired') else float('nan')
        )
        rows.append(row)

    return pd.DataFrame(rows)


def _plot_substrate_defect_density(
    summary_df: pd.DataFrame,
    pairs: List[Dict[str, Any]],
    out_dir: str,
    template: str,
    suffix: str,
    save_html: bool = True,
) -> None:
    """Grouped bar chart: substrate baselines vs deposit stacks."""
    labels: List[str] = []
    hole_dens: List[float] = []
    prot_dens: List[float] = []
    total_dens: List[float] = []
    plotted: set = set()

    def _append_row(row: pd.Series, label: str) -> None:
        if label in plotted:
            return
        plotted.add(label)
        labels.append(label)
        hole_dens.append(_num(row, 'holes_per_um2', 0))
        prot_dens.append(_num(row, 'prots_per_um2', 0))
        total_dens.append(_num(row, 'defects_per_um2', 0))

    substrates_seen: set = set()
    for pair in pairs:
        substrate = pair.get('substrate', '')
        if substrate not in substrates_seen and pair.get('baseline_row') is not None:
            substrates_seen.add(substrate)
            bname = pair.get('baseline_sample') or substrate
            _append_row(pair['baseline_row'], f'{bname} (substrate)')

    for pair in pairs:
        if pair.get('deposit_row') is not None:
            _append_row(pair['deposit_row'], pair['deposit_sample'])

    for pair in pairs:
        if pair.get('deposit_row') is None and pair.get('baseline_row') is not None:
            bname = pair.get('baseline_sample') or pair.get('substrate', 'baseline')
            _append_row(pair['baseline_row'], f'{bname} (substrate)')

    if not labels:
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Holes / µm²', x=labels, y=hole_dens, marker_color='#4C9BE8', opacity=0.85))
    fig.add_trace(go.Bar(name='Protrusions / µm²', x=labels, y=prot_dens, marker_color='#E87C4C', opacity=0.85))
    fig.add_trace(go.Bar(name='Total defects / µm²', x=labels, y=total_dens, marker_color='#2ECC71', opacity=0.85))
    fig.update_layout(
        barmode='group',
        title='<b>Substrate vs Deposit — Defect Density</b>',
        xaxis_title='Sample',
        yaxis_title='Features per µm²',
        template=template,
        width=max(700, len(labels) * 140),
        height=560,
        font=dict(family='Arial, sans-serif'),
        legend=dict(x=0.01, y=0.99),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'substrate_defect_density{suffix}.html'), include_plotlyjs='cdn')


def _plot_substrate_delta_chart(
    delta_df: pd.DataFrame,
    out_dir: str,
    template: str,
    suffix: str,
    save_html: bool = True,
) -> None:
    """Waterfall-style bar chart of deposit − substrate defect density deltas."""
    paired = delta_df[delta_df['paired'] == True].copy()  # noqa: E712
    if paired.empty:
        return

    labels = [
        f"{row['deposit_sample']} − {row['baseline_sample']}"
        for _, row in paired.iterrows()
    ]
    deltas = paired['delta_defects_per_um2'].fillna(0).values
    colours = ['#2ECC71' if d <= 0 else '#E74C3C' for d in deltas]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=deltas,
        marker_color=colours,
        text=[f'{v:+.4f}' for v in deltas],
        textposition='outside',
    ))
    fig.update_layout(
        title='<b>Defect Density Change</b> (deposit − substrate, defects/µm²)',
        xaxis_title='Comparison',
        yaxis_title='Δ defects / µm²',
        template=template,
        width=max(700, len(labels) * 160),
        height=520,
        font=dict(family='Arial, sans-serif'),
    )
    fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.6)
    if save_html:
        fig.write_html(os.path.join(out_dir, f'substrate_delta_chart{suffix}.html'), include_plotlyjs='cdn')


def run_substrate_analysis(
    summary_df: pd.DataFrame,
    output_dir: str,
    experiment_name: str = '',
    experiment_data_dir: Optional[str] = None,
    save_html: bool = True,
) -> pd.DataFrame:
    """
    Main entry: pair substrates to deposits, compute deltas, save CSV + plots.

    Parameters
    ----------
    summary_df : prefer replicate-averaged rows (one per base_sample_name)
    output_dir : comparison/ directory for this experiment
    experiment_data_dir : source Data/<folder>/ path for optional baseline.txt
    """
    os.makedirs(output_dir, exist_ok=True)
    pairs = build_substrate_pairs(summary_df, experiment_data_dir)
    delta_df = compute_deltas(pairs)

    csv_path = os.path.join(output_dir, 'substrate_delta_summary.csv')
    delta_df.to_csv(csv_path, index=False)

    if not delta_df.empty:
        _save_txt(_origin_txt_path(output_dir, 'substrate_delta_summary.txt'), delta_df)

    if SAVE_PLOTS and save_html:
        for template, suffix in TEMPLATES:
            _plot_substrate_defect_density(
                summary_df, pairs, output_dir, template, suffix, save_html=save_html,
            )
            _plot_substrate_delta_chart(
                delta_df, output_dir, template, suffix, save_html=save_html,
            )

    n_paired = int((delta_df['paired'] == True).sum()) if not delta_df.empty else 0  # noqa: E712
    print(f"  Substrate comparison ({experiment_name}): {n_paired} paired deposit(s) -> {csv_path}")
    return delta_df
