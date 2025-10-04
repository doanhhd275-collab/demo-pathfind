from fastapi import FastAPI
from sqlalchemy import create_engine
import geopandas as gpd
import networkx as nx
import osmnx as ox
import joblib       # Để tải model
import requests     # Để gọi API thời tiết
import pandas as pd # Để tạo DataFrame cho model
from datetime import datetime
import os
# --- SETUP (Chạy 1 lần khi server khởi động) ---
app = FastAPI()

# 1. Kết nối Database
 # Thêm dòng này ở đầu file

#... các dòng code khác ...

# THAY THẾ các dòng db_user, db_password, ... bằng khối code này
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("No DATABASE_URL set for the application")
engine = create_engine(DATABASE_URL)

# 2. Tải bản đồ từ PostGIS và tạo đồ thị gốc
print("Loading map data from PostGIS...")
nodes_gdf = gpd.read_postgis("SELECT * FROM nodes", engine, index_col='osmid', geom_col='geometry')
edges_gdf = gpd.read_postgis("SELECT * FROM edges", engine, index_col=['u', 'v', 'key'], geom_col='geometry')
G_base = ox.graph_from_gdfs(nodes_gdf, edges_gdf)
print("Map data loaded.")

# 3. Tải mô hình AI đã huấn luyện
print("Loading AI model...")
absolute_path = r"C:\DATA\Coding files\Python\project\flood_model.joblib"

flood_model = joblib.load(absolute_path)
print("AI model loaded.")

# 4. Cấu hình API thời tiết
API_KEY = "d4b84d495c4303582c5835a354d9b3c9" # <-- THAY API KEY CỦA BẠN
LATITUDE = 21.0245
LONGITUDE = 105.8412

# --- API ENDPOINTS ---
@app.get("/")
def read_root():
    return {"message": "AI Pathfinding API is ready!"}

@app.get("/find_smart_route")
def find_smart_route(start_node_id: int, end_node_id: int):
    # --- BƯỚC 1: LẤY DỮ LIỆU THỜI TIẾT HIỆN TẠI ---
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={LATITUDE}&lon={LONGITUDE}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    weather_data = response.json()
    
    # --- BƯỚC 2: DÙNG AI ĐỂ DỰ ĐOÁN NGẬP LỤT ---
    current_temp = weather_data['main']['temp']
    current_humidity = weather_data['main']['humidity']
    current_wind_speed = weather_data['wind']['speed']
    now = datetime.now()
    current_month = now.month
    current_hour = now.hour
    is_rainy = 1 if current_month in [6, 7, 8] else 0

    # Tạo DataFrame cho dữ liệu mới
    input_df = pd.DataFrame(
        [[current_temp, current_humidity, current_wind_speed, current_month, current_hour, is_rainy]],
        columns=['temp', 'humidity', 'wind_speed', 'month', 'hour', 'is_rainy_season']
    )
    
    # Dự đoán
    is_flooded_prediction = flood_model.predict(input_df)[0]

    # --- BƯỚC 3: CẬP NHẬT "CHI PHÍ" ĐƯỜNG ĐI DỰA TRÊN DỰ ĐOÁN ---
    G_dynamic = G_base.copy() # Tạo bản sao của đồ thị để thay đổi
    
    if is_flooded_prediction == 1:
        print("AI predicts flooding. Increasing travel costs...")
        for u, v, data in G_dynamic.edges(data=True):
            # Tăng chi phí của mỗi con đường lên 10 lần nếu có ngập
            data['weight'] = data['length'] * 10 
    else:
        print("Weather is clear. Using standard travel costs.")
        for u, v, data in G_dynamic.edges(data=True):
            # Chi phí bình thường là chiều dài
            data['weight'] = data['length']

    # --- BƯỚC 4: CHẠY A* TRÊN ĐỒ THỊ ĐÃ CẬP NHẬT ---
    try:
        # Chạy A* với trọng số (chi phí) đã được cập nhật
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