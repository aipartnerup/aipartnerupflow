"""
Documentation Loader

This module loads and formats framework documentation for LLM context
when generating task trees.
"""

import os
from pathlib import Path
from typing import Optional
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Get the project root directory (assuming this file is in src/aipartnerupflow/extensions/generate/)
# Go up from this file: generate/ -> extensions/ -> aipartnerupflow/ -> src/ -> project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_DOCS_DIR = _PROJECT_ROOT / "docs"


def _read_doc_file(relative_path: str) -> str:
    """
    Read a documentation file
    
    Args:
        relative_path: Path relative to docs/ directory
        
    Returns:
        File contents as string, or empty string if file not found
    """
    file_path = _DOCS_DIR / relative_path
    try:
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding='utf-8')
        else:
            logger.warning(f"Documentation file not found: {file_path}")
            return ""
    except Exception as e:
        logger.error(f"Error reading documentation file {file_path}: {e}")
        return ""


def load_task_orchestration_docs() -> str:
    """
    Load task orchestration guide
    
    Returns:
        Task orchestration documentation content
    """
    return _read_doc_file("guides/task-orchestration.md")


def load_task_examples() -> str:
    """
    Load task tree examples
    
    Returns:
        Task tree examples documentation content
    """
    return _read_doc_file("examples/task-tree.md")


def load_executor_docs() -> str:
    """
    Load custom tasks guide
    
    Returns:
        Custom tasks documentation content
    """
    return _read_doc_file("guides/custom-tasks.md")


def load_concepts() -> str:
    """
    Load core concepts documentation
    
    Returns:
        Core concepts documentation content
    """
    return _read_doc_file("getting-started/concepts.md")


def _truncate_text(text: str, max_chars: int = 3000) -> str:
    """
    Truncate text to maximum character count, preserving structure
    
    Args:
        text: Text to truncate
        max_chars: Maximum characters to keep
        
    Returns:
        Truncated text with indicator
    """
    if len(text) <= max_chars:
        return text
    
    # Try to truncate at a sentence boundary
    truncated = text[:max_chars]
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    
    # Use the later of period or newline
    cut_point = max(last_period, last_newline)
    if cut_point > max_chars * 0.8:  # Only use if we keep at least 80% of content
        truncated = truncated[:cut_point + 1]
    
    return truncated + f"\n\n[Content truncated to {max_chars} characters for brevity]"


def load_all_docs(max_chars_per_section: int = 2000) -> str:
    """
    Load all relevant documentation for LLM context (truncated for token limits)
    
    Args:
        max_chars_per_section: Maximum characters per documentation section
        
    Returns:
        Combined documentation content (truncated)
    """
    sections = []
    
    # Core concepts (essential, keep more)
    concepts = load_concepts()
    if concepts:
        sections.append("=== Core Concepts (Summary) ===")
        # Extract key points from concepts
        concepts_truncated = _truncate_text(concepts, max_chars_per_section)
        sections.append(concepts_truncated)
        sections.append("")
    
    # Task orchestration (key rules only)
    orchestration = load_task_orchestration_docs()
    if orchestration:
        sections.append("=== Task Orchestration (Key Rules) ===")
        # Extract key rules about parent_id vs dependencies
        key_rules = []
        lines = orchestration.split('\n')
        in_key_section = False
        for line in lines:
            if 'parent_id' in line.lower() or 'dependencies' in line.lower() or 'execution order' in line.lower():
                in_key_section = True
            if in_key_section and line.strip():
                key_rules.append(line)
                if len('\n'.join(key_rules)) > max_chars_per_section:
                    break
        
        if key_rules:
            sections.append(_truncate_text('\n'.join(key_rules), max_chars_per_section))
        else:
            sections.append(_truncate_text(orchestration, max_chars_per_section))
        sections.append("")
    
    # Task examples (just a few examples)
    examples = load_task_examples()
    if examples:
        sections.append("=== Task Tree Examples (Key Examples) ===")
        # Extract first example
        example_truncated = _truncate_text(examples, max_chars_per_section)
        sections.append(example_truncated)
        sections.append("")
    
    return "\n".join(sections)


__all__ = [
    "load_task_orchestration_docs",
    "load_task_examples",
    "load_executor_docs",
    "load_concepts",
    "load_all_docs",
]

