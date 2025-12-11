"""OpenRouter API client with tool calling support."""

import json
import os
from typing import Any, Optional
import requests


class OpenRouterPrivacyError(RuntimeError):
    """Raised when OpenRouter rejects a request due to data/privacy policy settings.

    This helps callers provide actionable guidance to users (e.g. enable free model
    publication in OpenRouter settings or choose a non-free model).
    """
    pass


class OpenRouterClient:
    """Client for OpenRouter API with tool calling support."""

    def __init__(self, api_key: Optional[str] = None, model: str = "anthropic/claude-sonnet-4"):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model identifier (default: Claude Sonnet 4)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")

        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

        # For free models, we need to allow data publication
        # See: https://openrouter.ai/docs#data-privacy
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/coscientist",  # Optional, for rankings
            "X-Title": "CoScientist",  # Optional, shows in rankings
        }

        # Check if using a free model and set appropriate data policy
        # Allow forcing the data-policy header via env var for CI or user opt-in
        force_allow = os.getenv("OPENROUTER_ALLOW_PUBLISH", "").lower() in ("1", "true", "yes")
        if ":free" in model.lower() or force_allow:
            # Free models require allowing data to be published
            self.headers["OpenRouter-Data-Policy"] = "allow-all"

    def create_message(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
    ) -> dict[str, Any]:
        """Send a message to OpenRouter with optional tool definitions.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter

        Returns:
            Response dict from OpenRouter API
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }

        # For free models, explicitly allow data publication
        if ":free" in self.model.lower():
            payload["allow_fallback"] = True

        # Add tools if provided
        if tools:
            payload["tools"] = tools

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=120,
        )
        # If we get a non-200 response, try to detect the privacy/data-policy error
        # that OpenRouter returns for free models when data publication is not enabled.
        if response.status_code != 200:
            # Try to extract an error message from JSON body or plain text
            err_msg = None
            try:
                body = response.json()
                # body may be {"error": {"message": "..."}} or similar
                if isinstance(body, dict):
                    err_msg = body.get("error", {}).get("message") or body.get("message") or str(body)
                else:
                    err_msg = str(body)
            except Exception:
                # Fallback to raw text
                err_msg = response.text or ""

            err_lower = (err_msg or "").lower()

            # Broad keyword matching to catch variations of the privacy error
            privacy_signals = [
                "no endpoints found",
                "data policy",
                "free model publication",
                "publication",
                "data privacy",
                "matching your data policy",
            ]

            if response.status_code in (403, 404) and any(sig in err_lower for sig in privacy_signals):
                # Attempt an automatic retry with the data-policy header and payload flag.
                # This fixes the root cause in many cases where the user simply needs
                # to allow free-model data publication. We set the header locally and
                # resend the request once.
                self.headers["OpenRouter-Data-Policy"] = "allow-all"
                payload["allow_fallback"] = True

                retry_resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                )

                if retry_resp.status_code == 200:
                    return retry_resp.json()

                # If retry also failed, raise a clear, actionable error
                raise OpenRouterPrivacyError(
                    "OpenRouter API error: No endpoints found matching your data policy even after adding the data-policy header. "
                    "Please enable 'Free model publication' at https://openrouter.ai/settings/privacy or choose a non-free model. "
                    f"(server responses: first_status={response.status_code}, first_body={err_msg!r}, retry_status={retry_resp.status_code}, retry_body={retry_resp.text})"
                )

            # Fallback generic error for other status codes
            raise RuntimeError(f"OpenRouter API error {response.status_code}: {response.text}")

        return response.json()

    def extract_tool_calls(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract tool calls from API response.

        Args:
            response: Response dict from create_message

        Returns:
            List of tool call dicts with 'id', 'name', 'input'
        """
        tool_calls = []

        if not response.get("choices"):
            return tool_calls

        message = response["choices"][0].get("message", {})

        # Handle tool_calls field (standard OpenAI format)
        if "tool_calls" in message:
            for call in message["tool_calls"]:
                if call.get("type") == "function":
                    func = call.get("function", {})
                    arguments_str = func.get("arguments", "{}")

                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError:
                        # Skip malformed tool calls
                        continue

                    # Validate arguments are not empty for functions that require parameters
                    tool_name = func.get("name", "")
                    if tool_name == "execute_python" and not arguments.get("code"):
                        # Skip execute_python calls without code parameter
                        continue

                    tool_calls.append({
                        "id": call.get("id", ""),
                        "name": tool_name,
                        "input": arguments
                    })

        return tool_calls

    def get_response_text(self, response: dict[str, Any]) -> str:
        """Extract text content from API response.

        Args:
            response: Response dict from create_message

        Returns:
            Text content from the response
        """
        if not response.get("choices"):
            return ""

        message = response["choices"][0].get("message", {})
        return message.get("content", "")
