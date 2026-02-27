"""
Utility Module
Provides helper functions for file operations, path handling, and validation.
"""

import os


class PathError(Exception):
    """Raised when path operations fail"""
    pass


class FileError(Exception):
    """Raised when file operations fail"""
    pass


# ===== PATH UTILITIES =====

def normalize_path(path) -> str:
    """
    Ensure we always get a clean string path.
    
    Args:
        path: String path, tuple of path components, or Path object
    
    Returns:
        Absolute path as string
    """
    if isinstance(path, tuple):
        path = os.path.join(*path)
    return os.path.abspath(str(path))


def ensure_directory_exists(path: str, source: str = "") -> None:
    """
    Ensure directory exists, raise error if not.
    
    Args:
        path: Directory path to check
        source: Source/context info for error message
    
    Raises:
        PathError: If directory does not exist
    """
    path = normalize_path(path)
    if not os.path.isdir(path):
        error_msg = f"Directory does not exist: {path}"
        if source:
            error_msg += f" (Source: {source})"
        raise PathError(error_msg)


def ensure_file_exists(path: str, source: str = "") -> None:
    """
    Ensure file exists, raise error if not.
    
    Args:
        path: File path to check
        source: Source/context info for error message
    
    Raises:
        FileError: If file does not exist
    """
    path = normalize_path(path)
    if not os.path.isfile(path):
        error_msg = f"File does not exist: {path}"
        if source:
            error_msg += f" (Source: {source})"
        raise FileError(error_msg)


def create_directories(*paths) -> None:
    """
    Create directories if they don't exist.
    
    Args:
        *paths: Variable number of directory paths to create
    """
    for path in paths:
        path = normalize_path(path)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)


def join_and_ensure_path(
    target_directory: str,
    filename: str,
    source: str = "",
    create_if_missing: bool = True
) -> str:
    """
    Join directory and filename, optionally creating directory.
    
    Args:
        target_directory: Directory path
        filename: Filename to join
        source: Source/context for error messages
        create_if_missing: Create directory if it doesn't exist
    
    Returns:
        Full path (directory + filename)
    
    Raises:
        PathError: If directory doesn't exist and create_if_missing=False
    """
    target_directory = normalize_path(target_directory)
    
    if not os.path.exists(target_directory):
        if create_if_missing:
            create_directories(target_directory)
        else:
            error_msg = f"Directory does not exist: {target_directory}"
            if source:
                error_msg += f" (Source: {source})"
            raise PathError(error_msg)
    
    return os.path.join(target_directory, filename)


def path_exists(path: str) -> bool:
    """
    Check if path exists (file or directory).
    
    Args:
        path: Path to check
    
    Returns:
        True if exists, False otherwise
    """
    path = normalize_path(path)
    return os.path.exists(path)


def is_directory(path: str) -> bool:
    """
    Check if path is a directory.
    
    Args:
        path: Path to check
    
    Returns:
        True if directory, False otherwise
    """
    path = normalize_path(path)
    return os.path.isdir(path)


def is_file(path: str) -> bool:
    """
    Check if path is a file.
    
    Args:
        path: Path to check
    
    Returns:
        True if file, False otherwise
    """
    path = normalize_path(path)
    return os.path.isfile(path)