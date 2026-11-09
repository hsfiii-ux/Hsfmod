import os
from collections import deque
import discord
from discord.ext import commands
import google.generativeai as genai

# 1. إعداد الذكاء الاصطناعي والموديل السريع مباشرة
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL = genai.GenerativeModel(
    model_name="gemini-3.8-flash",
    generation_config={
        "max_output_tokens": 900,
        "temperature": 0.6,
    }
)

# 2. ذاكرة كاش فورية في الـ RAM (لسرعة 0ms)
WEBHOOK_CACHE = {}
CHAT_MEMORY = deque(maxlen=6)

# 3. بطاقات الفريق تحت إدارتك المباشرة
TEAM_PERSONAS = {
    "معن": {
        "title": "Technical Architect AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Maan&backgroundColor=c0aede",
        "prompt": "أنت 'معن' كبير مهندسي النظم في Godot 4. المستخدم هو مدير الاستوديو. نفذ أوامره فوراً: صمم شجرة المشاهد (Scene Trees)، المجلدات، والـ EventBus باختصار ودقة هندسية."
    },
    "ملهم": {
        "title": "Creative Ideator AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Molhem&backgroundColor=ffe082",
        "prompt": "أنت 'ملهم' مفكر الاستوديو ومصمم الألعاب. المستخدم هو مدير الاستوديو. نفذ أوامره فوراً: ابتكر أفكار ألعاب، قصص، ووثائق GDD مركزة ومبهرة."
    },
    "هتان": {
        "title": "Game Developer AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Hattan&backgroundColor=d1f4c9",
        "prompt": "أنت 'هتّان' مبرمج GDScript 2.0 في Godot 4. المستخدم هو مدير الاستوديو. نفذ أوامره فوراً: اكتب كود GDScript نظيف وجاهز للنسخ مع Static Typing مباشرة بدون مقدمات طويلة."
    },
    "امير": {
        "title": "Game Artist AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Ameer&backgroundColor=ffd5dc",
        "prompt": "أنت 'أمير' فنان الألعاب ومصمم الواجهات. المستخدم هو مدير الاستوديو. نفذ أوامره فوراً: اعطِ برومبتات توليد الرسوم، الألوان، وتصميم عُقد Control في Godot مباشرة."
    },
    "احسان": {
        "title": "QA Tester AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Ihsan&backgroundColor=ffdfba",
        "prompt": "أنت 'إحسان' مهندس جودة واختبار الألعاب. المستخدم هو مدير الاستوديو. نفذ أوامره فوراً: افحص الكود، استخرج الثغرات، واكتب اختبارات GUT وتقارير الأخطاء باختصار."
    }
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def normalize_name(text):
    return text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ّ", "").strip()

async def get_fast_webhook(channel):
    if channel.id in WEBHOOK_CACHE:
        return WEBHOOK_CACHE[channel.id]
    webhooks = await channel.webhooks()
    for wh in webhooks:
        if wh.name == "StudioAIWebhook":
            WEBHOOK_CACHE[channel.id] = wh
            return wh
    wh = await channel.create_webhook(name="StudioAIWebhook")
    WEBHOOK_CACHE[channel.id] = wh
    return wh

async def ask_agent_turbo(persona_key, user_prompt):
    persona = TEAM_PERSONAS[persona_key]
    context_str = "\n".join(CHAT_MEMORY)
    full_prompt = (
        f"{persona['prompt']}\n"
        f"سياق المحادثة:\n{context_str}\n"
        f"أمر المدير: {user_prompt}\n"
        f"نفذ الأمر مباشرة بصفتك {persona_key}:"
    )
    try:
        response = await MODEL.generate_content_async(full_prompt)
        return response.text[:1900] if response and response.text else "تم التنفيذ."
    except Exception as e:
        return f"خطأ تقني: {e}"

@bot.event
async def on_ready():
    print(f"Turbo Studio Bot Online: {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot or message.webhook_id is not None:
        return

    content = message.content.strip()
    if not content:
        return

    norm_content = normalize_name(content)

    # إذا قال المدير "يا فريق" أو "الكل"، يردون جميعاً بالتتابع السريع
    if "فريق" in norm_content or "الكل" in norm_content or "شباب" in norm_content:
        targets = list(TEAM_PERSONAS.keys())
    else:
        targets = [k for k in TEAM_PERSONAS.keys() if normalize_name(k) in norm_content]

    if not targets:
        return

    CHAT_MEMORY.append(f"المدير: {content}")
    webhook = await get_fast_webhook(message.channel)

    for member in targets:
        persona = TEAM_PERSONAS[member]
        reply_text = await ask_agent_turbo(member, content)
        CHAT_MEMORY.append(f"{member}: {reply_text[:200]}")

        await webhook.send(
            content=reply_text,
            username=f"{member} | {persona['title']}",
            avatar_url=persona["avatar"]
        )

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
