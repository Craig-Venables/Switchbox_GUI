"""
comparison.py  –  Cross-file / cross-sample statistical plots
==============================================================
Called automatically by main.py after all files are processed.
All plots are saved to  Output/comparison/
Each plot also gets a tab-separated .txt for Origin.

Plots produced
--------------
1. hole_count_bar        – n_holes per sample (bar chart)
2. hole_width_box        – hole width distribution per sample (box + strip)
3. hole_depth_box        – hole depth distribution per sample (box + strip)
4. width_vs_depth        – mean hole width vs mean depth, bubble = n_holes
5. threshold_width_bars  – mean hole width at each threshold per sample
6. ranking_table         – PNG table ranking samples on key metrics
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import to_rgba

plt.rcParams.update({
    'font.family': 'sans-serif',
    'axes.grid': True,
    'grid.alpha': 0.25,
    'axes.spines.top': False,
    'axes.spines.right': False,
})

DPI = 150
_PALETTE = ['#4C9BE8', '#E87C4C', '#2ECC71', '#9B59B6', '#F39C12',
            '#1ABC9C', '#E74C3C', '#3498DB', '#E67E22', '#27AE60']


def _col(i): return _PALETTE[i % len(_PALETTE)]


def _save_txt(path, df):
    df.to_csv(path, sep='\t', index=False)


def _short(name):
    """Strip extension for display."""
    return os.path.splitext(name)[0]


# ---------------------------------------------------------------------------

def plot_cross_file_comparison(summary_df: pd.DataFrame,
                               all_prof_df: pd.DataFrame,
                               out_dir: str,
                               threshold_range: list):
    """
    Main entry point called from main.py.

    Parameters
    ----------
    summary_df      : one row per file (from summary.csv)
    all_prof_df     : all per-profile rows across every file
    out_dir         : Output/comparison/
    threshold_range : list of threshold fractions used in analysis
    """
    samples   = summary_df['filename'].tolist()
    n         = len(samples)
    colours   = [_col(i) for i in range(n)]
    labels    = [_short(s) for s in samples]

    holes_df  = all_prof_df[all_prof_df['feature_type'] == 'hole'].copy()
    prots_df  = all_prof_df[all_prof_df['feature_type'] == 'protrusion'].copy()

    # --- Feature counts ---
    _plot_feature_count_bar(summary_df, labels, colours, out_dir)

    # --- Holes ---
    _plot_box_by_sample(holes_df, 'width_nm',  'Hole Width (nm)',
                        labels, colours, 'hole_width_box', out_dir)
    _plot_box_by_sample(holes_df, 'height_nm', 'Hole Depth (nm)',
                        labels, colours, 'hole_depth_box', out_dir)
    _plot_width_vs_depth(summary_df, labels, colours, out_dir)
    _plot_threshold_bars(holes_df, labels, colours, threshold_range, out_dir)

    # --- Protrusions ---
    if not prots_df.empty:
        _plot_box_by_sample(prots_df, 'width_nm',  'Protrusion Width (nm)',
                            labels, colours, 'protrusion_width_box', out_dir)
        _plot_box_by_sample(prots_df, 'height_nm', 'Protrusion Height (nm)',
                            labels, colours, 'protrusion_height_box', out_dir)
        _plot_prot_width_vs_height(summary_df, labels, colours, out_dir)

    _plot_ranking_table(summary_df, labels, out_dir)


# ---------------------------------------------------------------------------

def _plot_feature_count_bar(summary_df, labels, colours, out_dir):
    """Grouped bar: holes vs protrusions per sample."""
    hole_counts = summary_df['n_holes'].fillna(0).astype(int).values
    prot_counts = summary_df['n_protrusions'].fillna(0).astype(int).values

    x     = np.arange(len(labels))
    w     = 0.35
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.4), 5))

    bars_h = ax.bar(x - w/2, hole_counts, w, label='Holes',
                    color='#4C9BE8', alpha=0.85, edgecolor='white')
    bars_p = ax.bar(x + w/2, prot_counts, w, label='Protrusions',
                    color='#E87C4C', alpha=0.85, edgecolor='white')

    for bar, v in list(zip(bars_h, hole_counts)) + list(zip(bars_p, prot_counts)):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    str(v), ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha='right')
    ax.set_ylabel('Feature count')
    ax.set_title('Holes & Protrusions per Sample', fontweight='bold')
    ax.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, 'feature_count_bar.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    _save_txt(os.path.join(out_dir, 'feature_count_bar.txt'),
              pd.DataFrame({'sample': labels, 'n_holes': hole_counts,
                            'n_protrusions': prot_counts}))


def _plot_box_by_sample(holes_df, col, ylabel, labels, colours, stem, out_dir):
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.4), 5))

    positions = list(range(1, len(labels) + 1))
    groups = []
    for lbl in labels:
        sub = holes_df[holes_df['filename'].apply(_short) == lbl][col].dropna()
        groups.append(sub.values)

    bp = ax.boxplot(groups, positions=positions, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', lw=2),
                    whiskerprops=dict(lw=1.2), capprops=dict(lw=1.2))

    for i, (patch, g, c) in enumerate(zip(bp['boxes'], groups, colours)):
        patch.set_facecolor(c)
        patch.set_alpha(0.65)
        # Strip plot overlay
        jitter = np.random.normal(positions[i], 0.06, len(g))
        ax.scatter(jitter, g, color=c, s=28, zorder=4,
                   edgecolors='white', linewidths=0.4)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=20, ha='right')
    ax.set_ylabel(ylabel)
    ax.set_title(f'{ylabel} — per sample', fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, f'{stem}.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # TXT: one column per sample
    max_len = max((len(g) for g in groups), default=0)
    txt_dict = {}
    for lbl, g in zip(labels, groups):
        padded = list(g) + [float('nan')] * (max_len - len(g))
        txt_dict[lbl] = padded
    _save_txt(os.path.join(out_dir, f'{stem}.txt'), pd.DataFrame(txt_dict))


def _plot_prot_width_vs_height(summary_df, labels, colours, out_dir):
    """Scatter: mean protrusion width vs height per sample."""
    fig, ax = plt.subplots(figsize=(7, 5))
    x = summary_df['avg_protrusion_width_nm'].values
    y = summary_df['avg_protrusion_height_nm'].values
    n = summary_df['n_protrusions'].values
    sizes = np.clip(n * 80, 60, 800)

    for i in range(len(labels)):
        if not (np.isnan(x[i]) or np.isnan(y[i])):
            ax.scatter(x[i], y[i], s=sizes[i], color=colours[i],
                       edgecolors='white', linewidths=0.8, zorder=3, alpha=0.85)
            ax.annotate(labels[i], (x[i], y[i]),
                        textcoords='offset points', xytext=(6, 4), fontsize=8)

    ax.set_xlabel('Mean protrusion width (nm)')
    ax.set_ylabel('Mean protrusion height (nm)')
    ax.set_title('Protrusion Width vs Height per Sample\n(bubble size = count)',
                 fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, 'protrusion_width_vs_height.png'),
                dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    _save_txt(os.path.join(out_dir, 'protrusion_width_vs_height.txt'),
              pd.DataFrame({'sample': labels,
                            'mean_prot_width_nm': x,
                            'mean_prot_height_nm': y,
                            'n_protrusions': n}))


def _plot_width_vs_depth(summary_df, labels, colours, out_dir):
    fig, ax = plt.subplots(figsize=(7, 5))

    x = summary_df['avg_hole_width_nm'].values
    y = summary_df['avg_hole_depth_nm'].values
    n = summary_df['n_holes'].values

    # Bubble size proportional to n_holes
    sizes = np.clip(n * 80, 60, 800)

    for i in range(len(labels)):
        if not (np.isnan(x[i]) or np.isnan(y[i])):
            ax.scatter(x[i], y[i], s=sizes[i], color=colours[i],
                       edgecolors='white', linewidths=0.8, zorder=3, alpha=0.85)
            ax.annotate(labels[i], (x[i], y[i]),
                        textcoords='offset points', xytext=(6, 4), fontsize=8)

    ax.set_xlabel('Mean hole width (nm)')
    ax.set_ylabel('Mean hole depth (nm)')
    ax.set_title('Width vs Depth per Sample\n(bubble size = hole count)', fontweight='bold')

    # Add "better" annotation (lower-left is better)
    ax.annotate('Fewer / shallower holes ->', xy=(0.02, 0.04),
                xycoords='axes fraction', fontsize=8, color='grey', style='italic')
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, 'width_vs_depth.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    _save_txt(os.path.join(out_dir, 'width_vs_depth.txt'),
              pd.DataFrame({'sample': labels,
                            'mean_hole_width_nm': x,
                            'mean_hole_depth_nm': y,
                            'n_holes': n}))


def _plot_threshold_bars(holes_df, labels, colours, threshold_range, out_dir):
    """
    Grouped bar chart: for each sample, show mean hole width at every
    threshold fraction in threshold_range.
    """
    thr_cols = [f'width_at_{int(f*100):02d}pct_nm' for f in threshold_range]
    available = [c for c in thr_cols if c in holes_df.columns]
    if not available:
        return

    pct_labels = [f'{int(f*100)}%' for f in threshold_range
                  if f'width_at_{int(f*100):02d}pct_nm' in available]

    n_samples = len(labels)
    n_thr     = len(available)
    x         = np.arange(n_samples)
    bar_w     = 0.75 / n_thr
    thr_cols_pal = ['#4C9BE8', '#E87C4C', '#2ECC71', '#9B59B6']

    fig, ax = plt.subplots(figsize=(max(7, n_samples * 1.6), 5))

    for ti, (col, pct_lbl) in enumerate(zip(available, pct_labels)):
        means = []
        errs  = []
        for lbl in labels:
            sub = holes_df[holes_df['filename'].apply(_short) == lbl][col].dropna()
            means.append(sub.mean() if len(sub) else float('nan'))
            errs.append(sub.std()   if len(sub) > 1 else 0)

        offset = (ti - n_thr / 2 + 0.5) * bar_w
        tc = thr_cols_pal[ti % len(thr_cols_pal)]
        bars = ax.bar(x + offset, means, bar_w * 0.9,
                      label=f'Threshold {pct_lbl}',
                      color=tc, alpha=0.80, edgecolor='white')
        ax.errorbar(x + offset, means, yerr=errs, fmt='none',
                    ecolor='black', elinewidth=1, capsize=3)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha='right')
    ax.set_ylabel('Mean hole width (nm)')
    ax.set_title('Hole Width at Multiple Thresholds per Sample', fontweight='bold')
    ax.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, 'threshold_width_bars.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # TXT
    txt_rows = {'sample': labels}
    for col, pct_lbl in zip(available, pct_labels):
        means = []
        stds  = []
        for lbl in labels:
            sub = holes_df[holes_df['filename'].apply(_short) == lbl][col].dropna()
            means.append(sub.mean() if len(sub) else float('nan'))
            stds.append(sub.std()   if len(sub) > 1 else float('nan'))
        txt_rows[f'mean_width_{pct_lbl}_nm'] = means
        txt_rows[f'std_width_{pct_lbl}_nm']  = stds
    _save_txt(os.path.join(out_dir, 'threshold_width_bars.txt'), pd.DataFrame(txt_rows))


def _plot_ranking_table(summary_df, labels, out_dir):
    """
    PNG table ranking each sample by:
      - n_holes (fewer = better, rank 1)
      - avg_hole_width_nm (narrower = better)
      - avg_hole_depth_nm (shallower = better)
      - composite score = normalised sum of above ranks
    """
    df = summary_df.copy()
    df['_label'] = labels

    def _rank(col, ascending=True):
        return df[col].rank(ascending=ascending, na_option='bottom').astype(int)

    df['rank_n_holes'] = _rank('n_holes', ascending=True)
    df['rank_width']   = _rank('avg_hole_width_nm', ascending=True)
    df['rank_depth']   = _rank('avg_hole_depth_nm', ascending=True)
    df['composite_rank'] = (df['rank_n_holes'] + df['rank_width'] + df['rank_depth'])
    df = df.sort_values('composite_rank')

    display_cols = ['_label', 'n_holes',
                    'avg_hole_width_nm', 'std_hole_width_nm',
                    'avg_hole_depth_nm', 'std_hole_depth_nm',
                    'rank_n_holes', 'rank_width', 'rank_depth', 'composite_rank']
    col_labels = ['Sample', 'N holes',
                  'Width mean (nm)', 'Width std (nm)',
                  'Depth mean (nm)', 'Depth std (nm)',
                  'Rank N', 'Rank W', 'Rank D', 'Composite']

    tbl_data = []
    for _, row in df[display_cols].iterrows():
        tbl_data.append([
            str(row['_label']),
            str(int(row['n_holes'])) if not np.isnan(row['n_holes']) else 'N/A',
            f"{row['avg_hole_width_nm']:.1f}" if not np.isnan(row['avg_hole_width_nm']) else 'N/A',
            f"{row['std_hole_width_nm']:.1f}" if not np.isnan(row['std_hole_width_nm']) else 'N/A',
            f"{row['avg_hole_depth_nm']:.3f}" if not np.isnan(row['avg_hole_depth_nm']) else 'N/A',
            f"{row['std_hole_depth_nm']:.3f}" if not np.isnan(row['std_hole_depth_nm']) else 'N/A',
            str(int(row['rank_n_holes'])),
            str(int(row['rank_width'])),
            str(int(row['rank_depth'])),
            str(int(row['composite_rank'])),
        ])

    fig_h = max(2.5, 0.5 + 0.45 * len(tbl_data))
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis('off')
    tbl = ax.table(cellText=tbl_data, colLabels=col_labels,
                   cellLoc='center', loc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.4)

    # Highlight header
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor('#2C3E50')
        tbl[0, j].set_text_props(color='white', fontweight='bold')

    # Highlight best (row 0 after sort = lowest composite)
    if len(tbl_data) > 0:
        for j in range(len(col_labels)):
            tbl[1, j].set_facecolor('#D5F5E3')

    ax.set_title('Sample Ranking  (rank 1 = best, lowest composite = overall best)',
                 fontweight='bold', pad=10)
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, 'ranking_table.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # TXT
    out_df = pd.DataFrame(tbl_data, columns=col_labels)
    _save_txt(os.path.join(out_dir, 'ranking_table.txt'), out_df)
