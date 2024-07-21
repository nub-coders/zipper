from flask import Flask, session, request, render_template, redirect, url_for, send_file

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'


@app.route('/')
def index():
    return 'index.html'


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)
