import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("STRIPE_SECRET_KEY")  # change this

# -----------------------------
# STRIPE CONFIG
# -----------------------------
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY")

# -----------------------------
# ALIEXPRESS CONFIG (WAITING FOR YOUR KEYS)
# -----------------------------
ALIEXPRESS_APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY")
ALIEXPRESS_APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET")

# Placeholder API URL (replace when approved)
ALIEXPRESS_API_URL = "https://api.aliexpress.com/products/search"


# -----------------------------
# FETCH PRODUCTS FROM ALIEXPRESS
# -----------------------------
def fetch_products_from_aliexpress(query="electronics", page=1, page_size=20):
    if not ALIEXPRESS_APP_KEY or not ALIEXPRESS_APP_SECRET:
        print("AliExpress API keys missing — using fallback products.")
        return fallback_products()

    try:
        params = {
            "app_key": ALIEXPRESS_APP_KEY,
            "sign": ALIEXPRESS_APP_SECRET,
            "keywords": query,
            "page": page,
            "page_size": page_size,
        }

        resp = requests.get(ALIEXPRESS_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        products = []

        # You will adjust this once you see the real AliExpress JSON structure
        for item in data.get("products", []):
            products.append({
                "id": item.get("product_id"),
                "name": item.get("title", "No title"),
                "price": float(item.get("sale_price", 0)),
                "shipping": float(item.get("shipping_cost", 5)),
                "image": item.get("image_url", "https://via.placeholder.com/300"),
                "description": item.get("description", "No description"),
                "category": item.get("category_name", "General"),
            })

        if not products:
            print("AliExpress returned no products — using fallback.")
            return fallback_products()

        print(f"Loaded {len(products)} products from AliExpress.")
        return products

    except Exception as e:
        print("AliExpress fetch failed:", e)
        return fallback_products()


# -----------------------------
# FALLBACK PRODUCTS (WORKS NOW)
# -----------------------------
def fallback_products():
    return [
        {
            "id": 1,
            "name": "Mini Gadget",
            "price": 9.99,
            "shipping": 3.99,
            "image": "https://via.placeholder.com/300",
            "description": "A tiny but powerful gadget.",
            "category": "Gadgets"
        },
        {
            "id": 2,
            "name": "Cool Accessory",
            "price": 14.99,
            "shipping": 4.99,
            "image": "https://via.placeholder.com/300",
            "description": "Makes your setup look cooler.",
            "category": "Accessories"
        },
        {
            "id": 3,
            "name": "Pro Tool",
            "price": 29.99,
            "shipping": 6.99,
            "image": "https://via.placeholder.com/300",
            "description": "For serious builders and tinkerers.",
            "category": "Tools"
        }
    ]


# -----------------------------
# LOAD PRODUCTS
# -----------------------------
products = fetch_products_from_aliexpress()


# -----------------------------
# CART HELPERS
# -----------------------------
def get_cart():
    return session.get("cart", [])


def save_cart(cart):
    session["cart"] = cart


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    category = request.args.get("category")
    if category:
        filtered = [p for p in products if p["category"] == category]
    else:
        filtered = products

    categories = sorted(set(p["category"] for p in products))

    return render_template("index.html",
                           products=filtered,
                           categories=categories,
                           selected_category=category)


@app.route("/product/<string:id>")
def product(id):
    item = next((p for p in products if str(p["id"]) == str(id)), None)
    if not item:
        return "Product not found", 404
    return render_template("product.html", **item)


@app.route("/add_to_cart/<string:id>")
def add_to_cart(id):
    item = next((p for p in products if str(p["id"]) == str(id)), None)
    if not item:
        return "Product not found", 404

    cart = get_cart()
    cart.append({
        "id": item["id"],
        "name": item["name"],
        "price": item["price"],
        "shipping": item["shipping"]
    })
    save_cart(cart)

    return redirect(url_for("cart"))


@app.route("/cart")
def cart():
    cart = get_cart()
    subtotal = sum(i["price"] for i in cart)
    shipping_total = sum(i["shipping"] for i in cart)
    total = subtotal + shipping_total

    return render_template("cart.html",
                           cart=cart,
                           subtotal=subtotal,
                           shipping_total=shipping_total,
                           total=total)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = get_cart()
    if not cart:
        return redirect(url_for("home"))

    subtotal = sum(i["price"] for i in cart)
    shipping_total = sum(i["shipping"] for i in cart)
    total = subtotal + shipping_total

    if request.method == "POST":
        email = request.form.get("email")

        line_items = []
        for item in cart:
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item["name"]},
                    "unit_amount": int(item["price"] * 100),
                },
                "quantity": 1,
            })

        if shipping_total > 0:
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Shipping"},
                    "unit_amount": int(shipping_total * 100),
                },
                "quantity": 1,
            })

        session_stripe = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=url_for("payment_success", _external=True),
            cancel_url=url_for("payment_cancel", _external=True),
            customer_email=email
        )

        save_cart([])

        return redirect(session_stripe.url, code=303)

    return render_template("checkout.html",
                           cart=cart,
                           subtotal=subtotal,
                           shipping_total=shipping_total,
                           total=total)


@app.route("/payment/success")
def payment_success():
    return render_template("payment_success.html")


@app.route("/payment/cancel")
def payment_cancel():
    return render_template("payment_cancel.html")


@app.route("/clear_cart")
def clear_cart():
    save_cart([])
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
