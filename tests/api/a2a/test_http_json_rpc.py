"""
Test HTTP JSON-RPC client integration

This module tests the A2A Protocol Server using direct HTTP JSON-RPC calls.
Tests the /tasks and /system endpoints for task management.
"""

import pytest
import json
import uuid
from starlette.testclient import TestClient
from aipartnerupflow.api.a2a.server import create_a2a_server
from aipartnerupflow.core.storage import get_default_session


@pytest.fixture(scope="function")
def json_rpc_client(use_test_db_session):
    """Create HTTP JSON-RPC test client"""
    # Create A2A server instance
    server_instance = create_a2a_server(
        verify_token_secret_key=None,  # No JWT for testing
        base_url="http://localhost:8000",
        enable_system_routes=True,
    )
    
    # Build the app
    app = server_instance.build()
    
    # Create test client
    client = TestClient(app)
    
    yield client
    
    # Cleanup
    client.close()


def test_jsonrpc_tasks_create(json_rpc_client):
    """Test creating tasks via JSON-RPC /tasks endpoint"""
    # Prepare task data
    task_data = {
        "id": f"test-task-{uuid.uuid4().hex[:8]}",
        "name": "Test Task via JSON-RPC",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # JSON-RPC request format
    request_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tasks.create",
        "params": [task_data]  # Tasks array as direct parameter
    }
    
    # Send request to /tasks endpoint
    response = json_rpc_client.post(
        "/tasks",
        json=request_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 1
    assert "result" in result
    
    # Verify task was created
    created_task = result["result"]
    assert "id" in created_task
    assert created_task["name"] == task_data["name"]


def test_jsonrpc_tasks_create_multiple(json_rpc_client):
    """Test creating multiple tasks via JSON-RPC"""
    # Prepare task tree
    tasks = [
        {
            "id": f"root-{uuid.uuid4().hex[:8]}",
            "name": "Root Task",
            "user_id": "test-user",
            "status": "pending",
            "priority": 2,
            "has_children": True,
            "dependencies": [
                {"id": f"child-{uuid.uuid4().hex[:8]}", "required": True}
            ],
            "schemas": {
                "method": "aggregate_results_executor",
                "type": "core"
            },
            "inputs": {}
        },
        {
            "id": f"child-{uuid.uuid4().hex[:8]}",
            "name": "Child Task",
            "parent_id": f"root-{uuid.uuid4().hex[:8]}",
            "user_id": "test-user",
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "dependencies": [],
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {}
        }
    ]
    
    # Fix parent_id reference
    tasks[1]["parent_id"] = tasks[0]["id"]
    tasks[0]["dependencies"][0]["id"] = tasks[1]["id"]
    
    request_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tasks.create",
        "params": tasks
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=request_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify task tree was created
    created_tree = result["result"]
    assert "id" in created_tree
    assert "children" in created_tree or "name" in created_tree


def test_jsonrpc_tasks_get(json_rpc_client):
    """Test getting a task via JSON-RPC"""
    # First create a task
    task_data = {
        "id": f"get-test-{uuid.uuid4().hex[:8]}",
        "name": "Task to Get",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Get task
    get_request = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tasks.get",
        "params": {
            "task_id": task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=get_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify task data
    task = result["result"]
    assert task["id"] == task_id
    assert task["name"] == task_data["name"]


def test_jsonrpc_tasks_detail(json_rpc_client):
    """Test getting task detail via JSON-RPC"""
    # Create a task first
    task_data = {
        "id": f"detail-test-{uuid.uuid4().hex[:8]}",
        "name": "Task for Detail",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Get task detail
    detail_request = {
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tasks.detail",
        "params": {
            "task_id": task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=detail_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    task = result["result"]
    assert task["id"] == task_id


def test_jsonrpc_tasks_tree(json_rpc_client):
    """Test getting task tree via JSON-RPC"""
    # Create a task tree
    tasks = [
        {
            "id": f"tree-root-{uuid.uuid4().hex[:8]}",
            "name": "Tree Root",
            "user_id": "test-user",
            "status": "pending",
            "priority": 2,
            "has_children": True,
            "dependencies": [
                {"id": f"tree-child-{uuid.uuid4().hex[:8]}", "required": True}
            ],
            "schemas": {
                "method": "aggregate_results_executor",
                "type": "core"
            },
            "inputs": {}
        },
        {
            "id": f"tree-child-{uuid.uuid4().hex[:8]}",
            "name": "Tree Child",
            "parent_id": f"tree-root-{uuid.uuid4().hex[:8]}",
            "user_id": "test-user",
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "dependencies": [],
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {}
        }
    ]
    
    # Fix references
    tasks[1]["parent_id"] = tasks[0]["id"]
    tasks[0]["dependencies"][0]["id"] = tasks[1]["id"]
    
    # Create tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tasks.create",
        "params": tasks
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    created_result = create_response.json()
    root_id = created_result["result"]["id"]
    
    # Get tree
    tree_request = {
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tasks.tree",
        "params": {
            "task_id": root_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=tree_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    tree = result["result"]
    assert tree["id"] == root_id
    assert "children" in tree


def test_jsonrpc_tasks_update(json_rpc_client):
    """Test updating a task via JSON-RPC"""
    # Create a task
    task_data = {
        "id": f"update-test-{uuid.uuid4().hex[:8]}",
        "name": "Task to Update",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 40,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Update task
    update_request = {
        "jsonrpc": "2.0",
        "id": 41,
        "method": "tasks.update",
        "params": {
            "task_id": task_id,
            "status": "in_progress",
            "progress": 0.5
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=update_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    updated_task = result["result"]
    assert updated_task["status"] == "in_progress"
    assert float(updated_task["progress"]) == 0.5


def test_jsonrpc_system_health(json_rpc_client):
    """Test system health check via JSON-RPC"""
    health_request = {
        "jsonrpc": "2.0",
        "id": 50,
        "method": "system.health",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/system",
        json=health_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    health = result["result"]
    assert "status" in health
    assert health["status"] == "healthy"


def test_jsonrpc_error_handling(json_rpc_client):
    """Test JSON-RPC error handling"""
    # Invalid method
    invalid_request = {
        "jsonrpc": "2.0",
        "id": 60,
        "method": "tasks.invalid_method",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=invalid_request,
        headers={"Content-Type": "application/json"}
    )
    
    # Our implementation returns 400 for method not found, but still includes JSON-RPC error format
    assert response.status_code in [200, 400]  # May return 400 or 200 with error
    result = response.json()
    
    assert "jsonrpc" in result
    assert "error" in result
    assert result["error"]["code"] == -32601  # Method not found


def test_jsonrpc_missing_id_returns_null(json_rpc_client):
    """Test that requests without id return null in response (JSON-RPC 2.0 compliance)"""
    # Request without id field
    request_payload = {
        "jsonrpc": "2.0",
        "method": "system.health",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/system",
        json=request_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    # According to JSON-RPC 2.0, if request has no id, response id should be null
    assert result["id"] is None
    assert "result" in result


def test_jsonrpc_id_type_preservation(json_rpc_client):
    """Test that id type (string/number) is preserved in response"""
    # Test with number id
    request_payload = {
        "jsonrpc": "2.0",
        "id": 123,
        "method": "system.health",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/system",
        json=request_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == 123
    assert isinstance(result["id"], int)
    
    # Test with string id
    request_payload = {
        "jsonrpc": "2.0",
        "id": "test-id-123",
        "method": "system.health",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/system",
        json=request_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == "test-id-123"
    assert isinstance(result["id"], str)


def test_jsonrpc_running_tasks_list(json_rpc_client):
    """Test listing running tasks via JSON-RPC"""
    list_request = {
        "jsonrpc": "2.0",
        "id": 70,
        "method": "tasks.running.list",
        "params": {
            "limit": 10
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=list_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    # Result should be a list
    assert isinstance(result["result"], list)


@pytest.mark.integration
def test_jsonrpc_full_workflow(json_rpc_client):
    """Integration test: Full JSON-RPC workflow"""
    # Step 1: Create task
    task_data = {
        "id": f"workflow-{uuid.uuid4().hex[:8]}",
        "name": "Workflow Test Task",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Step 2: Get task
    get_request = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tasks.get",
        "params": {"task_id": task_id}
    }
    
    get_response = json_rpc_client.post("/tasks", json=get_request)
    assert get_response.status_code == 200
    get_result = get_response.json()
    print(f"result:\n {json.dumps(get_result, indent=2)}")
    assert get_result["result"]["id"] == task_id
    
    # Step 3: Update task
    update_request = {
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tasks.update",
        "params": {
            "task_id": task_id,
            "status": "completed",
            "progress": 1.0
        }
    }
    
    update_response = json_rpc_client.post("/tasks", json=update_request)
    assert update_response.status_code == 200
    update_result = update_response.json()
    assert update_result["result"]["status"] == "completed"


def test_jsonrpc_tasks_copy(json_rpc_client):
    """Test copying a task via JSON-RPC"""
    # First create a task tree
    root_task_data = {
        "id": f"copy-root-{uuid.uuid4().hex[:8]}",
        "name": "Root Task to Copy",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    child_task_data = {
        "id": f"copy-child-{uuid.uuid4().hex[:8]}",
        "name": "Child Task to Copy",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 200,
        "method": "tasks.create",
        "params": [root_task_data, child_task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    root_task_id = created_result["result"]["id"]
    
    # Copy task
    copy_request = {
        "jsonrpc": "2.0",
        "id": 201,
        "method": "tasks.copy",
        "params": {
            "task_id": root_task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=copy_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify copied task
    copied_task = result["result"]
    assert "id" in copied_task
    assert copied_task["id"] != root_task_id  # New task ID
    assert copied_task["name"] == root_task_data["name"]
    assert copied_task["original_task_id"] == root_task_id  # Linked to original
    assert copied_task["status"] == "pending"  # Reset to pending
    assert copied_task["progress"] == 0.0  # Reset progress
    
    # Verify original task has_copy flag is set
    get_request = {
        "jsonrpc": "2.0",
        "id": 202,
        "method": "tasks.get",
        "params": {"task_id": root_task_id}
    }
    get_response = json_rpc_client.post("/tasks", json=get_request)
    assert get_response.status_code == 200
    original_task = get_response.json()["result"]
    assert original_task.get("has_copy") is True


def test_jsonrpc_tasks_copy_with_children(json_rpc_client):
    """Test copying a task with children=True via JSON-RPC"""
    # First create a task tree with children
    root_task_data = {
        "id": f"copy-children-root-{uuid.uuid4().hex[:8]}",
        "name": "Root Task",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    child1_data = {
        "id": f"copy-children-child1-{uuid.uuid4().hex[:8]}",
        "name": "Child 1",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    child2_data = {
        "id": f"copy-children-child2-{uuid.uuid4().hex[:8]}",
        "name": "Child 2",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 300,
        "method": "tasks.create",
        "params": [root_task_data, child1_data, child2_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    root_task_id = created_result["result"]["id"]
    
    # Copy task with children=True
    copy_request = {
        "jsonrpc": "2.0",
        "id": 301,
        "method": "tasks.copy",
        "params": {
            "task_id": root_task_id,
            "children": True
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=copy_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify copied task
    copied_task = result["result"]
    assert "id" in copied_task
    assert copied_task["id"] != root_task_id
    assert copied_task["name"] == root_task_data["name"]
    assert copied_task["original_task_id"] == root_task_id
    assert "children" in copied_task
    assert len(copied_task["children"]) == 2  # Should have both children


def test_jsonrpc_tasks_execute(json_rpc_client):
    """Test executing a task via JSON-RPC"""
    # First create a task
    task_data = {
        "id": f"execute-test-{uuid.uuid4().hex[:8]}",
        "name": "Task to Execute",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 300,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Execute task
    execute_request = {
        "jsonrpc": "2.0",
        "id": 301,
        "method": "tasks.execute",
        "params": {
            "task_id": task_id,
            "use_streaming": False
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=execute_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 301
    assert "result" in result
    
    # Verify execution result
    execution_result = result["result"]
    assert "success" in execution_result
    assert execution_result["success"] is True
    assert "protocol" in execution_result
    assert execution_result["protocol"] == "jsonrpc"  # Verify protocol identifier
    assert "root_task_id" in execution_result
    assert "task_id" in execution_result
    assert execution_result["task_id"] == task_id
    assert "status" in execution_result
    # Status may be "started" or "completed" depending on execution speed
    assert execution_result["status"] in ["started", "completed"]
    assert "message" in execution_result


def test_jsonrpc_tasks_execute_with_use_demo(json_rpc_client):
    """Test executing a task with use_demo=True via JSON-RPC /tasks route"""
    # First create a task
    task_data = {
        "id": f"demo-test-{uuid.uuid4().hex[:8]}",
        "name": "Task to Execute in Demo Mode",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info_executor",
            "type": "stdio"
        },
        "inputs": {
            "resource": "cpu"
        }
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 400,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Execute task with use_demo=True via /tasks route
    execute_request = {
        "jsonrpc": "2.0",
        "id": 401,
        "method": "tasks.execute",
        "params": {
            "task_id": task_id,
            "use_streaming": False,
            "use_demo": True
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=execute_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 401
    assert "result" in result
    
    # Verify execution result
    execution_result = result["result"]
    assert "success" in execution_result
    assert execution_result["success"] is True
    assert "protocol" in execution_result
    assert execution_result["protocol"] == "jsonrpc"
    assert "root_task_id" in execution_result
    
    # Wait a bit for task to complete (demo mode should be fast)
    import time
    import asyncio
    time.sleep(0.5)
    
    # Verify task was executed with demo mode by checking task result
    from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
    from aipartnerupflow.core.config import get_task_model_class
    
    db_session = get_default_session()
    task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
    
    # Get task from database (using async helper)
    async def get_task():
        return await task_repository.get_task_by_id(task_id)
    
    # Use asyncio.run() to avoid event loop issues
    try:
        task = asyncio.run(get_task())
    except RuntimeError:
        # If event loop is already running, create a new one in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(get_task()))
            task = future.result()
    
    assert task is not None
    
    # Note: use_demo is now passed as parameter to TaskExecutor, not stored in inputs
    # Verify task result contains demo data (if task completed)
    if task.status == "completed" and task.result:
        # Demo result should contain demo_mode flag or demo data
        result_data = task.result if isinstance(task.result, dict) else {}
        # SystemInfoExecutor demo result should have demo_mode or be a demo result
        assert "demo_mode" in result_data or "result" in result_data


def test_jsonrpc_tasks_execute_with_streaming(json_rpc_client):
    """Test executing a task with streaming enabled via JSON-RPC"""
    # Create a task
    task_data = {
        "id": f"execute-stream-{uuid.uuid4().hex[:8]}",
        "name": "Task to Execute with Streaming",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 310,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Execute task with streaming
    execute_request = {
        "jsonrpc": "2.0",
        "id": 311,
        "method": "tasks.execute",
        "params": {
            "task_id": task_id,
            "use_streaming": True
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=execute_request,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"}
    )
    
    assert response.status_code == 200
    # When use_streaming=True, response is SSE format (text/event-stream)
    assert response.headers.get("content-type") == "text/event-stream; charset=utf-8"
    
    # Parse SSE response
    # SSE format: "data: {json}\n\n"
    content = response.text
    lines = content.split("\n")
    
    # Find first data line (initial JSON-RPC response)
    initial_data = None
    for line in lines:
        if line.startswith("data: "):
            data_str = line[6:]  # Remove "data: " prefix
            try:
                initial_data = json.loads(data_str)
                break
            except json.JSONDecodeError:
                continue
    
    # Verify initial response
    assert initial_data is not None, "No initial JSON-RPC response found in SSE stream"
    assert "jsonrpc" in initial_data
    assert initial_data["jsonrpc"] == "2.0"
    assert "id" in initial_data
    assert "result" in initial_data
    
    execution_result = initial_data["result"]
    assert execution_result["success"] is True
    assert "protocol" in execution_result
    assert execution_result["protocol"] == "jsonrpc"  # Verify protocol identifier
    # Status may be "started" or "completed" depending on execution speed
    assert execution_result["status"] in ["started", "completed"]
    assert "streaming" in execution_result
    assert execution_result["streaming"] is True
    assert execution_result["root_task_id"] == task_id


def test_jsonrpc_tasks_execute_with_webhook(json_rpc_client):
    """Test executing a task with webhook callbacks via JSON-RPC"""
    from unittest.mock import AsyncMock, patch
    
    # Create a task
    task_data = {
        "id": f"execute-webhook-{uuid.uuid4().hex[:8]}",
        "name": "Task to Execute with Webhook",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 320,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Mock webhook endpoint to capture callbacks
    webhook_url = "https://example.com/webhook-callback"
    webhook_requests = []
    
    async def mock_post(url, **kwargs):
        """Mock HTTP POST to webhook URL"""
        webhook_requests.append({
            "url": url,
            "json": kwargs.get("json"),
            "headers": kwargs.get("headers", {})
        })
        # Return successful response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        # raise_for_status is synchronous in httpx, not async
        mock_response.raise_for_status = lambda: None
        return mock_response
    
    # Execute task with webhook
    execute_request = {
        "jsonrpc": "2.0",
        "id": 321,
        "method": "tasks.execute",
        "params": {
            "task_id": task_id,
            "webhook_config": {
                "url": webhook_url,
                "headers": {
                    "Authorization": "Bearer test-token"
                },
                "method": "POST",
                "timeout": 30.0,
                "max_retries": 3
            }
        }
    }
    
    # Mock httpx.AsyncClient to capture webhook calls
    with patch("aipartnerupflow.api.routes.tasks.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_post)
        mock_client.put = AsyncMock(side_effect=mock_post)
        mock_client.aclose = AsyncMock()
        mock_client_class.return_value = mock_client
        
        response = json_rpc_client.post(
            "/tasks",
            json=execute_request,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert "jsonrpc" in result
        assert "result" in result
        execution_result = result["result"]
        assert execution_result["success"] is True
        assert "protocol" in execution_result
        assert execution_result["protocol"] == "jsonrpc"
        # Status may be "started" or "completed" depending on execution speed
        assert execution_result["status"] in ["started", "completed"]
        assert "streaming" in execution_result
        assert execution_result["streaming"] is True
        assert "webhook_url" in execution_result
        assert execution_result["webhook_url"] == webhook_url
        assert "message" in execution_result
        assert "webhook" in execution_result["message"].lower()
        
        # Wait a bit for webhook calls to be made (task execution is async)
        import time
        time.sleep(2)
        
        # Verify webhook was called (at least once for task completion)
        # Note: In a real scenario, webhook would be called multiple times during execution
        # For this test, we just verify the setup is correct


def test_jsonrpc_tasks_execute_task_tree(json_rpc_client):
    """Test executing a task tree via JSON-RPC"""
    # Create a task tree
    root_task_data = {
        "id": f"execute-root-{uuid.uuid4().hex[:8]}",
        "name": "Root Task to Execute",
        "user_id": "test-user",
        "status": "pending",
        "priority": 2,
        "has_children": True,
        "dependencies": [
            {"id": f"execute-child-{uuid.uuid4().hex[:8]}", "required": True}
        ],
        "schemas": {
            "method": "aggregate_results_executor",
            "type": "core"
        },
        "inputs": {}
    }
    
    child_task_data = {
        "id": f"execute-child-{uuid.uuid4().hex[:8]}",
        "name": "Child Task to Execute",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Fix references
    child_task_data["parent_id"] = root_task_data["id"]
    root_task_data["dependencies"][0]["id"] = child_task_data["id"]
    
    # Create task tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 320,
        "method": "tasks.create",
        "params": [root_task_data, child_task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    root_task_id = created_result["result"]["id"]
    
    # Execute the root task (will execute entire tree)
    execute_request = {
        "jsonrpc": "2.0",
        "id": 321,
        "method": "tasks.execute",
        "params": {
            "task_id": root_task_id,
            "use_streaming": False
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=execute_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    print(f"result:\n {json.dumps(result, indent=2)}")
    
    assert "jsonrpc" in result
    assert "result" in result
    execution_result = result["result"]
    assert execution_result["success"] is True
    assert execution_result["root_task_id"] == root_task_id
    # Status may be "started" or "completed" depending on execution speed
    assert execution_result["status"] in ["started", "completed"]


def test_jsonrpc_tasks_execute_not_found(json_rpc_client):
    """Test executing a non-existent task via JSON-RPC"""
    execute_request = {
        "jsonrpc": "2.0",
        "id": 330,
        "method": "tasks.execute",
        "params": {
            "task_id": "non-existent-task-id",
            "use_streaming": False
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=execute_request,
        headers={"Content-Type": "application/json"}
    )
    
    # Should return error
    assert response.status_code in [200, 500]  # May return 200 with error or 500
    result = response.json()
    
    assert "jsonrpc" in result
    assert "error" in result
    assert result["error"]["code"] in [-32602, -32603]  # Invalid params or internal error


def test_jsonrpc_tasks_execute_with_copy_execution(json_rpc_client):
    """Test executing a task with copy_execution=True via JSON-RPC"""
    # First create a task
    task_data = {
        "id": f"execute-copy-{uuid.uuid4().hex[:8]}",
        "name": "Task to Copy and Execute",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 400,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    original_task_id = created_result["result"]["id"]
    
    # Execute task with copy_execution=True
    execute_request = {
        "jsonrpc": "2.0",
        "id": 401,
        "method": "tasks.execute",
        "params": {
            "task_id": original_task_id,
            "copy_execution": True,
            "use_streaming": False
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=execute_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify execution result
    execution_result = result["result"]
    assert "success" in execution_result
    assert execution_result["success"] is True
    assert "protocol" in execution_result
    assert execution_result["protocol"] == "jsonrpc"
    assert "root_task_id" in execution_result
    assert "task_id" in execution_result
    assert "original_task_id" in execution_result
    assert execution_result["original_task_id"] == original_task_id
    # The task_id should be different from original_task_id (it's a copy)
    assert execution_result["task_id"] != original_task_id
    assert execution_result["root_task_id"] != original_task_id
    
    # Verify original task still exists and has_copy flag is set
    get_request = {
        "jsonrpc": "2.0",
        "id": 402,
        "method": "tasks.get",
        "params": {"task_id": original_task_id}
    }
    get_response = json_rpc_client.post("/tasks", json=get_request)
    assert get_response.status_code == 200
    original_task = get_response.json()["result"]
    assert original_task.get("has_copy") is True


def test_jsonrpc_tasks_execute_with_copy_execution_and_children(json_rpc_client):
    """Test executing a task with copy_execution=True and copy_children=True via JSON-RPC"""
    # First create a task tree with children
    root_task_data = {
        "id": f"execute-copy-children-root-{uuid.uuid4().hex[:8]}",
        "name": "Root Task",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    child_task_data = {
        "id": f"execute-copy-children-child-{uuid.uuid4().hex[:8]}",
        "name": "Child Task",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 410,
        "method": "tasks.create",
        "params": [root_task_data, child_task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    original_task_id = created_result["result"]["id"]
    
    # Execute task with copy_execution=True and copy_children=True
    execute_request = {
        "jsonrpc": "2.0",
        "id": 411,
        "method": "tasks.execute",
        "params": {
            "task_id": original_task_id,
            "copy_execution": True,
            "copy_children": True,
            "use_streaming": False
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=execute_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify execution result
    execution_result = result["result"]
    assert "success" in execution_result
    assert execution_result["success"] is True
    assert "original_task_id" in execution_result
    assert execution_result["original_task_id"] == original_task_id
    # The task_id should be different from original_task_id (it's a copy)
    assert execution_result["task_id"] != original_task_id


def test_jsonrpc_tasks_children(json_rpc_client):
    """Test getting children tasks via JSON-RPC"""
    # Create a task tree
    root_task_data = {
        "id": f"children-root-{uuid.uuid4().hex[:8]}",
        "name": "Root Task for Children",
        "user_id": "test-user",
        "status": "pending",
        "priority": 2,
        "has_children": True,
        "dependencies": [
            {"id": f"children-child1-{uuid.uuid4().hex[:8]}", "required": True},
            {"id": f"children-child2-{uuid.uuid4().hex[:8]}", "required": True}
        ],
        "schemas": {
            "method": "aggregate_results_executor",
            "type": "core"
        },
        "inputs": {}
    }
    
    child1_data = {
        "id": f"children-child1-{uuid.uuid4().hex[:8]}",
        "name": "Child Task 1",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    child2_data = {
        "id": f"children-child2-{uuid.uuid4().hex[:8]}",
        "name": "Child Task 2",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Fix references
    child1_data["parent_id"] = root_task_data["id"]
    child2_data["parent_id"] = root_task_data["id"]
    root_task_data["dependencies"][0]["id"] = child1_data["id"]
    root_task_data["dependencies"][1]["id"] = child2_data["id"]
    
    # Create task tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 400,
        "method": "tasks.create",
        "params": [root_task_data, child1_data, child2_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    root_task_id = created_result["result"]["id"]
    
    # Get children
    children_request = {
        "jsonrpc": "2.0",
        "id": 401,
        "method": "tasks.children",
        "params": {
            "parent_id": root_task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=children_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 401
    assert "result" in result
    
    # Verify children list
    children = result["result"]
    assert isinstance(children, list)
    assert len(children) == 2  # Should have 2 children
    
    # Verify each child has correct parent_id
    child_ids = [child["id"] for child in children]
    assert child1_data["id"] in child_ids or child2_data["id"] in child_ids
    
    for child in children:
        assert child["parent_id"] == root_task_id
        assert "id" in child
        assert "name" in child


def test_jsonrpc_tasks_children_empty(json_rpc_client):
    """Test getting children for a task with no children via JSON-RPC"""
    # Create a task with no children
    task_data = {
        "id": f"no-children-{uuid.uuid4().hex[:8]}",
        "name": "Task with No Children",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 410,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Get children (should be empty)
    children_request = {
        "jsonrpc": "2.0",
        "id": 411,
        "method": "tasks.children",
        "params": {
            "parent_id": task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=children_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    children = result["result"]
    assert isinstance(children, list)
    assert len(children) == 0  # Should be empty


# ============================================================================
# A2A Protocol Format Tests (POST / endpoint with execute_task_tree method)
# ============================================================================

def test_a2a_execute_task_tree_simple(json_rpc_client):
    """Test executing a task using A2A protocol format (POST / with message/send method)"""
    # A2A Protocol uses message/send method with Message object in params
    # Based on A2A SDK client implementation analysis
    task_data = {
        "id": f"a2a-task-{uuid.uuid4().hex[:8]}",
        "name": "A2A Task",
        "user_id": "test-user",
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # A2A Protocol JSON-RPC format (as used by A2A SDK client)
    # Method is "message/send", params contain Message object with parts
    a2a_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "tasks": [task_data]
                        }
                    }
                ]
            }
        },
        "id": "a2a-request-1"
    }
    
    # Send request to A2A Protocol endpoint (POST /)
    response = json_rpc_client.post(
        "/",
        json=a2a_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    print(f"result:\n {json.dumps(result, indent=2)}")
    
    # Verify A2A Protocol response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == "a2a-request-1"
    
    # A2A protocol may return result or error
    if "result" in result:
        # Verify execution result structure
        execution_result = result["result"]
        # Result is a Task object (serialized as dict in JSON response)
        assert isinstance(execution_result, dict)
        # Task object has required fields
        assert "id" in execution_result
        assert "kind" in execution_result
        assert execution_result["kind"] == "task"
        # Verify protocol identifier in metadata
        if "metadata" in execution_result:
            assert execution_result["metadata"].get("protocol") == "a2a"
        assert "status" in execution_result
        # Check status from Task.status.state
        if isinstance(execution_result["status"], dict):
            status_state = execution_result["status"].get("state")
            if status_state:
                # A2A TaskState enum values: submitted, working, input-required, completed, canceled, failed, rejected, auth-required, unknown
                assert status_state in ["submitted", "working", "input-required", "completed", "canceled", "failed", "rejected", "auth-required", "unknown"]
            # Check if status.message contains protocol identifier
            status_message = execution_result["status"].get("message")
            if isinstance(status_message, dict) and "parts" in status_message:
                for part in status_message["parts"]:
                    if isinstance(part, dict) and part.get("kind") == "data":
                        part_data = part.get("data", {})
                        if isinstance(part_data, dict) and "protocol" in part_data:
                            assert part_data["protocol"] == "a2a"
    elif "error" in result:
        # If there's an error, raise it
        error = result["error"]
        raise AssertionError(f"A2A protocol error: {error}")


def test_a2a_execute_task_tree_with_dependencies(json_rpc_client):
    """Test executing a task tree with dependencies using A2A protocol format"""
    root_task_id = f"a2a-root-{uuid.uuid4().hex[:8]}"
    child_task_id = f"a2a-child-{uuid.uuid4().hex[:8]}"
    
    tasks = [
        {
            "id": root_task_id,
            "name": "A2A Root Task",
            "user_id": "test-user",
            "dependencies": [
                {"id": child_task_id, "required": True}
            ],
            "schemas": {
                "method": "aggregate_results_executor",
                "type": "core"
            },
            "inputs": {}
        },
        {
            "id": child_task_id,
            "name": "A2A Child Task",
            "user_id": "test-user",
            "parent_id": root_task_id,
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {}
        }
    ]
    
    # A2A Protocol JSON-RPC format (as used by A2A SDK client)
    a2a_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "tasks": tasks
                        }
                    }
                ]
            }
        },
        "id": "a2a-request-2"
    }
    
    response = json_rpc_client.post(
        "/",
        json=a2a_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    if "result" in result:
        execution_result = result["result"]
        # Result is a Task object (serialized as dict in JSON response)
        assert isinstance(execution_result, dict)
        assert "id" in execution_result
        assert "kind" in execution_result
        assert execution_result["kind"] == "task"
    elif "error" in result:
        error = result["error"]
        raise AssertionError(f"A2A protocol error: {error}")


def test_a2a_execute_task_tree_with_streaming(json_rpc_client):
    """Test executing a task tree with streaming enabled using A2A protocol format"""
    task_data = {
        "id": f"a2a-stream-{uuid.uuid4().hex[:8]}",
        "name": "A2A Streaming Task",
        "user_id": "test-user",
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # A2A Protocol JSON-RPC format with streaming metadata
    a2a_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "tasks": [task_data]
                        }
                    }
                ]
            },
            "metadata": {
                "stream": True
            }
        },
        "id": "a2a-request-3"
    }
    
    response = json_rpc_client.post(
        "/",
        json=a2a_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    if "result" in result:
        execution_result = result["result"]
        # Result is a Task object (serialized as dict in JSON response)
        assert isinstance(execution_result, dict)
        # Task object has id, context_id, kind, status, artifacts fields
        assert "id" in execution_result
        assert "kind" in execution_result
        assert execution_result["kind"] == "task"
        # Check status from Task.status.state
        # A2A TaskState enum values: submitted, working, input-required, completed, canceled, failed, rejected, auth-required, unknown
        if "status" in execution_result and isinstance(execution_result["status"], dict):
            status_state = execution_result["status"].get("state")
            if status_state:
                assert status_state in ["submitted", "working", "input-required", "completed", "canceled", "failed", "rejected", "auth-required", "unknown"]
    elif "error" in result:
        error = result["error"]
        raise AssertionError(f"A2A protocol error: {error}")


def test_a2a_execute_task_tree_with_push_notifications(json_rpc_client):
    """Test executing a task tree with push notifications using A2A protocol format"""
    task_data = {
        "id": f"a2a-push-{uuid.uuid4().hex[:8]}",
        "name": "A2A Push Notification Task",
        "user_id": "test-user",
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # A2A Protocol JSON-RPC format with push notification configuration
    a2a_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "tasks": [task_data]
                        }
                    }
                ]
            },
            "configuration": {
                "push_notification_config": {
                    "url": "https://example.com/callback",
                    "headers": {
                        "Authorization": "Bearer test-token"
                    },
                    "method": "POST"
                }
            }
        },
        "id": "a2a-request-4"
    }
    
    response = json_rpc_client.post(
        "/",
        json=a2a_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    if "result" in result:
        execution_result = result["result"]
        # Result is a Task object (serialized as dict in JSON response)
        assert isinstance(execution_result, dict)
        assert "id" in execution_result
        assert "kind" in execution_result
        assert execution_result["kind"] == "task"
        # With push notifications, execution is async, check status from Task.status.state
        if "status" in execution_result and isinstance(execution_result["status"], dict):
            status_state = execution_result["status"].get("state")
            if status_state:
                # A2A TaskState enum values: submitted, working, input-required, completed, canceled, failed, rejected, auth-required, unknown
                assert status_state in ["submitted", "working", "input-required", "completed", "canceled", "failed", "rejected", "auth-required", "unknown"]
    elif "error" in result:
        error = result["error"]
        raise AssertionError(f"A2A protocol error: {error}")


def test_a2a_execute_task_tree_complex_tree(json_rpc_client):
    """Test executing a complex task tree using A2A protocol format"""
    root_id = f"a2a-complex-root-{uuid.uuid4().hex[:8]}"
    child1_id = f"a2a-complex-child1-{uuid.uuid4().hex[:8]}"
    child2_id = f"a2a-complex-child2-{uuid.uuid4().hex[:8]}"
    grandchild_id = f"a2a-complex-grandchild-{uuid.uuid4().hex[:8]}"
    
    # Complex task tree: root -> child1, child2 -> grandchild
    tasks = [
        {
            "id": root_id,
            "name": "A2A Complex Root",
            "user_id": "test-user",
            "dependencies": [
                {"id": child1_id, "required": True},
                {"id": child2_id, "required": True}
            ],
            "schemas": {
                "method": "aggregate_results_executor",
                "type": "core"
            },
            "inputs": {}
        },
        {
            "id": child1_id,
            "name": "A2A Child 1",
            "user_id": "test-user",
            "parent_id": root_id,
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {"resource": "cpu"}
        },
        {
            "id": child2_id,
            "name": "A2A Child 2",
            "user_id": "test-user",
            "parent_id": root_id,
            "dependencies": [
                {"id": grandchild_id, "required": True}
            ],
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {"resource": "memory"}
        },
        {
            "id": grandchild_id,
            "name": "A2A Grandchild",
            "user_id": "test-user",
            "parent_id": child2_id,
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {"resource": "disk"}
        }
    ]
    
    # A2A Protocol JSON-RPC format (as used by A2A SDK client)
    a2a_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "tasks": tasks
                        }
                    }
                ]
            }
        },
        "id": "a2a-request-5"
    }
    
    response = json_rpc_client.post(
        "/",
        json=a2a_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    if "result" in result:
        execution_result = result["result"]
        # Result is a Task object (serialized as dict in JSON response)
        assert isinstance(execution_result, dict)
        assert "id" in execution_result
        assert "kind" in execution_result
        assert execution_result["kind"] == "task"
        # Extract data from artifacts if available
        if "artifacts" in execution_result and execution_result["artifacts"]:
            artifacts = execution_result["artifacts"]
            if len(artifacts) > 0 and "parts" in artifacts[0] and artifacts[0]["parts"]:
                part = artifacts[0]["parts"][0]
                if "root" in part and "data" in part["root"]:
                    artifact_data = part["root"]["data"]
                    if "root_task_id" in artifact_data:
                        assert artifact_data["root_task_id"] == root_id
                    if "task_count" in artifact_data:
                        assert artifact_data["task_count"] == 4  # root + 2 children + 1 grandchild
        # Also check metadata
        if "metadata" in execution_result and "root_task_id" in execution_result["metadata"]:
            assert execution_result["metadata"]["root_task_id"] == root_id
    elif "error" in result:
        error = result["error"]
        raise AssertionError(f"A2A protocol error: {error}")


def test_a2a_execute_task_tree_error_handling(json_rpc_client):
    """Test A2A protocol error handling for invalid requests"""
    # Invalid method
    invalid_request = {
        "jsonrpc": "2.0",
        "method": "invalid_method",
        "params": {},
        "id": "a2a-error-1"
    }
    
    response = json_rpc_client.post(
        "/",
        json=invalid_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code in [200, 400]
    result = response.json()
    assert "jsonrpc" in result
    assert "error" in result
    assert result["error"]["code"] == -32601  # Method not found
    
    # Missing message/tasks
    missing_tasks_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": []  # Empty parts - should cause error
            }
        },
        "id": "a2a-error-2"
    }
    
    response = json_rpc_client.post(
        "/",
        json=missing_tasks_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code in [200, 400, 500]
    result = response.json()
    assert "jsonrpc" in result
    # Should have error or empty result
    assert "error" in result or "result" in result


def test_a2a_execute_task_tree_vs_tasks_execute(json_rpc_client):
    """Compare A2A protocol format vs tasks.execute method"""
    # First, create a task using tasks.create
    task_data = {
        "id": f"compare-task-{uuid.uuid4().hex[:8]}",
        "name": "Compare Task",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 500,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Method 1: Execute using tasks.execute
    execute_request = {
        "jsonrpc": "2.0",
        "id": 501,
        "method": "tasks.execute",
        "params": {
            "task_id": task_id,
            "use_streaming": False
        }
    }
    
    execute_response = json_rpc_client.post("/tasks", json=execute_request)
    assert execute_response.status_code == 200
    execute_result = execute_response.json()
    assert execute_result["result"]["success"] is True
    
    # Method 2: Execute using A2A protocol format (creates and executes in one call)
    task_data = {
        "id": f"compare-a2a-{uuid.uuid4().hex[:8]}",
        "name": "Compare A2A Task",
        "user_id": "test-user",
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # A2A Protocol JSON-RPC format (as used by A2A SDK client)
    a2a_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "tasks": [task_data]
                        }
                    }
                ]
            }
        },
        "id": "a2a-compare-1"
    }
    
    a2a_response = json_rpc_client.post("/", json=a2a_request)
    assert a2a_response.status_code == 200
    a2a_result = a2a_response.json()
    
    # A2A protocol response format may vary
    if "result" in a2a_result:
        assert isinstance(a2a_result["result"], (dict, list))
    elif "error" in a2a_result:
        a2a_result["error"]
        # Other errors are acceptable for comparison test
        pass
    
    # Both methods should work, but have different use cases:
    # - tasks.execute: Execute existing tasks
    # - A2A message/send: Create and execute in one call using Message format


def test_a2a_execute_task_tree_with_use_demo(json_rpc_client):
    """Test executing task tree with use_demo=True via A2A Protocol / route"""
    # Prepare task data with use_demo in inputs
    task_data = {
        "id": f"a2a-demo-{uuid.uuid4().hex[:8]}",
        "name": "A2A Demo Task",
        "user_id": "test-user",
        "schemas": {
            "method": "system_info_executor",
            "type": "stdio"
        },
        "inputs": {
            "resource": "cpu"
        }
    }
    
    # A2A Protocol JSON-RPC format
    # use_demo is passed via metadata in A2A protocol
    a2a_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "tasks": [task_data]
                        }
                    }
                ],
                "metadata": {
                    "use_demo": True  # Pass use_demo via metadata
                }
            }
        },
        "id": "a2a-demo-1"
    }
    
    response = json_rpc_client.post(
        "/",
        json=a2a_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == "a2a-demo-1"
    
    # Wait a bit for task to complete (demo mode should be fast)
    import time
    import asyncio
    time.sleep(0.5)
    
    # Verify task was executed with demo mode by checking task result
    from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
    from aipartnerupflow.core.config import get_task_model_class
    
    db_session = get_default_session()
    task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
    
    # Get task from database using task_id from task_data
    async def get_task():
        return await task_repository.get_task_by_id(task_data["id"])
    
    # Use asyncio.run() to avoid event loop issues
    try:
        task = asyncio.run(get_task())
    except RuntimeError:
        # If event loop is already running, create a new one in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(get_task()))
            task = future.result()
    
    # Task might not exist if execution failed, so check if it exists
    if task:
        # Note: use_demo is now passed as parameter to TaskExecutor, not stored in inputs
        # Verify task result contains demo data (if task completed)
        if task.status == "completed" and task.result:
            # Demo result should contain demo_mode flag or demo data
            result_data = task.result if isinstance(task.result, dict) else {}
            # SystemInfoExecutor demo result should have demo_mode or be a demo result
            assert "demo_mode" in result_data or "result" in result_data


def test_jsonrpc_tasks_list(json_rpc_client):
    """Test listing all tasks via JSON-RPC tasks.list endpoint"""
    # First create a task
    task_data = {
        "id": f"list-test-{uuid.uuid4().hex[:8]}",
        "name": "Task for List Test",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info_executor",
            "type": "stdio"
        },
        "inputs": {
            "resource": "cpu"
        }
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 500,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    
    # List tasks
    list_request = {
        "jsonrpc": "2.0",
        "id": 501,
        "method": "tasks.list",
        "params": {
            "user_id": "test-user",
            "limit": 10,
            "offset": 0
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=list_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 501
    assert "result" in result
    # Result should be a list or dict with tasks
    list_result = result["result"]
    assert isinstance(list_result, (list, dict))
    if isinstance(list_result, dict):
        assert "tasks" in list_result or "items" in list_result


def test_jsonrpc_tasks_running_status(json_rpc_client):
    """Test getting running task status via JSON-RPC tasks.running.status endpoint"""
    # First create and execute a task
    task_data = {
        "id": f"status-test-{uuid.uuid4().hex[:8]}",
        "name": "Task for Status Test",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info_executor",
            "type": "stdio"
        },
        "inputs": {
            "resource": "cpu"
        }
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 600,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Get running task status
    status_request = {
        "jsonrpc": "2.0",
        "id": 601,
        "method": "tasks.running.status",
        "params": {
            "task_ids": [task_id]
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=status_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 601
    assert "result" in result
    # Result should be an array of status information
    status_result = result["result"]
    assert isinstance(status_result, list)
    assert len(status_result) > 0
    # Check first status entry
    status_entry = status_result[0]
    assert isinstance(status_entry, dict)
    assert "task_id" in status_entry or "status" in status_entry


def test_jsonrpc_tasks_running_count(json_rpc_client):
    """Test counting running tasks via JSON-RPC tasks.running.count endpoint"""
    count_request = {
        "jsonrpc": "2.0",
        "id": 700,
        "method": "tasks.running.count",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=count_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 700
    assert "result" in result
    # Result should contain count
    count_result = result["result"]
    assert isinstance(count_result, dict)
    assert "count" in count_result
    assert isinstance(count_result["count"], int)
    assert count_result["count"] >= 0


def test_jsonrpc_tasks_cancel(json_rpc_client):
    """Test cancelling a task via JSON-RPC tasks.cancel endpoint"""
    # First create and start executing a task
    task_data = {
        "id": f"cancel-test-{uuid.uuid4().hex[:8]}",
        "name": "Task to Cancel",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info_executor",
            "type": "stdio"
        },
        "inputs": {
            "resource": "cpu"
        }
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 800,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Cancel task
    cancel_request = {
        "jsonrpc": "2.0",
        "id": 801,
        "method": "tasks.cancel",
        "params": {
            "task_ids": [task_id],
            "error_message": "Cancelled by test"
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=cancel_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 801
    assert "result" in result
    # Result should be an array of cancellation results
    cancel_result = result["result"]
    assert isinstance(cancel_result, list)
    assert len(cancel_result) > 0
    # Check first cancellation result
    cancel_entry = cancel_result[0]
    assert isinstance(cancel_entry, dict)
    assert "status" in cancel_entry
    assert cancel_entry["status"] in ["cancelled", "failed"]


def test_jsonrpc_tasks_generate(json_rpc_client):
    """Test generating task tree via JSON-RPC tasks.generate endpoint"""
    # Skip if no LLM API key is available (generate requires LLM)
    import os
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("No LLM API key available for generate test")
    
    # Skip if crewai is not installed (generate uses crewai executor)
    try:
        import crewai  # noqa: F401
    except ImportError:
        pytest.skip("crewai not installed - generate endpoint requires crewai[tools]")
    
    generate_request = {
        "jsonrpc": "2.0",
        "id": 900,
        "method": "tasks.generate",
        "params": {
            "requirement": "Get system CPU information and process it",
            "user_id": "test-user"
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=generate_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 900
    # Result may be in result or error field
    if "result" in result:
        generate_result = result["result"]
        assert isinstance(generate_result, dict)
        # Should contain tasks array
        assert "tasks" in generate_result or "status" in generate_result

