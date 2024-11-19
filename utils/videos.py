import os
import time
import streamlit as st
import google.generativeai as genai
from utils.supabase_client import init_supabase, require_auth
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
import requests
from urllib.parse import urlparse

def upload_to_gemini(file_path, mime_type):
    """Upload file to Gemini API"""
    try:
        file = genai.upload_file(file_path, mime_type=mime_type)
        # Wait for file to be processed
        while True:
            status = genai.get_file(file.name)
            if status.state.name == "ACTIVE":
                break
            elif status.state.name == "FAILED":
                raise Exception(f"File processing failed: {status.error}")
            time.sleep(2)
        return file.name
    except Exception as e:
        st.error(f"Failed to upload to Gemini: {str(e)}")
        return None

def add_video_group(name, description):
    """Add new video group"""
    supabase = init_supabase()
    return supabase.table("video_groups").insert({
        "name": name,
        "description": description,
        "created_by": st.session_state.user.id
    }).execute()

def get_video_groups():
    """Get user's video groups"""
    supabase = init_supabase()
    return supabase.table("video_groups").select("*").eq(
        "created_by", st.session_state.user.id
    ).execute()

def generate_thumbnail(video_file):
    """Generate thumbnail from middle frame of video"""
    try:
        # Read video file into memory
        video_bytes = video_file.read()
        video_file.seek(0)  # Reset file pointer for later use
        
        # Save temporarily to disk since OpenCV can't read from memory
        temp_path = f"temp_{int(time.time())}.mp4"
        with open(temp_path, "wb") as f:
            f.write(video_bytes)
        
        try:
            # Open video
            cap = cv2.VideoCapture(temp_path)
            
            # Get total frames
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames == 0:
                raise Exception("Could not read video frames")
            
            # Set position to middle frame
            middle_frame = total_frames // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            
            # Read frame
            ret, frame = cap.read()
            cap.release()
            
            # Clean up temp file
            os.remove(temp_path)
            
            if not ret:
                return None
                
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Resize to thumbnail
            thumbnail = Image.fromarray(frame_rgb)
            thumbnail.thumbnail((320, 180))  # 16:9 ratio
            
            # Convert to bytes
            thumb_io = BytesIO()
            thumbnail.save(thumb_io, format='JPEG', quality=85)
            thumb_io.seek(0)
            
            return thumb_io
            
        except Exception as e:
            # Clean up temp file in case of error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
            
    except Exception as e:
        st.error(f"Failed to generate thumbnail: {str(e)}")
        return None

def upload_thumbnail(video_id, thumb_data):
    """Upload thumbnail to Supabase storage"""
    supabase = init_supabase()
    try:
        # Upload to videos/thumbnails/{video_id}.jpg
        path = f"videos/thumbnails/{video_id}.jpg"
        result = supabase.storage.from_("videos").upload(
            path,
            thumb_data.getvalue(),
            {
                "content-type": "image/jpeg",
                "x-upsert": "true"  # Override if exists
            }
        )
        return path
    except Exception as e:
        st.error(f"Failed to upload thumbnail: {str(e)}")
        return None

def add_video(gemini_file_id, group_id, thumbnail_path=None, source_url=None):
    """Add video to database"""
    supabase = init_supabase()
    return supabase.table("videos").insert({
        "gemini_file_id": gemini_file_id,
        "group_id": group_id,
        "thumbnail_path": thumbnail_path,
        "source_url": source_url,
        "created_by": st.session_state.user.id
    }).execute()

def get_group_videos(group_id):
    """Get videos in a group"""
    supabase = init_supabase()
    return supabase.table("videos").select("*").eq("group_id", group_id).execute()

def get_thumbnail_url(path):
    """Get public URL for thumbnail"""
    supabase = init_supabase()
    return supabase.storage.from_("videos").get_public_url(path)

def is_valid_video_url(url):
    """Validate video URL"""
    try:
        # Check if URL is valid
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return False
            
        # Check if URL points to a video file
        response = requests.head(url, allow_redirects=True)
        content_type = response.headers.get('content-type', '')
        return content_type.startswith('video/')
    except:
        return False

def download_video_from_url(url):
    """Download video from URL and return as bytes"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        return BytesIO(response.content), response.headers.get('content-type')
    except Exception as e:
        st.error(f"Failed to download video: {str(e)}")
        return None, None

def manage_video_groups():
    """Video groups management UI"""
    require_auth()
    st.header("📁 Video Groups")
    
    # Add new group in collapsible section
    with st.expander("➕ Create New Group"):
        with st.form("add_group"):
            group_name = st.text_input("Group Name")
            description = st.text_area("Description")
            col1, col2 = st.columns([4,1])
            with col2:
                submitted = st.form_submit_button("Create", use_container_width=True)
            
            if submitted:
                if not group_name:
                    st.error("Group name is required")
                else:
                    add_video_group(group_name, description)
                    st.success("Group created!")
                    time.sleep(0.5)
                    st.rerun()

    # Get all groups for selection
    groups = get_video_groups()
    if not groups.data:
        st.warning("Create a group first to upload videos")
        return

    # Upload section
    st.subheader("📤 Upload Videos")
    tab1, tab2 = st.tabs(["Upload Files", "Add from URL"])

    # Get group options
    group_options = {g["name"]: g["id"] for g in groups.data}
    selected_group = st.selectbox("Select Group", options=list(group_options.keys()))
    group_id = group_options[selected_group]

    # File upload tab
    with tab1:
        uploaded_files = st.file_uploader(
            "Upload Video Files", 
            type=["mp4", "mov", "avi"],
            accept_multiple_files=True,
            key="file_upload"
        )
        
        if uploaded_files:
            for video in uploaded_files:
                process_video_upload(video, None, group_id)

    # URL upload tab
    with tab2:
        with st.form("url_form"):
            url = st.text_input("Video URL", placeholder="https://example.com/video.mp4")
            submitted = st.form_submit_button("Add URL")
            
            if submitted and url:
                if is_valid_video_url(url):
                    video_data, mime_type = download_video_from_url(url)
                    if video_data:
                        process_video_upload(video_data, url, group_id, mime_type)
                else:
                    st.error("Invalid video URL")

def process_video_upload(video_data, source_url, group_id, mime_type=None):
    """Process video upload from either file or URL"""
    with st.status("Processing video...") as status:
        # Generate thumbnail
        status.write("Generating thumbnail...")
        thumb_data = generate_thumbnail(video_data)
        
        # Upload to Gemini
        status.write("Uploading to Gemini...")
        mime_type = mime_type or getattr(video_data, 'type', 'video/mp4')
        gemini_file_id = upload_to_gemini(video_data, mime_type)
        
        if gemini_file_id and thumb_data:
            # Upload thumbnail
            status.write("Uploading thumbnail...")
            thumb_path = upload_thumbnail(gemini_file_id, thumb_data)
            
            # Add to database
            add_video(gemini_file_id, group_id, thumb_path, source_url)
            status.update(label="✅ Upload complete", state="complete")
        else:
            status.update(label="❌ Upload failed", state="error")