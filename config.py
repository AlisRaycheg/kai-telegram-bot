# config.py
import os

TELEGRAM_BOT_TOKEN = "8838554185:AAEcnODJD01mvseF2Lnvr3WbYB88Y2KTNAk"
MAX_THREADS = 5
LOGO_URL = "https://1s4oyld5dc.ucarecd.net/c1f49818-fb27-4bf7-9427-1ed661dc880d/"

# Ценники для оценки аккаунта
PRICE_PER_1K_ROBUX = 3.8
PRICE_GROUP_DISCOUNT = 0.8
PRICE_PER_1K_RAP = 2.2
PRICE_RAP_MIN = 10000
PRICE_KORBLOX = 20
PRICE_KORBLOX_DISCOUNT = 10
PRICE_HEADLESS = 55
PRICE_HEADLESS_DISCOUNT = 40
PRICE_COMBO = 90
PRICE_COMBO_DISCOUNT = 60
PRICE_PREMIUM = 1.5
PRICE_ACTIVE_MIN_MINUTES = 60

# Паттерны редких предметов
RARE_ITEM_PATTERNS = [
    'valkyrie', 'valk', '8 bit crown', '8-bit crown',
    'infernal deathwalker', 'korblox deathwalker',
    'tentacles', 'rainbow barf face', 'otakufaic',
    'pop queen', 'princess alexis', 'sapphire gaze',
    'arachnid queen', 'persephone', 'winning smile',
    'tsundere', 'star sorority', 'navy queen',
    'golden horns of pwnage', 'white sword cane',
    'headless horseman', 'headless head',
    'epic face', 'ninja face', 'poisonous beast mode',
    'workclock headphones', 'workclock shades',
    'clockwork headphones', 'clockwork shades',
    'festive sword valkyrie', 'sly cat', 'yaik',
    'shy lady', 'pink wistful wink', 'epic vampire face',
    'doomsekkar', 'dusekkar', 'ghost fedora'
]

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

DB_FILE = "bot.db"