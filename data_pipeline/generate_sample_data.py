"""
data_pipeline/generate_sample_data.py
──────────────────────────────────────
Generates realistic, schema-accurate synthetic Yelp dataset files for testing
and development when the actual multi-gigabyte Yelp Open Dataset is not available.

Files generated:
  - business.json (or yelp_academic_dataset_business.json)
  - review.json   (or yelp_academic_dataset_review.json)
  - user.json     (or yelp_academic_dataset_user.json)

CRITICAL SAFETY RULE:
  All synthetic records have:
    1. 'is_synthetic': True flag.
    2. Identifiers prefixed with 'syn_' (e.g. 'syn_b_001', 'syn_u_001', 'syn_r_001').
  Synthetic records are saved exclusively to sample/test directories and are
  never mixed with real Yelp dataset exports.

Usage:
  python data_pipeline/generate_sample_data.py --output-dir data/sample_raw --num-restaurants 60
"""

import os
import sys
import json
import random
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Configure sys.path so the script can be invoked from any directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# UTF-8 stdout configuration for Windows PowerShell
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tastetrail.generator")

# ── Realistic seed data ────────────────────────────────────────────────────────
CITIES_DATA = [
    {"city": "Philadelphia", "state": "PA", "postal_code": "19107", "lat": 39.9526, "lon": -75.1652},
    {"city": "Tampa", "state": "FL", "postal_code": "33602", "lat": 27.9506, "lon": -82.4572},
    {"city": "Nashville", "state": "TN", "postal_code": "37203", "lat": 36.1627, "lon": -86.7816},
    {"city": "Tucson", "state": "AZ", "postal_code": "85701", "lat": 32.2226, "lon": -110.9747},
    {"city": "Indianapolis", "state": "IN", "postal_code": "46204", "lat": 39.7684, "lon": -86.1581},
    {"city": "New Orleans", "state": "LA", "postal_code": "70112", "lat": 29.9511, "lon": -90.0715},
]

CUISINE_PROFILES = [
    {
        "names": ["Bella Trattoria", "Luigi's Osteria", "Pasta Fresca", "Nonna's Kitchen", "Via Veneto"],
        "categories": ["Restaurants", "Italian", "Pizza", "Bars", "Wine Bars"],
        "price": "2",
    },
    {
        "names": ["Golden Dragon", "Sichuan Spice House", "Wok & Roll", "Dim Sum Palace", "Jade Garden"],
        "categories": ["Restaurants", "Chinese", "Asian Fusion", "Noodles"],
        "price": "1",
    },
    {
        "names": ["El Sombrero", "Taqueria Los Amigos", "Cantina del Sol", "Tacos & Mezcal", "La Fiesta"],
        "categories": ["Restaurants", "Mexican", "Bars", "Cocktail Bars"],
        "price": "2",
    },
    {
        "names": ["The Rustic Oak Burger Bar", "Main Street Smokehouse", "Liberty Diner", "Grill & Tap"],
        "categories": ["Restaurants", "American (Traditional)", "Burgers", "Barbeque", "Pubs"],
        "price": "2",
    },
    {
        "names": ["Sakura Japanese Bistro", "Tokyo Sushi & Ramen", "Zen Garden Sushi", "Izakaya Katsu"],
        "categories": ["Restaurants", "Japanese", "Sushi Bars", "Asian Fusion"],
        "price": "3",
    },
    {
        "names": ["Café de la Rue", "Artisan Roast & Bakery", "Morning Glory Espresso", "The Daily Grind"],
        "categories": ["Food", "Coffee & Tea", "Cafes", "Bakeries", "Breakfast & Brunch"],
        "price": "1",
    },
    {
        "names": ["Mumbai Masala Kitchen", "Taj Mahal Indian Bistro", "Curry Leaf", "Spice Route Express"],
        "categories": ["Restaurants", "Indian", "Vegetarian", "Halal"],
        "price": "2",
    },
    {
        "names": ["The Velvet Cellar", "Bistro 1892", "Starlight Lounge & Supper Club", "Heritage Table"],
        "categories": ["Restaurants", "American (New)", "Fine Dining", "Wine Bars", "Cocktail Bars"],
        "price": "4",
    },
]

NON_RESTAURANT_BUSINESSES = [
    {"name": "Quick Fix Auto Repair", "categories": "Automotive, Auto Repair, Oil Change Stations"},
    {"name": "Downtown Dental Care", "categories": "Health & Medical, Dentists, Cosmetic Dentists"},
    {"name": "Sparkle Clean Laundromat", "categories": "Local Services, Dry Cleaning & Laundry"},
    {"name": "Metro Fitness Gym", "categories": "Active Life, Fitness & Instruction, Gyms"},
    {"name": "Pet Paradise Grooming", "categories": "Pets, Pet Groomers, Pet Services"},
]

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Casey", "Riley",
    "Avery", "Jamie", "Elena", "Marcus", "Priya", "Carlos", "Sophia", "Liam",
    "Noah", "Emma", "Olivia", "Ava", "Lucas", "Maya", "Leo", "Zoe", "David",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
]

REVIEW_TEMPLATES_HIGH = [
    "Absolutely fantastic experience! The {dish} was cooked to perfection and the ambiance was wonderful.",
    "Outstanding service and delicious food. One of the best places in town for {cuisine}.",
    "Incredible meal! Staff was attentive, friendly, and very welcoming. Will definitely be returning soon.",
    "Exceeded all expectations! Generous portions, fresh ingredients, and prompt service.",
    "A true gem in the city. Every course was beautifully presented and full of flavor.",
]

REVIEW_TEMPLATES_MID = [
    "Decent food and friendly staff. The {dish} was good, though service was slightly slow on a busy night.",
    "A solid choice for casual dining. Nothing mind-blowing, but consistently good and fair prices.",
    "Good overall experience. Nice atmosphere, but the {dish} could have used a bit more seasoning.",
]

REVIEW_TEMPLATES_LOW = [
    "Disappointed with our visit. The wait was over 45 minutes and the food arrived lukewarm.",
    "Unfortunately did not live up to the hype. The {dish} was underwhelming and overpriced.",
    "Service was lacking and the order was incorrect. Would probably not return.",
]

DISHES = [
    "wood-fired pizza", "truffle pasta", "signature burger", "spicy ramen",
    "tasting platter", "guacamole & tacos", "house salad", "grilled salmon",
    "ribeye steak", "butter chicken", "sushi combo", "artisanal pastry",
]


def generate_synthetic_dataset(
    output_dir: Path,
    num_restaurants: int = 50,
    num_other_businesses: int = 10,
    num_users: int = 80,
    reviews_per_restaurant: int = 6,
    seed: int = 42,
) -> dict:
    """
    Generate synthetic Yelp dataset files adhering to Yelp's schema format.
    All records contain 'is_synthetic': True and 'syn_' prefixed identifiers.
    """
    random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    business_file = output_dir / "business.json"
    user_file = output_dir / "user.json"
    review_file = output_dir / "review.json"

    logger.info(
        "Generating synthetic dataset in %s: %d restaurants, %d non-restaurants, %d users",
        output_dir, num_restaurants, num_other_businesses, num_users
    )

    # ── 1. Generate Restaurants ────────────────────────────────────────────────
    businesses = []
    b_idx = 1

    for i in range(num_restaurants):
        profile = CUISINE_PROFILES[i % len(CUISINE_PROFILES)]
        city_info = CITIES_DATA[i % len(CITIES_DATA)]
        base_name = random.choice(profile["names"])
        name = f"{base_name} #{b_idx}" if (i >= len(profile["names"])) else base_name

        # Scatter coordinates slightly around city center
        lat = round(city_info["lat"] + random.uniform(-0.06, 0.06), 6)
        lon = round(city_info["lon"] + random.uniform(-0.06, 0.06), 6)

        stars = round(random.choice([3.0, 3.5, 4.0, 4.0, 4.5, 4.5, 5.0]), 1)
        rev_count = random.randint(15, 350)
        categories_str = ", ".join(profile["categories"])

        biz = {
            "business_id": f"syn_b_{b_idx:04d}",
            "name": name,
            "address": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Chestnut', 'Market', 'Broad', 'Pine'])} St",
            "city": city_info["city"],
            "state": city_info["state"],
            "postal_code": city_info["postal_code"],
            "latitude": lat,
            "longitude": lon,
            "stars": stars,
            "review_count": rev_count,
            "is_open": 1 if random.random() > 0.1 else 0,
            "attributes": {
                "RestaurantsPriceRange2": profile["price"],
                "RestaurantsTakeOut": "True" if random.random() > 0.2 else "False",
                "OutdoorSeating": "True" if random.random() > 0.4 else "False",
                "GoodForKids": "True" if random.random() > 0.3 else "False",
                "WiFi": random.choice(["free", "no", "paid"]),
                "BusinessAcceptsCreditCards": "True",
            },
            "categories": categories_str,
            "hours": {
                "Monday": "11:0-22:0",
                "Tuesday": "11:0-22:0",
                "Wednesday": "11:0-22:0",
                "Thursday": "11:0-22:0",
                "Friday": "11:0-23:0",
                "Saturday": "10:0-23:0",
                "Sunday": "10:0-21:0",
            },
            "is_synthetic": True,
        }
        businesses.append(biz)
        b_idx += 1

    # ── 2. Generate Non-Restaurant Businesses (for cleaner filter testing) ───────
    for i in range(num_other_businesses):
        non_rest = random.choice(NON_RESTAURANT_BUSINESSES)
        city_info = random.choice(CITIES_DATA)
        biz = {
            "business_id": f"syn_b_non_{i+1:03d}",
            "name": f"{non_rest['name']} - {city_info['city']}",
            "address": f"{random.randint(100, 5000)} Commercial Way",
            "city": city_info["city"],
            "state": city_info["state"],
            "postal_code": city_info["postal_code"],
            "latitude": round(city_info["lat"] + random.uniform(-0.05, 0.05), 6),
            "longitude": round(city_info["lon"] + random.uniform(-0.05, 0.05), 6),
            "stars": round(random.uniform(2.5, 4.8), 1),
            "review_count": random.randint(5, 80),
            "is_open": 1,
            "attributes": {"BusinessAcceptsCreditCards": "True"},
            "categories": non_rest["categories"],
            "hours": {"Monday": "9:0-17:0", "Tuesday": "9:0-17:0"},
            "is_synthetic": True,
        }
        businesses.append(biz)

    # Write business.json line-by-line
    with open(business_file, "w", encoding="utf-8") as f:
        for b in businesses:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    logger.info("Wrote %d businesses to %s", len(businesses), business_file)

    # ── 3. Generate Users ──────────────────────────────────────────────────────
    users = []
    for u_idx in range(1, num_users + 1):
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        start_year = random.randint(2015, 2023)
        user = {
            "user_id": f"syn_u_{u_idx:04d}",
            "name": f"{fname} {lname[0]}.",
            "review_count": random.randint(3, 120),
            "yelping_since": f"{start_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d} 12:00:00",
            "useful": random.randint(0, 150),
            "funny": random.randint(0, 60),
            "cool": random.randint(0, 90),
            "fans": random.randint(0, 15),
            "average_stars": round(random.uniform(2.8, 4.8), 2),
            "is_synthetic": True,
        }
        users.append(user)

    with open(user_file, "w", encoding="utf-8") as f:
        for u in users:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    logger.info("Wrote %d users to %s", len(users), user_file)

    # ── 4. Generate Reviews (referencing retained restaurants and users) ────────
    reviews = []
    r_idx = 1
    restaurant_biz_ids = [b["business_id"] for b in businesses if not b["business_id"].startswith("syn_b_non_")]
    user_ids = [u["user_id"] for u in users]

    base_date = datetime(2023, 1, 1, 12, 0, 0)

    for biz_id in restaurant_biz_ids:
        # Pick between 3 and reviews_per_restaurant * 2 reviews for this restaurant
        count = random.randint(max(2, reviews_per_restaurant - 2), reviews_per_restaurant + 4)
        reviewing_users = random.sample(user_ids, min(count, len(user_ids)))

        for uid in reviewing_users:
            star = random.choices([5.0, 4.0, 3.0, 2.0, 1.0], weights=[0.45, 0.30, 0.12, 0.08, 0.05])[0]
            dish = random.choice(DISHES)
            cuisine = "dining"

            if star >= 4.0:
                text = random.choice(REVIEW_TEMPLATES_HIGH).format(dish=dish, cuisine=cuisine)
            elif star == 3.0:
                text = random.choice(REVIEW_TEMPLATES_MID).format(dish=dish, cuisine=cuisine)
            else:
                text = random.choice(REVIEW_TEMPLATES_LOW).format(dish=dish, cuisine=cuisine)

            days_offset = random.randint(0, 700)
            rev_date = base_date + timedelta(days=days_offset, hours=random.randint(0, 12))

            rev = {
                "review_id": f"syn_r_{r_idx:05d}",
                "user_id": uid,
                "business_id": biz_id,
                "stars": star,
                "useful": random.randint(0, 12),
                "funny": random.randint(0, 5),
                "cool": random.randint(0, 8),
                "text": text,
                "date": rev_date.strftime("%Y-%m-%d %H:%M:%S"),
                "is_synthetic": True,
            }
            reviews.append(rev)
            r_idx += 1

    with open(review_file, "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info("Wrote %d reviews to %s", len(reviews), review_file)

    manifest = {
        "is_synthetic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_directory": str(output_dir.resolve()),
        "counts": {
            "restaurants": num_restaurants,
            "non_restaurants": num_other_businesses,
            "total_businesses": len(businesses),
            "users": len(users),
            "reviews": len(reviews),
        },
        "files": {
            "business": str(business_file.resolve()),
            "user": str(user_file.resolve()),
            "review": str(review_file.resolve()),
        },
    }

    manifest_file = output_dir / "sample_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Synthetic dataset creation complete. Manifest saved to %s", manifest_file)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Yelp dataset files for testing.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/sample_raw",
        help="Directory to save synthetic files (default: data/sample_raw)",
    )
    parser.add_argument(
        "--num-restaurants",
        type=int,
        default=50,
        help="Number of restaurant businesses to generate (default: 50)",
    )
    parser.add_argument(
        "--num-other-businesses",
        type=int,
        default=10,
        help="Number of non-restaurant businesses to generate for filter testing (default: 10)",
    )
    parser.add_argument(
        "--num-users",
        type=int,
        default=80,
        help="Number of users to generate (default: 80)",
    )
    parser.add_argument(
        "--reviews-per-restaurant",
        type=int,
        default=6,
        help="Average reviews per restaurant (default: 6)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible generation (default: 42)",
    )

    args = parser.parse_args()
    output_path = Path(args.output_dir)
    generate_synthetic_dataset(
        output_dir=output_path,
        num_restaurants=args.num_restaurants,
        num_other_businesses=args.num_other_businesses,
        num_users=args.num_users,
        reviews_per_restaurant=args.reviews_per_restaurant,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
