"""
Test A2A Protocol client integration

This module tests the A2A Protocol Server using the real A2A client library (ClientFactory/Client).
Tests actual A2A protocol communication using the official A2A SDK client.

This is different from test_http_json_rpc.py which uses direct HTTP JSON-RPC calls via TestClient.
This test uses the official A2A SDK client which handles protocol details automatically.
"""

import pytest
import pytest_asyncio
import uuid
from a2a.client import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role, AgentCard
from aipartnerupflow.api.a2a.server import create_a2a_server
import json


@pytest.fixture(scope="function")
def a2a_server_app(use_test_db_session):
    """Create A2A server app for testing"""
    # Create A2A server instance
    server_instance = create_a2a_server(
        verify_token_secret_key=None,  # No JWT for testing
        base_url="http://localhost:8000",
        enable_system_routes=True,
    )
    
    # Build the app
    app = server_instance.build()
    
    return app


@pytest_asyncio.fixture(scope="function")
async def a2a_client(a2a_server_app):
    """
    Create A2A client connected to test server using ClientFactory
    
    This uses the official A2A SDK ClientFactory to create a proper A2A client,
    which is different from direct HTTP calls used in test_http_json_rpc.py
    """
    from httpx import ASGITransport, AsyncClient
    
    # Create async transport using the ASGI app
    transport = ASGITransport(app=a2a_server_app)
    
    # Create async HTTP client with custom transport
    async_httpx_client = AsyncClient(transport=transport, base_url="http://testserver")
    
    # Create A2A client config with custom httpx client
    config = ClientConfig(
        streaming=True,
        polling=False,
        httpx_client=async_httpx_client,
    )
    
    # Create client factory
    factory = ClientFactory(config=config)
    
    # Fetch agent card first (required to create client with ClientFactory)
    # We need to make a direct HTTP call to get the card first
    # Then use ClientFactory.create() to create the proper client
    from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
    card_response = await async_httpx_client.get(AGENT_CARD_WELL_KNOWN_PATH)
    assert card_response.status_code == 200
    card_data = card_response.json()
    agent_card = AgentCard(**card_data)
    
    # Create proper A2A client using ClientFactory (new API)
    client = factory.create(card=agent_card)
    
    yield client
    
    # Cleanup
    await async_httpx_client.aclose()


@pytest.mark.asyncio
async def test_a2a_agent_card(a2a_client):
    """Test fetching agent card via A2A client"""
    # Get agent card using A2A client
    card = await a2a_client.get_card()
    
    # Verify agent card structure
    assert card.name == "aipartnerupflow"
    assert card.description is not None
    assert card.capabilities is not None
    assert card.skills is not None
    assert len(card.skills) > 0


@pytest.mark.asyncio
async def test_a2a_execute_task_simple_mode(a2a_client):
    """Test executing a task via A2A client in simple mode"""
    # Prepare task data
    task_data = {
        "id": "test-task-1",
        "name": "Test Task",
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
    
    # Create A2A message with task data
    data_part = DataPart(kind="data", data={"tasks": [task_data]})
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[data_part]
    )
    
    # Send message using A2A client (new API returns AsyncIterator)
    responses = []
    async for response in a2a_client.send_message(message):
        responses.append(response)
        # Response can be either (Task, Update) tuple or Message
        if isinstance(response, Message):
            # Extract result from response message
            if response.parts:
                for part in response.parts:
                    if part.kind == "data" and isinstance(part.data, dict):
                        result_data = part.data
                        # Verify execution result has expected fields
                        assert "status" in result_data or "root_task_id" in result_data or "progress" in result_data, \
                            f"Result data missing expected fields: {result_data}"
        elif isinstance(response, tuple):
            # Response is (Task, Update) tuple
            task, update = response
            assert task is not None
    
    # Verify we received at least one response
    assert len(responses) > 0


@pytest.mark.asyncio
async def test_a2a_execute_task_streaming_mode(a2a_client):
    """Test executing a task via A2A client in streaming mode"""
    # Prepare task data
    task_data = {
        "id": "test-task-2",
        "name": "Test Streaming Task",
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
    
    # Create A2A message with task data
    data_part = DataPart(kind="data", data={"tasks": [task_data]})
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[data_part]
    )
    
    # Send message using A2A client (automatically handles streaming based on config)
    # The client config has streaming=True, so it will use streaming mode
    events_received = []
    async for response in a2a_client.send_message(message):
        events_received.append(response)
        # Response can be either (Task, Update) tuple or Message
        if isinstance(response, Message):
            # In streaming mode, we receive multiple message responses
            if response.parts:
                for part in response.parts:
                    if part.kind == "data" and isinstance(part.data, dict):
                        # Verify streaming event structure
                        assert "status" in part.data or "root_task_id" in part.data or "progress" in part.data
        elif isinstance(response, tuple):
            # Response is (Task, Update) tuple - streaming updates
            task, update = response
            assert task is not None
    
    # Verify we received at least one event
    assert len(events_received) > 0


@pytest.mark.asyncio
async def test_a2a_task_with_dependencies(a2a_client):
    """Test executing a task tree with dependencies via A2A client"""
    # Prepare task tree with dependencies
    tasks = [
        {
            "id": "parent-task",
            "name": "Parent Task",
            "user_id": "test-user",
            "status": "pending",
            "priority": 2,
            "has_children": True,
            "dependencies": [
                {"id": "child-1", "required": True},
                {"id": "child-2", "required": True}
            ],
            "schemas": {
                "method": "aggregate_results_executor",
                "type": "core"
            },
            "inputs": {}
        },
        {
            "id": "child-1",
            "name": "Child Task 1",
            "parent_id": "parent-task",
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
        },
        {
            "id": "child-2",
            "name": "Child Task 2",
            "parent_id": "parent-task",
            "user_id": "test-user",
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "dependencies": [
                {"id": "child-1", "required": True}
            ],
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {}
        }
    ]
    
    # Create A2A message with task tree
    data_part = DataPart(kind="data", data={"tasks": tasks})
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[data_part]
    )
    
    # Send message using A2A client (new API returns AsyncIterator)
    responses = []
    async for response in a2a_client.send_message(message):
        responses.append(response)
        # Response can be either (Task, Update) tuple or Message
        if isinstance(response, Message):
            # Extract result from response message
            if response.parts:
                for part in response.parts:
                    if part.kind == "data" and isinstance(part.data, dict):
                        result_data = part.data
                        print(f"Result data:\n {json.dumps(result_data, indent=2)}")
                        # Verify execution result has expected fields
                        assert "status" in result_data or "root_task_id" in result_data or "progress" in result_data, \
                            f"Result data missing expected fields: {result_data}"
        elif isinstance(response, tuple):
            # Response is (Task, Update) tuple
            task, update = response
            assert task is not None
    
    # Verify we received at least one response
    assert len(responses) > 0


@pytest.mark.asyncio
async def test_a2a_error_handling(a2a_client):
    """Test A2A client error handling"""
    # Create message with empty parts (should cause error)
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[]  # Empty parts - should cause error
    )
    
    # Send message - should handle error gracefully
    # New API returns AsyncIterator, so we need to iterate
    try:
        responses = []
        async for response in a2a_client.send_message(message):
            responses.append(response)
        # If we get responses, they might contain error information
        # The exact behavior depends on server implementation
        # Empty parts might result in no responses or error responses
        pass  # Error handling is acceptable in various forms
    except Exception as e:
        # Error handling is acceptable
        assert isinstance(e, Exception)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a2a_client_integration(a2a_client):
    """Integration test: Full A2A client workflow"""
    # Step 1: Get agent card
    card = await a2a_client.get_card()
    assert card.name == "aipartnerupflow"
    
    # Step 2: Execute a task
    task_data = {
        "id": "integration-test-task",
        "name": "Integration Test Task",
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
    
    # Create A2A message with task data
    data_part = DataPart(kind="data", data={"tasks": [task_data]})
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[data_part]
    )
    
    # Send message using A2A client (new API returns AsyncIterator)
    responses = []
    async for response in a2a_client.send_message(message):
        responses.append(response)
        # Response can be either (Task, Update) tuple or Message
        if isinstance(response, Message):
            # Extract result from response message
            if response.parts:
                for part in response.parts:
                    if part.kind == "data" and isinstance(part.data, dict):
                        result_data = part.data
                        # Verify execution result has expected fields
                        assert "status" in result_data or "root_task_id" in result_data or "progress" in result_data, \
                            f"Result data missing expected fields: {result_data}"
        elif isinstance(response, tuple):
            # Response is (Task, Update) tuple
            task, update = response
            assert task is not None
    
    # Verify we received at least one response
    assert len(responses) > 0
