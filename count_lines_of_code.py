"""
Script to count lines of code in the repository.

This script walks through the repository and counts:
- Total lines in Python files
- Total lines in other code files (JSON, etc.)
- Breakdown by file type
- Excludes common non-code directories and files
"""

import os
from pathlib import Path
from collections import defaultdict

# Directories and files to exclude
EXCLUDE_DIRS = {
    '__pycache__',
    '.git',
    'node_modules',
    '.pytest_cache',
    '.mypy_cache',
    'build',
    'dist',
    'venv',
    'env',
    '.venv',
    '.env',
    'Data_save_loc',  # User data directory
}

EXCLUDE_EXTENSIONS = {
    '.pyc',
    '.pyo',
    '.pyd',
    '.dll',
    '.exe',
    '.so',
    '.dylib',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.pdf',
    '.svg',
    '.ico',
    '.zip',
    '.tar',
    '.gz',
    '.csv',  # Data files
}

# File types to analyze
CODE_EXTENSIONS = {
    '.py': 'Python',
    '.json': 'JSON',
    '.md': 'Markdown',
    '.txt': 'Text',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.ini': 'Config',
    '.cfg': 'Config',
    '.toml': 'TOML',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.html': 'HTML',
    '.css': 'CSS',
    '.xml': 'XML',
    '.sql': 'SQL',
    '.sh': 'Shell',
    '.bat': 'Batch',
    '.ps1': 'PowerShell',
    '.cpp': 'C++',
    '.c': 'C',
    '.h': 'C/C++ Header',
    '.hpp': 'C++ Header',
    '.java': 'Java',
    '.go': 'Go',
    '.rs': 'Rust',
    '.ino': 'Arduino',
    '.backup': 'Backup',
}


def should_exclude_path(path: Path) -> bool:
    """Check if a path should be excluded from counting."""
    # Check if any part of the path is in exclude dirs
    parts = path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    
    # Check extension
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    
    # Exclude hidden files/dirs (starting with .)
    if any(part.startswith('.') and part not in {'.', '..'} for part in parts):
        # Allow .md and .json files though
        if path.suffix.lower() not in {'.md', '.json', '.yaml', '.yml'}:
            return True
    
    return False


def count_lines_in_file(file_path: Path) -> tuple[int, int, int]:
    """
    Count lines in a file.
    
    Returns:
        (total_lines, code_lines, blank_lines)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        total = len(lines)
        blank = sum(1 for line in lines if not line.strip())
        code = total - blank
        
        return total, code, blank
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return 0, 0, 0


def count_repository_lines(root_dir: str = '.') -> dict:
    """Count lines of code in the repository."""
    root = Path(root_dir).resolve()
    
    if not root.exists():
        print(f"Error: Directory '{root_dir}' does not exist!")
        return {}
    
    stats = defaultdict(lambda: {
        'files': 0,
        'total_lines': 0,
        'code_lines': 0,
        'blank_lines': 0,
        'file_list': []
    })
    
    # Walk through all files
    for file_path in root.rglob('*'):
        # Skip directories
        if file_path.is_dir():
            continue
        
        # Check if should exclude
        if should_exclude_path(file_path):
            continue
        
        # Get file extension
        ext = file_path.suffix.lower()
        
        # Skip if not a recognized code file type
        if ext not in CODE_EXTENSIONS:
            continue
        
        # Count lines
        total, code, blank = count_lines_in_file(file_path)
        
        # Update stats
        file_type = CODE_EXTENSIONS[ext]
        stats[file_type]['files'] += 1
        stats[file_type]['total_lines'] += total
        stats[file_type]['code_lines'] += code
        stats[file_type]['blank_lines'] += blank
        stats[file_type]['file_list'].append(str(file_path.relative_to(root)))
    
    return dict(stats)


def print_statistics(stats: dict):
    """Print statistics in a formatted way."""
    if not stats:
        print("No files found to count!")
        return
    
    # Calculate totals
    total_files = sum(s['files'] for s in stats.values())
    total_lines = sum(s['total_lines'] for s in stats.values())
    total_code = sum(s['code_lines'] for s in stats.values())
    total_blank = sum(s['blank_lines'] for s in stats.values())
    
    print("=" * 70)
    print("REPOSITORY CODE STATISTICS")
    print("=" * 70)
    print()
    
    # Summary
    print(f"SUMMARY:")
    print(f"  Total Files Analyzed: {total_files:,}")
    print(f"  Total Lines:          {total_lines:,}")
    print(f"  Code Lines:           {total_code:,}")
    print(f"  Blank Lines:          {total_blank:,}")
    print(f"  Code/Total Ratio:     {total_code/total_lines*100:.1f}%")
    print()
    
    # Breakdown by file type
    print("BREAKDOWN BY FILE TYPE:")
    print("-" * 70)
    print(f"{'Type':<20} {'Files':<10} {'Total Lines':<15} {'Code Lines':<15} {'Blank Lines':<15}")
    print("-" * 70)
    
    # Sort by code lines (descending)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['code_lines'], reverse=True)
    
    for file_type, data in sorted_stats:
        print(f"{file_type:<20} {data['files']:<10,} {data['total_lines']:<15,} "
              f"{data['code_lines']:<15,} {data['blank_lines']:<15,}")
    
    print("-" * 70)
    print()
    
    # Top 10 largest files
    print("TOP 10 LARGEST FILES (by code lines):")
    print("-" * 70)
    
    all_files = []
    for file_type, data in stats.items():
        for file_path in data['file_list']:
            total, code, blank = count_lines_in_file(Path(file_path))
            all_files.append((file_path, file_type, total, code, blank))
    
    # Sort by code lines
    all_files.sort(key=lambda x: x[3], reverse=True)
    
    for i, (file_path, file_type, total, code, blank) in enumerate(all_files[:10], 1):
        # Truncate path if too long
        display_path = file_path if len(file_path) <= 60 else "..." + file_path[-57:]
        print(f"{i:2}. {display_path:<60} [{file_type}] {code:,} lines")
    
    print()


if __name__ == "__main__":
    # Get repository root (current directory by default)
    repo_root = os.getcwd()
    
    print(f"Scanning repository: {repo_root}")
    print()
    
    # Count lines
    statistics = count_repository_lines(repo_root)
    
    # Print results
    print_statistics(statistics)
    
    # Save detailed report
    report_file = Path(repo_root) / "lines_of_code_report.txt"
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("DETAILED CODE STATISTICS REPORT\n")
            f.write("=" * 70 + "\n\n")
            
            total_files = sum(s['files'] for s in statistics.values())
            total_lines = sum(s['total_lines'] for s in statistics.values())
            total_code = sum(s['code_lines'] for s in statistics.values())
            
            f.write(f"Total Files: {total_files:,}\n")
            f.write(f"Total Lines: {total_lines:,}\n")
            f.write(f"Code Lines:  {total_code:,}\n\n")
            
            f.write("BREAKDOWN BY FILE TYPE:\n")
            f.write("-" * 70 + "\n")
            
            sorted_stats = sorted(statistics.items(), key=lambda x: x[1]['code_lines'], reverse=True)
            for file_type, data in sorted_stats:
                f.write(f"\n{file_type}:\n")
                f.write(f"  Files: {data['files']:,}\n")
                f.write(f"  Total Lines: {data['total_lines']:,}\n")
                f.write(f"  Code Lines: {data['code_lines']:,}\n")
                f.write(f"  Blank Lines: {data['blank_lines']:,}\n")
            
            f.write("\n\nALL FILES:\n")
            f.write("-" * 70 + "\n")
            for file_type, data in sorted_stats:
                for file_path in sorted(data['file_list']):
                    total, code, blank = count_lines_in_file(Path(file_path))
                    f.write(f"{file_path} [{file_type}] - {code:,} code lines, {total:,} total lines\n")
        
        print(f"Detailed report saved to: {report_file}")
    except Exception as e:
        print(f"Warning: Could not save detailed report: {e}")

