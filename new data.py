import os
import osmnx as ox
import geopandas as gpd
import folium

# Define the place of interest
place = "Dhamtari, Chhattisgarh, India"

# Define OSM tags of interest
tags = {
    'amenity': ['hospital', 'school', 'townhall', 'bus_station', 'place_of_worship'],
    'railway': ['station']
}

# Download OSM data for the defined tags
print("🔍 Downloading OpenStreetMap data...")
gdf = ox.features_from_place(place, tags)
print("✅ Data downloaded.")

# Create a base Folium map centered on Dhamtari
map_dhamtari = folium.Map(location=[20.71, 81.55], zoom_start=12)

# Helper function to add each feature type to the map
def add_layer(gdf, key, value, color, label):
    if key in gdf.columns:
        sub = gdf[gdf[key] == value]
        for _, row in sub.iterrows():
            geom = row.geometry
            name = row.get('name', label)
            if geom.geom_type == 'Point':
                folium.Marker(
                    location=[geom.y, geom.x],
                    tooltip=name,
                    icon=folium.Icon(color=color)
                ).add_to(map_dhamtari)
            elif geom.geom_type in ['LineString', 'Polygon', 'MultiPolygon']:
                folium.GeoJson(
                    geom,
                    name=label,
                    tooltip=name,
                    style_function=lambda x: {'color': color, 'weight': 2}
                ).add_to(map_dhamtari)



# Save the interactive map
map_dhamtari.save("dhamtari_shelters_map.html")
print("✅ Map saved as dhamtari_shelters_map.html")

# Create output directory for shapefiles
output_dir = "dhamtari_shapefiles"
os.makedirs(output_dir, exist_ok=True)

# Export filtered GeoDataFrames to individual shapefiles
print("💾 Saving shapefiles...")
if 'amenity' in gdf.columns:
    gdf[gdf['amenity'] == 'hospital'].to_file(f"{output_dir}/hospitals.shp")
    gdf[gdf['amenity'] == 'school'].to_file(f"{output_dir}/schools.shp")
    gdf[gdf['amenity'] == 'townhall'].to_file(f"{output_dir}/townhalls.shp")
    gdf[gdf['amenity'] == 'bus_station'].to_file(f"{output_dir}/bus_stations.shp")
    gdf[gdf['amenity'] == 'place_of_worship'].to_file(f"{output_dir}/temples.shp")

if 'railway' in gdf.columns:
    gdf[gdf['railway'] == 'station'].to_file(f"{output_dir}/railway_stations.shp")

print(f"✅ Shapefiles saved in folder: {output_dir}")
# Merge all layers into one GeoDataFrame with a new column 'facility_type'
merged_layers = []

if 'amenity' in gdf.columns:
    hospital = gdf[gdf['amenity'] == 'hospital'].copy()
    hospital['facility_type'] = 'hospital'
    merged_layers.append(hospital)

    school = gdf[gdf['amenity'] == 'school'].copy()
    school['facility_type'] = 'school'
    merged_layers.append(school)

    townhall = gdf[gdf['amenity'] == 'townhall'].copy()
    townhall['facility_type'] = 'townhall'
    merged_layers.append(townhall)

    temple = gdf[gdf['amenity'] == 'place_of_worship'].copy()
    temple['facility_type'] = 'temple_church'
    merged_layers.append(temple)

    bus = gdf[gdf['amenity'] == 'bus_station'].copy()
    bus['facility_type'] = 'bus_station'
    merged_layers.append(bus)

if 'railway' in gdf.columns:
    rail = gdf[gdf['railway'] == 'station'].copy()
    rail['facility_type'] = 'railway_station'
    merged_layers.append(rail)

# Concatenate all
merged_gdf = gpd.GeoDataFrame(pd.concat(merged_layers, ignore_index=True), crs=gdf.crs)

# Export to a merged shapefile and GeoPackage
merged_gdf.to_file(f"{output_dir}/merged_facilities.shp")
merged_gdf.to_file(f"{output_dir}/merged_facilities.gpkg", layer='facilities', driver="GPKG")

print("✅ Merged shapefile and GeoPackage saved.")
