"""
Generate Executor

This executor generates valid task tree JSON arrays from natural language
requirements using LLM. The generated tasks are compatible with
TaskCreator.create_task_tree_from_array().
"""

import json
import re
from typing import Dict, Any, List, Optional, Set
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.extensions.generate.executor_info import format_executors_for_llm
from aipartnerupflow.extensions.generate.docs_loader import load_all_docs, load_relevant_docs_for_requirement
from aipartnerupflow.extensions.generate.llm_client import create_llm_client, LLMClient

logger = get_logger(__name__)


@executor_register()
class GenerateExecutor(BaseTask):
    """
    Executor for generating task trees from natural language requirements
    
    This executor uses LLM to generate valid task tree JSON arrays that can be
    used with TaskCreator.create_task_tree_from_array().
    
    Example usage:
        task = await task_manager.task_repository.create_task(
            name="generate_executor",
            user_id="user123",
            inputs={
                "requirement": "Fetch data from API, process it, and save to database",
                "user_id": "user123"
            }
        )
    """
    
    id = "generate_executor"
    name = "Generate Executor"
    description = "Generate task tree JSON arrays from natural language requirements using LLM"
    tags = ["generation", "llm", "task-tree", "automation"]
    examples = [
        "Generate task tree from requirement",
        "Create workflow from natural language",
        "Auto-generate task structure"
    ]
    
    cancelable: bool = False
    
    @property
    def type(self) -> str:
        """Extension type identifier"""
        return "generate"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate task tree JSON array from requirement
        
        Args:
            inputs: Dictionary containing:
                - requirement: Natural language requirement (required)
                - user_id: User ID for generated tasks (optional)
                - llm_provider: LLM provider ("openai" or "anthropic", optional)
                - model: Model name (optional)
                - temperature: LLM temperature (optional, default 0.7)
                - max_tokens: Maximum tokens (optional, default 4000)
        
        Returns:
            Dictionary with:
                - status: "completed" or "failed"
                - tasks: List of task dictionaries (if successful)
                - error: Error message (if failed)
        """
        try:
            requirement = inputs.get("requirement")
            if not requirement:
                return {
                    "status": "failed",
                    "error": "requirement is required in inputs",
                    "tasks": []
                }
            
            user_id = inputs.get("user_id")
            llm_provider = inputs.get("llm_provider")
            model = inputs.get("model")
            temperature = inputs.get("temperature", 0.7)
            max_tokens = inputs.get("max_tokens", 4000)
            api_key = inputs.get("api_key")  # Get API key from inputs (injected by pre-hook)
            
            # Create LLM client
            try:
                llm_client = create_llm_client(
                    provider=llm_provider,
                    api_key=api_key,  # Pass API key if available (from X-LLM-API-KEY header)
                    model=model
                )
            except Exception as e:
                logger.error(f"Failed to create LLM client: {e}")
                return {
                    "status": "failed",
                    "error": f"Failed to create LLM client: {str(e)}",
                    "tasks": []
                }
            
            # Build prompt
            prompt = self._build_llm_prompt(requirement, user_id)
            
            # Generate response
            logger.info(f"Generating task tree for requirement: {requirement[:100]}...")
            try:
                response = await llm_client.generate(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except Exception as e:
                logger.error(f"LLM generation error: {e}")
                return {
                    "status": "failed",
                    "error": f"LLM generation failed: {str(e)}",
                    "tasks": []
                }
            
            # Parse response
            try:
                tasks = self._parse_llm_response(response)
            except Exception as e:
                logger.error(f"Failed to parse LLM response: {e}")
                return {
                    "status": "failed",
                    "error": f"Failed to parse LLM response: {str(e)}",
                    "tasks": []
                }
            
            # Validate tasks
            validation_result = self._validate_tasks_array(tasks)
            if not validation_result["valid"]:
                return {
                    "status": "failed",
                    "error": f"Validation failed: {validation_result['error']}",
                    "tasks": tasks  # Return tasks anyway for debugging
                }
            
            # Set user_id if provided
            if user_id:
                for task in tasks:
                    if "user_id" not in task:
                        task["user_id"] = user_id
            
            logger.info(f"Successfully generated {len(tasks)} tasks")
            return {
                "status": "completed",
                "tasks": tasks,
                "count": len(tasks)
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in generate_executor: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": f"Unexpected error: {str(e)}",
                "tasks": []
            }
    
    def _build_llm_prompt(self, requirement: str, user_id: Optional[str] = None) -> str:
        """
        Build intelligent LLM prompt with context tailored to the requirement
        
        Args:
            requirement: User's natural language requirement
            user_id: Optional user ID
            
        Returns:
            Complete prompt string optimized for the specific requirement
        """
        # Load relevant documentation based on requirement keywords
        docs = load_relevant_docs_for_requirement(requirement, max_chars_per_section=2000)
        
        # Get executor information (limited but relevant)
        executors_info = format_executors_for_llm(max_executors=15, max_schema_props=3)
        
        # Build intelligent, requirement-focused prompt
        prompt_parts = [
            "You are an expert task tree generator for the aipartnerupflow framework.",
            "Your goal is to understand the business requirement and generate a valid, practical task tree JSON array.",
            "",
            "=== Your Task ===",
            "Analyze the requirement below and generate a task tree that:",
            "1. Fulfills the business need described in the requirement",
            "2. Uses appropriate executors from the available list",
            "3. Sets correct dependencies to ensure proper execution order",
            "4. Includes complete, realistic input parameters",
            "5. Follows framework best practices and patterns",
            "",
            "=== Critical Framework Rules ===",
            "⚠️ IMPORTANT: Understand these concepts correctly:",
            "",
            "1. parent_id vs dependencies:",
            "   - parent_id: REQUIRED for tree structure - ensures all tasks form a single tree",
            "   - dependencies: Controls EXECUTION ORDER - tasks wait for dependencies to complete",
            "   - CRITICAL: If a task has dependencies, it MUST have a parent_id (usually the first dependency)",
            "   - Example: Task B depends on Task A → Task B must have parent_id='task_a' AND dependencies=[{'id': 'task_a'}]",
            "",
            "2. Task identification:",
            "   - Either ALL tasks have 'id' field, or NONE do (no mixing)",
            "   - If using 'id', all references (parent_id, dependencies) must use 'id'",
            "   - If not using 'id', references can use 'name'",
            "",
            "3. Tree structure (CRITICAL):",
            "   - Exactly ONE root task (task with no parent_id and no dependencies)",
            "   - All other tasks MUST have a parent_id to form a single tree",
            "   - If a task depends on multiple tasks, set parent_id to the FIRST dependency",
            "   - For sequential tasks (A → B → C), each task's parent_id should be the previous task",
            "   - All tasks must be reachable from the root via parent_id chain",
            "   - No circular dependencies",
            "",
            "4. Executor matching:",
            "   - Task 'name' field MUST exactly match an available executor ID",
            "   - Input parameters MUST match the executor's input schema",
            "",
            "=== Task Object Structure ===",
            "{",
            '  "name": "executor_id",        // REQUIRED: Must match available executor ID exactly',
            '  "id": "task_1",               // OPTIONAL: If used, ALL tasks must have id',
            '  "user_id": "user123",         // OPTIONAL: User identifier',
            '  "priority": 1,                // OPTIONAL: 0=urgent, 1=high, 2=normal, 3=low (default: 1)',
            '  "inputs": {                   // OPTIONAL: Executor-specific input parameters',
            '    "param1": "value1",         // Must match executor input schema',
            '    "param2": "value2"',
            '  },',
            '  "schemas": {                  // OPTIONAL: Task schemas',
            '    "method": "executor_id"      // Usually same as name',
            '  },',
            '  "parent_id": "task_0",        // OPTIONAL: For organization only (like folders)',
            '  "dependencies": [             // OPTIONAL: Controls execution order',
            '    {"id": "task_0", "required": true}  // Task waits for task_0 to complete',
            '  ]',
            "}",
            "",
            "=== Framework Documentation (Relevant to Your Requirement) ===",
            docs[:2500] if len(docs) > 2500 else docs,
            "",
            "=== Available Executors ===",
            executors_info[:3500] if len(executors_info) > 3500 else executors_info,
            "",
            "=== Business Requirement ===",
            requirement,
            "",
            "=== Analysis & Generation Instructions ===",
            "1. UNDERSTAND the requirement:",
            "   - What is the business goal?",
            "   - What steps are needed to achieve it?",
            "   - What data flows between steps?",
            "",
            "2. DESIGN the task tree:",
            "   - Identify the root task (starting point - no parent_id, no dependencies)",
            "   - Map business steps to executor tasks",
            "   - Determine execution order (use dependencies)",
            "   - Set parent_id for ALL non-root tasks to form a single tree:",
            "     * For sequential tasks: each task's parent_id = previous task",
            "     * For tasks with multiple dependencies: parent_id = first dependency",
            "     * For parallel tasks: choose one as root, others as its children",
            "",
            "3. SELECT executors:",
            "   - Match each step to an appropriate executor",
            "   - Check executor input schemas",
            "   - Ensure all required parameters are provided",
            "",
            "4. CONFIGURE tasks:",
            "   - Set complete, realistic input parameters",
            "   - For command_executor: use full commands with arguments (e.g., 'python script.py --input file.json')",
            "   - For rest_executor: use complete URLs and proper HTTP methods",
            "   - Set dependencies to ensure correct execution order",
            "   - Set parent_id for ALL non-root tasks (REQUIRED for tree structure):",
            "     * If task has dependencies, set parent_id to the FIRST dependency",
            "     * For sequential chain: parent_id = previous task in chain",
            "     * This ensures all tasks form a single tree with one root",
            "",
            "5. VALIDATE:",
            "   - Single root task",
            "   - All references valid",
            "   - No circular dependencies",
            "   - All executor names match available executors",
            "   - All input parameters match executor schemas",
            "",
            "=== Output Format ===",
            "Return ONLY a valid JSON array of task objects.",
            "No markdown code blocks, no explanations, no comments.",
            "The JSON should be directly parseable.",
            "",
            "Example output structure:",
            json.dumps([
                {
                    "id": "task_1",
                    "name": "rest_executor",
                    "inputs": {
                        "url": "https://api.example.com/data",
                        "method": "GET",
                        "headers": {"Accept": "application/json"}
                    },
                    "priority": 1
                    # No parent_id = root task
                },
                {
                    "id": "task_2",
                    "name": "command_executor",
                    "parent_id": "task_1",  # REQUIRED: parent_id = first dependency
                    "dependencies": [{"id": "task_1", "required": True}],
                    "inputs": {
                        "command": "python process_data.py --input /tmp/api_response.json --output /tmp/processed.json"
                    },
                    "priority": 2
                },
                {
                    "id": "task_3",
                    "name": "rest_executor",
                    "parent_id": "task_2",  # REQUIRED: parent_id = previous task in chain
                    "dependencies": [{"id": "task_2", "required": True}],
                    "inputs": {
                        "url": "https://api.example.com/notify",
                        "method": "POST",
                        "data": {"status": "completed"}
                    },
                    "priority": 2
                }
            ], indent=2),
            "",
            "=== CRITICAL: parent_id Rules ===",
            "1. Root task: NO parent_id (only one root task allowed)",
            "2. Sequential tasks: parent_id = previous task in the chain",
            "3. Tasks with dependencies: parent_id = FIRST dependency",
            "4. Parallel tasks: Choose one as root, others have parent_id = root",
            "5. Example: If Task B depends on [Task A, Task C], then:",
            "   - Task B.parent_id = 'task_a' (first dependency)",
            "   - Task B.dependencies = [{'id': 'task_a'}, {'id': 'task_c'}]",
            "",
        ]
        
        if user_id:
            prompt_parts.append("")
            prompt_parts.append(f"Note: Use user_id='{user_id}' for all generated tasks.")
        
        prompt_parts.append("")
        prompt_parts.append("=== Generate Task Tree ===")
        prompt_parts.append("Now generate the task tree JSON array based on the requirement above.")
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM JSON response
        
        Args:
            response: LLM response text
            
        Returns:
            List of task dictionaries
            
        Raises:
            ValueError: If response cannot be parsed
        """
        # Try to extract JSON from response (might be wrapped in markdown code blocks)
        response = response.strip()
        
        # Remove markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
        
        # Parse JSON
        try:
            tasks = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}. Response: {response[:500]}")
        
        # Validate it's a list
        if not isinstance(tasks, list):
            raise ValueError(f"LLM response is not a list, got {type(tasks)}")
        
        # Validate each task is a dict
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError(f"Task at index {i} is not a dictionary, got {type(task)}")
        
        return tasks
    
    def _validate_tasks_array(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate generated tasks array against TaskCreator requirements
        
        Args:
            tasks: List of task dictionaries
            
        Returns:
            Dictionary with:
                - valid: bool
                - error: str (if invalid)
        """
        if not tasks:
            return {"valid": False, "error": "Tasks array is empty"}
        
        # Check all tasks have 'name' field
        for i, task in enumerate(tasks):
            if "name" not in task:
                return {"valid": False, "error": f"Task at index {i} is missing 'name' field"}
            if not task["name"]:
                return {"valid": False, "error": f"Task at index {i} has empty 'name' field"}
        
        # Check id consistency (either all have id or none do)
        tasks_with_id = sum(1 for task in tasks if "id" in task)
        tasks_without_id = len(tasks) - tasks_with_id
        
        if tasks_with_id > 0 and tasks_without_id > 0:
            return {
                "valid": False,
                "error": "Mixed mode not supported: either all tasks must have 'id', or all tasks must not have 'id'"
            }
        
        # Build identifier sets
        if tasks_with_id > 0:
            # Use id for references
            identifiers: Set[str] = {task["id"] for task in tasks if "id" in task}
            identifier_to_task = {task["id"]: task for task in tasks if "id" in task}
        else:
            # Use name for references
            identifiers = {task["name"] for task in tasks}
            identifier_to_task = {task["name"]: task for task in tasks}
        
        # Check for duplicate identifiers
        if len(identifiers) < len(tasks):
            return {"valid": False, "error": "Duplicate task identifiers found"}
        
        # Validate parent_id references
        for i, task in enumerate(tasks):
            parent_id = task.get("parent_id")
            if parent_id:
                if parent_id not in identifiers:
                    return {
                        "valid": False,
                        "error": f"Task '{task.get('name', i)}' has parent_id '{parent_id}' which is not in the tasks array"
                    }
        
        # Validate dependency references
        for i, task in enumerate(tasks):
            dependencies = task.get("dependencies")
            if dependencies:
                if not isinstance(dependencies, list):
                    return {
                        "valid": False,
                        "error": f"Task '{task.get('name', i)}' has invalid dependencies (must be a list)"
                    }
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_ref = dep.get("id") or dep.get("name")
                        if dep_ref and dep_ref not in identifiers:
                            return {
                                "valid": False,
                                "error": f"Task '{task.get('name', i)}' has dependency '{dep_ref}' which is not in the tasks array"
                            }
                    elif isinstance(dep, str):
                        if dep not in identifiers:
                            return {
                                "valid": False,
                                "error": f"Task '{task.get('name', i)}' has dependency '{dep}' which is not in the tasks array"
                            }
        
        # Check for single root task
        root_tasks = [task for task in tasks if not task.get("parent_id")]
        if len(root_tasks) == 0:
            return {"valid": False, "error": "No root task found (task with no parent_id)"}
        if len(root_tasks) > 1:
            root_task_names = [task.get('name', 'unknown') for task in root_tasks]
            return {
                "valid": False,
                "error": (
                    f"Multiple root tasks found: {root_task_names}. "
                    f"Only one root task is allowed. "
                    f"Fix: Set parent_id for all non-root tasks. "
                    f"For sequential tasks, set parent_id to the previous task. "
                    f"For tasks with dependencies, set parent_id to the first dependency. "
                    f"For parallel tasks, choose one as root and set others' parent_id to the root."
                )
            }
        
        # Check for circular dependencies (simple check - all tasks reachable from root)
        if tasks_with_id > 0:
            root_id = root_tasks[0]["id"]
            reachable = {root_id}
            
            def collect_reachable(current_id: str):
                for task in tasks:
                    if task.get("parent_id") == current_id:
                        task_id = task["id"]
                        if task_id not in reachable:
                            reachable.add(task_id)
                            collect_reachable(task_id)
            
            collect_reachable(root_id)
            
            all_ids = {task["id"] for task in tasks}
            unreachable = all_ids - reachable
            if unreachable:
                return {
                    "valid": False,
                    "error": f"Tasks not reachable from root: {[identifier_to_task[id].get('name', id) for id in unreachable]}"
                }
        
        return {"valid": True, "error": None}
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo generated task tree"""
        requirement = inputs.get("requirement", "Demo requirement")
        user_id = inputs.get("user_id", "demo_user")
        
        # Return a simple demo task tree based on requirement
        demo_tasks = [
            {
                "id": "demo-task-1",
                "name": "demo_task_1",
                "user_id": user_id,
                "schemas": {"method": "system_info_executor"},
                "inputs": {"resource": "cpu"}
            },
            {
                "id": "demo-task-2",
                "name": "demo_task_2",
                "user_id": user_id,
                "schemas": {"method": "system_info_executor"},
                "inputs": {"resource": "memory"},
                "dependencies": [{"id": "demo-task-1", "required": True}]
            }
        ]
        
        return {
            "status": "completed",
            "tasks": demo_tasks,
            "requirement": requirement,
            "task_count": len(demo_tasks),
            "_demo_sleep": 1.5  # Simulate LLM generation time (longer for realistic demo)
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "requirement": {
                    "type": "string",
                    "description": "Natural language requirement describing the task tree to generate"
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID for generated tasks (optional)"
                },
                "llm_provider": {
                    "type": "string",
                    "enum": ["openai", "anthropic"],
                    "description": "LLM provider to use (defaults to OPENAI_API_KEY or AIPARTNERUPFLOW_LLM_PROVIDER env var)"
                },
                "model": {
                    "type": "string",
                    "description": "LLM model name (optional, uses provider default)"
                },
                "temperature": {
                    "type": "number",
                    "description": "LLM temperature (default: 0.7)",
                    "default": 0.7
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens for LLM response (default: 4000)",
                    "default": 4000
                }
            },
            "required": ["requirement"]
        }

