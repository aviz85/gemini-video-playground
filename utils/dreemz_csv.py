import pandas as pd
import streamlit as st
from .video_processor import process_video_upload
import io

def process_dreemz_csv(csv_file, group_id):
    """Process Dreemz CSV file and upload videos"""
    try:
        # Read CSV
        df = pd.read_csv(csv_file)
        
        # Process each row
        for _, row in df.iterrows():
            # Extract video URL and metadata
            video_url = row['mediaSharePath']
            metadata = {
                'title': row['title'],
                'relateId': row['relateId'] if pd.notna(row['relateId']) else None,
                'score': int(row['score']) if pd.notna(row['score']) else None
            }
            
            # Process video
            with st.status(f"Processing video: {row['title']}") as status:
                try:
                    # Download video from URL
                    import requests
                    response = requests.get(video_url, stream=True)
                    response.raise_for_status()
                    
                    # Create file-like object from response content
                    video_data = io.BytesIO(response.content)
                    
                    # Process the video
                    process_video_upload(
                        video_data=video_data,
                        source_url=video_url,
                        group_id=group_id,
                        mime_type='video/mp4',
                        metadata=metadata
                    )
                    
                    status.update(label=f"✅ Processed: {row['title']}", state="complete")
                except Exception as e:
                    status.update(label=f"❌ Failed: {row['title']} - {str(e)}", state="error")
                    continue
                
    except Exception as e:
        st.error(f"Failed to process CSV: {str(e)}")