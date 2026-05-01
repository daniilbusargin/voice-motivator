"""
Mock product catalog and prices across 5 grocery chains.
Prices are approximate and reflect realistic Russian market as of 2025.
"""

from typing import Dict, List, Any

STORES: Dict[str, Dict[str, Any]] = {
    "magnit": {
        "id": "magnit",
        "name": "Магнит",
        "color": "#e11f28",
        "delivery_fee": 149,
        "free_delivery_from": 999,
        "min_order": 300,
    },
    "pyaterochka": {
        "id": "pyaterochka",
        "name": "Пятёрочка",
        "color": "#ef7f1a",
        "delivery_fee": 149,
        "free_delivery_from": 1499,
        "min_order": 500,
    },
    "auchan": {
        "id": "auchan",
        "name": "Ашан",
        "color": "#e2001a",
        "delivery_fee": 299,
        "free_delivery_from": 2500,
        "min_order": 1000,
    },
    "lenta": {
        "id": "lenta",
        "name": "Лента",
        "color": "#f7941d",
        "delivery_fee": 199,
        "free_delivery_from": 1500,
        "min_order": 500,
    },
    "dixy": {
        "id": "dixy",
        "name": "Дикси",
        "color": "#e5002b",
        "delivery_fee": 99,
        "free_delivery_from": 599,
        "min_order": 200,
    },
}

# Products: id, name, category, unit
PRODUCTS: List[Dict[str, str]] = [
    # Молочные
    {"id": "milk_1l",       "name": "Молоко 3.2% 1л",           "category": "Молочные", "unit": "шт"},
    {"id": "kefir_1l",      "name": "Кефир 1% 1л",               "category": "Молочные", "unit": "шт"},
    {"id": "tvorog_200g",   "name": "Творог 9% 200г",            "category": "Молочные", "unit": "шт"},
    {"id": "butter_180g",   "name": "Масло сливочное 82.5% 180г","category": "Молочные", "unit": "шт"},
    {"id": "smetana_200g",  "name": "Сметана 15% 200г",          "category": "Молочные", "unit": "шт"},
    {"id": "yogurt_150g",   "name": "Йогурт натуральный 150г",   "category": "Молочные", "unit": "шт"},
    {"id": "cheese_200g",   "name": "Сыр Российский 200г",       "category": "Молочные", "unit": "шт"},
    # Хлеб
    {"id": "bread_white",   "name": "Хлеб пшеничный 600г",      "category": "Хлеб", "unit": "шт"},
    {"id": "bread_black",   "name": "Хлеб ржаной 350г",         "category": "Хлеб", "unit": "шт"},
    {"id": "baton",         "name": "Батон нарезной 400г",       "category": "Хлеб", "unit": "шт"},
    # Крупы и макароны
    {"id": "rice_1kg",      "name": "Рис круглый 1кг",           "category": "Крупы", "unit": "шт"},
    {"id": "buckwheat_1kg", "name": "Гречка ядрица 1кг",         "category": "Крупы", "unit": "шт"},
    {"id": "pasta_450g",    "name": "Макароны спагетти 450г",    "category": "Крупы", "unit": "шт"},
    {"id": "oatmeal_500g",  "name": "Овсянка Геркулес 500г",     "category": "Крупы", "unit": "шт"},
    {"id": "flour_2kg",     "name": "Мука пшеничная 2кг",        "category": "Крупы", "unit": "шт"},
    # Мясо и птица
    {"id": "chicken_f_1kg","name": "Куриное филе 1кг",           "category": "Мясо", "unit": "шт"},
    {"id": "mince_500g",    "name": "Фарш говяжий 500г",         "category": "Мясо", "unit": "шт"},
    {"id": "pork_1kg",      "name": "Свинина шея 1кг",           "category": "Мясо", "unit": "шт"},
    {"id": "sausage_400g",  "name": "Сосиски молочные 400г",     "category": "Мясо", "unit": "шт"},
    # Овощи и фрукты
    {"id": "potato_1kg",    "name": "Картофель 1кг",             "category": "Овощи и фрукты", "unit": "кг"},
    {"id": "carrot_1kg",    "name": "Морковь 1кг",               "category": "Овощи и фрукты", "unit": "кг"},
    {"id": "onion_1kg",     "name": "Лук репчатый 1кг",          "category": "Овощи и фрукты", "unit": "кг"},
    {"id": "tomato_1kg",    "name": "Помидоры 1кг",              "category": "Овощи и фрукты", "unit": "кг"},
    {"id": "cucumber_1kg",  "name": "Огурцы 1кг",                "category": "Овощи и фрукты", "unit": "кг"},
    {"id": "apple_1kg",     "name": "Яблоки Голден 1кг",         "category": "Овощи и фрукты", "unit": "кг"},
    {"id": "banana_1kg",    "name": "Бананы 1кг",                "category": "Овощи и фрукты", "unit": "кг"},
    # Яйца
    {"id": "eggs_10",       "name": "Яйца С1 10шт",              "category": "Яйца", "unit": "шт"},
    # Консервы
    {"id": "tuna_can",      "name": "Тунец в масле 185г",        "category": "Консервы", "unit": "шт"},
    {"id": "peas_can",      "name": "Горошек зелёный 400г",      "category": "Консервы", "unit": "шт"},
    {"id": "corn_can",      "name": "Кукуруза сладкая 400г",     "category": "Консервы", "unit": "шт"},
    # Бакалея
    {"id": "sunflower_oil", "name": "Масло подсолнечное 1л",     "category": "Бакалея", "unit": "шт"},
    {"id": "sugar_1kg",     "name": "Сахар-песок 1кг",           "category": "Бакалея", "unit": "шт"},
    {"id": "salt_1kg",      "name": "Соль пищевая 1кг",          "category": "Бакалея", "unit": "шт"},
    # Напитки
    {"id": "water_1_5l",    "name": "Вода питьевая 1.5л",        "category": "Напитки", "unit": "шт"},
    {"id": "juice_1l",      "name": "Сок апельсиновый 1л",       "category": "Напитки", "unit": "шт"},
    {"id": "tea_100g",      "name": "Чай чёрный листовой 100г",  "category": "Напитки", "unit": "шт"},
    {"id": "coffee_95g",    "name": "Кофе растворимый 95г",      "category": "Напитки", "unit": "шт"},
    # Сладкое и снеки
    {"id": "chocolate_100g","name": "Шоколад молочный 100г",     "category": "Сладкое", "unit": "шт"},
    {"id": "cookies_400g",  "name": "Печенье сахарное 400г",     "category": "Сладкое", "unit": "шт"},
]

# Prices per product per store (in RUB).
# None means product is not available at that store.
# magnit / pyaterochka / auchan / lenta / dixy
PRICES: Dict[str, Dict[str, float]] = {
    "milk_1l":       {"magnit": 89,  "pyaterochka": 85,  "auchan": 79,  "lenta": 82,  "dixy": 87},
    "kefir_1l":      {"magnit": 75,  "pyaterochka": 72,  "auchan": 68,  "lenta": 71,  "dixy": 74},
    "tvorog_200g":   {"magnit": 89,  "pyaterochka": 92,  "auchan": 84,  "lenta": 86,  "dixy": 90},
    "butter_180g":   {"magnit": 189, "pyaterochka": 185, "auchan": 175, "lenta": 179, "dixy": 192},
    "smetana_200g":  {"magnit": 79,  "pyaterochka": 76,  "auchan": 72,  "lenta": 74,  "dixy": 81},
    "yogurt_150g":   {"magnit": 55,  "pyaterochka": 52,  "auchan": 49,  "lenta": 51,  "dixy": 57},
    "cheese_200g":   {"magnit": 219, "pyaterochka": 225, "auchan": 205, "lenta": 212, "dixy": 229},
    "bread_white":   {"magnit": 55,  "pyaterochka": 52,  "auchan": 49,  "lenta": 53,  "dixy": 54},
    "bread_black":   {"magnit": 49,  "pyaterochka": 47,  "auchan": 44,  "lenta": 46,  "dixy": 50},
    "baton":         {"magnit": 42,  "pyaterochka": 39,  "auchan": 37,  "lenta": 40,  "dixy": 43},
    "rice_1kg":      {"magnit": 89,  "pyaterochka": 86,  "auchan": 79,  "lenta": 83,  "dixy": 91},
    "buckwheat_1kg": {"magnit": 119, "pyaterochka": 115, "auchan": 109, "lenta": 112, "dixy": 122},
    "pasta_450g":    {"magnit": 65,  "pyaterochka": 62,  "auchan": 58,  "lenta": 61,  "dixy": 67},
    "oatmeal_500g":  {"magnit": 89,  "pyaterochka": 85,  "auchan": 79,  "lenta": 83,  "dixy": 92},
    "flour_2kg":     {"magnit": 99,  "pyaterochka": 95,  "auchan": 89,  "lenta": 92,  "dixy": 102},
    "chicken_f_1kg": {"magnit": 329, "pyaterochka": 319, "auchan": 299, "lenta": 309, "dixy": 339},
    "mince_500g":    {"magnit": 259, "pyaterochka": 249, "auchan": 235, "lenta": 245, "dixy": 265},
    "pork_1kg":      {"magnit": 449, "pyaterochka": 439, "auchan": 419, "lenta": 429, "dixy": None},
    "sausage_400g":  {"magnit": 189, "pyaterochka": 179, "auchan": 169, "lenta": 175, "dixy": 195},
    "potato_1kg":    {"magnit": 42,  "pyaterochka": 39,  "auchan": 35,  "lenta": 37,  "dixy": 44},
    "carrot_1kg":    {"magnit": 39,  "pyaterochka": 36,  "auchan": 32,  "lenta": 34,  "dixy": 41},
    "onion_1kg":     {"magnit": 35,  "pyaterochka": 32,  "auchan": 29,  "lenta": 31,  "dixy": 37},
    "tomato_1kg":    {"magnit": 149, "pyaterochka": 139, "auchan": 129, "lenta": 135, "dixy": 155},
    "cucumber_1kg":  {"magnit": 129, "pyaterochka": 119, "auchan": 109, "lenta": 115, "dixy": 135},
    "apple_1kg":     {"magnit": 119, "pyaterochka": 115, "auchan": 105, "lenta": 109, "dixy": 125},
    "banana_1kg":    {"magnit": 99,  "pyaterochka": 95,  "auchan": 89,  "lenta": 92,  "dixy": 105},
    "eggs_10":       {"magnit": 99,  "pyaterochka": 95,  "auchan": 89,  "lenta": 92,  "dixy": 102},
    "tuna_can":      {"magnit": 179, "pyaterochka": 175, "auchan": 165, "lenta": 169, "dixy": None},
    "peas_can":      {"magnit": 59,  "pyaterochka": 56,  "auchan": 52,  "lenta": 54,  "dixy": 61},
    "corn_can":      {"magnit": 59,  "pyaterochka": 56,  "auchan": 52,  "lenta": 54,  "dixy": 61},
    "sunflower_oil": {"magnit": 149, "pyaterochka": 145, "auchan": 135, "lenta": 139, "dixy": 155},
    "sugar_1kg":     {"magnit": 79,  "pyaterochka": 75,  "auchan": 69,  "lenta": 72,  "dixy": 82},
    "salt_1kg":      {"magnit": 29,  "pyaterochka": 27,  "auchan": 24,  "lenta": 26,  "dixy": 31},
    "water_1_5l":    {"magnit": 39,  "pyaterochka": 36,  "auchan": 32,  "lenta": 34,  "dixy": 41},
    "juice_1l":      {"magnit": 119, "pyaterochka": 115, "auchan": 105, "lenta": 109, "dixy": 125},
    "tea_100g":      {"magnit": 129, "pyaterochka": 125, "auchan": 115, "lenta": 119, "dixy": 135},
    "coffee_95g":    {"magnit": 279, "pyaterochka": 269, "auchan": 249, "lenta": 259, "dixy": 289},
    "chocolate_100g":{"magnit": 99,  "pyaterochka": 95,  "auchan": 89,  "lenta": 92,  "dixy": 105},
    "cookies_400g":  {"magnit": 119, "pyaterochka": 115, "auchan": 109, "lenta": 112, "dixy": 125},
}
