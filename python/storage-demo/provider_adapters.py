from dataclasses import dataclass
from typing import Any, Protocol

from gateway_audit import TokenUsage
from gateway_execution import (
    ProviderExecutionError,
    ProviderResult,
    ProviderTimeout,
)


class ModelProvider(Protocol):
    def execute(
        self,
        deployment: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> ProviderResult:
        ...


@dataclass(frozen=True)
class ProviderConfig:
    endpoint: str
    api_key: str
    api_version: str = "2024-10-21"


class AzureOpenAIAdapter:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def execute(
        self,
        deployment: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> ProviderResult:

        try:
            from openai import AzureOpenAI, APITimeoutError, APIError

            client = AzureOpenAI(
                azure_endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                api_version=self.config.api_version,
                timeout=timeout_seconds,
                max_retries=0,
            )

            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=max_output_tokens,
            )

            output = response.choices[0].message.content or ""

            usage = response.usage

            return ProviderResult(
                output=output,
                usage=TokenUsage(
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                ),
            )

        except APITimeoutError as exc:
            raise ProviderTimeout("Azure provider timeout") from exc

        except APIError as exc:
            raise ProviderExecutionError(
                f"Azure provider API error: {exc.status_code}"
            ) from exc


class AWSBedrockAdapter:
    def execute(
        self,
        deployment: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> ProviderResult:
        raise NotImplementedError(
            "AWS Bedrock integration requires configured AWS infrastructure"
        )


class VertexAIAdapter:
    def execute(
        self,
        deployment: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> ProviderResult:
        raise NotImplementedError(
            "Vertex AI integration requires configured GCP infrastructure"
        )