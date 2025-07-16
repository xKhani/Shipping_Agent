import streamlit as st
import streamlit.components.v1 as components

st.title("🚀 IFrame Test")
components.html("""
<iframe src="http://localhost:8502" width="100%" height="600px" style="border:none;"></iframe>
""", height=600)
