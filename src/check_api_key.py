from admin.models import ApiKey
from core.database import db, init_db
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://myuser@localhost:5432/chatbotdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
init_db(app)

with app.app_context():
    api_keys = ApiKey.query.all()
    print(f"Found {len(api_keys)} API keys:")
    for k in api_keys:
        print(f"ID: {k.id}, Key: {k.key[:8]}..., Company: {k.company_id}, Status: {k.status}")
