from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateField, TimeField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange


class TaskForm(FlaskForm):
    title = StringField(
        "Title", validators=[DataRequired(), Length(min=1, max=200)]
    )
    description = TextAreaField("Description")
    script_type = SelectField(
        "Script Type",
        choices=[("python", "Python"), ("bat", "Batch / CMD"), ("sql", "SQL")],
        default="python",
    )
    script_code = TextAreaField("Script Code")
    schedule_type = SelectField(
        "Schedule",
        choices=[("once", "Once"), ("daily", "Daily"), ("weekly", "Weekly"), ("custom", "Custom Interval")],
        default="once",
    )
    scheduled_date = DateField("Start Date", validators=[DataRequired()])
    scheduled_time = TimeField("Start Time")
    end_date = DateField("End Date", validators=[Optional()])
    end_time = TimeField("End Time", validators=[Optional()])
    custom_interval_value = IntegerField(
        "Interval Value", validators=[Optional(), NumberRange(min=1, message="Must be at least 1")]
    )
    custom_interval_unit = SelectField(
        "Interval Unit",
        choices=[("minutes", "Minutes"), ("hours", "Hours"), ("days", "Days")],
        default="hours",
    )
    priority = SelectField(
        "Priority",
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
    )
    status = SelectField(
        "Status",
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
        ],
        default="pending",
    )
    notify_email = StringField("Notification Email", validators=[Optional(), Email()])
