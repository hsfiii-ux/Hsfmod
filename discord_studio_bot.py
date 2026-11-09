import os
import json
from collections import deque
import discord
from discord.ext import commands
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

WEBHOOK_CACHE = {}
CHAT_MEMORY = deque(maxlen=6)

# قائمة الموديلات المجانية (إذا انتهى رصيد واحد ينتقل للذي يليه تلقائياً في أجزاء من الثانية)
AVAILABLE_MODELS = []

def init_models():
    global AVAILABLE_MODELS
    preferred_order = [
        "gemini-3.8-flash-lite",
        "gemini-3.8-flash-8b",
        "gemini-3.0-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.8-pro",
    ]
    try:
        fetched = [
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        # رتب الموديلات بحيث يبدأ بموديلات Lite ذات الرصيد المجاني الضخم (1500 طلب يومياً)
        lite_models = [m for m in fetched if "lite" in m or "8b" in m]
        other_models = [m for m in fetched if m not in lite_models]
        AVAILABLE_MODELS = lite_models + other_models
    except Exception:
        AVAILABLE_MODELS = preferred_order

init_models()

TEAM_PERSONAS = {
    "معن": {
        "title": "Technical Architect AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Maan&backgroundColor=c0aede",
        "prompt": "أنت 'معن' كبير مهندسي النظم في Godot 4. المستخدم هو مدير الاستوديو. صمم شجرة المشاهد (Scene Trees)، المجلدات، والـ EventBus باختصار ودقة هندسية."
    },
    "ملهم": {
        "title": "Creative Ideator AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Molhem&backgroundColor=ffe082",
        "prompt": "أنت 'ملهم' مفكر الاستوديو ومصمم الألعاب. المستخدم هو مدير الاستوديو. ابتكر أفكار ألعاب، قصص، ووثائق GDD مركزة ومبهرة."
    },
    "هتان": {
        "title": "Game Developer AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Hattan&backgroundColor=d1f4c9",
        "prompt": "أنت 'هتّان' مبرمج GDScript 2.0 في Godot 4. المستخدم هو مدير الاستوديو. اكتب كود GDScript نظيف وجاهز للنسخ مع Static Typing مباشرة بدون مقدمات."
    },
    "امير": {
        "title": "Game Artist AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Ameer&backgroundColor=ffd5dc",
        "prompt": "أنت 'أمير' فنان الألعاب ومصمم الواجهات. المستخدم هو مدير الاستوديو. اعطِ برومبتات توليد الرسوم، الألوان، وتصميم عُقد Control في Godot مباشرة."
    },
    "احسان": {
        "title": "QA Tester AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Ihsan&backgroundColor=ffdfba",
        "prompt": "أنت 'إحسان' مهندس جودة واختبار الألعاب. المستخدم هو مدير الاستوديو. افحص الكود، استخرج الثغرات، واكتب اختبارات GUT وتقارير الأخطاء باختصار."
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

async def generate_with_fallback(prompt_text):
    if not AVAILABLE_MODELS:
        init_models()
    for model_name in list(AVAILABLE_MODELS):
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"max_output_tokens": 900, "temperature": 0.6}
            )
            response = await model.generate_content_async(prompt_text)
            if response and response.text:
                return response.text[:1900]
        except Exception as e:
            err_str = str(e)
            # إذا انتهت حصة هذا الموديل (429) أو غير متاح (404)، انقله لآخر القائمة وجرب الموديل التالي فوراً!
            if "429" in err_str or "404" in err_str or "quota" in err_str.lower():
                AVAILABLE_MODELS.remove(model_name)
                AVAILABLE_MODELS.append(model_name)
                continue
    return "جميع الموديلات المجانية وصلت للحد الأقصى اللحظي، انتظر دقيقة وجرب مجدداً أو أضف مفتاح API جديد."

@bot.event
async def on_ready():
    print(f"Smart Quota Studio Online: {bot.user.name} | Models: {AVAILABLE_MODELS}")

@bot.event
async def on_message(message):
    if message.author.bot or message.webhook_id is not None:
        return

    content = message.content.strip()
    if not content:
        return

    norm_content = normalize_name(content)
    webhook = await get_fast_webhook(message.channel)
    context_str = "\n".join(CHAT_MEMORY)
    CHAT_MEMORY.append(f"المدير: {content}")

    # إذا نادى المدير "يا فريق" -> نرسل طلباً واحداً فقط يوفر الرصيد ويقسم الرد على الـ 5 موظفين!
    if "فريق" in norm_content or "الكل" in norm_content or "شباب" in norm_content:
        combined_prompt = (
            f"سياق المحادثة:\n{context_str}\n"
            f"توجيه المدير للفريق بالكامل: {content}\n\n"
            "اكتب رد كل موظف من الخمسة باختصار شديد (سطرين لكل موظف) بالصيغة التالية تماماً:\n"
            "[معن]: رد معن هنا\n"
            "[ملهم]: رد ملهم هنا\n"
            "[هتان]: رد هتان هنا\n"
            "[امير]: رد امير هنا\n"
            "[احسان]: رد احسان هنا"
        )
        raw_reply = await generate_with_fallback(combined_prompt)
        for member, persona in TEAM_PERSONAS.items():
            tag = f"[{member}]:"
            if tag in raw_reply:
                part = raw_reply.split(tag)[1].split("[")[0].strip()
                if part:
                    await webhook.send(
                        content=part,
                        username=f"{member} | {persona['title']}",
                        avatar_url=persona["avatar"]
                    )
        return

    # إذا نادى موظفاً محدداً بالاسم
    targets = [k for k in TEAM_PERSONAS.keys() if normalize_name(k) in norm_content]
    for member in targets:
        persona = TEAM_PERSONAS[member]
        full_prompt = (
            f"{persona['prompt']}\n"
            f"سياق المحادثة:\n{context_str}\n"
            f"أمر المدير: {content}\n"
            f"نفذ الأمر مباشرة بصفتك {member}:"
        )
        reply_text = await generate_with_fallback(full_prompt)
        CHAT_MEMORY.append(f"{member}: {reply_text[:150]}")
        await webhook.send(
            content=reply_text,
            username=f"{member} | {persona['title']}",
            avatar_url=persona["avatar"]
        )

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
