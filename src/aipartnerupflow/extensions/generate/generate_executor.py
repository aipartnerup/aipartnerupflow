"""
Generate Executor

This executor generates valid task tree JSON arrays from natural language
requirements using LLM. The generated tasks are compatible with
TaskCreator.create_task_tree_from_array().
"""

import json
import re
import uuid
from typing import Dict, Any, List, Optional, Set
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.extensions.generate.executor_info import format_executors_for_llm
from aipartnerupflow.extensions.generate.docs_loader import load_relevant_docs_for_requirement
from aipartnerupflow.extensions.generate.llm_client import create_llm_client

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
            
            # Get user_id from task context (via self.user_id property) or fallback to inputs
            # self.user_id property automatically gets from task.user_id if task is available
            user_id = self.user_id or inputs.get("user_id")
            llm_provider = inputs.get("llm_provider")
            model = inputs.get("model")
            temperature = inputs.get("temperature", 0.7)
            max_tokens = inputs.get("max_tokens", 4000)
            
            # Get LLM API key with unified priority order:
            # API context: header -> LLMKeyConfigManager -> env
            # CLI context: params -> LLMKeyConfigManager -> env
            from aipartnerupflow.core.utils.llm_key_context import get_llm_key
            api_key = inputs.get("api_key")  # First check inputs (CLI params)
            if not api_key:
                # Get from unified context (header/config/env)
                api_key = get_llm_key(user_id=user_id, provider=llm_provider, context="auto")
            
            # Create LLM client
            try:
                llm_client = create_llm_client(
                    provider=llm_provider,
                    api_key=api_key,  # Pass API key if available
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
            
            # Post-process tasks: ensure UUID format IDs and correct user_id
            tasks = self._post_process_tasks(tasks, user_id=user_id)
            
            # Validate tasks
            validation_result = self._validate_tasks_array(tasks)
            if not validation_result["valid"]:
                return {
                    "status": "failed",
                    "error": f"Validation failed: {validation_result['error']}",
                    "tasks": tasks  # Return tasks anyway for debugging
                }
            
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
            "   - ALL tasks MUST have 'id' field with UUID format (e.g., '550e8400-e29b-41d4-a716-446655440000')",
            "   - Task IDs must be valid UUIDs (36 characters: 8-4-4-4-12 format)",
            "   - All references (parent_id, dependencies) must use 'id'",
            "   - Generate unique UUIDs for each task using UUID v4 format",
            "",
            "3. Tree structure (CRITICAL):",
            "   - Exactly ONE root task (task with no parent_id and no dependencies)",
            "   - All other tasks MUST have a parent_id to form a single tree",
            "   - If a task depends on multiple tasks, set parent_id to the FIRST dependency",
            "   - For sequential tasks (A → B → C), each task's parent_id should be the previous task",
            "   - All tasks must be reachable from the root via parent_id chain",
            "   - No circular dependencies",
            "",
            "4. Executor matching (CRITICAL):",
            "   - Task 'schemas.method' field MUST exactly match an available executor ID from the extensions registry",
            "   - The 'name' field is a descriptive task name (e.g., 'Get System Info', 'Process Data'), NOT the executor ID",
            "   - Input parameters MUST match the executor's input schema",
            "",
            "=== Task Object Structure ===",
            "{",
            '  "name": "Get System Information",  // REQUIRED: Descriptive task name (human-readable, NOT executor ID)',
            '  "id": "550e8400-e29b-41d4-a716-446655440000",  // REQUIRED: UUID v4 format (36 chars)',
            '  "user_id": "user123",         // REQUIRED: User identifier (use the provided user_id)',
            '  "priority": 1,                // OPTIONAL: 0=urgent, 1=high, 2=normal, 3=low (default: 1)',
            '  "inputs": {                   // OPTIONAL: Executor-specific input parameters',
            '    "resource": "cpu"           // Must match executor input schema',
            '  },',
            '  "schemas": {                  // REQUIRED: Task schemas (must include method field)',
            '    "method": "system_info_executor"  // REQUIRED: Must exactly match executor ID from extensions registry',
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
            "   - Match each step to an appropriate executor from the available executors list",
            "   - Set schemas.method to the executor's ID (e.g., 'system_info_executor', 'command_executor', 'rest_executor')",
            "   - Check executor input schemas to understand required parameters",
            "   - Ensure all required parameters are provided in the inputs field",
            "",
            "4. CONFIGURE tasks:",
            "   - Set a descriptive 'name' field for each task (e.g., 'Get System Info', 'Process Data', 'Send Notification')",
            "   - Set 'schemas.method' to the executor ID (e.g., 'system_info_executor', 'command_executor', 'rest_executor')",
            "   - Set complete, realistic input parameters matching the executor's input schema",
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
            "   - All schemas.method values match available executor IDs from extensions registry",
            "   - All input parameters match executor schemas",
            "   - Each task has a descriptive 'name' field (not executor ID) and correct 'schemas.method' field (executor ID)",
            "",
            "=== Output Format ===",
            "Return ONLY a valid JSON array of task objects.",
            "No markdown code blocks, no explanations, no comments.",
            "The JSON should be directly parseable.",
            "",
            "Example output structure:",
            json.dumps([
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Fetch API Data",
                    "user_id": "user123",
                    "schemas": {"method": "rest_executor"},
                    "inputs": {
                        "url": "https://api.example.com/data",
                        "method": "GET",
                        "headers": {"Accept": "application/json"}
                    },
                    "priority": 1
                    # No parent_id = root task
                },
                {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "Process Data",
                    "user_id": "user123",
                    "schemas": {"method": "command_executor"},
                    "parent_id": "550e8400-e29b-41d4-a716-446655440000",  # REQUIRED: parent_id = first dependency
                    "dependencies": [{"id": "550e8400-e29b-41d4-a716-446655440000", "required": True}],
                    "inputs": {
                        "command": "python process_data.py --input /tmp/api_response.json --output /tmp/processed.json"
                    },
                    "priority": 2
                },
                {
                    "id": "770e8400-e29b-41d4-a716-446655440002",
                    "name": "Notify Completion",
                    "user_id": "user123",
                    "schemas": {"method": "rest_executor"},
                    "parent_id": "660e8400-e29b-41d4-a716-446655440001",  # REQUIRED: parent_id = previous task in chain
                    "dependencies": [{"id": "660e8400-e29b-41d4-a716-446655440001", "required": True}],
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
            "   - Task B.parent_id = '550e8400-e29b-41d4-a716-446655440000' (first dependency's UUID)",
            "   - Task B.dependencies = [{'id': '550e8400-e29b-41d4-a716-446655440000'}, {'id': '660e8400-e29b-41d4-a716-446655440001'}]",
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
    
    def _post_process_tasks(self, tasks: List[Dict[str, Any]], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Post-process generated tasks to ensure correct format
        
        - Ensures all tasks have UUID format IDs
        - Ensures all tasks have correct user_id from BaseTask
        - Ensures all dependencies references use correct UUID IDs
        
        Args:
            tasks: List of task dictionaries from LLM
            user_id: User ID from BaseTask (self.user_id)
            
        Returns:
            Post-processed list of task dictionaries
        """
        # Get user_id from BaseTask if not provided
        if not user_id:
            user_id = self.user_id
            if user_id:
                logger.debug(f"Using user_id '{user_id}' from BaseTask.task.user_id")
            else:
                logger.debug("No user_id available from BaseTask.task.user_id (task.user_id is None)")
        
        # UUID validation regex (UUID v4 format: 8-4-4-4-12)
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
        
        # Step 1: Build task ID mapping (name -> task) for reference lookup
        name_to_task: Dict[str, Dict[str, Any]] = {}
        id_to_task: Dict[str, Dict[str, Any]] = {}
        
        for task in tasks:
            task_name = task.get("name")
            task_id = task.get("id")
            if task_name:
                name_to_task[task_name] = task
            if task_id:
                id_to_task[task_id] = task
        
        # Step 2: Track ID mappings for updating references
        id_mapping: Dict[str, str] = {}  # old_id -> new_uuid
        
        # Step 3: Fix all task IDs to be UUIDs and ensure correct user_id
        for task in tasks:
            # Fix user_id: ALWAYS use BaseTask.user_id (self.user_id) to override any LLM-generated value
            # This ensures generated tasks use the correct user_id from the request context,
            # not hardcoded values like "api_user" or "user123" that LLM might generate
            
            # Determine the correct user_id to use (priority: parameter > self.user_id > None)
            correct_user_id = user_id or self.user_id
            
            if correct_user_id:
                logger.debug(f"Using correct_user_id '{correct_user_id}' for task '{task.get('name')}' (parameter: {user_id}, self.user_id: {self.user_id})")
                # Always override LLM-generated user_id with correct one from BaseTask context
                old_user_id = task.get("user_id")
                if old_user_id != correct_user_id:
                    task["user_id"] = correct_user_id
                    if old_user_id:
                        logger.debug(f"Overrode LLM-generated user_id '{old_user_id}' with actual user_id '{correct_user_id}' for task '{task.get('name')}'")
            else:
                # No user_id available from BaseTask context, set to None
                # Don't keep LLM-generated values like "api_user" or "user123"
                if task.get("user_id"):
                    logger.warning(
                        f"Removed LLM-generated user_id '{task.get('user_id')}' for task '{task.get('name')}' "
                        f"(no user_id in context: parameter={user_id}, self.user_id={self.user_id}). "
                        f"This means the request had no JWT token or verify_token_func is not available."
                    )
                task["user_id"] = None
            
            # Fix task ID: ensure it's a valid UUID
            old_id = task.get("id")
            if old_id:
                # Check if it's a valid UUID
                if not uuid_pattern.match(old_id):
                    # Generate new UUID and track mapping
                    new_id = str(uuid.uuid4())
                    id_mapping[old_id] = new_id
                    task["id"] = new_id
                    logger.debug(f"Generated new UUID for task '{task.get('name')}': {old_id} -> {new_id}")
                # If it's already a valid UUID, keep it
            else:
                # No ID provided, generate one
                new_id = str(uuid.uuid4())
                task["id"] = new_id
                logger.debug(f"Generated UUID for task '{task.get('name')}': {new_id}")
        
        # Step 4: Update all references (parent_id and dependencies) with correct UUIDs
        for task in tasks:
            # Update parent_id
            if "parent_id" in task and task["parent_id"]:
                parent_ref = task["parent_id"]
                # Check if parent_ref needs to be mapped
                if parent_ref in id_mapping:
                    task["parent_id"] = id_mapping[parent_ref]
                # If parent_ref is not a UUID, try to find the task by name and use its ID
                elif not uuid_pattern.match(parent_ref):
                    if parent_ref in name_to_task:
                        task["parent_id"] = name_to_task[parent_ref]["id"]
                        logger.debug(f"Updated parent_id for task '{task.get('name')}': {parent_ref} -> {name_to_task[parent_ref]['id']}")
                    elif parent_ref in id_to_task:
                        # Parent ref exists but was mapped, use the mapped ID
                        mapped_id = id_mapping.get(parent_ref)
                        if mapped_id:
                            task["parent_id"] = mapped_id
                
                # Final validation: ensure parent_id is a valid UUID
                if task["parent_id"] and not uuid_pattern.match(task["parent_id"]):
                    logger.warning(f"Task '{task.get('name')}' has invalid parent_id '{task['parent_id']}', removing it")
                    task.pop("parent_id", None)
            
            # Update dependencies - ensure all dependency IDs are correct UUIDs
            if "dependencies" in task and isinstance(task["dependencies"], list):
                updated_deps = []
                for dep in task["dependencies"]:
                    if isinstance(dep, dict):
                        dep_id = dep.get("id")
                        if dep_id:
                            # Check if dep_id needs to be mapped
                            if dep_id in id_mapping:
                                dep["id"] = id_mapping[dep_id]
                                updated_deps.append(dep)
                            # If dep_id is not a UUID, try to find the task by name and use its ID
                            elif not uuid_pattern.match(dep_id):
                                if dep_id in name_to_task:
                                    dep["id"] = name_to_task[dep_id]["id"]
                                    updated_deps.append(dep)
                                    logger.debug(f"Updated dependency id for task '{task.get('name')}': {dep_id} -> {name_to_task[dep_id]['id']}")
                                elif dep_id in id_to_task:
                                    # Dep ref exists but was mapped, use the mapped ID
                                    mapped_id = id_mapping.get(dep_id)
                                    if mapped_id:
                                        dep["id"] = mapped_id
                                        updated_deps.append(dep)
                                else:
                                    # Invalid dependency reference, skip it
                                    logger.warning(f"Task '{task.get('name')}' has invalid dependency id '{dep_id}', skipping it")
                            else:
                                # Valid UUID, keep it
                                updated_deps.append(dep)
                        else:
                            # No id in dependency, skip it
                            logger.warning(f"Task '{task.get('name')}' has dependency without 'id' field, skipping it")
                    else:
                        # Invalid dependency format, skip it
                        logger.warning(f"Task '{task.get('name')}' has invalid dependency format, skipping it")
                
                # Update dependencies list
                task["dependencies"] = updated_deps
        
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

