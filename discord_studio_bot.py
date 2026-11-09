import os
import discord
from discord.ext import commands
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def generate_smart_reply(prompt_text):
    candidate_models = [
        "gemini-3.8-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                name = m.name.replace("models/", "")
                if name not in candidate_models:
                    candidate_models.insert(0, name)
    except Exception:
        pass

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt_text)
            if response and response.text:
                return response.text[:1900]
        except Exception:
            continue
    return "تعذر الاتصال بموديل الذكاء الاصطناعي."

# بطاقات شخصيات الفريق تحت إدارتك المباشرة
TEAM_PERSONAS = {
    "معن": {
        "title": "Technical Architect AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Maan&backgroundColor=c0aede",
        "prompt": "أنت 'معن' كبير مهندسي النظم التقنية في استوديو ألعاب Godot 4. المستخدم هو مديرك التنفيذي وصاحب الاستوديو؛ خاطبه باحترام ومهنية كمديرك. مهمتك: أخذ توجيهات المدير وتحويلها لهيكلة معمارية وشجرة مشاهد (Scene Trees) ومجلدات وأنظمة إشارات (EventBus)، وتوزيع المهام التقنية على هتان وأمير وإحسان وعرض تقرير الإنجاز على المدير."
    },
    "ملهم": {
        "title": "Creative Ideator AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Molhem&backgroundColor=ffe082",
        "prompt": "أنت 'ملهم' مسؤول الأفكار وتصميم الألعاب الإبداعي. المستخدم هو مديرك التنفيذي وصاحب الاستوديو. مهمتك: تقديم مقترحات أفكار ألعاب مبتكرة وممتعة، وصياغة وثائق التصميم (GDD) والقصص، وعرض الخيارات المتنوعة على المدير ليختار منها ويعتمدها."
    },
    "هتان": {
        "title": "Game Developer AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Hattan&backgroundColor=d1f4c9",
        "prompt": "أنت 'هتّان' مطور الألعاب الرئيسي وخبير GDScript 2.0 في Godot 4. المستخدم هو مدير الاستوديو. مهمتك: برمجة الميكانيكيات والأنظمة بدقة واحترافية وفق مواصفات معن وتوجيهات المدير، وكتابة كود نظيف وجاهز، وإصلاح أي ملاحظات يطلبها المدير أو يرصدها إحسان."
    },
    "امير": {
        "title": "Game Artist AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Ameer&backgroundColor=ffd5dc",
        "prompt": "أنت 'أمير' فنان الألعاب ومصمم الواجهات (UI/UX). المستخدم هو مدير الاستوديو. مهمتك: ابتكار الهوية البصرية، وتجهيز مواصفات وبرومبتات توليد الرسوم والشخصيات والبكسل، وتصميم شاشات واجهات المستخدم (HUD) في Godot وعرض المقترحات على المدير للاعتماد."
    },
    "احسان": {
        "title": "QA Tester AI",
        "avatar": "https://api.dicebear.com/7.x/bottts/png?seed=Ihsan&backgroundColor=ffdfba",
        "prompt": "أنت 'إحسان' مهندس ضبط الجودة واختبار الألعاب. المستخدم هو مدير الاستوديو. مهمتك: اختبار ألعاب الفريق، واكتشاف الثغرات وحالات الحافة، وكتابة اختبارات GUT الآلية، ورفع تقارير جودة واضحة ومباشرة للمدير لطمأنته على استقرار المشروع."
    }
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def get_or_create_webhook(channel):
    webhooks = await channel.webhooks()
    for wh in webhooks:
        if wh.name == "StudioAIWebhook":
            return wh
    return await channel.create_webhook(name="StudioAIWebhook")

def normalize_name(text):
    return text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ّ", "").strip()

async def call_ai_persona(persona_key, user_prompt, chat_context=""):
    persona = TEAM_PERSONAS[persona_key]
    full_prompt = (
        f"{persona['prompt']}\n\n"
        f"المحادثة السابقة في الاستوديو:\n{chat_context}\n\n"
        f"توجيه المدير (صاحب الاستوديو):\n{user_prompt}\n\n"
        f"أجب بصفتك {persona_key} ({persona['title']}) بالعربية، بأسلوب موظف محترف يرفع تقريره أو اقتراحه لمديره."
    )
    return generate_smart_reply(full_prompt)

@bot.event
async def on_ready():
    print(f"استوديو الألعاب جاهز بإدارة المدير: {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot or message.webhook_id is not None:
        return

    content = message.content.strip()
    target_member = None

    for key in TEAM_PERSONAS.keys():
        if normalize_name(key) in normalize_name(content):
            target_member = key
            break

    if target_member:
        async with message.channel.typing():
            history_msgs = []
            async for prev_msg in message.channel.history(limit=5):
                history_msgs.append(f"{prev_msg.author.display_name}: {prev_msg.content}")
            context_str = "\n".join(reversed(history_msgs))

            reply_text = await call_ai_persona(target_member, content, context_str)
            persona = TEAM_PERSONAS[target_member]

            webhook = await get_or_create_webhook(message.channel)
            await webhook.send(
                content=reply_text,
                username=f"{target_member} | {persona['title']}",
                avatar_url=persona["avatar"]
            )
            return

    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
