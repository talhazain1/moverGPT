class Config:
    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT configuration
    JWT_SECRET_KEY = 'your-secret-key'  # Change this in production
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    
    # Flask configuration
    SECRET_KEY = 'your-secret-key'  # Change this in production
    DEBUG = True 