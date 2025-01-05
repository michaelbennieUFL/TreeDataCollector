from flask import Flask
from flask_session import Session
from  blueprints.testing import testing_bp

app = Flask(__name__)
Session(app)
app.secret_key = 'bdde50015bf5581fabb62fb820cb2aac2d3002fe4b169092c885c4b8ed72dc04'

app.register_blueprint(testing_bp)




if __name__ == '__main__':
    app.run(debug=True)
