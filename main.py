from fastapi import FastAPI
from sqlalchemy import create_engine
import geopandas as gpd
import networkx as nx
import osmnx as ox
import joblib
import requests
import pandas as pd
from datetime import datetime
import os

app = FastAPI()

# --- SETUP ---
# 1. Connect to the database (which is now pre-populated)
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# 2. Load map data from the pre-populated database
print("Loading map data from PostGIS...")
nodes_gdf = gpd.read_postgis("SELECT * FROM nodes", engine, index_col='osmid', geom_col='geometry')
edges_gdf = gpd.read_postgis("SELECT * FROM edges", engine, index_col=['u', 'v', 'key'], geom_col='geometry')
G_base = ox.graph_from_gdfs(nodes_gdf, edges_gdf)
print("Map data loaded.")

# ... (các phần code còn lại giữ nguyên) ...
# 4. Tải mô hình AI
print("Loading AI model...")
flood_model = joblib.load('flood_model.joblib')
print("AI model loaded.")

# 5. Cấu hình API thời tiết
API_KEY = "d4b84d495c4303582c5835a354d9b3c9" # <-- THAY API KEY CỦA BẠN
LATITUDE = 21.0245
LONGITUDE = 105.8412


# --- API ENDPOINTS (Giữ nguyên) ---
@app.get("/")
def read_root():
    return {"message": "AI Pathfinding API is ready!"}

@app.get("/find_smart_route")
def find_smart_route(start_node_id: int, end_node_id: int):
    # ... (toàn bộ code của endpoint này giữ nguyên như trước) ...
    # Lấy thời tiết -> Dự đoán -> Cập nhật chi phí -> Chạy A*
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={LATITUDE}&lon={LONGITUDE}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    weather_data = response.json()
    
    current_temp = weather_data['main']['temp']
    current_humidity = weather_data['main']['humidity']
    current_wind_speed = weather_data['wind']['speed']
    now = datetime.now()
    current_month = now.month
    current_hour = now.hour
    is_rainy = 1 if current_month in [6, 7, 8] else 0

    input_df = pd.DataFrame(
        [[current_temp, current_humidity, current_wind_speed, current_month, current_hour, is_rainy]],
        columns=['temp', 'humidity', 'wind_speed', 'month', 'hour', 'is_rainy_season']
    )
    
    is_flooded_prediction = flood_model.predict(input_df)[0]

    G_dynamic = G_base.copy()
    
    if is_flooded_prediction == 1:
        print("AI predicts flooding. Increasing travel costs...")
        for u, v, data in G_dynamic.edges(data=True):
            data['weight'] = data['length'] * 10 
    else:
        print("Weather is clear. Using standard travel costs.")
        for u, v, data in G_dynamic.edges(data=True):
            data['weight'] = data['length']

    try:
        path = nx.astar_path(G_dynamic, source=start_node_id, target=end_node_id, weight='weight')
        return {
            "message": "Smart route found!",
            "is_flooded_predicted": bool(is_flooded_prediction),
            "path": path
        }
    except nx.NetworkXNoPath:
        return {"error": f"No path found between {start_node_id} and {end_node_id}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}