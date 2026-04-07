# -*- coding: utf-8 -*-
"""
Batch AFM/SPM preprocessing for \"presentable\" images using Gwyddion's pygwy API.

Pipeline (default):
  1. align_rows  — scan-line correction (linematch)
  2. level       — plane / polynomial leveling
  3. fix_zero    — optional minimum-to-zero (use --no-fix-zero to skip)
  4. flatten_base — optional (--flatten-base)

Prerequisites
-------------
The C extension module ``gwy`` must be importable. Official pygwy docs target
Python 2.7; use the Python interpreter bundled with your Gwyddion install on
Windows, or run from Data Process → Pygwy Console after fixing sys.path.

References
----------
https://gwyddion.net/documentation/user-guide-en/pygwy.html
https://gwyddion.net/documentation/head/pygwy/

Examples
--------
  python afm_presentable_batch.py C:\\data\\afm_raw
  python afm_presentable_batch.py C:\\data\\afm_raw -o C:\\data\\afm_clean --flatten-base
  python afm_presentable_batch.py . --pattern \"*.nid\" --all-channels -v
"""

from __future__ import print_function

import argparse
import glob
import os
import sys
import traceback

DEFAULT_EXTENSIONS = (".gwy", ".nid", ".spm", ".afm", ".dat")


def _parse_extensions(s):
    if not s:
        return list(DEFAULT_EXTENSIONS)
    parts = [p.strip().lower() for p in s.split(",")]
    out = []
    for p in parts:
        if not p:
            continue
        if not p.startswith("."):
            p = "." + p
        out.append(p)
    return out if out else list(DEFAULT_EXTENSIONS)


def _apply_default_settings(gwy, settings):
    """Deterministic linematch + level defaults (override GUI last-used values)."""
    # align_rows / linematch (see Gwyddion pygwy batch example)
    settings["/module/linematch/direction"] = int(gwy.ORIENTATION_HORIZONTAL)
    settings["/module/linematch/do_extract"] = False
    settings["/module/linematch/do_plot"] = False
    settings["/module/linematch/method"] = 2
    # plane level: exclude masked regions if any (same as user-guide example)
    settings["/module/level/mode"] = int(gwy.MASKING_EXCLUDE)


def _choose_input_dir_with_popup():
    """Open a simple folder picker popup and return selected path or None."""
    try:
        # Python 3
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        try:
            # Python 2 fallback (common for pygwy environments)
            tk = __import__("Tkinter")
            filedialog = __import__("tkFileDialog")
        except ImportError:
            return None

    root = tk.Tk()
    root.withdraw()
    root.update()
    path = filedialog.askdirectory(title="Select AFM data folder")
    root.destroy()
    if not path:
        return None
    return os.path.abspath(path)


def _discover_files(input_dir, pattern, extensions, recursive):
    input_dir = os.path.abspath(input_dir)
    files = []
    if pattern:
        if recursive:
            for root, _dirs, names in os.walk(input_dir):
                for name in names:
                    full = os.path.join(root, name)
                    if os.path.isfile(full):
                        if not os.path.fnmatch.fnmatch(name, pattern):
                            continue
                        ext = os.path.splitext(name)[1].lower()
                        if ext in extensions:
                            files.append(full)
        else:
            glob_pat = os.path.join(input_dir, pattern)
            for full in sorted(glob.glob(glob_pat)):
                if os.path.isfile(full):
                    ext = os.path.splitext(full)[1].lower()
                    if ext in extensions:
                        files.append(full)
    else:
        if recursive:
            for root, _dirs, names in os.walk(input_dir):
                for name in names:
                    full = os.path.join(root, name)
                    if os.path.isfile(full):
                        ext = os.path.splitext(name)[1].lower()
                        if ext in extensions:
                            files.append(full)
        else:
            for name in sorted(os.listdir(input_dir)):
                full = os.path.join(input_dir, name)
                if not os.path.isfile(full):
                    continue
                ext = os.path.splitext(name)[1].lower()
                if ext in extensions:
                    files.append(full)
    files.sort()
    return files


def _resolve_channel_ids(gwy, container, height_only, verbose):
    if height_only:
        ids = gwy.gwy_app_data_browser_find_data_by_title(container, "Height*")
        if not ids:
            ids = list(gwy.gwy_app_data_browser_get_data_ids(container))
            if verbose:
                print(
                    "  Warning: no channel title matching Height*; processing all %d channel(s)."
                    % len(ids),
                    file=sys.stderr,
                )
        return ids
    return list(gwy.gwy_app_data_browser_get_data_ids(container))


def _datafield_to_matrix(data_field):
    """Convert gwy data field to 2D Python list [y][x]."""
    xres = int(data_field.get_xres())
    yres = int(data_field.get_yres())
    flat = list(data_field.get_data())
    if len(flat) != xres * yres:
        return None
    return [flat[y * xres : (y + 1) * xres] for y in range(yres)]


def _save_change_preview_image(path_png, raw_mat, proc_mat, title):
    """Save side-by-side raw/processed/difference PNG."""
    try:
        import numpy as np
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False

    raw = np.asarray(raw_mat, dtype=float)
    proc = np.asarray(proc_mat, dtype=float)
    diff = proc - raw

    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    fig.suptitle(title)

    im0 = axes[0].imshow(raw, cmap="viridis")
    axes[0].set_title("Raw")
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    fig.colorbar(im0, ax=axes[0], shrink=0.7)

    im1 = axes[1].imshow(proc, cmap="viridis")
    axes[1].set_title("Processed")
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    fig.colorbar(im1, ax=axes[1], shrink=0.7)

    im2 = axes[2].imshow(diff, cmap="coolwarm")
    axes[2].set_title("Change (Processed - Raw)")
    axes[2].set_xticks([])
    axes[2].set_yticks([])
    fig.colorbar(im2, ax=axes[2], shrink=0.7)

    out_dir = os.path.dirname(path_png)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    fig.savefig(path_png, dpi=150)
    plt.close(fig)
    return True


def _process_one_file(
    gwy,
    path,
    out_path,
    height_only,
    do_fix_zero,
    do_flatten_base,
    save_change_images,
    image_path_base,
    verbose,
):
    container = gwy.gwy_file_load(path, gwy.RUN_NONINTERACTIVE)
    raw_container = None
    if save_change_images:
        raw_container = gwy.gwy_file_load(path, gwy.RUN_NONINTERACTIVE)
    gwy.gwy_app_data_browser_add(container)
    if raw_container is not None:
        gwy.gwy_app_data_browser_add(raw_container)
    try:
        ids = _resolve_channel_ids(gwy, container, height_only, verbose)
        raw_ids = []
        if raw_container is not None:
            raw_ids = _resolve_channel_ids(gwy, raw_container, height_only, verbose)
        if not ids:
            if verbose:
                print("  Skip: no data fields in file.", file=sys.stderr)
            return False

        for i in ids:
            gwy.gwy_app_data_browser_select_data_field(container, i)
            gwy.gwy_process_func_run("align_rows", container, gwy.RUN_IMMEDIATE)
            gwy.gwy_process_func_run("level", container, gwy.RUN_IMMEDIATE)
            if do_flatten_base:
                gwy.gwy_process_func_run("flatten_base", container, gwy.RUN_IMMEDIATE)
            if do_fix_zero:
                gwy.gwy_process_func_run("fix_zero", container, gwy.RUN_IMMEDIATE)
            key = gwy.gwy_app_get_data_key_for_id(i)
            data_field = container[key]
            data_field.data_changed()

        if save_change_images and raw_container is not None:
            raw_by_idx = {}
            for rid in raw_ids:
                rkey = gwy.gwy_app_get_data_key_for_id(rid)
                raw_by_idx[rid] = raw_container[rkey]
            for i in ids:
                key = gwy.gwy_app_get_data_key_for_id(i)
                proc_field = container[key]
                raw_field = raw_by_idx.get(i)
                if raw_field is None:
                    continue
                raw_mat = _datafield_to_matrix(raw_field)
                proc_mat = _datafield_to_matrix(proc_field)
                if raw_mat is None or proc_mat is None:
                    continue

                suffix = "_ch%s" % i
                png_path = image_path_base + suffix + ".png"
                _save_change_preview_image(
                    png_path,
                    raw_mat,
                    proc_mat,
                    os.path.basename(path) + " " + suffix,
                )

        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        gwy.gwy_file_save(container, out_path, gwy.RUN_NONINTERACTIVE)
        return True
    finally:
        gwy.gwy_app_data_browser_remove(container)
        if raw_container is not None:
            gwy.gwy_app_data_browser_remove(raw_container)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Batch AFM preprocessing via Gwyddion pygwy (align_rows, level, ...)."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=None,
        help="Directory containing SPM files (non-recursive unless --recursive). If omitted, a folder picker opens.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="Output directory (default: <input_dir>/presentable_out).",
    )
    parser.add_argument(
        "--pattern",
        default=None,
        help='Optional glob pattern relative to input dir, e.g. "*.nid" or "sample_*.gwy".',
    )
    parser.add_argument(
        "--extensions",
        default=None,
        help="Comma-separated extensions to include, e.g. .nid,.gwy (default: built-in list).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recurse into subdirectories when collecting files.",
    )
    parser.add_argument(
        "--all-channels",
        action="store_true",
        help="Process every data field; default is Height* titles only (with fallback).",
    )
    parser.add_argument(
        "--no-fix-zero",
        action="store_true",
        help="Do not run fix_zero after leveling.",
    )
    parser.add_argument(
        "--flatten-base",
        action="store_true",
        help="Run flatten_base after level (polynomial background).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Force a simple folder picker popup for input directory selection.",
    )
    parser.add_argument(
        "--save-change-images",
        action="store_true",
        help="Save before/after/difference preview PNG images for processed channels.",
    )
    args = parser.parse_args(argv)

    selected_input = args.input_dir
    if args.gui or not selected_input:
        selected_input = _choose_input_dir_with_popup()
        if not selected_input:
            sys.stderr.write("No input folder selected.\n")
            return 1

    input_dir = os.path.abspath(selected_input)
    if not os.path.isdir(input_dir):
        sys.stderr.write("Error: not a directory: %s\n" % input_dir)
        return 2

    extensions = set(_parse_extensions(args.extensions))
    files = _discover_files(input_dir, args.pattern, extensions, args.recursive)
    if not files:
        sys.stderr.write("No matching files under %s\n" % input_dir)
        return 1

    try:
        import gwy
    except ImportError:
        sys.stderr.write(
            "Error: could not import gwy. Run with Gwyddion's Python (pygwy), not plain python3.\n"
        )
        return 2

    out_root = args.output_dir
    if not out_root:
        out_root = os.path.join(input_dir, "presentable_out")
    out_root = os.path.abspath(out_root)

    settings = gwy.gwy_app_settings_get()
    _apply_default_settings(gwy, settings)

    height_only = not args.all_channels
    do_fix_zero = not args.no_fix_zero
    ok = 0
    fail = 0

    for path in files:
        rel = os.path.relpath(path, input_dir)
        if args.recursive or args.pattern:
            out_path = os.path.join(out_root, rel)
            od = os.path.dirname(out_path)
            if od and not os.path.isdir(od):
                os.makedirs(od)
            image_path_base = os.path.splitext(os.path.join(out_root, rel))[0] + "_changes"
        else:
            out_path = os.path.join(out_root, os.path.basename(path))
            image_path_base = os.path.splitext(out_path)[0] + "_changes"

        if args.verbose:
            print("%s -> %s" % (path, out_path))

        try:
            if _process_one_file(
                gwy,
                path,
                out_path,
                height_only,
                do_fix_zero,
                args.flatten_base,
                args.save_change_images,
                image_path_base,
                args.verbose,
            ):
                ok += 1
            else:
                fail += 1
        except Exception as exc:
            fail += 1
            sys.stderr.write("Error processing %s: %s\n" % (path, exc))
            if args.verbose:
                traceback.print_exc()

    print("Done. %d ok, %d failed, %d files total." % (ok, fail, len(files)))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
