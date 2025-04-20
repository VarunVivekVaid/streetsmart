import streamlit as st
import os
import pandas as pd
import subprocess
import folium
import datetime
import base64
from streamlit_folium import st_folium

def parse_gps_data(gps_str):
    """
    Safely evaluate the gps_data string.
    Uses eval with a restricted globals dictionary to allow datetime.datetime calls.
    """
    try:
        # Allow only the datetime module to resolve datetime.datetime(...)
        gps_points = eval(gps_str, {"datetime": datetime})
        return gps_points
    except Exception as e:
        st.warning(f"Failed to parse gps_data: {e}")
        return []

def get_video_data_url(clip_file):
    """
    Read the video file, encode it as base64, and return a data URL.
    This enables embedding the video in the HTML popup.
    """
    if os.path.exists(clip_file):
        try:
            with open(clip_file, "rb") as f:
                video_bytes = f.read()
            video_base64 = base64.b64encode(video_bytes).decode("utf-8")
            return f"data:video/mp4;base64,{video_base64}"
        except Exception as e:
            st.warning(f"Failed to load video file {clip_file}: {e}")
            return None
    else:
        st.warning(f"Video file {clip_file} does not exist.")
        return None

def main():
    st.title("Video Map Generator")

    # Ensure required directories exist
    for folder in ["input_videos", "output_clips"]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    st.header("1. Upload MP4 Videos")
    uploaded_files = st.file_uploader("Upload MP4 files", type=["mp4"], accept_multiple_files=True)
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_path = os.path.join("input_videos", uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
        st.success("Uploaded MP4 files successfully saved to input_videos/.")

    st.header("2. Process Videos")
    if st.button("Process Videos"):
        try:
            # Run the external video processing script.
            subprocess.run(["python", "video_processor.py"], check=True)
            st.success("Video processing completed. clips_data.csv generated.")
        except Exception as e:
            st.error(f"An error occurred while processing videos: {e}")

    st.header("3. Map with Video Clips")
    if os.path.exists("clips_data.csv"):
        df = pd.read_csv("clips_data.csv")
        st.write("Preview of clips_data.csv:")
        st.dataframe(df)

        # Determine default map center using the first valid GPS point
        default_lat, default_lon = 41.77, -88.12  # fallback coordinates
        for _, row in df.iterrows():
            gps_points = parse_gps_data(row["gps_data"])
            if gps_points and isinstance(gps_points, list) and "latitude" in gps_points[0]:
                default_lat = gps_points[0]["latitude"]
                default_lon = gps_points[0]["longitude"]
                break

        folium_map = folium.Map(location=[default_lat, default_lon], zoom_start=13)

        # Add one marker per video (using only the first GPS coordinate)
        for index, row in df.iterrows():
            clip_file = row["clip_file"]
            gps_points = parse_gps_data(row["gps_data"])
            if not gps_points or not isinstance(gps_points, list):
                continue

            first_point = gps_points[0]
            lat = first_point.get("latitude")
            lon = first_point.get("longitude")
            if lat is None or lon is None:
                continue

            # Encode the video file as a base64 data URL
            video_data_url = get_video_data_url(clip_file)
            if video_data_url:
                popup_html = f"""
                <div style="width: 340px">
                  <p><strong>Clip:</strong> {clip_file}</p>
                  <video width="320" height="240" controls>
                    <source src="{video_data_url}" type="video/mp4">
                    Your browser does not support the video tag.
                  </video>
                </div>
                """
            else:
                popup_html = f"<p>Clip file {clip_file} not found.</p>"

            popup = folium.Popup(popup_html, max_width=400)
            pin_color = "red" if row["pothole"] else "blue"
            folium.Marker(
                location=[lat, lon],
                popup=popup,
                icon=folium.Icon(color=pin_color, icon="film", prefix="fa")
            ).add_to(folium_map)

        st.subheader("Map View")
        st_folium(folium_map, width=700, height=500)
    else:
        st.info("clips_data.csv not found. Please upload videos and click 'Process Videos' first.")

if __name__ == "__main__":
    main()
