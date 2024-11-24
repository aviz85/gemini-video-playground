import streamlit as st
import json
from utils.supabase_client import init_supabase, require_auth
import re
from typing import Dict, Any
import pandas as pd

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
    if 'json_toggles' not in st.session_state:
        st.session_state.json_toggles = {}
    if 'table_settings' not in st.session_state:
        st.session_state.table_settings = {
            'sort_by': None,
            'sort_ascending': True,
            'filters': {},
            'visible_columns': ['title', 'status', 'overall_score']
        }

    supabase = init_supabase()
    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(id, thumbnail_path, source_url, metadata)") \
        .eq("batch_id", batch_id) \
        .execute()

    if not tasks.data:
        st.warning("No tasks found for this batch")
        return

    # Table controls tab
    tab1, tab2 = st.tabs(["🎥 Video View", "📊 Table View"])
    
    with tab1:
        # Original video view code
        status_filter = st.multiselect(
            "Filter by Status",
            options=["completed", "failed", "pending"],
            default=["completed"]
        )
        filtered_tasks = [t for t in tasks.data if t['status'] in status_filter]
        show_video_results(filtered_tasks)

    with tab2:
        # Table controls
        with st.expander("Table Controls", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("Sort")
                sort_by = st.selectbox(
                    "Sort by",
                    options=['title', 'status', 'overall_score', 'created_at'],
                    key='sort_by'
                )
                sort_order = st.radio(
                    "Order",
                    options=['Ascending', 'Descending'],
                    key='sort_order'
                )
            
            with col2:
                st.subheader("Filter")
                status_filter = st.multiselect(
                    "Status",
                    options=["completed", "failed", "pending"],
                    default=["completed"],
                    key='table_status_filter'
                )
                score_range = st.slider(
                    "Score Range",
                    min_value=0,
                    max_value=1000,
                    value=(0, 1000),
                    key='score_filter'
                )
            
            with col3:
                st.subheader("Columns")
                available_columns = [
                    'title', 'status', 'overall_score', 'created_at',
                    'completed_at', 'error'
                ]
                visible_columns = st.multiselect(
                    "Show Columns",
                    options=available_columns,
                    default=['title', 'status', 'overall_score'],
                    key='visible_columns'
                )

        # Process and display table data
        table_data = []
        for task in tasks.data:
            if task['status'] not in status_filter:
                continue
                
            row = {
                'title': task['videos'].get('metadata', {}).get('title', task['videos']['id']),
                'status': task['status'],
                'overall_score': parse_analysis_result(task.get('result', {})).get('overall_score', 0),
                'created_at': task['created_at'],
                'completed_at': task.get('completed_at'),
                'error': task.get('error')
            }
            
            if score_range[0] <= row['overall_score'] <= score_range[1]:
                table_data.append(row)

        # Sort data
        if sort_by:
            reverse = sort_order == 'Descending'
            table_data.sort(
                key=lambda x: (x[sort_by] is None, x[sort_by]), 
                reverse=reverse
            )

        # Display table
        if table_data:
            df = pd.DataFrame(table_data)
            st.dataframe(
                df[visible_columns],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No data matches the current filters")

def show_video_results(filtered_tasks):
    """Display results in video view format"""
    for task in filtered_tasks:
        st.divider()
        # Original video display code here