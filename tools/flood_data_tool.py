import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import requests
from typing import Dict, List, Optional, Tuple
import json
import logging
import geopandas as gpd
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FloodDataTool:
    def __init__(self):
        """Initialize the FloodDataTool with necessary configurations."""
        self.data = None
        self.last_updated = None
    
    def load_data_from_csv(self, file_path: str) -> bool:
        """
        Load flood data from a CSV file.
        
        Args:
            file_path (str): Path to the CSV file containing flood data
            
        Returns:
            bool: True if data was loaded successfully, False otherwise
        """
        try:
            self.data = pd.read_csv(file_path)
            self.last_updated = datetime.now()
            logger.info(f"Successfully loaded data from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            return False
    
    def fetch_weather_data(self, api_key: str, location: Dict[str, float]) -> Dict:
        """
        Fetch current weather data for flood risk assessment.
        
        Args:
            api_key (str): API key for weather service
            location (Dict[str, float]): Dictionary containing latitude and longitude
            
        Returns:
            Dict: Weather data response
        """
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": location["latitude"],
                "lon": location["longitude"],
                "appid": api_key,
                "units": "metric"
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching weather data: {str(e)}")
            return {}

    def calculate_flood_risk(self, rainfall: float, water_level: float, 
                           terrain_slope: float) -> Tuple[str, float]:
        """
        Calculate flood risk based on various parameters.
        
        Args:
            rainfall (float): Recent rainfall in mm
            water_level (float): Current water level in meters
            terrain_slope (float): Terrain slope in degrees
            
        Returns:
            Tuple[str, float]: Risk category and risk score
        """
        try:
            # Simple risk calculation formula
            risk_score = (rainfall * 0.4) + (water_level * 0.4) + ((90 - terrain_slope) * 0.2)
            risk_score = min(100, max(0, risk_score))
            
            # Determine risk category
            if risk_score >= 75:
                category = "Severe"
            elif risk_score >= 50:
                category = "High"
            elif risk_score >= 25:
                category = "Moderate"
            else:
                category = "Low"
                
            return category, risk_score
        except Exception as e:
            logger.error(f"Error calculating flood risk: {str(e)}")
            return "Unknown", 0.0

    def visualize_flood_data(self, data_type: str = "risk_over_time") -> None:
        """
        Create visualizations of flood data.
        
        Args:
            data_type (str): Type of visualization to create
        """
        try:
            if self.data is None:
                logger.error("No data available for visualization")
                return

            plt.figure(figsize=(10, 6))
            
            if data_type == "risk_over_time":
                plt.plot(self.data['timestamp'], self.data['risk_score'])
                plt.title('Flood Risk Over Time')
                plt.xlabel('Time')
                plt.ylabel('Risk Score')
            
            plt.grid(True)
            plt.tight_layout()
            plt.savefig('flood_risk_visualization.png')
            plt.close()
            
            logger.info(f"Successfully created {data_type} visualization")
        except Exception as e:
            logger.error(f"Error creating visualization: {str(e)}")

    def generate_report(self, location: str) -> Dict:
        """
        Generate a comprehensive flood report.
        
        Args:
            location (str): Location name for the report
            
        Returns:
            Dict: Report containing flood analysis results
        """
        try:
            if self.data is None:
                return {"error": "No data available for report generation"}

            report = {
                "location": location,
                "timestamp": datetime.now().isoformat(),
                "data_summary": {
                    "total_records": len(self.data),
                    "last_updated": self.last_updated.isoformat() if self.last_updated else None,
                },
                "risk_analysis": {
                    "current_risk": self.data['risk_score'].iloc[-1] if 'risk_score' in self.data.columns else None,
                    "average_risk": self.data['risk_score'].mean() if 'risk_score' in self.data.columns else None,
                },
                "recommendations": self._generate_recommendations()
            }
            
            return report
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return {"error": str(e)}

    def _generate_recommendations(self) -> List[str]:
        """
        Generate safety recommendations based on flood risk.
        
        Returns:
            List[str]: List of safety recommendations
        """
        recommendations = [
            "Monitor local weather updates regularly",
            "Keep emergency supplies ready",
            "Know your evacuation routes",
            "Keep important documents in a waterproof container"
        ]
        
        if self.data is not None and 'risk_score' in self.data.columns:
            current_risk = self.data['risk_score'].iloc[-1]
            if current_risk >= 75:
                recommendations.extend([
                    "Evacuate to higher ground immediately",
                    "Follow emergency services instructions"
                ])
            elif current_risk >= 50:
                recommendations.extend([
                    "Prepare for possible evacuation",
                    "Move valuable items to higher levels"
                ])
        
        return recommendations

def load_zones():
    """Load flood zones as a GeoDataFrame."""
    return gpd.read_file(Path(__file__).parent.parent / "data/dhamtari_zones.geojson").to_crs(epsg=4326)

def load_shelters():
    """Load shelters as a GeoDataFrame."""
    df = pd.read_csv(Path(__file__).parent.parent / "data/shelters.csv")
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")

if __name__ == "__main__":
    # Example usage
    flood_tool = FloodDataTool()
    
    # Example location
    sample_location = {
        "latitude": 41.2565,
        "longitude": -95.9345
    }
    
    # Calculate sample flood risk
    risk_category, risk_score = flood_tool.calculate_flood_risk(
        rainfall=50.0,
        water_level=2.5,
        terrain_slope=15.0
    )
    
    print(f"Flood Risk Category: {risk_category}")
    print(f"Risk Score: {risk_score:.2f}")

