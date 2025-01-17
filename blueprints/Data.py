from flask import Blueprint, jsonify, send_from_directory
from flask_caching import Cache
from extension import cache  # Import the shared cache instance
from PIL import Image  # For image processing
from io import BytesIO  # To create in-memory files
import os

data_bp = Blueprint("data", __name__, url_prefix="/data")

# Define the paths to images and features directories
IMAGES_DIR = "./DataManager/cache/images"
FEATURES_DIR = "./DataManager/cache/features"
JPEG_DIR = "./DataManager/cache/jpeg_images"  # Directory to store cached JPEGs

# Ensure JPEG directory exists
os.makedirs(JPEG_DIR, exist_ok=True)


@data_bp.route('/images/<path:filename>', methods=['GET'])
def get_image_file(filename):
    """
    GET /data/images/<filename>
    Serves image files from the local images directory if they exist.
    """
    file_path = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(file_path):
        return send_from_directory(IMAGES_DIR, filename)
    else:
        return jsonify({"error": f"Image file '{filename}' not found"}), 404


@data_bp.route('/features/<path:filename>', methods=['GET'])
def get_feature_file(filename):
    """
    GET /data/features/<filename>
    Serves GeoJSON feature files from the local features directory if they exist.
    """
    file_path = os.path.join(FEATURES_DIR, filename)
    if os.path.exists(file_path):
        return send_from_directory(FEATURES_DIR, filename)
    else:
        return jsonify({"error": f"Feature file '{filename}' not found"}), 404


@data_bp.route('/jpegimage/<path:filename>', methods=['GET'])
def get_jpeg_image(filename):
    """
    GET /data/jpegimage/<filename>
    Converts a TIFF image to JPEG format and serves it.
    Caching is handled via filesystem (JPEG_DIR).
    """
    if not filename.lower().endswith(".tif"):
        return jsonify({"error": "Only TIFF files can be converted to JPEG"}), 400

    tiff_path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(tiff_path):
        return jsonify({"error": f"TIFF file '{filename}' not found"}), 404

    # Create the output JPEG filename
    jpeg_filename = filename.rsplit(".", 1)[0] + ".jpg"
    jpeg_path = os.path.join(JPEG_DIR, jpeg_filename)

    # If the JPEG already exists, serve it directly
    if os.path.exists(jpeg_path):
        return send_from_directory(JPEG_DIR, jpeg_filename)

    # Convert TIFF to JPEG
    try:
        with Image.open(tiff_path) as img:
            # Convert image to RGB if it's not already
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Save as JPEG to the JPEG_DIR
            img.save(jpeg_path, "JPEG", quality=100, optimize=True, progressive=True)
    except Exception as e:
        return jsonify({"error": f"Failed to convert TIFF to JPEG: {str(e)}"}), 500

    # Serve the newly created JPEG
    return send_from_directory(JPEG_DIR, jpeg_filename)
