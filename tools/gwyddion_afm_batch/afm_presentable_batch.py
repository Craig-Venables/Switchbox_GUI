# -*- coding: utf-8 -*-
"""
Batch AFM/SPM preprocessing for "presentable" images using Gwyddion's pygwy API.

Pipeline (default):
  1. align_rows  — scan-line correction (linematch)
  2. level       — plane / polynomial leveling
  3. fix_zero    — optional minimum-to-zero (use --no-fix-zero to skip)
  4. flatten_base — optional (--flatten-base)

Modifications for this workflow:
- Processes the AFM file
- Saves a .png image of the processed data
- Saves a .gwy file of the processed data
- Moves the original raw data to a 'raw_data' folder

Prerequisites
-------------
Must be run using Python 2.7 with PyGTK and 32-bit Gwyddion installed on Windows.
"""

from __future__ import print_function

import argparse
import glob
import os
import sys
import traceback
import shutil

DEFAULT_EXTENSIONS = (".gwy", ".nid", ".spm", ".afm", ".dat",".ibw")

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
    settings["/module/linematch/direction"] = int(gwy.ORIENTATION_HORIZONTAL)
    settings["/module/linematch/do_extract"] = False
    settings["/module/linematch/do_plot"] = False
    settings["/module/linematch/method"] = 2
    settings["/module/level/mode"] = int(gwy.MASKING_EXCLUDE)

def _choose_input_dir_with_popup():
    """Open a simple folder picker popup and return selected path or None."""
    try:
        import Tkinter as tk
        import tkFileDialog as filedialog
    except ImportError:
        try:
            import tkinter as tk
            from tkinter import filedialog
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
                # Skip raw_data folder to prevent infinite processing loops
                if os.path.basename(root) == "raw_data":
                    continue
                for name in names:
                    full = os.path.join(root, name)
                    if os.path.isfile(full):
                        if not fnmatch.fnmatch(name, pattern):
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
                if os.path.basename(root) == "raw_data":
                    continue
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

def _save_processed_image(path_png, proc_mat, title):
    """Save processed PNG."""
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib or numpy not installed. Cannot save PNG.", file=sys.stderr)
        return False

    proc = np.asarray(proc_mat, dtype=float)

    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
    ax.set_title(title)

    im = ax.imshow(proc, cmap="viridis")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.7)

    out_dir = os.path.dirname(path_png)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    fig.savefig(path_png, dpi=150)
    plt.close(fig)
    return True

def _process_one_file(
    gwy,
    path,
    input_dir,
    height_only,
    do_fix_zero,
    do_flatten_base,
    verbose,
):
    container = gwy.gwy_file_load(path, gwy.RUN_NONINTERACTIVE)
    gwy.gwy_app_data_browser_add(container)
    
    try:
        ids = _resolve_channel_ids(gwy, container, height_only, verbose)
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
            
            # Save PNG for each channel
            proc_mat = _datafield_to_matrix(data_field)
            if proc_mat is not None:
                filename_no_ext = os.path.splitext(os.path.basename(path))[0]
                suffix = "" if len(ids) == 1 else "_ch%s" % i
                png_path = os.path.join(input_dir, filename_no_ext + suffix + ".png")
                _save_processed_image(
                    png_path,
                    proc_mat,
                    filename_no_ext + suffix,
                )

        # Output .gwy file in the same directory
        filename_no_ext = os.path.splitext(os.path.basename(path))[0]
        out_gwy_path = os.path.join(input_dir, filename_no_ext + "_processed.gwy")
        gwy.gwy_file_save(container, out_gwy_path, gwy.RUN_NONINTERACTIVE)
        
        return True
    finally:
        gwy.gwy_app_data_browser_remove(container)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Batch AFM preprocessing via Gwyddion pygwy. Moves raw data to 'raw_data' folder, saves .gwy and .png."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=None,
        help="Directory containing SPM files. If omitted, a folder picker opens.",
    )
    parser.add_argument(
        "--pattern",
        default=None,
        help='Optional glob pattern relative to input dir, e.g. "*.nid".',
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
        help="Process every data field; default is Height* titles only.",
    )
    parser.add_argument(
        "--no-fix-zero",
        action="store_true",
        help="Do not run fix_zero after leveling.",
    )
    parser.add_argument(
        "--flatten-base",
        action="store_true",
        help="Run flatten_base after level.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args(argv)

    selected_input = args.input_dir
    if not selected_input:
        selected_input = _choose_input_dir_with_popup()
        if not selected_input:
            sys.stderr.write("No input folder selected.\n")
            return 1

    input_dir = os.path.abspath(selected_input)
    if not os.path.isdir(input_dir):
        sys.stderr.write("Error: not a directory: %s\n" % input_dir)
        return 2

    # Create raw_data folder
    raw_dir = os.path.join(input_dir, "raw_data")
    if not os.path.exists(raw_dir):
        os.makedirs(raw_dir)

    extensions = set(_parse_extensions(args.extensions))
    files = _discover_files(input_dir, args.pattern, extensions, args.recursive)
    
    # Filter out files that are already processed .gwy files or inside raw_data
    files = [f for f in files if not f.endswith("_processed.gwy")]
    
    if not files:
        sys.stderr.write("No matching files under %s\n" % input_dir)
        return 1

    try:
        import gwy
    except ImportError:
        sys.stderr.write(
            "Error: could not import gwy. Run with Gwyddion's Python 2.7 (pygwy), not plain python3.\n"
            "Please refer to python27_setup_guide.md for installation instructions.\n"
        )
        return 2

    settings = gwy.gwy_app_settings_get()
    _apply_default_settings(gwy, settings)

    height_only = not args.all_channels
    do_fix_zero = not args.no_fix_zero
    ok = 0
    fail = 0

    for path in files:
        if args.verbose:
            print("Processing: %s" % path)

        try:
            success = _process_one_file(
                gwy,
                path,
                input_dir,
                height_only,
                do_fix_zero,
                args.flatten_base,
                args.verbose,
            )
            if success:
                # Move the raw file to the raw_data folder
                base_name = os.path.basename(path)
                dest_path = os.path.join(raw_dir, base_name)
                # Handle filename collisions in raw_data
                if os.path.exists(dest_path):
                    name, ext = os.path.splitext(base_name)
                    import time
                    dest_path = os.path.join(raw_dir, "%s_%d%s" % (name, int(time.time()), ext))
                shutil.move(path, dest_path)
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
it(main())
