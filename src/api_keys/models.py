from datetime import datetime
from core.database import db

class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    company = db.relationship('Company', backref='api_keys_main')
    key = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='active')  # active, inactive, revoked
    active = db.Column(db.Boolean, default=True)
    subscription_plan = db.Column(db.String(50), nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ApiKey {self.id} for company {self.company_id}>"