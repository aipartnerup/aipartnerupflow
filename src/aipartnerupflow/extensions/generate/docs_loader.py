"""
Documentation Loader

This module loads and formats framework documentation for LLM context
when generating task trees.
"""

from pathlib import Path
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


def _extract_relevant_sections(text: str, keywords: list, max_chars: int = 2000) -> str:
    """
    Extract sections relevant to keywords from documentation
    
    Args:
        text: Documentation text
        keywords: List of keywords to search for
        max_chars: Maximum characters to extract
        
    Returns:
        Relevant sections of documentation
    """
    if not text or not keywords:
        return _truncate_text(text, max_chars)
    
    lines = text.split('\n')
    relevant_lines = []
    current_section = []
    in_relevant_section = False
    
    # Normalize keywords to lowercase
    keywords_lower = [kw.lower() for kw in keywords]
    
    for line in lines:
        line_lower = line.lower()
        # Check if line contains any keyword
        contains_keyword = any(kw in line_lower for kw in keywords_lower)
        
        if contains_keyword:
            in_relevant_section = True
            # Add current section if it exists
            if current_section:
                relevant_lines.extend(current_section)
                current_section = []
            relevant_lines.append(line)
        elif in_relevant_section:
            # Continue collecting lines in relevant section
            if line.strip():
                relevant_lines.append(line)
            else:
                # Empty line might indicate section end, but keep collecting
                current_section.append(line)
                if len('\n'.join(relevant_lines)) > max_chars * 0.8:
                    break
        elif line.strip().startswith('#') or line.strip().startswith('##'):
            # New section header, reset
            in_relevant_section = False
            current_section = []
    
    result = '\n'.join(relevant_lines)
    if not result.strip():
        # If no relevant sections found, return truncated original
        return _truncate_text(text, max_chars)
    
    return _truncate_text(result, max_chars)


def _extract_keywords_from_requirement(requirement: str) -> list:
    """
    Extract relevant keywords from requirement for document matching
    
    Args:
        requirement: User's natural language requirement
        
    Returns:
        List of keywords
    """
    # Common task-related keywords
    task_keywords = [
        'api', 'rest', 'http', 'fetch', 'request', 'get', 'post', 'put', 'delete',
        'command', 'execute', 'run', 'script', 'process', 'transform', 'convert',
        'database', 'db', 'save', 'store', 'insert', 'update', 'query',
        'file', 'read', 'write', 'download', 'upload', 'parse',
        'parallel', 'sequential', 'dependency', 'wait', 'after', 'before',
        'data', 'process', 'analyze', 'filter', 'aggregate',
        'workflow', 'pipeline', 'tree', 'hierarchy', 'parent', 'child'
    ]
    
    requirement_lower = requirement.lower()
    found_keywords = []
    
    for keyword in task_keywords:
        if keyword in requirement_lower:
            found_keywords.append(keyword)
    
    # Also extract executor-related terms
    executor_terms = [
        'rest_executor', 'command_executor', 'system_info_executor',
        'crewai', 'batch', 'mcp', 'ssh', 'docker', 'grpc'
    ]
    
    for term in executor_terms:
        if term in requirement_lower:
            found_keywords.append(term)
    
    return found_keywords[:10]  # Limit to top 10 keywords


def load_relevant_docs_for_requirement(requirement: str, max_chars_per_section: int = 2000) -> str:
    """
    Load documentation relevant to the specific requirement
    
    Args:
        requirement: User's natural language requirement
        max_chars_per_section: Maximum characters per section
        
    Returns:
        Relevant documentation content
    """
    keywords = _extract_keywords_from_requirement(requirement)
    
    sections = []
    
    # Load and filter task orchestration docs
    orchestration = load_task_orchestration_docs()
    if orchestration:
        if keywords:
            relevant_orchestration = _extract_relevant_sections(orchestration, keywords, max_chars_per_section)
        else:
            relevant_orchestration = _truncate_text(orchestration, max_chars_per_section)
        
        if relevant_orchestration:
            sections.append("=== Task Orchestration (Relevant Patterns) ===")
            sections.append(relevant_orchestration)
            sections.append("")
    
    # Load task examples (always include, they're valuable)
    examples = load_task_examples()
    if examples:
        sections.append("=== Task Tree Examples ===")
        # Extract examples that match keywords
        if keywords:
            relevant_examples = _extract_relevant_sections(examples, keywords, max_chars_per_section)
        else:
            relevant_examples = _truncate_text(examples, max_chars_per_section)
        sections.append(relevant_examples)
        sections.append("")
    
    # Load core concepts (essential, but filtered)
    concepts = load_concepts()
    if concepts:
        sections.append("=== Core Concepts (Summary) ===")
        concepts_truncated = _truncate_text(concepts, max_chars_per_section // 2)
        sections.append(concepts_truncated)
        sections.append("")
    
    return "\n".join(sections)


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
    "load_relevant_docs_for_requirement",
]

