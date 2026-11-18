"""Turning a QuestionSet into concrete questions (shared by every game)."""

import random

from .models import DIFFICULTY_MAX, Operation, Operator, QuestionMode, QuestionSet


def _q(index: int, a: int, op: str, b: int) -> dict:
    answer = a + b if op == Operator.PLUS else a - b
    return {"id": f"q{index + 1}", "a": a, "op": op, "b": b, "answer": answer}


def generate(difficulty: str, operation: str, count: int, rng: random.Random) -> list[dict]:
    """Random questions inside the difficulty range; never negative, operands ≥ 1."""
    limit = DIFFICULTY_MAX[difficulty]
    out = []
    for i in range(count):
        op = operation
        if op == Operation.MIXED:
            op = rng.choice([Operation.ADD, Operation.SUB])
        if op == Operation.ADD:
            a = rng.randint(1, limit - 1)
            b = rng.randint(1, limit - a)
            out.append(_q(i, a, Operator.PLUS, b))
        else:
            a = rng.randint(2, limit)
            b = rng.randint(1, a)  # a - b ≥ 0
            out.append(_q(i, a, Operator.MINUS, b))
    return out


def questions_for(question_set: QuestionSet, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    if question_set.mode == QuestionMode.GENERATED:
        return generate(
            question_set.difficulty, question_set.operation, question_set.question_count, rng
        )
    rows = list(question_set.questions.all()[: question_set.question_count])
    return [
        _q(i, r.operand_a, r.operator, r.operand_b) | {"extra": r.extra} for i, r in enumerate(rows)
    ]


def answer_choices(answer: int, limit: int, rng: random.Random, n: int = 3) -> list[int]:
    """The answer plus nearby wrong options (±1, ±2…), all within 0..limit, shuffled."""
    choices = {answer}
    step = 1
    while len(choices) < n and step <= limit + n:
        for candidate in (answer + step, answer - step):
            if 0 <= candidate <= limit and len(choices) < n:
                choices.add(candidate)
        step += 1
    result = list(choices)
    rng.shuffle(result)
    return result
