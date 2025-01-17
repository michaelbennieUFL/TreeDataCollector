import os
import json
from shapely.geometry import shape, Point
from datetime import datetime, timedelta

class TreeManipulator:
    def __init__(self, features_dir="./features"):
        """
        :param features_dir: Path to the folder containing your *.geojson feature files.
        """
        self.features_dir = features_dir
        self.all_feature_files = sorted([
            f for f in os.listdir(self.features_dir)
            if f.endswith(".geojson")
        ])

    def getTreeInformation(self, feature_filename, lat, lon):
        """
        1) Reads the specified local GeoJSON file.
        2) Finds which polygon contains the given (lat, lon).
        3) Returns that tree’s Feature ID + properties (or None if not found).

        :param feature_filename: The name of the .geojson file, e.g. "2024_02_01.geojson"
        :param lat: latitude of the target point
        :param lon: longitude of the target point
        :return: dict with {'id': ..., 'properties': ...} or None if no polygon found.
        """
        file_path = os.path.join(self.features_dir, feature_filename)
        if not os.path.exists(file_path):
            print(f"[ERROR] File {feature_filename} not found in {self.features_dir}.")
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)

        point = Point(lat,lon)
        # Loop through features and check if the point is contained within the feature geometry
        for feature in geojson_data.get('features', []):
            # Parse geometry
            geom = shape(feature.get('geometry', {}))
            if geom.contains(point):
                # Found the containing polygon
                # The feature might have 'id' or might rely on properties['global_id']:
                fid = feature.get('id', None)  # or feature['properties']['global_id']
                props = feature.get('properties', {})
                return {'id': fid, 'properties': props}

        print(f"[INFO] No polygon in {feature_filename} contains point ({lat}, {lon}).")
        return None

    def updateTreeInformation(self, feature_filename, global_id, new_properties, adjacency_days=0):
        """
        1) Parse the date from `feature_filename` (e.g. "YYYY_MM_DD.geojson").
        2) Find all geojson files in `self.features_dir` whose dates are within ± adjacency_days of that date.
        3) For each such file, if a feature with matching global_id exists, update that feature's properties.
        4) Save the updated file back to disk (overwrite).

        :param feature_filename: e.g. "2024_02_01.geojson"
        :param global_id: the unique tree id to look for (could be in feature['id'] or properties['global_id'])
        :param new_properties: dict of properties to update (e.g. {'status': 'fallen', 'height': 22.5})
        :param adjacency_days: number of days before and after the date to update as well
        """
        # 1) Parse the date from the feature_filename, which we expect to be "YYYY_MM_DD.geojson"
        base_date_str = feature_filename.replace(".geojson", "")
        try:
            base_date = datetime.strptime(base_date_str, "%Y_%m_%d")
        except ValueError:
            print(f"[ERROR] Could not parse date from filename {feature_filename}. Expected 'YYYY_MM_DD.geojson'.")
            return

        # 2) Build a list of all candidate filenames within ± adjacency_days
        #    We'll parse each file's date and check if it's within the range.
        #    We assume all files have valid "YYYY_MM_DD.geojson" naming.
        date_min = base_date - timedelta(days=adjacency_days)
        date_max = base_date + timedelta(days=adjacency_days)

        # Filter the self.all_feature_files by date
        candidate_files = []
        for fname in self.all_feature_files:
            # parse date
            file_date_str = fname.replace(".geojson", "")
            try:
                file_date = datetime.strptime(file_date_str, "%Y_%m_%d")
            except ValueError:
                continue
            if date_min <= file_date <= date_max:
                candidate_files.append(fname)

        if not candidate_files:
            print("[INFO] No candidate files found within adjacency range.")
            return

        # 3) For each file in candidate_files, find and update the relevant feature
        for cfile in candidate_files:
            cpath = os.path.join(self.features_dir, cfile)
            with open(cpath, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)

            updated_any_feature = False
            for feature in geojson_data.get('features', []):

                props = feature.get('properties', {})
                # Compare either feature['id'] == global_id or props['global_id'] == global_id

                if 'GlobalID' in props and props['GlobalID'] == global_id:
                    # Update properties
                    props.update(new_properties)
                    feature['properties'] = props
                    updated_any_feature = True

            # 4) Save changes back to the same file if we changed anything
            if updated_any_feature:
                with open(cpath, 'w', encoding='utf-8') as outf:
                    json.dump(geojson_data, outf, ensure_ascii=False, indent=2)
                print(f"[INFO] Updated file: {cfile} for global_id: {global_id}")
            else:
                print(f"[INFO] No matching feature with global_id={global_id} found in {cfile}.")

# -------------------------------------------------------------------------
# Example Usage
# -------------------------------------------------------------------------
if __name__ == "__main__":
    tm = TreeManipulator(features_dir="./cache/features")

    # 1. Get tree info from a specific file by location
    lat_test, lon_test = -79.84771837349704,9.151337790586185  # example coordinates near BCI
    tree_info = tm.getTreeInformation("2024_02_01.geojson", lat_test, lon_test)
    if tree_info:
        print("Found Tree:", tree_info)

    # 2. Update a tree's property for a given global_id and also
    #    for all files within ±10 days from 2024_02_01.
    new_props = {"status": "fallen"}
    tm.updateTreeInformation(
        feature_filename="2024_02_01.geojson",
        global_id=tree_info["properties"]["GlobalID"],
        new_properties=new_props,
        adjacency_days=10
    )
