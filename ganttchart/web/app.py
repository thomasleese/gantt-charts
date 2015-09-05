from flask import Flask, render_template


app = Flask('ganttchart.web')


@app.route('/')
def home():
    return render_template('home.html')
