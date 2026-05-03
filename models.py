from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    script_type = db.Column(db.String(10), default="python")  # python, bat, sql
    script_code = db.Column(db.Text, nullable=True)  # Code to execute
    variables = db.Column(db.Text, nullable=True)  # JSON: [{"name": "...", "value": "..."}]
    # SQL connection fields
    sql_type = db.Column(db.String(20), nullable=True)  # mssql, postgres, mysql, sqlite
    db_server = db.Column(db.String(200), nullable=True)
    db_port = db.Column(db.Integer, nullable=True)
    db_name = db.Column(db.String(200), nullable=True)
    db_username = db.Column(db.String(200), nullable=True)
    db_password = db.Column(db.String(200), nullable=True)
    db_win_auth = db.Column(db.Boolean, default=False)  # Windows Authentication for MSSQL
    schedule_type = db.Column(db.String(20), default="once")  # once, daily, weekly, custom
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.Time, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    custom_interval_value = db.Column(db.Integer, nullable=True)  # e.g. 30
    custom_interval_unit = db.Column(db.String(10), nullable=True)  # minutes, hours, days
    priority = db.Column(db.String(10), default="medium")  # low, medium, high
    status = db.Column(db.String(20), default="pending")  # pending, in_progress, completed
    notify_email = db.Column(db.String(200), nullable=True)  # email for notifications
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_run_status = db.Column(db.String(10), nullable=True)  # success, failure
    last_run_output = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Task {self.title}>"


class ExecutionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(10))  # success, failure
    output = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)

    task = db.relationship("Task", backref=db.backref("executions", lazy="dynamic", order_by="ExecutionLog.started_at.desc()"))
