from flask import Flask


app = Flask('ganttchart.web')


@app.route('/')
def home():
    return 'Hello, world.'
