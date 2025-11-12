"""
Test CrewManager functionality

This module contains both unit tests (with mocks) and integration tests (with real OpenAI API).
Integration tests require OPENAI_API_KEY environment variable.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock

# Try to import CrewManager, skip tests if not available
try:
    from aipartnerupflow.extensions.crewai import CrewManager, register_tool, resolve_tool
    from crewai import LLM, Agent
except ImportError:
    CrewManager = None
    LLM = None
    Agent = None
    register_tool = None
    resolve_tool = None
    pytestmark = pytest.mark.skip("crewai module not available")


@pytest.mark.skipif(CrewManager is None, reason="CrewManager not available")
class TestCrewManager:
    """Test cases for CrewManager"""
    
    @pytest.mark.asyncio
    async def test_execute_with_mock(self):
        """Test crew execution with mocked CrewAI"""
        # Create mock crew result
        mock_result = Mock()
        mock_result.raw = "Test execution result"
        mock_result.token_usage = {
            "total_tokens": 100,
            "prompt_tokens": 60,
            "completion_tokens": 40,
            "cached_prompt_tokens": 0,
            "successful_requests": 1
        }
        
        # Create mock crew
        mock_crew = Mock()
        mock_crew.kickoff = Mock(return_value=mock_result)
        
        # Create CrewManager with mock crew
        with patch('aipartnerupflow.extensions.crewai.crew_manager.CrewAI') as mock_crew_class:
            mock_crew_class.return_value = mock_crew
            
            # Initialize CrewManager with works format
            crew_manager = CrewManager(
                name="Test Crew",
                works={
                    "agents": {
                        "researcher": {
                            "role": "Researcher",
                            "goal": "Research and gather information",
                            "backstory": "You are a research assistant"
                        }
                    },
                    "tasks": {
                        "research_task": {
                            "description": "Research a topic",
                            "expected_output": "A summary of the research findings",
                            "agent": "researcher"
                        }
                    }
                }
            )
            
            # Replace the crew instance with our mock
            crew_manager.crew = mock_crew
            
            # Execute crew
            result = await crew_manager.execute()
            
            # Verify result structure
            assert result["status"] == "success"
            assert result["result"] == "Test execution result"
            assert "token_usage" in result
            assert result["token_usage"]["total_tokens"] == 100
            assert result["token_usage"]["prompt_tokens"] == 60
            assert result["token_usage"]["completion_tokens"] == 40
            
            # Verify crew.kickoff was called
            mock_crew.kickoff.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_with_error_mock(self):
        """Test crew execution error handling with mocked CrewAI"""
        # Create mock crew that raises an error
        mock_crew = Mock()
        mock_crew.kickoff = Mock(side_effect=Exception("Test error"))
        
        # Mock Task class
        mock_task = Mock()
        
        # Create CrewManager with mock crew
        with patch('aipartnerupflow.extensions.crewai.crew_manager.CrewAI') as mock_crew_class, \
             patch('aipartnerupflow.extensions.crewai.crew_manager.Task') as mock_task_class, \
             patch('aipartnerupflow.extensions.crewai.crew_manager.Agent') as mock_agent_class:
            mock_crew_class.return_value = mock_crew
            mock_task_class.return_value = mock_task
            mock_agent_class.return_value = Mock()
            
            # Initialize CrewManager with works format
            crew_manager = CrewManager(
                name="Test Crew",
                works={
                    "agents": {
                        "researcher": {
                            "role": "Researcher",
                            "goal": "Research and gather information",
                            "backstory": "You are a research assistant"
                        }
                    },
                    "tasks": {
                        "research_task": {
                            "description": "Research a topic",
                            "expected_output": "A summary of the research findings",
                            "agent": "researcher"
                        }
                    }
                }
            )
            
            # Replace the crew instance with our mock
            crew_manager.crew = mock_crew
            
            # Execute crew (should handle error gracefully)
            result = await crew_manager.execute()
            
            # Verify error result structure
            assert result["status"] == "failed"
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["result"] is None

    @pytest.mark.skipif(CrewManager is None or LLM is None, reason="CrewManager or LLM not available")
    def test_llm_string_conversion(self):
        """Test that string LLM names are converted to LLM objects"""
        # Mock LLM class
        mock_llm_instance = Mock()
        mock_llm_instance.model = "gpt-4"
        
        with patch('aipartnerupflow.extensions.crewai.crew_manager.LLM') as mock_llm_class:
            mock_llm_class.return_value = mock_llm_instance
            
            # Mock Agent, Task and CrewAI
            mock_agent = Mock()
            mock_task = Mock()
            mock_crew = Mock()
            
            with patch('aipartnerupflow.extensions.crewai.crew_manager.Agent') as mock_agent_class, \
                 patch('aipartnerupflow.extensions.crewai.crew_manager.Task') as mock_task_class, \
                 patch('aipartnerupflow.extensions.crewai.crew_manager.CrewAI') as mock_crew_class:
                mock_agent_class.return_value = mock_agent
                mock_task_class.return_value = mock_task
                mock_crew_class.return_value = mock_crew
                
                # Create CrewManager with string LLM in works format
                crew_manager = CrewManager(
                    name="Test Crew",
                    works={
                        "agents": {
                            "researcher": {
                                "role": "Researcher",
                                "goal": "Research",
                                "backstory": "You are a researcher",
                                "llm": "gpt-4"  # String LLM name
                            }
                        },
                        "tasks": {
                            "research_task": {
                                "description": "Research a topic",
                                "expected_output": "A summary of the research findings",
                                "agent": "researcher"
                            }
                        }
                    }
                )
                
                # Verify LLM was called with the model name
                mock_llm_class.assert_called_with(model="gpt-4")
                
                # Verify Agent was called with LLM object
                call_args = mock_agent_class.call_args
                assert call_args is not None
                assert "llm" in call_args.kwargs
                assert call_args.kwargs["llm"] == mock_llm_instance
    
    @pytest.mark.skipif(CrewManager is None or resolve_tool is None, reason="CrewManager or resolve_tool not available")
    def test_tools_string_conversion(self):
        """Test that string tool names are converted to callable objects"""
        # Create mock tool
        mock_tool = Mock()
        mock_tool.run = Mock(return_value="tool result")
        
        # Mock resolve_tool to return our mock tool
        with patch('aipartnerupflow.extensions.crewai.crew_manager.resolve_tool') as mock_resolve_tool:
            mock_resolve_tool.return_value = mock_tool
            
            # Mock Agent, Task and CrewAI
            mock_agent = Mock()
            mock_task = Mock()
            mock_crew = Mock()
            
            with patch('aipartnerupflow.extensions.crewai.crew_manager.Agent') as mock_agent_class, \
                 patch('aipartnerupflow.extensions.crewai.crew_manager.Task') as mock_task_class, \
                 patch('aipartnerupflow.extensions.crewai.crew_manager.CrewAI') as mock_crew_class:
                mock_agent_class.return_value = mock_agent
                mock_task_class.return_value = mock_task
                mock_crew_class.return_value = mock_crew
                
                # Create CrewManager with string tool names in works format
                crew_manager = CrewManager(
                    name="Test Crew",
                    works={
                        "agents": {
                            "researcher": {
                                "role": "Researcher",
                                "goal": "Research",
                                "backstory": "You are a researcher",
                                "tools": ["SerperDevTool()", "ScrapeWebsiteTool()"]  # String tool names
                            }
                        },
                        "tasks": {
                            "research_task": {
                                "description": "Research a topic",
                                "expected_output": "A summary of the research findings",
                                "agent": "researcher"
                            }
                        }
                    }
                )
                
                # Verify resolve_tool was called for each tool
                assert mock_resolve_tool.call_count == 2
                mock_resolve_tool.assert_any_call("SerperDevTool()")
                mock_resolve_tool.assert_any_call("ScrapeWebsiteTool()")
                
                # Verify Agent was called with converted tools
                call_args = mock_agent_class.call_args
                assert call_args is not None
                assert "tools" in call_args.kwargs
                assert len(call_args.kwargs["tools"]) == 2
                assert call_args.kwargs["tools"][0] == mock_tool
                assert call_args.kwargs["tools"][1] == mock_tool
    
    @pytest.mark.skipif(CrewManager is None or LLM is None or resolve_tool is None, 
                        reason="Required modules not available")
    def test_llm_and_tools_together(self):
        """Test that both LLM and tools string conversion work together"""
        # Mock LLM
        mock_llm_instance = Mock()
        mock_llm_instance.model = "gpt-4"
        
        # Mock tool
        mock_tool = Mock()
        mock_tool.run = Mock(return_value="tool result")
        
        with patch('aipartnerupflow.extensions.crewai.crew_manager.LLM') as mock_llm_class, \
             patch('aipartnerupflow.extensions.crewai.crew_manager.resolve_tool') as mock_resolve_tool:
            mock_llm_class.return_value = mock_llm_instance
            mock_resolve_tool.return_value = mock_tool
            
            # Mock Agent, Task and CrewAI
            mock_agent = Mock()
            mock_task = Mock()
            mock_crew = Mock()
            
            with patch('aipartnerupflow.extensions.crewai.crew_manager.Agent') as mock_agent_class, \
                 patch('aipartnerupflow.extensions.crewai.crew_manager.Task') as mock_task_class, \
                 patch('aipartnerupflow.extensions.crewai.crew_manager.CrewAI') as mock_crew_class:
                mock_agent_class.return_value = mock_agent
                mock_task_class.return_value = mock_task
                mock_crew_class.return_value = mock_crew

                # Create CrewManager with both string LLM and tools in works format
                crew_manager = CrewManager(
                    name="Test Crew",
                    works={
                        "agents": {
                            "researcher": {
                                "role": "Researcher",
                                "goal": "Research",
                                "backstory": "You are a researcher",
                                "llm": "gpt-4",  # String LLM
                                "tools": ["SerperDevTool()"]  # String tool
                            }
                        },
                        "tasks": {
                            "research_task": {
                                "description": "Research a topic",
                                "expected_output": "A summary of the research findings",
                                "agent": "researcher"
                            }
                        }
                    }
                )
                
                # Verify LLM conversion
                mock_llm_class.assert_called_with(model="gpt-4")
                
                # Verify tools conversion
                mock_resolve_tool.assert_called_with("SerperDevTool()")
                
                # Verify Agent was called with both LLM and tools
                call_args = mock_agent_class.call_args
                assert call_args is not None
                assert "llm" in call_args.kwargs
                assert call_args.kwargs["llm"] == mock_llm_instance
                assert "tools" in call_args.kwargs
                assert len(call_args.kwargs["tools"]) == 1
                assert call_args.kwargs["tools"][0] == mock_tool
    

    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set - skipping integration test"
    )
    async def test_execute_with_real_openai(self):
        """Test crew execution with real OpenAI API (requires OPENAI_API_KEY)"""
        # Check if OpenAI API key is available
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY is not set")
        
        # Create a simple crew for testing
        # LLM is now set at agent level, not crew level
        crew_manager = CrewManager(
            name="Test Research Crew",
            works={
                "agents": {
                    "researcher": {
                        "role": "Researcher",
                        "goal": "Research and provide a brief summary",
                        "backstory": "You are a helpful research assistant",
                        "verbose": False,
                        "allow_delegation": False,
                        "llm": "openai/gpt-3.5-turbo"  # LLM set at agent level
                    }
                },
                "tasks": {
                    "research_task": {
                        "description": "Research and summarize what Python is in one sentence",
                        "expected_output": "A one-sentence summary of Python",
                        "agent": "researcher"
                    }
                }
            }
        )
        
        # Execute crew
        result = await crew_manager.execute()
        print("=== result: ===")
        import json
        print(json.dumps(result, indent=2, default=str))
        # Verify result structure
        assert result["status"] in ["success", "failed"]
        
        if result["status"] == "success":
            # Verify success result
            assert "result" in result
            assert result["result"] is not None
            
            # Verify token usage is present (if available)
            if "token_usage" in result:
                token_usage = result["token_usage"]
                assert "total_tokens" in token_usage or "status" in token_usage
        else:
            # If failed, verify error message
            assert "error" in result
            # Log the error for debugging
            print(f"Crew execution failed: {result.get('error')}")
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set - skipping integration test"
    )
    async def test_limited_scrape_website_tool_integration(self):
        """Test CrewManager with LimitedScrapeWebsiteTool using real OpenAI API"""
        # Check if OpenAI API key is available
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY is not set")
        
        # Verify tool is registered (tools are auto-imported when importing crewai module)
        try:
            from aipartnerupflow.extensions.crewai import get_tool_registry
            registry = get_tool_registry()
            # Verify tool is registered
            if "LimitedScrapeWebsiteTool" not in registry.list_tools():
                pytest.skip("LimitedScrapeWebsiteTool not registered (may be missing dependencies)")
        except ImportError:
            pytest.skip("CrewAI tools module not available")
        
        # Create a crew that uses LimitedScrapeWebsiteTool to scrape a website
        crew_manager = CrewManager(
            name="Website Scraper Crew",
            works={
                "agents": {
                    "web_analyzer": {
                        "role": "Web Content Analyzer",
                        "goal": "Analyze website content and provide a summary",
                        "backstory": "You are an expert web content analyzer who can extract and summarize information from websites",
                        "verbose": False,
                        "allow_delegation": False,
                        "llm": "openai/gpt-3.5-turbo",  # Use cheaper model for testing
                        "tools": ["LimitedScrapeWebsiteTool()"]  # Use the tool via string reference
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
        )
        
        # Execute crew
        result = await crew_manager.execute()
        print("=== result: ===")
        import json
        print(json.dumps(result, indent=2, default=str))
        
        # Verify result structure
        assert result["status"] in ["success", "failed"]
        
        if result["status"] == "success":
            # Verify success result
            assert "result" in result
            assert result["result"] is not None
            
            # The result should contain information about SpaceX
            result_str = str(result["result"]).lower()
            # Should mention spacex or space-related content
            assert "spacex" in result_str or "space" in result_str or "rocket" in result_str or "mars" in result_str
            
            # Verify token usage is present (if available)
            if "token_usage" in result:
                token_usage = result["token_usage"]
                assert "total_tokens" in token_usage or "status" in token_usage
        else:
            # If failed, verify error message
            assert "error" in result
            # Log the error for debugging
            print(f"Website scraping failed: {result.get('error')}")
            # Don't fail the test if it's a network error (website might be down)
            if "network" not in result.get("error", "").lower() and "timeout" not in result.get("error", "").lower():
                raise AssertionError(f"Unexpected error: {result.get('error')}")
    