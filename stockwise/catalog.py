"""Display catalogue: a made-up product name, pack, group, emoji, photo title and rupee price for each M5 item.
Only the presentation layer. The forecasts and detections still use the real M5 item IDs."""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ["Produce", "Dairy", "Beverages", "Grocery", "Snacks", "Household", "Hobbies"]

# item_id, name, pack, group, emoji, Wikipedia article title for the photo, price in rupees
_ROWS = [
    ("FOODS_1_017", "Fresh Mangoes", "1 kg", "Produce", "\U0001F96D", "Mango", 160),
    ("FOODS_1_114", "Bananas", "12 pc", "Produce", "\U0001F34C", "Banana", 60),
    ("FOODS_1_141", "Fresh Spinach", "250 g", "Produce", "\U0001F96C", "Spinach", 25),
    ("FOODS_1_181", "Tomatoes", "1 kg", "Produce", "\U0001F345", "Tomato", 40),
    ("FOODS_1_186", "Cucumbers", "500 g", "Produce", "\U0001F952", "Cucumber", 30),
    ("FOODS_1_205", "Carrots", "500 g", "Produce", "\U0001F955", "Carrot", 40),
    ("FOODS_1_217", "Onions", "1 kg", "Produce", "\U0001F9C5", "Onion", 35),
    ("FOODS_2_032", "Paneer", "200 g", "Dairy", "\U0001F9C0", "Paneer", 90),
    ("FOODS_2_041", "Butter", "100 g", "Dairy", "\U0001F9C8", "Butter", 58),
    ("FOODS_2_045", "Plain Yogurt", "400 g", "Dairy", "\U0001F963", "Yogurt", 40),
    ("FOODS_2_056", "Farm Eggs", "12 pc", "Dairy", "\U0001F95A", "Egg_as_food", 84),
    ("FOODS_2_078", "Cheddar Cheese", "200 g", "Dairy", "\U0001F9C0", "Cheddar_cheese", 140),
    ("FOODS_2_147", "Pure Ghee", "500 ml", "Dairy", "\U0001F9C8", "Ghee", 320),
    ("FOODS_2_165", "Soy Milk", "1 L", "Dairy", "\U0001F95B", "Soy_milk", 110),
    ("FOODS_2_214", "Black Tea", "250 g", "Beverages", "\U0001F375", "Black_tea", 130),
    ("FOODS_2_217", "Filter Coffee Powder", "200 g", "Beverages", "\u2615", "Coffee", 180),
    ("FOODS_2_235", "Tender Coconut Water", "200 ml", "Beverages", "\U0001F965", "Coconut_water", 30),
    ("FOODS_2_242", "Orange Juice", "1 L", "Beverages", "\U0001F9C3", "Orange_juice", 110),
    ("FOODS_2_244", "Packaged Drinking Water", "1 L", "Beverages", "\U0001F4A7", "Bottled_water", 20),
    ("FOODS_2_267", "Sweet Lassi", "200 ml", "Beverages", "\U0001F95B", "Lassi", 25),
    ("FOODS_3_050", "Basmati Rice", "5 kg", "Grocery", "\U0001F35A", "Basmati", 520),
    ("FOODS_3_053", "Whole Wheat Atta", "5 kg", "Grocery", "\U0001F33E", "Wheat_flour", 260),
    ("FOODS_3_067", "Red Lentils (Masoor Dal)", "1 kg", "Grocery", "\U0001FAD8", "Lentil", 110),
    ("FOODS_3_080", "Toned Milk", "500 ml", "Dairy", "\U0001F95B", "Milk", 27),
    ("FOODS_3_125", "Sugar", "1 kg", "Grocery", "\U0001F36C", "Sugar", 48),
    ("FOODS_3_143", "Iodised Salt", "1 kg", "Grocery", "\U0001F9C2", "Salt", 28),
    ("FOODS_3_161", "Sunflower Oil", "1 L", "Grocery", "\U0001F33B", "Sunflower_oil", 150),
    ("FOODS_3_164", "Mustard Oil", "500 ml", "Grocery", "\U0001FAD2", "Mustard_oil", 95),
    ("FOODS_3_165", "Honey", "250 g", "Grocery", "\U0001F36F", "Honey", 130),
    ("FOODS_3_186", "Turmeric Powder", "100 g", "Grocery", "\U0001F7E1", "Turmeric", 40),
    ("FOODS_3_221", "Red Chilli Powder", "100 g", "Grocery", "\U0001F336\uFE0F", "Chili_powder", 45),
    ("FOODS_3_236", "Black Pepper", "50 g", "Grocery", "\u26AB", "Black_pepper", 70),
    ("FOODS_3_264", "Cumin Seeds", "100 g", "Grocery", "\U0001F33F", "Cumin", 55),
    ("FOODS_3_266", "Roasted Peanuts", "500 g", "Snacks", "\U0001F95C", "Peanut", 90),
    ("FOODS_3_270", "Cashew Nuts", "250 g", "Snacks", "\U0001F95C", "Cashew", 260),
    ("FOODS_3_281", "Sandwich Bread", "400 g", "Grocery", "\U0001F35E", "Bread", 45),
    ("FOODS_3_308", "Wheat Pasta", "500 g", "Grocery", "\U0001F35D", "Pasta", 85),
    ("FOODS_3_385", "Rolled Oats", "1 kg", "Grocery", "\U0001F963", "Rolled_oats", 190),
    ("FOODS_3_428", "Digestive Biscuits", "250 g", "Snacks", "\U0001F36A", "Digestive_biscuit", 40),
    ("FOODS_3_556", "Potato Chips", "52 g", "Snacks", "\U0001F954", "Potato_chip", 20),
    ("FOODS_3_599", "Dark Chocolate", "100 g", "Snacks", "\U0001F36B", "Dark_chocolate", 150),
    ("FOODS_3_698", "Namkeen Mixture", "200 g", "Snacks", "\U0001F968", "Bombay_mix", 60),
    ("FOODS_3_704", "Instant Noodles", "70 g", "Grocery", "\U0001F35C", "Instant_noodles", 14),
    ("FOODS_3_759", "Popcorn", "100 g", "Snacks", "\U0001F37F", "Popcorn", 40),
    ("FOODS_3_762", "Peanut Butter", "340 g", "Snacks", "\U0001F95C", "Peanut_butter", 180),
    ("FOODS_3_787", "Apples", "1 kg", "Produce", "\U0001F34E", "Apple", 180),
    ("FOODS_3_809", "Potatoes", "1 kg", "Produce", "\U0001F954", "Potato", 35),
    ("HOBBIES_1_016", "Ruled Notebook", "A5", "Hobbies", "\U0001F4D3", "Notebook", 60),
    ("HOBBIES_1_042", "Ball Pens", "Pack of 10", "Hobbies", "\U0001F58A\uFE0F", "Ballpoint_pen", 100),
    ("HOBBIES_1_043", "Pencils", "Pack of 10", "Hobbies", "\u270F\uFE0F", "Pencil", 50),
    ("HOBBIES_1_048", "Erasers", "Pack of 5", "Hobbies", "\u270F\uFE0F", "Eraser", 25),
    ("HOBBIES_1_057", "Wax Crayons", "24 shades", "Hobbies", "\U0001F58D\uFE0F", "Crayon", 90),
    ("HOBBIES_1_073", "Paint Brush Set", "Set of 6", "Hobbies", "\U0001F58C\uFE0F", "Paintbrush", 120),
    ("HOBBIES_1_089", "School Scissors", "1 pc", "Hobbies", "\u2702\uFE0F", "Scissors", 60),
    ("HOBBIES_1_099", "Glue Stick", "1 pc", "Hobbies", "\U0001F9F4", "Glue_stick", 30),
    ("HOBBIES_1_132", "Jigsaw Puzzle", "500 pc", "Hobbies", "\U0001F9E9", "Jigsaw_puzzle", 350),
    ("HOBBIES_1_139", "Playing Cards", "1 deck", "Hobbies", "\U0001F0CF", "Playing_card", 80),
    ("HOBBIES_1_207", "Chess Set", "1 set", "Hobbies", "\u265F\uFE0F", "Chess", 450),
    ("HOBBIES_1_285", "Football", "Size 5", "Hobbies", "\u26BD", "Ball_(association_football)", 550),
    ("HOBBIES_1_360", "Skipping Rope", "1 pc", "Hobbies", "\U0001FAA2", "Jump_rope", 120),
    ("HOBBIES_1_386", "Kite", "1 pc", "Hobbies", "\U0001FA81", "Kite", 40),
    ("HOBBIES_2_013", "Harmonica", "1 pc", "Hobbies", "\U0001F3B5", "Harmonica", 250),
    ("HOBBIES_2_054", "Ukulele", "1 pc", "Hobbies", "\U0001F3B8", "Ukulele", 1800),
    ("HOBBIES_2_112", "Knitting Yarn", "100 g", "Hobbies", "\U0001F9F6", "Yarn", 90),
    ("HOBBIES_2_117", "Tabla Set", "1 set", "Hobbies", "\U0001F941", "Tabla", 3500),
    ("HOBBIES_2_131", "Bansuri Flute", "1 pc", "Hobbies", "\U0001F3B6", "Bansuri", 300),
    ("HOUSEHOLD_1_063", "Detergent Powder", "1 kg", "Household", "\U0001F9FA", "Laundry_detergent", 110),
    ("HOUSEHOLD_1_077", "Bathing Soap", "100 g", "Household", "\U0001F9FC", "Soap", 40),
    ("HOUSEHOLD_1_115", "Toothpaste", "150 g", "Household", "\U0001FAA5", "Toothpaste", 95),
    ("HOUSEHOLD_1_133", "Toothbrush", "1 pc", "Household", "\U0001FAA5", "Toothbrush", 30),
    ("HOUSEHOLD_1_180", "Dishwash Liquid", "500 ml", "Household", "\U0001F37D\uFE0F", "Dishwashing_liquid", 110),
    ("HOUSEHOLD_1_182", "Broom", "1 pc", "Household", "\U0001F9F9", "Broom", 90),
    ("HOUSEHOLD_1_189", "Floor Mop", "1 pc", "Household", "\U0001F9F9", "Mop", 250),
    ("HOUSEHOLD_1_201", "Scrub Sponge", "Pack of 3", "Household", "\U0001F9FD", "Sponge_(tool)", 30),
    ("HOUSEHOLD_1_211", "Plastic Bucket", "16 L", "Household", "\U0001FAA3", "Bucket", 150),
    ("HOUSEHOLD_1_314", "Garbage Bags", "Pack of 30", "Household", "\U0001F5D1\uFE0F", "Bin_bag", 80),
    ("HOUSEHOLD_1_319", "Facial Tissues", "100 pulls", "Household", "\U0001F9FB", "Facial_tissue", 60),
    ("HOUSEHOLD_1_356", "Aluminium Foil", "9 m", "Household", "\U0001F4E6", "Aluminium_foil", 110),
    ("HOUSEHOLD_1_422", "Safety Matches", "Pack of 10", "Household", "\U0001F525", "Match", 10),
    ("HOUSEHOLD_1_433", "Candles", "Pack of 6", "Household", "\U0001F56F\uFE0F", "Candle", 40),
    ("HOUSEHOLD_1_455", "LED Bulb", "9 W", "Household", "\U0001F4A1", "LED_lamp", 90),
    ("HOUSEHOLD_1_457", "Hand Sanitizer", "100 ml", "Household", "\U0001F9F4", "Hand_sanitizer", 60),
    ("HOUSEHOLD_1_525", "Shampoo", "340 ml", "Household", "\U0001F9F4", "Shampoo", 180),
    ("HOUSEHOLD_2_056", "Bath Towel", "1 pc", "Household", "\U0001F6C1", "Towel", 250),
    ("HOUSEHOLD_2_073", "Pillow", "1 pc", "Household", "\U0001F6CF\uFE0F", "Pillow", 350),
    ("HOUSEHOLD_2_094", "Woollen Blanket", "1 pc", "Household", "\U0001F6CC", "Blanket", 650),
    ("HOUSEHOLD_2_103", "Window Curtains", "Pair", "Household", "\U0001FA9F", "Curtain", 450),
    ("HOUSEHOLD_2_145", "Door Mat", "1 pc", "Household", "\U0001F6AA", "Doormat", 180),
    ("HOUSEHOLD_2_166", "Wall Clock", "1 pc", "Household", "\U0001F570\uFE0F", "Clock", 350),
    ("HOUSEHOLD_2_191", "Flower Vase", "1 pc", "Household", "\U0001F3FA", "Vase", 250),
    ("HOUSEHOLD_2_196", "Photo Frame", "6x4 in", "Household", "\U0001F5BC\uFE0F", "Picture_frame", 150),
    ("HOUSEHOLD_2_295", "Steel Water Bottle", "750 ml", "Household", "\U0001F964", "Water_bottle", 300),
    ("HOUSEHOLD_2_307", "Lunch Box", "1 pc", "Household", "\U0001F371", "Lunchbox", 280),
    ("HOUSEHOLD_2_434", "Extension Board", "4 socket", "Household", "\U0001F50C", "Power_strip", 350),
    ("HOUSEHOLD_2_440", "Electric Kettle", "1.5 L", "Household", "\U0001FAD6", "Electric_kettle", 900),
    ("HOUSEHOLD_2_467", "Pressure Cooker", "5 L", "Household", "\U0001F372", "Pressure_cooker", 1400),
    ("HOUSEHOLD_2_491", "Umbrella", "1 pc", "Household", "\u2602\uFE0F", "Umbrella", 350),
    ("HOUSEHOLD_2_504", "Hair Dryer", "1200 W", "Household", "\U0001F4A8", "Hair_dryer", 800),
    ("HOUSEHOLD_2_514", "Steam Iron", "1 pc", "Household", "\U0001F454", "Clothes_iron", 1100),
]

EXCLUDED = {"HOUSEHOLD_2_483"}  # hidden from the app on request; its data stays in the database
CATALOG = {r[0]: dict(name=r[1], pack=r[2], group=r[3], emoji=r[4], wiki=r[5], price=r[6]) for r in _ROWS}


def info(item_id):
    return CATALOG[item_id]


def label(item_id):
    c = CATALOG[item_id]
    return f"{c['name']} ({c['pack']})"


@lru_cache(maxsize=1)
def _photos():
    p = ROOT / "data" / "photos.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def photo_url(item_id):
    return _photos().get(CATALOG[item_id]["wiki"])