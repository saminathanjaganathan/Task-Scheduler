import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "mssql+pyodbc://ODSDBETDEV1/TEST?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes&TrustServerCertificate=yes"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email settings - Outlook/Office 365
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.office365.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "saminathan.jaganathan@williamoneilindia.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "Sami@apr@9869")
    MAIL_FROM = os.environ.get("MAIL_FROM", "saminathan.jaganathan@williamoneilindia.com")
