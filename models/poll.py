from enum import IntEnum, auto
from typing import Any, Literal, TypeAlias
from uuid import UUID, uuid4

from pydantic import Field, validator

from models import BaseModel, account


class QuestionType(IntEnum):
    selector = auto()
    slider = auto()
    top_list = auto()
    text = auto()


class BaseQuestion(BaseModel):
    question_id: UUID = Field(default_factory=uuid4)
    question_type: QuestionType
    label: str = Field(min_length=1)
    description: str | None = Field(None, min_length=1)
    image: str | None = None
    hide_results: bool = False


class Option(BaseModel):
    label: str
    image: str | None


class BaseOptionQuestion(BaseQuestion):
    options: list[Option] = []

    @validator("options")
    def options_validator(
        cls,
        value: list[Option],
        values: dict[str, Any],
        **kwargs: Any,
    ) -> list[Option]:
        assert len(value) >= 2, "len(options) >= 2"
        return value


class SelectorQuestion(BaseOptionQuestion):
    question_type: Literal[QuestionType.selector] = QuestionType.selector
    min_checked: int = 1
    max_checked: int | None = None

    @validator("max_checked")
    def max_checked_validator(
        cls,
        value: int | None,
        values: dict[str, Any],
        **kwargs: Any,
    ) -> int | None:
        assert (
            value is None
            or "options" not in values
            or "min_checked" not in values
            or values["min_checked"] <= value <= len(values["options"])
        ), "min_checked <= max_checked <= len(options)"
        return value


class SliderQuestion(BaseOptionQuestion):
    question_type: Literal[QuestionType.slider] = QuestionType.slider
    min_value: int = 1
    max_value: int = 5

    @validator("max_value")
    def max_value_validator(
        cls,
        value: int,
        values: dict[str, Any],
        **kwargs: Any,
    ) -> int:
        assert (
            "min_value" not in values or value > values["min_value"]
        ), "max_value > min_value"
        return value


class TopListQuestion(BaseOptionQuestion):
    question_type: Literal[QuestionType.top_list] = QuestionType.top_list
    min_ranks: int = 1
    max_ranks: int | None = None

    @validator("max_ranks")
    def max_ranks_validator(
        cls,
        value: int | None,
        values: dict[str, Any],
        **kwargs: Any,
    ) -> int | None:
        assert (
            value is None
            or "options" not in values
            or "min_ranks" not in values
            or values["min_ranks"] <= value <= len(values["options"])
        ), "min_ranks <= max_ranks <= len(options)"
        return value


class TextQuestion(BaseQuestion):
    question_type: Literal[QuestionType.text] = QuestionType.text
    min_length: int | None = None
    max_length: int | None = None

    @validator("max_length")
    def max_length_validator(
        cls,
        value: int | None,
        values: dict[str, Any],
        **kwargs: Any,
    ) -> int | None:
        assert (
            value is None
            or "min_length" not in values
            or values["min_length"] is None
            or values["min_length"] < value
        ), "min_length < max_length"
        return value


Question: TypeAlias = SelectorQuestion | SliderQuestion | TopListQuestion | TextQuestion


class PlotType(IntEnum):
    bar = auto()
    pie = auto()
    doughnut = auto()
    radar = auto()
    area = auto()
    word_cloud = auto()


class BasePlot(BaseModel):
    plot_type: PlotType
    name: str = Field(min_length=1)
    questions: list[Question] = []

    @property
    def uuids(self) -> dict[UUID, Question]:
        return {q.question_id: q for q in self.questions}

    @validator("questions")
    def questions_validator(
        cls,
        value: list[Question],
        values: dict[str, Any],
        **kwargs: Any,
    ) -> list[Question]:
        assert len(value) >= 1, "len(questions) >= 1"

        question_type = value[0].question_type
        uuids = {value[0].question_id}
        for question in value[1:]:
            assert (
                question.question_type == question_type
            ), "All questions must be of the same type"
            assert (
                question.question_id not in uuids
            ), "All questions must be have different id's"
            uuids.add(question.question_id)

        return value


class BaseNumberPlot(BasePlot):
    @validator("questions")
    def questions_validator(
        cls,
        value: list[Question],
        values: dict[str, Any],
        **kwargs: Any,
    ) -> list[Question]:
        assert all(
            question.question_type
            in (
                QuestionType.selector,
                QuestionType.slider,
                QuestionType.top_list,
            )
            for question in value
        ), "Question must only have these types: selector, slider and top_list"

        return value


class BarPlot(BaseNumberPlot):
    plot_type: Literal[PlotType.bar] = PlotType.bar


class PiePlot(BaseNumberPlot):
    plot_type: Literal[PlotType.pie] = PlotType.pie


class DoughnutPlot(BaseNumberPlot):
    plot_type: Literal[PlotType.doughnut] = PlotType.doughnut


class RadarPlot(BaseNumberPlot):
    plot_type: Literal[PlotType.radar] = PlotType.radar


class AreaPlot(BaseNumberPlot):
    plot_type: Literal[PlotType.area] = PlotType.area


class WordCloudPlot(BasePlot):
    plot_type: Literal[PlotType.word_cloud] = PlotType.word_cloud


Plot: TypeAlias = (
    BarPlot | PiePlot | DoughnutPlot | RadarPlot | AreaPlot | WordCloudPlot
)


class PollSchema(BaseModel):
    name: str = Field(min_length=1)
    plots: list[Plot] = []

    @property
    def uuids(self) -> dict[UUID, Question]:
        return {u: q for p in self.plots for u, q in p.uuids.items()}

    @validator("plots")
    def plots_validator(
        cls,
        value: list[Plot],
        values: dict[str, Any],
        **kwargs: Any,
    ) -> list[Plot]:
        assert len(value) >= 1, "len(plots) >= 1"
        uuids = set()
        for plots in value:
            for question in plots.questions:
                assert (
                    question.question_id not in uuids
                ), "All questions must be have different id's"
                uuids.add(question.question_id)
        return value


class Poll(BaseModel):
    id: int
    owner: account.User
    poll: PollSchema
