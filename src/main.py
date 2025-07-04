import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui_123456789'  # Importante para sessões
app.template_folder = 'templates'
app.static_folder = 'static'

from views import *

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8000)
