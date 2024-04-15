import os
import subprocess
import shutil
import requests
import hashlib
from flask import Flask, send_file
ggg=os.getcwd()
app = Flask(__name__)
subprocess.Popen(['ssh', '-R', 'https://justtesting-5055c1719887.herokuapp.com:8080:localhost:8080', 'serveo.net'])
@app.route("/")
def home():
    return "nothing here"
@app.route("/<file_hash>")
def download_zip(file_hash):
    # Check file hash of all files in f"{ggg}/data directory
    destination_dir = os.path.join(ggg, "userspace")
    for file_name in os.listdir(destination_dir):
        file_path = os.path.join(destination_dir, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() == file_hash:
                    return send_file(
                        file_path,
                        as_attachment=True)
    return "File not found"

if __name__ == "__main__":
    app.run()
