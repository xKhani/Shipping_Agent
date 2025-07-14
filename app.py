from flask import Flask, request, jsonify
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
    return jsonify({"status": "✅ Shipping Agent API is running."})

if __name__ == "__main__":
    # Enable hot reload + debug mode for development
    app.run(host="0.0.0.0", port=5000, debug=True)