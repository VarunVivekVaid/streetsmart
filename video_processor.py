import os
import subprocess
import json
import re
import pandas as pd
from datetime import datetime, timedelta

def segment_video_single(input_file, output_dir, segment_length=10):
    """
    Uses FFmpeg to segment a single video file into clips of segment_length seconds.
    Output files are named as <basename>_clip_%03d.mp4 in output_dir.
    Returns the list of output clip filenames (full paths).
    """
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_pattern = os.path.join(output_dir, f"{base_name}_clip_%03d.mp4")
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", input_file,
        "-c", "copy",
        "-map_metadata", "0",
        "-f", "segment",
        "-segment_time", str(segment_length),
        "-reset_timestamps", "1",
        output_pattern
    ]
    print(f"Segmenting {input_file} into 10-second clips...")
    subprocess.run(ffmpeg_cmd, check=True)
    
    # Gather generated clips for this file.
    clips = [os.path.join(output_dir, f)
             for f in os.listdir(output_dir)
             if f.startswith(base_name + "_clip_") and f.endswith(".mp4")]
    clips.sort()  # Ensure ordering.
    return clips

def get_clip_duration(clip_file):
    """
    Uses FFprobe to determine the duration (in seconds) of a video clip.
    """
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        clip_file
    ]
    try:
        output = subprocess.check_output(ffprobe_cmd).decode().strip()
        duration = float(output)
    except Exception as e:
        print(f"Error getting duration for {clip_file}: {e}")
        duration = 0.0
    return duration

def extract_clip_metadata(clip_file):
    """
    Uses FFprobe to extract full metadata for the given clip.
    Returns the metadata as a Python dictionary.
    """
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        clip_file
    ]
    try:
        output = subprocess.check_output(ffprobe_cmd).decode()
        metadata = json.loads(output)
    except Exception as e:
        print(f"Error extracting metadata for {clip_file}: {e}")
        metadata = {}
    return metadata

def extract_raw_gps_data(input_file):
    """
    Uses ExifTool to extract the raw metadata string (including embedded mov_text stream data)
    from the input file.
    """
    cmd = ["exiftool", "-ee", "-b", input_file]
    try:
        output = subprocess.check_output(cmd).decode('utf-8', errors='ignore')
        return output
    except Exception as e:
        print("Error extracting raw GPS data:", e)
        return ""

def parse_gps_data(raw_string):
    """
    Parses the raw GPS metadata string to extract records.
    Each valid record is expected to match the following pattern:
      YYYY:MM:DD HH:MM:SSZ<latitude><longitude>
    For example:
      2025:03:31 23:00:35Z41.7698047868907-88.120337175205329
    Returns a list of dictionaries with keys: timestamp, latitude, longitude.
    """
    gps_records = []
    # Regex pattern: timestamp with 'Z', then latitude then longitude (allowing for spaces).
    pattern = re.compile(
        r'(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}Z)\s*([+-]?\d+\.\d+)\s*([+-]\d+\.\d+)'
    )
    matches = pattern.findall(raw_string)
    for ts_str, lat_str, lon_str in matches:
        try:
            dt = datetime.strptime(ts_str, "%Y:%m:%d %H:%M:%SZ")
            lat = float(lat_str)
            lon = float(lon_str)
            gps_records.append({
                "timestamp": dt,
                "latitude": lat,
                "longitude": lon
            })
        except Exception as e:
            print("Error processing GPS record:", (ts_str, lat_str, lon_str), e)
    gps_records.sort(key=lambda x: x["timestamp"])
    return gps_records

def get_video_start_time(input_file):
    """
    Uses FFprobe to extract the video's start time from available tags.
    Tries 'encoded_date' first, then 'creation_time'.
    Returns a datetime object, or None if extraction fails.
    """
    for tag in ["encoded_date", "creation_time"]:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", f"format_tags={tag}",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_file
        ]
        try:
            output = subprocess.check_output(cmd).decode().strip()
            if output:
                output = output.replace("UTC", "").strip()
                dt = datetime.strptime(output, "%Y-%m-%d %H:%M:%S")
                return dt
        except Exception as e:
            print(f"Error extracting {tag} from video: {e}")
    return None

def associate_gps_with_clips(clips_info, gps_records, video_start, segment_length=10):
    """
    Associates each GPS record with its corresponding clip based on time.
    Each clip covers the interval:
      video_start + i*segment_length  to video_start + (i+1)*segment_length
    Adds a 'gps_data' key (a list of GPS records) to each clip's dictionary.
    """
    for i, clip in enumerate(clips_info):
        clip_start = video_start + timedelta(seconds=i * segment_length)
        clip_end = video_start + timedelta(seconds=(i + 1) * segment_length)
        clip_gps = [rec for rec in gps_records if clip_start <= rec["timestamp"] < clip_end]
        clip["gps_data"] = clip_gps
    return clips_info

def process_single_file(input_file, output_dir, segment_length=10):
    """
    Processes a single MP4 file:
      - Segments it into 10-second clips (output in output_dir).
      - Discards clips that are not exactly 10 seconds.
      - Extracts raw GPS metadata and parses it.
      - Determines the video's start time.
      - Associates GPS data with each clip.
    Returns a list of dictionaries (one per valid clip) with clip details.
    """
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    # Segment the video into clips.
    clip_files = segment_video_single(input_file, output_dir, segment_length)
    
    # Extract and parse GPS data.
    raw_gps_data = extract_raw_gps_data(input_file)
    gps_records = parse_gps_data(raw_gps_data)
    print(f"File {input_file}: Extracted {len(gps_records)} GPS records.")
    
    # Determine the video's start time.
    video_start = get_video_start_time(input_file)
    if video_start is None and gps_records:
        video_start = gps_records[0]["timestamp"]
    if video_start is None:
        raise ValueError(f"Unable to determine the start time for {input_file}.")
    print(f"File {input_file}: Video start time: {video_start}")
    
    file_clips = []
    for idx, clip_file in enumerate(clip_files):
        duration = get_clip_duration(clip_file)
        if abs(duration - segment_length) < 0.1:
            #metadata = extract_clip_metadata(clip_file)
            clip_data = {
                "source_file": input_file,
                "clip_file": clip_file,
                "clip_index": idx,
                "duration": duration,
                #"metadata": metadata,
                "pothole" : False,
                # gps_data will be added after association.
            }
            file_clips.append(clip_data)
        else:
            print(f"Discarding clip {clip_file} with duration {duration:.2f} seconds")
            os.remove(clip_file)
    
    # Associate the parsed GPS records with the clip time intervals.
    file_clips = associate_gps_with_clips(file_clips, gps_records, video_start, segment_length)
    return file_clips

def process_folder(input_folder, output_dir, segment_length=10):
    """
    Processes all MP4 files in input_folder, segments each file,
    and returns a combined list of clip information. All output clips are saved in output_dir.
    """
    all_clips = []
    for file in os.listdir(input_folder):
        if file.lower().endswith(".mp4"):
            input_file = os.path.join(input_folder, file)
            print(f"Processing file: {input_file}")
            try:
                file_clips = process_single_file(input_file, output_dir, segment_length)
                all_clips.extend(file_clips)
            except Exception as e:
                print(f"Error processing {input_file}: {e}")
    return all_clips

if __name__ == "__main__":
    # Specify the folder with source MP4 files and the output folder for clips.
    input_folder = "input_videos"    # Folder containing source MP4 files.
    output_folder = "output_clips"     # Folder to store all 10-second clips.
    segment_length = 10  # seconds
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Process every MP4 file in the input folder.
    clips_data = process_folder(input_folder, output_folder, segment_length)
    print(f"Total valid clips generated: {len(clips_data)}")
    
    # Create a DataFrame from the combined clip data.
    df = pd.DataFrame(clips_data)
    print("Final DataFrame (first few rows):")
    print(df.head())
    
    # Optionally, if using ace_tools:
    # ace_tools.display_dataframe_to_user("Clips Data", df)

    df.to_csv("clips_data.csv", index=False)
