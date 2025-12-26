"""
Test docs_loader module
"""

from aipartnerupflow.extensions.generate.docs_loader import (
    load_task_orchestration_docs,
    load_task_examples,
    load_executor_docs,
    load_concepts,
    load_all_docs
)


class TestDocsLoader:
    """Test documentation loading"""
    
    def test_load_task_orchestration_docs(self):
        """Test loading task orchestration docs"""
        docs = load_task_orchestration_docs()
        assert isinstance(docs, str)
        # Should contain some content if file exists
        # (might be empty if file doesn't exist in test environment)
    
    def test_load_task_examples(self):
        """Test loading task examples"""
        docs = load_task_examples()
        assert isinstance(docs, str)
    
    def test_load_executor_docs(self):
        """Test loading executor docs"""
        docs = load_executor_docs()
        assert isinstance(docs, str)
    
    def test_load_concepts(self):
        """Test loading concepts"""
        docs = load_concepts()
        assert isinstance(docs, str)
    
    def test_load_all_docs(self):
        """Test loading all docs"""
        docs = load_all_docs()
        assert isinstance(docs, str)
        # Should contain multiple sections
        assert len(docs) > 0

