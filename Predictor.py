import sys
import os
import numpy as np
import cv2
import pandas as pd
from tensorflow.keras.models import load_model

# Frame size expected by the model
size = 100

# Load the pretrained model
model = load_model('sample.keras')

# Usage: python Predictor.py <input_csv>
if len(sys.argv) < 2:
    print("Usage: python Predictor.py <input_csv>")
    sys.exit(1)

csv_path = sys.argv[1]

# Read the CSV containing clip metadata
if not os.path.isfile(csv_path):
    print(f"CSV file not found: {csv_path}")
    sys.exit(1)
df = pd.read_csv(csv_path)

# Iterate over each clip row
for idx, row in df.iterrows():
    clip_file = row['clip_file']
    print(f"Processing clip: {clip_file}...")
    if not os.path.isfile(clip_file):
        print(f"  Error: clip file not found: {clip_file}")
        continue

    cap = cv2.VideoCapture(clip_file)
    if not cap.isOpened():
        print(f"  Error opening video file: {clip_file}")
        continue

    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    pothole_detected = False

    # Extract 10 evenly spaced frames (in-memory, no files saved)
    for i in range(10):
        frame_idx = int(i * total_frames / 10)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            print(f"  Warning: could not read frame {frame_idx}")
            continue

        # Preprocess for model
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (size, size))
        x = resized.reshape(1, size, size, 1)

        # Predict
        predictions = model.predict(x)
        predicted_class = np.argmax(predictions, axis=1)[0]
        print(f"    Frame {i} -> class {predicted_class}")

        # Class 1 indicates pothole
        if predicted_class == 1:
            pothole_detected = True
            break

    cap.release()

    # Update the DataFrame
    df.at[idx, 'pothole'] = pothole_detected
    print(f"  Pothole detected: {pothole_detected}\n")

# Write updates back to the same CSV (in-place)
df.to_csv(csv_path, index=False)
print(f"CSV updated: {csv_path}")
