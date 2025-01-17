from flask import Blueprint, request, jsonify
from datetime import datetime
import os

# Assuming your TreeManipulator code is in the same folder or an importable module
from DataManager.TreeManipulator import TreeManipulator
from DataManager.treeData import TreeDataManager

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Instance of your Earth Engine-based data manager
dataManager = TreeDataManager(
    projectName='ee-michaelalexanderbennie',
    imageLocation='projects/ee-vasquezavicente/assets/BCI_50ha',
    featureLocation='projects/ee-vasquezavicente/assets/BCI_50ha_crownmap_timeseries',
    fileStorageLocation='./DataManager/cache',
    max_threads=30,
    poll_interval=3,
    working_directory="./DataManager/"
)

# Instance of your TreeManipulator (pointing to the same features folder)
treeManipulator = TreeManipulator(features_dir="./DataManager/cache/features")


@api_bp.route('/')
def index():
    """
    Original endpoint listing available image files and feature files.
    """
    data = {
        "image_files": dataManager.listImageTimeStamps(),
        "feature_files": dataManager.listFeaturesTimeStates()
    }
    return jsonify(data)


@api_bp.route('/treeinfo', methods=['GET'])
def get_tree_info():
    """
    GET /api/treeinfo?filename=YYYY_MM_DD.geojson&lat=xx.xxxxxx&lon=yy.yyyyyy
    Returns tree info (ID + properties) if the point is inside any polygon.
    """
    feature_filename = request.args.get('filename')
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not feature_filename or lat is None or lon is None:
        return jsonify({"error": "Missing required parameters: filename, lat, lon"}), 400

    tree_info = treeManipulator.getTreeInformation(feature_filename, lat, lon)
    if tree_info:
        return jsonify({"tree_found": True, "tree_info": tree_info}), 200
    else:
        return jsonify({"tree_found": False, "message": "No polygon contains this point"}), 200


@api_bp.route('/treeinfo', methods=['POST'])
def update_tree_info():
    """
    POST /api/treeinfo
    JSON body should contain:
    {
      "filename": "YYYY_MM_DD.geojson",
      "global_id": "SOME_ID",
      "adjacency_days": 10,
      "new_properties": { "status": "fallen" }
    }
    """
    data = request.json
    if not data:
        return jsonify({"error": "JSON body is required"}), 400

    filename = data.get('filename')
    global_id = data.get('global_id')
    adjacency_days = data.get('adjacency_days', 0)
    new_properties = data.get('new_properties', {})

    if not filename or not global_id:
        return jsonify({"error": "Missing required fields: filename, global_id"}), 400

    treeManipulator.updateTreeInformation(
        feature_filename=filename,
        global_id=global_id,
        new_properties=new_properties,
        adjacency_days=adjacency_days
    )
    return jsonify({"status": "update initiated"}), 200


@api_bp.route('/features/sorted', methods=['GET'])
def list_features_sorted():
    """
    GET /api/features/sorted
    Returns the feature files in ascending date order.
    (If you want descending, you can reverse it.)
    """
    feature_dates = dataManager.listFeaturesTimeStates()  # e.g. ["2018_04_04", "2018_05_01", ...]
    # If you want actual file names with .geojson, you might do:
    # sorted_fnames = sorted([f"{d}.geojson" for d in feature_dates])
    # For demonstration, we return the date strings themselves
    return jsonify({"sorted_feature_dates": feature_dates}), 200


@api_bp.route('/feature/<feature_filename>/image', methods=['GET'])
def get_corresponding_image(feature_filename):
    """
    GET /api/feature/2024_02_01.geojson/image
    1) Parse date from '2024_02_01.geojson' => '2024-02-01'
    2) Check if '2024-02-01.tif' is in local image folder
    3) Return a JSON with the image path or an error if not found
    """
    # Strip out .geojson
    date_str = feature_filename.replace(".geojson", "")
    try:
        parsed_date = datetime.strptime(date_str, "%Y_%m_%d").strftime("%Y-%m-%d")
    except ValueError:
        return jsonify({"error": f"Invalid feature filename {feature_filename}. Expected YYYY_MM_DD.geojson"}), 400

    # The local image file we expect to see
    expected_image_name = f"{parsed_date}.tif"
    images_folder = os.path.join(dataManager.fileStorageLocation, 'images')
    local_path = os.path.join(images_folder, expected_image_name)

    if os.path.exists(local_path):
        return jsonify({
            "feature_filename": feature_filename,
            "image_filename": expected_image_name,
            "local_path": local_path
        }), 200
    else:
        # Perhaps the image doesn’t exist locally yet
        return jsonify({"error": "No corresponding image file found", "expected_image": expected_image_name}), 404
