import json

import pytest

from recipe_agent.result_schema import (
    InvalidResult,
    coerce_int,
    extract_json_object,
    parse_result,
    unwrap_cli_output,
)

GOOD = {
    "is_food": True,
    "dish_name": "番茄炒蛋",
    "ingredients": ["番茄", "雞蛋"],
    "photos": [{"index": 1, "short_name": "番茄"}, {"index": 2, "short_name": "雞蛋"}],
    "recipe": {
        "servings": 2,
        "cook_minutes": 15,
        "from_photos": ["番茄 2 顆"],
        "pantry": ["鹽 1/2 小匙"],
        "to_prepare": [],
        "steps": ["切塊", "炒"],
    },
}


def test_good_food_result():
    r = parse_result(GOOD, 2)
    assert r.is_food and r.dish_name == "番茄炒蛋" and r.recipe.cook_minutes == 15
    assert r.name_for(1) == "番茄" and r.name_for(2) == "雞蛋" and r.name_for(3) == "照片3"


def test_servings_always_two_even_if_claude_says_otherwise():
    data = json.loads(json.dumps(GOOD))
    data["recipe"]["servings"] = 99
    assert parse_result(data, 2).recipe.servings == 2


def test_nonfood_needs_only_is_food_and_ingredients():
    r = parse_result({"is_food": False, "ingredients": ["貓"]}, 1)
    assert not r.is_food and r.ingredients == ["貓"] and r.recipe is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("is_food"),
        lambda d: d.update(is_food="也許"),
        lambda d: d.update(ingredients=[]),
        lambda d: d.update(ingredients="番茄"),
        lambda d: d.pop("dish_name"),
        lambda d: d.pop("recipe"),
        lambda d: d["recipe"].update(steps=[]),
        lambda d: d["recipe"].update(steps="直接煮"),
    ],
)
def test_invalid_results_raise_invalid_result_not_other_errors(mutate):
    data = json.loads(json.dumps(GOOD))
    mutate(data)
    with pytest.raises(InvalidResult):
        parse_result(data, 2)


def test_is_food_string_true_false_accepted():
    assert parse_result({**GOOD, "is_food": "true"}, 2).is_food is True
    assert parse_result({"is_food": "false", "ingredients": ["杯子"]}, 1).is_food is False


@pytest.mark.parametrize(
    "value,expected",
    [(15, 15), (15.0, 15), ("15", 15), (" 15 ", 15), ("大約十五分鐘", None), ("15分鐘", None),
     (None, None), (True, None), (-3, None), (601, None), (15.5, None), (float("nan"), None), ([], None)],
)
def test_coerce_int(value, expected):
    assert coerce_int(value, 1, 600) == expected


def test_bad_cook_minutes_is_tolerated_not_fatal():
    data = json.loads(json.dumps(GOOD))
    data["recipe"]["cook_minutes"] = "大約十五分鐘"
    assert parse_result(data, 2).recipe.cook_minutes is None


def test_bad_photo_indexes_fall_back_to_order():
    data = json.loads(json.dumps(GOOD))
    data["photos"] = [{"index": "x", "short_name": "番茄"}, {"index": 1, "short_name": "雞蛋"}]
    r = parse_result(data, 2)
    assert [(p.index, p.short_name) for p in r.photos] == [(1, "番茄"), (2, "雞蛋")]


def test_long_text_is_truncated_not_rejected():
    data = json.loads(json.dumps(GOOD))
    data["dish_name"] = "菜" * 500
    data["recipe"]["steps"] = ["步" * 5000] * 100
    r = parse_result(data, 2)
    assert len(r.dish_name) == 50 and len(r.recipe.steps) == 30 and len(r.recipe.steps[0]) == 500


def test_extract_json_object_tolerates_fences_and_chatter():
    text = '好的，結果如下：\n```json\n{"a": 1}\n```\n希望有幫助'
    assert extract_json_object(text) == {"a": 1}


@pytest.mark.parametrize("text", ["", "不是 JSON", "[1, 2]", "{壞掉", None])
def test_extract_json_object_rejects_garbage(text):
    with pytest.raises(InvalidResult):
        extract_json_object(text)


def test_unwrap_prefers_structured_output():
    outer = {"is_error": False, "structured_output": {"is_food": False}, "result": "忽略我"}
    assert unwrap_cli_output(json.dumps(outer)) == {"is_food": False}


def test_unwrap_falls_back_to_result_text():
    outer = {"is_error": False, "result": '{"is_food": false}'}
    assert unwrap_cli_output(json.dumps(outer)) == {"is_food": False}


@pytest.mark.parametrize("stdout", ["", "亂碼", "[]", json.dumps({"is_error": True, "result": "x"}), json.dumps({"x": 1})])
def test_unwrap_rejects_bad_outer(stdout):
    with pytest.raises(InvalidResult):
        unwrap_cli_output(stdout)
