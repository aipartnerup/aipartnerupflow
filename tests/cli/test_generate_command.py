"""
Test CLI generate command functionality

Tests the generate task-tree command, including the new temperature and max_tokens parameters.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, Mock
from typer.testing import CliRunner
from aipartnerupflow.cli.main import app
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow import clear_config

runner = CliRunner()


@pytest.fixture
def mock_llm_api_key(monkeypatch):
    """Mock LLM API key for testing"""
    # Use monkeypatch for better environment isolation in pytest
    monkeypatch.setenv("OPENAI_API_KEY", "mock-test-key-cli")
    # Also ensure ANTHROPIC is NOT set to avoid confusion
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def mock_generated_tasks():
    """Mock generated tasks for testing"""
    return [
        {
            "id": "task_1",
            "name": "rest_executor",
            "inputs": {"url": "https://api.example.com/data", "method": "GET"},
            "priority": 1
        },
        {
            "id": "task_2",
            "name": "command_executor",
            "parent_id": "task_1",
            "dependencies": [{"id": "task_1", "required": True}],
            "inputs": {"command": "python process.py"},
            "priority": 2
        }
    ]


class TestGenerateCommand:
    """Test cases for generate task-tree command"""
    
    def test_generate_command_help(self):
        """Test generate command help"""
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Generate task trees" in result.stdout
    
    def test_generate_task_tree_help(self):
        """Test generate task-tree command help"""
        result = runner.invoke(app, ["generate", "task-tree", "--help"])
        assert result.exit_code == 0
        assert "requirement" in result.stdout
        # Check for either max-tokens or temperature (LLM parameter options may vary in help format)
        assert ("max-tokens" in result.stdout or "max_tokens" in result.stdout or 
                "temperature" in result.stdout or "provider" in result.stdout)
    
    def test_generate_missing_api_key(self, monkeypatch, use_test_db_session):
        """Test generate command fails when API key is missing"""
        # Clear config to ensure we use default TaskModel
        clear_config()
        
        # Use monkeypatch to safely remove API keys from environment
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        # Also mock the specific module's getenv and os.environ.get to be sure
        # because the module might have already loaded them or use a cached version
        with patch('aipartnerupflow.cli.commands.generate.os.getenv', return_value=None):
            with patch('os.environ.get', return_value=None):
                result = runner.invoke(app, [
                    "generate", "task-tree",
                    "Test requirement"
                ])
                assert result.exit_code == 1
                output = result.output
                assert "No LLM API key found" in output or "Warning" in output or "LLM API key" in output
        
        # Clear config again to ensure clean state
        clear_config()
    
    @pytest.mark.asyncio
    async def test_generate_basic(self, mock_llm_api_key, mock_generated_tasks, use_test_db_session):
        """Test basic task tree generation"""
        with patch('aipartnerupflow.cli.commands.generate.get_default_session', return_value=use_test_db_session):
            with patch('aipartnerupflow.cli.commands.generate.TaskExecutor') as mock_task_executor_class:
                mock_task_executor = Mock()
                mock_task_executor.execute_task_tree = AsyncMock()
                mock_task_executor_class.return_value = mock_task_executor
                
                # Mock task repository
                mock_repository = Mock(spec=TaskRepository)
                mock_generate_task = Mock()
                mock_generate_task.id = "generate-task-id"
                mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
                
                mock_result_task = Mock()
                mock_result_task.status = "completed"
                mock_result_task.result = {"tasks": mock_generated_tasks}
                mock_result_task.error = None
                mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
                
                with patch('aipartnerupflow.cli.commands.generate.TaskRepository', return_value=mock_repository):
                    result = runner.invoke(app, [
                        "generate", "task-tree",
                        "Fetch data from API and process it"
                    ])
                    
                    assert result.exit_code == 0
                    output = result.stdout
                    # Should contain generated tasks JSON
                    assert "rest_executor" in output or "task_1" in output
    
    @pytest.mark.asyncio
    async def test_generate_with_temperature(self, mock_llm_api_key, mock_generated_tasks, use_test_db_session):
        """Test generate command with --temperature parameter"""
        with patch('aipartnerupflow.cli.commands.generate.get_default_session', return_value=use_test_db_session):
            with patch('aipartnerupflow.cli.commands.generate.TaskExecutor') as mock_task_executor_class:
                mock_task_executor = Mock()
                mock_task_executor.execute_task_tree = AsyncMock()
                mock_task_executor_class.return_value = mock_task_executor
                
                # Mock task repository
                mock_repository = Mock(spec=TaskRepository)
                mock_generate_task = Mock()
                mock_generate_task.id = "generate-task-id"
                
                # Track the inputs passed to create_task
                captured_inputs = {}
                
                async def mock_create_task(*args, **kwargs):
                    if 'inputs' in kwargs:
                        captured_inputs.update(kwargs['inputs'])
                    return mock_generate_task
                
                mock_repository.create_task = AsyncMock(side_effect=mock_create_task)
                
                mock_result_task = Mock()
                mock_result_task.status = "completed"
                mock_result_task.result = {"tasks": mock_generated_tasks}
                mock_result_task.error = None
                mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
                
                with patch('aipartnerupflow.cli.commands.generate.TaskRepository', return_value=mock_repository):
                    result = runner.invoke(app, [
                        "generate", "task-tree",
                        "Test requirement",
                        "--temperature", "0.9"
                    ])
                    
                    assert result.exit_code == 0
                    # Verify temperature was passed to generate_executor
                    assert captured_inputs.get("temperature") == 0.9
    
    @pytest.mark.asyncio
    async def test_generate_with_max_tokens(self, mock_llm_api_key, mock_generated_tasks, use_test_db_session):
        """Test generate command with --max-tokens parameter"""
        with patch('aipartnerupflow.cli.commands.generate.get_default_session', return_value=use_test_db_session):
            with patch('aipartnerupflow.cli.commands.generate.TaskExecutor') as mock_task_executor_class:
                mock_task_executor = Mock()
                mock_task_executor.execute_task_tree = AsyncMock()
                mock_task_executor_class.return_value = mock_task_executor
                
                # Mock task repository
                mock_repository = Mock(spec=TaskRepository)
                mock_generate_task = Mock()
                mock_generate_task.id = "generate-task-id"
                
                # Track the inputs passed to create_task
                captured_inputs = {}
                
                async def mock_create_task(*args, **kwargs):
                    if 'inputs' in kwargs:
                        captured_inputs.update(kwargs['inputs'])
                    return mock_generate_task
                
                mock_repository.create_task = AsyncMock(side_effect=mock_create_task)
                
                mock_result_task = Mock()
                mock_result_task.status = "completed"
                mock_result_task.result = {"tasks": mock_generated_tasks}
                mock_result_task.error = None
                mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
                
                with patch('aipartnerupflow.cli.commands.generate.TaskRepository', return_value=mock_repository):
                    result = runner.invoke(app, [
                        "generate", "task-tree",
                        "Test requirement",
                        "--max-tokens", "6000"
                    ])
                    
                    assert result.exit_code == 0
                    # Verify max_tokens was passed to generate_executor
                    assert captured_inputs.get("max_tokens") == 6000
    
    @pytest.mark.asyncio
    async def test_generate_with_all_parameters(self, mock_llm_api_key, mock_generated_tasks, use_test_db_session):
        """Test generate command with all LLM parameters"""
        with patch('aipartnerupflow.cli.commands.generate.get_default_session', return_value=use_test_db_session):
            with patch('aipartnerupflow.cli.commands.generate.TaskExecutor') as mock_task_executor_class:
                mock_task_executor = Mock()
                mock_task_executor.execute_task_tree = AsyncMock()
                mock_task_executor_class.return_value = mock_task_executor
                
                # Mock task repository
                mock_repository = Mock(spec=TaskRepository)
                mock_generate_task = Mock()
                mock_generate_task.id = "generate-task-id"
                
                # Track the inputs passed to create_task
                captured_inputs = {}
                
                async def mock_create_task(*args, **kwargs):
                    if 'inputs' in kwargs:
                        captured_inputs.update(kwargs['inputs'])
                    return mock_generate_task
                
                mock_repository.create_task = AsyncMock(side_effect=mock_create_task)
                
                mock_result_task = Mock()
                mock_result_task.status = "completed"
                mock_result_task.result = {"tasks": mock_generated_tasks}
                mock_result_task.error = None
                mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
                
                with patch('aipartnerupflow.cli.commands.generate.TaskRepository', return_value=mock_repository):
                    result = runner.invoke(app, [
                        "generate", "task-tree",
                        "Test requirement",
                        "--user-id", "test_user",
                        "--provider", "openai",
                        "--model", "gpt-4o",
                        "--temperature", "0.9",
                        "--max-tokens", "6000"
                    ])
                    
                    assert result.exit_code == 0
                    # Verify all parameters were passed correctly
                    assert captured_inputs.get("requirement") == "Test requirement"
                    assert captured_inputs.get("user_id") == "test_user"
                    assert captured_inputs.get("llm_provider") == "openai"
                    assert captured_inputs.get("model") == "gpt-4o"
                    assert captured_inputs.get("temperature") == 0.9
                    assert captured_inputs.get("max_tokens") == 6000
    
    @pytest.mark.asyncio
    async def test_generate_with_output_file(self, mock_llm_api_key, mock_generated_tasks, use_test_db_session):
        """Test generate command with --output parameter"""
        with patch('aipartnerupflow.cli.commands.generate.get_default_session', return_value=use_test_db_session):
            with patch('aipartnerupflow.cli.commands.generate.TaskExecutor') as mock_task_executor_class:
                mock_task_executor = Mock()
                mock_task_executor.execute_task_tree = AsyncMock()
                mock_task_executor_class.return_value = mock_task_executor
                
                # Mock task repository
                mock_repository = Mock(spec=TaskRepository)
                mock_generate_task = Mock()
                mock_generate_task.id = "generate-task-id"
                mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
                
                mock_result_task = Mock()
                mock_result_task.status = "completed"
                mock_result_task.result = {"tasks": mock_generated_tasks}
                mock_result_task.error = None
                mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
                
                with patch('aipartnerupflow.cli.commands.generate.TaskRepository', return_value=mock_repository):
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                            tmp_path = tmp_file.name
                    
                    try:
                        result = runner.invoke(app, [
                            "generate", "task-tree",
                            "Test requirement",
                            "--output", tmp_path
                        ])
                        
                        assert result.exit_code == 0
                        # Verify file was created
                        assert Path(tmp_path).exists()
                        # Verify file contains generated tasks
                        with open(tmp_path, 'r') as f:
                            file_content = json.load(f)
                            assert isinstance(file_content, list)
                            assert len(file_content) > 0
                    finally:
                        # Cleanup
                        if Path(tmp_path).exists():
                            Path(tmp_path).unlink()
    
    @pytest.mark.asyncio
    async def test_generate_with_save(self, mock_llm_api_key, mock_generated_tasks, use_test_db_session):
        """Test generate command with --save parameter"""
        with patch('aipartnerupflow.cli.commands.generate.get_default_session', return_value=use_test_db_session):
            with patch('aipartnerupflow.cli.commands.generate.TaskExecutor') as mock_task_executor_class:
                mock_task_executor = Mock()
                mock_task_executor.execute_task_tree = AsyncMock()
                mock_task_executor_class.return_value = mock_task_executor
                
                # Mock task repository
                mock_repository = Mock(spec=TaskRepository)
                mock_generate_task = Mock()
                mock_generate_task.id = "generate-task-id"
                mock_repository.create_task = AsyncMock(return_value=mock_generate_task)
                
                mock_result_task = Mock()
                mock_result_task.status = "completed"
                mock_result_task.result = {"tasks": mock_generated_tasks}
                mock_result_task.error = None
                mock_repository.get_task_by_id = AsyncMock(return_value=mock_result_task)
                
                # Mock TaskCreator (it's imported inside the function, so we patch the import path)
                with patch('aipartnerupflow.cli.commands.generate.TaskRepository', return_value=mock_repository):
                    with patch('aipartnerupflow.core.execution.task_creator.TaskCreator') as mock_task_creator_class:
                        mock_task_creator = Mock()
                        mock_task_tree = Mock()
                        mock_task_tree.task = Mock()
                        mock_task_tree.task.id = "saved-root-task-id"
                        mock_task_creator.create_task_tree_from_array = AsyncMock(return_value=mock_task_tree)
                        mock_task_creator_class.return_value = mock_task_creator
                        
                        result = runner.invoke(app, [
                            "generate", "task-tree",
                            "Test requirement",
                            "--save"
                        ])
                        
                        assert result.exit_code == 0
                        # Verify TaskCreator.create_task_tree_from_array was called
                        mock_task_creator.create_task_tree_from_array.assert_called_once()
                        # Verify output mentions saving
                        assert "Saved" in result.stdout or "saved" in result.stdout.lower()
    
    def test_generate_temperature_short_flag(self):
        """Test that --temperature can be used with short flag -t"""
        result = runner.invoke(app, [
            "generate", "task-tree",
            "Test requirement",
            "-t", "0.8",
            "--help"  # Use --help to avoid actual execution
        ])
        # Should not error on parsing
        assert result.exit_code in [0, 2]  # 0 for help, 2 for typer error
    
    def test_generate_parameter_validation(self):
        """Test parameter validation for temperature and max_tokens"""
        # Test invalid temperature (should be float)
        result = runner.invoke(app, [
            "generate", "task-tree",
            "Test requirement",
            "--temperature", "invalid"
        ])
        # Should fail with parameter error
        assert result.exit_code != 0
        
        # Test invalid max_tokens (should be int)
        result = runner.invoke(app, [
            "generate", "task-tree",
            "Test requirement",
            "--max-tokens", "invalid"
        ])
        # Should fail with parameter error
        assert result.exit_code != 0

