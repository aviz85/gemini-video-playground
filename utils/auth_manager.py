import streamlit as st
from utils.supabase_client import init_supabase

def login_form():
    """Display login form"""
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            try:
                supabase = init_supabase()
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.authenticated = True
                st.session_state.user = response.user
                st.session_state.session = response.session
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {str(e)}")

def signup_form():
    """Display signup form"""
    with st.form("signup"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Sign Up")
        
        if submitted:
            if password != confirm_password:
                st.error("Passwords don't match")
                return
            try:
                supabase = init_supabase()
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                st.success("Signup successful! Please check your email to verify your account.")
            except Exception as e:
                st.error(f"Signup failed: {str(e)}")

def show_auth_page():
    """Display authentication page"""
    st.title("🎥 Gemini Video Analysis")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        login_form()
    with tab2:
        signup_form()