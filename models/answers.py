from typing import Any, TypeAlias
from uuid import UUID

from pydantic import validator

from models import BaseModel, account, poll


class BaseValue(BaseModel):
    question_id: UUID
    question_type: poll.QuestionType


class SelectorValue(BaseValue):
    question_type = poll.QuestionType.selector
    selected: set[int]

    def check(self, question: poll.SelectorQuestion) -> None:
        max_checked: int = (
            question.max_checked
            if question.max_checked is not None
            else len(question.options)
        )

        assert (
            question.min_checked <= len(self.selected) <= max_checked
        ), f"{question.min_checked} <= len(selected) <= {max_checked}"
        assert all(
            [0 <= s < len(question.options) for s in self.selected]
        ), f"0 <= select < {len(question.options)}"


class SliderValue(BaseValue):
    question_type = poll.QuestionType.slider
    sliders: list[int]

    def check(self, question: poll.SliderQuestion) -> None:
        assert len(self.sliders) == len(
            question.options
        ), f"len(values) == {len(question.options)}"
        assert all(
            [question.min_value <= s <= question.max_value for s in self.sliders]
        ), f"{question.min_value} <= slider <= {question.max_value}"


class TopListValue(BaseValue):
    question_type = poll.QuestionType.top_list
    ranks: list[int]

    def check(self, question: poll.TopListQuestion) -> None:
        max_ranks: int = (
            question.max_ranks
            if question.max_ranks is not None
            else len(question.options)
        )

        assert (
            question.min_ranks <= len(self.ranks) <= max_ranks
        ), f"{question.min_ranks} <= len(ranks) <= {max_ranks}"
        assert len(self.ranks) == len(set(self.ranks)), "All ranks must be unique"
        assert all(
            [0 <= rank < len(question.options) for rank in self.ranks]
        ), f"0 <= rank < {len(question.options)}"


class TextValue(BaseValue):
    question_type = poll.QuestionType.text
    text: str

    def check(self, question: poll.TextQuestion) -> None:
        assert (
            question.min_length is None or len(self.text) >= question.min_length
        ), f"len(value) >= {question.min_length}"
        assert (
            question.max_length is None or len(self.text) <= question.max_length
        ), f"len(value) <= {question.max_length}"


Value: TypeAlias = SelectorValue | SliderValue | TopListValue | TextValue


class AnswerSchema(BaseModel):
    values: list[Value]

    @validator("values")
    def values_validator(
        cls,
        value: list[Value],
        values: dict[str, Any],
        **kwargs: Any,
    ) -> list[Value]:
        uuids = set()
        for v in value:
            assert (
                v.question_id not in uuids
            ), "All values must be linked to different questions"
            uuids.add(v.question_id)

        return value


class Answer(BaseModel):
    id: int
    poll: poll.Poll
    answerer: account.User | None
    answer: AnswerSchema

    @validator("answer")
    def answer_validator(
        cls,
        value: AnswerSchema,
        values: dict[str, Any],
        **kwargs: Any,
    ) -> AnswerSchema:
        uuids: dict[UUID, poll.Question] = values["poll"].poll.uuids
        for v in value.values:
            assert (
                v.question_id in uuids
            ), f"Question with id {v.question_id} is not included in the poll"
            assert (
                uuids[v.question_id].question_type == v.question_type
            ), f"Question and value has different types ({v.question_type} != {uuids[v.question_id].question_type})"
            v.check(uuids[v.question_id])  # type: ignore[arg-type]
        return value
