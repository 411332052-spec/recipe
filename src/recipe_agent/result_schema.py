"""claude -p 回傳內容的約定、拆包、檢查。

原則：不相信 Claude 回來的任何東西。格式不合就丟 InvalidResult，由呼叫端決定重試或回覆失敗，
絕不讓程式當掉。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

MAX_PHOTOS = 4
SERVINGS = 2  # 需求固定 2 人份，不採用 Claude 給的值

_MAX_DISH = 50
_MAX_ITEM = 60
_MAX_STEP = 500
_MAX_STEPS = 30
_MAX_ITEMS = 30
_MAX_NOTE = 200


class InvalidResult(Exception):
    """Claude 回傳的東西不能用。"""


@dataclass
class Recipe:
    from_photos: list[str]
    pantry: list[str]
    to_prepare: list[str]
    steps: list[str]
    servings: int = SERVINGS
    cook_minutes: int | None = None


@dataclass
class PhotoInfo:
    index: int
    short_name: str


@dataclass
class AnalysisResult:
    is_food: bool
    ingredients: list[str]
    dish_name: str
    photos: list[PhotoInfo]
    skipped_note: str
    recipe: Recipe | None

    def name_for(self, index: int) -> str:
        for p in self.photos:
            if p.index == index:
                return p.short_name
        return f"照片{index}"


# JSON schema 交給 claude -p 的 --json-schema。檢查的主力仍是下面的 parse_result。
JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "is_food": {"type": "boolean"},
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "dish_name": {"type": "string"},
        "photos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "short_name": {"type": "string"}},
                "required": ["index", "short_name"],
            },
        },
        "skipped_note": {"type": "string"},
        "recipe": {
            "type": "object",
            "properties": {
                "servings": {"type": "integer"},
                "cook_minutes": {"type": "integer"},
                "from_photos": {"type": "array", "items": {"type": "string"}},
                "pantry": {"type": "array", "items": {"type": "string"}},
                "to_prepare": {"type": "array", "items": {"type": "string"}},
                "steps": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "required": ["is_food", "ingredients"],
}


# ---------- 拆包 ----------


def extract_json_object(text: str) -> dict:
    """從 Claude 的文字答案裡取出 JSON 物件（容忍前後說明文字與 ``` 標記）。"""
    text = (text or "").strip()
    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            return obj
    raise InvalidResult("答案不是合法的 JSON 物件")


def unwrap_cli_output(stdout: str) -> dict:
    """剝掉 --output-format json 的外層，回傳 Claude 的答案（dict）。"""
    try:
        outer = json.loads(stdout)
    except (json.JSONDecodeError, ValueError, TypeError):
        raise InvalidResult("claude 的外層輸出不是 JSON") from None
    if not isinstance(outer, dict):
        raise InvalidResult("claude 的外層輸出不是物件")
    if outer.get("is_error"):
        raise InvalidResult("claude 回報錯誤")
    structured = outer.get("structured_output")
    if isinstance(structured, dict):
        return structured
    result = outer.get("result")
    if isinstance(result, str):
        return extract_json_object(result)
    raise InvalidResult("claude 的輸出裡找不到答案")


# ---------- 欄位整理 ----------


def coerce_int(value, low: int, high: int) -> int | None:
    """能安心當整數就轉成整數，否則回傳 None（不丟例外）。"""
    if isinstance(value, bool):
        return None
    result: int | None = None
    if isinstance(value, int):
        result = value
    elif isinstance(value, float):
        if value == value and value not in (float("inf"), float("-inf")) and value == int(value):
            result = int(value)
    elif isinstance(value, str):
        s = value.strip()
        if re.fullmatch(r"\d{1,6}", s):
            result = int(s)
    if result is None or not (low <= result <= high):
        return None
    return result


def _text(value, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    s = " ".join(value.split()) if "\n" not in value else value.strip()
    if not s:
        return None
    return s[:limit]


def _str_list(value, item_limit: int, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        s = _text(item, item_limit)
        if s:
            out.append(s)
        if len(out) >= max_items:
            break
    return out


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise InvalidResult("is_food 不是 true / false")


def parse_result(data: dict, photo_count: int) -> AnalysisResult:
    """檢查並整理 Claude 的答案。不合格丟 InvalidResult。"""
    if not isinstance(data, dict):
        raise InvalidResult("答案不是物件")

    if "is_food" not in data:
        raise InvalidResult("缺少 is_food")
    is_food = _to_bool(data["is_food"])

    ingredients = _str_list(data.get("ingredients"), _MAX_ITEM, _MAX_ITEMS)
    if not ingredients:
        raise InvalidResult("ingredients 是空的或格式不對")

    photos = _parse_photos(data.get("photos"), photo_count)
    skipped_note = _text(data.get("skipped_note"), _MAX_NOTE) or ""

    if not is_food:
        return AnalysisResult(False, ingredients, "", photos, skipped_note, None)

    dish_name = _text(data.get("dish_name"), _MAX_DISH)
    if not dish_name:
        raise InvalidResult("食材照片缺少 dish_name")
    raw_recipe = data.get("recipe")
    if not isinstance(raw_recipe, dict):
        raise InvalidResult("食材照片缺少 recipe")
    steps = _str_list(raw_recipe.get("steps"), _MAX_STEP, _MAX_STEPS)
    if not steps:
        raise InvalidResult("recipe.steps 是空的")

    recipe = Recipe(
        from_photos=_str_list(raw_recipe.get("from_photos"), _MAX_ITEM, _MAX_ITEMS),
        pantry=_str_list(raw_recipe.get("pantry"), _MAX_ITEM, _MAX_ITEMS),
        to_prepare=_str_list(raw_recipe.get("to_prepare"), _MAX_ITEM, _MAX_ITEMS),
        steps=steps,
        servings=SERVINGS,
        cook_minutes=coerce_int(raw_recipe.get("cook_minutes"), 1, 600),
    )
    return AnalysisResult(True, ingredients, dish_name, photos, skipped_note, recipe)


def _parse_photos(raw, photo_count: int) -> list[PhotoInfo]:
    """photos 有問題只退回預設，不算失敗。"""
    if not isinstance(raw, list):
        return []
    out: list[PhotoInfo] = []
    used: set[int] = set()
    for position, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        name = _text(item.get("short_name"), _MAX_ITEM)
        if not name:
            continue
        idx = coerce_int(item.get("index"), 1, photo_count)
        if idx is None or idx in used:
            idx = position
        if idx > photo_count or idx in used:
            continue
        used.add(idx)
        out.append(PhotoInfo(idx, name))
    return out
