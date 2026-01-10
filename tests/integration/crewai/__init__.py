"""End-to-end integration tests for CrewAI deliberation (Story 10-5).

These tests validate the complete deliberation pipeline:
- Topic submission -> ArchonSelection -> LLM invocation -> Collective output

IMPORTANT: These tests require LLM API keys to run.
Set at least one of:
- ANTHROPIC_API_KEY=sk-ant-...
- OPENAI_API_KEY=sk-...

Tests are automatically skipped if no API keys are configured.

Cost Expectations:
- Smoke tests: ~$0.05-0.10 per run (2-3 agents)
- Load tests: ~$0.50-2.00 per run (72 agents)
"""
