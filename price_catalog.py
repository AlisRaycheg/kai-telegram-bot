# price_catalog.py
import os
import json

class PriceCatalog:
    def __init__(self):
        self.prices = {
            "mm2": {},
            "adoptme": {}
        }
        self.load_prices()

    def load_prices(self):
        try:
            if os.path.exists("prices.json"):
                with open("prices.json", "r", encoding="utf-8") as f:
                    self.prices = json.load(f)
            else:
                self._create_default_prices()
        except:
            self._create_default_prices()

    def _create_default_prices(self):
        self.prices = {
            "mm2": {
                "godly_knife": 5.00, "chroma_knife": 10.00, "vintage_knife": 8.00,
                "ancient_knife": 15.00, "godly_gun": 5.00, "chroma_gun": 12.50,
                "vintage_gun": 6.00, "legendary_knife": 1.00, "rare_knife": 0.50,
                "uncommon_knife": 0.25, "common_knife": 0.10, "godly": 5.00,
                "chroma": 10.00, "vintage": 8.00, "ancient": 15.00,
                "legendary": 1.00, "rare": 0.50
            },
            "adoptme": {
                "shadow_dragon": 35.00, "frost_dragon": 28.00, "giraffe": 20.00,
                "mega_neon_unicorn": 25.00, "neon_parrot": 15.00, "neon_dragon": 12.00,
                "fly_ride_turtle": 6.00, "ride_kangaroo": 4.00, "fly_unicorn": 3.50,
                "unicorn": 2.00, "dragon": 1.50, "turtle": 1.00, "kangaroo": 0.80
            }
        }
        self.save_prices()

    def save_prices(self):
        try:
            with open("prices.json", "w", encoding="utf-8") as f:
                json.dump(self.prices, f, indent=2, ensure_ascii=False)
        except:
            pass

    def get_price(self, game, item_name, category=None):
        game_data = self.prices.get(game, {})
        if not game_data:
            return 0.0
        item_name = item_name.lower().strip()
        if item_name in game_data:
            return game_data[item_name]
        item_lower = item_name.lower()
        for key, price in game_data.items():
            if key.lower() in item_lower or item_lower in key.lower():
                return price
        if category and category.lower() in game_data:
            return game_data[category.lower()]
        return 0.0

    def estimate_gamepasses(self, game, gamepasses):
        total = 0.0
        valuable_items = []
        for game_name, passes in gamepasses.items():
            for p in passes:
                name = p.get('name', 'Товар')
                price_val = p.get('price', 0)
                estimated = self.get_price(game, name)
                if estimated > 0:
                    total += estimated
                    valuable_items.append({
                        'name': name,
                        'game': game_name,
                        'robux_price': price_val,
                        'estimated_usd': estimated
                    })
                elif price_val > 0:
                    estimated = price_val * 0.0035
                    total += estimated
                    valuable_items.append({
                        'name': name,
                        'game': game_name,
                        'robux_price': price_val,
                        'estimated_usd': estimated
                    })
        valuable_items.sort(key=lambda x: x['estimated_usd'], reverse=True)
        return total, valuable_items