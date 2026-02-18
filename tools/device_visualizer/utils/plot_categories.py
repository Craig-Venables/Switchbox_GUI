"""
Plot image categories for Gallery and Overlay tabs.

Organises plot images into categories so the IV dashboard appears first,
followed by conduction, SCLC, endurance, retention, forming, and other plots.
"""

import re
from pathlib import Path
from typing import List, Tuple

# Display order: IV dashboard first, then other known types, then "Other".
# Order in list is sort priority (index = rank).
CATEGORY_ORDER = [
    "IV Dashboard",
    "Conduction",
    "SCLC",
    "Endurance",
    "Retention",
    "Forming",
    "Other",
]


def _natural_sort_key(path: Path) -> List:
    """Natural sort key for filenames (1, 2, 10, 11)."""
    def atoi(text):
        return int(text) if text.isdigit() else text.lower()
    return [atoi(c) for c in re.split(r"(\d+)", str(path.name))]


def get_plot_category(path: Path) -> str:
    """
    Classify a plot image path into a display category.

    Uses filename (case-insensitive) to match known plot types from the
    plotting package (e.g. iv_dashboard, conduction, sclc_fit, endurance,
    retention, forming).

    Args:
        path: Path to the plot image.

    Returns:
        One of CATEGORY_ORDER (e.g. "IV Dashboard", "Conduction", "Other").
    """
    name = path.name.lower()
    if "iv_dashboard" in name or "iv dashboard" in name:
        return "IV Dashboard"
    if "conduction" in name:
        return "Conduction"
    if "sclc" in name:
        return "SCLC"
    if "endurance" in name:
        return "Endurance"
    if "retention" in name:
        return "Retention"
    if "forming" in name:
        return "Forming"
    return "Other"


def plot_sort_key(path: Path) -> Tuple[int, List]:
    """
    Sort key for plot images: category order first, then natural filename sort.

    IV Dashboard plots appear first, then Conduction, SCLC, Endurance,
    Retention, Forming, then Other. Within each category, files are sorted
    naturally by name (e.g. 1, 2, 10, 11).

    Args:
        path: Path to the plot image.

    Returns:
        (category_rank, natural_sort_parts) for sorting.
    """
    category = get_plot_category(path)
    try:
        rank = CATEGORY_ORDER.index(category)
    except ValueError:
        rank = len(CATEGORY_ORDER) - 1  # Other
    return (rank, _natural_sort_key(path))


def sort_plot_paths(paths: List[Path]) -> List[Path]:
    """
    Sort a list of plot paths by category (IV dashboard first) then by name.

    Args:
        paths: List of paths to plot images.

    Returns:
        New list with the same paths in sorted order.
    """
    return sorted(paths, key=plot_sort_key)


def group_plots_by_category(paths: List[Path]) -> List[Tuple[str, List[Path]]]:
    """
    Group plot paths by category, in display order (IV Dashboard first).

    Args:
        paths: List of paths to plot images (can be unsorted).

    Returns:
        List of (category_name, [paths]) in CATEGORY_ORDER. Categories
        with no plots are omitted.
    """
    sorted_paths = sort_plot_paths(paths)
    groups = []
    current_cat = None
    current_list = []

    for p in sorted_paths:
        cat = get_plot_category(p)
        if cat != current_cat:
            if current_list:
                groups.append((current_cat, current_list))
            current_cat = cat
            current_list = [p]
        else:
            current_list.append(p)

    if current_list:
        groups.append((current_cat, current_list))
    return groups
