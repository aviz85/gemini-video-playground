import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Now imports will work
from utils.prompt_manager import show_prompt_management
from utils.videos import manage_video_groups

import streamlit as st
import google.generativeai as genai
from supabase import create_client

# Initialize Supabase client
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# Page configuration
st.set_page_config(
    page_title="Gemini Video Analysis",
    page_icon="🎥",
    layout="wide"
)

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None

def verify_api_key():
    """Verify Gemini API key"""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        models = genai.list_models()
        st.session_state.available_models = [
            m.name for m in models 
            if "generateContent" in m.supported_generation_methods
        ]
        return True
    except Exception as e:
        st.error(f"❌ API key verification failed: {str(e)}")
        return False

def login_form():
    """Display login form"""
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            try:
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

def main():
    """Main application"""
    init_session_state()
    
    if not verify_api_key():
        st.stop()
    
    if not st.session_state.authenticated:
        show_auth_page()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Prompt Management", "Video Groups", "Create Batch", "View Results"]
    )
    
    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    
    # Page routing
    if page == "Prompt Management":
        show_prompt_management()
    elif page == "Video Groups":
        manage_video_groups()
    elif page == "Create Batch":
        create_batch()
    elif page == "View Results":
        view_results()

if __name__ == "__main__":
    main() 