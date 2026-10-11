"""Regression coverage for restricted in-memory Python execution."""

import pytest

from app.agent.tools.code_execution_tool import CodeExecutionTool


@pytest.mark.parametrize(
    "code, expected",
    [
        ("print(sum(range(1, 11)))", "55"),
        ("print(math.sqrt(81))", "9.0"),
        ("print(json.loads('{\\\"value\\\": 7}')[\"value\"])", "7"),
    ],
)
def test_restricted_python_allows_in_memory_calculations(code: str, expected: str):
    result = CodeExecutionTool().execute(code=code)

    assert result.success
    assert result.output.strip() == expected


@pytest.mark.parametrize(
    "code",
    [
        "import os\nprint(os.getcwd())",
        "print(open('secret.txt').read())",
        "print(__import__('socket'))",
        "print((()).__class__.__base__)",
    ],
)
def test_restricted_python_rejects_escape_attempts(code: str):
    result = CodeExecutionTool().execute(code=code)

    assert not result.success
    assert "Restricted execution rejected" in result.error
