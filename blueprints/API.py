from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, send_from_directory


api_bp=Blueprint("api", __name__, url_prefix="/api")

@api_bp.route('/')
def get_languages():
    return jsonify({"API": "Blueprint"})

