import os
import tempfile
import yt_dlp
import json
import re

# ===============================================
#              0. دوال التخزين الدائم
# ===============================================

TEMP_STORAGE_FILE = 'temp_links.json' 

def load_links():
    if os.path.exists(TEMP_STORAGE_FILE):
        try:
            with open(TEMP_STORAGE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_links(data):
    try:
        with open(TEMP_STORAGE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ فشل حفظ البيانات في ملف JSON: {e}")

# ===============================================
#              2. دالة التحميل الرئيسية (منطق التحميل الأساسي)
# ===============================================

# CHANNEL_USERNAME يجب أن يُعرف في main.py
CHANNEL_USERNAME = "@SuPeRx1" # قم بتعريفه هنا أيضاً لتجنب خطأ NameError

# تم تبسيط هذه الدالة لتقليد المنطق الفعال الذي أرسلته
def download_media_yt_dlp(bot, chat_id, url, platform_name, loading_msg_id, download_as_mp3=False, clip_times=None):
    """
    دالة متخصصة للتحميل باستخدام yt-dlp وإرسال الملف.
    تم تبسيطها لتقليد المنطق الأساسي والمختبر (تحميل الفيديو فقط).
    """
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, f'downloaded_media.mp4')
        
        # خيارات yt-dlp الأساسية لتحميل أفضل فيديو
        ydl_opts = {
            'outtmpl': file_path,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            # تم تعطيل Metadata والتخصيص لضمان الاستقرار
        }
        
        if download_as_mp3:
            # إذا طلب MP3، نستخدم تنسيق الصوت
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                 'key': 'FFmpegExtractAudio',
                 'preferredcodec': 'mp3',
                 'preferredquality': '192',
            }]
            file_path = os.path.join(tmpdir, f'downloaded_media.mp3')

        # 1. بدء التنزيل
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
        except Exception as e:
             raise Exception(f"فشل التحميل عبر yt-dlp. قد يكون الرابط غير متاح: {e}")
            
        # 2. حذف رسالة "جاري التحميل"
        bot.delete_message(chat_id, loading_msg_id)
        
        # 3. الإرسال إلى تيليجرام (منطقك الذي أرسلته)
        caption_text = f"✅ تم التحميل من {platform_name} بواسطة: {CHANNEL_USERNAME}" 
        
        if os.path.exists(file_path):
             with open(file_path, 'rb') as f:
                if 'mp3' in file_path.lower():
                     bot.send_audio(chat_id, f, caption=f'<b>{caption_text}</b>', parse_mode='HTML')
                else:
                    bot.send_video(
                        chat_id,
                        f,
                        caption=f'<b>{caption_text}</b>', 
                        parse_mode='HTML',
                        supports_streaming=True
                    )
             return True
        else:
             raise Exception("فشل yt-dlp في حفظ أو إيجاد الملف بعد التنزيل.")
