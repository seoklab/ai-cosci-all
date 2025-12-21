import os
from abc import ABC, abstractmethod

# Lazy imports - only import when needed
# This allows using OpenRouter without installing Gemini/Ollama dependencies

class ModelProvider(ABC):
    """Abstract base class for model providers."""

    @classmethod
    @abstractmethod
    def provider_instance(cls, model_name: str) -> bool:
        """Check if this provider can handle the given model name."""
        pass

    @property
    @abstractmethod
    def env_var_name(self) -> str:
        """The name of the environment variable required for the API key."""
        pass

    @abstractmethod
    def generate_content(self, prompt: str) -> str:
        """Generates content based on the prompt."""
        pass


class GeminiProvider(ModelProvider):
    """Provider for Google's Gemini models."""
    
    def __init__(self, config_api_key: str, model_name: str):
        # Lazy import - only import when actually using Gemini
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai is required for GeminiProvider. "
                "Install with: pip install google-generativeai"
            )
        
        # In GeminiProvider the order is first config_api_key for backward compatibility
        self.api_key = config_api_key or os.getenv(self.env_var_name)
        if not self.api_key:
            raise ValueError(f"Missing API key for {model_name}. Env var = {self.env_var_name}.")

        self.model_name = model_name
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    @classmethod
    def provider_instance(cls, model_name: str) -> bool:
        """For backward compatibility, Gemini is the default provider."""
        return True

    @property
    def env_var_name(self) -> str:
        return "GEMINI_API_KEY"
        
    def generate_content(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        return response.text


class OpenAIProvider(ModelProvider):
    """Provider for OpenAI models."""
    
    def __init__(self, config_api_key: str, model_name: str):
        # Lazy import - only import when actually using OpenAI
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai is required for OpenAIProvider. "
                "Install with: pip install openai"
            )
        
        self.api_key = os.getenv(self.env_var_name, config_api_key)
        if not self.api_key:
            raise ValueError(f"Missing API key for {model_name}. Env var = {self.env_var_name}.")

        self.model_name = model_name
        self.client = openai.OpenAI(api_key=self.api_key)

    @classmethod
    def provider_instance(cls, model_name: str) -> bool:
        return model_name.startswith("gpt") or model_name.startswith("o1")

    @property
    def env_var_name(self) -> str:
        return "OPENAI_API_KEY"
        
    def generate_content(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


class OpenRouterProvider(ModelProvider):
    """Provider for OpenRouter API (supports multiple models through OpenRouter)."""
    
    def __init__(self, config_api_key: str, model_name: str):
        # Lazy import - only import when actually using OpenRouter
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai is required for OpenRouterProvider. "
                "Install with: pip install openai"
            )
        
        self.api_key = os.getenv(self.env_var_name, config_api_key)
        if not self.api_key:
            raise ValueError(f"Missing API key for {model_name}. Env var = {self.env_var_name}.")

        # Remove 'openrouter/' prefix if present
        self.model_name = model_name.replace("openrouter/", "")
        
        # Initialize OpenAI client with OpenRouter base URL
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1"
        )

    @classmethod
    def provider_instance(cls, model_name: str) -> bool:
        """Check if model should use OpenRouter (models with 'openrouter/' prefix)."""
        return model_name.startswith("openrouter/")

    @property
    def env_var_name(self) -> str:
        return "OPENROUTER_API_KEY"
        
    def generate_content(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


class OllamaProvider(ModelProvider):
    """Provider for Ollama models."""

    def __init__(self, config_api_key: str, model_name: str):
        # Lazy import - only import when actually using Ollama
        try:
            import ollama
        except ImportError:
            raise ImportError(
                "ollama is required for OllamaProvider. "
                "Install with: pip install ollama"
            )
        
        self.api_key = os.getenv(self.env_var_name, config_api_key)
        self.model_name = model_name.lstrip("ollama/")

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = ollama.Client(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            headers=headers
        )

    @classmethod
    def provider_instance(cls, model_name: str) -> bool:
        return model_name.startswith("ollama/")

    @property
    def env_var_name(self) -> str:
        return "OLLAMA_API_KEY"

    def generate_content(self, prompt: str) -> str:
        response = self.client.chat(
            self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.message.content
