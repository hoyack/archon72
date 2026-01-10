#!/usr/bin/env python3
"""Quick smoke test for Ollama + CrewAI integration.

Tests:
1. Ollama server connectivity
2. Model availability
3. Single agent invocation via CrewAI
4. Sequential deliberation with multiple agents

Usage:
    python scripts/test_ollama_connection.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_env_config() -> bool:
    """Test environment configuration."""
    print("\n" + "=" * 60)
    print("1. ENVIRONMENT CONFIGURATION")
    print("=" * 60)

    ollama_host = os.environ.get("OLLAMA_HOST", "not set")
    delib_mode = os.environ.get("DELIBERATION_MODE", "not set")

    print(f"   OLLAMA_HOST: {ollama_host}")
    print(f"   DELIBERATION_MODE: {delib_mode}")

    if ollama_host == "not set":
        print("   ❌ OLLAMA_HOST not configured in .env")
        return False

    print("   ✅ Environment configured")
    return True


def test_ollama_connectivity() -> bool:
    """Test Ollama server connectivity."""
    import httpx

    print("\n" + "=" * 60)
    print("2. OLLAMA SERVER CONNECTIVITY")
    print("=" * 60)

    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    try:
        response = httpx.get(f"{ollama_host}/api/tags", timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            print(f"   Server: {ollama_host}")
            print(f"   Status: Connected ✅")
            print(f"   Models available: {len(models)}")
            for model in models[:5]:
                print(f"     - {model}")
            if len(models) > 5:
                print(f"     ... and {len(models) - 5} more")
            return True
        else:
            print(f"   ❌ Server returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False


def test_crewai_llm_creation() -> bool:
    """Test CrewAI LLM object creation."""
    print("\n" + "=" * 60)
    print("3. CREWAI LLM CREATION")
    print("=" * 60)

    try:
        from crewai import LLM
        from src.domain.models.llm_config import LLMConfig
        from src.infrastructure.adapters.external.crewai_adapter import _create_crewai_llm

        # Create a test LLM config for local model
        config = LLMConfig(
            provider="local",
            model="gemma3:4b",  # Smallest model for quick test
            temperature=0.5,
            max_tokens=256,
            timeout_ms=60000,
        )

        llm = _create_crewai_llm(config)

        print(f"   Provider: {config.provider}")
        print(f"   Model: {config.model}")
        print(f"   LLM Type: {type(llm).__name__}")

        if isinstance(llm, LLM):
            print(f"   Base URL: {llm.base_url}")
            print("   ✅ LLM object created successfully")
            return True
        else:
            print(f"   ❌ Expected LLM object, got {type(llm)}")
            return False

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_single_agent_invoke() -> bool:
    """Test single agent invocation with real Ollama."""
    print("\n" + "=" * 60)
    print("4. SINGLE AGENT INVOCATION (Real LLM)")
    print("=" * 60)
    print("   This will call Ollama - may take 30-60 seconds...")

    try:
        from crewai import Agent, Task, Crew, LLM

        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        # Use smallest model for quick test
        llm = LLM(
            model="ollama/gemma3:4b",
            base_url=ollama_host,
            temperature=0.5,
            max_tokens=256,
        )

        agent = Agent(
            role="Test Agent",
            goal="Respond briefly to test connectivity",
            backstory="You are a test agent verifying system connectivity.",
            llm=llm,
            verbose=False,
            max_iter=1,
        )

        task = Task(
            description="Say 'Connection successful!' in exactly 3 words.",
            expected_output="A 3-word confirmation message",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )

        print("   Invoking agent...")
        start = datetime.now()

        result = await asyncio.wait_for(
            asyncio.to_thread(crew.kickoff),
            timeout=120.0,
        )

        elapsed = (datetime.now() - start).total_seconds()

        print(f"   Response: {str(result)[:100]}...")
        print(f"   Time: {elapsed:.1f}s")
        print("   ✅ Agent invocation successful")
        return True

    except asyncio.TimeoutError:
        print("   ❌ Timeout after 120 seconds")
        return False
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_sequential_deliberation() -> bool:
    """Test sequential deliberation with stub (no real LLM calls)."""
    print("\n" + "=" * 60)
    print("5. SEQUENTIAL DELIBERATION (Stub)")
    print("=" * 60)

    try:
        from src.application.ports.agent_orchestrator import (
            AgentRequest,
            ContextBundle,
        )
        from src.infrastructure.stubs.agent_orchestrator_stub import (
            AgentOrchestratorStub,
        )

        stub = AgentOrchestratorStub(latency_ms=10)

        # Create 5 test requests
        requests = []
        for i in range(5):
            context = ContextBundle(
                bundle_id=uuid4(),
                topic_id="test-topic",
                topic_content="Test deliberation topic",
                metadata=None,
                created_at=datetime.now(timezone.utc),
            )
            requests.append(AgentRequest(
                request_id=uuid4(),
                agent_id=f"archon-{i}",
                context=context,
            ))

        progress_log = []

        def on_progress(current: int, total: int, agent_id: str, status: str) -> None:
            progress_log.append((current, total, agent_id, status))
            if status == "completed":
                print(f"   Turn {current}/{total}: {agent_id} ✓")

        print("   Running 5-agent sequential deliberation...")
        outputs = await stub.invoke_sequential(requests, on_progress=on_progress)

        print(f"   Outputs received: {len(outputs)}")
        print(f"   Progress callbacks: {len(progress_log)}")
        print("   ✅ Sequential deliberation successful")
        return True

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main() -> None:
    """Run all tests."""
    print("\n" + "=" * 60)
    print("   ARCHON 72 - OLLAMA INTEGRATION SMOKE TEST")
    print("=" * 60)

    results = {}

    # Test 1: Environment
    results["env"] = test_env_config()

    # Test 2: Ollama connectivity
    results["ollama"] = test_ollama_connectivity()

    # Test 3: CrewAI LLM creation
    results["crewai_llm"] = test_crewai_llm_creation()

    # Test 4: Single agent (real LLM) - only if previous tests passed
    if all([results["env"], results["ollama"], results["crewai_llm"]]):
        results["single_agent"] = await test_single_agent_invoke()
    else:
        print("\n" + "=" * 60)
        print("4. SINGLE AGENT INVOCATION")
        print("=" * 60)
        print("   ⏭️  Skipped (previous tests failed)")
        results["single_agent"] = None

    # Test 5: Sequential deliberation (stub)
    results["sequential"] = await test_sequential_deliberation()

    # Summary
    print("\n" + "=" * 60)
    print("   SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for name, result in results.items():
        status = "✅ PASS" if result is True else "❌ FAIL" if result is False else "⏭️  SKIP"
        print(f"   {name}: {status}")

    print(f"\n   Total: {passed} passed, {failed} failed, {skipped} skipped")

    if failed == 0:
        print("\n   🎉 All tests passed! Ready for deliberation.")
    else:
        print("\n   ⚠️  Some tests failed. Check configuration.")


if __name__ == "__main__":
    asyncio.run(main())
