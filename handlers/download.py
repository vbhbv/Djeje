import os
import tempfile
import yt_dlp
import json
import re
import math

# ===============================================
#              0. دوال التخزين الدائم (Persistent Storage)
# ===============================================

TEMP_STORAGE_FILE = 'temp_links.json' 

def load_links():
    """تحميل جميع الروابط المخزنة من ملف JSON."""
    if os.path.exists(TEMP_STORAGE_FILE):
        try:
            with open(TEMP_STORAGE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_links(data):
    """حفظ الروابط الحالية إلى ملف JSON."""
    try:
        with open(TEMP_STORAGE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ فشل حفظ البيانات في ملف JSON: {e}")

# ===============================================
#              1. دالة قص الفيديو (الميزة 3)
# ===============================================

def clip_video(input_path, output_path, start_time_str, end_time_str):
    """قص الفيديو باستخدام MoviePy."""
    try:
        # تحويل الأوقات من ثواني/دقائق إلى ثواني
        start_time = parse_time_to_seconds(start_time_str)
        end_time = parse_time_to_seconds(end_time_str)
        
        if start_time >= end_time:
            raise ValueError("نقطة النهاية يجب أن تكون بعد نقطة البداية.")
            
        with VideoFileClip(input_path) as clip:
            final_clip = clip.subclip(start_time, end_time)
            final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
        
        return True
    except Exception as e:
        raise Exception(f"فشل عملية القص: {e}")

def parse_time_to_seconds(time_str):
    """تحويل (MM:SS) أو (SS) إلى ثواني."""
    if ':' in time_str:
        minutes, seconds = map(float, time_str.split(':'))
        return minutes * 60 + seconds
    return float(time_str)

# ===============================================
#              2. دالة التحميل الرئيسية (الميزات 1 و 2)
# ===============================================

def download_media_yt_dlp(bot, chat_id, url, platform_name, loading_msg_id, download_as_mp3=False, clip_times=None):
    """
    دالة متخصصة للتحميل المباشر باستخدام yt-dlp وإرسال الملف.
    """
    
    # 🚨 التحميل السريع عبر الرابط المباشر (Direct CDN) - الميزة 2
    try:
        ydl_opts_info = {'quiet': True, 'skip_download': True, 'force_generic_extractor': True}
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # محاولة إرسال رابط مباشر لتقليل استهلاك الخادم (خاصة انستجرام وتيك توك)
            if 'direct_link' in info.get('requested_formats', [{}])[0]:
                direct_link = info['requested_formats'][0]['direct_link']
                bot.delete_message(chat_id, loading_msg_id)
                
                caption_text = f"✅ تم التحميل مباشرةً من {platform_name} بواسطة: @SuPeRx1"
                bot.send_video(
                    chat_id,
                    direct_link, # إرسال الرابط المباشر
                    caption=f'<b>{caption_text}</b>', 
                    parse_mode='HTML',
                    supports_streaming=True
                )
                return True
                
    except Exception as e:
        # إذا فشل التحميل المباشر، نعود لعملية التحميل التقليدية
        print(f"فشل التحميل المباشر: {e}. العودة للتحميل عبر الخادم...")


    # 🧹 التحميل التقليدي عبر الخادم (للفيديوهات التي لا تدعم CDN، أو التحويل لـ MP3/القص)
    with tempfile.TemporaryDirectory() as tmpdir:
        output_ext = 'mp4' if not download_as_mp3 and not clip_times else 'mp4' # يتم تحديد اللاحقة لاحقاً بعد القص/التحويل
        initial_file_path = os.path.join(tmpdir, f'initial_download.mp4')
        final_file_path = os.path.join(tmpdir, f'final_output.{output_ext}')

        ydl_opts = {
            'outtmpl': initial_file_path,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'cookiefile': None,
            # 🚨 تفعيل استخراج البيانات الوصفية والصورة المصغرة (الميزة 1)
            'writethumbnail': True, 
            'postprocessors': [
                {'key': 'FFmpegMetadata'}, # يضيف البيانات الوصفية
                {'key': 'EmbedThumbnail'},  # يضيف الصورة المصغرة لملف الفيديو
            ],
            'format': 'bestaudio/best' if download_as_mp3 else 'best[ext=mp4]/best',
        }
        
        # 🚨 إضافة خيارات التحويل لـ MP3
        if download_as_mp3:
             ydl_opts['postprocessors'].append({
                 'key': 'FFmpegExtractAudio',
                 'preferredcodec': 'mp3',
                 'preferredquality': '192',
             })
             final_file_path = os.path.join(tmpdir, f'final_output.mp3')
             
        # 1. بدء التنزيل
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
        # 2. القص (إذا طلب) - الميزة 3
        current_path = initial_file_path
        if clip_times:
            start_time, end_time = clip_times
            clip_video(initial_file_path, final_file_path, start_time, end_time)
            current_path = final_file_path # الآن سنرسل الملف المقصوص
        
        # إذا لم يكن هناك قص ولكن كان هناك تحويل MP3
        elif download_as_mp3:
            current_path = final_file_path
        
        # إذا لم يكن هناك قص ولا تحويل MP3
        else:
            current_path = initial_file_path 
            
        # 3. حذف رسالة "جاري التحميل"
        bot.delete_message(chat_id, loading_msg_id)
        
        # 4. الإرسال إلى تيليجرام
        CHANNEL_USERNAME = "@SuPeRx1"
        caption_text = f"✅ تم التحميل من {platform_name} بواسطة: {CHANNEL_USERNAME}"
        
        if os.path.exists(current_path):
             with open(current_path, 'rb') as f:
                if 'mp3' in current_path.lower():
                    bot.send_audio(chat_id, f, caption=f'<b>{caption_text}</b>', parse_mode='HTML')
                else:
                    bot.send_video(chat_id, f, caption=f'<b>{caption_text}</b>', parse_mode='HTML', supports_streaming=True)
             return True
        else:
             raise Exception(f"فشل حفظ أو إيجاد الملف النهائي ({current_path}).")
