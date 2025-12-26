"""
Integration tests for TaskExecutor with tools

These tests verify that tools are automatically registered when extensions are imported,
and that TaskExecutor can successfully execute tasks using tools through the extension system.

This is an integration test that tests the full flow:
1. Import extensions (which auto-imports tools)
2. Use TaskExecutor to execute tasks
3. Verify tools work correctly in the execution context
"""

import pytest
import os

# Try to import required modules
try:
    from aipartnerupflow.core.execution.task_executor import TaskExecutor
    from aipartnerupflow.core.tools import get_tool_registry, tool_register, BaseTool
    from pydantic import BaseModel, Field
    from typing import Type
except ImportError:
    TaskExecutor = None
    get_tool_registry = None
    tool_register = None
    BaseTool = None
    pytestmark = pytest.mark.skip("Required modules not available")


@pytest.mark.skipif(TaskExecutor is None, reason="TaskExecutor not available")
class TestTaskExecutorToolsIntegration:
    """Integration tests for TaskExecutor with tools"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set - skipping integration test"
    )
    async def test_task_executor_with_limited_scrape_website_tool(self, use_test_db_session):
        """
        Test TaskExecutor execution with LimitedScrapeWebsiteTool
        
        This test verifies:
        1. Tools are auto-imported when extensions are imported
        2. TaskExecutor can execute tasks using tools through CrewManager
        3. The full execution flow works correctly
        """
        # Check if OpenAI API key is available
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY is not set")
        
        # TaskExecutor automatically imports extensions (which auto-imports tools)
        # So tools should already be registered when TaskExecutor is imported
        # Verify tool is registered
        try:
            from aipartnerupflow.core.tools import get_tool_registry
            registry = get_tool_registry()
            
            # Verify tool is registered (should be auto-registered via TaskExecutor import)
            if "LimitedScrapeWebsiteTool" not in registry.list_tools():
                pytest.skip("LimitedScrapeWebsiteTool not registered (may be missing dependencies)")
        except ImportError:
            pytest.skip("Extensions or tools module not available")
        
        # Create task tree that uses CrewManager with LimitedScrapeWebsiteTool
        # This simulates how users would actually use the system
        # Note: method="crewai_executor" (CrewManager's id) is sufficient, type is optional
        # works should be in params, not inputs
        # Use unique task ID to avoid conflicts with other tests
        import uuid
        task_id = f"test_scrape_{uuid.uuid4().hex[:8]}"
        tasks = [
            {
                "id": task_id,
                "name": "Website Scraper Task",
                "user_id": "test_user",  # Required field
                "schemas": {
                    "method": "crewai_executor"  # Direct executor id lookup, type not needed
                },
                "params": {
                    "name": "Website Scraper Crew",
                    "works": {
                        "agents": {
                            "web_analyzer": {
                                "role": "Web Content Analyzer",
                                "goal": "Analyze website content and provide a summary",
                                "backstory": "You are an expert web content analyzer who can extract and summarize information from websites",
                                "verbose": False,
                                "allow_delegation": False,
                                "llm": "openai/gpt-3.5-turbo",
                                "tools": ["LimitedScrapeWebsiteTool()"]
                            }
                        },
                        "tasks": {
                            "scrape_and_summarize": {
                                "description": "Use the LimitedScrapeWebsiteTool to scrape https://www.spacex.com and provide a brief summary (2-3 sentences) of what the website is about. Focus on the main purpose and key information.",
                                "expected_output": "A brief 2-3 sentence summary of the SpaceX website content",
                                "agent": "web_analyzer"
                            }
                        }
                    }
                }
            }
        ]
        
        # Execute using TaskExecutor (the actual entry point users would use)
        task_executor = TaskExecutor()
        result = await task_executor.execute_tasks(
            tasks=tasks,
            root_task_id=None,
            use_streaming=False
        )
        
        print("=== TaskExecutor result: ===")
        import json
        print(json.dumps(result, indent=2, default=str))
        
        # Verify result structure
        assert result["status"] in ["completed", "failed"]
        
        if result["status"] == "completed":
            # Verify success result
            assert "root_task_id" in result
            assert "progress" in result
            
            # The result should contain information about SpaceX
            # Extract result from task execution
            root_task_id = result["root_task_id"]
            # Note: In a real scenario, you might need to query the database
            # to get the actual task result. For now, we verify the execution completed.
            assert root_task_id is not None
        else:
            # If failed, verify error message
            assert "error" in result or "progress" in result
            # Log the error for debugging
            print(f"Task execution failed: {result.get('error', result.get('progress'))}")
            # Don't fail the test if it's a network error (website might be down)
            error_str = str(result.get('error', result.get('progress', ''))).lower()
            if "network" not in error_str and "timeout" not in error_str:
                raise AssertionError(f"Unexpected error: {result.get('error', result.get('progress'))}")
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set - skipping integration test"
    )
    async def test_task_executor_with_custom_tool(self, use_test_db_session):
        """
        Test TaskExecutor execution with a custom tool registered using @tool_register decorator
        
        This test verifies:
        1. Custom tools can be registered with @tool_register
        2. TaskExecutor can execute tasks using custom tools
        3. The full execution flow works correctly
        """
        # Check if OpenAI API key is available
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY is not set")
        
        try:
            from aipartnerupflow.core.tools import tool_register, get_tool_registry, BaseTool
            from pydantic import BaseModel, Field
            from typing import Type
        except ImportError:
            pytest.skip("CrewAI tools module not available")
        
        # Define a custom tool with @tool_register decorator
        class TextProcessorInputSchema(BaseModel):
            text: str = Field(..., description="The text to process")
            operation: str = Field(default="uppercase", description="Operation to perform: uppercase, lowercase, reverse, or word_count")
        
        @tool_register()
        class TextProcessorTool(BaseTool):
            """A custom tool for text processing operations"""
            name: str = "Text Processor"
            description: str = "Process text with various operations: uppercase, lowercase, reverse, or word_count"
            args_schema: Type[BaseModel] = TextProcessorInputSchema
            
            def _run(self, text: str, operation: str = "uppercase") -> str:
                """Process text based on the operation"""
                if operation == "uppercase":
                    return text.upper()
                elif operation == "lowercase":
                    return text.lower()
                elif operation == "reverse":
                    return text[::-1]
                elif operation == "word_count":
                    return str(len(text.split()))
                else:
                    return f"Unknown operation: {operation}"
        
        # Verify tool is registered
        registry = get_tool_registry()
        assert "TextProcessorTool" in registry.list_tools(), "TextProcessorTool should be registered"
        
        # Create task tree that uses CrewManager with TextProcessorTool
        # Note: method="crewai_executor" (CrewManager's id) is sufficient, type is optional
        # works should be in params, not inputs
        # Use unique task ID to avoid conflicts with other tests
        import uuid
        task_id = f"test_text_{uuid.uuid4().hex[:8]}"
        tasks = [
            {
                "id": task_id,
                "name": "Text Processor Task",
                "user_id": "test_user",  # Required field
                "schemas": {
                    "method": "crewai_executor"  # Direct executor id lookup, type not needed
                },
                "params": {
                    "name": "Text Processor Crew",
                    "works": {
                        "agents": {
                            "text_processor": {
                                "role": "Text Processing Assistant",
                                "goal": "Process and analyze text using various operations",
                                "backstory": "You are an expert text processor who can perform various text operations",
                                "verbose": False,
                                "allow_delegation": False,
                                "llm": "openai/gpt-3.5-turbo",
                                "tools": ["TextProcessorTool()"]
                            }
                        },
                        "tasks": {
                            "process_text": {
                                "description": "Use the TextProcessorTool to process the text 'Hello World' with the 'uppercase' operation, then use 'word_count' operation on the result. Provide a summary of what operations were performed.",
                                "expected_output": "A summary of the text processing operations performed",
                                "agent": "text_processor"
                            }
                        }
                    }
                }
            }
        ]
        
        # Execute using TaskExecutor
        task_executor = TaskExecutor()
        result = await task_executor.execute_tasks(
            tasks=tasks,
            root_task_id=None,
            use_streaming=False
        )
        
        print("=== TaskExecutor result: ===")
        import json
        print(json.dumps(result, indent=2, default=str))
        
        # Verify result structure
        assert result["status"] in ["completed", "failed"]
        
        if result["status"] == "completed":
            # Verify success result
            assert "root_task_id" in result
            assert "progress" in result
            root_task_id = result["root_task_id"]
            assert root_task_id is not None
        else:
            # If failed, verify error message
            assert "error" in result or "progress" in result
            print(f"Text processing failed: {result.get('error', result.get('progress'))}")
            raise AssertionError(f"Unexpected error: {result.get('error', result.get('progress'))}")

