from flask import Flask
from routes import app
# from auth import google

app.secret_key = b'\x95\x1f\x89\x9d\xf0\x19\xd3\xd0\xdc\x81\x02\x9e\x91\xaf\xb9\x07\x8c\xef\x17\xa4\x11\xcf'

if __name__ == '__main__':
    app.run(debug=True)
