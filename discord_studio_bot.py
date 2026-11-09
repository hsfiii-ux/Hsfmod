import os
import asyncio
from collections import deque
import discord
from discord.ext import commands
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

WEBHOOK_CACHE = {}
# ذاكرة كبيرة تحفظ تفاصيل المشروع والأكواد بين الموظفين
PROJECT_MEMORY = deque(maxlen=15)

# جلب كل الموديلات الشغالة في حسابك للتبديل التلقائي لو خلص رصيد واحد منها
AVAILABLE_MODELS = []

def refresh_models():
    global AVAILABLE_MODELS
    try:
        models = [
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        # نرتب الموديلات القوية والحديثة أولاً
        priority = [m for m in models if "flash" in m or "pro" in m]
        AVAILABLE_MODELS = priority if priority else models
    except Exception:
        AVAILABLE_MODELS = ["gemini-3.8-flash", "gemini-3.0-flash", "gemini-2.5-flash"]

refresh_models()

# الموظفون الخمسة بمهام تنفيذية إنتاجية حقيقية (بدون اختصار مخل)
TEAM_PERSONAS = {
    "ملهم": {
        "title": "Creative Ideator & Game Designer AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Molhem&backgroundColor=ffe082",
        "prompt": (
            "أنت 'ملهم' مصمم الألعاب ومبتكر الأفكار في استوديو Godot 4. المستخدم هو المدير التنفيذي.\n"
            "مهمتك التنفيذية: لا تكتفِ بالكلام النظري؛ اكتب وثيقة تصميم اللعبة (GDD) الفعلية وتشمل: القصة، ميكانيكيات اللعب التفصيلية، التحكم، وتصميم المرحلة الأولى، وسلمها لـ 'معن' ليبدأ الهيكلة."
        )
    },
    "معن": {
        "title": "Technical Architect AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Maan&backgroundColor=c0aede",
        "prompt": (
            "أنت 'معن' كبير المعماريين التقنيين لمحرك Godot 4. المستخدم هو المدير التنفيذي.\n"
            "مهمتك التنفيذية: بناءً على تصميم ملهم وأمر المدير، ارسم شجرة المشاهد الكاملة (Scene Tree) والعقد (Nodes) بدقة، وهيكل مجلدات res://، ونظام الإشارات (Signals/EventBus)، وحدد الملفات المطلوب من 'هتان' برمجتها."
        )
    },
    "هتان": {
        "title": "Game Developer AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Hattan&backgroundColor=d1f4c9",
        "prompt": (
            "أنت 'هتّان' المبرمج الرئيسي بلغة GDScript 2.0 في Godot 4. المستخدم هو المدير التنفيذي.\n"
            "مهمتك التنفيذية: اكتب أكواد GDScript الفعلية الكاملة والجاهزة للتشغيل (حركة اللاعب، الفيزياء، الأنظمة، التحكم) داخل مربعات كود ```gdscript مع استخدام Static Typing، بناءً على هيكلة معن."
        )
    },
    "امير": {
        "title": "Game Artist & UI/UX AI",
        "avatar": "[https://api.dicebear.com/7.x/bottts/png?seed=Ameer&backgroundColor=ffd5dc](https://api.dicebear.com/7.x/bottts/png?seed=Ameer&backgroundColor=ffd5dc)",
        "prompt": (
            "أنت 'أمير' فنان الألعاب ومصمم الواجهات في Godot 4. المستخدم هو المدير التنفيذي.\n"
            "مهمتك التنفيذية: اكتب البرومبتات الجاهزة لتوليد رسوم الشخصيات والبيئات (Sprites/Tilesets) بمقاساتها، وصمم شجرة عُقد الواجهة (Control Nodes / HUD) ولوحة الألوان بالـ Hex Codes."
        )
    },
    "احسان": {
        "title": "QA Tester AI",
        "avatar": "[https://api.dicebear.com/7.x/bottts/png?seed=Ihsan&backgroundColor=ffdfba](https://api.dicebear.com/7.x/bottts/png?seed=Ihsan&backgroundColor=ffdfba)",
        "prompt": (
            "أنت 'إحسان' مهندس الجودة واختبار الألعاب في Godot 4. المستخدم هو المدير التنفيذي.\n"
            "مهمتك التنفيذية: راجع كود هتان وهيكلة معن، واستخرج أي ثغرات أو أخطاء محتملة، واكتب كود اختبار وحدة فعلي باستخدام GUT Framework للتأكد من سلامة اللعبة."
        )
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

async def send_long_webhook(webhook, text, username, avatar_url):
    # تقسيم الرسائل الطويلة (مثل الأكواد الكاملة) حتى لا يرفضها ديسكورد
    chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
    for chunk in chunks:
        await webhook.send(content=chunk, username=username, avatar_url=avatar_url)

async def execute_agent_work(member, user_order):
    persona = TEAM_PERSONAS[member]
    project_context = "\n---\n".join(PROJECT_MEMORY)
    full_prompt = (
        f"{persona['prompt']}\n\n"
        f"=== سجل عمل الفريق والمشروع الحالي ===\n{project_context}\n\n"
        f"=== أمر المدير التنفيذي الحالي ===\n{user_order}\n\n"
        f"نفذ مهمتك كاملة الآن بصفتك {member} ({persona['title']}) وقدم شغلك الفعلي للمدير:"
    )

    if not AVAILABLE_MODELS:
        refresh_models()

    for model_name in list(AVAILABLE_MODELS):
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"max_output_tokens": 2048, "temperature": 0.7}
            )
            response = await model.generate_content_async(full_prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            err = str(e)
            if "429" in err or "404" in err or "quota" in err.lower():
                AVAILABLE_MODELS.remove(model_name)
                AVAILABLE_MODELS.append(model_name)
                await asyncio.sleep(1)
                continue
    return "تم الوصول للحد اليومي المجاني لمفتاح Gemini API الحالي. يمكنك إنشاء مفتاح جديد في ثوانٍ من Google AI Studio أو الانتظار لتجدد الحصة."

@bot.event
async def on_ready():
    print(f"Game Production Studio Active: {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot or message.webhook_id is not None:
        return

    content = message.content.strip()
    if not content:
        return

    norm_content = normalize_name(content)

    # تحديد من الموظف المطلوب (أو الفريق كامل بالترتيب الهندسي: ملهم -> معن -> هتان -> امير -> احسان)
    if any(w in norm_content for w in ["فريق", "الكل", "شباب", "ابداوا", "ابدؤوا", "نفذوا"]):
        targets = ["ملهم", "معن", "هتان", "امير", "احسان"]
    else:
        targets = [k for k in TEAM_PERSONAS.keys() if normalize_name(k) in norm_content]

    if not targets:
        return

    PROJECT_MEMORY.append(f"أمر المدير: {content}")
    webhook = await get_fast_webhook(message.channel)

    for member in targets:
        persona = TEAM_PERSONAS[member]
        async with message.channel.typing():
            work_output = await execute_agent_work(member, content)
            # حفظ شغل الموظف في ذاكرة المشروع ليقرأه الموظف الذي بعده ويبني عليه!
            PROJECT_MEMORY.append(f"مخرجات {member} ({persona['title']}):\n{work_output[:1000]}")

            await send_long_webhook(
                webhook,
                work_output,
                username=f"{member} | {persona['title']}",
                avatar_url=persona["avatar"]
            )
            await asyncio.sleep(1.5)

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
