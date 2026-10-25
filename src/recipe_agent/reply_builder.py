"""組回覆文字、組 Excel 的食譜欄、把長回覆切成 Discord 放得下的幾則。"""

from __future__ import annotations

from .result_schema import AnalysisResult

DISCORD_LIMIT = 1900  # Discord 單則上限 2000，留一點餘裕給 @ 提及

# ---- 固定訊息 ----
MSG_FAILED = "分析失敗，請再傳一次"
MSG_ONLY_PHOTOS = "目前只支援照片（JPG、PNG、WebP、GIF，單張 8 MB 以下）。"
MSG_BUSY = "你上一張還在處理中，請等結果出來再傳。"
MSG_ONLINE = "食譜機器人上線了！傳食材照片到這裡就可以拿到食譜。"
MSG_OFFLINE = "食譜機器人下線了。"
MSG_SHUTTING_DOWN = "機器人下線了，請上線後重傳。"
REACTION_QUEUED = "⏳"


def join_list(items: list[str]) -> str:
    return "、".join(items)


def ingredients_cell(result: AnalysisResult) -> str:
    """Excel「辨識到的食材清單」欄。非食材時寫「貓，不是食材」。"""
    text = join_list(result.ingredients)
    return text if result.is_food else f"{text}，不是食材"


def dish_cell(result: AnalysisResult) -> str:
    """Excel「推薦料理名稱」欄。非食材時寫「無」。"""
    return result.dish_name if result.is_food else "無"


def _ingredient_block(result: AnalysisResult) -> str:
    r = result.recipe
    assert r is not None
    head = f"【食材（{r.servings} 人份"
    if r.cook_minutes:
        head += f"，約 {r.cook_minutes} 分鐘"
    head += "）】"
    lines = [head]
    if r.from_photos:
        lines.append(f"照片裡有：{join_list(r.from_photos)}")
    if r.pantry:
        lines.append(f"家裡的基本調味料：{join_list(r.pantry)}")
    if r.to_prepare:
        lines.append(f"需另外準備：{join_list(r.to_prepare)}")
    return "\n".join(lines)


def recipe_cell(result: AnalysisResult) -> str:
    """Excel「完整食譜與步驟」欄。非食材時留空。"""
    if not result.is_food or result.recipe is None:
        return ""
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(result.recipe.steps, start=1))
    return f"{_ingredient_block(result)}\n\n【步驟】\n{steps}"


def build_reply(result: AnalysisResult, notes: list[str], mention: str) -> list[str]:
    """回覆上傳者的訊息（可能切成多則）。第一則開頭 @上傳者。"""
    if not result.is_food:
        text = f"{mention} 你傳的不是食材，是{join_list(result.ingredients)}。"
        if notes:
            text += "\n" + "\n".join(f"（{n}）" for n in notes)
        return pack_blocks([text])

    head = f"{mention}\n📷 辨識到的食材：{join_list(result.ingredients)}\n🍳 推薦料理：{result.dish_name}"
    if notes:
        head += "\n" + "\n".join(f"（{n}）" for n in notes)
    blocks = [head + "\n", _ingredient_block(result) + "\n", "【步驟】"]
    assert result.recipe is not None
    blocks += [f"{i}. {s}" for i, s in enumerate(result.recipe.steps, start=1)]
    return pack_blocks(blocks)


def pack_blocks(blocks: list[str], limit: int = DISCORD_LIMIT) -> list[str]:
    """把區塊依序塞進訊息，每則不超過 limit。只在區塊之間切；單一區塊太長才強制切開。"""
    messages: list[str] = []
    current = ""
    for block in blocks:
        for piece in _hard_split(block, limit):
            candidate = piece if not current else current + "\n" + piece
            if len(candidate) <= limit:
                current = candidate
            else:
                messages.append(current.rstrip())
                current = piece
    if current.strip():
        messages.append(current.rstrip())
    return messages


def _hard_split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]
