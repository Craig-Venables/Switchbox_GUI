"""
comparison.py  —  Cross-file / cross-sample statistical comparison
===================================================================
Called automatically by main.py after all files are processed.
All plots are saved to Output/comparison/ as interactive Plotly HTML files
plus tab-separated .txt companions for Origin.

Plots produced
--------------
1.  feature_counts.html      – raw holes vs protrusions per sample (bar)
2.  feature_density.html     – holes, protrusions & combined defects per µm² (area-normalised bar)
3.  hole_depth_box.html      – hole depth distribution per sample (box + strip)
4.  hole_diameter_box.html   – hole equivalent diameter per sample
5.  prot_height_box.html     – protrusion height distribution per sample
6.  prot_diameter_box.html   – protrusion diameter per sample
7.  depth_vs_diameter.html   – mean depth vs diameter bubble chart (size ∝ density)
8.  stats_overview.html      – 4-panel summary: density, depth, diameter, prot height
9.  ranking_table.html       – ranked table using area-normalised density score
10. fixed_depth_sensitivity  – % interior pixels ≥ X nm below scan median (shared cutoffs)
11. hole_depth_over_Rq_box   – detected hole depth / Rq per sample
12. threshold_review_grid   – per base_sample_name: stacked height | feature maps (reload .ibw)
13. feature_spacing.html    – mean nearest-neighbour centroid spacing per sample (bar)
14. hole_spacing_box / prot_spacing_box – per-feature NN spacing distributions
"""

import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from main import (
    TEMPLATES,
    SAVE_PNGS,
    SAVE_PNG_COMP_FIXED_DEPTH, SAVE_PNG_COMP_ROUGHNESS,
    SAVE_PNG_COMP_COUNTS, SAVE_PNG_COMP_DENSITY,
    SAVE_PNG_COMP_COVERAGE, SAVE_PNG_COMP_BOXPLOTS,
    SAVE_PNG_COMP_BUBBLE, SAVE_PNG_COMP_OVERVIEW,
    SAVE_PNG_COMP_RANKING, SAVE_PNG_COMP_DEPTH_OVER_RQ,
    SAVE_PNG_COMP_SPACING,
)
_PALETTE = [
    '#4C9BE8', '#E87C4C', '#2ECC71', '#9B59B6',
    '#F39C12', '#1ABC9C', '#E74C3C', '#3498DB',
    '#E91E63', '#00BCD4',
]

def _col(i): return _PALETTE[i % len(_PALETTE)]
def _short(name):
    if not isinstance(name, str):
        return str(name)
    name = name.strip()
    if not name:
        return name
    stem, ext = os.path.splitext(name)
    # If no extension exists, assume this is already a sample label.
    return stem if ext else name
def _origin_txt_path(out_dir: str, filename: str) -> str:
    origin_dir = os.path.join(out_dir, 'origin data')
    os.makedirs(origin_dir, exist_ok=True)
    return os.path.join(origin_dir, filename)


def _save_txt(path, df): df.to_csv(path, sep='\t', index=False)
def _fmt(v, decimals=2):
    try:
        return f'{float(v):.{decimals}f}' if not np.isnan(float(v)) else 'N/A'
    except Exception:
        return str(v)


def plot_cross_file_comparison(summary_df: pd.DataFrame,
                                all_holes_df: pd.DataFrame,
                                all_prots_df: pd.DataFrame,
                                out_dir: str,
                                save_html: bool = True):
    """
    Main entry point called from main.py.

    Parameters
    ----------
    summary_df   : one row per file (from summary.csv), includes holes_per_um2
    all_holes_df : all hole features across every file (with 'filename' column)
    all_prots_df : all protrusion features across every file
    out_dir      : Output/comparison/
    """
    labels  = [_short(s) for s in summary_df['filename'].tolist()]
    colours = [_col(i) for i in range(len(labels))]

    from main import (
        PLOT_COMP_COUNTS, PLOT_COMP_DENSITY, PLOT_COMP_COVERAGE,
        PLOT_COMP_ROUGHNESS, PLOT_COMP_BOXPLOTS, PLOT_COMP_BUBBLE,
        PLOT_COMP_OVERVIEW, PLOT_COMP_RANKING,
        PLOT_COMP_FIXED_DEPTH, PLOT_COMP_DEPTH_OVER_RQ,
        PLOT_COMP_SPACING,
    )

    for template, suffix in TEMPLATES:
        # --- Raw counts ---
        if PLOT_COMP_COUNTS:
            _plot_feature_counts(summary_df, labels, colours, out_dir, template, suffix, save_html)

        # --- Area-normalised density (key new plot) ---
        if PLOT_COMP_DENSITY:
            _plot_feature_density(summary_df, labels, colours, out_dir, template, suffix, save_html)

        # --- Surface coverage ---
        if PLOT_COMP_COVERAGE:
            _plot_surface_coverage(summary_df, labels, out_dir, template, suffix, save_html)
            _plot_summary_box_by_group(summary_df, 'pct_surface_total', 'Surface Coverage (%)',
                                       'surface_coverage_box', out_dir, template, suffix, save_html)

        # --- Roughness ---
        if PLOT_COMP_ROUGHNESS:
            _plot_roughness_comparison(summary_df, labels, colours, out_dir, template, suffix, save_html)
            _plot_summary_box_by_group(summary_df, 'Rq_nm', 'Rq RMS Roughness (nm)',
                                       'rq_box', out_dir, template, suffix, save_html)

        # --- Per-feature box plots ---
        if PLOT_COMP_BOXPLOTS:
            if not all_holes_df.empty:
                _plot_box_by_sample(all_holes_df, 'depth_nm',         'Hole Depth (nm)',
                                    labels, colours, 'hole_depth_box', out_dir, template, suffix, save_html)
                _plot_box_by_sample(all_holes_df, 'equiv_diameter_nm','Hole Diameter (nm)',
                                    labels, colours, 'hole_diameter_box', out_dir, template, suffix, save_html)
                
            if not all_prots_df.empty:
                _plot_box_by_sample(all_prots_df, 'height_nm',        'Protrusion Height (nm)',
                                    labels, colours, 'prot_height_box', out_dir, template, suffix, save_html)
                _plot_box_by_sample(all_prots_df, 'equiv_diameter_nm','Protrusion Diameter (nm)',
                                    labels, colours, 'prot_diameter_box', out_dir, template, suffix, save_html)

        if PLOT_COMP_BUBBLE:
            if not all_holes_df.empty:
                _plot_depth_vs_diameter(summary_df, labels, colours, out_dir, template, suffix, save_html)

        # --- 4-panel stats overview ---
        if PLOT_COMP_OVERVIEW:
            _plot_stats_overview(summary_df, labels, colours, out_dir, template, suffix, save_html)

        # --- Ranking table (uses density) ---
        if PLOT_COMP_RANKING:
            _plot_ranking_table(summary_df, labels, out_dir, template, suffix, save_html)

        if PLOT_COMP_FIXED_DEPTH:
            _plot_fixed_depth_sensitivity(summary_df, labels, colours, out_dir, template, suffix, save_html)

        if PLOT_COMP_DEPTH_OVER_RQ:
            _plot_hole_depth_over_rq(all_holes_df, summary_df, labels, colours, out_dir, template, suffix, save_html)

        if PLOT_COMP_SPACING:
            _plot_feature_spacing(summary_df, labels, colours, out_dir, template, suffix, save_html)
            if not all_holes_df.empty and 'nn_spacing_nm' in all_holes_df.columns:
                _plot_box_by_sample(all_holes_df, 'nn_spacing_nm', 'Hole NN Spacing (nm)',
                                    labels, colours, 'hole_spacing_box', out_dir, template, suffix, save_html)
            if not all_prots_df.empty and 'nn_spacing_nm' in all_prots_df.columns:
                _plot_box_by_sample(all_prots_df, 'nn_spacing_nm', 'Protrusion NN Spacing (nm)',
                                    labels, colours, 'prot_spacing_box', out_dir, template, suffix, save_html)


# ===========================================================================
# FIXED-DEPTH (median-referenced) — apples-to-apples across roughness
# ===========================================================================

def _plot_fixed_depth_sensitivity(summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    from main import FIXED_DEPTH_CUTOFFS_NM, fixed_depth_pct_column

    xs = [float(x) for x in FIXED_DEPTH_CUTOFFS_NM]
    fig = go.Figure()
    for i, lbl in enumerate(labels):
        row = summary_df.iloc[i]
        ys = []
        for c in FIXED_DEPTH_CUTOFFS_NM:
            col = fixed_depth_pct_column(c)
            if col not in summary_df.columns:
                ys.append(float('nan'))
            else:
                v = row[col]
                ys.append(float(v) if pd.notna(v) else float('nan'))
        fig.add_trace(go.Scatter(
            x=xs, y=ys, name=lbl, mode='lines+markers',
            line=dict(color=colours[i], width=2),
            marker=dict(color=colours[i], size=9),
            hovertemplate=(
                '<b>' + str(lbl) + '</b><br>'
                'Cutoff: %{x} nm<br>'
                '% of interior pixels: %{y:.4f}<extra></extra>'
            ),
        ))

    fig.update_layout(
        title=(
            '<b>Fixed-depth comparison (median-referenced)</b><br>'
            '<sup>% of interior (non-NaN) pixels at least X nm below the scan median '
            '— same edge exclusion as detection</sup>'
        ),
        xaxis_title='Depth cutoff (nm)',
        yaxis_title='% of interior pixels',
        template=template,
        width=max(760, 24 * len(labels) + 400),
        height=560,
        font=dict(family='Arial, sans-serif'),
        legend=dict(x=0.01, y=0.99),
        hovermode='x unified',
    )
    stem = 'fixed_depth_sensitivity'
    if save_html:
        fig.write_html(os.path.join(out_dir, f'{stem}{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_FIXED_DEPTH:
        try:
            fig.write_image(os.path.join(out_dir, f'{stem}{suffix}.png'), scale=2)
        except Exception:
            pass
    if not suffix:
        txt_rows = []
        for j, lbl in enumerate(labels):
            rec = {'sample': lbl}
            row = summary_df.iloc[j]
            for c in FIXED_DEPTH_CUTOFFS_NM:
                col = fixed_depth_pct_column(c)
                if col in summary_df.columns:
                    v = row[col]
                    rec[col] = float(v) if pd.notna(v) else float('nan')
                else:
                    rec[col] = float('nan')
            txt_rows.append(rec)
        _save_txt(_origin_txt_path(out_dir, f'{stem}.txt'), pd.DataFrame(txt_rows))


def _plot_hole_depth_over_rq(all_holes_df, summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    if all_holes_df.empty or 'depth_nm' not in all_holes_df.columns:
        return
    if 'Rq_nm' not in summary_df.columns:
        return
    rq_map = dict(zip(summary_df['filename'].astype(str), summary_df['Rq_nm']))
    df = all_holes_df.copy()
    df['__Rq_nm__'] = df['filename'].astype(str).map(rq_map)
    d = pd.to_numeric(df['depth_nm'], errors='coerce')
    rq = pd.to_numeric(df['__Rq_nm__'], errors='coerce')
    rq = rq.replace(0, np.nan)
    df['depth_over_Rq'] = d / rq
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['depth_over_Rq'])
    if df.empty:
        return
    _plot_box_by_sample(
        df, 'depth_over_Rq', 'Hole depth / Rq (detected)',
        labels, colours, 'hole_depth_over_Rq_box', out_dir, template, suffix, save_html,
    )


# ===========================================================================
# ROUGHNESS COMPARISON  ← new
# ===========================================================================

def _plot_roughness_comparison(summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    """
    4-panel bar chart comparing roughness metrics across samples:
      Ra, Rq, Rsk, Rku
    """
    def _col_vals(col):
        if col in summary_df.columns:
            return summary_df[col].fillna(float('nan')).values
        return np.full(len(labels), float('nan'))

    Ra  = _col_vals('Ra_nm')
    Rq  = _col_vals('Rq_nm')
    Rsk = _col_vals('Rsk')
    Rku = _col_vals('Rku')
    Rz  = _col_vals('Rz_nm')
    Rpv = _col_vals('Rpv_nm')

    if all(np.isnan(v) for v in Ra):
        return   # no roughness data

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=[
            'Ra  (arithmetic roughness, nm)',
            'Rq  (RMS roughness, nm)',
            'Rz  (max height range, nm)',
            'Rpv (P99 - P01, nm)',
            'Rsk (skewness — negative = more holes)',
            'Rku (kurtosis — >3 = sharp features)',
        ],
        vertical_spacing=0.20,
        horizontal_spacing=0.10,
    )

    def _bar(row, col, y_vals, ytitle, ref_line=None):
        fig.add_trace(go.Bar(
            x=labels, y=y_vals,
            marker=dict(color=colours, opacity=0.85, line=dict(width=0)),
            hovertemplate='%{x}<br>' + ytitle + ': %{y:.4f}<extra></extra>',
            showlegend=False,
        ), row=row, col=col)
        fig.update_yaxes(title_text=ytitle, row=row, col=col)
        if ref_line is not None:
            fig.add_hline(y=ref_line, line=dict(color='white', width=1, dash='dot'),
                          row=row, col=col)

    _bar(1, 1, Ra,  'Ra (nm)')
    _bar(1, 2, Rq,  'Rq (nm)')
    _bar(1, 3, Rz,  'Rz (nm)')
    _bar(2, 1, Rpv, 'Rpv (nm)')
    _bar(2, 2, Rsk, 'Rsk',  ref_line=0)   # zero line: negative = more holes
    _bar(2, 3, Rku, 'Rku',  ref_line=3)   # 3 = Gaussian reference

    fig.update_layout(
        title='<b>Surface Roughness Comparison</b>  '
              '(Rsk < 0 = more valleys; Rku > 3 = sharp features)',
        template=template,
        width=max(900, len(labels) * 120 + 300),
        height=680,
        font=dict(family='Arial, sans-serif'),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'roughness_comparison{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_ROUGHNESS:
        try:
            fig.write_image(os.path.join(out_dir, f'roughness_comparison{suffix}.png'), scale=2)
        except Exception as e:
            pass
    if not suffix: _save_txt(_origin_txt_path(out_dir, 'roughness_comparison.txt'),
              pd.DataFrame({'sample': labels,
                            'Ra_nm': Ra, 'Rq_nm': Rq,
                            'Rz_nm': Rz, 'Rpv_nm': Rpv,
                            'Rsk': Rsk, 'Rku': Rku}))


# ===========================================================================
# RAW FEATURE COUNTS
# ===========================================================================

def _plot_feature_counts(summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    hole_counts = summary_df['n_holes'].fillna(0).astype(int).values
    prot_counts = summary_df['n_protrusions'].fillna(0).astype(int).values

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Holes', x=labels, y=hole_counts,
        marker_color='#4C9BE8', opacity=0.85,
        text=hole_counts, textposition='outside',
    ))
    fig.add_trace(go.Bar(
        name='Protrusions', x=labels, y=prot_counts,
        marker_color='#E87C4C', opacity=0.85,
        text=prot_counts, textposition='outside',
    ))
    fig.update_layout(
        barmode='group',
        title='<b>Raw Feature Counts per Sample</b><br>'
              '<sup>Note: scan areas may differ — use Feature Density for fair comparison</sup>',
        xaxis_title='Sample', yaxis_title='Count',
        template=template,
        width=max(650, len(labels) * 130),
        height=520,
        font=dict(family='Arial, sans-serif'),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'feature_counts{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_COUNTS:
        try:
            fig.write_image(os.path.join(out_dir, f'feature_counts{suffix}.png'), scale=2)
        except Exception as e:
            pass
    if not suffix: _save_txt(_origin_txt_path(out_dir, 'feature_counts.txt'),
              pd.DataFrame({'sample': labels, 'n_holes': hole_counts,
                            'n_protrusions': prot_counts}))


# ===========================================================================
# AREA-NORMALISED DENSITY  ← new
# ===========================================================================

def _plot_feature_density(summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    """Bar chart of holes/µm², protrusions/µm², and combined defects/µm²."""
    hole_dens = summary_df.get('holes_per_um2', pd.Series([float('nan')] * len(summary_df))).fillna(0).values
    prot_dens = summary_df.get('prots_per_um2', pd.Series([float('nan')] * len(summary_df))).fillna(0).values
    if 'defects_per_um2' in summary_df.columns:
        total_dens = summary_df['defects_per_um2'].fillna(0).values
    else:
        total_dens = hole_dens + prot_dens
    areas     = summary_df.get('scan_area_um2', pd.Series([float('nan')] * len(summary_df))).values

    hover_h = [
        f'<b>{lbl}</b><br>Holes/µm²: {hd:.3f}<br>Scan area: {a:.3f} µm²'
        for lbl, hd, a in zip(labels, hole_dens, areas)
    ]
    hover_p = [
        f'<b>{lbl}</b><br>Prots/µm²: {pd_:.3f}<br>Scan area: {a:.3f} µm²'
        for lbl, pd_, a in zip(labels, prot_dens, areas)
    ]
    hover_t = [
        f'<b>{lbl}</b><br>Total defects/µm²: {td:.3f}<br>Scan area: {a:.3f} µm²'
        for lbl, td, a in zip(labels, total_dens, areas)
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Holes / µm²', x=labels, y=hole_dens,
        marker_color='#4C9BE8', opacity=0.85,
        text=[f'{v:.3f}' for v in hole_dens], textposition='outside',
        hovertext=hover_h, hoverinfo='text',
    ))
    fig.add_trace(go.Bar(
        name='Protrusions / µm²', x=labels, y=prot_dens,
        marker_color='#E87C4C', opacity=0.85,
        text=[f'{v:.3f}' for v in prot_dens], textposition='outside',
        hovertext=hover_p, hoverinfo='text',
    ))
    fig.add_trace(go.Bar(
        name='Total defects / µm²', x=labels, y=total_dens,
        marker_color='#2ECC71', opacity=0.85,
        text=[f'{v:.3f}' for v in total_dens], textposition='outside',
        hovertext=hover_t, hoverinfo='text',
    ))
    fig.update_layout(
        barmode='group',
        title='<b>Feature Density per Sample</b> (area-normalised)',
        xaxis_title='Sample',
        yaxis_title='Features per µm²',
        template=template,
        width=max(650, len(labels) * 130),
        height=540,
        font=dict(family='Arial, sans-serif'),
        legend=dict(x=0.01, y=0.99),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'feature_density{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_DENSITY:
        try:
            fig.write_image(os.path.join(out_dir, f'feature_density{suffix}.png'), scale=2)
        except Exception as e:
            pass
    if not suffix: _save_txt(_origin_txt_path(out_dir, 'feature_density.txt'),
              pd.DataFrame({'sample': labels,
                            'holes_per_um2': hole_dens,
                            'prots_per_um2': prot_dens,
                            'defects_per_um2': total_dens,
                            'scan_area_um2': areas}))


# ===========================================================================
# NEAREST-NEIGHBOUR SPACING
# ===========================================================================

def _plot_feature_spacing(summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    """Bar chart of mean nearest-neighbour centroid spacing for holes and protrusions."""
    hole_sp = summary_df.get('avg_hole_spacing_nm', pd.Series([float('nan')] * len(summary_df))).values
    prot_sp = summary_df.get('avg_prot_spacing_nm', pd.Series([float('nan')] * len(summary_df))).values
    if all(np.isnan(v) for v in hole_sp) and all(np.isnan(v) for v in prot_sp):
        return

    hover_h = [
        f'<b>{lbl}</b><br>Avg hole NN spacing: {_fmt(hs)} nm'
        for lbl, hs in zip(labels, hole_sp)
    ]
    hover_p = [
        f'<b>{lbl}</b><br>Avg protrusion NN spacing: {_fmt(ps)} nm'
        for lbl, ps in zip(labels, prot_sp)
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Holes', x=labels, y=hole_sp,
        marker_color='#4C9BE8', opacity=0.85,
        text=[_fmt(v) for v in hole_sp], textposition='outside',
        hovertext=hover_h, hoverinfo='text',
    ))
    fig.add_trace(go.Bar(
        name='Protrusions', x=labels, y=prot_sp,
        marker_color='#E87C4C', opacity=0.85,
        text=[_fmt(v) for v in prot_sp], textposition='outside',
        hovertext=hover_p, hoverinfo='text',
    ))
    fig.update_layout(
        barmode='group',
        title=(
            '<b>Mean Nearest-Neighbour Spacing</b><br>'
            '<sup>Centroid-to-centroid distance to the closest feature of the same type (nm)</sup>'
        ),
        xaxis_title='Sample',
        yaxis_title='NN spacing (nm)',
        template=template,
        width=max(650, len(labels) * 130),
        height=540,
        font=dict(family='Arial, sans-serif'),
        legend=dict(x=0.01, y=0.99),
    )
    stem = 'feature_spacing'
    if save_html:
        fig.write_html(os.path.join(out_dir, f'{stem}{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_SPACING:
        try:
            fig.write_image(os.path.join(out_dir, f'{stem}{suffix}.png'), scale=2)
        except Exception:
            pass
    if not suffix:
        _save_txt(
            _origin_txt_path(out_dir, 'feature_spacing.txt'),
            pd.DataFrame({
                'sample': labels,
                'avg_hole_spacing_nm': hole_sp,
                'avg_prot_spacing_nm': prot_sp,
            }),
        )


# ===========================================================================
# SURFACE COVERAGE
# ===========================================================================

def _plot_surface_coverage(summary_df, labels, out_dir, template, suffix, save_html=True):
    """Stacked bar chart showing the percentage of the surface covered by holes/protrusions."""
    pct_holes = summary_df.get('pct_surface_holes', pd.Series([float('nan')] * len(summary_df))).fillna(0).values
    pct_prots = summary_df.get('pct_surface_prots', pd.Series([float('nan')] * len(summary_df))).fillna(0).values

    hover_h = [f'<b>{lbl}</b><br>Holes: {v:.4f}%<extra></extra>' for lbl, v in zip(labels, pct_holes)]
    hover_p = [f'<b>{lbl}</b><br>Protrusions: {v:.4f}%<extra></extra>' for lbl, v in zip(labels, pct_prots)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Holes Area %', x=labels, y=pct_holes,
        marker_color='#4C9BE8', opacity=0.85,
        text=[f'{v:.3f}%' if v > 0.001 else '' for v in pct_holes], 
        textposition='inside',
        hovertext=hover_h, hoverinfo='text',
    ))
    fig.add_trace(go.Bar(
        name='Protrusions Area %', x=labels, y=pct_prots,
        marker_color='#E87C4C', opacity=0.85,
        text=[f'{v:.3f}%' if v > 0.001 else '' for v in pct_prots], 
        textposition='inside',
        hovertext=hover_p, hoverinfo='text',
    ))
    
    fig.update_layout(
        barmode='stack',
        title='<b>Surface Coverage</b> (% area taken up by features)',
        xaxis_title='Sample',
        yaxis_title='Surface Coverage (%)',
        template=template,
        width=max(650, len(labels) * 130),
        height=540,
        font=dict(family='Arial, sans-serif'),
        legend=dict(x=0.01, y=0.99),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'surface_coverage{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_COVERAGE:
        try:
            fig.write_image(os.path.join(out_dir, f'surface_coverage{suffix}.png'), scale=2)
        except Exception as e:
            pass
    if not suffix: _save_txt(_origin_txt_path(out_dir, 'surface_coverage.txt'),
              pd.DataFrame({'sample': labels,
                            'pct_surface_holes': pct_holes,
                            'pct_surface_prots': pct_prots,
                            'pct_surface_total': pct_holes + pct_prots}))


# ===========================================================================
# BOX PLOTS PER SAMPLE
# ===========================================================================

def _plot_box_by_sample(df, col, ylabel, labels, colours, stem, out_dir, template, suffix, save_html=True):
    if col not in df.columns:
        return

    fig = go.Figure()
    txt_dict = {}

    for lbl, colour in zip(labels, colours):
        sub    = df[df['filename'].apply(_short) == lbl][col].dropna()
        values = sub.values.tolist()
        txt_dict[lbl] = values

        if not values:
            continue

        fig.add_trace(go.Box(
            y=values, name=lbl,
            marker_color=colour,
            line_color=colour,
            boxpoints='all',
            jitter=0.35,
            pointpos=0,
            marker=dict(size=5, opacity=0.7, line=dict(width=0.5, color='white')),
            opacity=0.85,
        ))

    fig.update_layout(
        title=f'<b>{ylabel} — per Sample</b>',
        yaxis_title=ylabel,
        template=template,
        showlegend=False,
        width=max(620, len(labels) * 150),
        height=540,
        font=dict(family='Arial, sans-serif'),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'{stem}{suffix}.html'), include_plotlyjs='cdn')
    flag = SAVE_PNG_COMP_DEPTH_OVER_RQ if stem == 'hole_depth_over_Rq_box' else (
        SAVE_PNG_COMP_SPACING if stem in ('hole_spacing_box', 'prot_spacing_box') else SAVE_PNG_COMP_BOXPLOTS
    )
    if SAVE_PNGS and flag:
        try:
            fig.write_image(os.path.join(out_dir, f'{stem}{suffix}.png'), scale=2)
        except Exception as e:
            pass

    max_len = max((len(v) for v in txt_dict.values()), default=0)
    padded  = {k: v + [float('nan')] * (max_len - len(v)) for k, v in txt_dict.items()}
    _save_txt(_origin_txt_path(out_dir, f'{stem}.txt'), pd.DataFrame(padded))


def _plot_summary_box_by_group(summary_df, col, ylabel, stem, out_dir, template, suffix, save_html=True):
    if col not in summary_df.columns:
        return
    group_col = 'base_sample_name' if 'base_sample_name' in summary_df.columns else 'filename'
    fig = go.Figure()
    txt_dict = {}

    for i, (group_name, grp) in enumerate(summary_df.groupby(group_col, dropna=False)):
        label = _short(group_name) if isinstance(group_name, str) else str(group_name)
        values = pd.to_numeric(grp[col], errors='coerce').dropna().tolist()
        txt_dict[label] = values
        if not values:
            continue
        colour = _col(i)
        fig.add_trace(go.Box(
            y=values, name=label,
            marker_color=colour,
            line_color=colour,
            boxpoints='all',
            jitter=0.35,
            pointpos=0,
            marker=dict(size=5, opacity=0.7, line=dict(width=0.5, color='white')),
            opacity=0.85,
        ))

    if not fig.data:
        return

    fig.update_layout(
        title=f'<b>{ylabel} — Replication Comparison</b>',
        yaxis_title=ylabel,
        template=template,
        showlegend=False,
        width=max(620, len(txt_dict) * 160),
        height=540,
        font=dict(family='Arial, sans-serif'),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'{stem}{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_BOXPLOTS:
        try:
            fig.write_image(os.path.join(out_dir, f'{stem}{suffix}.png'), scale=2)
        except Exception:
            pass

    if not suffix:
        max_len = max((len(v) for v in txt_dict.values()), default=0)
        padded = {k: v + [float('nan')] * (max_len - len(v)) for k, v in txt_dict.items()}
        _save_txt(_origin_txt_path(out_dir, f'{stem}.txt'), pd.DataFrame(padded))


# ===========================================================================
# DEPTH vs DIAMETER BUBBLE CHART
# ===========================================================================

def _plot_depth_vs_diameter(summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    x    = summary_df['avg_hole_diameter_nm'].values
    y    = summary_df['avg_hole_depth_nm'].values
    dens = summary_df.get('holes_per_um2', pd.Series([1.0] * len(summary_df))).fillna(1).values

    fig = go.Figure()
    for i, lbl in enumerate(labels):
        if np.isnan(x[i]) or np.isnan(y[i]):
            continue
        # bubble size proportional to density
        bsize = max(12, int(dens[i] * 30))
        fig.add_trace(go.Scatter(
            x=[x[i]], y=[y[i]],
            mode='markers+text',
            marker=dict(size=bsize, color=colours[i],
                        opacity=0.85, line=dict(width=1.5, color='white')),
            text=[lbl], textposition='top center',
            hovertemplate=(
                f'<b>{lbl}</b><br>'
                f'Diameter: {x[i]:.1f} nm<br>'
                f'Depth: {y[i]:.3f} nm<br>'
                f'Density: {dens[i]:.3f} /µm²'
                '<extra></extra>'
            ),
            name=lbl,
        ))

    fig.update_layout(
        title='<b>Mean Hole Depth vs Diameter</b> (bubble size ∝ density)',
        xaxis_title='Mean Hole Diameter (nm)',
        yaxis_title='Mean Hole Depth (nm)',
        template=template,
        showlegend=False,
        width=740, height=560,
        font=dict(family='Arial, sans-serif'),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'depth_vs_diameter{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_BUBBLE:
        try:
            fig.write_image(os.path.join(out_dir, f'depth_vs_diameter{suffix}.png'), scale=2)
        except Exception as e:
            pass
    if not suffix: _save_txt(_origin_txt_path(out_dir, 'depth_vs_diameter.txt'),
              pd.DataFrame({'sample': labels,
                            'mean_hole_diameter_nm': x,
                            'mean_hole_depth_nm': y,
                            'holes_per_um2': dens}))


# ===========================================================================
# 4-PANEL STATS OVERVIEW  ← new
# ===========================================================================

def _plot_stats_overview(summary_df, labels, colours, out_dir, template, suffix, save_html=True):
    """
    4-panel bar chart summarising the key cross-sample metrics:
      1. Hole density (holes / µm²)
      2. Mean hole depth (nm)
      3. Mean hole diameter (nm)
      4. Mean protrusion height (nm)
    Error bars show ± 1 std where available.
    """
    def _col_vals(col):
        if col in summary_df.columns:
            return summary_df[col].fillna(float('nan')).values
        return np.full(len(labels), float('nan'))

    hole_dens   = _col_vals('holes_per_um2')
    hole_depth  = _col_vals('avg_hole_depth_nm')
    hole_depth_e= _col_vals('std_hole_depth_nm')
    hole_diam   = _col_vals('avg_hole_diameter_nm')
    hole_diam_e = _col_vals('std_hole_diameter_nm')
    prot_h      = _col_vals('avg_prot_height_nm')
    prot_h_e    = _col_vals('std_prot_height_nm')

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            'Hole Density (holes / µm²)',
            'Mean Hole Depth (nm)',
            'Mean Hole Diameter (nm)',
            'Mean Protrusion Height (nm)',
        ],
        vertical_spacing=0.18,
        horizontal_spacing=0.12,
    )

    def _bar(row, col, y_vals, err_vals, colour, ytitle):
        valid_err = [e if not np.isnan(e) else 0 for e in err_vals]
        fig.add_trace(go.Bar(
            x=labels,
            y=y_vals,
            error_y=dict(type='data', array=valid_err, visible=True,
                         color='rgba(255,255,255,0.6)', thickness=1.5, width=4),
            marker=dict(
                color=colours,
                opacity=0.85,
                line=dict(width=0),
            ),
            hovertemplate='%{x}<br>' + ytitle + ': %{y:.3f}<extra></extra>',
            showlegend=False,
        ), row=row, col=col)
        fig.update_yaxes(title_text=ytitle, row=row, col=col)

    _bar(1, 1, hole_dens,  np.zeros(len(labels)), colours, 'holes / µm²')
    _bar(1, 2, hole_depth, hole_depth_e,           colours, 'Depth (nm)')
    _bar(2, 1, hole_diam,  hole_diam_e,            colours, 'Diameter (nm)')
    _bar(2, 2, prot_h,     prot_h_e,               colours, 'Height (nm)')

    fig.update_layout(
        title='<b>Cross-Sample Statistics Overview</b>  (error bars = ±1 std)',
        template=template,
        width=max(800, len(labels) * 100 + 300),
        height=700,
        font=dict(family='Arial, sans-serif'),
        plot_bgcolor='rgba(0,0,0,0)',
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'stats_overview{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_OVERVIEW:
        try:
            fig.write_image(os.path.join(out_dir, f'stats_overview{suffix}.png'), scale=2)
        except Exception as e:
            pass

    # TXT companion
    if not suffix: _save_txt(_origin_txt_path(out_dir, 'stats_overview.txt'), pd.DataFrame({
        'sample':              labels,
        'holes_per_um2':       hole_dens,
        'avg_hole_depth_nm':   hole_depth,
        'std_hole_depth_nm':   hole_depth_e,
        'avg_hole_diam_nm':    hole_diam,
        'std_hole_diam_nm':    hole_diam_e,
        'avg_prot_height_nm':  prot_h,
        'std_prot_height_nm':  prot_h_e,
    }))


# ===========================================================================
# RANKING TABLE  (updated to use density)
# ===========================================================================

def _plot_ranking_table(summary_df, labels, out_dir, template, suffix, save_html=True):
    """
    Rank samples on three metrics (all ascending = lower is better):
      - holes_per_um2   : fewer holes per unit area
      - avg_hole_depth  : shallower holes
      - avg_hole_diam   : smaller-diameter holes
    Composite = sum of the three ranks (lower = better overall).
    """
    df = summary_df.copy()
    df['_label'] = labels

    def _rank(col, ascending=True):
        if col in df.columns:
            return df[col].rank(ascending=ascending, na_option='bottom').astype(int)
        return pd.Series([0] * len(df), index=df.index)

    df['rank_density']  = _rank('holes_per_um2',       ascending=True)
    df['rank_depth']    = _rank('avg_hole_depth_nm',   ascending=True)
    df['rank_diameter'] = _rank('avg_hole_diameter_nm',ascending=True)
    df['rank_Ra']       = _rank('Ra_nm',               ascending=True)
    df['composite']     = (df['rank_density'] + df['rank_depth']
                          + df['rank_diameter'] + df['rank_Ra'])
    df = df.sort_values('composite').reset_index(drop=True)

    # Highlight colour per row: best = green tint, worst = red tint
    n = len(df)
    def _row_colour(i):
        if n == 1:
            return '#1a2535'
        frac = i / max(n - 1, 1)   # 0 = best, 1 = worst
        r = int(26  + frac * (80  - 26))
        g = int(37  + frac * (20  - 37))
        b = int(53  + frac * (40  - 53))
        return f'rgb({r},{g},{b})'
    row_colours = [_row_colour(i) for i in range(n)]

    def _get(col): return df[col].values if col in df.columns else ['N/A'] * n

    header_vals = [
        'Rank', 'Sample', 'Scan (µm²)',
        'Holes/µm²', 'Ra (nm)', 'Avg depth (nm)', 'Avg diam (nm)',
        'N holes', 'N prots',
        'Rank ρ', 'Rank D', 'Rank Ø', 'Rank Ra', 'Composite',
    ]

    areas    = _get('scan_area_um2')
    dens     = _get('holes_per_um2')
    Ra_vals  = _get('Ra_nm')
    depths   = _get('avg_hole_depth_nm')
    diams    = _get('avg_hole_diameter_nm')
    n_holes  = _get('n_holes')
    n_prots  = _get('n_protrusions')

    cell_vals = [
        list(range(1, n + 1)),
        df['_label'].tolist(),
        [_fmt(v, 3) for v in areas],
        [_fmt(v, 4) for v in dens],
        [_fmt(v, 4) for v in Ra_vals],
        [_fmt(v, 3) for v in depths],
        [_fmt(v, 1) for v in diams],
        [str(int(v)) if str(v) != 'nan' else 'N/A' for v in n_holes],
        [str(int(v)) if str(v) != 'nan' else 'N/A' for v in n_prots],
        df['rank_density'].tolist(),
        df['rank_depth'].tolist(),
        df['rank_diameter'].tolist(),
        df['rank_Ra'].tolist(),
        df['composite'].tolist(),
    ]

    fig = go.Figure(go.Table(
        header=dict(
            values=[f'<b>{h}</b>' for h in header_vals],
            fill_color='#2C3E50',
            font=dict(color='white', size=11),
            align='center', height=34,
        ),
        cells=dict(
            values=cell_vals,
            fill_color=[row_colours],
            font=dict(color='white', size=10),
            align='center', height=30,
        ),
    ))
    fig.update_layout(
        title=(
            '<b>Sample Ranking</b>  '
            '(ranked by holes/µm², depth, and diameter — rank 1 = best)'
        ),
        template=template,
        width=max(1000, n * 60 + 400),
        height=max(380, 100 + 34 * n),
        font=dict(family='Arial, sans-serif'),
    )
    if save_html:
        fig.write_html(os.path.join(out_dir, f'ranking_table{suffix}.html'), include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_COMP_RANKING:
        try:
            fig.write_image(os.path.join(out_dir, f'ranking_table{suffix}.png'), scale=2)
        except Exception as e:
            pass

    out_df = pd.DataFrame({h: c for h, c in zip(header_vals, cell_vals)})
    if not suffix: _save_txt(_origin_txt_path(out_dir, 'ranking_table.txt'), out_df)


def plot_threshold_review_grid(summary_grp: pd.DataFrame, out_dir: str,
                               stem: str = 'threshold_review_grid'):
    """
    Build one multi-row Plotly figure per theme: each row is one scan (same base_sample_name),
    left = Viridis height map, right = greyscale height + hole/protrusion overlays (same style as
    per-sample feature maps). Reloads each .ibw and re-runs detection so results match current
    ``main.py`` threshold settings.
    """
    from main import (
        PLOT_COMP_THRESHOLD_REVIEW,
        load_ibw,
        detect_features,
        measure_features,
        COL_HOLE,
        COL_PROT,
        TEMPLATES,
    )
    if not PLOT_COMP_THRESHOLD_REVIEW:
        return
    if summary_grp.empty or 'ibw_path' not in summary_grp.columns:
        return
    os.makedirs(out_dir, exist_ok=True)

    rows_df = summary_grp.sort_values('filename').reset_index(drop=True)
    base_label = ''
    if 'base_sample_name' in rows_df.columns and pd.notna(rows_df['base_sample_name'].iloc[0]):
        base_label = str(rows_df['base_sample_name'].iloc[0]).strip()

    scans = []
    for _, row in rows_df.iterrows():
        path = str(row.get('ibw_path', '')).strip()
        fn = str(row.get('filename', os.path.basename(path) if path else ''))
        if not path or not os.path.isfile(path):
            continue
        try:
            z_nm, pixel_nm, _, _ = load_ibw(path)
            hole_mask, prot_mask, stats = detect_features(z_nm, pixel_nm)
            fh, hl = measure_features(z_nm, hole_mask, pixel_nm, 'hole', stats['mean_nm'])
            fp, pl = measure_features(z_nm, prot_mask, pixel_nm, 'protrusion', stats['mean_nm'])
            scans.append({
                'label': _short(fn),
                'z_nm': z_nm,
                'pixel_nm': pixel_nm,
                'hole_labeled': hl,
                'prot_labeled': pl,
                'features_holes': fh,
                'features_prots': fp,
            })
        except Exception:
            continue

    if not scans:
        return

    n_scans = len(scans)
    subplot_titles = []
    for s in scans:
        subplot_titles.extend([f"{s['label']} — height", f"{s['label']} — features"])

    for template, suffix in TEMPLATES:
        fig = make_subplots(
            rows=n_scans, cols=2,
            subplot_titles=tuple(subplot_titles),
            horizontal_spacing=0.06,
            vertical_spacing=0.03 if n_scans > 1 else 0.08,
        )
        for i, s in enumerate(scans):
            r = i + 1
            z_nm = s['z_nm']
            pixel_nm = s['pixel_nm']
            ny, nx = z_nm.shape
            x_um = np.arange(nx) * pixel_nm / 1000.0
            y_um = np.arange(ny) * pixel_nm / 1000.0
            hole_labeled = s['hole_labeled']
            prot_labeled = s['prot_labeled']
            fh = s['features_holes']
            fp = s['features_prots']

            kwargs_h = dict(
                z=z_nm, x=x_um, y=y_um,
                colorscale='Viridis',
                hovertemplate='X: %{x:.3f} µm<br>Y: %{y:.3f} µm<br>Z: %{z:.3f} nm<extra></extra>',
            )
            if i == n_scans - 1:
                kwargs_h['showscale'] = True
                kwargs_h['colorbar'] = dict(title=dict(text='Z (nm)', side='right'))
            else:
                kwargs_h['showscale'] = False
            fig.add_trace(go.Heatmap(**kwargs_h), row=r, col=1)

            fig.add_trace(go.Heatmap(
                z=z_nm, x=x_um, y=y_um,
                colorscale='Greys',
                showscale=False,
                hovertemplate='X: %{x:.3f} µm<br>Y: %{y:.3f} µm<br>Z: %{z:.3f} nm<extra></extra>',
            ), row=r, col=2)

            if np.any(hole_labeled > 0):
                overlay_h = np.where(hole_labeled > 0, 1.0, np.nan)
                fig.add_trace(go.Heatmap(
                    z=overlay_h, x=x_um, y=y_um,
                    colorscale=[[0, 'rgba(76,155,232,0.55)'], [1, 'rgba(76,155,232,0.55)']],
                    showscale=False,
                    hoverinfo='skip',
                ), row=r, col=2)
            if np.any(prot_labeled > 0):
                overlay_p = np.where(prot_labeled > 0, 1.0, np.nan)
                fig.add_trace(go.Heatmap(
                    z=overlay_p, x=x_um, y=y_um,
                    colorscale=[[0, 'rgba(232,124,76,0.55)'], [1, 'rgba(232,124,76,0.55)']],
                    showscale=False,
                    hoverinfo='skip',
                ), row=r, col=2)

            if fh:
                cx = [f['centroid_x_nm'] / 1000 for f in fh]
                cy = [f['centroid_y_nm'] / 1000 for f in fh]
                htxt = [
                    f"Hole {f['feature_id']}<br>Depth: {f.get('depth_nm', 0):.2f} nm"
                    f"<br>⌀: {f['equiv_diameter_nm']:.1f} nm"
                    for f in fh
                ]
                fig.add_trace(go.Scatter(
                    x=cx, y=cy, mode='markers',
                    marker=dict(symbol='x-thin', size=8, color=COL_HOLE,
                                line=dict(width=2, color=COL_HOLE)),
                    hovertext=htxt, hoverinfo='text',
                    showlegend=False,
                ), row=r, col=2)
            if fp:
                cx = [f['centroid_x_nm'] / 1000 for f in fp]
                cy = [f['centroid_y_nm'] / 1000 for f in fp]
                htxt = [
                    f"Prot {f['feature_id']}<br>H: {f.get('height_nm', 0):.2f} nm"
                    f"<br>⌀: {f['equiv_diameter_nm']:.1f} nm"
                    for f in fp
                ]
                fig.add_trace(go.Scatter(
                    x=cx, y=cy, mode='markers',
                    marker=dict(symbol='diamond', size=7, color=COL_PROT,
                                line=dict(width=1, color='white')),
                    hovertext=htxt, hoverinfo='text',
                    showlegend=False,
                ), row=r, col=2)

        title_txt = '<b>Threshold review — height vs feature map</b>'
        if base_label:
            title_txt += f'<br><sup>base_sample_name: {base_label}</sup>'
        fig.update_layout(
            title=title_txt,
            template=template,
            height=min(280 * n_scans + 140, 9000),
            width=1100,
            font=dict(family='Arial, sans-serif'),
        )
        fig.write_html(os.path.join(out_dir, f'{stem}{suffix}.html'), include_plotlyjs='cdn')

    print(f"  Threshold review ({n_scans} scans) -> {out_dir} ({stem}*.html)")
