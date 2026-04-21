"""Tests for errordog.evaluator — expression evaluation against frame locals."""

from errordog.evaluator import eval_expression, reconstruct_namespace


class TestReconstructNamespace:
    def test_parses_int(self) -> None:
        ns, unavail = reconstruct_namespace({"x": "42"})
        assert ns == {"x": 42}
        assert unavail == []

    def test_parses_string(self) -> None:
        ns, _ = reconstruct_namespace({"name": "'hello'"})
        assert ns == {"name": "hello"}

    def test_parses_list(self) -> None:
        ns, _ = reconstruct_namespace({"items": "[1, 2, 3]"})
        assert ns == {"items": [1, 2, 3]}

    def test_parses_dict(self) -> None:
        ns, _ = reconstruct_namespace({"data": "{'a': 1, 'b': 2}"})
        assert ns == {"data": {"a": 1, "b": 2}}

    def test_parses_nested(self) -> None:
        ns, _ = reconstruct_namespace(
            {"items": "[{'price': 1500, 'qty': '1'}]"}
        )
        assert ns == {"items": [{"price": 1500, "qty": "1"}]}

    def test_skips_unparseable(self) -> None:
        ns, unavail = reconstruct_namespace({
            "x": "42",
            "conn": "<sqlite3.Connection object at 0x...>",
            "func": "<function foo at 0x...>",
        })
        assert ns == {"x": 42}
        assert set(unavail) == {"conn", "func"}

    def test_empty_locals(self) -> None:
        ns, unavail = reconstruct_namespace({})
        assert ns == {}
        assert unavail == []

    def test_parses_none_and_bool(self) -> None:
        ns, _ = reconstruct_namespace({"a": "None", "b": "True", "c": "False"})
        assert ns == {"a": None, "b": True, "c": False}


class TestEvalExpression:
    def test_simple_expression(self) -> None:
        result = eval_expression("x + 1", {"x": "10"})
        assert result["success"] is True
        assert result["result"] == "11"
        assert result["error"] is None

    def test_len_on_list(self) -> None:
        result = eval_expression("len(items)", {"items": "[1, 2, 3]"})
        assert result["success"] is True
        assert result["result"] == "3"

    def test_expression_with_error(self) -> None:
        result = eval_expression("1 / 0", {"x": "1"})
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]
        assert result["result"] is None

    def test_undefined_variable(self) -> None:
        result = eval_expression("y + 1", {"x": "10"})
        assert result["success"] is False
        assert "NameError" in result["error"]

    def test_reports_unavailable_vars(self) -> None:
        result = eval_expression(
            "x + 1",
            {"x": "10", "conn": "<Connection>"},
        )
        assert result["success"] is True
        assert result["result"] == "11"
        assert "conn" in result["unavailable_vars"]

    def test_no_sandboxing_builtins_accessible(self) -> None:
        result = eval_expression("type(x).__name__", {"x": "42"})
        assert result["success"] is True
        assert result["result"] == "'int'"

    def test_complex_expression(self) -> None:
        result = eval_expression(
            "sum(item['price'] * item['qty'] for item in items)",
            {"items": "[{'price': 100, 'qty': 2}, {'price': 200, 'qty': 3}]"},
        )
        assert result["success"] is True
        assert result["result"] == "800"

    def test_syntax_error_in_expression(self) -> None:
        result = eval_expression("x +", {"x": "1"})
        assert result["success"] is False
        assert "SyntaxError" in result["error"]
