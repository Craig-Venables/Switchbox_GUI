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


def _process_one_file(
    gwy,
    path,
    out_path,
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

        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        gwy.gwy_file_save(container, out_path, gwy.RUN_NONINTERACTIVE)
        return True
    finally:
        gwy.gwy_app_data_browser_remove(container)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Batch AFM preprocessing via Gwyddion pygwy (align_rows, level, ...)."
    )
    parser.add_argument(
        "input_dir",
        help="Directory containing SPM files (non-recursive unless --recursive).",
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
    args = parser.parse_args(argv)

    input_dir = os.path.abspath(args.input_dir)
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
        else:
            out_path = os.path.join(out_root, os.path.basename(path))

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
                args.verbose,
            ):
                ok += 1
            else:
                fail += 1
        except Exception as exc:
            fail += 1
            sys.stderr.write("Error processing %s: %s\n" % (path, exc))

    print("Done. %d ok, %d failed, %d files total." % (ok, fail, len(files)))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
