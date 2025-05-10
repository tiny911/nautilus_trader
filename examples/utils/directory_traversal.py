#!/usr/bin/env python3
# -------------------------------------------------------------------------------------------------
#  Directory Traversal Utility
#
#  Demonstrates various ways to traverse directories in Python
# -------------------------------------------------------------------------------------------------

import os
from pathlib import Path


def traverse_with_os_walk(root_dir: str, recursive: bool = True):
    """Traverse directories using os.walk()"""
    print(f"\nTraversing with os.walk (recursive={recursive}): {root_dir}")
    for root, dirs, files in os.walk(root_dir):
        print(f"\nDirectory: {root}")
        print(f"Subdirectories: {dirs}")
        print(f"Files: {files}")

        if not recursive:
            break  # Only show top level


def traverse_with_pathlib(root_dir: str, recursive: bool = True):
    """Traverse directories using pathlib.Path"""
    print(f"\nTraversing with pathlib (recursive={recursive}): {root_dir}")
    path = Path(root_dir)

    if recursive:
        for item in path.rglob("*"):
            if item.is_dir():
                print(f"Directory: {item}")
            else:
                print(f"File: {item}")
    else:
        for item in path.glob("*"):
            if item.is_dir():
                print(f"Directory: {item}")
            else:
                print(f"File: {item}")


def filter_files_by_extension(root_dir: str, extension: str):
    """Filter files by extension using pathlib"""
    print(f"\nFiltering files with extension '{extension}': {root_dir}")
    path = Path(root_dir)
    for file in path.rglob(f"*.{extension}"):
        print(file)


if __name__ == "__main__":
    # Example usage
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = "/home/tiny/github/CZSC投研数据/"

    print("=== Directory Traversal Examples ===")
    traverse_with_os_walk(test_dir, recursive=False)
    traverse_with_pathlib(test_dir, recursive=False)

    print("\n=== Recursive Examples ===")
    traverse_with_os_walk(test_dir)
    traverse_with_pathlib(test_dir)

    print("\n=== Filtering Examples ===")
    filter_files_by_extension(test_dir, "py")
