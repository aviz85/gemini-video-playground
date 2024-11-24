import streamlit as st
from .videos import upload_to_gemini, generate_thumbnail, upload_thumbnail, add_video

def process_video_upload(video_data, source_url, group_id, mime_type=None, metadata=None):
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
            
            # Add to database with metadata
            add_video(gemini_file_id, group_id, metadata, thumb_path, source_url)
            status.update(label="✅ Upload complete", state="complete")
        else:
            status.update(label="❌ Upload failed", state="error")