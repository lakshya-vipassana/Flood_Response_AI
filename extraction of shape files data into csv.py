import os
import glob
import geopandas as gpd
import pandas as pd

# Folder containing your shapefiles
shapefile_dir = "D:/flood data"

# Output directory for CSVs
output_dir = os.path.join(shapefile_dir, "csv_exports")
os.makedirs(output_dir, exist_ok=True)

# Get all shapefiles recursively
shapefiles = glob.glob(f"{shapefile_dir}/**/*.shp", recursive=True)

# Combined list (optional)
combined_data = []

for shp_path in shapefiles:
    try:
        gdf = gpd.read_file(shp_path)

        if gdf.empty:
            print(f"⚠️ Empty shapefile skipped: {shp_path}")
            continue

        # Get file name without extension
        base_name = os.path.splitext(os.path.basename(shp_path))[0]

        # Extract lat/lon from geometry (centroid for polygons)
        if gdf.geom_type.iloc[0] in ['Polygon', 'MultiPolygon']:
            gdf['latitude'] = gdf.geometry.centroid.y
            gdf['longitude'] = gdf.geometry.centroid.x
        elif gdf.geom_type.iloc[0] in ['Point', 'MultiPoint', 'LineString']:
            gdf['latitude'] = gdf.geometry.y
            gdf['longitude'] = gdf.geometry.x
        else:
            gdf['latitude'] = gdf.geometry.centroid.y
            gdf['longitude'] = gdf.geometry.centroid.x

        # Drop geometry column before saving to CSV
        gdf.drop(columns='geometry', inplace=True)

        # Save individual CSV
        csv_path = os.path.join(output_dir, f"{base_name}.csv")
        gdf.to_csv(csv_path, index=False)

        # For combined export
        gdf['source_file'] = base_name
        combined_data.append(gdf)

        print(f"✅ Exported: {base_name}.csv")

    except Exception as e:
        print(f"❌ Failed to process {shp_path}: {e}")

# Optional: Combined CSV of all
if combined_data:
    all_landmarks = pd.concat(combined_data, ignore_index=True)
    all_landmarks.to_csv(os.path.join(output_dir, "all_landmarks_combined.csv"), index=False)
    print("✅ Combined file: all_landmarks_combined.csv")
else:
    print("⚠️ No shapefiles processed.")

