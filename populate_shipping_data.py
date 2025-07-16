# populate_shipping_data.py
import psycopg2
import uuid
import random
from datetime import datetime, timedelta

# Import DB_CONFIG from your config.py
from config import DB_CONFIG

# === Configuration ===
# Using the DB_CONFIG dictionary for connection parameters
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# === Sample Data ===
cities = [
    {"city": "Karachi", "state": "Sindh"},
    {"city": "Lahore", "state": "Punjab"},
    {"city": "Islamabad", "state": "Capital"},
    {"city": "Peshawar", "state": "KPK"},
    {"city": "Quetta", "state": "Balochistan"},
]

couriers = ["TCS", "Leopard", "M&P", "Pakistan Post"]
first_names = ["Ahmed", "Ayesha", "Ali", "Fatima", "Hassan", "Zara"]
last_names = ["Khan", "Malik", "Sheikh", "Raza", "Chaudhry", "Hussain"]

def generate_pii(address_type):
    name = random.choice(first_names)
    surname = random.choice(last_names)
    city = random.choice(cities)
    email = f"{name.lower()}.{surname.lower()}@mail.com"
    phone = f"+92{random.randint(3000000000, 3499999999)}"
    pii_id = str(uuid.uuid4())
    
    cur.execute("""
        INSERT INTO pii (id, "firstName", "lastName", "companyName", address1, address2,
                         city, country, state, "postalCode", email, phone, "addressType")
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pakistan', %s, %s, %s, %s, %s)
    """, (
        pii_id, name, surname, "PakLogistics", "Street 12", "Phase 4",
        city["city"], city["state"], "54000", email, phone, address_type
    ))
    return pii_id

def create_order(pii_id, index):
    order_id = str(uuid.uuid4())
    order_number = f"ORDPK-{index:04d}"
    tracking = f"TRACKPK-{index:05d}"
    courier = random.choice(couriers)

    cur.execute("""
        INSERT INTO "order" (id, "orderNumber", "createdAt", "shipToId", "trackingNumber", "shippingCourier")
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (order_id, order_number, datetime.now() - timedelta(days=index), pii_id, tracking, courier))
    return order_id, tracking

def create_shipment(order_id, from_id, to_id):
    shipment_id = str(uuid.uuid4())
    cost = round(random.uniform(200, 1500), 2)
    shipped = random.choice([True, False])
    cur.execute("""
        INSERT INTO shipment (id, "orderId", "shipFromId", "shipToId", cost, shipped)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (shipment_id, order_id, from_id, to_id, cost, shipped))
    return shipment_id

def create_package(shipment_id):
    package_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO package (id, weight, length, width, height, "shipmentId")
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        package_id,
        round(random.uniform(0.5, 10.0), 2),
        random.randint(10, 50),
        random.randint(10, 40),
        random.randint(5, 30),
        shipment_id
    ))
    return package_id

def create_tracking(package_id, tracking_number):
    tracking_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO "trackingInfo" (id, "trackingNumber", "packageReference", "packageId")
        VALUES (%s, %s, %s, %s)
    """, (tracking_id, tracking_number, f"REF-{random.randint(1000,9999)}", package_id))

# === Main Insertion Loop ===
try:
    print("📦 Inserting Pakistani shipping records...")
    for i in range(1, 201):  # Insert 200 records
        from_id = generate_pii("shipping")
        to_id = generate_pii("shipping")
        order_id, tracking_number = create_order(to_id, i)
        shipment_id = create_shipment(order_id, from_id, to_id)
        package_id = create_package(shipment_id)
        create_tracking(package_id, tracking_number)
    conn.commit()
    print("✅ Done! 200 Pakistani shipping records inserted.")
except Exception as e:
    conn.rollback()
    print("❌ Error during insertion:", e)
finally:
    cur.close()
    conn.close()