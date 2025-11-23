"""
Example task data definitions

This module contains example task definitions that demonstrate various features:
- All tasks are in pending status (ready to be executed via webapp)
- Task trees with parent-child relationships
- Tasks with different priorities
- Tasks with dependencies
- CrewAI task example (requires LLM key)
"""

from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

# Example user ID for demo tasks
EXAMPLE_USER_ID = "example_user"


def get_example_tasks() -> List[Dict[str, Any]]:
    """
    Get example task definitions
    
    Returns:
        List of task dictionaries ready to be created
    """
    now = datetime.now(timezone.utc)
    
    # Root task: System Analysis Project
    root_task = {
        "id": "example_root_001",
        "name": "System Analysis Project",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": None,
        "priority": 1,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "has_children": True,  # Has 3 child tasks: CPU, Memory, Disk
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "all"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Child task 1: CPU Analysis
    cpu_task = {
        "id": "example_cpu_001",
        "name": "CPU Analysis",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": "example_root_001",
        "priority": 1,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "cpu"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Child task 2: Memory Analysis
    memory_task = {
        "id": "example_memory_001",
        "name": "Memory Analysis",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": "example_root_001",
        "priority": 1,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "memory"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Child task 3: Disk Analysis (depends on CPU and Memory)
    disk_task = {
        "id": "example_disk_001",
        "name": "Disk Analysis",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": "example_root_001",
        "priority": 2,
        "dependencies": [
            {"id": "example_cpu_001", "required": True},
            {"id": "example_memory_001", "required": True}
        ],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "disk"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Second root task: CrewAI Example (pending - requires LLM key)
    # Note: LLM key should be provided via request header (X-LLM-API-KEY) or user config API
    # This example shows the structure but won't execute without LLM key
    crewai_task = {
        "id": "example_crewai_001",
        "name": "CrewAI Research Task",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": None,
        "priority": 1,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "crewai_executor"
        },
        "params": {
            "works": {
                "agents": {
                    "researcher": {
                        "role": "Research Analyst",
                        "goal": "Research and analyze the given topic",
                        "backstory": "You are an expert research analyst with years of experience.",
                        "llm": "openai/gpt-4"  # LLM model name, API key from header/config
                    }
                },
                "tasks": {
                    "research": {
                        "description": "Research the topic: {topic}",
                        "agent": "researcher"
                    }
                }
            }
        },
        "inputs": {
            "topic": "Artificial Intelligence"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Third root task: Pending Task
    pending_root = {
        "id": "example_pending_001",
        "name": "Pending System Check",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": None,
        "priority": 3,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "all"
        },
        "created_at": now - timedelta(hours=2)
    }
    
    # Fourth root task: Memory System Check
    in_progress_root = {
        "id": "example_in_progress_001",
        "name": "Memory System Check",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": None,
        "priority": 2,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "memory"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Fifth root task: Task Tree with Multiple Levels
    tree_root = {
        "id": "example_tree_001",
        "name": "Multi-Level Analysis",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": None,
        "priority": 1,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "has_children": True,  # Has 3 child tasks: tree_child_1, tree_child_2, tree_child_3
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "all"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Level 2 child
    tree_child_1 = {
        "id": "example_tree_child_001",
        "name": "Level 2 - CPU Check",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": "example_tree_001",
        "priority": 1,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "cpu"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Level 2 child 2
    tree_child_2 = {
        "id": "example_tree_child_002",
        "name": "Level 2 - Memory Check",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": "example_tree_001",
        "priority": 1,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "memory"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    # Level 3 child (depends on level 2 children)
    tree_child_3 = {
        "id": "example_tree_child_003",
        "name": "Level 3 - Combined Analysis",
        "user_id": EXAMPLE_USER_ID,
        "parent_id": "example_tree_001",
        "priority": 2,
        "dependencies": [
            {"id": "example_tree_child_001", "required": True},
            {"id": "example_tree_child_002", "required": True}
        ],
        "status": "pending",
        "progress": 0.0,
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {
            "resource": "disk"
        },
        "created_at": now - timedelta(hours=1)
    }
    
    return [
        root_task,
        cpu_task,
        memory_task,
        disk_task,
        crewai_task,
        pending_root,
        in_progress_root,
        tree_root,
        tree_child_1,
        tree_child_2,
        tree_child_3,
    ]

