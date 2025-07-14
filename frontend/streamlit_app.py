import streamlit as st
import requests
# import json # Not strictly needed if response is always plain string, but harmless

st.set_page_config(page_title="Shipping Analytics Agent", page_icon="📦")
st.title("📦 Shipping Analytics Agent")

st.markdown("Ask about your shipping data or general supply chain queries.")

# Initialize chat history if not already present
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"]) # Always display as markdown now

question = st.chat_input("Enter your question:")

if question:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": question})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(question)

    with st.spinner("Thinking..."):
        try:
            # Send the question to your Flask API
            response = requests.post(
                "http://localhost:5000/ask",
                json={"question": question.strip()}
            )

            if response.status_code == 200:
                api_response_data = response.json()
                agent_response_content = api_response_data.get("response") # This will now be a formatted string

                # Add agent response to chat history
                st.session_state.messages.append({"role": "assistant", "content": f"### 💬 Agent Response:\n{agent_response_content}"})
                with st.chat_message("assistant"):
                    st.markdown(f"### 💬 Agent Response:\n{agent_response_content}") # Display as markdown

            else:
                error_message = response.json().get('error', 'Unknown error')
                st.session_state.messages.append({"role": "assistant", "content": f"❌ Error: {response.status_code} - {error_message}"})
                with st.chat_message("assistant"):
                    st.error(f"❌ Error: {response.status_code} - {error_message}")
        except requests.exceptions.ConnectionError:
            st.session_state.messages.append({"role": "assistant", "content": "⚠️ Could not connect to the API. Make sure your Flask app is running at http://localhost:5000."})
            with st.chat_message("assistant"):
                st.error("⚠️ Could not connect to the API. Make sure your Flask app is running at http://localhost:5000.")
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ Request failed: {e}"})
            with st.chat_message("assistant"):
                st.error(f"⚠️ Request failed: {e}")

    st.rerun() # Use st.rerun() for newer Streamlit versions