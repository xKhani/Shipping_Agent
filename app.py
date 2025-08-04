from flask import Flask, request, jsonify, render_template
from agent.shipping_agent import agent_response # This now uses SQLCoder & Mistral as needed
from flask_cors import CORS # Assuming you need CORS for your Streamlit frontend

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"error": "Missing question"}), 400

        # Call the smart agent that decides between SQL or LLM
        answer = agent_response(question)

        return jsonify({
            "question": question,
            "response": answer  # Preformatted readable text (not raw JSON)
        })

    except Exception as e:
        print(f"[❌ Error] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return render_template('dashboard.html')

@app.route("/dashboard")
def dashboard():
    return render_template('dashboard.html')

@app.route("/api/dashboard-data")
def dashboard_data():
    try:
        import psycopg2
        from config import DB_CONFIG
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        query = """
            SELECT
                o."createdAt"::date AS shipment_date,
                s.shipped,
                s.cost,
                o."shippingCourier",
                p.city AS destination_city,
                EXTRACT(DOW FROM o."createdAt") AS day_of_week,
                EXTRACT(HOUR FROM o."createdAt") AS hour_of_day,
                p.state AS destination_province
            FROM shipment s
            JOIN "order" o ON o.id = s."orderId"
            JOIN pii p ON p.id = s."shipToId"
            ORDER BY o."createdAt"
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        data = []
        for row in results:
            data.append({
                'shipment_date': row[0].isoformat(),
                'shipped': row[1],
                'cost': float(row[2]),
                'shippingCourier': row[3],
                'destination_city': row[4],
                'day_of_week': int(row[5]),
                'hour_of_day': int(row[6]),
                'destination_province': row[7]
            })
        
        cur.close()
        conn.close()
        
        return jsonify(data)
        
    except Exception as e:
        print(f"[❌ Dashboard Data Error] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Enable hot reload + debug mode for development
    app.run(host="0.0.0.0", port=5000, debug=True)