import os
import time
from pathlib import Path
import streamlit as st
import google.generativeai as genai

def verify_api_key():
    """Verify that the API key is valid"""
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("❌ Missing GEMINI_API_KEY in Streamlit secrets")
        st.info("Please add your API key to .streamlit/secrets.toml")
        st.stop()
        
    try:
        # Configure and test the API key
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # List available models
        models = genai.list_models()
        
        # Get models that support content generation
        available_models = [
            m.name for m in models 
            if "generateContent" in m.supported_generation_methods
        ]
        
        if not available_models:
            st.error("❌ No models available")
            st.stop()
            
        # Store available models in session state
        st.session_state.available_models = available_models
        
        # Set default model if not already selected
        if 'selected_model' not in st.session_state:
            st.session_state.selected_model = "models/gemini-1.5-pro"
            
        return True
        
    except Exception as e:
        st.error(f"❌ API key verification failed: {str(e)}")
        st.info("""
        Please check:
        1. Your API key is valid
        2. You have enabled the Gemini API
        3. You have billing enabled (if required)
        4. You're not using a restricted IP
        """)
        st.stop()
        return False

# Verify API key before proceeding
verify_api_key()

def upload_video(video_file, mime_type="video/mp4"):
    """Upload video file to Gemini API"""
    # Save uploaded file temporarily
    temp_path = f"temp_{video_file.name}"
    with open(temp_path, "wb") as f:
        f.write(video_file.getvalue())
    
    try:
        file = genai.upload_file(temp_path, mime_type=mime_type)
        return file
    finally:
        # Clean up temp file
        os.remove(temp_path)

def wait_for_file_processing(file):
    """Wait for uploaded file to be processed"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    attempt = 0
    max_attempts = 60  # 5 minutes max (with 5s sleep)
    
    while attempt < max_attempts:
        status_text.text("Processing video...")
        progress_bar.progress(attempt / max_attempts)
        
        file = genai.get_file(file.name)
        if file.state.name == "ACTIVE":
            progress_bar.progress(1.0)
            status_text.text("Video ready!")
            return True
        elif file.state.name == "FAILED":
            status_text.text("❌ Video processing failed")
            raise Exception(f"Video processing failed: {file.error}")
            
        time.sleep(5)
        attempt += 1
    
    status_text.text("❌ Processing timeout")
    return False

def analyze_video(video_file, prompt):
    """Analyze video using Gemini model"""
    model = genai.GenerativeModel(
        model_name=st.session_state.selected_model,  # Use the selected model
        generation_config={
            "temperature": 0.4,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
    )
    
    with st.spinner("Analyzing video..."):
        response = model.generate_content([video_file, prompt])
        return response.text

def main():
    st.title("🎥 Gemini Video Analysis")
    st.write("Upload a video and ask Gemini to analyze it!")

    # Model selection
    if 'available_models' in st.session_state:
        st.session_state.selected_model = st.selectbox(
            "Select Gemini Model",
            st.session_state.available_models,
            index=st.session_state.available_models.index(st.session_state.selected_model),
            help="Choose which Gemini model to use for analysis"
        )

    # File uploader
    video_file = st.file_uploader(
        "Choose a video file", 
        type=["mp4", "mov", "avi"],
        help="Upload a video file (MP4, MOV, or AVI format)"
    )

    # Sample prompts
    sample_prompts = [
        "Describe what happens in this video",
        "What are the main actions and events?",
        "Analyze the mood and atmosphere",
        "List all objects and people visible",
        "Provide a detailed timeline of events"
    ]
    
    # Prompt input
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        prompt = st.text_area(
            "Enter your analysis prompt",
            help="Type your question or what you'd like to know about the video"
        )
    with col2:
        st.write("Sample prompts:")
        selected_prompt = st.selectbox(
            "Select a sample prompt",
            ["Custom"] + sample_prompts,
            label_visibility="collapsed"
        )
        if selected_prompt != "Custom":
            prompt = selected_prompt

    # Analysis button
    analyze_button = st.button(
        "Analyze Video", 
        disabled=not (video_file and prompt),
        type="primary"
    )

    if analyze_button:
        try:
            # Show video preview
            st.video(video_file)
            
            # Upload to Gemini
            with st.spinner("Uploading video..."):
                gemini_file = upload_video(video_file)
            
            # Wait for processing
            if wait_for_file_processing(gemini_file):
                # Get analysis
                analysis = analyze_video(gemini_file, prompt)
                
                # Display results
                st.markdown("### Analysis Results")
                st.write(analysis)
                
                # Cleanup
                gemini_file.delete()
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 