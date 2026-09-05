"""Short style exemplars adapted from official HSK5 样卷 tone/structure.

Keep each block brief (few-shot only). Invent NEW situations at generation time;
do not copy these plots. Diversity: everyday / workplace-study / anecdote-or-opinion.
"""

from __future__ import annotations

# Three deliberately different situations each.

LISTENING_P1 = [
    """日常安排
F1: 明天上午九点我准时到。
M1: 我觉得还是提前几分钟吧。
NARR: 男的主要是什么意思？""",
    """职场合作
F1: 关于产品的价格，对方是什么意见？
M1: 价格是关键，如果我们不降低价格，他们恐怕就会放弃和我们合作。
NARR: 关于这次合作，下列哪项正确？""",
    """邻里生活
M1: 您是新搬来的吧？我就住楼上，有事儿就打个招呼。
F1: 好的，以后少不了麻烦您。
NARR: 他们是什么关系？""",
]

LISTENING_P2 = [
    """服务场景（餐厅）
F1: 您好！欢迎光临。请问您几位？
M1: 三个，我们提前预订了。
F1: 好的，请问先生您怎么称呼？
M1: 我姓李。
F1: 李先生，里面请，靠窗户的那个桌子是给您留的。
NARR: 根据对话，下列哪项正确？""",
    """天气与通勤
M1: 看天气预报了吗？明天天气怎么样？
F1: 有大雾，而且要降温，你明天多穿点儿。
M1: 那你明天上班别开车了。
F1: 不开了，我坐地铁去公司。
NARR: 女的明天怎么去上班？""",
    """健康劝告
M1: 最近一段时间，脖子疼得很厉害。
F1: 长时间一个姿势坐在电脑前，脖子肯定会疼的。你应该去锻炼身体！
M1: 我还不到四十岁，等四十岁以后再锻炼吧。
F1: 要珍惜健康，等身体出了问题，就后悔也来不及了。
NARR: 男的最近怎么了？""",
]

READING_P1 = [
    """生活哲理小故事（鞋）
在高速行驶的火车上，有一位老人不小心把刚买的新鞋从窗口掉下去一只，周围的人都觉得很____。没想到老人把另一只鞋也从窗口扔了出去……老人笑着____说：剩下那只对我已经没用了；扔出去，就有人可能____到一双鞋子。""",
    """历史小故事（两小儿辩日）
一位老师路上遇到两个小孩在争论太阳远近。一个小孩____太阳刚出来时离我们近；老师问他们的____；另一个用气温说明远近。小孩最后笑着问：____？""",
    """说明议论（篮球架高度）
很多人喜欢打篮球，但很少想篮球架为什么是3.05米。这个高度普通人跳一跳够得着。太低会因为太____而失去吸引力；____，人们也会因太难而失去兴趣。正是现在的高度让篮球____一项世界性运动。""",
]

READING_P2 = [
    """个人计划
从1995年开始，学校每年举行一次演讲比赛……今年的比赛定在下周六，我非常有把握，要争取发挥出最好水平。
一致项方向：我对这次比赛很有信心。""",
    """社会议题
煤和石油目前仍然是人类使用的最重要的能源，然而大量使用也对地球环境造成严重破坏。寻找新的绿色能源已成为新问题。
一致项方向：煤、石油目前对人类仍然很重要。""",
    """科普改正常识
鲜嫩的瓜果蔬菜，生着吃比煮熟了吃更有营养——不少人这么想。但专家发现，至少对西红柿来说，熟吃比生吃总体营养价值要高。
一致项方向：西红柿熟吃更有营养。""",
]

READING_P3 = [
    """人物传记式长文
他学法律却爱历史。小时候爸爸买了《上下五千年》，他反复读；后来写出深受欢迎的历史书，说明历史可以写得很好看。""",
    """社会观察议论文
很多人总觉得自己钱不够；真正有钱以后，又觉得时间不够用。有钱和有闲往往很难同时得到。""",
    """职场/成长叙事
她大学学的是设计，毕业后却进了一家普通公司做行政。工作三年后，她利用晚上的时间重新学习，完成了自己的第一个作品集。朋友起初并不支持，觉得她应该先好好上班；父母也担心她太累。但她没有放弃。半年后，一家杂志采用了她的一组照片，同事这才发现她一直在努力。这说明，坚持自己的兴趣，有时候也能打开新的机会。""",
]

WRITING_P1 = [
    """情绪动作：大笑 / 忍不住 / 起来 / 他 → 他忍不住大笑起来。""",
    """建议习惯：情绪 / 听音乐 / 可以 / 缓解 / 紧张的 → 听音乐可以缓解紧张的情绪。""",
    """被动结果：摔 / 玩具 / 被 / 了 / 坏 → 玩具被摔坏了。""",
]

WRITING_KEYWORDS = [
    """节日放松：元旦、放松、礼物、表演、善良（相关、可写成短文主题）""",
    """职场成长：机会、努力、经验、同事、成功""",
    """旅行见闻：风景、方便、天气、照片、印象""",
]

WRITING_PICTURE = [
    """Photorealistic candid photo of two friends chatting on a park bench at dusk, natural light, no text.""",
    """Photorealistic photo of a busy but ordinary subway platform in a Chinese city, people waiting, no logos or readable text.""",
    """Photorealistic kitchen scene: someone cooking a simple home meal, warm indoor light, no text.""",
]

BY_PART: dict[str, list[str]] = {
    "listening_p1": LISTENING_P1,
    "listening_p2": LISTENING_P2,
    "reading_p1": READING_P1,
    "reading_p2": READING_P2,
    "reading_p3": READING_P3,
    "writing_p1": WRITING_P1,
    "writing_keywords": WRITING_KEYWORDS,
    "writing_picture": WRITING_PICTURE,
}


def format_exemplars(part: str) -> str:
    items = BY_PART.get(part) or []
    if not items:
        return ""
    lines = [
        "Style exemplars (official HSK5-like natural Chinese). "
        "Match tone and naturalness; invent a NEW situation; do not copy plots or wording:",
    ]
    for i, block in enumerate(items, 1):
        lines.append(f"--- exemplar {i} ---")
        lines.append(block.strip())
    return "\n".join(lines)
