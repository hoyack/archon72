# CrewAI + Ollama Cloud Integration Specification

**Version:** 1.0  
**Date:** January 2026  
**Status:** Draft

---

## 1. Overview

This specification defines the configuration patterns for connecting CrewAI applications to Ollama Cloud, replacing the traditional local Ollama server setup.

### 1.1 Key Differences

| Aspect | Local Ollama | Ollama Cloud |
|--------|--------------|--------------|
| Base URL | `http://localhost:11434` | `https://ollama.com` |
| Authentication | None required | Bearer token (API key) |
| Model naming | `ollama/llama3:70b` | `ollama/gpt-oss:120b` or cloud-specific models |
| Setup | Requires local Ollama installation | No local installation required |
| GPU | Requires local GPU | Cloud-hosted inference |

---

## 2. Authentication

### 2.1 Obtaining an API Key

1. Create an account at [ollama.com](https://ollama.com)
2. Navigate to [ollama.com/settings/keys](https://ollama.com/settings/keys)
3. Generate a new API key
4. Store securely (never commit to version control)

### 2.2 Environment Variable

```bash
# .env file
OLLAMA_API_KEY=your_api_key_here
```

---

## 3. Configuration Patterns

### 3.1 Environment Variables (Recommended)

```bash
# .env file - Complete configuration
OLLAMA_API_KEY=your_api_key_here
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_MODEL=gpt-oss:120b
```

### 3.2 Config File Pattern

For applications using a YAML or JSON config file:

#### YAML Config (config.yaml)

```yaml
# CrewAI Ollama Cloud Configuration
llm:
  provider: ollama_cloud
  base_url: ${OLLAMA_BASE_URL:-https://ollama.com}
  model: ${OLLAMA_MODEL:-gpt-oss:120b}
  # API key should come from environment, not config file
  # api_key: ${OLLAMA_API_KEY}  # Loaded from env

# Optional settings
settings:
  temperature: 0.7
  max_tokens: 4096
  timeout: 120
```

#### JSON Config (config.json)

```json
{
  "llm": {
    "provider": "ollama_cloud",
    "base_url": "https://ollama.com",
    "model": "gpt-oss:120b"
  },
  "settings": {
    "temperature": 0.7,
    "max_tokens": 4096,
    "timeout": 120
  }
}
```

---

## 4. CrewAI Integration Code

### 4.1 Direct LLM Configuration

```python
import os
from crewai import LLM, Agent, Task, Crew

# Load from environment
api_key = os.getenv("OLLAMA_API_KEY")
base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")
model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")

# Configure LLM for Ollama Cloud
llm = LLM(
    model=f"ollama/{model}",
    base_url=base_url,
    api_key=api_key,
    # Optional parameters
    temperature=0.7,
    max_tokens=4096,
)

# Use with Agent
agent = Agent(
    role="Research Analyst",
    goal="Analyze data and provide insights",
    backstory="Expert data analyst with years of experience",
    llm=llm,
    verbose=True
)
```

### 4.2 Config File Loader Pattern

```python
import os
import yaml
from crewai import LLM, Agent

def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file with environment variable substitution."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def create_ollama_cloud_llm(config: dict) -> LLM:
    """
    Create LLM instance configured for Ollama Cloud.
    
    Supports both local Ollama and Ollama Cloud based on config.
    """
    llm_config = config.get('llm', {})
    provider = llm_config.get('provider', 'ollama_local')
    
    if provider == 'ollama_cloud':
        # Ollama Cloud configuration
        base_url = os.getenv('OLLAMA_BASE_URL', llm_config.get('base_url', 'https://ollama.com'))
        api_key = os.getenv('OLLAMA_API_KEY')
        model = os.getenv('OLLAMA_MODEL', llm_config.get('model', 'gpt-oss:120b'))
        
        if not api_key:
            raise ValueError("OLLAMA_API_KEY environment variable is required for Ollama Cloud")
        
        return LLM(
            model=f"ollama/{model}",
            base_url=base_url,
            api_key=api_key,
            temperature=config.get('settings', {}).get('temperature', 0.7),
            max_tokens=config.get('settings', {}).get('max_tokens', 4096),
        )
    else:
        # Local Ollama configuration (fallback)
        base_url = os.getenv('OLLAMA_BASE_URL', llm_config.get('base_url', 'http://localhost:11434'))
        model = os.getenv('OLLAMA_MODEL', llm_config.get('model', 'llama3:70b'))
        
        return LLM(
            model=f"ollama/{model}",
            base_url=base_url,
            temperature=config.get('settings', {}).get('temperature', 0.7),
        )

# Usage
config = load_config("config.yaml")
llm = create_ollama_cloud_llm(config)
```

### 4.3 Migration from Local Ollama

If your existing config uses a path variable for the Ollama server:

```python
# BEFORE: Local Ollama pattern
# config.yaml had: ollama_path: http://localhost:11434

# AFTER: Ollama Cloud pattern with backward compatibility

import os
from crewai import LLM

def get_llm_from_config(config: dict) -> LLM:
    """
    Backward-compatible LLM factory.
    
    Supports:
    - Legacy: ollama_path variable
    - New: provider-based configuration
    """
    # Check for legacy ollama_path
    ollama_path = config.get('ollama_path') or os.getenv('OLLAMA_PATH')
    
    # Detect if using Ollama Cloud
    is_cloud = (
        config.get('llm', {}).get('provider') == 'ollama_cloud' or
        os.getenv('OLLAMA_CLOUD_ENABLED', '').lower() == 'true' or
        (ollama_path and 'ollama.com' in ollama_path)
    )
    
    if is_cloud:
        # Ollama Cloud
        base_url = ollama_path if ollama_path and 'ollama.com' in ollama_path else 'https://ollama.com'
        api_key = os.getenv('OLLAMA_API_KEY')
        model = config.get('model', os.getenv('OLLAMA_MODEL', 'gpt-oss:120b'))
        
        return LLM(
            model=f"ollama/{model}",
            base_url=base_url,
            api_key=api_key,
        )
    else:
        # Local Ollama (legacy behavior)
        base_url = ollama_path or 'http://localhost:11434'
        model = config.get('model', os.getenv('OLLAMA_MODEL', 'llama3:70b'))
        
        return LLM(
            model=f"ollama/{model}",
            base_url=base_url,
        )
```

---

## 5. YAML Config for Agents

CrewAI supports defining agents in YAML. Here's the pattern for Ollama Cloud:

### 5.1 agents.yaml

```yaml
# agents.yaml
researcher:
  role: Senior Research Analyst
  goal: Conduct comprehensive analysis of {topic}
  backstory: >
    You are a distinguished research analyst with expertise in 
    emerging technologies and market trends.
  llm: ollama/gpt-oss:120b
  verbose: true

writer:
  role: Content Writer
  goal: Write engaging content about {topic}
  backstory: >
    You are a talented writer who simplifies complex information
    into accessible content.
  llm: ollama/gpt-oss:120b
  verbose: true
```

### 5.2 Custom LLM in YAML (with base_url)

```yaml
# agents.yaml - With explicit cloud configuration
researcher:
  role: Senior Research Analyst
  goal: Analyze emerging trends in {topic}
  backstory: Expert analyst with deep domain knowledge
  llm:
    model: ollama/gpt-oss:120b
    base_url: https://ollama.com
    temperature: 0.7
```

**Note:** API keys should NOT be in YAML files. Use environment variables.

---

## 6. Async / Multi-Agent Pattern

For CrewAI applications making concurrent calls:

```python
import os
import asyncio
from crewai import LLM, Agent, Task, Crew

def create_cloud_llm() -> LLM:
    """Factory function for Ollama Cloud LLM instances."""
    return LLM(
        model=f"ollama/{os.getenv('OLLAMA_MODEL', 'gpt-oss:120b')}",
        base_url=os.getenv('OLLAMA_BASE_URL', 'https://ollama.com'),
        api_key=os.getenv('OLLAMA_API_KEY'),
    )

# Create multiple agents with shared or separate LLM instances
researcher = Agent(
    role="Researcher",
    goal="Research {topic}",
    backstory="Expert researcher",
    llm=create_cloud_llm(),
)

analyst = Agent(
    role="Analyst", 
    goal="Analyze research on {topic}",
    backstory="Expert analyst",
    llm=create_cloud_llm(),
)

writer = Agent(
    role="Writer",
    goal="Write report on {topic}",
    backstory="Expert writer",
    llm=create_cloud_llm(),
)

# Create crew with async execution
crew = Crew(
    agents=[researcher, analyst, writer],
    tasks=[
        Task(description="Research {topic}", agent=researcher, async_execution=True),
        Task(description="Analyze findings", agent=analyst, async_execution=True),
        Task(description="Write final report", agent=writer),
    ],
    verbose=True,
)

result = crew.kickoff(inputs={"topic": "AI governance"})
```

---

## 7. Available Ollama Cloud Models

Query available models via API:

```bash
curl https://ollama.com/api/tags \
  -H "Authorization: Bearer $OLLAMA_API_KEY"
```

Or browse: [ollama.com/search?c=cloud](https://ollama.com/search?c=cloud)

Common cloud models:
- `gpt-oss:120b` - Large general-purpose model
- `gpt-oss:120b-cloud` - Same model, cloud variant naming

---

## 8. Error Handling

```python
import os
from crewai import LLM
from requests.exceptions import RequestException

def create_llm_with_fallback() -> LLM:
    """Create LLM with validation and fallback."""
    api_key = os.getenv('OLLAMA_API_KEY')
    
    if not api_key:
        raise EnvironmentError(
            "OLLAMA_API_KEY not set. "
            "Get your key at https://ollama.com/settings/keys"
        )
    
    try:
        llm = LLM(
            model=f"ollama/{os.getenv('OLLAMA_MODEL', 'gpt-oss:120b')}",
            base_url=os.getenv('OLLAMA_BASE_URL', 'https://ollama.com'),
            api_key=api_key,
        )
        return llm
    except Exception as e:
        raise ConnectionError(f"Failed to initialize Ollama Cloud LLM: {e}")
```

---

## 9. Environment Switching

Support multiple environments (dev/staging/prod):

```bash
# .env.development
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b
# No API key needed for local

# .env.production  
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_MODEL=gpt-oss:120b
OLLAMA_API_KEY=prod_key_here
OLLAMA_CLOUD_ENABLED=true
```

```python
from dotenv import load_dotenv
import os

# Load environment-specific config
env = os.getenv('ENVIRONMENT', 'development')
load_dotenv(f'.env.{env}')
```

---

## 10. Complete Example: config.py

```python
"""
config.py - CrewAI Ollama Cloud Configuration Module

This module provides a unified configuration interface for CrewAI
applications, supporting both local Ollama and Ollama Cloud.
"""

import os
from dataclasses import dataclass
from typing import Optional
import yaml
from crewai import LLM


@dataclass
class OllamaConfig:
    """Configuration for Ollama LLM provider."""
    base_url: str
    model: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120
    
    @property
    def is_cloud(self) -> bool:
        """Check if configured for Ollama Cloud."""
        return 'ollama.com' in self.base_url
    
    def to_llm(self) -> LLM:
        """Convert config to CrewAI LLM instance."""
        kwargs = {
            'model': f"ollama/{self.model}",
            'base_url': self.base_url,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }
        
        if self.is_cloud:
            if not self.api_key:
                raise ValueError("API key required for Ollama Cloud")
            kwargs['api_key'] = self.api_key
            
        return LLM(**kwargs)


def load_ollama_config(config_path: Optional[str] = None) -> OllamaConfig:
    """
    Load Ollama configuration from environment and optional config file.
    
    Priority (highest to lowest):
    1. Environment variables
    2. Config file values
    3. Default values
    
    Environment variables:
    - OLLAMA_BASE_URL: Base URL for Ollama API
    - OLLAMA_MODEL: Model name to use
    - OLLAMA_API_KEY: API key (required for cloud)
    - OLLAMA_CLOUD_ENABLED: Set to 'true' to use cloud defaults
    
    Args:
        config_path: Optional path to YAML config file
        
    Returns:
        OllamaConfig instance
    """
    # Defaults based on cloud vs local
    use_cloud = os.getenv('OLLAMA_CLOUD_ENABLED', '').lower() == 'true'
    
    defaults = {
        'base_url': 'https://ollama.com' if use_cloud else 'http://localhost:11434',
        'model': 'gpt-oss:120b' if use_cloud else 'llama3:70b',
        'temperature': 0.7,
        'max_tokens': 4096,
        'timeout': 120,
    }
    
    # Load from config file if provided
    file_config = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
            file_config = raw_config.get('llm', {})
            file_config.update(raw_config.get('settings', {}))
    
    # Build final config with priority
    return OllamaConfig(
        base_url=os.getenv('OLLAMA_BASE_URL', file_config.get('base_url', defaults['base_url'])),
        model=os.getenv('OLLAMA_MODEL', file_config.get('model', defaults['model'])),
        api_key=os.getenv('OLLAMA_API_KEY', file_config.get('api_key')),
        temperature=float(os.getenv('OLLAMA_TEMPERATURE', file_config.get('temperature', defaults['temperature']))),
        max_tokens=int(os.getenv('OLLAMA_MAX_TOKENS', file_config.get('max_tokens', defaults['max_tokens']))),
        timeout=int(os.getenv('OLLAMA_TIMEOUT', file_config.get('timeout', defaults['timeout']))),
    )


# Convenience function
def get_llm(config_path: Optional[str] = None) -> LLM:
    """Get configured LLM instance ready for use with CrewAI."""
    config = load_ollama_config(config_path)
    return config.to_llm()


# Example usage
if __name__ == "__main__":
    # Test configuration loading
    config = load_ollama_config()
    print(f"Provider: {'Ollama Cloud' if config.is_cloud else 'Local Ollama'}")
    print(f"Base URL: {config.base_url}")
    print(f"Model: {config.model}")
    print(f"API Key: {'*****' if config.api_key else 'Not set'}")
```

---

## 11. Migration Checklist

When migrating from local Ollama to Ollama Cloud:

- [ ] Create Ollama Cloud account
- [ ] Generate API key at ollama.com/settings/keys
- [ ] Add `OLLAMA_API_KEY` to environment/.env
- [ ] Update `OLLAMA_BASE_URL` to `https://ollama.com`
- [ ] Update model names to cloud-available models
- [ ] Test with single agent before full crew
- [ ] Update CI/CD secrets if applicable
- [ ] Remove local Ollama dependency from Dockerfile (optional)

---

## 12. Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Missing or invalid API key | Check `OLLAMA_API_KEY` is set correctly |
| Model not found | Invalid model name | Check available models at ollama.com/search?c=cloud |
| Connection timeout | Network issues or rate limiting | Increase timeout, implement retry logic |
| SSL errors | Proxy or cert issues | Check network configuration |

---

## Appendix A: Quick Reference

### Environment Variables

```bash
# Required for Ollama Cloud
OLLAMA_API_KEY=your_key_here

# Optional (with defaults)
OLLAMA_BASE_URL=https://ollama.com      # Default: https://ollama.com
OLLAMA_MODEL=gpt-oss:120b               # Default: gpt-oss:120b
OLLAMA_CLOUD_ENABLED=true               # Enables cloud defaults
OLLAMA_TEMPERATURE=0.7                  # Default: 0.7
OLLAMA_MAX_TOKENS=4096                  # Default: 4096
OLLAMA_TIMEOUT=120                      # Default: 120 seconds
```

### Minimal Code

```python
import os
from crewai import LLM, Agent

llm = LLM(
    model="ollama/gpt-oss:120b",
    base_url="https://ollama.com",
    api_key=os.getenv("OLLAMA_API_KEY"),
)

agent = Agent(role="Assistant", goal="Help user", backstory="Expert", llm=llm)
```