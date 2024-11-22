import itertools
from http.client import HTTPException
from typing import Any, Optional, List, Dict
from collections import defaultdict

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
from diskcache import Cache
from pydantic import BaseModel

# Initialize cache and page config
cache = Cache("cache_dir")
st.set_page_config(page_title="1mg Report Exporter", layout="wide")


class ReportEntry(BaseModel):
    user_id: str
    patient_id: str
    booking_id: str
    order_group_id: str
    source: str
    standard_lab_parameter_id: str
    standard_lab_parameter_name: str
    value: str
    unit: str
    low_value: str
    high_value: str
    page_number: Any
    line_number: Any
    validated: Any
    created_at: str
    report_parameter_id: str
    report_parameter_name: str
    report_package_name: str
    inference: Optional[str]
    reference_range: Optional[str]
    display_text: Optional[str]
    observation: str
    category: str


class Report(BaseModel):
    entries: list[ReportEntry]


@cache.memoize()
def get_report(report_id: str, cookie: str, member_id: str):
    response = requests.get(
        url=f"https://www.1mg.com/pwa-api/api/v5/user/health-record/diagnostics/{report_id}/{member_id}",
        headers={"cookie": cookie},
    )
    if not response.ok:
        raise HTTPException(
            f"failed to retrieve report {report_id}. status code {response.status_code}, content {response.text}"
        )
    return response.json()


def clean_unit_string(unit: str) -> str:
    return unit.replace("Â", "")

def parse_json_report(report_contents: dict) -> Report:
    parameters = report_contents.get("data", {}).get("widgets", [])[1].get('data', {}).get('parameters', [])
    report_values: list[dict] = list(
        itertools.chain(*[p.get("values", {}) for p in parameters])
    )
    # Clean unit strings
    for value in report_values:
        if "unit" in value:
            value["unit"] = clean_unit_string(value["unit"])
    return Report(entries=report_values)


def build_biomarker_db(
    report_ids: list[str], cookie: str, member_id: str
) -> list[ReportEntry]:
    reports: list[Report] = [
        parse_json_report(
            get_report(
                report_id=report_id,
                cookie=cookie,
                member_id=member_id,
            )
        )
        for report_id in report_ids
    ]
    report_entries: list[ReportEntry] = list(
        itertools.chain(*[r.entries for r in reports])
    )
    return report_entries


def main():
    st.title("1mg Report Exporter")
    
    st.markdown("""
    ### Instructions:
    1. Change the user agent to iOS/Chrome using a user agent switcher
    2. Retrieve cookie from any authenticated 1mg request
    3. Get the member ID from the /health-record page
    4. Get report IDs from /health-record/<member-id> page
    """)

    cookie = st.text_input("Cookie from authenticated 1mg request", type="password")
    member_id = st.text_input("Member ID")
    report_ids = st.text_area(
        "Enter Report IDs (one per line)",
        height=200,
        help="Each line should contain exactly one report ID",
        placeholder="Enter your report IDs here\nOne ID per line"
    )
    report_id_list = [rid.strip() for rid in report_ids.split('\n') if rid.strip()]

    if st.button("Export Reports", type="primary"):
        if not all([cookie, member_id]):
            st.error("Please provide both Cookie and Member ID")
            return
            
        if not report_id_list:
            st.error("Please provide at least one Report ID")
            return
        
        with st.spinner("Fetching and processing reports..."):
            biomarker_db: list[ReportEntry] = build_biomarker_db(
                report_id_list, cookie=cookie, member_id=member_id
            )
            df = pd.DataFrame.from_records([el.dict() for el in biomarker_db])
            
            st.dataframe(df)
            
            # Create visualization section
            st.subheader("Lab Parameters Analysis")

            def get_parameter_metadata(df: pd.DataFrame, param_name: str) -> Dict:
                param_data = df[df['standard_lab_parameter_name'] == param_name].copy()
                param_data['value'] = pd.to_numeric(param_data['value'], errors='coerce')
                
                metadata = {
                    'category': param_data['category'].iloc[0] if not param_data.empty else 'Unknown',
                    'unit': param_data['unit'].iloc[0] if not param_data.empty else '',
                    'latest_value': param_data.iloc[-1]['value'] if not param_data.empty else None,
                    'trend': None,
                    'is_numeric': not param_data['value'].isna().all(),
                    'measurements': len(param_data),
                    'reference_range': f"{param_data['low_value'].iloc[0]} - {param_data['high_value'].iloc[0]}" 
                        if not param_data.empty else 'N/A'
                }
                
                if metadata['is_numeric'] and len(param_data) > 1:
                    last_values = param_data['value'].tail(2).values
                    metadata['trend'] = 'increasing' if last_values[1] > last_values[0] else 'decreasing'
                
                return metadata

            def plot_parameter(df: pd.DataFrame, param_name: str) -> bool:
                param_data = df[df['standard_lab_parameter_name'] == param_name].copy()
                param_data['created_at'] = pd.to_datetime(param_data['created_at'])
                param_data['value'] = pd.to_numeric(param_data['value'], errors='coerce')
                
                if param_data['value'].isna().all():
                    return False
                
                # Create the plot
                fig = px.line(
                    param_data.sort_values('created_at'), 
                    x='created_at', 
                    y='value',
                    title=f'{param_name} ({param_data["unit"].iloc[0]})',
                    markers=True
                )
                
                # Add reference ranges
                if not param_data.empty:
                    low_val = pd.to_numeric(param_data['low_value'].iloc[0], errors='coerce')
                    high_val = pd.to_numeric(param_data['high_value'].iloc[0], errors='coerce')
                    
                    if pd.notna(low_val):
                        fig.add_hline(y=low_val, line_dash="dash", 
                                    annotation_text="Lower Limit", line_color="red")
                    if pd.notna(high_val):
                        fig.add_hline(y=high_val, line_dash="dash", 
                                    annotation_text="Upper Limit", line_color="red")
                
                fig.update_layout(
                    hovermode='x unified',
                    showlegend=False,
                    height=400
                )
                
                return fig

            # Organize parameters by category
            parameters_by_category = defaultdict(list)
            all_parameters = sorted(df['standard_lab_parameter_name'].unique())
            
            for param in all_parameters:
                metadata = get_parameter_metadata(df, param)
                if metadata['is_numeric']:
                    parameters_by_category[metadata['category']].append(
                        {'name': param, 'metadata': metadata}
                    )

            if not parameters_by_category:
                st.warning("No parameters with numeric values found to plot.")
                return

            # Search functionality
            search_term = st.text_input("🔍 Search parameters", "").lower()

            # Create tabs for categories
            tabs = st.tabs(list(parameters_by_category.keys()))
            
            for tab, (category, parameters) in zip(tabs, parameters_by_category.items()):
                with tab:
                    st.markdown(f"### {category}")
                    
                    # Filter parameters based on search
                    filtered_params = [
                        p for p in parameters 
                        if search_term in p['name'].lower()
                    ]
                    
                    if not filtered_params:
                        st.info("No matching parameters in this category.")
                        continue

                    # Create columns for parameters
                    cols = st.columns(2)
                    for idx, param in enumerate(filtered_params):
                        with cols[idx % 2]:
                            with st.expander(f"📊 {param['name']}", expanded=True):
                                # Show metadata
                                meta = param['metadata']
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric(
                                        "Latest Value", 
                                        f"{meta['latest_value']} {meta['unit']}", 
                                        delta="↑" if meta['trend'] == 'increasing' else "↓" 
                                        if meta['trend'] else None
                                    )
                                with col2:
                                    st.markdown(f"""
                                        **Reference Range:** {meta['reference_range']}  
                                        **Measurements:** {meta['measurements']}
                                    """)
                                
                                # Show plot
                                fig = plot_parameter(df, param['name'])
                                if fig:
                                    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
