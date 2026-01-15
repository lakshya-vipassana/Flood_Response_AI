# app.py
import os
from pathlib import Path
from datetime import datetime
import glob

import streamlit as st
# Must be the first Streamlit command
st.set_page_config(page_title="Flood AI + Chat", page_icon="🌊", layout="wide")

import pandas as pd
import geopandas as gpd
import pydeck as pdk
from shapely.geometry import shape
from shapely.ops import nearest_points
from dotenv import load_dotenv
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import rasterio
from rasterio.plot import reshape_as_image
import numpy as np
from folium.raster_layers import ImageOverlay
import matplotlib.pyplot as plt
from matplotlib import cm
import osmnx as ox

print(ox.__version__)

def add_shapefile_to_map(folium_map, shp_path, color='blue'):
    gdf = gpd.read_file(shp_path)
    folium.GeoJson(
        gdf,
        style_function=lambda x: {
            'color': color,
            'weight': 2,
            'fillOpacity': 0.1
        }
    ).add_to(folium_map)

def add_tiff_to_map(folium_map, tiff_path, opacity=1.0, max_size=1024):
    with rasterio.open(tiff_path) as src:
        bounds = src.bounds
        scale = max(src.height / max_size, src.width / max_size, 1)
        out_height = int(src.height / scale)
        out_width = int(src.width / scale)
        img = src.read(
            1,
            out_shape=(out_height, out_width)
        ).astype(np.float32)
        if src.nodata is not None:
            mask = img != src.nodata
        else:
            mask = np.ones_like(img, dtype=bool)

        valid = img[mask]
        img_min, img_max = np.nanmin(valid), np.nanmax(valid)
        if img_max - img_min == 0:
            norm = np.zeros_like(img, dtype=np.float32)
        else:
            norm = (img - img_min) / (img_max - img_min)
        norm = np.clip(norm, 0, 1)
        norm[~mask] = 0

        cmap = cm.get_cmap('Reds')
        img_rgba = (cmap(norm) * 255).astype(np.uint8)
        img_rgba[..., 3] = (img_rgba[..., 3] * opacity).astype(np.uint8)
        img_rgba[~mask] = [0, 0, 0, 0]

        # Override color for value == 2.33 to dark red
        dark_red = np.array([139, 0, 0, 255], dtype=np.uint8)
        special_mask = (img == 2.33) & mask
        img_rgba[special_mask] = dark_red

        bounds_latlon = [
            [bounds.bottom, bounds.left],
            [bounds.top, bounds.right]
        ]
        ImageOverlay(
            image=img_rgba,
            bounds=bounds_latlon,
            opacity=1.0,
            interactive=True,
            cross_origin=False
        ).add_to(folium_map)

# Hardcode the OpenAI API key placeholder
api_key = "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"

import openai
openai.api_key = api_key

# Hardcode the Mapbox API key placeholder
MAPBOX_API_KEY = "sk-proj-9Y59VxFGy8lqUd7H1U0tQ-oK6AxJHLrlnIe8V8bS4rGo28qhKlGUtb4c06O6w2wInFJH5AYXM_T3BlbkFJxly3uQdPYt6xKjjbMCWHHmHl2q722E0HDZbIL-xPSYM0MXDcaENsYbmO2y7qpdCBP7lP2TT-kAE"

# Debug: Print first few characters of API key (for verification)
st.sidebar.text(f"Using API Key (starts with): {api_key[:8]}...")

# ── Constants ────────────────────────────────────────────────
AGENTS = ["CommanderAgent", "LogisticsAgent", "SearchAgent", "RescueAgent", "CommsAgent"]

# ── Helper Functions ────────────────────────────────────────────
def get_severity_color(severity):
    """Return color code based on severity level"""
    colors = {
        'High': '#ff0000',     # Red
        'Moderate': '#ffa500', # Orange
        'Low': '#00ff00'       # Green
    }
    return colors.get(severity, '#808080')  # Default gray if severity not found

def get_evacuation_instructions(severity):
    """Get evacuation instructions based on severity level"""
    if severity == 'High':
        return "IMMEDIATE EVACUATION REQUIRED. Proceed to nearest shelter."
    elif severity == 'Moderate':
        return "Be prepared to evacuate. Monitor official communications."
    else:
        return "Stay alert and monitor updates."

def update_agent_status(agent, task, status="Active"):
    """Update agent's status and last task"""
    if 'agent_status' not in st.session_state:
        st.session_state.agent_status = {
            a:{'last_task':'Idle','status':'Ready'} for a in AGENTS
        }
    st.session_state.agent_status[agent] = {
        'last_task': task,
        'status': status
    }

def issue_public_alert(severity, location, details):
    """CommsAgent issues public alerts"""
    alert_types = {
        'High': "🚨 EMERGENCY ALERT",
        'Moderate': "⚠️ WARNING ALERT",
        'Low': "ℹ️ ADVISORY ALERT"
    }
    
    # Update CommsAgent status
    update_agent_status('CommsAgent', f"Issuing {severity} alert for {location}")
    
    return {
        'agent': 'CommsAgent',
        'type': 'alert',
        'msg': f"{alert_types.get(severity, '❗ ALERT')}\n"
               f"Location: {location}\n"
               f"Status: {severity} Risk\n"
               f"Details: {details}\n"
               f"Instructions: {get_evacuation_instructions(severity)}",
        'time': datetime.now().strftime("%H:%M:%S")
    }

def commander_execute_command(command, agents_data):
    """Commander agent executes high-level commands and coordinates other agents"""
    responses = []
    time_now = datetime.now().strftime("%H:%M:%S")
    
    try:
        # Get current situation data
        high_risk_zones = zones[zones['severity'] == 'High']
        
        # Commander's initial assessment with data
        situation_report = (
            f"SITUATION REPORT:\n"
            f"- High Risk Zones: {len(high_risk_zones)} "
            f"(Population at risk: {high_risk_zones['population'].sum():,})\n"
            f"Command: {command}"
        )
        
        update_agent_status('CommanderAgent', f"Issued command with data analysis: {command}")
        responses.append({
            'agent': 'CommanderAgent',
            'type': 'auto',
            'msg': situation_report,
            'time': time_now
        })

        prompt = f"""As a flood response commander, analyze the following situation and command:
        
        Situation:
        - High Risk Zones: {len(high_risk_zones)} (Population at risk: {high_risk_zones['population'].sum():,})
        
        Command: {command}
        
        Generate appropriate responses for each agent based on their role:
        - RescueAgent: Handles rescue operations and team deployment
        - SearchAgent: Manages search operations and area scanning
        - LogisticsAgent: Handles resource allocation and supply management
        - CommsAgent: Manages communications and public alerts
        
        Format the response as a JSON object with agent-specific responses."""
        
        # Get response from OpenAI
        ai_response = llm.invoke(prompt)
        
        # Process the response for each agent
        if "deploy" in command.lower():
            # Coordinate deployment
            update_agent_status('RescueAgent', "Deploying rescue teams")
            update_agent_status('LogisticsAgent', "Mobilizing emergency supplies")
            
            responses.extend([
                {
                    'agent': 'RescueAgent',
                    'type': 'auto',
                    'msg': "Deploying rescue teams as commanded. Teams are being mobilized to high-risk zones.",
                    'time': time_now
                },
                {
                    'agent': 'LogisticsAgent',
                    'type': 'auto',
                    'msg': "Mobilizing emergency supplies and transport. Coordinating with rescue teams for resource distribution.",
                    'time': time_now
                }
            ])
        elif "search" in command.lower():
            # Coordinate search operations
            update_agent_status('SearchAgent', "Conducting area search")
            update_agent_status('CommsAgent', "Broadcasting search details")
            
            responses.extend([
                {
                    'agent': 'SearchAgent',
                    'type': 'auto',
                    'msg': "Initiating search patterns in affected areas. Deploying drones for aerial reconnaissance.",
                    'time': time_now
                },
                {
                    'agent': 'CommsAgent',
                    'type': 'auto',
                    'msg': "Broadcasting search operation details to emergency channels. Coordinating with local authorities.",
                    'time': time_now
                }
            ])
        elif "resource" in command.lower():
            # Resource allocation
            update_agent_status('LogisticsAgent', "Allocating resources")
            
            responses.extend([
                {
                    'agent': 'LogisticsAgent',
                    'type': 'auto',
                    'msg': "Calculating resource requirements and distribution plan. Prioritizing medical supplies and emergency rations.",
                    'time': time_now
                }
            ])
        elif "alert" in command.lower():
            # Public alert handling
            update_agent_status('CommsAgent', "Preparing public alert")
            
            responses.extend([
                {
                    'agent': 'CommsAgent',
                    'type': 'auto',
                    'msg': "Preparing emergency broadcast channels. Coordinating evacuation routes and shelter information.",
                    'time': time_now
                }
            ])
            
    except Exception as e:
        error_msg = f"Error generating situation report: {str(e)}"
        responses.append({
            'agent': 'CommanderAgent',
            'type': 'error',
            'msg': error_msg,
            'time': time_now
        })
    
    return responses

# ── LangChain Agent Setup ─────────────────────────────────────
from langchain.agents import initialize_agent, Tool, AgentType
from langchain_openai import ChatOpenAI
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from agents.commander_agent import get_commander_tool
from agents.logistics_agent import get_logistics_tool
from agents.search_agent import get_search_tool
from agents.rescue_agent import get_rescue_tool
from agents.comms_agent import get_comms_tool

# ── Load Geo Data ─────────────────────────────────────────────
@st.cache_data
def load_zones():
    """Load flood zones as a GeoDataFrame."""
    return gpd.read_file(Path(__file__).parent / "data/dhamtari_zones.geojson").to_crs(epsg=4326)

zones = load_zones()

# Update population values for specific zones
pop_updates = {
    'Nagari': 13308,
    'Sihawa': 3359,
    'Magarlod': 121430,
    'Kurud': 11469,
    'Dhamtari': 799781,
}
for zone, pop in pop_updates.items():
    zones.loc[zones['name'].str.lower() == zone.lower(), 'population'] = pop

# Load shelters from CSV as a GeoDataFrame
@st.cache_data
def load_shelters():
    df = pd.read_csv("D:/flood data/csv_exports/shelters.csv")
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
    return gdf

shelters = load_shelters()

# Precompute nearest shelters for each zone (must be after data is loaded)
zone_to_nearest_shelters = {}
if not zones.empty and 'geometry' in zones.columns:
    for _, zone in zones.iterrows():
        if zone.geometry is None:
            continue  # Skip zones with no geometry
        shelters_with_distance = zones.copy()
        shelters_with_distance['distance'] = shelters_with_distance.geometry.distance(zone.geometry)
        nearest = shelters_with_distance.sort_values('distance')[['name', 'population', 'distance']].head(3)
        zone_to_nearest_shelters[zone['name'].strip().lower()] = nearest

# Initialize the agent with tools
tools = [
    get_commander_tool(),
    get_logistics_tool(),
    get_search_tool(),
    get_rescue_tool(),
    get_comms_tool()
]

# Initialize OpenAI LLM with GPT-4.1-nano with error handling
try:
    llm = ChatOpenAI(
        model="gpt-4.1-nano",
        temperature=0.5,  # Lower temperature for more focused responses
        openai_api_key=api_key,
        callback_manager=CallbackManager([StreamingStdOutCallbackHandler()])
    )
    
    # Test the API with a simple call
    test_response = llm.invoke("test")
    st.sidebar.success("✅ OpenAI API connected successfully")
    
except Exception as e:
    st.sidebar.error(f"❌ OpenAI API connection failed: {str(e)}")

# Define custom prompt template for better agent responses
from langchain.prompts import PromptTemplate
template = """Role: {current_role} in flood response system
Input: {input}
Available Tools: {tools}

Instructions:
1. If no tool needed: Provide direct, concise response
2. If using tool:
   Thought: [reasoning]
   Action: [tool_name]
   Action Input: [specific input]
   Observation: [result]
   Final Answer: [response]
3. If the user asks for a list of names or entities from a shapefile, always:
   a. Use ShapefileEntityNamesTool with the correct arguments to extract and return the actual list of names or entities.
   b. Never stop at just identifying the file/column—always return the actual data if possible.
4. When specifying an Action, always use the tool name exactly as listed in Available Tools, without parentheses. For example, use Action: ShapefileEntityNamesTool, not Action: ShapefileEntityNamesTool().
5. If the user asks about flood zones, always use ZoneDataTool to retrieve and return the relevant information from the flood zones table.
6. For all shelter-related queries, ONLY use the official CSV shelter data. Do NOT use ShapefileEntityNamesTool or ShapefileCountTool for shelter queries. Use ONLY ShelterDataTool or NearestSheltersTool for shelters. For evacuation or rescue in a specific area, do NOT use SearchTool. Always immediately use NearestSheltersTool and EvacuationPlanTool, even if you do not have affected population data. Assume the area is affected and proceed with evacuation planning.

Response:"""

prompt = PromptTemplate(
    input_variables=["current_role", "input", "tools"],
    template=template
)

# Add after the tools initialization but before agent initialization
def get_zone_data(query):
    """Get information about flood zones based on query"""
    try:
        filtered_zones = zones
        if 'high' in query.lower():
            filtered_zones = zones[zones['severity'] == 'High']
        elif 'moderate' in query.lower():
            filtered_zones = zones[zones['severity'] == 'Moderate']
        elif 'low' in query.lower():
            filtered_zones = zones[zones['severity'] == 'Low']
        
        return filtered_zones[['name', 'severity', 'population', 'water_level', 'evacuation_status']].to_string()
    except Exception as e:
        return f"Error accessing zone data: {str(e)}"

def get_shelter_data(query):
    """Get information about shelters based on query"""
    try:
        # Calculate current occupancy from session state
        shelter_assignments = st.session_state.get('shelter_assignments', {})
        shelter_data = zones.copy()
        # Add occupancy information
        shelter_data['current_occupancy'] = shelter_data['name'].apply(
            lambda x: sum(a['assigned_population'] for a in shelter_assignments.get(x, []))
        )
        shelter_data['available_capacity'] = shelter_data['population'] - shelter_data['current_occupancy']
        # Always return available shelters if available_capacity exists
        if 'available_capacity' in shelter_data.columns:
            shelter_data = shelter_data[shelter_data['available_capacity'] > 0]
        elif 'population' in shelter_data.columns:
            shelter_data = shelter_data[shelter_data['population'] > 0]
        return shelter_data[['name', 'population', 'current_occupancy', 'available_capacity']].to_string()
    except Exception as e:
        return f"Error accessing shelter data: {str(e)}"

# Helper to list files by extension in a directory (recursive)
def list_files_by_extension(directory, extension):
    files = glob.glob(f"{directory}/**/*{extension}", recursive=True)
    return [(os.path.relpath(f, start=directory), f) for f in files]

data_root = "D:/flood data"
shapefile_choices = list_files_by_extension(data_root, ".shp")
tiff_choices = list_files_by_extension(data_root, ".tif")
# Aggregate all shelter shapefiles into one GeoDataFrame
shelter_gdfs = []
for name, path in shapefile_choices:
    lower_name = name.lower()
    if 'location' in lower_name or 'landmark' in lower_name:
        continue  # Skip location and landmark shapefiles
    try:
        gdf = gpd.read_file(path)
        shelter_gdfs.append(gdf)
    except Exception:
        pass
if shelter_gdfs:
    all_shelters = gpd.GeoDataFrame(pd.concat(shelter_gdfs, ignore_index=True), crs=shelter_gdfs[0].crs)
else:
    all_shelters = gpd.GeoDataFrame()

# Remove old all_shelters aggregation from shapefiles and replace usages with shelters
# Update get_nearest_shelters to use shelters GeoDataFrame

def get_nearest_shelters(zone_name):
    """Return the three nearest shelters for a given zone name (case/whitespace-insensitive)."""
    import re
    try:
        if not zone_name:
            return "No zone name provided."
        # Clean up zone name: remove all whitespace, newlines, tabs, and quotes
        zone_name_clean = re.sub(r"[\s'\"\\]+", "", zone_name).lower()
        matched_zone = None
        # Try to match in zones data
        for zn in zones['name']:
            zn_clean = re.sub(r"[\s'\"\\]+", "", str(zn)).lower()
            if zn_clean == zone_name_clean:
                matched_zone = zn
                zone_geom = zones.loc[zones['name'] == matched_zone].geometry.values[0]
                break
        # If not found, use hardcoded landmarks
        if not matched_zone:
            landmarks = {
                'nagari': (20.3484, 81.9593),
                'sihawa': (20.3099964, 81.9159666),
                'magarlod': (20.748417, 81.8505),
                'kurud': (20.835528, 81.719472),
                'dhamtari': (20.715667, 81.55),
            }
            if zone_name_clean in landmarks:
                lat, lon = landmarks[zone_name_clean]
                from shapely.geometry import Point
                zone_geom = Point(lon, lat)
                matched_zone = zone_name_clean.title()
            else:
                available = ', '.join(list(zones['name'].unique()) + [k.title() for k in landmarks.keys()])
                return f"Zone or landmark '{zone_name}' not found. Available: {available}"
        if shelters.empty:
            return "No shelter data found."
        shelters_with_distance = shelters.copy()
        shelters_with_distance['distance'] = shelters_with_distance.geometry.distance(zone_geom)
        nearest = shelters_with_distance.sort_values('distance')[['name', 'amenity', 'addr_full', 'contact_ph', 'distance']].head(3)
        lines = []
        for _, row in nearest.iterrows():
            lines.append(f"- {row['name']} (Amenity: {row['amenity']}, Address: {row['addr_full']}, Contact: {row['contact_ph']}, Distance: {row['distance']:.1f}m)")
        return f"Nearest shelters for '{matched_zone}':\n" + '\n'.join(lines)
    except Exception as e:
        return f"Error finding nearest shelters: {str(e)}"

# Update create_evacuation_plan to use shelters

def create_evacuation_plan(query: str = ""):
    plan_summary = []
    shelter_assignments = {}
    # If capacity is missing, assume infinite capacity
    if not shelters.empty and 'capacity' in shelters.columns:
        shelter_remaining_capacity = shelters.set_index('name')['capacity'].to_dict()
    else:
        shelter_remaining_capacity = {name: float('inf') for name in shelters['name']} if not shelters.empty else {}
    # If a specific area is given, only process that area
    if query and query.strip():
        area_name = query.strip()
        # Try to match the area in zones
        import re
        area_name_clean = re.sub(r"[\s'\"\\]+", "", area_name).lower()
        matched_zone = None
        for zn in zones['name']:
            zn_clean = re.sub(r"[\s'\"\\]+", "", str(zn)).lower()
            if zn_clean == area_name_clean:
                matched_zone = zn
                zone_geom = zones.loc[zones['name'] == matched_zone].geometry.values[0]
                break
        if not matched_zone:
            return f"Area '{area_name}' not found in zones."
        needed_capacity = zones.loc[zones['name'] == matched_zone, 'population'].values[0] if 'population' in zones.columns else 0
        nearby_shelters = shelters.copy()
        nearby_shelters['distance'] = nearby_shelters.geometry.distance(zone_geom)
        nearby_shelters = nearby_shelters.sort_values('distance')
        assigned_shelters_for_zone = []
        for _, shelter in nearby_shelters.iterrows():
            if needed_capacity <= 0:
                break
            shelter_name = shelter['name']
            available_capacity = shelter_remaining_capacity.get(shelter_name, float('inf'))
            if available_capacity > 0:
                assign_pop = min(needed_capacity, available_capacity)
                assigned_shelters_for_zone.append({
                    'shelter_name': shelter_name,
                    'assigned_population': assign_pop,
                    'distance': shelter['distance']
                })
                needed_capacity -= assign_pop
                shelter_remaining_capacity[shelter_name] = available_capacity - assign_pop if available_capacity != float('inf') else float('inf')
                if shelter_name not in shelter_assignments:
                    shelter_assignments[shelter_name] = []
                shelter_assignments[shelter_name].append({
                    'zone_name': matched_zone,
                    'assigned_population': assign_pop
                })
        shelter_info = "\n".join([
            f"- To {s['shelter_name']}: Evacuate {s['assigned_population']} people ({s['distance']:.1f}m away)"
            for s in assigned_shelters_for_zone
        ])
        plan_summary.append(f"Plan for {matched_zone} (Population: {zones.loc[zones['name'] == matched_zone, 'population'].values[0] if 'population' in zones.columns else 'unknown'}):\n{shelter_info}")
        if needed_capacity > 0:
            plan_summary.append(f"WARNING: Could not find shelter for {needed_capacity} people from {matched_zone}.")
        st.session_state.shelter_assignments = shelter_assignments
        return "Evacuation Plan Created:\n" + "\n\n".join(plan_summary)
    # Default: all high-risk zones (legacy)
    high_risk_zones = zones[zones['severity'] == 'High'] if 'severity' in zones.columns else zones
    if high_risk_zones.empty:
        return "No high-risk zones identified. No evacuation plan needed at this time."
    for _, zone in high_risk_zones.iterrows():
        if zone.geometry is None:
            continue
        needed_capacity = zone['population'] if 'population' in zone else 0
        nearby_shelters = shelters.copy()
        nearby_shelters['distance'] = nearby_shelters.geometry.distance(zone.geometry.centroid)
        nearby_shelters = nearby_shelters.sort_values('distance')
        assigned_shelters_for_zone = []
        for _, shelter in nearby_shelters.iterrows():
            if needed_capacity <= 0:
                break
            shelter_name = shelter['name']
            available_capacity = shelter_remaining_capacity.get(shelter_name, float('inf'))
            if available_capacity > 0:
                assign_pop = min(needed_capacity, available_capacity)
                assigned_shelters_for_zone.append({
                    'shelter_name': shelter_name,
                    'assigned_population': assign_pop,
                    'distance': shelter['distance']
                })
                needed_capacity -= assign_pop
                shelter_remaining_capacity[shelter_name] = available_capacity - assign_pop if available_capacity != float('inf') else float('inf')
                if shelter_name not in shelter_assignments:
                    shelter_assignments[shelter_name] = []
                shelter_assignments[shelter_name].append({
                    'zone_name': zone['name'],
                    'assigned_population': assign_pop
                })
        shelter_info = "\n".join([
            f"- To {s['shelter_name']}: Evacuate {s['assigned_population']} people ({s['distance']:.1f}m away)"
            for s in assigned_shelters_for_zone
        ])
        plan_summary.append(f"Plan for {zone['name']} (Population: {zone['population'] if 'population' in zone else 'unknown'}):\n{shelter_info}")
        if needed_capacity > 0:
            plan_summary.append(f"WARNING: Could not find shelter for {needed_capacity} people from {zone['name']}.")
    st.session_state.shelter_assignments = shelter_assignments
    return "Evacuation Plan Created:\n" + "\n\n".join(plan_summary)

# Create data access tools
# --- Shapefile Count Tool ---
def get_shapefile_count(query=None):
    """
    Returns the number of features in a specified shapefile. Usage: provide the shapefile name (as listed in ShapefileInfoTool).
    """
    if not query:
        return "Please provide the shapefile name."
    query_clean = query.strip().lower().replace('.shp', '')
    for name, path in shapefile_choices:
        name_clean = name.lower().replace('.shp', '')
        if query_clean == name_clean:
            try:
                gdf = gpd.read_file(path)
                return f"Shapefile '{name}' contains {len(gdf)} features."
            except Exception as e:
                return f"Error reading shapefile '{name}': {e}"
    return f"Shapefile '{query}' not found. Use ShapefileInfoTool to see available names."

# --- Shapefile Entity Names Tool ---
def get_shapefile_entity_names(query=None):
    """
    Returns the list of entity names (or values from a specified column) in a given shapefile.
    Usage: input should be 'shapefile_name,column_name' (e.g., 'hospitals_dhamtari.shp,name')
    """
    if not query or ',' not in query:
        return "Please provide input as 'shapefile_name,column_name'."
    shapefile_name, column_name = [x.strip(' \'"\t\r\n') for x in query.split(',', 1)]
    shapefile_name_clean = shapefile_name.lower().replace('.shp', '')
    for name, path in shapefile_choices:
        name_clean = name.lower().replace('.shp', '')
        if shapefile_name_clean == name_clean:
            try:
                gdf = gpd.read_file(path)
                if column_name not in gdf.columns:
                    return f"Column '{column_name}' not found in '{name}'."
                values = gdf[column_name].dropna().unique()
                if len(values) == 0:
                    return f"No values found in column '{column_name}' of '{name}'."
                return f"Entities in '{name}' ({column_name}):\n" + '\n'.join(map(str, values))
            except Exception as e:
                return f"Error reading shapefile '{name}': {e}"
    return f"Shapefile '{shapefile_name}' not found. Use ShapefileInfoTool to see available names."

def get_osm_shelters(place="Dhamtari, India"):
    # Try both function names for compatibility
    try:
        gdf = ox.features_from_place(place, tags={'amenity': 'shelter'})
    except AttributeError:
        gdf = ox.geometries_from_place(place, tags={'amenity': 'shelter'})
    if gdf.empty:
        return "No OSM shelters found."
    return gdf[['name', 'geometry']].to_string()

data_tools = [
    Tool(
        name="ZoneDataTool",
        func=get_zone_data,
        description="Get information about flood zones. Use keywords 'high', 'moderate', 'low' to filter by severity."
    ),
    Tool(
        name="ShelterDataTool",
        func=get_shelter_data,
        description="Get information about evacuation shelters. Always returns available shelters if possible."
    ),
    Tool(
        name="NearestSheltersTool",
        func=get_nearest_shelters,
        description="Find the nearest shelters to a given zone name. Only uses the official CSV shelter data."
    ),
    Tool(
        name="EvacuationPlanTool",
        func=create_evacuation_plan,
        description="Creates a detailed evacuation plan for all high-risk zones by assigning their populations to the nearest available shelters. Uses only the CSV shelter data."
    ),
    Tool(
        name="ShapefileCountTool",
        func=get_shapefile_count,
        description="Returns the number of features in a specified shapefile. Input should be the shapefile name as listed in ShapefileInfoTool (e.g., 'hospitals_dhamtari.shp')."
    ),
    Tool(
        name="ShapefileEntityNamesTool",
        func=get_shapefile_entity_names,
        description="Returns the list of entity names (or values from a specified column) in a given shapefile. Input should be 'shapefile_name,column_name' (e.g., 'hospitals_dhamtari.shp,name')."
    )
]

# Update tools list to include data tools (without OSMShelterTool)
tools = [
    get_commander_tool(),
    get_logistics_tool(),
    get_search_tool(),
    get_rescue_tool(),
    get_comms_tool(),
] + data_tools

# Update agent initialization with new tools
agent = initialize_agent(
    tools,
    llm,
    AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={
        "prompt": prompt
    }
)

# ── Streamlit Config ─────────────────────────────────────────────
# Page config moved to top of file

# ── Streamlit Layout ──────────────────────────────────────────
st.title("SURAKSHA AGENT")

# ── Simulation & Map ──────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺️ Flood Zone Map")
    
    # Helper to list files by extension in a directory (recursive)
    def list_files_by_extension(directory, extension):
        files = glob.glob(f"{directory}/**/*{extension}", recursive=True)
        return [(os.path.relpath(f, start=directory), f) for f in files]
    
    data_root = "D:/flood data"
    shapefile_choices = list_files_by_extension(data_root, ".shp")
    tiff_choices = list_files_by_extension(data_root, ".tif")
    # Aggregate all shelter shapefiles into one GeoDataFrame
    shelter_gdfs = []
    for name, path in shapefile_choices:
        lower_name = name.lower()
        if 'location' in lower_name or 'landmark' in lower_name:
            continue  # Skip location and landmark shapefiles
        try:
            gdf = gpd.read_file(path)
            shelter_gdfs.append(gdf)
        except Exception:
            pass
    if shelter_gdfs:
        all_shelters = gpd.GeoDataFrame(pd.concat(shelter_gdfs, ignore_index=True), crs=shelter_gdfs[0].crs)
    else:
        all_shelters = gpd.GeoDataFrame()
    # Always center on Dhamtari
    center_lat = 20.71
    center_lon = 81.55
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)
    # Add marker for Dhamtari
    folium.Marker([center_lat, center_lon], popup="Dhamtari").add_to(m)
    # Add markers for other towns
    town_coords = {
        "Nagari": (20.3484, 81.9593),
        "Sihawa": (20.3099964, 81.9159666),
        "Magarlod": (20.748417, 81.8505),  # 20°44'54.3"N 81°51'01.8"E
        "Kurud": (20.835528, 81.719472),   # 20°50'07.9"N 81°43'10.1"E
        "Dhamtari": (20.715667, 81.55),    # 20°42'56.4"N 81°33'00.0"E
    }
    for town, (lat, lon) in town_coords.items():
        folium.Marker([lat, lon], popup=town).add_to(m)
    # Add all shapefile layers with popups/tooltips for attributes
    for name, path in shapefile_choices:
        try:
            gdf = gpd.read_file(path)
            if gdf.empty or len(gdf.columns) == 0:
                continue  # Silently skip shapefiles with no data or attributes
            # Exclude geometry column for popups/tooltips
            geom_col = gdf.geometry.name if hasattr(gdf, 'geometry') else 'geometry'
            attr_cols = [col for col in gdf.columns if col != geom_col]
            gj_kwargs = {"name": name}
            if attr_cols:
                gj_kwargs["tooltip"] = folium.GeoJsonTooltip(fields=attr_cols, aliases=attr_cols)
                gj_kwargs["popup"] = folium.GeoJsonPopup(fields=attr_cols)
            folium.GeoJson(gdf, **gj_kwargs).add_to(m)
        except Exception as e:
            st.warning(f"Could not add shapefile {name}: {e}")
    # Only add the TIFF layer with the exact name 'ALL FACTORS RE CLASSIFIED.tif' (case-insensitive)
    for name, path in tiff_choices:
        if name.strip().lower() == 'all factors re classified.tif':
            try:
                add_tiff_to_map(m, path, opacity=0.4)
            except Exception as e:
                st.warning(f"Could not add TIFF {name}: {e}")
    # Update map display to plot shelters as markers
    for _, row in shelters.iterrows():
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=f"{row['name']}<br>Amenity: {row['amenity']}<br>Address: {row['addr_full']}<br>Contact: {row['contact_ph']}",
            icon=folium.Icon(color='blue', icon='home')
        ).add_to(m)
    folium_static(m)

with col2:
    st.subheader("📊 Rescue Planning")
    
    # Combine all zones into a single risk zone
    single_zone = zones.copy()
    single_zone['severity'] = 'Risk Zone'
    # Update population values for specific zones
    pop_updates = {
        'Nagari': 13308,
        'Sihawa': 3359,
        'Magarlod': 121430,
        'Kurud': 11469,
        'Dhamtari': 799781,
    }
    for zone, pop in pop_updates.items():
        single_zone.loc[single_zone['name'].str.lower() == zone.lower(), 'population'] = pop
    total_population = 799_781  # Set to provided value
    num_zones = len(single_zone)
    total_capacity = 11250  # Keep as before or update if needed
    
    # Display single metric
    st.markdown('<span style="color:#FFCCCB;font-weight:bold;font-size:1.2em;">🟥 Risk Zone</span>', unsafe_allow_html=True)
    
    # Display total statistics
    col_metrics, col_buttons = st.columns([2, 1])
    with col_metrics:
        st.metric("Total Population of Dhamtari", f"{total_population:,} people")
        # Add hospital beds metric
        st.metric("Total Hospital Bed Capacity", "250 beds")
        # Add details in figures
        st.markdown("**Details in figures:**")
        st.markdown("- **Total Population:** 799,781")
        st.markdown("- **Male:** 397,897")
        st.markdown("- **Female:** 401,884")
    with col_buttons:
        st.write("")
        st.write("")
        if st.button("🔄 Refresh Shelter Status"):
            if 'shelter_assignments' in st.session_state:
                del st.session_state.shelter_assignments
            st.rerun()
    
    # Zone list (no risk filter)
    st.subheader("🏘️ Flood Zones")
    display_zones = single_zone[['name', 'population']].copy()
    display_zones.columns = ['Zone Name', 'Population']
    st.dataframe(
        display_zones,
        hide_index=True,
        height=min(400, len(display_zones) * 35 + 38)
    )

# ── Multi-Agent Chat Panel ────────────────────────────────────

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
    # Add initial system message
    st.session_state.chat_history.append({
        'agent': 'CommanderAgent',
        'type': 'status',
        'msg': 'Flood Response System initialized. All agents standing by.',
        'time': datetime.now().strftime("%H:%M:%S")
    })

if 'current_role' not in st.session_state:
    st.session_state.current_role = 'CommanderAgent'

if 'agent_status' not in st.session_state:
    st.session_state.agent_status = {
        a:{'last_task':'Idle','status':'Ready'} for a in AGENTS
    }

st.markdown("---")
st.header("🤖 Agentic Chat Interface")

# Chat input
msg = st.text_input("Send message as Commander:", key="chat_input")

# Place Send and Clear All Logs buttons side by side
send_col, clear_col = st.columns([3, 1])
send_clicked = send_col.button("Send")
clear_clicked = clear_col.button("🗑️ Clear All Logs")

if clear_clicked:
    st.session_state.chat_history = []
    if 'shelter_assignments' in st.session_state:
        del st.session_state.shelter_assignments
    # Reset agent statuses to initial state
    st.session_state.agent_status = {
        a: {'last_task': 'Idle', 'status': 'Ready'} for a in AGENTS
    }
    st.rerun()

# Send message
if send_clicked:
    time_now = datetime.now().strftime("%H:%M:%S")
    
    # Update sending agent's status
    update_agent_status('CommanderAgent', f"Sent message: {msg[:30]}..." if len(msg) > 30 else f"Sent message: {msg}")
    
    # Add the sent message to chat history
    st.session_state.chat_history.append({
        'agent': 'CommanderAgent',
        'type': 'chat',
        'msg': msg,
        'time': time_now
    })
    
    # Use LangChain agents for intelligent responses
    try:
        # Process commander's message through the agent
        try:
            # Run the message through the LangChain agent with role context
            ai_response = agent.run(
                prompt.format(
                    current_role="CommanderAgent",
                    input=msg,
                    tools="\n".join(f"- {t.name}: {t.description}" for t in tools)
                )
            )
            
            # Extract 'Thought:' section if present
            import re
            thought_match = re.search(r"Thought:(.*?)(?:Action:|Observation:|Final Answer:|$)", ai_response, re.DOTALL)
            if thought_match:
                thought_text = thought_match.group(1).strip()
                if thought_text:
                    st.session_state.chat_history.append({
                        'agent': 'CommanderAgent',
                        'type': 'thought',
                        'msg': f"💡 Thought: {thought_text}",
                        'time': time_now
                    })
            # Extract 'Observation:' section if present
            observation_match = re.search(r"Observation:(.*?)(?:Thought:|Action:|Final Answer:|$)", ai_response, re.DOTALL)
            if observation_match:
                observation_text = observation_match.group(1).strip()
                if observation_text:
                    st.session_state.chat_history.append({
                        'agent': 'CommanderAgent',
                        'type': 'observation',
                        'msg': f"🔎 Observation: {observation_text}",
                        'time': time_now
                    })
            # Extract 'Final Answer:' section if present
            final_answer_match = re.search(r"Final Answer:(.*?)(?:\n[A-Z][a-z]+:|$)", ai_response, re.DOTALL)
            if final_answer_match:
                final_answer = final_answer_match.group(1).strip()
                if final_answer:
                    st.session_state.chat_history.append({
                        'agent': 'CommanderAgent',
                        'type': 'auto',
                        'msg': final_answer,
                        'time': time_now
                    })
                else:
                    st.session_state.chat_history.append({
                        'agent': 'CommanderAgent',
                        'type': 'auto',
                        'msg': ai_response,
                        'time': time_now
                    })
            else:
                st.session_state.chat_history.append({
                    'agent': 'CommanderAgent',
                    'type': 'auto',
                    'msg': ai_response,
                    'time': time_now
                })

            # Extract agent-specific tasks from the AI response
            tasks = {}
            try:
                task_extraction_prompt = f"""
                From the following response, extract a single, concise task instruction for each of these agents: {', '.join(AGENTS)}.
                If an agent is not mentioned or has no specific task, its task should be "Standing by".
                If a rescue or evacuation is needed (even if only implied), always assign a specific task to RescueAgent.
                Provide the output as a single JSON object where keys are the agent names and values are their assigned tasks.

                Response:
                ---
                {ai_response}
                ---
                """
                task_response_content = llm.invoke(task_extraction_prompt).content
                
                import re
                import json
                json_match = re.search(r'\{.*\}', task_response_content, re.DOTALL)
                if json_match:
                    tasks = json.loads(json_match.group(0))
                else:
                    st.warning("Could not parse agent tasks from AI response.")
                # Post-process: If rescue/evacuation is in user message or AI response and RescueAgent is 'Standing by', assign a default rescue task
                rescue_keywords = ["rescue", "evacuate", "evacuation"]
                if (
                    any(kw in msg.lower() for kw in rescue_keywords) or
                    any(kw in ai_response.lower() for kw in rescue_keywords)
                ):
                    if tasks.get("RescueAgent", "Standing by").strip().lower() == "standing by":
                        tasks["RescueAgent"] = "Initiate rescue operations in high-risk zones"
            except Exception as e:
                st.error(f"Error extracting agent tasks: {str(e)}")

            # Generate contextual responses for each agent based on the command
            for agent_name in AGENTS:
                if agent_name != 'CommanderAgent':
                    agent_task = tasks.get(agent_name, "Standing by")
                    # Only allow agent to respond if the task is not 'Standing by' and not a generic acknowledgement
                    if agent_task and agent_task.strip().lower() != "standing by":
                        agent_response = ""
                        try:
                            if agent_name == "SearchAgent":
                                agent_response = get_search_tool().func(agent_task)
                            elif agent_name == "RescueAgent":
                                agent_response = get_rescue_tool().func(agent_task)
                            elif agent_name == "LogisticsAgent":
                                agent_response = get_logistics_tool().func(agent_task)
                            elif agent_name == "CommsAgent":
                                agent_response = get_comms_tool().func(agent_task)
                            else:
                                agent_response = None
                        except Exception as e:
                            agent_response = f"Error processing command: {str(e)}"
                        # Update agent status after performing a real task
                        update_agent_status(agent_name, agent_task)
                        # Only add to chat history if the response is not a generic acknowledgement and not empty
                        if agent_response and not agent_response.lower().startswith("acknowledged") and not agent_response.lower().startswith("standing by"):
                            st.session_state.chat_history.append({
                                'agent': agent_name,
                                'type': 'auto',
                                'msg': agent_response,
                                'time': time_now
                            })
        except Exception as e:
            st.error(f"Error processing command: {str(e)}")
    except Exception as e:
        # Log any errors that occur during agent processing
        st.session_state.chat_history.append({
            'agent': 'System',
            'type': 'error',
            'msg': f"Error processing message: {str(e)}",
            'time': datetime.now().strftime("%H:%M:%S")
        })

# Status report
if st.button("Status Report"):
    time_now = datetime.now().strftime("%H:%M:%S")
    
    # Update CommanderAgent status for generating report
    update_agent_status('CommanderAgent', "Generating status report", "Reporting")
    
    for a in AGENTS:
        s = st.session_state.agent_status[a]
        
        # Format status message
        status_msg = (
            f"Current Status: {s['status']}\n"
            f"Last Task: {s['last_task']}\n"
            f"Last Updated: {time_now}"
        )
        
        st.session_state.chat_history.append({
            'agent': a,
            'type': 'status',
            'msg': status_msg,
            'time': time_now
        })
    
    # Reset CommanderAgent status after report
    update_agent_status('CommanderAgent', "Status report completed", "Ready")

# Chat Interface
st.markdown("---")
chat_col1, chat_col2 = st.columns([2, 1])

with chat_col1:
    st.subheader("💬 Commander Chat Log")
    chat_container = st.container()
    st.markdown("""
        <style>
        .stChatLog { overflow-y: auto; border: 1px solid #ddd; padding: 0; border-radius: 5px; background-color: #ffffff; display: flex; flex-direction: column; }
        .stChatLog > div:first-child { margin: 0 !important; padding: 0; display: flex; flex-direction: column-reverse; min-height: 100%; }
        .stChatLog > div { display: flex; flex-direction: column-reverse; }
        .chat-message { margin: 4px 8px; padding: 12px; border-radius: 8px; background-color: #f0f2f6; box-shadow: 0 1px 2px rgba(0,0,0,0.1); color: #1f1f1f; white-space: pre-wrap; order: 1; }
        .chat-header { margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
        .chat-time { color: #555; font-size: 0.8em; font-weight: 500; }
        .chat-message strong { color: #1f1f1f; margin-right: 4px; }
        .chat-message em { color: #2c5282; font-style: normal; font-weight: 500; padding: 2px 6px; background: rgba(44, 82, 130, 0.1); border-radius: 4px; }
        .chat-message pre { margin: 0; font-family: inherit; line-height: 1.5; }
        </style>
    """, unsafe_allow_html=True)
    with chat_container:
        st.markdown('<div class="stChatLog">', unsafe_allow_html=True)
        for e in st.session_state.chat_history:
            if e['agent'] == 'CommanderAgent' and e['type'] in ['chat', 'thought', 'observation', 'auto']:
                t = e['time']
                m = e['msg']
                ty = e['type']
                
                if ty == 'chat':
                    ag = 'Commander Agent'
                else:
                    ag = 'AI Agent'

                message_html = f'<div class="chat-message">'
                header = f'<div class="chat-header">'
                if ty == 'chat':
                    header += f'<span class="chat-time">👤 [{t}]</span> <strong>{ag}</strong>'
                elif ty == 'thought':
                    header += f'<span class="chat-time">💡 [{t}]</span> <strong>{ag}</strong> <em>thought</em>'
                elif ty == 'observation':
                    header += f'<span class="chat-time">🔎 [{t}]</span> <strong>{ag}</strong> <em>observation</em>'
                elif ty == 'auto':
                    header += f'<span class="chat-time">🤖 [{t}]</span> <strong>{ag}</strong> <em>response</em>'
                message_html += header + f'</div><pre>{m}</pre>'
                message_html += '</div>'
                st.markdown(message_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Add JavaScript for auto-scrolling
    st.markdown("""
        <script>
            function scrollToBottom() {
                const chatLog = document.querySelector('.stChatLog');
                if (chatLog) {
                    chatLog.scrollTop = 0;
                }
            }
            scrollToBottom();
            setTimeout(scrollToBottom, 100);
            const chatLog = document.querySelector('.stChatLog');
            if (chatLog) {
                chatLog.addEventListener('DOMSubtreeModified', () => {
                    if (chatLog.scrollTop <= 50) {
                        scrollToBottom();
                    }
                });
            }
        </script>
    """, unsafe_allow_html=True)

# Show other agents' logs in separate expanders
with chat_col1:
    for agent in ['LogisticsAgent', 'SearchAgent', 'RescueAgent', 'CommsAgent']:
        with st.expander(f"{agent} Dialogue Log", expanded=False):
            for e in st.session_state.chat_history:
                if e['agent'] == agent:
                    t = e['time']
                    m = e['msg']
                    ty = e['type']
                    st.markdown(f"**[{t}]** *{ty}*")
                    st.text(m)

with chat_col2:
    # Remove Commander Control and command_type UI
    pass

# Render agent status table
st.markdown("---")
st.subheader("📊 Agent Statuses")
df_status = pd.DataFrame([
    {"Agent":a, **st.session_state.agent_status[a]} for a in AGENTS
])
st.table(df_status.set_index("Agent"))