from flask import Flask
from flask_session import Session

from blueprints.API import api_bp
from  blueprints.testing import testing_bp
from  blueprints.Data import data_bp

app = Flask(__name__)
Session(app)
app.secret_key = 'bdde50015bf5581fabb62fb820cb2aac2d3002fe4b169092c885c4b8ed72dc04'

app.register_blueprint(testing_bp)
app.register_blueprint(api_bp)
app.register_blueprint(data_bp)



if __name__ == '__main__':
    app.run(debug=True)
