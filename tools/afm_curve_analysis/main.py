"""
AFM Line Profile Analyser
=========================
Processes AFM profile data files from Data/, classifies each line profile
as a hole or protrusion, measures full baseline width and amplitude, then
outputs per-profile and summary CSVs plus (optionally) plots.

OUTPUT FOLDER STRUCTURE
-----------------------
Output/
  <filename>/
    profiles/
      profile_01.png   <- raw + corrected with threshold/width markers
      profile_01.txt   <- Origin-compatible tab-separated data
      ...
    stats/
      boxplot.png / .txt
      violin.png  / .txt
      scatter.png / .txt
      histogram.png / .txt
  <filename>_profiles.csv
  summary.csv

CONFIGURATION (edit the block below)
--------------------------------------
  SAVE_PLOTS           – set False to skip all plotting
  WIDTH_THRESHOLD_FRAC – fraction of amplitude at which width is measured
  N_EDGE_PTS           – edge points used to fit the linear baseline
  MIN_SIGNAL_FRAC      – minimum feature/range ratio (noise rejection)
  DPI                  – plot resolution

Dependencies: numpy, pandas, matplotlib
"""

# ===========================================================================
# CONFIGURATION
# ===========================================================================
SAVE_PLOTS           = True    # False → skip all plotting (faster batch runs)
WIDTH_THRESHOLD_FRAC = 0.20    # width at 5 % of amplitude ≈ full baseline width
N_EDGE_PTS           = 2       # edge points for linear baseline fit
MIN_SIGNAL_FRAC      = 0.10    # feature must be > 10 % of profile range
DPI                  = 150     # figure resolution (dots per inch)
# Width is re-measured at each fraction below to show the sensitivity range.
# The primary reported width still uses WIDTH_THRESHOLD_FRAC.
THRESHOLD_RANGE      = [0.05, 0.10, 0.20]
# ===========================================================================

import os
import glob
import re
import traceback

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')           # non-interactive; safe for batch use
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.family': 'sans-serif',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
COL_HOLE  = '#4C9BE8'
COL_PROT  = '#E87C4C'
COL_BASE  = '#F5A623'
COL_THRES = '#E84C4C'
COL_WIDTH = '#2ECC71'


# ===========================================================================
# PARSING
# ===========================================================================

def parse_afm_file(filepath: str) -> list:
    """
    Parse a Gwyddion-exported AFM profile file.

    Row 0  : Profile 1   Profile 2  ...
    Row 1  : x   y       x   y      ...
    Row 2  : [m] [m]     [m] [m]    ...
    Row 3+ : numeric pairs; missing values shown as '-'

    Returns [{'index': int, 'x': ndarray_m, 'y': ndarray_m}, ...]
    """
    with open(filepath, 'r') as fh:
        lines = fh.readlines()

    if len(lines) < 4:
        raise ValueError(f"File too short: {filepath}")

    n_profiles = len(re.findall(r'Profile\s+\d+', lines[0]))
    if n_profiles == 0:
        raise ValueError(f"No 'Profile N' headers in: {filepath}")

    xs = [[] for _ in range(n_profiles)]
    ys = [[] for _ in range(n_profiles)]

    for line in lines[3:]:
        tokens = line.split()
        if not tokens:
            continue
        for p in range(n_profiles):
            ix, iy = p * 2, p * 2 + 1
            if iy >= len(tokens):
                break
            if tokens[ix] == '-' or tokens[iy] == '-':
                continue
            try:
                xs[p].append(float(tokens[ix]))
                ys[p].append(float(tokens[iy]))
            except ValueError:
                pass

    profiles = []
    for p in range(n_profiles):
        if len(xs[p]) >= 5:
            profiles.append({
                'index': p + 1,
                'x': np.array(xs[p]),
                'y': np.array(ys[p]),
            })
    return profiles


# ===========================================================================
# ANALYSIS HELPERS
# ===========================================================================

def _linear_baseline(x: np.ndarray, y: np.ndarray, n_edge: int) -> np.ndarray:
    """Fit a line to the edge points and return the baseline evaluated at x."""
    n_edge = max(1, min(n_edge, len(x) // 3))
    xb = np.concatenate([x[:n_edge], x[-n_edge:]])
    yb = np.concatenate([y[:n_edge], y[-n_edge:]])
    return np.polyval(np.polyfit(xb, yb, 1), x)


def _crossing_width(x: np.ndarray, signal: np.ndarray,
                    amplitude: float, frac: float):
    """
    Measure the width of a positive peak in `signal` at level frac*amplitude.

    Returns (width_m, x_left_m, x_right_m).
    """
    threshold = frac * amplitude
    above = signal >= threshold
    trans = np.diff(above.astype(int))
    rising  = np.where(trans ==  1)[0]
    falling = np.where(trans == -1)[0]

    if len(rising) > 0:
        li = rising[0]
        denom = signal[li + 1] - signal[li]
        x_left = x[li] + (threshold - signal[li]) / denom * (x[li + 1] - x[li]) if denom else x[li]
    else:
        x_left = x[0]

    if len(falling) > 0:
        ri = falling[-1]
        denom = signal[ri + 1] - signal[ri]
        x_right = x[ri] + (threshold - signal[ri]) / denom * (x[ri + 1] - x[ri]) if denom else x[ri]
    else:
        x_right = x[-1]

    return float(x_right - x_left), float(x_left), float(x_right)


def classify_and_analyse(x: np.ndarray, y: np.ndarray) -> dict | None:
    """
    Classify one line profile and compute its width and amplitude.

    Returns a rich dict (used by both the CSV writer and the plotter),
    or None if the profile is too noisy.
    """
    baseline = _linear_baseline(x, y, N_EDGE_PTS)
    yc = y - baseline

    peak_pos = float(np.max(yc))
    peak_neg = float(np.min(yc))
    data_range = float(np.ptp(yc))

    if data_range == 0:
        return None

    if abs(peak_neg) >= abs(peak_pos):
        feature_type = 'hole'
        amplitude    = abs(peak_neg)
        signal       = -yc
    else:
        feature_type = 'protrusion'
        amplitude    = peak_pos
        signal       = yc

    if amplitude < MIN_SIGNAL_FRAC * data_range:
        return None

    width_m, x_left, x_right = _crossing_width(
        x, signal, amplitude, WIDTH_THRESHOLD_FRAC
    )

    # Compute width at every threshold in THRESHOLD_RANGE for sensitivity analysis
    range_widths = {}
    for frac in THRESHOLD_RANGE:
        w, xl, xr = _crossing_width(x, signal, amplitude, frac)
        key = f'width_at_{int(frac*100):02d}pct_nm'
        range_widths[key] = (w * 1e9, xl, xr)

    return {
        'type':         feature_type,
        'width_nm':     width_m * 1e9,
        'height_nm':    amplitude * 1e9,
        'range_widths': range_widths,     # {key: (width_nm, x_left_m, x_right_m)}
        # --- extra data for plotting ---
        'baseline':   baseline,
        'yc':         yc,
        'signal':     signal,
        'amplitude':  amplitude,
        'threshold':  WIDTH_THRESHOLD_FRAC * amplitude,
        'x_left':     x_left,
        'x_right':    x_right,
    }


# ===========================================================================
# PLOTTING – individual profiles
# ===========================================================================

def _save_origin_txt(path: str, header: str, data: np.ndarray):
    """Save a tab-separated TXT file readable by Origin."""
    np.savetxt(path, data, delimiter='\t', header=header, comments='', fmt='%.6e')


def plot_profile(prof: dict, res: dict | None, out_dir: str):
    """
    Two-panel figure for one profile:
      Top    – raw data + linear baseline
      Bottom – baseline-corrected signal with threshold line, width shading,
               and vertical markers at the crossing points
    """
    idx = prof['index']
    x_nm = prof['x'] * 1e9
    y_nm = prof['y'] * 1e9

    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    fig.subplots_adjust(hspace=0.35)

    # --- Top panel: raw + baseline ---
    ax1 = axes[0]
    ax1.plot(x_nm, y_nm, 'o-', color='steelblue', lw=1.5, ms=4, label='Raw data')

    if res is not None:
        base_nm = res['baseline'] * 1e9
        ax1.plot(x_nm, base_nm, '--', color=COL_BASE, lw=1.5, label='Linear baseline')

    ax1.set_ylabel('Height (nm)')
    title_top = f"Profile {idx}"
    if res is not None:
        title_top += f"  [{res['type'].capitalize()}]"
    ax1.set_title(title_top, fontsize=10, fontweight='bold')
    ax1.legend(fontsize=8)

    # --- Bottom panel: corrected signal with markers ---
    ax2 = axes[1]

    if res is not None:
        sig_nm  = res['signal']    * 1e9
        amp_nm  = res['amplitude'] * 1e9
        thr_nm  = res['threshold'] * 1e9
        xl_nm   = res['x_left']    * 1e9
        xr_nm   = res['x_right']   * 1e9
        w_nm    = res['width_nm']
        h_nm    = res['height_nm']
        ftype   = res['type']

        ax2.plot(x_nm, sig_nm, 'o-', color='steelblue', lw=1.5, ms=4,
                 label='Corrected' + (' (inverted)' if ftype == 'hole' else ''))

        # Zero line
        ax2.axhline(0, color='grey', lw=0.8, ls='-', alpha=0.5)

        # Primary threshold + width markers
        ax2.axhline(thr_nm, color=COL_THRES, lw=1.5, ls='--',
                    label=f'Primary threshold ({WIDTH_THRESHOLD_FRAC*100:.0f}%)')
        ax2.axvline(xl_nm, color=COL_WIDTH, lw=1.5, ls=':')
        ax2.axvline(xr_nm, color=COL_WIDTH, lw=1.5, ls=':', label='Primary width')
        ax2.fill_betweenx([0, thr_nm], xl_nm, xr_nm, alpha=0.12, color=COL_WIDTH)
        ax2.fill_between(x_nm, 0, np.clip(sig_nm, 0, None), alpha=0.08, color='steelblue')
        mid_x = (xl_nm + xr_nm) / 2
        ax2.annotate(
            f'{w_nm:.1f} nm',
            xy=(mid_x, thr_nm), xytext=(mid_x, thr_nm + amp_nm * 0.18),
            ha='center', fontsize=8, color=COL_WIDTH, fontweight='bold',
            arrowprops=dict(arrowstyle='->', color=COL_WIDTH, lw=1.2),
        )

        # Additional threshold range lines
        range_colours = ['#9B59B6', '#1ABC9C', '#E67E22']
        if 'range_widths' in res:
            for ci, (key, (rw, rxl, rxr)) in enumerate(res['range_widths'].items()):
                pct = int(key.split('_')[2].replace('pct', ''))
                if pct == int(WIDTH_THRESHOLD_FRAC * 100):
                    continue   # already drawn above
                rc = range_colours[ci % len(range_colours)]
                rthr = (pct / 100) * amp_nm
                ax2.axhline(rthr, color=rc, lw=1.0, ls=':', alpha=0.7,
                            label=f'{pct}% → {rw:.1f} nm')

        depth_label = 'Depth' if ftype == 'hole' else 'Height'
        ax2.set_title(f'Width = {w_nm:.1f} nm  |  {depth_label} = {h_nm:.3f} nm',
                      fontsize=9)
        ax2.set_ylabel(
            'Height (nm, inverted)' if ftype == 'hole' else 'Height (nm)'
        )
        ax2.legend(fontsize=8, loc='upper right')

        # --- Companion TXT for Origin ---
        yc_nm = res['yc'] * 1e9
        txt_data = np.column_stack([
            x_nm,
            y_nm,
            res['baseline'] * 1e9,
            yc_nm,
            sig_nm,
            np.full(len(x_nm), thr_nm),
        ])
        hdr = 'x_nm\ty_raw_nm\tbaseline_nm\ty_corrected_nm\tsignal_nm\tthreshold_nm'
        _save_origin_txt(os.path.join(out_dir, f'profile_{idx:02d}.txt'), hdr, txt_data)

    else:
        ax2.plot(x_nm, y_nm, 'o-', color='grey', lw=1.5, ms=4)
        ax2.set_title('No clear feature detected', fontsize=9)
        ax2.set_ylabel('Height (nm)')

    ax2.set_xlabel('Position (nm)')
    plt.tight_layout()
    out_path = os.path.join(out_dir, f'profile_{idx:02d}.png')
    fig.savefig(out_path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)


# ===========================================================================
# PLOTTING – statistics
# ===========================================================================

def plot_statistics(per_profile: list, stats_dir: str, fname: str):
    """
    Generate statistical plots for all classified profiles in one file:
      1. Box plot  – width and amplitude
      2. Violin    – width and amplitude  (needs ≥ 3 points per group)
      3. Scatter   – width vs amplitude
      4. Histogram – width and amplitude distributions
    Each plot is saved as .png and an Origin-compatible .txt.
    """
    df = pd.DataFrame(per_profile)
    df = df[df['feature_type'] != 'undetermined'].dropna(subset=['width_nm', 'height_nm'])

    if df.empty:
        print("    (No classified profiles – skipping stats plots)")
        return

    holes = df[df['feature_type'] == 'hole']
    prots = df[df['feature_type'] == 'protrusion']

    def _groups(col):
        grps, labs, cols = [], [], []
        if not holes.empty:
            grps.append(holes[col].values); labs.append('Holes');      cols.append(COL_HOLE)
        if not prots.empty:
            grps.append(prots[col].values); labs.append('Protrusions'); cols.append(COL_PROT)
        return grps, labs, cols

    # ------------------------------------------------------------------ #
    # 1. Box plot
    # ------------------------------------------------------------------ #
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    for ax, col, ylabel, title in zip(
        axes,
        ['width_nm', 'height_nm'],
        ['Width (nm)', 'Depth / Height (nm)'],
        ['Feature Width', 'Feature Amplitude'],
    ):
        grps, labs, cols = _groups(col)
        if not grps:
            continue
        bp = ax.boxplot(grps, tick_labels=labs, patch_artist=True, notch=False,
                        medianprops=dict(color='black', lw=2))
        for patch, c in zip(bp['boxes'], cols):
            patch.set_facecolor(c); patch.set_alpha(0.65)
        # Overlay individual points
        for i, (g, c) in enumerate(zip(grps, cols), start=1):
            ax.scatter(np.random.normal(i, 0.06, len(g)), g,
                       color=c, s=30, zorder=3, edgecolors='white', lw=0.5)
        ax.set_ylabel(ylabel); ax.set_title(title)

    fig.suptitle(f'{fname} — Box Plots', fontsize=11, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(stats_dir, 'boxplot.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    df[['profile', 'feature_type', 'width_nm', 'height_nm']].to_csv(
        os.path.join(stats_dir, 'boxplot.txt'), sep='\t', index=False)

    # ------------------------------------------------------------------ #
    # 2. Violin plot (≥ 2 points per group required)
    # ------------------------------------------------------------------ #
    viable = {
        'holes': holes if len(holes) >= 2 else None,
        'prots': prots if len(prots) >= 2 else None,
    }
    if any(v is not None for v in viable.values()):
        fig, axes = plt.subplots(1, 2, figsize=(10, 5))
        for ax, col, ylabel in zip(
            axes,
            ['width_nm', 'height_nm'],
            ['Width (nm)', 'Depth / Height (nm)'],
        ):
            vdata, vlabs, vcols = [], [], []
            if viable['holes'] is not None:
                vdata.append(viable['holes'][col].values)
                vlabs.append('Holes'); vcols.append(COL_HOLE)
            if viable['prots'] is not None:
                vdata.append(viable['prots'][col].values)
                vlabs.append('Protrusions'); vcols.append(COL_PROT)

            if not vdata:
                continue
            vp = ax.violinplot(vdata, positions=range(1, len(vdata) + 1),
                               showmeans=True, showmedians=True, showextrema=True)
            for body, c in zip(vp['bodies'], vcols):
                body.set_facecolor(c); body.set_alpha(0.55)
            for part in ('cmeans', 'cmedians', 'cbars', 'cmins', 'cmaxes'):
                if part in vp:
                    vp[part].set_color('black'); vp[part].set_lw(1.2)

            # Overlay strip
            for i, (g, c) in enumerate(zip(vdata, vcols), start=1):
                ax.scatter(np.random.normal(i, 0.04, len(g)), g,
                           color=c, s=25, zorder=3, edgecolors='white', lw=0.4)

            ax.set_xticks(range(1, len(vdata) + 1))
            ax.set_xticklabels(vlabs)
            ax.set_ylabel(ylabel)

        fig.suptitle(f'{fname} — Violin Plots', fontsize=11, fontweight='bold')
        plt.tight_layout()
        fig.savefig(os.path.join(stats_dir, 'violin.png'), dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        df[['profile', 'feature_type', 'width_nm', 'height_nm']].to_csv(
            os.path.join(stats_dir, 'violin.txt'), sep='\t', index=False)

    # ------------------------------------------------------------------ #
    # 3. Scatter: width vs amplitude
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(7, 5))
    for subset, c, label in [(holes, COL_HOLE, 'Holes'), (prots, COL_PROT, 'Protrusions')]:
        if subset.empty:
            continue
        ax.scatter(subset['width_nm'], subset['height_nm'],
                   color=c, s=60, label=label, zorder=3, edgecolors='white', lw=0.5)
        for _, row in subset.iterrows():
            ax.annotate(f"P{int(row['profile'])}",
                        (row['width_nm'], row['height_nm']),
                        textcoords='offset points', xytext=(5, 4), fontsize=7.5)
    ax.set_xlabel('Width (nm)')
    ax.set_ylabel('Depth / Height (nm)')
    ax.set_title(f'{fname} — Width vs Amplitude')
    ax.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(stats_dir, 'scatter.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    df[['profile', 'feature_type', 'width_nm', 'height_nm']].to_csv(
        os.path.join(stats_dir, 'scatter.txt'), sep='\t', index=False)

    # ------------------------------------------------------------------ #
    # 4. Histograms
    # ------------------------------------------------------------------ #
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    for ax, col, xlabel in zip(
        axes,
        ['width_nm', 'height_nm'],
        ['Width (nm)', 'Depth / Height (nm)'],
    ):
        grps, labs, cols = _groups(col)
        bins = max(5, len(df) // 2)
        for g, c, lab in zip(grps, cols, labs):
            ax.hist(g, bins=bins, color=c, alpha=0.60, label=lab, edgecolor='white')
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Count')
        ax.legend(fontsize=8)

    fig.suptitle(f'{fname} — Histograms', fontsize=11, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(stats_dir, 'histogram.png'), dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    df[['profile', 'feature_type', 'width_nm', 'height_nm']].to_csv(
        os.path.join(stats_dir, 'histogram.txt'), sep='\t', index=False)


# ===========================================================================
# PER-FILE PROCESSING
# ===========================================================================

def _safe_mean(lst): return float(np.mean(lst)) if lst else float('nan')
def _safe_std(lst):  return float(np.std(lst))  if lst else float('nan')


def process_file(filepath: str, output_root: str) -> tuple:
    profiles = parse_afm_file(filepath)
    fname    = os.path.splitext(os.path.basename(filepath))[0]

    # Build output sub-directories
    file_dir    = os.path.join(output_root, fname)
    profile_dir = os.path.join(file_dir, 'profiles')
    stats_dir   = os.path.join(file_dir, 'stats')
    for d in (profile_dir, stats_dir):
        os.makedirs(d, exist_ok=True)

    prot_w, prot_h = [], []
    hole_w, hole_d = [], []
    per_profile_rows = []

    for prof in profiles:
        res = classify_and_analyse(prof['x'], prof['y'])

        if SAVE_PLOTS:
            plot_profile(prof, res, profile_dir)

        if res is None:
            ftype = 'undetermined'; w = h = float('nan')
        else:
            ftype = res['type']; w = res['width_nm']; h = res['height_nm']
            if ftype == 'protrusion':
                prot_w.append(w); prot_h.append(h)
            else:
                hole_w.append(w); hole_d.append(h)

        row = {
            'filename':     os.path.basename(filepath),
            'profile':      prof['index'],
            'n_points':     len(prof['x']),
            'feature_type': ftype,
            'width_nm':     round(w, 3) if not np.isnan(w) else float('nan'),
            'height_nm':    round(h, 3) if not np.isnan(h) else float('nan'),
        }
        # Add per-threshold widths
        if res is not None and 'range_widths' in res:
            for key, (rw, _, _) in res['range_widths'].items():
                row[key] = round(rw, 3)
        else:
            for frac in THRESHOLD_RANGE:
                row[f'width_at_{int(frac*100):02d}pct_nm'] = float('nan')
        per_profile_rows.append(row)

    if SAVE_PLOTS:
        plot_statistics(per_profile_rows, stats_dir, fname)

    summary = {
        'filename':                 os.path.basename(filepath),
        'n_profiles':               len(profiles),
        'n_protrusions':            len(prot_w),
        'avg_protrusion_width_nm':  _safe_mean(prot_w),
        'std_protrusion_width_nm':  _safe_std(prot_w),
        'avg_protrusion_height_nm': _safe_mean(prot_h),
        'std_protrusion_height_nm': _safe_std(prot_h),
        'n_holes':                  len(hole_w),
        'avg_hole_width_nm':        _safe_mean(hole_w),
        'std_hole_width_nm':        _safe_std(hole_w),
        'avg_hole_depth_nm':        _safe_mean(hole_d),
        'std_hole_depth_nm':        _safe_std(hole_d),
    }

    return summary, per_profile_rows


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir   = os.path.join(script_dir, 'Data')
    output_dir = os.path.join(script_dir, 'Output')
    os.makedirs(output_dir, exist_ok=True)

    txt_files = sorted(glob.glob(os.path.join(data_dir, '*.txt')))
    if not txt_files:
        print(f"No .txt files found in {data_dir}")
        return

    all_summaries    = []
    all_per_profiles = []

    for filepath in txt_files:
        fname = os.path.basename(filepath)
        print(f"\n{'='*60}\nProcessing: {fname}\n{'='*60}")
        try:
            summary, per_profile = process_file(filepath, output_dir)
            all_summaries.append(summary)
            all_per_profiles.extend(per_profile)

            base      = os.path.splitext(fname)[0]
            prof_path = os.path.join(output_dir, f'{base}_profiles.csv')
            pd.DataFrame(per_profile).to_csv(prof_path, index=False)

            def _f(v): return f"{v:.2f}" if not np.isnan(v) else "N/A"

            print(f"  Profiles : {summary['n_profiles']}")
            print(f"  PROTRUSIONS ({summary['n_protrusions']})")
            print(f"    Width  : {_f(summary['avg_protrusion_width_nm'])} +/- {_f(summary['std_protrusion_width_nm'])} nm")
            print(f"    Height : {_f(summary['avg_protrusion_height_nm'])} +/- {_f(summary['std_protrusion_height_nm'])} nm")
            print(f"  HOLES ({summary['n_holes']})")
            print(f"    Width  : {_f(summary['avg_hole_width_nm'])} +/- {_f(summary['std_hole_width_nm'])} nm")
            print(f"    Depth  : {_f(summary['avg_hole_depth_nm'])} +/- {_f(summary['std_hole_depth_nm'])} nm")
            if SAVE_PLOTS:
                print(f"  Plots -> Output/{base}/")

        except Exception as exc:
            print(f"  ERROR: {exc}")
            traceback.print_exc()

    summary_path = os.path.join(output_dir, 'summary.csv')
    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_csv(summary_path, index=False)
    print(f"\n{'='*60}\nSummary CSV -> {summary_path}")

    # Cross-file comparison (only meaningful with 2+ files, but runs either way)
    if len(all_summaries) >= 1 and SAVE_PLOTS:
        try:
            from comparison import plot_cross_file_comparison
            comp_dir = os.path.join(output_dir, 'comparison')
            os.makedirs(comp_dir, exist_ok=True)
            all_prof_df = pd.DataFrame(all_per_profiles)
            plot_cross_file_comparison(summary_df, all_prof_df, comp_dir, THRESHOLD_RANGE)
            print(f"Comparison plots -> {comp_dir}")
        except Exception as exc:
            print(f"Comparison plots ERROR: {exc}")
            traceback.print_exc()
    print('='*60)


if __name__ == '__main__':
    main()
