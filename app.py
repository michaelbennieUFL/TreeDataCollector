from flask import Flask, render_template, request
from flask_caching import Cache
from flask_session import Session

from extension import cache  # Import the shared cache instance
from blueprints.API import api_bp
from blueprints.testing import testing_bp
from blueprints.Data import data_bp

app = Flask(__name__)
app.secret_key = 'bdde50015bf5581fabb62fb820cb2aac2d3002fe4b169092c885c4b8ed72dc04'

# Initialize Session
Session(app)

# Initialize Cache with the app
cache.init_app(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 3600})

# Register the blueprints
app.register_blueprint(testing_bp)
app.register_blueprint(api_bp)
app.register_blueprint(data_bp)




@app.route('/')
def index():
    return render_template('mainpage.html')


if __name__ == '__main__':
    app.run(debug=True)
