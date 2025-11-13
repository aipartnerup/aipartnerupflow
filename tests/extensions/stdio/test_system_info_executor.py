"""
Test SystemInfoExecutor functionality

This module tests that system information queries work correctly
and are always available (safe predefined commands).
"""

import pytest
from aipartnerupflow.extensions.stdio import SystemInfoExecutor


class TestSystemInfoExecutor:
    """Test cases for SystemInfoExecutor"""

    @pytest.mark.asyncio
    async def test_system_info_always_available(self):
        """Test that system_info executor is always available (safe commands)"""
        executor = SystemInfoExecutor()
        
        # system_info should work (safe predefined commands)
        result = await executor.execute({
            "resource": "cpu"
        })
        
        # Should succeed (may vary by system, but should not be security-blocked)
        assert "system" in result
        assert "security_blocked" not in result

    @pytest.mark.asyncio
    async def test_get_cpu_info(self):
        """Test CPU information retrieval"""
        executor = SystemInfoExecutor()
        
        result = await executor.execute({
            "resource": "cpu"
        })
        
        # Should contain system information
        assert "system" in result
        # May contain cores, brand, etc. depending on system
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_memory_info(self):
        """Test memory information retrieval"""
        executor = SystemInfoExecutor()
        
        result = await executor.execute({
            "resource": "memory"
        })
        
        # Should contain system information
        assert "system" in result
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_disk_info(self):
        """Test disk information retrieval"""
        executor = SystemInfoExecutor()
        
        result = await executor.execute({
            "resource": "disk"
        })
        
        # Should contain system information
        assert "system" in result
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_all_resources(self):
        """Test getting all system resources at once"""
        executor = SystemInfoExecutor()
        
        result = await executor.execute({
            "resource": "all"
        })
        
        # Should contain cpu, memory, and disk
        assert "cpu" in result
        assert "memory" in result
        assert "disk" in result
        assert isinstance(result["cpu"], dict)
        assert isinstance(result["memory"], dict)
        assert isinstance(result["disk"], dict)

    @pytest.mark.asyncio
    async def test_invalid_resource(self):
        """Test that invalid resource raises error"""
        executor = SystemInfoExecutor()
        
        with pytest.raises(ValueError, match="Unknown resource"):
            await executor.execute({
                "resource": "invalid_resource"
            })

    @pytest.mark.asyncio
    async def test_timeout_parameter(self):
        """Test that timeout parameter is respected"""
        executor = SystemInfoExecutor()
        
        result = await executor.execute({
            "resource": "cpu",
            "timeout": 10
        })
        
        # Should succeed with custom timeout
        assert "system" in result

