from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, send_from_directory
from DataManager.treeData import TreeDataManager
import os
api_bp=Blueprint("api", __name__, url_prefix="/api")

dataManager =TreeDataManager(
        projectName='ee-michaelalexanderbennie',
        imageLocation='projects/ee-vasquezavicente/assets/BCI_50ha',
        featureLocation='projects/ee-vasquezavicente/assets/BCI_50ha_crownmap_timeseries',
        fileStorageLocation='./DataManager/cache',
        max_threads=30,      # default is 10, can be tweaked
        poll_interval=3,     # example: poll every 5 seconds
        working_directory="./DataManager/"
    )

@api_bp.route('/')
def get_languages():
    data={
        "image_files"  :dataManager.listImageTimeStamps(),
        "feature_files":dataManager.listFeaturesTimeStates()
    }
    return jsonify(data)

