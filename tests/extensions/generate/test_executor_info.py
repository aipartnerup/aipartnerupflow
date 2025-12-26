"""
Test executor_info module
"""

from aipartnerupflow.extensions.generate.executor_info import (
    get_available_executors,
    get_executor_schema,
    format_executors_for_llm
)


class TestExecutorInfo:
    """Test executor information collection"""
    
    def test_get_available_executors(self):
        """Test that we can get available executors"""
        executors = get_available_executors()
        assert isinstance(executors, list)
        # Should have at least some executors registered
        assert len(executors) > 0
        
        # Check structure
        for executor in executors:
            assert "id" in executor
            assert "name" in executor
            assert "description" in executor
            assert "tags" in executor
            assert "task_type" in executor
            assert "input_schema" in executor
    
    def test_get_executor_schema(self):
        """Test getting schema for specific executor"""
        executors = get_available_executors()
        if executors:
            executor_id = executors[0]["id"]
            schema = get_executor_schema(executor_id)
            # Schema might be None if not available, but should not raise error
            assert schema is None or isinstance(schema, dict)
    
    def test_get_executor_schema_not_found(self):
        """Test getting schema for non-existent executor"""
        schema = get_executor_schema("non_existent_executor")
        assert schema is None
    
    def test_format_executors_for_llm(self):
        """Test formatting executors for LLM context"""
        formatted = format_executors_for_llm()
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        # Should contain executor information
        assert "Available Executors" in formatted or "No executors" in formatted

