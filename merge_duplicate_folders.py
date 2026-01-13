"""
Script to merge duplicate folders with spaces and underscores.

This script finds folders where there are duplicates:
- One with spaces (e.g., "D108-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s5")
- One with underscores (e.g., "D108-0.1mgml-ITO-PMMA_2.0(2%)-Gold-s5")

It merges the contents from the underscore version into the space version,
then deletes the underscore version.

Usage:
    python merge_duplicate_folders.py [data_folder_path]
    
If no path is provided, it will use the default Data_folder location.
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional


def find_default_data_folder() -> Path:
    """Find the default Data_folder location."""
    home = Path.home()
    candidates = []
    
    # Check OneDrive locations
    for env_key in ("OneDriveCommercial", "OneDrive"):
        env_path = os.environ.get(env_key)
        if env_path:
            root = Path(env_path)
            candidates.append(root / "Documents" / "Data_folder")
    
    # Check explicit OneDrive path
    candidates.append(home / "OneDrive - The University of Nottingham" / "Documents" / "Data_folder")
    
    # Fallback to local Documents
    candidates.append(home / "Documents" / "Data_folder")
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    # Return default even if it doesn't exist yet
    return candidates[-1]


def find_duplicate_folders(data_folder: Path) -> List[Tuple[Path, Path]]:
    """
    Find pairs of folders where one has spaces and one has underscores.
    
    Returns list of tuples: (space_version_path, underscore_version_path)
    """
    duplicates = []
    
    if not data_folder.exists():
        print(f"Data folder does not exist: {data_folder}")
        return duplicates
    
    # Get all folders in the data directory
    folders = [f for f in data_folder.iterdir() if f.is_dir()]
    
    # Create a mapping of normalized names to actual paths
    # Normalize by replacing underscores with spaces for comparison
    normalized_map = {}
    
    for folder in folders:
        # Normalize: replace underscores with spaces for comparison
        normalized = folder.name.replace("_", " ")
        if normalized not in normalized_map:
            normalized_map[normalized] = []
        normalized_map[normalized].append(folder)
    
    # Find pairs where one has spaces and one has underscores
    for normalized_name, folder_list in normalized_map.items():
        if len(folder_list) == 2:
            folder1, folder2 = folder_list[0], folder_list[1]
            
            # Check if one has spaces and the other has underscores in the same positions
            # We want: space_version.replace(" ", "_") == underscore_version
            has_space1 = " " in folder1.name
            has_space2 = " " in folder2.name
            has_underscore1 = "_" in folder1.name
            has_underscore2 = "_" in folder2.name
            
            # One should have spaces, the other should have underscores
            if (has_space1 and has_underscore2) or (has_space2 and has_underscore1):
                # Check if converting spaces to underscores makes them match
                if has_space1 and has_underscore2:
                    if folder1.name.replace(" ", "_") == folder2.name:
                        duplicates.append((folder1, folder2))
                elif has_space2 and has_underscore1:
                    if folder2.name.replace(" ", "_") == folder1.name:
                        duplicates.append((folder2, folder1))
    
    return duplicates


def merge_folders(source: Path, destination: Path) -> bool:
    """
    Merge contents from source folder into destination folder.
    
    Args:
        source: Folder to copy from (will be deleted after merge)
        destination: Folder to copy to (keeps this one)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not destination.exists():
            destination.mkdir(parents=True, exist_ok=True)
        
        # Copy all files and subdirectories from source to destination
        for item in source.iterdir():
            dest_item = destination / item.name
            
            if item.is_file():
                # If file exists in destination, skip it (don't overwrite)
                if dest_item.exists():
                    print(f"  Skipping existing file: {item.name}")
                else:
                    shutil.copy2(item, dest_item)
                    print(f"  Copied file: {item.name}")
            
            elif item.is_dir():
                # If directory exists, merge recursively
                if dest_item.exists():
                    print(f"  Merging subdirectory: {item.name}")
                    merge_folders(item, dest_item)
                else:
                    shutil.copytree(item, dest_item)
                    print(f"  Copied directory: {item.name}")
        
        return True
    
    except Exception as e:
        print(f"  ERROR merging {source.name}: {e}")
        return False


def main(data_folder_path: Optional[str] = None, auto_confirm: bool = False):
    """Main function to merge duplicate folders."""
    if data_folder_path:
        data_folder = Path(data_folder_path)
    else:
        data_folder = find_default_data_folder()
    
    print(f"Looking for duplicate folders in: {data_folder}")
    print()
    
    if not data_folder.exists():
        print(f"ERROR: Data folder does not exist: {data_folder}")
        return
    
    # Find duplicate folders
    duplicates = find_duplicate_folders(data_folder)
    
    if not duplicates:
        print("No duplicate folders found (space vs underscore versions).")
        return
    
    print(f"Found {len(duplicates)} duplicate folder pair(s):")
    print()
    
    for space_folder, underscore_folder in duplicates:
        print(f"  Space version:    {space_folder.name}")
        print(f"  Underscore version: {underscore_folder.name}")
        print()
    
    # Ask for confirmation (unless auto_confirm is True)
    if not auto_confirm:
        try:
            response = input(f"Merge {len(duplicates)} folder pair(s)? (yes/no): ").strip().lower()
            if response not in ('yes', 'y'):
                print("Cancelled.")
                return
        except EOFError:
            # If running non-interactively, auto-confirm
            print("Running in non-interactive mode, auto-confirming merge...")
            auto_confirm = True
    
    print()
    print("Merging folders...")
    print()
    
    success_count = 0
    error_count = 0
    
    for space_folder, underscore_folder in duplicates:
        print(f"Merging: {underscore_folder.name} -> {space_folder.name}")
        
        # Merge underscore version into space version
        if merge_folders(underscore_folder, space_folder):
            # Delete the underscore version after successful merge
            try:
                shutil.rmtree(underscore_folder)
                print(f"  Deleted: {underscore_folder.name}")
                print(f"  Successfully merged into: {space_folder.name}")
                success_count += 1
            except Exception as e:
                print(f"  ERROR deleting {underscore_folder.name}: {e}")
                error_count += 1
        else:
            print(f"  Failed to merge {underscore_folder.name}")
            error_count += 1
        
        print()
    
    print("=" * 60)
    print(f"Summary: {success_count} successful, {error_count} errors")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    data_folder = None
    auto_confirm = False
    
    for arg in sys.argv[1:]:
        if arg in ('--yes', '-y', '--auto'):
            auto_confirm = True
        else:
            data_folder = arg
    
    main(data_folder, auto_confirm=auto_confirm)

