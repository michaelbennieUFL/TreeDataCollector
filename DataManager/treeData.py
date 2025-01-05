import os
import json
import time
import ee
import folium
import concurrent.futures

try:
    from pydrive2.auth import GoogleAuth, ServiceAccountCredentials
    from pydrive2.drive import GoogleDrive
except ImportError:
    raise ImportError("PyDrive is required for automated Drive downloads. "
                      "Install with: pip install PyDrive")


class TreeDataManager:
    def __init__(self,
                 projectName,
                 imageLocation,
                 featureLocation,
                 fileStorageLocation,
                 max_threads=10,
                 poll_interval=10):
        """
        Initialize the TreeDataManager.

        :param projectName:         Name of the Earth Engine project or user project ID
        :param imageLocation:       Path to the Earth Engine ImageCollection
        :param featureLocation:     Path to the Earth Engine FeatureCollection
        :param fileStorageLocation: Local folder path to store downloaded images/features
        :param max_threads:         Maximum number of threads in the thread pool (default=10)
        :param poll_interval:       How many seconds to wait between polling for finished tasks (default=10)
        """

        self.SERVICE_ACCOUNT_FILE = 'service-account-key.json'
        self.projectName = projectName
        self.imageLocation = imageLocation
        self.featureLocation = featureLocation
        self.fileStorageLocation = fileStorageLocation
        self.max_threads = max_threads
        self.poll_interval = poll_interval

        # Authenticate and initialize Earth Engine
        # ee.Authenticate()  # Uncomment if needed for interactive authentication
        ee.Initialize(project=self.projectName)

        # Create local folders if they don't exist
        self.images_folder = os.path.join(self.fileStorageLocation, 'images')
        self.features_folder = os.path.join(self.fileStorageLocation, 'features')
        os.makedirs(self.images_folder, exist_ok=True)
        os.makedirs(self.features_folder, exist_ok=True)

        # Authenticate Google Drive (PyDrive).
        self.drive = self._authenticate_google_drive()

        # Ensure we have a Google Drive folder for Earth Engine exports
        self.drive_folder_name = 'EarthEngineExports'  # You can change this as needed.
        self.drive_folder_id = self._get_or_create_drive_folder(self.drive_folder_name)

    def updateFileCache(self):
        """
        1. Check which images and feature files already exist locally.
        2. Create separate threads to:
            a) Create Earth Engine export tasks to Google Drive for any missing images
            b) Download new feature GeoJSONs directly
        3. Wait for both threads to finish creating tasks/downloading features.
        4. Continuously poll Earth Engine tasks and download files from Drive as soon as they're ready.
        """
        local_images, local_features = self._list_local_files()

        # Use a thread pool to run the creation of export tasks and feature downloads in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            future_export_tasks = executor.submit(self._create_export_tasks_for_images, local_images)
            future_download_features = executor.submit(self._download_new_feature_files, local_features)

        # Retrieve the export_tasks list (once creation is done)
        export_tasks = future_export_tasks.result()
        # Feature downloads happen in parallel. If you want to catch exceptions, do:
        # future_download_features.result()

        # Now monitor tasks in a loop and download each as soon as it's complete.
        self._monitor_and_download(export_tasks)
        print("[INFO] updateFileCache completed.")

    def listImageTimeStamps(self):
        """
        List all available images in Earth Engine (based on system:time_start).
        """
        collection = ee.ImageCollection(self.imageLocation)
        dates = collection.aggregate_array('system:time_start') \
                          .map(lambda d: ee.Date(d).format('YYYY-MM-dd')) \
                          .getInfo()
        return dates

    def listFeaturesTimeStates(self):
        """
        List all available feature "dates" from Earth Engine based on a 'date' property.
        """
        fc = ee.FeatureCollection(self.featureLocation)
        all_dates = fc.aggregate_array('date').distinct().sort().getInfo()
        return all_dates

    def renderHTMLexample(self, image_date_str, feature_date_str, out_html):
        """
        Renders an example Folium map with a given image date and feature date.

        :param image_date_str:   e.g. '2018-04-04'
        :param feature_date_str: e.g. '2018_04_04'
        :param out_html:         filename for the output HTML
        """
        # Load the image from Earth Engine
        collection = ee.ImageCollection(self.imageLocation)
        image = collection.filterDate(image_date_str).first()

        # Visualization
        vis_params = {
            'bands': ['b1', 'b2', 'b3'],
            'min': 0,
            'max': 255,
            'gamma': 1
        }
        region = image.geometry()
        map_center = region.centroid().coordinates().getInfo()[::-1]
        m = folium.Map(location=map_center, zoom_start=16)

        # Add the image layer
        map_id_dict = image.getMapId(vis_params)
        folium.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Google Earth Engine',
            overlay=True,
            name='Image Layer'
        ).add_to(m)

        # Load the crowns for the given feature_date_str
        crowns = ee.FeatureCollection(self.featureLocation)
        filtered_crowns = crowns.filter(ee.Filter.eq('date', feature_date_str))
        count = filtered_crowns.size().getInfo()
        print(f"Number of crowns for {feature_date_str}: {count}")

        # Add crowns to the map
        folium.GeoJson(
            data=filtered_crowns.getInfo(),
            name='Crowns',
            style_function=lambda x: {
                'fillColor': 'transparent',
                'color': 'red',
                'weight': 1
            }
        ).add_to(m)

        # Layer control and save
        m.add_child(folium.LayerControl())
        m.save(out_html)
        print(f"[INFO] Map saved to {out_html}")

    # -------------------------------------------------------------------------
    # INTERNAL HELPER METHODS
    # -------------------------------------------------------------------------
    def _authenticate_google_drive(self):
        # Specify the scopes your app needs.
        # For basic Drive file read/write, this is the usual scope:
        scope = ["https://www.googleapis.com/auth/drive"]

        # Create GoogleAuth and load service account credentials
        gauth = GoogleAuth()
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self.SERVICE_ACCOUNT_FILE,
            scopes=scope
        )

        # Assign the service account credentials directly
        gauth.credentials = credentials
        print("[INFO] Service account credentials loaded successfully with PyDrive2.")

        # Create and return the GoogleDrive instance
        return GoogleDrive(gauth)

    def _get_or_create_drive_folder(self, folder_name):
        """
        Retrieves the folder ID for 'folder_name' in Drive.
        If it doesn't exist, creates it.
        Returns the folder ID as a string.
        """
        query = f"title = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false"
        file_list = self.drive.ListFile({'q': query}).GetList()

        if file_list:
            return file_list[0]['id']
        else:
            folder_metadata = {
                'title': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder_obj = self.drive.CreateFile(folder_metadata)
            folder_obj.Upload()
            return folder_obj['id']

    def _list_local_files(self):
        """
        Return the sets of local image filenames and local feature filenames.
        """
        local_images = set(os.listdir(self.images_folder))
        local_features = set(os.listdir(self.features_folder))
        return local_images, local_features

    # -------------------------------------------------------------------------
    # IMAGE EXPORTS
    # -------------------------------------------------------------------------
    def _create_export_tasks_for_images(self, local_images):
        """
        Creates Earth Engine export tasks for images that are missing locally *and*
        not already present in the Drive's EarthEngineExports folder.

        Returns a list of tuples (date_str, filename, ee_task) for the newly created tasks.
        """
        # 1) Build a dictionary of existing files in EarthEngineExports folder (to skip re-exports).
        query = f"'{self.drive_folder_id}' in parents and trashed=false"
        file_list = self.drive.ListFile({'q': query}).GetList()
        drive_files_dict = {f['title']: f for f in file_list}

        collection = ee.ImageCollection(self.imageLocation)
        dates = collection.aggregate_array('system:time_start') \
                          .map(lambda d: ee.Date(d).format('YYYY-MM-dd')) \
                          .getInfo()

        export_tasks = []

        for date_str in dates:
            filename = f"{date_str}.tif"

            # If we already have the local file, skip
            if filename in local_images:
                print(f"[INFO] Image for date {date_str} is already downloaded locally.")
                continue

            # If it's not local, check if it's already on Drive (main file or possibly tiled)
            if self._file_exists_in_drive(date_str, filename, drive_files_dict):
                # If found on Drive, download it immediately (synchronously)
                print(f"[INFO] File for date {date_str} already in Drive. Downloading now...")
                self._download_existing_from_drive(date_str, filename, drive_files_dict)
            else:
                # If not on Drive, create a new Earth Engine export task
                print(f"[INFO] Creating Earth Engine export task for image date: {date_str}")
                image = collection.filterDate(date_str).first()
                task_config = {
                    'image': image,
                    'description': f"Export_{date_str}",
                    'folder': self.drive_folder_name,
                    'fileNamePrefix': date_str,
                    'region': image.geometry(),
                    'fileFormat': 'GeoTIFF',
                    'maxPixels': 1e13,
                    'scale': 0.5
                }
                task = ee.batch.Export.image.toDrive(**task_config)
                task.start()
                export_tasks.append((date_str, filename, task))

        return export_tasks

    # -------------------------------------------------------------------------
    # FEATURE FILE DOWNLOAD
    # -------------------------------------------------------------------------
    def _download_new_feature_files(self, local_features):
        """
        Downloads new feature GeoJSON files from Earth Engine for each date
        that doesn't already exist locally.
        """
        crowns = ee.FeatureCollection(self.featureLocation)
        # Distinct dates from the 'date' property
        all_dates = crowns.aggregate_array('date').distinct().sort().getInfo()

        for crown_date in all_dates:
            features_filename = f"{crown_date}.geojson"
            if features_filename not in local_features:
                print(f"[INFO] Downloading new features for date {crown_date}")
                filtered_crowns = crowns.filter(ee.Filter.eq('date', crown_date))
                try:
                    fc_info = filtered_crowns.getInfo()
                    local_path = os.path.join(self.features_folder, features_filename)
                    with open(local_path, 'w', encoding='utf-8') as f:
                        json.dump(fc_info, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"[ERROR] Failed to download features for {crown_date}. Error: {e}")
            else:
                print(f"[INFO] Feature file {features_filename} already exists locally.")

    # -------------------------------------------------------------------------
    # MONITOR AND DOWNLOAD
    # -------------------------------------------------------------------------
    def _monitor_and_download(self, export_tasks):
        """
        Polls Earth Engine tasks until each completes (or fails).
        As soon as a task finishes, we download its result from Google Drive.
        We do this in parallel for each task, if desired.
        """
        if not export_tasks:
            print("[INFO] No new images to export. Skipping Drive download/polling.")
            return

        print("[INFO] Monitoring export tasks and downloading as they complete...")

        # We'll keep track of tasks that are still running
        tasks_remaining = set(export_tasks)

        # We'll use a thread pool for parallel downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as download_executor:
            while tasks_remaining:
                # We must iterate over a copy of tasks_remaining, so we don't modify
                # the set while iterating over it.
                for (date_str, filename, ee_task) in list(tasks_remaining):
                    status = ee_task.status().get('state', 'UNKNOWN')
                    if status == 'COMPLETED':
                        # Submit a separate task to download in parallel
                        download_executor.submit(self._download_exported_file_from_drive, date_str, filename)
                        # Remove from the set of tasks to monitor
                        tasks_remaining.remove((date_str, filename, ee_task))
                    elif status in ['FAILED', 'CANCELLED']:
                        print(f"[WARNING] Task for {date_str} has status {status}. Removing from queue.")
                        tasks_remaining.remove((date_str, filename, ee_task))
                # If there are still tasks left, sleep before the next polling
                if tasks_remaining:
                    time.sleep(self.poll_interval)

        print("[INFO] All Earth Engine export tasks have finished processing.")

    # -------------------------------------------------------------------------
    # DRIVE-RELATED HELPERS
    # -------------------------------------------------------------------------
    def _file_exists_in_drive(self, date_str, filename, drive_files_dict):
        """
        Check if a file for this date_str already exists in 'drive_files_dict'.
        This includes either an exact filename match or partial-tile matches.
        """
        # 1) Direct match?
        if filename in drive_files_dict:
            return True

        # 2) Check for partial tiles (e.g. 'YYYY-MM-DD.tif-00000')
        for drive_filename in drive_files_dict.keys():
            if drive_filename.startswith(date_str):
                return True

        return False

    def _download_existing_from_drive(self, date_str, filename, drive_files_dict):
        """
        Since the file (or tiles) already exist(s) in Drive, download them immediately.
        """
        # 1) If there's a direct match, download it
        if filename in drive_files_dict:
            drive_file = drive_files_dict[filename]
            self._download_file(drive_file, filename)
        else:
            # Possibly multiple tiles
            matching_tiles = [
                f_obj for (f_title, f_obj) in drive_files_dict.items()
                if f_title.startswith(date_str)
            ]
            if not matching_tiles:
                print(f"[WARNING] _download_existing_from_drive: No Drive files found for date {date_str}.")
                return

            # Download each tile
            for tile_file in matching_tiles:
                tile_title = tile_file['title']  # e.g. "YYYY-MM-DD.tif-00000"
                local_tile_name = tile_title.replace('.tif-', '_tile-')
                self._download_file(tile_file, local_tile_name)

    def _download_exported_file_from_drive(self, date_str, filename):
        """
        Download the exported file for a single (date_str, filename) from Drive.
        (Used once an Earth Engine export task completes.)
        """
        # Query all files in EarthEngineExports folder
        query = f"'{self.drive_folder_id}' in parents and trashed=false"
        file_list = self.drive.ListFile({'q': query}).GetList()
        drive_files = {f['title']: f for f in file_list}

        # If there's a direct match, download that file
        if filename in drive_files:
            self._download_file(drive_files[filename], filename)
        else:
            # Possibly multiple tiles (e.g. "YYYY-MM-DD.tif-00000", etc.)
            matching_tiles = [
                df for (title, df) in drive_files.items()
                if title.startswith(date_str)
            ]
            if not matching_tiles:
                print(f"  [WARNING] No Drive files found for date {date_str}.")
                return
            # Download each tile
            for tile_file in matching_tiles:
                tile_title = tile_file['title']
                local_tile_name = tile_title.replace('.tif-', '_tile-')
                self._download_file(tile_file, local_tile_name)

    def _download_file(self, drive_file, local_filename):
        """
        Downloads 'drive_file' to local_filename in self.images_folder if not existing.
        """
        local_path = os.path.join(self.images_folder, local_filename)
        if os.path.exists(local_path):
            print(f"  [INFO] Local file {local_filename} already exists. Skipping.")
            return
        print(f"  [INFO] Downloading {local_filename} from Drive...")
        drive_file.GetContentFile(local_path)


# -------------------------------------------------------------------------
# Example usage (local script or Colab)
# -------------------------------------------------------------------------
if __name__ == "__main__":
    tree_manager = TreeDataManager(
        projectName='ee-michaelalexanderbennie',
        imageLocation='projects/ee-vasquezavicente/assets/BCI_50ha',
        featureLocation='projects/ee-vasquezavicente/assets/BCI_50ha_crownmap_timeseries',
        fileStorageLocation='./cache',
        max_threads=30,      # default is 10, can be tweaked
        poll_interval=3     # example: poll every 5 seconds
    )

    # 1) Export & download new images, download new feature files
    tree_manager.updateFileCache()

    # 2) Check available dates
    all_img_dates = tree_manager.listImageTimeStamps()
    all_feat_dates = tree_manager.listFeaturesTimeStates()
    print("[INFO] Available image dates:", all_img_dates)
    print("[INFO] Available feature dates:", all_feat_dates)

    # 3) Render an example Folium map for a given date
    example_img_date_str = '2018-04-04'
    example_feat_date_str = '2018_04_04'
    tree_manager.renderHTMLexample(example_img_date_str, example_feat_date_str, 'map.html')
