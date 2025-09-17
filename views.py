# views.py
import requests
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_GET

# External API (replace with actual API)
ELECTRONICS_API = 'https://example.com/api/electronics'

# Static conversion rate
USD_TO_INR = 83.0

# Field renaming map
FIELD_RENAME_MAP = {
    'average_rating': 'avgRating',
    'rating_count': 'ratingCount',
    'release_date': 'releaseDate',
    'brand_name': 'brandName',
    'product_name': 'productName',
    'product_id': 'productId'
}

# Custom order for renamed fields
CUSTOM_FIELD_ORDER = [
    'avgRating', 'ratingCount', 'releaseDate', 'price', 'priceInINR',
    'brandName', 'category_name', 'processor', 'memory', 'description_text',
    'productName', 'productId'
]


@require_GET
def products(request):
    try:
        response = requests.get(ELECTRONICS_API)
        response.raise_for_status()
        raw_data = response.json()
    except Exception:
        return JsonResponse({'error': 'Failed to fetch product data'}, status=500)

    # Step 1: Filter out malformed data
    products = []
    for item in raw_data:
        try:
            required_keys = [
                'id', 'name', 'brand', 'category', 'description',
                'price', 'currency', 'processor', 'memory',
                'release_date', 'average_rating', 'rating_count'
            ]
            if not all(k in item for k in required_keys):
                continue

            product = {
                'product_id': item['id'],
                'product_name': item['name'],
                'brand_name': item['brand'],
                'category_name': item['category'],
                'description_text': item['description'],
                'price': item['price'],
                'currency': item['currency'],
                'processor': item['processor'],
                'memory': item['memory'],
                'release_date': item['release_date'],
                'average_rating': item['average_rating'],
                'rating_count': item['rating_count']
            }

            products.append(product)
        except Exception:
            continue

    # Step 2: Filtering
    min_rating = request.GET.get('min_rating')
    brand = request.GET.get('brand')
    category = request.GET.get('category')

    if min_rating:
        try:
            min_rating = float(min_rating)
            products = [p for p in products if p['average_rating'] is not None and float(p['average_rating']) >= min_rating]
        except ValueError:
            return JsonResponse({'error': 'Invalid min_rating value'}, status=400)

    if brand:
        products = [p for p in products if p['brand_name'].lower() == brand.lower()]

    if category:
        products = [p for p in products if p['category_name'].lower() == category.lower()]

    # Step 3: Sorting
    sort_by = request.GET.get('sort_by')
    sort_order = request.GET.get('sort_order', 'asc')

    valid_sort_fields = ['price', 'release_date', 'rating_count']
    if sort_by and sort_by in valid_sort_fields:
        reverse = (sort_order == 'desc')
        try:
            products.sort(key=lambda x: x.get(sort_by) or 0, reverse=reverse)
        except Exception:
            return JsonResponse({'error': 'Sorting error occurred'}, status=500)
    elif sort_by:
        return JsonResponse({'error': f'Invalid sort_by field. Allowed: {valid_sort_fields}'}, status=400)

    # Step 4: Transformations
    rename_fields = request.GET.get('rename_fields') == 'true'
    format_date = request.GET.get('format_date') == 'true'
    field_order = request.GET.get('field_order', '')  # alpha, reverse, custom

    transformed_products = []

    for p in products:
        transformed = {}

        for key, value in p.items():
            final_key = FIELD_RENAME_MAP.get(key, key) if rename_fields else key

            # Format date
            if format_date and key == 'release_date' and value:
                try:
                    date_obj = datetime.strptime(value, '%Y-%m-%d')
                    value = date_obj.strftime('%B %d, %Y')
                except ValueError:
                    pass

            transformed[final_key] = value

        # Add computed field
        if p['currency'] == 'USD' and p['price'] is not None:
            price_in_inr = round(float(p['price']) * USD_TO_INR, 2)
            transformed['priceInINR' if rename_fields else 'price_in_inr'] = price_in_inr

        transformed_products.append(transformed)

    # Step 5: Top N
    top_n = request.GET.get('top_n')
    top_by = request.GET.get('top_by')

    if top_n and top_by:
        try:
            top_n = int(top_n)
            valid_top_fields = ['price', 'average_rating', 'rating_count']
            top_field_key = FIELD_RENAME_MAP.get(top_by, top_by) if rename_fields else top_by

            if top_by not in valid_top_fields:
                return JsonResponse({'error': f'Invalid top_by field. Choose from {valid_top_fields}'}, status=400)

            transformed_products.sort(key=lambda x: x.get(top_field_key) or 0, reverse=True)
            transformed_products = transformed_products[:top_n]

        except ValueError:
            return JsonResponse({'error': 'Invalid top_n value. Must be an integer.'}, status=400)

    # Step 6: Field ordering
    if field_order == 'alpha':
        for i, p in enumerate(transformed_products):
            transformed_products[i] = dict(sorted(p.items(), key=lambda x: x[0]))

    elif field_order == 'reverse':
        for i, p in enumerate(transformed_products):
            transformed_products[i] = dict(sorted(p.items(), key=lambda x: x[0], reverse=True))

    elif field_order == 'custom' and rename_fields:
        for i, p in enumerate(transformed_products):
            ordered = {}
            for field in CUSTOM_FIELD_ORDER:
                if field in p:
                    ordered[field] = p[field]
            for k in p:
                if k not in ordered:
                    ordered[k] = p[k]
            transformed_products[i] = ordered

    return JsonResponse(transformed_products, safe=False)
