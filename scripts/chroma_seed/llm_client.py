from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from .models import TitleRecord

_HUMAN_PROMPT_TEMPLATE = """
You are generating a short film description for a catalog.

Write a clear, neutral summary of the film.

Requirements:
- 3-4 sentences
- 70-100 words
- No opinions, ratings, or promotional language
- No actor names
- Focus on premise, main characters, and central conflict
- Mention setting only if relevant
- Use natural, readable language

Output plain text only.
"""

_EMBEDDING_PROMPT_TEMPLATE = """
You are generating a structured semantic description of a film for embedding and similarity search.

Rules:
- Be concise, factual, and information-dense.
- Do NOT include opinions, ratings, or subjective language.
- Do NOT use marketing phrases.
- Use consistent vocabulary.
- Output in plain text (no JSON, no markdown).
- Max 120 words per description
- Use simple vocabulary. Avoid rare words and synonyms.
- Prefer canonical genre and theme labels.

Fill in all fields in this structure:
Genres: ...
Setting: ...
Themes: ...
Plot: ...
Characters: ...
Style: ...
Director: ...
Writer: ...
Starring: ...
"""


@dataclass(slots=True)
class TextGenerationClient:
    model: str
    max_retries: int
    human_max_tokens: int
    embedding_max_tokens: int
    _client: Any = field(init=False, repr=False)
    _sampling_params_cls: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            from vllm import LLM, SamplingParams  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The vllm package is required for Chroma seed generation."
            ) from exc
        self._client = LLM(model=self.model)
        self._sampling_params_cls = SamplingParams

    def generate_human_descriptions(self, titles: list[TitleRecord]) -> dict[str, str]:
        return self._generate_descriptions(
            titles=titles,
            system_prompt=_HUMAN_PROMPT_TEMPLATE,
            max_tokens=self.human_max_tokens,
        )

    def generate_embedding_descriptions(
        self,
        titles: list[TitleRecord],
    ) -> dict[str, str]:
        return self._generate_descriptions(
            titles=titles,
            system_prompt=_EMBEDDING_PROMPT_TEMPLATE,
            max_tokens=self.embedding_max_tokens,
        )

    def _generate_descriptions(
        self,
        titles: list[TitleRecord],
        system_prompt: str,
        max_tokens: int,
    ) -> dict[str, str]:
        prompts = [_build_prompt(system_prompt, title) for title in titles]
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                sampling_params = self._sampling_params_cls(
                    temperature=0,
                    max_tokens=max_tokens,
                )
                raw_outputs = self._client.generate(prompts, sampling_params)
                parsed = _parse_batch_outputs(raw_outputs, titles)
                return parsed
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self.max_retries:
                    break

        raise RuntimeError(
            "Text generation failed after max retries."
        ) from last_error


def _build_prompt(system_prompt: str, title: TitleRecord) -> str:
    return (
        f"{system_prompt.strip()}\n\n"
        "Film:\n"
        f"Title: {title.title}\n"
        f"Year: {title.start_year}"
    )


def _parse_batch_outputs(
    raw_outputs: object,
    titles: list[TitleRecord],
) -> dict[str, str]:
    if not isinstance(raw_outputs, list):
        raise ValueError("Model output must be a list.")
    outputs_list = cast(list[object], raw_outputs)
    if len(outputs_list) != len(titles):
        raise ValueError("Model output item count did not match the requested batch.")

    result: dict[str, str] = {}
    for index, title in enumerate(titles):
        output_item = outputs_list[index]
        text = _extract_output_text(output_item)
        if not text:
            raise ValueError("Model output text must be non-empty for each requested title.")
        result[title.title_id] = text

    return result


def _extract_output_text(output_item: object) -> str:
    candidates_obj = getattr(output_item, "outputs", None)
    if not isinstance(candidates_obj, list) or not candidates_obj:
        raise ValueError("Model output item must include at least one candidate.")
    candidates = cast(list[object], candidates_obj)

    first_candidate = candidates[0]
    text_obj = getattr(first_candidate, "text", None)
    if not isinstance(text_obj, str):
        raise ValueError("Model output candidate text must be a string.")
    return text_obj.strip()
