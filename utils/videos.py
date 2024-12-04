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
import json
import pandas as pd

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

def add_video_group(name, description, is_red=False):
    """Add new video group"""
    supabase = init_supabase()
    return supabase.table("video_groups").insert({
        "name": name,
        "description": description,
        "is_red": is_red,
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

def add_video(gemini_file_id, group_id, metadata=None, thumbnail_path=None, source_url=None):
    """Add video to database"""
    supabase = init_supabase()
    
    # Get group info to check if it's red
    group = supabase.table("video_groups").select("*").eq("id", group_id).single().execute()
    is_red = group.data.get("is_red", False)
    
    return supabase.table("videos").insert({
        "gemini_file_id": gemini_file_id,
        "group_id": group_id,
        "thumbnail_path": thumbnail_path,
        "source_url": source_url,
        "metadata": metadata or {},  # Default empty JSON if None
        "created_by": st.session_state.user.id,
        "is_red": is_red  # Add is_red from group
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

def process_video_upload(video_data, source_url, group_id, mime_type=None, metadata=None):
    """Process video upload from either file or URL"""
    with st.status("Processing video...") as status:
        # Get group info
        supabase = init_supabase()
        group = supabase.table("video_groups").select("*").eq("id", group_id).single().execute()
        is_red = group.data.get("is_red", False)
        
        thumb_data = None
        if not is_red:
            # Generate thumbnail
            status.write("Generating thumbnail...")
            thumb_data = generate_thumbnail(video_data)
        
        # Upload to Gemini
        status.write("Uploading to Gemini...")
        mime_type = mime_type or getattr(video_data, 'type', 'video/mp4')
        gemini_file_id = upload_to_gemini(video_data, mime_type)
        
        if gemini_file_id:
            thumb_path = None
            if thumb_data:
                # Upload thumbnail
                status.write("Uploading thumbnail...")
                thumb_path = upload_thumbnail(gemini_file_id, thumb_data)
            
            # Add to database with metadata and is_red
            add_video(gemini_file_id, group_id, metadata, thumb_path, source_url)
            status.update(label="✅ Upload complete", state="complete")
        else:
            status.update(label="❌ Upload failed", state="error")

def manage_video_groups():
    """Video groups management UI"""
    require_auth()
    st.header("📁 Video Groups")
    
    # Add new group in collapsible section
    with st.expander("➕ Create New Group"):
        with st.form("add_group"):
            group_name = st.text_input("Group Name")
            description = st.text_area("Description")
            is_red = st.checkbox("Red List (No Thumbnails)", value=False)
            col1, col2 = st.columns([4,1])
            with col2:
                submitted = st.form_submit_button("Create", use_container_width=True)
            
            if submitted:
                if not group_name:
                    st.error("Group name is required")
                else:
                    add_video_group(group_name, description, is_red)
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "Upload Files", 
        "Add from URL", 
        "Import Dreemz CSV",
        "Add from CSV"
    ])

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
        
        # Add metadata input
        metadata_str = st.text_area(
            "Metadata (JSON)",
            placeholder='{"key": "value", "another_key": "another_value"}',
            help="Enter video metadata as JSON"
        )
        
        if uploaded_files:
            try:
                metadata = json.loads(metadata_str) if metadata_str else {}
            except json.JSONDecodeError:
                st.error("Invalid JSON format in metadata")
                return
                
            for video in uploaded_files:
                process_video_upload(video, None, group_id, metadata=metadata)

    # URL upload tab
    with tab2:
        with st.form("url_form"):
            url = st.text_input("Video URL", placeholder="https://example.com/video.mp4")
            metadata_str = st.text_area(
                "Metadata (JSON)",
                placeholder='{"key": "value", "another_key": "another_value"}',
                help="Enter video metadata as JSON"
            )
            submitted = st.form_submit_button("Add URL")
            
            if submitted and url:
                try:
                    metadata = json.loads(metadata_str) if metadata_str else {}
                except json.JSONDecodeError:
                    st.error("Invalid JSON format in metadata")
                    return
                    
                if is_valid_video_url(url):
                    video_data, mime_type = download_video_from_url(url)
                    if video_data:
                        process_video_upload(video_data, url, group_id, mime_type, metadata)
                else:
                    st.error("Invalid video URL")

    # Dreemz CSV import tab
    with tab3:
        st.markdown("""
        ### Dreemz CSV Format
        Your CSV should have these columns:
        - `mediaSharePath`: URL to the video file
        - `title`: Video title
        - `relateId`: Related ID
        - `score`: Score value
        """)
        
        csv_source = st.radio(
            "CSV Source",
            ["Upload File", "Paste Text"],
            key="dreemz_csv_source"
        )
        
        df = None
        if csv_source == "Upload File":
            uploaded_csv = st.file_uploader(
                "Upload Dreemz CSV File", 
                type=["csv"],
                key="dreemz_csv_upload"
            )
            if uploaded_csv:
                df = pd.read_csv(uploaded_csv)
        else:
            csv_text = st.text_area(
                "Paste CSV Content",
                height=200,
                help="Paste your CSV content here",
                key="dreemz_csv_text"
            )
            if csv_text:
                try:
                    df = pd.read_csv(BytesIO(csv_text.encode()), sep=',')
                except Exception as e:
                    st.error(f"Invalid CSV format: {str(e)}")
        
        if df is not None:
            total_rows = len(df)
            rows_per_page = 5
            total_pages = (total_rows + rows_per_page - 1) // rows_per_page  # Ceiling division

            if total_rows > 0:
                page = st.number_input(
                    f"Page (1-{total_pages})", 
                    min_value=1, 
                    max_value=total_pages, 
                    value=1,
                    key=f"{csv_source}_page"  # Unique key for each tab
                )
                
                start_idx = (page - 1) * rows_per_page
                end_idx = min(start_idx + rows_per_page, total_rows)
                
                st.dataframe(
                    df.iloc[start_idx:end_idx], 
                    use_container_width=True
                )
                
                st.caption(f"Showing rows {start_idx + 1}-{end_idx} of {total_rows}")
            
            if 'mediaSharePath' not in df.columns:
                st.error("CSV must contain 'mediaSharePath' column")
                return
            
            if st.button("Process Dreemz CSV"):
                for _, row in df.iterrows():
                    metadata = {
                        'title': row['title'],
                        'relateId': row['relateId'] if pd.notna(row['relateId']) else None,
                        'score': float(row['score']) if pd.notna(row['score']) and row['score'] != '' else None
                    }
                    
                    video_url = row['mediaSharePath']
                    if is_valid_video_url(video_url):
                        video_data, mime_type = download_video_from_url(video_url)
                        if video_data:
                            process_video_upload(
                                video_data=video_data,
                                source_url=video_url,
                                group_id=group_id,
                                mime_type=mime_type,
                                metadata=metadata
                            )
                    else:
                        st.error(f"Invalid video URL: {video_url}")

    # Generic CSV import tab
    with tab4:
        st.markdown("""
        ### CSV Format
        Your CSV should have these columns:
        - `video_url`: URL to the video file
        - `title` (optional): Video title
        - `metadata` (optional): Additional JSON metadata
        """)
        
        csv_source = st.radio(
            "CSV Source",
            ["Upload File", "Paste Text"],
            key="generic_csv_source"
        )
        
        df = None
        if csv_source == "Upload File":
            uploaded_csv = st.file_uploader(
                "Upload CSV File", 
                type=["csv"],
                key="generic_csv_upload"
            )
            if uploaded_csv:
                df = pd.read_csv(uploaded_csv)
        else:
            csv_text = st.text_area(
                "Paste CSV Content",
                height=200,
                help="Paste your CSV content here",
                key="generic_csv_text"
            )
            if csv_text:
                try:
                    df = pd.read_csv(BytesIO(csv_text.encode()), sep=',')
                except Exception as e:
                    st.error(f"Invalid CSV format: {str(e)}")
        
        if df is not None:
            total_rows = len(df)
            rows_per_page = 5
            total_pages = (total_rows + rows_per_page - 1) // rows_per_page  # Ceiling division

            if total_rows > 0:
                page = st.number_input(
                    f"Page (1-{total_pages})", 
                    min_value=1, 
                    max_value=total_pages, 
                    value=1,
                    key=f"{csv_source}_page"  # Unique key for each tab
                )
                
                start_idx = (page - 1) * rows_per_page
                end_idx = min(start_idx + rows_per_page, total_rows)
                
                st.dataframe(
                    df.iloc[start_idx:end_idx], 
                    use_container_width=True
                )
                
                st.caption(f"Showing rows {start_idx + 1}-{end_idx} of {total_rows}")
            
            if 'video_url' not in df.columns:
                st.error("CSV must contain 'video_url' column")
                return
            
            if st.button("Process CSV"):
                for _, row in df.iterrows():
                    metadata = {}
                    if 'title' in df.columns:
                        metadata['title'] = row['title']
                    
                    # Parse additional metadata if exists
                    if 'metadata' in df.columns and pd.notna(row['metadata']):
                        try:
                            additional_metadata = json.loads(row['metadata'])
                            metadata.update(additional_metadata)
                        except json.JSONDecodeError:
                            st.warning(f"Invalid JSON metadata for URL: {row['video_url']}")
                    
                    # Download and process video
                    if is_valid_video_url(row['video_url']):
                        video_data, mime_type = download_video_from_url(row['video_url'])
                        if video_data:
                            process_video_upload(
                                video_data=video_data,
                                source_url=row['video_url'],
                                group_id=group_id,
                                mime_type=mime_type,
                                metadata=metadata
                            )
                    else:
                        st.error(f"Invalid video URL: {row['video_url']}")

def process_csv_uploads(df, group_id):
    """Process multiple video uploads with a single progress bar"""
    total_files = len(df)
    
    with st.status(f"Processing {total_files} videos...") as status:
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        for index, row in df.iterrows():
            current = index + 1
            progress_text.write(f"Processing video {current}/{total_files}")
            progress_bar.progress(current/total_files)
            
            try:
                # Extract video URL and metadata based on CSV type
                video_url = row.get('mediaSharePath') or row.get('video_url')
                if not is_valid_video_url(video_url):
                    st.error(f"Invalid video URL: {video_url}")
                    continue
                
                # Download video
                status.write(f"⬇️ Downloading video {current}/{total_files}")
                video_data, mime_type = download_video_from_url(video_url)
                if not video_data:
                    continue
                
                # Generate thumbnail
                status.write(f"🖼️ Generating thumbnail {current}/{total_files}")
                thumb_data = generate_thumbnail(video_data)
                
                # Upload to Gemini
                status.write(f"📤 Uploading to Gemini {current}/{total_files}")
                gemini_file_id = upload_to_gemini(video_data, mime_type)
                
                if gemini_file_id and thumb_data:
                    # Upload thumbnail
                    status.write(f"🖼️ Uploading thumbnail {current}/{total_files}")
                    thumb_path = upload_thumbnail(gemini_file_id, thumb_data)
                    
                    # Add to database
                    metadata = create_metadata_from_row(row)
                    add_video(gemini_file_id, group_id, metadata, thumb_path, video_url)
                    
            except Exception as e:
                st.error(f"Failed to process video {current}: {str(e)}")
                continue
        
        if index == total_files - 1:
            status.update(label=f"✅ Processed {total_files} videos", state="complete")
        else:
            status.update(label=f"⚠️ Completed with some errors", state="error")

def create_metadata_from_row(row):
    """Create metadata dict from CSV row"""
    if 'mediaSharePath' in row:  # Dreemz CSV
        return {
            'title': row['title'],
            'relateId': row['relateId'] if pd.notna(row['relateId']) else None,
            'score': float(row['score']) if pd.notna(row['score']) and row['score'] != '' else None
        }
    else:  # Generic CSV
        metadata = {}
        if 'title' in row:
            metadata['title'] = row['title']
        if 'metadata' in row and pd.notna(row['metadata']):
            try:
                additional_metadata = json.loads(row['metadata'])
                metadata.update(additional_metadata)
            except json.JSONDecodeError:
                st.warning(f"Invalid JSON metadata for URL: {row['video_url']}")
        return metadata

def add_analysis_task(batch_id, video_id, prompt_id):
    """Add analysis task"""
    supabase = init_supabase()
    
    # Get video info to check if it's red
    video = supabase.table("videos").select("is_red").eq("id", video_id).single().execute()
    is_red = video.data.get("is_red", False)
    
    return supabase.table("analysis_tasks").insert({
        "batch_id": batch_id,
        "video_id": video_id,
        "prompt_id": prompt_id,
        "status": "pending",
        "is_red": is_red  # Add is_red from video
    }).execute()