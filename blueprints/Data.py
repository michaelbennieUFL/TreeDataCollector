from flask import Blueprint, jsonify, send_from_directory
from flask_caching import Cache
from extension import cache  # Import the shared cache instance
import os

data_bp = Blueprint("data", __name__, url_prefix="/data")

# Define the paths to images and features directories
IMAGES_DIR = "./DataManager/cache/images"
FEATURES_DIR = "./DataManager/cache/features"


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
