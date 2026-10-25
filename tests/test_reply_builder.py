from recipe_agent.reply_builder import (
    DISCORD_LIMIT,
    build_reply,
    dish_cell,
    ingredients_cell,
    pack_blocks,
    recipe_cell,
)
from recipe_agent.result_schema import parse_result

FOOD = parse_result(
    {
        "is_food": True,
        "dish_name": "番茄炒蛋",
        "ingredients": ["番茄", "雞蛋"],
        "recipe": {"cook_minutes": 15, "from_photos": ["番茄 2 顆"], "pantry": ["鹽 1/2 小匙"], "to_prepare": ["蔥 1 根"],
                   "steps": ["切塊", "下鍋炒"]},
    },
    2,
)
NONFOOD = parse_result({"is_food": False, "ingredients": ["貓"]}, 1)
MENTION = "<@42>"


def test_food_reply_contains_everything_and_mentions_first():
    text = "\n".join(build_reply(FOOD, ["第 3 張是貓，不是食材，已略過"], MENTION))
    assert text.startswith(MENTION)
    for needle in ["番茄、雞蛋", "番茄炒蛋", "2 人份", "約 15 分鐘", "蔥 1 根", "1. 切塊", "2. 下鍋炒", "已略過"]:
        assert needle in text


def test_nonfood_reply_and_cells():
    assert build_reply(NONFOOD, [], MENTION) == ["<@42> 你傳的不是食材，是貓。"]
    assert ingredients_cell(NONFOOD) == "貓，不是食材"
    assert dish_cell(NONFOOD) == "無"
    assert recipe_cell(NONFOOD) == ""


def test_food_cells():
    assert ingredients_cell(FOOD) == "番茄、雞蛋" and dish_cell(FOOD) == "番茄炒蛋"
    assert recipe_cell(FOOD).startswith("【食材（2 人份，約 15 分鐘）】") and "1. 切塊" in recipe_cell(FOOD)


def test_long_recipe_split_without_cutting_steps():
    steps = [f"第{i}步" + "字" * 300 for i in range(1, 31)]
    long = parse_result({"is_food": True, "dish_name": "大菜", "ingredients": ["x"],
                         "recipe": {"steps": steps}}, 1)
    msgs = build_reply(long, [], MENTION)
    assert len(msgs) > 1 and all(len(m) <= DISCORD_LIMIT for m in msgs)
    assert msgs[0].startswith(MENTION) and not any(m.startswith(MENTION) for m in msgs[1:])
    joined = "\n".join(msgs)
    for i in range(1, 31):  # 每個步驟完整出現在某一則裡，沒被切半
        assert any(f"{i}. 第{i}步" + "字" * 300 in m for m in msgs)
    assert joined.count("【步驟】") == 1


def test_single_oversized_block_is_hard_split():
    msgs = pack_blocks(["字" * 5000])
    assert all(len(m) <= DISCORD_LIMIT for m in msgs) and sum(len(m) for m in msgs) == 5000
