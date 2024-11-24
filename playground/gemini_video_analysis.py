import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import streamlit as st
import google.generativeai as genai

from utils.prompt_manager import show_prompt_management
from utils.videos import manage_video_groups
from utils.batch_manager import create_batch
from utils.auth_manager import show_auth_page
from utils.supabase_client import init_supabase
from utils.results_manager import show_batch_results

# Page configuration
st.set_page_config(
    page_title="Gemini Video Analysis",
    page_icon="🎥",
    layout="wide"
)

PAGES = {
    "Prompt Management": show_prompt_management,
    "Video Groups": manage_video_groups,
    "Create Batch": create_batch,
    "View Results": show_batch_results
}

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

def main():
    """Main application"""
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    if not verify_api_key():
        st.stop()
    
    if not st.session_state.authenticated:
        show_auth_page()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", list(PAGES.keys()))
    
    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    
    # Route to selected page
    PAGES[page]()

if __name__ == "__main__":
    main() 