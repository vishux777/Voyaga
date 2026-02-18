import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voyaga.settings')
django.setup()

from apps.core.models import User
from apps.properties.models import Property


def seed():
    host, created = User.objects.get_or_create(
        email='host@voyaga.com',
        defaults={
            'username': 'superhost',
            'first_name': 'Alex',
            'last_name': 'Rivera',
            'role': 'host',
            'is_verified': True,
            'wallet_balance': 2500
        }
    )
    if created:
        host.set_password('host123')
        host.save()
        print("✓ Host user created")

    guest, created = User.objects.get_or_create(
        email='guest@voyaga.com',
        defaults={
            'username': 'traveler',
            'first_name': 'Jamie',
            'last_name': 'Chen',
            'role': 'guest',
            'is_verified': True,
            'wallet_balance': 1000
        }
    )
    if created:
        guest.set_password('guest123')
        guest.save()
        print("✓ Guest user created")

    properties = [
        {
            'title': 'Santorini Cliffside Villa',
            'city': 'Santorini', 'country': 'Greece',
            'address': 'Oia, Santorini 847 02',
            'property_type': 'villa', 'price_per_night': 420,
            'max_guests': 6, 'bedrooms': 3, 'bathrooms': 2,
            'amenities': ['wifi', 'pool', 'kitchen', 'ac', 'balcony'],
            'description': 'Perched on the volcanic cliffs of Oia, this stunning villa offers breathtaking views of the Aegean Sea. The whitewashed architecture, infinity pool, and sun-drenched terraces make this the ultimate Mediterranean escape.',
        },
        {
            'title': 'Manhattan Penthouse Loft',
            'city': 'New York', 'country': 'USA',
            'address': 'Tribeca, New York, NY 10013',
            'property_type': 'penthouse', 'price_per_night': 680,
            'max_guests': 4, 'bedrooms': 2, 'bathrooms': 2,
            'amenities': ['wifi', 'gym', 'parking', 'ac', 'tv', 'balcony'],
            'description': 'A sleek Tribeca penthouse with floor-to-ceiling windows offering panoramic Manhattan skyline views. Industrial-chic interiors, chef kitchen, and a private rooftop terrace.',
        },
        {
            'title': 'Ubud Jungle Retreat',
            'city': 'Ubud', 'country': 'Indonesia',
            'address': 'Jl. Raya Ubud, Bali 80571',
            'property_type': 'villa', 'price_per_night': 195,
            'max_guests': 4, 'bedrooms': 2, 'bathrooms': 2,
            'amenities': ['wifi', 'pool', 'kitchen', 'ac', 'balcony'],
            'description': 'Nestled in the lush rice terraces of Ubud, this traditional Balinese villa blends ancient culture with modern comfort. A private infinity pool overlooks the jungle canopy.',
        },
        {
            'title': 'Paris Haussman Apartment',
            'city': 'Paris', 'country': 'France',
            'address': 'Le Marais, Paris 75004',
            'property_type': 'apartment', 'price_per_night': 290,
            'max_guests': 3, 'bedrooms': 1, 'bathrooms': 1,
            'amenities': ['wifi', 'kitchen', 'heating', 'washer', 'tv'],
            'description': 'An elegant Haussman-era apartment in the heart of Le Marais. Original herringbone parquet floors, high ceilings, and a balcony with views of classic Parisian rooftops.',
        },
        {
            'title': 'Kyoto Machiya Townhouse',
            'city': 'Kyoto', 'country': 'Japan',
            'address': 'Gion District, Kyoto 605-0000',
            'property_type': 'house', 'price_per_night': 320,
            'max_guests': 5, 'bedrooms': 3, 'bathrooms': 2,
            'amenities': ['wifi', 'kitchen', 'heating', 'washer', 'tv'],
            'description': 'A beautifully restored 100-year-old Machiya wooden townhouse in Gion. Authentic Japanese interiors with tatami rooms, a zen garden, and a traditional soaking tub.',
        },
        {
            'title': 'Maldives Overwater Bungalow',
            'city': 'North Male Atoll', 'country': 'Maldives',
            'address': 'Velassaru Island, Maldives',
            'property_type': 'villa', 'price_per_night': 950,
            'max_guests': 2, 'bedrooms': 1, 'bathrooms': 1,
            'amenities': ['wifi', 'pool', 'ac', 'tv', 'balcony'],
            'description': 'Experience pure paradise in this overwater bungalow above a crystal-clear turquoise lagoon. Glass floor panels reveal vibrant marine life below.',
        },
        {
            'title': 'Copenhagen Design Studio',
            'city': 'Copenhagen', 'country': 'Denmark',
            'address': 'Norrebro, Copenhagen 2200',
            'property_type': 'studio', 'price_per_night': 130,
            'max_guests': 2, 'bedrooms': 1, 'bathrooms': 1,
            'amenities': ['wifi', 'kitchen', 'heating', 'washer', 'tv', 'balcony'],
            'description': 'A chic Scandinavian studio in the trendy Norrebro district. Minimalist Danish design with curated vintage pieces and cycling access to everything Copenhagen offers.',
        },
        {
            'title': 'Swiss Alpine Cabin',
            'city': 'Zermatt', 'country': 'Switzerland',
            'address': 'Zermatt 3920',
            'property_type': 'cabin', 'price_per_night': 380,
            'max_guests': 6, 'bedrooms': 3, 'bathrooms': 2,
            'amenities': ['wifi', 'kitchen', 'heating', 'tv', 'parking'],
            'description': 'A cozy timber chalet with the Matterhorn as your backdrop. Wood-burning fireplace, private hot tub on the snowy deck, and panoramic alpine views.',
        },
    ]

    count = 0
    for p in properties:
        if not Property.objects.filter(title=p['title']).exists():
            Property.objects.create(host=host, **p)
            count += 1

    print(f"✓ Created {count} properties")
    print("─────────────────────────────")
    print("  guest@voyaga.com  / guest123")
    print("  host@voyaga.com   / host123")
    print("  admin@voyaga.com  / admin123")
    print("─────────────────────────────")


seed()