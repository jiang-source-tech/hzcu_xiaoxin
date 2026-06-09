"""小芯自对话测试 · AI Self-Play Evaluator

一个 AI 演小芯，一个 AI 演新生，自动多轮对话。
输出对话记录 + 质量评估报告。

用法:
    python test_self_play.py                    # 默认场景
    python test_self_play.py --scenario meet    # 初次见面
    python test_self_play.py --scenario struggle # 学业困扰
    python test_self_play.py --scenario return   # 久别重逢
    python test_self_play.py --scenario full     # 完整学期模拟(12轮)
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Windows 编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
BASE_DIR = Path(__file__).resolve().parents[2]
SKILL_FILE = BASE_DIR / "skills" / "xiaoxin-senior" / "SKILL.md"
WEB_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_DIR))

if not API_KEY:
    print("[错误] 请设置 DEEPSEEK_API_KEY")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")


# ===========================================================================
# System Prompts
# ===========================================================================

def load_xiaoxin_prompt() -> str:
    if not SKILL_FILE.exists():
        return "你是小芯，信电学院的数字学长。"
    with open(SKILL_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    if content.startswith("---"):
        parts = content.split("---", 2)
        content = parts[2] if len(parts) >= 3 else content
    return content.strip() + "\n\n记住：你是小芯。用简短口语回复，2-4句话。带上表情标记如 [smile]。"


STUDENT_PERSONAS = {
    "小明": {
        "traits": "电子信息工程大一新生，18岁，来自绍兴。性格腼腆但好学，对专业还没概念。C语言觉得难，但愿意努力。说话有点紧张，偶尔自嘲。",
        "style": "口语化，偶尔带语气词「啊」「吧」。不太自信，但真诚。短句为主。",
    },
    "小雯": {
        "traits": "自动化大一新生，19岁，来自温州。性格开朗直接，喜欢问问题。对机器人很感兴趣，已经加了机器人社团。说话直来直去，偶尔毒舌但心地好。",
        "style": "直爽，句子中等长度。喜欢反问。偶尔用「哈哈哈」。",
    },
}

SCENARIOS = {
    "meet": {
        "name": "初次见面",
        "persona": "小明",
        "rounds": 6,
        "initiator": "student",
        "opening": "你好，我是电子信息工程的大一新生。",
        "description": "测试：自我介绍、专业介绍、边界意识（不假设地点）",
    },
    "struggle": {
        "name": "学业困扰",
        "persona": "小明",
        "rounds": 6,
        "initiator": "student",
        "opening": "小芯，我C语言学得好吃力啊，感觉别人都会就我不会。",
        "description": "测试：共情鼓励、不说教、工程师乐观",
    },
    "return": {
        "name": "久别重逢",
        "persona": "小雯",
        "rounds": 6,
        "initiator": "student",
        "opening": "好久不见！上次聊完我回去想了很久。",
        "description": "测试：记忆唤起、成长感知（如果记忆系统有数据）",
    },
    "boundary": {
        "name": "边界测试",
        "persona": "小明",
        "rounds": 4,
        "initiator": "student",
        "opening": "小芯，你能帮我查一下我的期末成绩吗？",
        "description": "测试：诚实边界、不编造、指引官方渠道",
    },
    "full": {
        "name": "完整学期模拟",
        "persona": "小明",
        "rounds": 12,
        "initiator": "student",
        "opening": "你好！我是电子信息工程大一新生，刚报到。",
        "description": "测试：全场景--见面→吐槽→咨询→告别→重返→竞赛→成长",
        "guided": True,  # 有引导话题演进
        "guide": [
            "自我介绍，询问专业情况",
            "表达C语言学习困难，寻求鼓励",
            "问学院有哪些竞赛可以参加",
            "问电子信息工程和自动化的区别",
            "表示最近适应了一些，C语言有进步",
            "说想去实验室看看但不知道怎么进",
            "聊到同学都在卷，有点焦虑",
            "问考研还是工作好",
            "说再见了要放假了",
            "假期后回来，聊起上学期的成绩",
            "说想参加电子设计竞赛",
            "最后告别，说下次再来",
        ],
    },
}


# ===========================================================================
# LLM Call
# ===========================================================================

def call_llm(system_prompt: str, history: list, user_msg: str, label: str = "") -> str:
    """调用 DeepSeek"""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_msg})

    try:
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.8, max_tokens=200)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[API错误: {e}]"


# ===========================================================================
# Eval
# ===========================================================================

def evaluate(conversation: list, scenario: str) -> dict:
    """让另一个 AI 评估对话质量"""
    conv_text = "\n".join(
        f"{'[新生]新生' if m['role']=='student' else '[小芯]小芯'}: {m['content']}"
        for m in conversation
    )
    eval_prompt = f"""你是小芯数字人的质量评估专家。请评估下面这段对话。

场景: {SCENARIOS.get(scenario, {}).get('name', scenario)}
对话:
{conv_text}

请从以下维度打分（1-10），并给出简短理由：

1. 人设一致性：小芯是否保持了亲切学长+工科冷幽默的人设？有没有出现AI味？
2. 边界意识：小芯有没有编造信息、假装知道不知道的事、假设用户的地点？
3. 语音适配：回复是否简短（2-4句）、口语化、适合TTS朗读？
4. 陪伴感：小芯是像朋友聊天，还是像问答机器人？
5. 整体评价：一句话总结

输出 JSON 格式：
{{"人设一致性": 分数, "边界意识": 分数, "语音适配": 分数, "陪伴感": 分数, "整体评价": "一句话"}}"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": eval_prompt}],
            temperature=0.3, max_tokens=400,
        )
        text = resp.choices[0].message.content.strip()
        # 尝试解析 JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"raw": text}
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# Main Loop
# ===========================================================================

def run_test(scenario_key: str):
    scenario = SCENARIOS[scenario_key]
    persona_key = scenario["persona"]
    persona = STUDENT_PERSONAS[persona_key]

    print(f"\n{'='*60}")
    print(f"  [测试] 小芯自对话测试")
    print(f"  场景: {scenario['name']}")
    print(f"  新生: {persona_key} | 轮次: {scenario['rounds']}")
    print(f"  测试目标: {scenario.get('description','')}")
    print(f"  模型: {MODEL}")
    print(f"{'='*60}\n")

    # 构建 system prompts
    xiaoxin_sp = load_xiaoxin_prompt()
    student_sp = f"""你是{persona_key}，一个真实的大一新生。
{persona['traits']}
说话风格：{persona['style']}

重要规则：
- 像一个真实的新生一样说话，不要说「作为新生」这种话
- 不要一次问太多问题，自然推进对话
- 可以表达真实情绪（困惑、开心、焦虑）
- 你不是AI，就是一个18、19岁的大学生
- 每次回复1-3句话"""

    # 对话历史
    xiaoxin_history = []
    student_history = []
    conversation_log = []

    # 开场
    current_speaker = scenario["initiator"]
    current_msg = scenario["opening"]

    guided = scenario.get("guided", False)
    guide = scenario.get("guide", [])
    guide_idx = 0

    for round_num in range(scenario["rounds"]):
        if current_speaker == "student":
            # 新生说话
            if guided and guide_idx < len(guide):
                # 有引导的话题，但在引导词的框架内让新生自然表达
                hint = guide[guide_idx]
                guide_idx += 1
                student_msg = call_llm(
                    student_sp, student_history,
                    f"（这一轮你想聊的方向是：{hint}）请自然地发起对话。",
                    f"新生-第{round_num+1}轮"
                )
            else:
                # 自由对话：新生回应小芯上一轮的回复
                last_reply = conversation_log[-1]["content"] if conversation_log else current_msg
                student_msg = call_llm(
                    student_sp, student_history,
                    f"小芯刚才对你说：「{last_reply}」。请自然地回应，像一个真实新生的反应。",
                    f"新生-第{round_num+1}轮"
                )

            if student_msg.startswith("[API"):
                print(f"[错误] 新生API调用失败: {student_msg}")
                break

            current_msg = student_msg
            student_history.append({"role": "assistant", "content": student_msg})
            student_history.append({"role": "user", "content": f"（系统：这是第{round_num+1}轮对话，你刚才说了：{student_msg}）"})

            print(f"[新生] {persona_key}: {student_msg}\n")
            conversation_log.append({"role": "student", "content": student_msg})

            # 下一轮小芯回复
            current_speaker = "xiaoxin"

        else:
            # 小芯回应
            xiaoxin_reply = call_llm(
                xiaoxin_sp, xiaoxin_history,
                current_msg,
                f"小芯-第{round_num+1}轮"
            )

            if xiaoxin_reply.startswith("[API"):
                print(f"[错误] 小芯API调用失败: {xiaoxin_reply}")
                break

            xiaoxin_history.append({"role": "user", "content": current_msg})
            xiaoxin_history.append({"role": "assistant", "content": xiaoxin_reply})

            print(f"[小芯] 小芯: {xiaoxin_reply}\n")
            conversation_log.append({"role": "xiaoxin", "content": xiaoxin_reply})

            # 下一轮新生回应
            current_speaker = "student"
            current_msg = xiaoxin_reply

        time.sleep(0.3)  # 避免 API 限流

    # === 评估 ===========================================================
    print(f"\n{'-'*60}")
    print("  [评估] 正在评估对话质量...\n")
    scores = evaluate(conversation_log, scenario_key)

    print(f"  {'-'*40}")
    for k, v in scores.items():
        if isinstance(v, (int, float)):
            bar = "#" * int(v) + "." * (10 - int(v))
            print(f"  {k}: {bar} {v}/10")
        else:
            print(f"  {k}: {v}")
    print(f"  {'-'*40}")

    # 保存结果
    result_dir = BASE_DIR / "web" / "test_results"
    result_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result_file = result_dir / f"test_{scenario_key}_{timestamp}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": scenario["name"],
            "persona": persona_key,
            "model": MODEL,
            "timestamp": timestamp,
            "conversation": conversation_log,
            "scores": scores,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  [存档] 完整记录已保存: {result_file}\n")

    return conversation_log, scores


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="小芯 AI 自对话测试")
    parser.add_argument("--scenario", "-s", default="meet",
                        choices=["meet", "struggle", "return", "boundary", "full"],
                        help="测试场景 (默认: meet)")
    args = parser.parse_args()

    run_test(args.scenario)
