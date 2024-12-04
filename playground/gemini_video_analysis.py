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
from utils.video_processor import process_video_upload
from utils.semantic_search import show_semantic_search, create_match_videos_function

# Page configuration
st.set_page_config(
    page_title="Gemini Video Analysis",
    page_icon="🎥",
    layout="wide"
)

def show_quick_analysis():
    """Simple single video analysis page"""
    st.header("Quick Video Analysis")
    
    # Video upload
    video = st.file_uploader("Upload video", type=["mp4", "mov", "avi"])
    
    # Analysis prompt
    prompt = st.text_area("Analysis prompt", 
                         "Analyze this video and provide detailed feedback in JSON format.")
    
    if video and prompt and st.button("Analyze"):
        # Create temporary group for the video
        supabase = init_supabase()
        temp_group = supabase.table("video_groups").insert({
            "name": "Quick Analysis",
            "created_by": st.session_state.user.id,
            "is_temporary": True
        }).execute()
        
        # Process video upload
        st.info("Uploading video...")
        process_video_upload(
            video, 
            source_url=None,
            group_id=temp_group.data[0]['id']
        )
        
        # Run analysis
        st.info("Running analysis...")
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Convert video to bytes and create blob
        video_bytes = video.getvalue()
        video_parts = [
            {
                "mime_type": video.type,
                "data": video_bytes
            }
        ]
        
        # Generate content with video parts
        response = model.generate_content([prompt, *video_parts])
        
        # Show raw results
        st.text_area("Analysis Results", response.text, height=400)
        st.success("✅ Analysis complete")

PAGES = {
    "Quick Analysis": show_quick_analysis,
    "Prompt Management": show_prompt_management,
    "Video Groups": manage_video_groups,
    "Create Batch": create_batch,
    "View Results": show_batch_results,
    "Semantic Search": show_semantic_search
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
    
    # Create match_videos function if not exists
    create_match_videos_function()
    
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