from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, send_from_directory


testing_bp=Blueprint("lp", __name__, url_prefix="/testing")

@testing_bp.route('/hello_world')
def get_languages():
    return jsonify({"Hello": "World"})