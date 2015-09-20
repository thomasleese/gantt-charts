from argparse import ArgumentParser

from ganttcharts.web import app


parser = ArgumentParser(description='Web server useful for testing.')
parser.add_argument('--host', default='0.0.0.0')
parser.add_argument('--port', type=int, default=5000)
args = parser.parse_args()

app.run(host=args.host, port=args.port, debug=True)
