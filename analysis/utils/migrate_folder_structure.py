"""
Migration script to reorganize analysis data into unified sample_analysis/ structure.

This script migrates existing data from the old scattered structure to the new unified structure:
- device_tracking/ → sample_analysis/device_tracking/
- device_research/ → sample_analysis/device_research/
- analysis/sweeps/ → sample_analysis/analysis/sweeps/
- sample_analysis/origin_data/ → sample_analysis/plots/data_origin_formatted/

Usage:
    python migrate_folder_structure.py <sample_folder_path>
    
Or import and use:
    from analysis.utils.migrate_folder_structure import migrate_sample
    migrate_sample("path/to/sample")
"""

import os
import shutil
from pathlib import Path
from typing import Optional
import json


def migrate_sample(sample_folder: str, dry_run: bool = False) -> dict:
    """
    Migrate a sample folder to the new unified structure.
    
    Args:
        sample_folder: Path to sample folder
        dry_run: If True, only report what would be done without making changes
    
    Returns:
        Dictionary with migration results
    """
    sample_path = Path(sample_folder)
    if not sample_path.exists():
        return {"error": f"Sample folder not found: {sample_folder}"}
    
    results = {
        "sample": str(sample_path),
        "moved": [],
        "skipped": [],
        "errors": [],
        "dry_run": dry_run
    }
    
    # Create sample_analysis directory structure
    sample_analysis_dir = sample_path / "sample_analysis"
    if not dry_run:
        sample_analysis_dir.mkdir(exist_ok=True)
    
    # 1. Migrate device_tracking/
    tracking_source = sample_path / "device_tracking"
    tracking_dest = sample_analysis_dir / "device_tracking"
    
    if tracking_source.exists() and tracking_source.is_dir():
        if not dry_run:
            tracking_dest.mkdir(exist_ok=True)
            # Move all files
            for file in tracking_source.iterdir():
                if file.is_file():
                    dest_file = tracking_dest / file.name
                    if not dest_file.exists():
                        shutil.move(str(file), str(dest_file))
                        results["moved"].append(f"device_tracking/{file.name}")
                    else:
                        results["skipped"].append(f"device_tracking/{file.name} (already exists)")
        else:
            # Dry run - just count files
            file_count = len([f for f in tracking_source.iterdir() if f.is_file()])
            results["moved"].append(f"device_tracking/ ({file_count} files)")
        
        # Remove empty source directory
        if not dry_run:
            try:
                if not any(tracking_source.iterdir()):
                    tracking_source.rmdir()
            except:
                pass
    
    # 2. Migrate device_research/
    research_source = sample_path / "device_research"
    research_dest = sample_analysis_dir / "device_research"
    
    if research_source.exists() and research_source.is_dir():
        if not dry_run:
            research_dest.mkdir(exist_ok=True)
            # Move all device subdirectories
            for device_dir in research_source.iterdir():
                if device_dir.is_dir():
                    dest_device_dir = research_dest / device_dir.name
                    if not dest_device_dir.exists():
                        shutil.move(str(device_dir), str(dest_device_dir))
                        results["moved"].append(f"device_research/{device_dir.name}/")
                    else:
                        # Merge contents
                        for file in device_dir.iterdir():
                            dest_file = dest_device_dir / file.name
                            if not dest_file.exists():
                                shutil.move(str(file), str(dest_file))
                                results["moved"].append(f"device_research/{device_dir.name}/{file.name}")
                            else:
                                results["skipped"].append(f"device_research/{device_dir.name}/{file.name} (already exists)")
                        try:
                            device_dir.rmdir()
                        except:
                            pass
        else:
            # Dry run
            device_count = len([d for d in research_source.iterdir() if d.is_dir()])
            results["moved"].append(f"device_research/ ({device_count} device folders)")
        
        # Remove empty source directory
        if not dry_run:
            try:
                if not any(research_source.iterdir()):
                    research_source.rmdir()
            except:
                pass
    
    # 3. Migrate analysis/sweeps/
    analysis_source = sample_path / "analysis" / "sweeps"
    analysis_dest = sample_analysis_dir / "analysis" / "sweeps"
    
    if analysis_source.exists() and analysis_source.is_dir():
        if not dry_run:
            analysis_dest.mkdir(parents=True, exist_ok=True)
            # Move all device subdirectories
            for device_dir in analysis_source.iterdir():
                if device_dir.is_dir():
                    dest_device_dir = analysis_dest / device_dir.name
                    if not dest_device_dir.exists():
                        shutil.move(str(device_dir), str(dest_device_dir))
                        results["moved"].append(f"analysis/sweeps/{device_dir.name}/")
                    else:
                        # Merge contents
                        for file in device_dir.iterdir():
                            dest_file = dest_device_dir / file.name
                            if not dest_file.exists():
                                shutil.move(str(file), str(dest_file))
                                results["moved"].append(f"analysis/sweeps/{device_dir.name}/{file.name}")
                            else:
                                results["skipped"].append(f"analysis/sweeps/{device_dir.name}/{file.name} (already exists)")
                        try:
                            device_dir.rmdir()
                        except:
                            pass
        else:
            # Dry run
            device_count = len([d for d in analysis_source.iterdir() if d.is_dir()])
            results["moved"].append(f"analysis/sweeps/ ({device_count} device folders)")
        
        # Remove empty analysis directory if it only contained sweeps
        if not dry_run:
            try:
                analysis_parent = analysis_source.parent
                if analysis_parent.exists() and not any(analysis_parent.iterdir()):
                    analysis_parent.rmdir()
            except:
                pass
    
    # 4. Migrate sample_analysis/origin_data/ to sample_analysis/plots/data_origin_formatted/
    origin_source = sample_analysis_dir / "origin_data"
    origin_dest = sample_analysis_dir / "plots" / "data_origin_formatted"
    
    if origin_source.exists() and origin_source.is_dir():
        if not dry_run:
            origin_dest.mkdir(parents=True, exist_ok=True)
            # Move all subdirectories (overall, code_names)
            for subdir in origin_source.iterdir():
                if subdir.is_dir():
                    dest_subdir = origin_dest / subdir.name
                    if not dest_subdir.exists():
                        shutil.move(str(subdir), str(dest_subdir))
                        results["moved"].append(f"origin_data/{subdir.name}/ → plots/data_origin_formatted/{subdir.name}/")
                    else:
                        # Merge contents
                        for file in subdir.iterdir():
                            dest_file = dest_subdir / file.name
                            if not dest_file.exists():
                                shutil.move(str(file), str(dest_file))
                                results["moved"].append(f"origin_data/{subdir.name}/{file.name}")
                            else:
                                results["skipped"].append(f"origin_data/{subdir.name}/{file.name} (already exists)")
                        try:
                            subdir.rmdir()
                        except:
                            pass
        else:
            # Dry run
            subdir_count = len([d for d in origin_source.iterdir() if d.is_dir()])
            results["moved"].append(f"origin_data/ ({subdir_count} subdirectories) → plots/data_origin_formatted/")
        
        # Remove empty origin_data directory
        if not dry_run:
            try:
                if not any(origin_source.iterdir()):
                    origin_source.rmdir()
            except:
                pass
    
    return results


def print_migration_results(results: dict) -> None:
    """Print migration results in a readable format."""
    print("\n" + "=" * 80)
    print("MIGRATION RESULTS")
    print("=" * 80)
    print(f"Sample: {results['sample']}")
    print(f"Mode: {'DRY RUN' if results['dry_run'] else 'LIVE'}")
    print()
    
    if results["moved"]:
        print(f"Moved/Migrated ({len(results['moved'])} items):")
        for item in results["moved"][:20]:  # Show first 20
            print(f"  ✓ {item}")
        if len(results["moved"]) > 20:
            print(f"  ... and {len(results['moved']) - 20} more")
        print()
    
    if results["skipped"]:
        print(f"Skipped ({len(results['skipped'])} items):")
        for item in results["skipped"][:10]:  # Show first 10
            print(f"  - {item}")
        if len(results["skipped"]) > 10:
            print(f"  ... and {len(results['skipped']) - 10} more")
        print()
    
    if results["errors"]:
        print(f"Errors ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"  ✗ {error}")
        print()
    
    print("=" * 80)


def main():
    """Command-line interface for migration."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python migrate_folder_structure.py <sample_folder_path> [--dry-run]")
        print("\nExample:")
        print("  python migrate_folder_structure.py 'C:/Data_folder/Chris_Sample_4'")
        print("  python migrate_folder_structure.py 'C:/Data_folder/Chris_Sample_4' --dry-run")
        sys.exit(1)
    
    sample_folder = sys.argv[1]
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    if dry_run:
        print("DRY RUN MODE - No files will be moved")
        print()
    
    results = migrate_sample(sample_folder, dry_run=dry_run)
    print_migration_results(results)
    
    if "error" in results:
        sys.exit(1)


if __name__ == "__main__":
    main()

