# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

"""
AFM 3D Surface Analyser — IBW Edition
======================================
Batch-processes pre-flattened Asylum/Igor .ibw AFM height maps from Data/.
Detects holes and protrusions via thresholding + connected-component labelling,
measures each feature, produces interactive Plotly HTML plots, and exports CSVs.

No plane-fitting is applied — files are assumed to be already levelled.

OUTPUT STRUCTURE
----------------
Output/
  <filename>/
    height_map_2d.html        ← interactive Plotly height map
    feature_map.html          ← annotated feature map (holes=blue, prots=orange)
    height_map_3d.html        ← interactive 3D surface render
    histograms.html           ← size/depth distribution charts
    holes.csv                 ← per-hole measurements
    protrusions.csv           ← per-protrusion measurements
  summary.csv                 ← one row per file
  comparison/                 ← cross-file comparison plots

CONFIGURATION (edit the block below)
--------------------------------------
  CHANNEL           – IBW channel index to use as height (0 = first/height)
  HOLE_THRESHOLD_SD – holes: interior mean or median minus N·spread (std or MAD)
  PROT_THRESHOLD_SD – protrusions: interior mean or median plus N·spread
  USE_ROBUST_THRESHOLD – if True, use median and MAD (scaled to σ) instead of mean/std
  ANNULUS_WIDTH_NM / ANNULUS_WIDTH_PX – rim width for hole depth (0 = depth vs global mean)
  MIN_EQUIV_DIAMETER_NM – reject holes smaller than this diameter (0 = off)
  MIN_AREA_PX       – minimum blob size in pixels (noise rejection)
  SAVE_PLOTS        – set False to skip HTML generation (faster batch)
  DOWNSAMPLE_3D     – max pixels per side for 3D surface (performance)
  FIXED_DEPTH_CUTOFFS_NM / PLOT_COMP_FIXED_DEPTH – median-referenced depth % in summary + comparison plot
  PLOT_COMP_DEPTH_OVER_RQ – detected-hole depth ÷ Rq comparison plot

Dependencies: igor2, numpy, scipy, pandas, plotly
"""

# ===========================================================================
# CONFIGURATION
# ===========================================================================
CHANNEL           = 0      # IBW channel index for height data
HOLE_THRESHOLD_SD = 2.5    # holes: pixels below mean - N * std 1.5
PROT_THRESHOLD_SD = 2.5    # protrusions: pixels above mean + N * std 1.5
MIN_AREA_PX       = 5    # minimum feature area in pixels
MIN_DEPTH_NM      = 1   # minimum depth for a hole to be counted (nm)
MIN_HEIGHT_NM     = 1.5   # minimum height for a protrusion to be counted (nm)
SAVE_PLOTS        = True  # Master switch for all plots

# --- Edge artifact rejection (unlevelled borders → false giant "holes") ---
# Widen EDGE_EXCLUDE_NM if strips remain; shrink if real features near the frame vanish.
EDGE_EXCLUDE_NM = 300.0   # nm cropped from each border for detection (0 = off)
EDGE_EXCLUDE_PX = 0       # if > 0, overrides EDGE_EXCLUDE_NM (border width in pixels)
THRESHOLD_USE_INTERIOR_ONLY = True  # mean/std for thresholds use interior pixels only
REJECT_FEATURES_TOUCHING_IMAGE_BORDER = True  # discard blobs touching image edge (0 / max row/col)

# --- Robust hole detection (reduces false positives on rough / long-tailed surfaces) ---
USE_ROBUST_THRESHOLD = True
# When True: threshold uses median ± N·(1.4826·MAD); mean_nm/std_nm still reported for reference.
# Annulus depth: rim (median Z outside hole) minus pit min; 0 = legacy depth vs global mean.
ANNULUS_WIDTH_NM = 40.0          # ring built by dilating mask; ~texture/hole scale (0 = off)
ANNULUS_WIDTH_PX = 0             # if > 0, overrides ANNULUS_WIDTH_NM
MIN_EQUIV_DIAMETER_NM = 0.0      # drop blobs smaller than this diameter (0 = off)

# --- Per-Sample Plots ---
PLOT_2D_MAP          = True
PLOT_3D_SURFACE      = False
PLOT_FEATURE_MAP     = True
PLOT_HISTOGRAMS      = True
PLOT_ROUGHNESS       = True

# --- Cross-Sample Comparison Plots ---
PLOT_COMP_COUNTS     = True
PLOT_COMP_DENSITY    = True
PLOT_COMP_COVERAGE   = True
PLOT_COMP_ROUGHNESS  = True
PLOT_COMP_BOXPLOTS   = True
PLOT_COMP_BUBBLE     = True
PLOT_COMP_OVERVIEW   = False
PLOT_COMP_RANKING    = False
# Apples-to-apples: % of interior pixels at least X nm below image median (same edge mask as detection)
PLOT_COMP_FIXED_DEPTH = False
# Detected holes only: depth / Rq (roughness-normalised severity)
PLOT_COMP_DEPTH_OVER_RQ = False
# Per base_sample_name: one HTML with height + feature map rows (reload .ibw for threshold QA)
PLOT_COMP_THRESHOLD_REVIEW = True

# --- PNG Export Configuration ---
SAVE_PNGS = False  # Master override for ALL PNGs. If False, no PNGs are generated.

# Per-Sample PNGs
SAVE_PNG_2D_MAP      = False
SAVE_PNG_3D_SURFACE  = False
SAVE_PNG_FEATURE_MAP = False
SAVE_PNG_HISTOGRAMS  = False
SAVE_PNG_ROUGHNESS   = False

# Cross-Sample Comparison PNGs
SAVE_PNG_COMP_COUNTS       = True
SAVE_PNG_COMP_DENSITY      = True
SAVE_PNG_COMP_COVERAGE     = True
SAVE_PNG_COMP_ROUGHNESS    = True
SAVE_PNG_COMP_BOXPLOTS     = True
SAVE_PNG_COMP_BUBBLE       = True
SAVE_PNG_COMP_OVERVIEW     = False
SAVE_PNG_COMP_RANKING      = True
SAVE_PNG_COMP_FIXED_DEPTH  = True
SAVE_PNG_COMP_DEPTH_OVER_RQ= True

# Cutoffs (nm) for fixed-depth comparison; edit as needed
FIXED_DEPTH_CUTOFFS_NM = (0.5,0.8,1.0, 1.2,1.5,2,5 )

DOWNSAMPLE_3D     = 250   # max pixels per side for 3D plot  0 = no limit) 300 origionaly 
TEMPLATES         = [('plotly_white', '_light')]
REPLICATE_STRIP_PATTERN = r'[-_ ]?\d+$'  # strip trailing replicate ids
LEGACY_RUN_TO_RESTRUCTURE = 'Run_2026-05-07_13-50-01final_comparison+2pacz2'
# ===========================================================================

import os
import re
import glob
import shutil
import traceback
from datetime import datetime
from typing import Tuple

import numpy as np
import pandas as pd
from scipy import ndimage
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
COL_HOLE = '#4C9BE8'
COL_PROT = '#E87C4C'
PLOTLY_TEMPLATE = 'plotly_dark'


# ===========================================================================
# IBW LOADING
# ===========================================================================

def load_ibw(filepath: str):
    """
    Load an Asylum/Igor .ibw file and return the height channel as a 2D array.

    Returns
    -------
    z_nm        : 2D ndarray, height values in nanometres
    pixel_nm    : float, pixel size in nm (assumes square pixels)
    scan_x_um   : float, total scan width in µm
    scan_y_um   : float, total scan height in µm
    """
    from igor2 import binarywave
    ibw   = binarywave.load(filepath)
    wave  = ibw['wave']
    data  = wave['wData'].astype(np.float64)
    wh    = wave['wave_header']
    sfA   = wh['sfA']

    pixel_nm = float(sfA[0]) * 1e9   # metres → nm

    if data.ndim == 3:
        z_m = data[:, :, CHANNEL]
    elif data.ndim == 2:
        z_m = data
    else:
        raise ValueError(f"Unexpected data dimensions: {data.shape}")

    z_nm      = z_m * 1e9
    ny, nx    = z_nm.shape
    scan_x_um = nx * pixel_nm / 1000.0
    scan_y_um = ny * pixel_nm / 1000.0

    return z_nm, pixel_nm, scan_x_um, scan_y_um


# ===========================================================================
# SURFACE ROUGHNESS & SCAN QUALITY
# ===========================================================================

def compute_scan_quality(z_nm: np.ndarray, Rq: float) -> dict:
    """
    Computes mathematical metrics to evaluate scan quality (blurriness, streaking).
    """
    # 1. Line Correlation (Streaking / Tracking)
    # Average Pearson correlation between adjacent horizontal scan rows.
    # Lower than 0.5 usually means uncorrelated lines (horrible noise).
    # Higher than 0.95 means lines are almost identical.
    valid_rows = [row for row in z_nm if not np.all(np.isnan(row))]
    line_corrs = []
    
    if len(valid_rows) > 1:
        for i in range(len(valid_rows) - 1):
            row1, row2 = valid_rows[i], valid_rows[i+1]
            if np.std(row1) > 0 and np.std(row2) > 0:
                corr = np.corrcoef(row1, row2)[0, 1]
                if not np.isnan(corr):
                    line_corrs.append(corr)
    
    mean_corr = float(np.mean(line_corrs)) if line_corrs else float('nan')

    # 2. Sharpness / Blur (Laplacian Variance)
    # A blurry image lacks high-frequency data, meaning its Laplacian has a low variance.
    # We normalise z_nm by Rq so that "naturally flat" samples aren't unfairly penalised.
    sharpness = float('nan')
    if Rq > 0:
        norm_z = (z_nm - np.nanmean(z_nm)) / Rq
        norm_z = np.nan_to_num(norm_z, nan=0.0)
        lap = ndimage.laplace(norm_z)
        sharpness = float(np.var(lap))

    return {
        'line_correlation': round(mean_corr, 4),
        'sharpness_score': round(sharpness, 4),
    }

def compute_roughness(z_nm: np.ndarray) -> dict:
    """
    Compute standard AFM surface roughness parameters from a height map.

    Metrics returned
    ----------------
    Ra      arithmetic mean roughness  = mean |z - z_mean|          (nm)
    Rq      RMS roughness              = sqrt(mean (z - z_mean)^2)  (nm)
    Rz      max height range           = z_max - z_min              (nm)
    Rpv     robust peak-valley         = P99 - P01 (excl. outliers) (nm)
    Rsk     skewness  < 0 → more valleys/holes, > 0 → more peaks
    Rku     kurtosis  > 3 → sharp features, < 3 → rounded
    z_min   global minimum height                                    (nm)
    z_max   global maximum height                                    (nm)
    z_mean  mean height                                              (nm)
    z_p01   1st  percentile (valley floor)                          (nm)
    z_p25   25th percentile (lower quartile)                        (nm)
    z_p50   median                                                   (nm)
    z_p75   75th percentile (upper quartile)                        (nm)
    z_p99   99th percentile (peak ceiling)                          (nm)
    """
    valid = z_nm[~np.isnan(z_nm)].astype(np.float64)
    if len(valid) == 0:
        return {k: float('nan') for k in [
            'Ra','Rq','Rz','Rpv','Rsk','Rku',
            'z_min','z_max','z_mean',
            'z_p01','z_p25','z_p50','z_p75','z_p99',
        ]}

    z_mean = float(np.mean(valid))
    dz     = valid - z_mean
    Rq     = float(np.sqrt(np.mean(dz ** 2)))

    return {
        'Ra':    round(float(np.mean(np.abs(dz))), 6),
        'Rq':    round(Rq, 6),
        'Rz':    round(float(valid.max() - valid.min()), 6),
        'Rpv':   round(float(np.percentile(valid, 99) - np.percentile(valid, 1)), 6),
        'Rsk':   round(float(np.mean(dz ** 3) / Rq ** 3) if Rq > 0 else 0.0, 4),
        'Rku':   round(float(np.mean(dz ** 4) / Rq ** 4) if Rq > 0 else 0.0, 4),
        'z_min': round(float(valid.min()),                6),
        'z_max': round(float(valid.max()),                6),
        'z_mean':round(z_mean,                            6),
        'z_p01': round(float(np.percentile(valid,  1)),   4),
        'z_p25': round(float(np.percentile(valid, 25)),   4),
        'z_p50': round(float(np.percentile(valid, 50)),   4),
        'z_p75': round(float(np.percentile(valid, 75)),   4),
        'z_p99': round(float(np.percentile(valid, 99)),   4),
    }


def plot_roughness_analysis(z_nm, roughness: dict, stats: dict,
                            pixel_nm: float, out_dir: str, fname: str, template: str, suffix: str):
    """
    Two-panel interactive Plotly page:
      Left  — height distribution histogram with threshold & percentile lines
      Right — metrics summary table
    """
    valid = z_nm[~np.isnan(z_nm)].flatten()

    # --- histogram ---
    nbins = min(300, max(50, len(valid) // 500))
    counts, bin_edges = np.histogram(valid, bins=nbins)
    bin_centres = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    # Gaussian overlay
    from scipy.stats import norm as _norm
    gauss_y = (_norm.pdf(bin_centres, roughness['z_mean'], roughness['Rq'])
               * len(valid) * (bin_edges[1] - bin_edges[0]))

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.55, 0.45],
        specs=[[{'type': 'xy'}, {'type': 'table'}]],
        subplot_titles=['Height Distribution', 'Surface Metrics'],
    )

    # Histogram
    fig.add_trace(go.Bar(
        x=bin_centres, y=counts,
        marker_color='#4C9BE8', opacity=0.70,
        name='Height distribution',
        hovertemplate='z: %{x:.3f} nm<br>Count: %{y}<extra></extra>',
    ), row=1, col=1)

    # Gaussian fit
    fig.add_trace(go.Scatter(
        x=bin_centres, y=gauss_y,
        mode='lines', line=dict(color='#F5A623', width=2, dash='dash'),
        name='Gaussian fit',
    ), row=1, col=1)

    # Vertical reference lines via shapes (added to layout after)
    line_col = 'black' if template == 'plotly_white' else 'white'
    line_defs = [
        (roughness['z_mean'],  line_col,   'mean',   'solid'),
        (roughness['z_p01'],   '#9B59B6', 'P01',    'dot'),
        (roughness['z_p99'],   '#9B59B6', 'P99',    'dot'),
        (stats['hole_thresh_nm'], '#4C9BE8', 'hole thr', 'dashdot'),
        (stats['prot_thresh_nm'], '#E87C4C', 'prot thr', 'dashdot'),
    ]
    for z_val, col, label, dash in line_defs:
        fig.add_vline(
            x=z_val, line=dict(color=col, width=1.5, dash=dash),
            annotation_text=f' {label}', annotation_font_size=9,
            annotation_font_color=col, row=1, col=1,
        )

    fig.update_xaxes(title_text='Height (nm)', row=1, col=1)
    fig.update_yaxes(title_text='Pixel count', row=1, col=1)

    # Metrics table
    metric_rows = [
        ('Ra  (arithmetic roughness)', f"{roughness['Ra']*1e3:.3f} pm"
         if roughness['Ra'] < 0.01 else f"{roughness['Ra']:.4f} nm"),
        ('Rq  (RMS roughness)',        f"{roughness['Rq']*1e3:.3f} pm"
         if roughness['Rq'] < 0.01 else f"{roughness['Rq']:.4f} nm"),
        ('Rz  (max range)',            f"{roughness['Rz']:.4f} nm"),
        ('Rpv (P99 - P01)',            f"{roughness['Rpv']:.4f} nm"),
        ('Rsk (skewness)',             f"{roughness['Rsk']:.3f}"),
        ('Rku (kurtosis)',             f"{roughness['Rku']:.3f}"),
        ('', ''),
        ('z minimum',                 f"{roughness['z_min']:.4f} nm"),
        ('z maximum',                 f"{roughness['z_max']:.4f} nm"),
        ('z mean',                    f"{roughness['z_mean']:.4f} nm"),
        ('P01 (valley floor)',        f"{roughness['z_p01']:.4f} nm"),
        ('P25 (lower quartile)',      f"{roughness['z_p25']:.4f} nm"),
        ('P50 (median)',              f"{roughness['z_p50']:.4f} nm"),
        ('P75 (upper quartile)',      f"{roughness['z_p75']:.4f} nm"),
        ('P99 (peak ceiling)',        f"{roughness['z_p99']:.4f} nm"),
        ('', ''),
        ('Scan Sharpness Score',      f"{roughness.get('sharpness_score', 0):.3f}"),
        ('Scan Line Correlation',     f"{roughness.get('line_correlation', 0):.3f}"),
    ]
    if template == 'plotly_white':
        row_colours = ['#e6f2ff' if i < 6 else ('#ffffff' if i == 6 or i == 15 else '#f8f9fa') for i in range(len(metric_rows))]
        font_color = 'black'
    else:
        row_colours = ['#1e3a5f' if i < 6 else ('#2a2a2a' if i == 6 or i == 15 else '#1a2535') for i in range(len(metric_rows))]
        font_color = 'white'

    fig.add_trace(go.Table(
        header=dict(
            values=['<b>Metric</b>', '<b>Value</b>'],
            fill_color='#2C3E50', font=dict(color='white', size=11),
            align='left', height=30,
        ),
        cells=dict(
            values=[[r[0] for r in metric_rows], [r[1] for r in metric_rows]],
            fill_color=[row_colours],
            font=dict(color=font_color, size=10),
            align=['left', 'right'], height=26,
        ),
    ), row=1, col=2)

    fig.update_layout(
        title=f'<b>{fname}</b> — Surface Roughness Analysis',
        template=template,
        width=1200, height=560,
        font=dict(family='Arial, sans-serif'),
        showlegend=True,
        legend=dict(x=0.02, y=0.98),
    )
    out_path = os.path.join(out_dir, f'roughness_analysis{suffix}.html')
    fig.write_html(out_path, include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_ROUGHNESS:
        try:
            fig.write_image(out_path.replace('.html', '.png'), scale=2)
        except Exception as e:
            pass
    return out_path


# ===========================================================================
# FEATURE DETECTION
# ===========================================================================


def interior_valid_mask(z_nm: np.ndarray, pixel_nm: float) -> np.ndarray:
    """
    True inside the scan, False in a border strip used to suppress edge artifacts.
    """
    ny, nx = z_nm.shape
    interior = np.ones((ny, nx), dtype=bool)
    if EDGE_EXCLUDE_PX > 0:
        b = int(EDGE_EXCLUDE_PX)
    elif EDGE_EXCLUDE_NM > 0:
        b = int(np.ceil(float(EDGE_EXCLUDE_NM) / float(pixel_nm)))
    else:
        return interior
    if b <= 0:
        return interior
    max_b = max(0, min(nx, ny) // 2 - 1)
    b = min(b, max_b)
    if b <= 0:
        return interior
    interior[:] = False
    interior[b : ny - b, b : nx - b] = True
    return interior


def _mad_sigma_from_valid(z: np.ndarray) -> Tuple[float, float, float]:
    """Return median, MAD, and MAD scaled to Gaussian sigma (1.4826·MAD)."""
    z = np.asarray(z, dtype=np.float64)
    z = z[np.isfinite(z)]
    if z.size == 0:
        return float('nan'), float('nan'), float('nan')
    med = float(np.median(z))
    mad = float(np.median(np.abs(z - med)))
    sigma = 1.4826 * mad if mad > 0 else 0.0
    return med, mad, sigma


def _hole_depth_from_rim(z_nm: np.ndarray, region: np.ndarray, pixel_nm: float,
                         background_mean: float) -> Tuple[float, float, float, str]:
    """
    Hole depth: median Z on dilated ring outside the blob minus pit minimum.
    If annulus width is 0 or ring has no valid pixels, fall back to global background_mean.
    """
    z_pix = z_nm[region]
    peak_z = float(np.nanmin(z_pix))
    if ANNULUS_WIDTH_PX > 0:
        annulus_px = max(1, int(ANNULUS_WIDTH_PX))
    elif ANNULUS_WIDTH_NM > 0:
        annulus_px = max(1, int(np.ceil(float(ANNULUS_WIDTH_NM) / float(pixel_nm))))
    else:
        return abs(background_mean - peak_z), background_mean, peak_z, 'global'

    dil = region.astype(bool)
    struct = ndimage.generate_binary_structure(2, 2)
    for _ in range(annulus_px):
        dil = ndimage.binary_dilation(dil, structure=struct)
    ring = dil & ~region
    z_ring = z_nm[ring]
    z_ring = z_ring[np.isfinite(z_ring)]
    if z_ring.size == 0:
        return abs(background_mean - peak_z), background_mean, peak_z, 'global_fallback'
    rim = float(np.median(z_ring))
    depth = max(0.0, rim - peak_z)
    return depth, rim, peak_z, 'annulus'


def fixed_depth_pct_column(cutoff_nm: float) -> str:
    """Summary column name for % interior pixels with (median - z) >= cutoff_nm."""
    return f'fixdep_{str(cutoff_nm).replace(".", "p")}_pct'


def compute_fixed_depth_below_median_metrics(z_nm: np.ndarray, pixel_nm: float) -> dict:
    """
    For each cutoff in FIXED_DEPTH_CUTOFFS_NM, fraction of valid interior pixels where
    z is at least that many nm below the median height (interior only; same mask as detection).
    """
    not_nan = ~np.isnan(z_nm)
    interior = interior_valid_mask(z_nm, pixel_nm)
    valid = interior & not_nan
    out = {}
    if not np.any(valid):
        for c in FIXED_DEPTH_CUTOFFS_NM:
            out[fixed_depth_pct_column(c)] = float('nan')
        out['fixdep_median_ref_nm'] = float('nan')
        return out
    z_med = float(np.nanmedian(z_nm[valid]))
    dep = z_med - z_nm
    n_pix = float(np.sum(valid))
    for c in FIXED_DEPTH_CUTOFFS_NM:
        pct = 100.0 * float(np.sum((dep >= float(c)) & valid)) / n_pix
        out[fixed_depth_pct_column(c)] = round(pct, 6)
    out['fixdep_median_ref_nm'] = round(z_med, 6)
    return out


def detect_features(z_nm: np.ndarray, pixel_nm: float):
    """
    Threshold a pre-levelled height map to create hole and protrusion masks.

    Returns
    -------
    hole_mask   : bool 2D array
    prot_mask   : bool 2D array
    stats       : dict with mean_nm, std_nm, hole_thresh_nm, prot_thresh_nm
    """
    not_nan = ~np.isnan(z_nm)
    interior = interior_valid_mask(z_nm, pixel_nm)

    if THRESHOLD_USE_INTERIOR_ONLY:
        stats_mask = interior & not_nan
    else:
        stats_mask = not_nan
    valid = z_nm[stats_mask]
    if valid.size == 0 or not np.any(np.isfinite(valid)):
        valid = z_nm[not_nan]
    mean_z = float(np.nanmean(valid))
    std_z = float(np.nanstd(valid))

    med_z, mad_z, sigma_rob = _mad_sigma_from_valid(valid)
    if USE_ROBUST_THRESHOLD and np.isfinite(sigma_rob) and sigma_rob > 0:
        hole_thresh = med_z - HOLE_THRESHOLD_SD * sigma_rob
        prot_thresh = med_z + PROT_THRESHOLD_SD * sigma_rob
    elif USE_ROBUST_THRESHOLD and np.isfinite(med_z) and std_z > 0:
        hole_thresh = med_z - HOLE_THRESHOLD_SD * std_z
        prot_thresh = med_z + PROT_THRESHOLD_SD * std_z
    else:
        hole_thresh = mean_z - HOLE_THRESHOLD_SD * std_z
        prot_thresh = mean_z + PROT_THRESHOLD_SD * std_z

    hole_mask = (z_nm < hole_thresh) & not_nan & interior
    prot_mask = (z_nm > prot_thresh) & not_nan & interior

    stats = dict(
        mean_nm       = mean_z,
        std_nm        = std_z,
        hole_thresh_nm= hole_thresh,
        prot_thresh_nm= prot_thresh,
        robust_median_nm=round(med_z, 6) if np.isfinite(med_z) else float('nan'),
        robust_mad_nm=round(mad_z, 6) if np.isfinite(mad_z) else float('nan'),
        robust_sigma_nm=round(sigma_rob, 6) if np.isfinite(sigma_rob) else float('nan'),
        threshold_uses_robust=bool(USE_ROBUST_THRESHOLD),
    )
    return hole_mask, prot_mask, stats


# ===========================================================================
# FEATURE MEASUREMENT
# ===========================================================================

def measure_features(z_nm: np.ndarray, mask: np.ndarray,
                     pixel_nm: float, feature_type: str,
                     background_mean: float):
    """
    Label connected regions in `mask` and measure each feature.

    Returns
    -------
    features : list of dicts (one per valid feature)
    labeled  : 2D int array (0 = background, N = feature N)
    """
    ny, nx = z_nm.shape
    raw_labeled, n_raw = ndimage.label(mask)
    features = []

    for i in range(1, n_raw + 1):
        region   = raw_labeled == i
        area_px  = int(np.sum(region))

        if area_px < MIN_AREA_PX:
            raw_labeled[region] = 0   # discard tiny blobs
            continue

        z_region     = z_nm[region]
        area_nm2     = area_px * pixel_nm ** 2
        equiv_diam   = 2.0 * np.sqrt(area_nm2 / np.pi)

        if feature_type == 'hole' and MIN_EQUIV_DIAMETER_NM > 0 and equiv_diam < MIN_EQUIV_DIAMETER_NM:
            raw_labeled[region] = 0
            continue

        rows, cols   = np.where(region)
        if REJECT_FEATURES_TOUCHING_IMAGE_BORDER:
            if (np.any(rows == 0) or np.any(rows == ny - 1)
                    or np.any(cols == 0) or np.any(cols == nx - 1)):
                raw_labeled[region] = 0
                continue
        cx_nm        = float(np.mean(cols)) * pixel_nm
        cy_nm        = float(np.mean(rows)) * pixel_nm

        if feature_type == 'hole':
            amplitude, rim_z, peak_z, depth_ref = _hole_depth_from_rim(
                z_nm, region, pixel_nm, background_mean)
            if amplitude < MIN_DEPTH_NM:
                raw_labeled[region] = 0
                continue
        else:
            peak_z    = float(np.nanmax(z_region))
            amplitude = abs(peak_z - background_mean)
            if amplitude < MIN_HEIGHT_NM:
                raw_labeled[region] = 0
                continue

        feat = {
            'feature_id':        i,
            'area_px':           area_px,
            'area_nm2':          round(area_nm2,   2),
            'equiv_diameter_nm': round(equiv_diam,  2),
            'centroid_x_nm':     round(cx_nm,       2),
            'centroid_y_nm':     round(cy_nm,       2),
            'peak_z_nm':         round(peak_z,      4),
        }
        if feature_type == 'hole':
            feat['depth_nm'] = round(amplitude, 4)
            feat['depth_reference'] = depth_ref
            if depth_ref == 'annulus':
                feat['hole_rim_z_nm'] = round(rim_z, 4)
        else:
            feat['height_nm'] = round(amplitude, 4)

        features.append(feat)

    # Re-label after dropping tiny features
    final_labeled, _ = ndimage.label(raw_labeled > 0)
    return features, final_labeled


# ===========================================================================
# PLOTLY — 2D HEIGHT MAP
# ===========================================================================

def plot_2d_map(z_nm, pixel_nm, out_dir, fname, template, suffix):
    ny, nx  = z_nm.shape
    x_um    = np.arange(nx) * pixel_nm / 1000.0
    y_um    = np.arange(ny) * pixel_nm / 1000.0

    fig = go.Figure(go.Heatmap(
        z=z_nm,
        x=x_um,
        y=y_um,
        colorscale='Viridis',
        colorbar=dict(title=dict(text='Height (nm)', side='right')),
        hovertemplate='X: %{x:.3f} µm<br>Y: %{y:.3f} µm<br>Z: %{z:.3f} nm<extra></extra>',
    ))
    fig.update_layout(
        title=f'<b>{fname}</b> — 2D Height Map',
        xaxis_title='X (µm)', yaxis_title='Y (µm)',
        width=720, height=660,
        template=template,
        font=dict(family='Arial, sans-serif'),
    )
    out_path = os.path.join(out_dir, f'height_map_2d{suffix}.html')
    fig.write_html(out_path, include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_2D_MAP:
        try:
            fig.write_image(out_path.replace('.html', '.png'), scale=2)
        except Exception as e:
            pass
    return out_path


# ===========================================================================
# PLOTLY — FEATURE ANNOTATION MAP
# ===========================================================================

def plot_feature_map(z_nm, pixel_nm, hole_labeled, prot_labeled,
                     features_holes, features_prots, out_dir, fname, template, suffix):
    ny, nx = z_nm.shape
    x_um   = np.arange(nx) * pixel_nm / 1000.0
    y_um   = np.arange(ny) * pixel_nm / 1000.0

    fig = go.Figure()

    # Base greyscale height map
    fig.add_trace(go.Heatmap(
        z=z_nm, x=x_um, y=y_um,
        colorscale='Greys',
        showscale=False,
        hovertemplate='X: %{x:.3f} µm<br>Y: %{y:.3f} µm<br>Z: %{z:.3f} nm<extra></extra>',
        name='Height',
    ))

    # Hole overlay (blue, NaN = transparent)
    if np.any(hole_labeled > 0):
        overlay_h = np.where(hole_labeled > 0, 1.0, np.nan)
        fig.add_trace(go.Heatmap(
            z=overlay_h, x=x_um, y=y_um,
            colorscale=[[0, 'rgba(76,155,232,0.55)'], [1, 'rgba(76,155,232,0.55)']],
            showscale=False, name='Holes',
        ))

    # Protrusion overlay (orange, NaN = transparent)
    if np.any(prot_labeled > 0):
        overlay_p = np.where(prot_labeled > 0, 1.0, np.nan)
        fig.add_trace(go.Heatmap(
            z=overlay_p, x=x_um, y=y_um,
            colorscale=[[0, 'rgba(232,124,76,0.55)'], [1, 'rgba(232,124,76,0.55)']],
            showscale=False, name='Protrusions',
        ))

    # Hole centroids
    if features_holes:
        cx = [f['centroid_x_nm'] / 1000 for f in features_holes]
        cy = [f['centroid_y_nm'] / 1000 for f in features_holes]
        htxt = [
            f"Hole {f['feature_id']}<br>Depth: {f.get('depth_nm', 0):.2f} nm"
            f"<br>⌀: {f['equiv_diameter_nm']:.1f} nm<br>Area: {f['area_nm2']:.0f} nm²"
            for f in features_holes
        ]
        fig.add_trace(go.Scatter(
            x=cx, y=cy, mode='markers',
            marker=dict(symbol='x-thin', size=10, color=COL_HOLE,
                        line=dict(width=2.5, color=COL_HOLE)),
            hovertext=htxt, hoverinfo='text',
            name=f'Holes ({len(features_holes)})',
        ))

    # Protrusion centroids
    if features_prots:
        cx = [f['centroid_x_nm'] / 1000 for f in features_prots]
        cy = [f['centroid_y_nm'] / 1000 for f in features_prots]
        htxt = [
            f"Protrusion {f['feature_id']}<br>Height: {f.get('height_nm', 0):.2f} nm"
            f"<br>⌀: {f['equiv_diameter_nm']:.1f} nm<br>Area: {f['area_nm2']:.0f} nm²"
            for f in features_prots
        ]
        fig.add_trace(go.Scatter(
            x=cx, y=cy, mode='markers',
            marker=dict(symbol='diamond', size=9, color=COL_PROT,
                        line=dict(width=1.5, color='white')),
            hovertext=htxt, hoverinfo='text',
            name=f'Protrusions ({len(features_prots)})',
        ))

    fig.update_layout(
        title=f'<b>{fname}</b> — Feature Map',
        xaxis_title='X (µm)', yaxis_title='Y (µm)',
        width=760, height=700,
        template=template,
        legend=dict(x=0.01, y=0.99, bgcolor='rgba(0,0,0,0.4)'),
        font=dict(family='Arial, sans-serif'),
    )
    out_path = os.path.join(out_dir, f'feature_map{suffix}.html')
    fig.write_html(out_path, include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_FEATURE_MAP:
        try:
            fig.write_image(out_path.replace('.html', '.png'), scale=2)
        except Exception as e:
            pass
    return out_path


# ===========================================================================
# PLOTLY — 3D SURFACE
# ===========================================================================

def plot_3d_surface(z_nm, pixel_nm, out_dir, fname, template, suffix):
    ny, nx = z_nm.shape

    # Downsample for performance
    if DOWNSAMPLE_3D > 0:
        step = max(1, max(ny, nx) // DOWNSAMPLE_3D)
    else:
        step = 1

    z_ds   = z_nm[::step, ::step]
    ny_ds, nx_ds = z_ds.shape
    x_um   = np.arange(nx_ds) * pixel_nm * step / 1000.0
    y_um   = np.arange(ny_ds) * pixel_nm * step / 1000.0

    fig = go.Figure(data=[go.Surface(
        z=z_ds, x=x_um, y=y_um,
        colorscale='Viridis',
        colorbar=dict(title=dict(text='Height (nm)', side='right')),
        lighting=dict(ambient=0.6, diffuse=0.8, specular=0.2, roughness=0.6),
        lightposition=dict(x=100, y=200, z=10000),
        hovertemplate='X: %{x:.3f} µm<br>Y: %{y:.3f} µm<br>Z: %{z:.3f} nm<extra></extra>',
    )])

    scan_x = nx * pixel_nm / 1000.0
    scan_y = ny * pixel_nm / 1000.0
    z_range = float(np.nanmax(z_nm) - np.nanmin(z_nm))

    fig.update_layout(
        title=f'<b>{fname}</b> — 3D Surface',
        scene=dict(
            xaxis_title='X (µm)',
            yaxis_title='Y (µm)',
            zaxis_title='Height (nm)',
            camera=dict(eye=dict(x=1.4, y=1.4, z=0.9)),
            aspectmode='manual',
            aspectratio=dict(x=scan_x, y=scan_y,
                             z=max(0.1, min(0.5, z_range / (scan_x * 1000)))),
        ),
        width=920, height=720,
        template=template,
        font=dict(family='Arial, sans-serif'),
    )
    out_path = os.path.join(out_dir, f'height_map_3d{suffix}.html')
    fig.write_html(out_path, include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_3D_SURFACE:
        try:
            fig.write_image(out_path.replace('.html', '.png'), scale=2)
        except Exception as e:
            pass
    return out_path


# ===========================================================================
# PLOTLY — HISTOGRAMS
# ===========================================================================

def plot_histograms(features_holes, features_prots, stats, out_dir, fname, template, suffix):
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            'Hole Equivalent Diameter', 'Hole Depth',
            'Protrusion Equivalent Diameter', 'Protrusion Height',
        ],
    )

    def _add_hist(row, col, data, color, xlabel):
        if not data:
            return
        fig.add_trace(go.Histogram(
            x=data, marker_color=color, opacity=0.80,
            nbinsx=max(5, len(data) // 2),
            hovertemplate=f'{xlabel}: %{{x:.1f}}<br>Count: %{{y}}<extra></extra>',
        ), row=row, col=col)
        fig.update_xaxes(title_text=xlabel, row=row, col=col)
        fig.update_yaxes(title_text='Count',  row=row, col=col)

    h_diams  = [f['equiv_diameter_nm'] for f in features_holes]
    h_depths = [f.get('depth_nm', 0)   for f in features_holes]
    p_diams  = [f['equiv_diameter_nm'] for f in features_prots]
    p_heights= [f.get('height_nm', 0)  for f in features_prots]

    _add_hist(1, 1, h_diams,   COL_HOLE, 'Diameter (nm)')
    _add_hist(1, 2, h_depths,  COL_HOLE, 'Depth (nm)')
    _add_hist(2, 1, p_diams,   COL_PROT, 'Diameter (nm)')
    _add_hist(2, 2, p_heights, COL_PROT, 'Height (nm)')

    fig.update_layout(
        title=f'<b>{fname}</b> — Feature Size Distributions',
        showlegend=False,
        width=900, height=700,
        template=template,
        font=dict(family='Arial, sans-serif'),
    )
    out_path = os.path.join(out_dir, f'histograms{suffix}.html')
    fig.write_html(out_path, include_plotlyjs='cdn')
    if SAVE_PNGS and SAVE_PNG_HISTOGRAMS:
        try:
            fig.write_image(out_path.replace('.html', '.png'), scale=2)
        except Exception as e:
            pass
    return out_path


# ===========================================================================
# PER-FILE PROCESSING
# ===========================================================================

def _safe_mean(lst): return float(np.mean(lst)) if lst else float('nan')
def _safe_std(lst):  return float(np.std(lst))  if lst else float('nan')


def _safe_slug(text: str) -> str:
    txt = (text or '').strip().lower()
    txt = re.sub(r'[^a-z0-9]+', '_', txt)
    txt = re.sub(r'_+', '_', txt).strip('_')
    return txt or 'unnamed'


def _split_sample_replicate(name: str):
    """Split names like '12_Hour_Tg_0001' into ('12_hour_tg', '0001')."""
    stem = os.path.splitext(name)[0].strip()
    m = re.match(r'^(.*?)[\s\-_]+(\d+)$', stem)
    if not m:
        return _safe_slug(stem), 'single'
    sample_raw = m.group(1).strip()
    rep_raw = m.group(2).strip()
    return _safe_slug(sample_raw), rep_raw


def _build_sample_output_dir(output_root: str, raw_name: str) -> str:
    sample_name, rep_id = _split_sample_replicate(raw_name)
    return os.path.join(output_root, sample_name, rep_id)


def _write_combined_html(folder: str, filename: str, html_files):
    html_path = os.path.join(folder, filename)
    title = os.path.splitext(filename)[0].replace('_', ' ').title()
    blocks = []
    for rel_name in html_files:
        blocks.append(
            f"<section><h2>{rel_name}</h2>"
            f"<iframe src=\"{rel_name}\" loading=\"lazy\"></iframe></section>"
        )
    doc = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{title}</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;margin:18px;} "
        "h1{margin-bottom:22px;} h2{font-size:16px;margin:20px 0 10px;} "
        "iframe{width:100%;height:740px;border:1px solid #bbb;border-radius:6px;} "
        "section{margin-bottom:28px;}"
        "</style></head><body>"
        f"<h1>{title}</h1>{''.join(blocks)}</body></html>"
    )
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(doc)


def generate_combined_dashboards(root_dir: str):
    """Create light/dark merged HTMLs for each folder containing direct HTML files."""
    for current_root, _, files in os.walk(root_dir):
        local_html = sorted([
            f for f in files
            if f.lower().endswith('.html')
            and f not in ('all_plots_dark.html', 'all_plots_light.html')
        ])
        if not local_html:
            continue
        dark = [f for f in local_html if not f.lower().endswith('_light.html')]
        light = [f for f in local_html if f.lower().endswith('_light.html')]
        if dark:
            _write_combined_html(current_root, 'all_plots_dark.html', dark)
        if light:
            _write_combined_html(current_root, 'all_plots_light.html', light)


def restructure_legacy_run(run_dir: str):
    """
    Move flat sample folders into grouped sample/replicate folders.
    Keeps `comparison` and top-level files intact.
    """
    if not os.path.isdir(run_dir):
        return
    for item in sorted(os.listdir(run_dir)):
        src = os.path.join(run_dir, item)
        if not os.path.isdir(src):
            continue
        if item in ('comparison', 'origin data'):
            continue
        m = re.match(r'^(.*?)[\s\-_]+(\d+)$', item.strip())
        if not m:
            # Skip already-grouped folders such as "12_hour_tg" or utility folders.
            continue
        sample_name = _safe_slug(m.group(1).strip())
        rep_id = m.group(2).strip()
        dst_parent = os.path.join(run_dir, sample_name)
        dst = os.path.join(dst_parent, rep_id)
        if os.path.normcase(src) == os.path.normcase(dst):
            continue
        os.makedirs(dst_parent, exist_ok=True)
        if os.path.exists(dst):
            n = 1
            while os.path.exists(f'{dst}_{n}'):
                n += 1
            dst = f'{dst}_{n}'
        shutil.move(src, dst)


def _safe_mean_series(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return float('nan')
    s = pd.to_numeric(df[col], errors='coerce').dropna()
    return float(s.mean()) if not s.empty else float('nan')


def _safe_sum_series(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return float('nan')
    s = pd.to_numeric(df[col], errors='coerce').dropna()
    return float(s.sum()) if not s.empty else float('nan')


def _safe_feature_stats(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return float('nan'), float('nan')
    s = pd.to_numeric(df[col], errors='coerce').dropna()
    if s.empty:
        return float('nan'), float('nan')
    return float(s.mean()), float(s.std(ddof=0))


def _aggregate_replicates(summary_df: pd.DataFrame,
                          all_holes_df: pd.DataFrame,
                          all_prots_df: pd.DataFrame):
    agg_rows = []
    agg_holes_rows = []
    agg_prots_rows = []

    for base_name, grp in summary_df.groupby('base_sample_name', dropna=False):
        if not isinstance(base_name, str) or not base_name.strip():
            base_name = 'unknown_sample'
        base_name = base_name.strip()

        g_holes = all_holes_df[all_holes_df['base_sample_name'] == base_name].copy() if not all_holes_df.empty else pd.DataFrame()
        g_prots = all_prots_df[all_prots_df['base_sample_name'] == base_name].copy() if not all_prots_df.empty else pd.DataFrame()

        total_area = _safe_sum_series(grp, 'scan_area_um2')
        n_holes = int(_safe_sum_series(grp, 'n_holes') or 0)
        n_prots = int(_safe_sum_series(grp, 'n_protrusions') or 0)
        hole_density = (n_holes / total_area) if total_area and not np.isnan(total_area) else float('nan')
        prot_density = (n_prots / total_area) if total_area and not np.isnan(total_area) else float('nan')

        avg_hole_depth, std_hole_depth = _safe_feature_stats(g_holes, 'depth_nm')
        avg_hole_diam, std_hole_diam = _safe_feature_stats(g_holes, 'equiv_diameter_nm')
        avg_prot_height, std_prot_height = _safe_feature_stats(g_prots, 'height_nm')
        avg_prot_diam, std_prot_diam = _safe_feature_stats(g_prots, 'equiv_diameter_nm')

        agg_rows.append({
            'filename': base_name,
            'base_sample_name': base_name,
            'scan_x_um': _safe_mean_series(grp, 'scan_x_um'),
            'scan_y_um': _safe_mean_series(grp, 'scan_y_um'),
            'scan_area_um2': round(total_area, 4) if not np.isnan(total_area) else float('nan'),
            'pixel_nm': _safe_mean_series(grp, 'pixel_nm'),
            'sharpness_score': _safe_mean_series(grp, 'sharpness_score'),
            'line_correlation': _safe_mean_series(grp, 'line_correlation'),
            'Ra_nm': _safe_mean_series(grp, 'Ra_nm'),
            'Rq_nm': _safe_mean_series(grp, 'Rq_nm'),
            'Rz_nm': _safe_mean_series(grp, 'Rz_nm'),
            'Rpv_nm': _safe_mean_series(grp, 'Rpv_nm'),
            'Rsk': _safe_mean_series(grp, 'Rsk'),
            'Rku': _safe_mean_series(grp, 'Rku'),
            'z_min_nm': _safe_mean_series(grp, 'z_min_nm'),
            'z_max_nm': _safe_mean_series(grp, 'z_max_nm'),
            'z_mean_nm': _safe_mean_series(grp, 'z_mean_nm'),
            'z_p01_nm': _safe_mean_series(grp, 'z_p01_nm'),
            'z_p50_nm': _safe_mean_series(grp, 'z_p50_nm'),
            'z_p99_nm': _safe_mean_series(grp, 'z_p99_nm'),
            'hole_thresh_nm': _safe_mean_series(grp, 'hole_thresh_nm'),
            'prot_thresh_nm': _safe_mean_series(grp, 'prot_thresh_nm'),
            'pct_surface_holes': _safe_mean_series(grp, 'pct_surface_holes'),
            'pct_surface_prots': _safe_mean_series(grp, 'pct_surface_prots'),
            'pct_surface_total': _safe_mean_series(grp, 'pct_surface_total'),
            'n_holes': n_holes,
            'holes_per_um2': round(hole_density, 4) if not np.isnan(hole_density) else float('nan'),
            'avg_hole_depth_nm': round(avg_hole_depth, 3) if not np.isnan(avg_hole_depth) else float('nan'),
            'std_hole_depth_nm': round(std_hole_depth, 3) if not np.isnan(std_hole_depth) else float('nan'),
            'avg_hole_diameter_nm': round(avg_hole_diam, 3) if not np.isnan(avg_hole_diam) else float('nan'),
            'std_hole_diameter_nm': round(std_hole_diam, 3) if not np.isnan(std_hole_diam) else float('nan'),
            'n_protrusions': n_prots,
            'prots_per_um2': round(prot_density, 4) if not np.isnan(prot_density) else float('nan'),
            'n_defects_total': n_holes + n_prots,
            'defects_per_um2': round((n_holes + n_prots) / total_area, 4) if total_area and not np.isnan(total_area) else float('nan'),
            'defects_per_mm2': round((n_holes + n_prots) / total_area * 1e6, 2) if total_area and not np.isnan(total_area) else float('nan'),
            'avg_prot_height_nm': round(avg_prot_height, 3) if not np.isnan(avg_prot_height) else float('nan'),
            'std_prot_height_nm': round(std_prot_height, 3) if not np.isnan(std_prot_height) else float('nan'),
            'avg_prot_diameter_nm': round(avg_prot_diam, 3) if not np.isnan(avg_prot_diam) else float('nan'),
            'std_prot_diameter_nm': round(std_prot_diam, 3) if not np.isnan(std_prot_diam) else float('nan'),
        })
        row = agg_rows[-1]
        for c in FIXED_DEPTH_CUTOFFS_NM:
            col = fixed_depth_pct_column(c)
            row[col] = _safe_mean_series(grp, col)
        row['fixdep_median_ref_nm'] = _safe_mean_series(grp, 'fixdep_median_ref_nm')

        if not g_holes.empty:
            g_holes = g_holes.copy()
            g_holes['filename'] = base_name
            agg_holes_rows.extend(g_holes.to_dict('records'))
        if not g_prots.empty:
            g_prots = g_prots.copy()
            g_prots['filename'] = base_name
            agg_prots_rows.extend(g_prots.to_dict('records'))

    return pd.DataFrame(agg_rows), pd.DataFrame(agg_holes_rows), pd.DataFrame(agg_prots_rows)


def process_file(filepath: str, output_root: str, replicate_regex: re.Pattern):
    fname = os.path.splitext(os.path.basename(filepath))[0]
    base_sample_name = replicate_regex.sub('', fname).strip() or fname
    print(f"\n{'='*60}\nProcessing: {os.path.basename(filepath)}\n{'='*60}")

    # --- Load ---
    z_nm, pixel_nm, scan_x_um, scan_y_um = load_ibw(filepath)
    print(f"  Array   : {z_nm.shape[0]}x{z_nm.shape[1]} px")
    print(f"  Scan    : {scan_x_um:.3f} x {scan_y_um:.3f} µm")
    print(f"  Pixel   : {pixel_nm:.3f} nm")
    print(f"  Z range : {np.nanmin(z_nm):.3f} -> {np.nanmax(z_nm):.3f} nm")

    # --- Detect ---
    hole_mask, prot_mask, stats = detect_features(z_nm, pixel_nm)
    print(f"  Mean    : {stats['mean_nm']:.4f} nm  Std: {stats['std_nm']:.4f} nm")
    print(f"  Hole thr: {stats['hole_thresh_nm']:.4f} nm  |  Prot thr: {stats['prot_thresh_nm']:.4f} nm")

    # --- Measure ---
    features_holes, hole_labeled = measure_features(
        z_nm, hole_mask, pixel_nm, 'hole', stats['mean_nm'])
    features_prots, prot_labeled = measure_features(
        z_nm, prot_mask, pixel_nm, 'protrusion', stats['mean_nm'])

    print(f"  Holes   : {len(features_holes)}")
    print(f"  Prots   : {len(features_prots)}")

    # --- Output directories ---
    file_dir = _build_sample_output_dir(output_root, fname)
    os.makedirs(file_dir, exist_ok=True)

    # --- CSVs ---
    if features_holes:
        pd.DataFrame(features_holes).to_csv(
            os.path.join(file_dir, 'holes.csv'), index=False)
    if features_prots:
        pd.DataFrame(features_prots).to_csv(
            os.path.join(file_dir, 'protrusions.csv'), index=False)

    # --- Roughness & Quality ---
    roughness = compute_roughness(z_nm)
    quality = compute_scan_quality(z_nm, roughness['Rq'])
    roughness.update(quality)

    print(f"  Ra      : {roughness['Ra']:.4f} nm  |  Rq: {roughness['Rq']:.4f} nm")
    print(f"  Rz      : {roughness['Rz']:.4f} nm  |  Rpv: {roughness['Rpv']:.4f} nm")
    print(f"  Rsk     : {roughness['Rsk']:.3f}      |  Rku: {roughness['Rku']:.3f}")
    print(f"  z_min   : {roughness['z_min']:.4f} nm  |  z_max: {roughness['z_max']:.4f} nm")
    print(f"  Quality : Sharpness {quality['sharpness_score']:.3f} | Line Corr {quality['line_correlation']:.3f}")

    if quality['sharpness_score'] < 0.5:
        print(f"  ! WARNING: Low sharpness detected. Scan may be blurry or tip blunted.")
    if quality['line_correlation'] < 0.7:
        print(f"  ! WARNING: Low line correlation. Scan may have severe tracking noise.")

    # --- Plots ---
    if SAVE_PLOTS:
        for template, suffix in TEMPLATES:
            if PLOT_2D_MAP:
                plot_2d_map(z_nm, pixel_nm, file_dir, fname, template, suffix)
            if PLOT_FEATURE_MAP:
                plot_feature_map(z_nm, pixel_nm, hole_labeled, prot_labeled,
                                 features_holes, features_prots, file_dir, fname, template, suffix)
            if PLOT_3D_SURFACE:
                plot_3d_surface(z_nm, pixel_nm, file_dir, fname, template, suffix)
            if PLOT_HISTOGRAMS and (features_holes or features_prots):
                plot_histograms(features_holes, features_prots, stats, file_dir, fname, template, suffix)
            if PLOT_ROUGHNESS:
                plot_roughness_analysis(z_nm, roughness, stats, pixel_nm, file_dir, fname, template, suffix)
        print(f"  Plots -> {file_dir}")

    # --- Summary row ---
    h_depths  = [f.get('depth_nm', 0)   for f in features_holes]
    h_diams   = [f['equiv_diameter_nm'] for f in features_holes]
    p_heights = [f.get('height_nm', 0)  for f in features_prots]
    p_diams   = [f['equiv_diameter_nm'] for f in features_prots]

    scan_area_um2 = scan_x_um * scan_y_um
    
    # Calculate surface percentages
    hole_area_um2 = sum(f['area_nm2'] for f in features_holes) / 1e6
    prot_area_um2 = sum(f['area_nm2'] for f in features_prots) / 1e6
    pct_holes = (hole_area_um2 / scan_area_um2) * 100 if scan_area_um2 > 0 else 0
    pct_prots = (prot_area_um2 / scan_area_um2) * 100 if scan_area_um2 > 0 else 0
    pct_total = pct_holes + pct_prots

    summary = {
        'filename':               os.path.basename(filepath),
        'ibw_path':               os.path.abspath(filepath),
        'base_sample_name':       base_sample_name,
        'scan_x_um':              round(scan_x_um, 4),
        'scan_y_um':              round(scan_y_um, 4),
        'scan_area_um2':          round(scan_area_um2, 4),
        'pixel_nm':               round(pixel_nm, 4),
        # --- quality ---
        'sharpness_score':        roughness['sharpness_score'],
        'line_correlation':       roughness['line_correlation'],
        # --- roughness ---
        'Ra_nm':                  roughness['Ra'],
        'Rq_nm':                  roughness['Rq'],
        'Rz_nm':                  roughness['Rz'],
        'Rpv_nm':                 roughness['Rpv'],
        'Rsk':                    roughness['Rsk'],
        'Rku':                    roughness['Rku'],
        'z_min_nm':               roughness['z_min'],
        'z_max_nm':               roughness['z_max'],
        'z_mean_nm':              roughness['z_mean'],
        'z_p01_nm':               roughness['z_p01'],
        'z_p50_nm':               roughness['z_p50'],
        'z_p99_nm':               roughness['z_p99'],
        # --- detection thresholds ---
        'hole_thresh_nm':         round(stats['hole_thresh_nm'], 4),
        'prot_thresh_nm':         round(stats['prot_thresh_nm'], 4),
        'robust_median_nm':       stats.get('robust_median_nm', float('nan')),
        'robust_mad_nm':          stats.get('robust_mad_nm', float('nan')),
        'robust_sigma_nm':        stats.get('robust_sigma_nm', float('nan')),
        'threshold_uses_robust':    stats.get('threshold_uses_robust', False),
        # --- features percentages ---
        'pct_surface_holes':      round(pct_holes, 4),
        'pct_surface_prots':      round(pct_prots, 4),
        'pct_surface_total':      round(pct_total, 4),
        # --- features ---
        'n_holes':                len(features_holes),
        'holes_per_um2':          round(len(features_holes) / scan_area_um2, 4),
        'avg_hole_depth_nm':      round(_safe_mean(h_depths), 3),
        'std_hole_depth_nm':      round(_safe_std(h_depths),  3),
        'avg_hole_diameter_nm':   round(_safe_mean(h_diams),  3),
        'std_hole_diameter_nm':   round(_safe_std(h_diams),   3),
        'n_protrusions':          len(features_prots),
        'prots_per_um2':          round(len(features_prots) / scan_area_um2, 4),
        'n_defects_total':        len(features_holes) + len(features_prots),
        'defects_per_um2':        round((len(features_holes) + len(features_prots)) / scan_area_um2, 4),
        'defects_per_mm2':        round((len(features_holes) + len(features_prots)) / scan_area_um2 * 1e6, 2),
        'avg_prot_height_nm':     round(_safe_mean(p_heights),3),
        'std_prot_height_nm':     round(_safe_std(p_heights), 3),
        'avg_prot_diameter_nm':   round(_safe_mean(p_diams),  3),
        'std_prot_diameter_nm':   round(_safe_std(p_diams),   3),
    }
    summary.update(compute_fixed_depth_below_median_metrics(z_nm, pixel_nm))

    return summary, features_holes, features_prots


def run_experiment(ibw_files, output_dir: str, replicate_regex: re.Pattern, experiment_name: str,
                   experiment_data_dir=None):
    if not ibw_files:
        print(f"No .ibw files found for experiment '{experiment_name}'")
        return
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n{'#'*72}\nExperiment: {experiment_name}\nFiles: {len(ibw_files)}\nOutput: {output_dir}\n{'#'*72}")

    all_summaries = []
    all_holes_rows = []
    all_prots_rows = []

    for filepath in ibw_files:
        try:
            summary, fh, fp = process_file(filepath, output_dir, replicate_regex)
            all_summaries.append(summary)
            fname = summary['filename']
            base_sample_name = summary.get('base_sample_name', os.path.splitext(fname)[0])
            for f in fh:
                all_holes_rows.append({
                    **f,
                    'filename': fname,
                    'base_sample_name': base_sample_name,
                })
            for f in fp:
                all_prots_rows.append({
                    **f,
                    'filename': fname,
                    'base_sample_name': base_sample_name,
                })
        except Exception as exc:
            print(f"  ERROR: {str(exc).encode('ascii', errors='replace').decode('ascii')}")
            traceback.print_exc()

    summary_df = pd.DataFrame(all_summaries)
    summary_path = os.path.join(output_dir, 'summary.csv')
    summary_df.to_csv(summary_path, index=False)
    print(f"\n{'='*60}\nSummary CSV -> {summary_path}")

    if len(all_summaries) >= 1 and SAVE_PLOTS:
        try:
            from comparison import plot_cross_file_comparison, plot_threshold_review_grid
            all_holes_df = pd.DataFrame(all_holes_rows)
            all_prots_df = pd.DataFrame(all_prots_rows)
            comp_dir = os.path.join(output_dir, 'comparison')
            os.makedirs(comp_dir, exist_ok=True)

            # Wave 1: per-base_sample_name comparisons + threshold QA HTML
            if 'base_sample_name' in summary_df.columns:
                for base_sample_name, grp in summary_df.groupby('base_sample_name', dropna=False):
                    if not isinstance(base_sample_name, str) or not base_sample_name.strip():
                        continue
                    group_holes = all_holes_df[all_holes_df['base_sample_name'] == base_sample_name].copy() if not all_holes_df.empty else pd.DataFrame()
                    group_prots = all_prots_df[all_prots_df['base_sample_name'] == base_sample_name].copy() if not all_prots_df.empty else pd.DataFrame()
                    grp_sorted = grp.sort_values('filename')
                    if len(grp_sorted) >= 2:
                        rep_comp_dir = os.path.join(comp_dir, f'{base_sample_name}_replicates')
                        os.makedirs(rep_comp_dir, exist_ok=True)
                        plot_cross_file_comparison(grp_sorted.copy(), group_holes, group_prots, rep_comp_dir, save_html=False)
                        plot_threshold_review_grid(grp_sorted.copy(), rep_comp_dir, stem='threshold_review_grid')
                    else:
                        plot_threshold_review_grid(
                            grp_sorted.copy(), comp_dir,
                            stem=f'threshold_review_{_safe_slug(base_sample_name)}',
                        )

            # Wave 2: global averaged comparisons.
            averaged_summary_df = pd.DataFrame()
            averaged_holes_df = pd.DataFrame()
            averaged_prots_df = pd.DataFrame()
            if 'base_sample_name' in summary_df.columns:
                averaged_summary_df, averaged_holes_df, averaged_prots_df = _aggregate_replicates(
                    summary_df, all_holes_df, all_prots_df
                )
            if not averaged_summary_df.empty:
                avg_comp_dir = os.path.join(comp_dir, 'Global_Averaged')
                os.makedirs(avg_comp_dir, exist_ok=True)
                averaged_summary_df.to_csv(os.path.join(avg_comp_dir, 'summary_averaged.csv'), index=False)
                plot_cross_file_comparison(
                    averaged_summary_df,
                    averaged_holes_df,
                    averaged_prots_df,
                    avg_comp_dir,
                )

            try:
                import substrate_comparison
                analysis_df = averaged_summary_df if not averaged_summary_df.empty else summary_df
                substrate_comparison.run_substrate_analysis(
                    summary_df=analysis_df,
                    output_dir=comp_dir,
                    experiment_name=experiment_name,
                    experiment_data_dir=experiment_data_dir,
                )
            except Exception as exc:
                print(f"Substrate comparison ERROR: {exc}")
                traceback.print_exc()

            plot_cross_file_comparison(
                summary_df,
                all_holes_df,
                all_prots_df,
                comp_dir,
            )
            print(f"Comparison plots -> {comp_dir}")
        except Exception as exc:
            print(f"Comparison plots ERROR: {exc}")
            traceback.print_exc()

    generate_combined_dashboards(output_dir)
    print(f"Merged dashboards generated under -> {output_dir}")


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'Data')
    output_base_dir = os.path.join(script_dir, 'Output')
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join(output_base_dir, f'Run_{run_id}')
    os.makedirs(output_base_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    replicate_regex = re.compile(REPLICATE_STRIP_PATTERN)

    if not os.path.isdir(data_dir):
        print(f"Data directory not found: {data_dir}")
        return

    legacy_dir = os.path.join(output_base_dir, LEGACY_RUN_TO_RESTRUCTURE)
    restructure_legacy_run(legacy_dir)

    experiment_specs = []
    for entry in sorted(os.listdir(data_dir)):
        exp_path = os.path.join(data_dir, entry)
        if not os.path.isdir(exp_path):
            continue
        exp_files = sorted(glob.glob(os.path.join(exp_path, '*.ibw')))
        if exp_files:
            experiment_specs.append((entry, exp_files))

    root_files = sorted(glob.glob(os.path.join(data_dir, '*.ibw')))
    if root_files:
        experiment_specs.append(('unnamed', root_files))

    if not experiment_specs:
        print(f"No .ibw files found in {data_dir} or its top-level experiment folders")
        return

    for exp_name, exp_files in experiment_specs:
        exp_out = os.path.join(output_dir, _safe_slug(exp_name))
        exp_data_dir = data_dir if exp_name == 'unnamed' else os.path.join(data_dir, exp_name)
        run_experiment(exp_files, exp_out, replicate_regex, exp_name, experiment_data_dir=exp_data_dir)

    print('=' * 60)


if __name__ == '__main__':
    main()
