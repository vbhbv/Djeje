import requests
import telebot
from telebot import types
from flask import Flask, request
import re 
import os 
import sys
import json 
import threading 

# 🚨 استيراد جميع الدوال من ملف التحميل الخارجي
from handlers.download import download_media_yt_dlp, load_links, save_links

# ===============================================
#              0. الإعدادات والثوابت والتهيئة
# ===============================================

BOT_TOKEN = os.getenv("BOT_TOKEN") 
WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL") 
WEBHOOK_URL_PATH = "/{}".format(BOT_TOKEN) 

DEVELOPER_USER_ID = "1315011160"
CHANNEL_USERNAME = "@SuPeRx1"

# التهيئة
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    app = Flask(__name__) 
except Exception as e:
    print(f"❌ فشل تهيئة البوت/Flask. الخطأ: {e}")

# ===============================================
#              1. نقاط وصول Webhook
# ===============================================

@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
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
        * يدعم الآن **التحميل المُجدوَل** (أرسل عدة روابط دفعة واحدة!).
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
#              3. معالجة التحميل المجدول
# ===============================================

def schedule_bulk_downloads(chat_id, link_data):
    """دالة تعمل في خيط منفصل لمعالجة قائمة الروابط وإرسال تقرير نهائي."""
    results = {'success': 0, 'failed': 0, 'platforms': set()}
    
    # ⚠️ ملاحظة: يمكن أن تحدث هذه الرسالة خطأ لأن رسالة "قيد التحميل" سيتم حذفها بواسطة دالة التحميل
    loading_msg = bot.send_message(chat_id, "<strong>⏳ بدء معالجة قائمة التحميل المُجدوَل...</strong>", parse_mode="html")
    
    for link_id, data in link_data.items():
        url = data['url']
        platform_name = data['platform_name']
        download_as_mp3 = data['download_as_mp3']

        try:
            # 🚨 استدعاء دالة التحميل من الملف الخارجي (ستحذف loading_msg)
            download_media_yt_dlp(
                bot, chat_id, url, platform_name, loading_msg.message_id, download_as_mp3=download_as_mp3
            )
            results['success'] += 1
            results['platforms'].add(platform_name)
            
        except Exception as e:
            print(f"❌ فشل تحميل {url}: {e}")
            results['failed'] += 1
            
    try:
        # محاولة حذف آخر رسالة "جارٍ التحميل" قبل إرسال التقرير
        bot.delete_message(chat_id, loading_msg.message_id) 
    except:
        pass # قد تكون الرسالة محذوفة بالفعل

    report_text = f"**تقرير التحميل المُجدوَل ✅**\n\n"
    report_text += f"▪️ تم بنجاح: {results['success']} ملف\n"
    report_text += f"▪️ فشلت: {results['failed']} ملف\n"
    report_text += f"▪️ المنصات: {', '.join(list(results['platforms'])) or 'لا توجد'}\n\n"
    report_text += "شكرًا لاستخدامك خدمة الجدولة المتميزة! /start"
    
    bot.send_message(chat_id, report_text, parse_mode='Markdown')

# ===============================================
#              4. الدالة الرئيسية الموحدة للمعالجة
# ===============================================

@bot.message_handler(func=lambda m: True)
def process_user_link(message):
    user_text = message.text
    loading_msg = None
    platform_key = getattr(message, 'platform_key', None) 
    
    if user_text.startswith('/'):
        bot.send_message(message.chat.id, "❌ تم إلغاء العملية. اضغط /start.", parse_mode='HTML')
        return send_welcome(message)

    link_regex = r'https?://(?:www\.)?(?:tiktok\.com|vt\.tiktok\.com|vm\.tiktok\.com|instagram\.com|youtube\.com|youtu\.be)/[^\s]*'
    all_links = re.findall(link_regex, user_text)
    
    if not all_links:
        bot.send_message(message.chat.id, "❌ **الرابط غير صالح!** يرجى إرسال رابط صحيح.", parse_mode='HTML')
        return send_welcome(message)

    # 3. معالجة التحميل المجمّع
    if len(all_links) > 1:
        links_to_schedule = {}
        platforms_detected = set()
        
        for i, url in enumerate(all_links):
            # تحديد المنصة هنا للجدولة
            if re.match(r'https?://(?:www\.)?(?:tiktok\.com|vt\.tiktok\.com|vm\.tiktok\.com)/', url):
                platform_key = 'tiktok'
                platform_name = 'تيك توك'
            elif re.match(r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/', url):
                platform_key = 'instagram'
                platform_name = 'إنستجرام'
            elif re.match(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/', url):
                platform_key = 'youtube'
                platform_name = 'يوتيوب'
            else:
                continue
                
            platforms_detected.add(platform_name)
            
            links_to_schedule[str(i)] = {
                'url': url,
                'platform_name': platform_name,
                'download_as_mp3': False 
            }
            
        if not links_to_schedule:
             bot.send_message(message.chat.id, "❌ لم يتم العثور على أي روابط مدعومة للجدولة.", parse_mode='HTML')
             return send_welcome(message)
             
        
        thread = threading.Thread(target=schedule_bulk_downloads, args=(message.chat.id, links_to_schedule))
        thread.start()
        
        bot.send_message(message.chat.id, 
                         f"**✅ بدء التحميل المجدول**\n\nتم استلام {len(links_to_schedule)} رابطاً من {', '.join(platforms_detected)}.\nسيتم معالجتها في الخلفية وإرسال تقرير نهائي.",
                         parse_mode='Markdown')
        return

    # 4. معالجة التحميل الفردي (رابط واحد فقط)
    user_url = all_links[0]
    
    if not platform_key:
        if re.match(r'https?://(?:www\.)?(?:tiktok\.com|vt\.tiktok\.com|vm\.tiktok\.com)/', user_url):
            platform_key = 'tiktok'
        elif re.match(r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/', user_url):
            platform_key = 'instagram'
        elif re.match(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/', user_url):
            platform_key = 'youtube'
        else:
            bot.send_message(message.chat.id, "❌ **الرابط غير صالح!** يرجى إرسال رابط صحيح.", parse_mode='HTML')
            return send_welcome(message)


    platforms = {'tiktok': 'تيك توك', 'instagram': 'إنستجرام', 'youtube': 'يوتيوب'}
    platform_name = platforms[platform_key]
    
    try:
        # 5. إرسال خيار التحويل لليوتيوب فقط 
        if platform_key == 'youtube':
            
            message_id_key = str(message.message_id) 
            links = load_links()
            links[message_id_key] = user_url
            save_links(links) 
            
            markup = types.InlineKeyboardMarkup()
            vid_btn = types.InlineKeyboardButton("تحميل فيديو 🎥", callback_data=f"final_dl_{platform_key}_video_{message_id_key}")
            aud_btn = types.InlineKeyboardButton("تحويل إلى صوت 🎧 (MP3)", callback_data=f"final_dl_{platform_key}_audio_{message_id_key}")
            # ⚠️ زر القص معطل مؤقتاً لتجنب انهيار البوت بسبب نقص ffmpeg
            # clip_btn = types.InlineKeyboardButton("قص الفيديو ✂️", callback_data=f"final_dl_{platform_key}_clip_{message_id_key}") 
            
            # markup.add(vid_btn, aud_btn, clip_btn) 
            markup.add(vid_btn, aud_btn) 
            
            bot.send_message(message.chat.id, f"✅ تم التعرف على رابط {platform_name}. الرجاء اختيار طريقة التحميل:", reply_markup=markup, parse_mode='HTML')
            return
            
        # 6. بدء عملية التحميل المباشر لـ تيك توك وإنستجرام (فيديو فقط)
        # 🚨 نعتمد هنا على أن دالة download_media_yt_dlp ستجرب التحميل السريع أولاً
        loading_msg = bot.send_message(message.chat.id, f"<strong>⏳ جارٍ التحميل السريع/المباشر من {platform_name} (فيديو)...</strong>", parse_mode="html")
        
        download_media_yt_dlp(bot, message.chat.id, user_url, platform_name, loading_msg.message_id, download_as_mp3=False)
            
    except Exception as e:
        print(f"=====================================================")
        print(f"❌ خطأ حرج في معالجة {platform_name or 'التحميل'}: {e}") 
        print(f"=====================================================")
        
        if loading_msg:
             try: bot.delete_message(message.chat.id, loading_msg.message_id) 
             except: pass 
        
        error_msg = str(e).split('\n')[0] 
        bot.send_message(message.chat.id, f"❌ حدث خطأ أثناء تحميل {platform_name or 'الملف'}: <b>{error_msg}</b>", parse_mode='HTML')
        
    finally:
        bot.send_message(message.chat.id, "اضغط على الأمر /start للعودة إلى القائمة الرئيسية.", parse_mode='HTML')

# ===============================================
#              5. معالجة التحميل النهائي (MP3/فيديو)
# ===============================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('final_dl_'))
def handle_final_download(call):
    parts = call.data.split('_')
    platform_key = parts[2]
    media_type = parts[3] 
    message_id_key = parts[4] 
    
    links = load_links()
    user_url = links.get(message_id_key) 
    
    if not user_url:
        bot.answer_callback_query(call.id, "❌ انتهت صلاحية هذا الرابط أو تم تحميله مسبقاً.")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"❌ انتهت صلاحية التحميل. اضغط /start للبدء مجدداً.",
            parse_mode='HTML'
        )
        return

    platforms = {'youtube': 'يوتيوب'}
    platform_name = platforms[platform_key]
    
    # ⚠️ جزء القص معطل مؤقتاً
    if media_type == 'clip':
        bot.answer_callback_query(call.id, "⚠️ ميزة القص معطلة مؤقتاً للصيانة. يرجى اختيار تحميل الفيديو كاملاً.")
        return # نوقف التنفيذ
        
    # إذا لم يكن قص، نحذف الرابط ونقوم بالتحميل
    user_url = links.pop(message_id_key) 
    save_links(links) 
    
    download_as_mp3 = (media_type == 'audio')
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"<b>⏳ جارٍ التحميل/التحويل من {platform_name} ({media_type.upper()})...</b>",
            parse_mode='HTML'
        )
        
        download_media_yt_dlp(
            bot, 
            call.message.chat.id,
            user_url,
            platform_name,
            call.message.message_id,
            download_as_mp3
        )
        
    except Exception as e:
        print(f"=====================================================")
        print(f"❌ خطأ حرج في التحميل النهائي {platform_name}: {e}") 
        print(f"=====================================================")
        
        error_msg = str(e).split('\n')[0] 
        bot.send_message(call.message.chat.id, f"❌ حدث خطأ أثناء تحميل {platform_name}: <b>{error_msg}</b>", parse_mode='HTML')
        
    finally:
        bot.send_message(call.message.chat.id, "اضغط على الأمر /start للعودة إلى القائمة الرئيسية.", parse_mode='HTML')


# ===============================================
#              6. معالجة وقت القص (معطلة)
# ===============================================

# تم تعطيل هذه الدالة مؤقتاً لتجنب مشاكل moviepy/ffmpeg

# ===============================================
#              7. تهيئة Webhook
# ===============================================

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
    print('✅ البوت جاهز للتشغيل بواسطة Gunicorn...')
