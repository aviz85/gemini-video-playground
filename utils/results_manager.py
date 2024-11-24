import streamlit as st
import json
from utils.supabase_client import init_supabase, require_auth
import re
from typing import Dict, Any

def clean_json_string(raw_json: str) -> str:
    """Clean JSON string from Gemini output"""
    # Extract JSON content between triple backticks
    json_match = re.search(r'```json\n(.*?)\n```', raw_json, re.DOTALL)
    if json_match:
        return json_match.group(1)
    return raw_json

def parse_analysis_result(result: Dict[str, Any]) -> Dict:
    """Parse and beautify analysis result"""
    if not result or 'analysis' not in result:
        return {}
        
    try:
        clean_json = clean_json_string(result['analysis'])
        parsed = json.loads(clean_json)
        
        # Find all numeric values in the parsed result that end with level/rating
        score_components = []
        for key, value in parsed.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    if (k.lower().endswith(('level', 'rating', 'score')) and 
                        isinstance(v, (int, float))):
                        score_components.append(v)
        
        # Calculate overall score (0-1000)
        valid_scores = [s for s in score_components if s > 0]
        parsed['overall_score'] = round((sum(valid_scores) / len(valid_scores)) * 100) if valid_scores else 0
        
        return parsed
        
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse JSON: {str(e)}")
        return {'error': 'Invalid JSON format'}

def display_json_field(key: str, value: Any, level: int = 0):
    """Recursively display JSON fields with proper formatting"""
    indent = "  " * level
    
    if isinstance(value, dict):
        # Handle dictionary with level + description pattern
        if 'level' in value and 'description' in value:
            st.markdown(f"{indent}**{key}:** {value['level']} - {value['description']}")
            return
            
        # Handle boolean fields with checkmarks
        if any(k.startswith('is') for k in value.keys()):
            bool_fields = [f"{k}: {'✅' if v else '❌'}" for k, v in value.items() if k.startswith('is')]
            other_fields = {k: v for k, v in value.items() if not k.startswith('is') and k not in ['level', 'description']}
            
            if bool_fields:
                st.markdown(f"{indent}**{key}:** {', '.join(bool_fields)}")
            if other_fields:
                for k, v in other_fields.items():
                    display_json_field(k, v, level + 1)
            return
            
        # Handle version fields
        if 'version' in value:
            st.markdown(f"{indent}**{key}:** {value['version']}")
            return
            
        # Default dictionary handling
        st.markdown(f"{indent}**{key}:**")
        for k, v in value.items():
            if k not in ['level', 'description', 'version']:
                display_json_field(k, v, level + 1)
    else:
        if not key.lower().endswith(('level', 'version')):
            st.markdown(f"{indent}**{key}:** {value}")

def show_batch_results():
    """Show analysis results"""
    require_auth()
    st.header("📊 Analysis Results")

    # Get all batches for user
    supabase = init_supabase()
    batches = supabase.table("analysis_batches") \
        .select("*") \
        .eq("created_by", st.session_state.user.id) \
        .order("created_at", desc=True) \
        .execute()

    if not batches.data:
        st.info("No analysis batches found")
        return

    # Select batch
    batch_options = {
        f"Batch {b['id'][:8]} ({b['total_videos']} videos, {b['status']})": b['id'] 
        for b in batches.data
    }
    selected_batch = st.selectbox(
        "Select Batch", 
        options=list(batch_options.keys())
    )
    batch_id = batch_options[selected_batch]

    # Create tabs for stats and individual results
    tab1, tab2 = st.tabs(["📈 Batch Statistics", "🔍 Individual Results"])

    with tab1:
        show_batch_statistics(batch_id)

    with tab2:
        show_individual_results(batch_id)

def show_batch_statistics(batch_id):
    """Show statistics for selected batch"""
    supabase = init_supabase()
    
    # Get all tasks for batch
    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(*), prompts(*)") \
        .eq("batch_id", batch_id) \
        .execute()

    if not tasks.data:
        st.warning("No tasks found for this batch")
        return

    # Calculate statistics
    total_tasks = len(tasks.data)
    completed_tasks = sum(1 for t in tasks.data if t['status'] == 'completed')
    failed_tasks = sum(1 for t in tasks.data if t['status'] == 'failed')
    pending_tasks = sum(1 for t in tasks.data if t['status'] == 'pending')

    # Display statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tasks", total_tasks)
    with col2:
        st.metric("Completed", completed_tasks)
    with col3:
        st.metric("Failed", failed_tasks)
    with col4:
        st.metric("Pending", pending_tasks)

    # Show completion percentage
    if total_tasks > 0:
        progress = completed_tasks / total_tasks
        st.progress(progress)
        st.caption(f"{progress:.1%} Complete")

def show_individual_results(batch_id):
    # Initialize session state for JSON toggles if not exists
    if 'json_toggles' not in st.session_state:
        st.session_state.json_toggles = {}

    supabase = init_supabase()
    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(id, thumbnail_path, source_url, metadata)") \
        .eq("batch_id", batch_id) \
        .execute()

    if not tasks.data:
        st.warning("No tasks found for this batch")
        return

    # Filter options
    status_filter = st.multiselect(
        "Filter by Status",
        options=["completed", "failed", "pending"],
        default=["completed"]
    )

    filtered_tasks = [t for t in tasks.data if t['status'] in status_filter]

    for task in filtered_tasks:
        st.divider()
        
        # Get video details
        video = task['videos']
        title = video.get('metadata', {}).get('title', video['id'])
        
        # Create columns for thumbnail and details
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader(title)
            
            # Display video player if source_url exists, otherwise show thumbnail
            if video['source_url']:
                st.video(video['source_url'])
            elif video['thumbnail_path']:
                try:
                    thumbnail_url = supabase.storage.from_('videos').get_public_url(video['thumbnail_path'])
                    st.image(thumbnail_url, use_container_width=True)
                except Exception as e:
                    st.error(f"Failed to load thumbnail: {str(e)}")
            
            st.write("**Status:**", task['status'])
            if task['status'] == 'failed':
                st.error(f"Error: {task.get('error', 'Unknown error')}")

        with col2:
            if task['result']:
                try:
                    parsed_result = parse_analysis_result(task['result'])
                    
                    # Add toggle for raw JSON
                    toggle_key = f"json_toggle_{task['id']}"
                    if toggle_key not in st.session_state:
                        st.session_state[toggle_key] = False
                    
                    show_raw = st.toggle('Show Raw JSON', key=toggle_key)
                    
                    if show_raw:
                        # Get the raw analysis string and beautify it
                        raw_analysis = task['result']['analysis']
                        # Remove JSON code block markers if present
                        clean_raw = clean_json_string(raw_analysis)
                        try:
                            # Parse and re-stringify with indentation
                            parsed_raw = json.loads(clean_raw)
                            beautified_raw = json.dumps(parsed_raw, indent=2)
                            st.code(beautified_raw, language='json')
                        except json.JSONDecodeError:
                            # If parsing fails, show original raw text
                            st.code(raw_analysis)
                    
                    # Find metrics to display
                    metrics_to_show = []
                    
                    # Always show overall score first
                    metrics_to_show.append(("Overall Score", parsed_result.get('overall_score', 'N/A')))
                    
                    # Find other metrics by looking for rating/level fields
                    for key, value in parsed_result.items():
                        if isinstance(value, dict):
                            for k, v in value.items():
                                if k.lower() in ('rating', 'level', 'score'):
                                    # Convert key from camelCase to Title Case
                                    display_name = ''.join(' ' + c if c.isupper() else c for c in key).title()
                                    metrics_to_show.append((display_name, v))
                    
                    # Display metrics in columns
                    num_metrics = len(metrics_to_show)
                    metrics = st.columns(num_metrics)
                    
                    for i, (name, value) in enumerate(metrics_to_show):
                        with metrics[i]:
                            st.metric(name, value, delta=None)
                    # Generic display of all fields
                    st.markdown("### Analysis Details")
                    excluded_fields = {'overall_score', 'videoQuality', 'audioQuality', 
                                     'authenticity', 'motivation'}  # Fields already shown in metrics
                    
                    for key, value in parsed_result.items():
                        if key not in excluded_fields:
                            display_json_field(key, value)
                            
                except Exception as e:
                    st.error(f"Failed to parse result: {str(e)}")
                    st.code(str(task['result']))