import requests
import telebot
from telebot import types
from flask import Flask, request
import re 
import os 
import sys
import json 

# 🚨 استيراد جميع الدوال من ملف التحميل الخارجي
from handlers.download import download_media_yt_dlp, load_links, save_links

# ===============================================
#              0. الإعدادات والثوابت والتهيئة
# ===============================================

# قراءة المتغيرات البيئية
BOT_TOKEN = os.getenv("BOT_TOKEN") 
WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL") 
WEBHOOK_URL_PATH = "/{}".format(BOT_TOKEN) 

DEVELOPER_USER_ID = "1315011160"
CHANNEL_USERNAME = "@SuPeRx1" # يُفضل وضعه كمتغير بيئي أيضاً

# التهيئة
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    app = Flask(name) 
except Exception as e:
    print(f"❌ فشل تهيئة البوت/Flask. الخطأ: {e}")

# ===============================================
#              1. نقاط وصول Webhook
# ===============================================

@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    """نقطة النهاية التي يستقبل منها البوت تحديثات تيليجرام."""
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
        except Exception as e:
            print(f"❌ خطأ حرج في معالجة Webhook: {e}")
        return '', 200 
    else:
        return 'Error', 403

# ===============================================
#              2. معالجة الأوامر الرئيسية (الواجهة)
# ===============================================

@bot.message_handler(commands=["start"])
def send_welcome(message):
    first_name = message.from_user.first_name if message.from_user else "صديقنا"
    markup = types.InlineKeyboardMarkup(row_width=2)
    tt_btn = types.InlineKeyboardButton("تحميل تيك توك 🎶", callback_data="download_tiktok")
    ig_btn = types.InlineKeyboardButton("تحميل إنستجرام 📸", callback_data="download_instagram")
    yt_btn = types.InlineKeyboardButton("تحميل يوتيوب ▶️", callback_data="download_youtube")
    dev_btn = types.InlineKeyboardButton("المطور 👨‍💻", url="https://t.me/yourusername") 
    markup.add(tt_btn, ig_btn, yt_btn, dev_btn)
    bot.send_message(
        message.chat.id,
        f"""<b>مرحباً بك {first_name}!</b> 👋
        أنا بوت التحميل الشامل. اختر المنصة التي تريد التحميل منها:
        * اختر من القائمة أدناه وأرسل <b>الرابط فوراً</b>.
        """,
        parse_mode='HTML', 
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
def handle_download_choice(call):
    platform_key = call.data.split('_')[1]
    platforms = {'tiktok': 'تيك توك', 'instagram': 'إنستجرام', 'youtube': 'يوتيوب'}
    platform = platforms.get(platform_key, 'غير معروف')
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"""<b>🚀 أرسل رابط فيديو {platform} الآن!</b>""",
        parse_mode='HTML' 
    )
    call.message.platform_key = platform_key 
    bot.register_next_step_handler(call.message, process_user_link)
    
# ===============================================
#              3. الدالة الرئيسية الموحدة للمعالجة
# ===============================================

@bot.message_handler(func=lambda m: True)
def process_user_link(message):
    user_url = message.text
    loading_msg = None
    platform_key = getattr(message, 'platform_key', None) 
    
    # 1. التحقق من إلغاء العملية
    if user_url.startswith('/'):
        bot.send_message(message.chat.id, "❌ تم إلغاء العملية. اضغط /start.", parse_mode='HTML')
        return send_welcome(message)

    # 2. تحديد المنصة بناءً على الرابط
    if not platform_key:
        if re.match(r'https?://(?:www\.)?(?:tiktok\.com|vt\.tiktok\.com|vm\.tiktok\.com)/', user_url):
