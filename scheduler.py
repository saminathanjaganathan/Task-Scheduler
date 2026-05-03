"""APScheduler integration for running scheduled tasks."""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, date, timedelta
import json
from executor import execute_script

scheduler = BackgroundScheduler()


def run_scheduled_task(app, task_id):
    """Execute a scheduled task and log results."""
    with app.app_context():
        from models import db, Task, ExecutionLog
        from notifier import send_notification

        task = Task.query.get(task_id)
        if not task or not task.script_code:
            return

        log = ExecutionLog(task_id=task.id, started_at=datetime.utcnow())

        # Parse variables
        variables = None
        if task.variables:
            try:
                var_list = json.loads(task.variables)
                variables = {v["name"]: v["value"] for v in var_list if v.get("name")}
            except (json.JSONDecodeError, KeyError):
                pass

        # Build db_config for SQL tasks
        db_config = None
        if task.script_type == "sql" and task.sql_type:
            db_config = {
                "sql_type": task.sql_type,
                "server": task.db_server or "localhost",
                "port": task.db_port,
                "database": task.db_name or "",
                "username": task.db_username or "",
                "password": task.db_password or "",
                "win_auth": task.db_win_auth or False,
            }

        status, output, error = execute_script(task.script_code, task.script_type, variables=variables, db_config=db_config)

        log.finished_at = datetime.utcnow()
        log.status = status
        log.output = output
        log.error = error

        task.last_run_at = log.finished_at
        task.last_run_status = status
        task.last_run_output = output if status == "success" else error

        db.session.add(log)
        db.session.commit()

        # Send email notification if configured
        if task.notify_email:
            try:
                send_notification(task.notify_email, task.title, status, output, error)
            except Exception as e:
                app.logger.error(f"Email notification failed for task {task.id}: {e}")


def init_scheduler(app):
    """Initialize the scheduler and load existing scheduled tasks."""
    if scheduler.running:
        return

    scheduler.start()
    _load_scheduled_tasks(app)


def _load_scheduled_tasks(app):
    """Load all active scheduled tasks from the database."""
    with app.app_context():
        from models import Task

        tasks = Task.query.filter(
            Task.schedule_type.in_(["daily", "weekly", "custom"]),
            Task.script_code.isnot(None),
            Task.status != "completed",
        ).all()

        for task in tasks:
            schedule_task(app, task)


def schedule_task(app, task):
    """Add or update a task's schedule in APScheduler."""
    job_id = f"task_{task.id}"

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not task.script_code or task.status == "completed":
        return

    hour = task.scheduled_time.hour if task.scheduled_time else 0
    minute = task.scheduled_time.minute if task.scheduled_time else 0

    # Build start/end datetime boundaries
    start_date = datetime.combine(task.scheduled_date, task.scheduled_time) if task.scheduled_time else datetime.combine(task.scheduled_date, datetime.min.time())
    end_date = None
    if task.end_date:
        end_date = datetime.combine(task.end_date, task.end_time) if task.end_time else datetime.combine(task.end_date, datetime.max.time().replace(microsecond=0))

    if task.schedule_type == "daily":
        scheduler.add_job(
            run_scheduled_task,
            "cron",
            id=job_id,
            hour=hour,
            minute=minute,
            start_date=start_date,
            end_date=end_date,
            args=[app, task.id],
            replace_existing=True,
        )
    elif task.schedule_type == "weekly":
        day_of_week = task.scheduled_date.strftime("%a").lower()[:3]
        scheduler.add_job(
            run_scheduled_task,
            "cron",
            id=job_id,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            start_date=start_date,
            end_date=end_date,
            args=[app, task.id],
            replace_existing=True,
        )
    elif task.schedule_type == "custom" and task.custom_interval_value:
        unit = task.custom_interval_unit or "hours"
        interval_kwargs = {unit: task.custom_interval_value}
        scheduler.add_job(
            run_scheduled_task,
            "interval",
            id=job_id,
            start_date=start_date,
            end_date=end_date,
            args=[app, task.id],
            replace_existing=True,
            **interval_kwargs,
        )


def remove_task_schedule(task_id):
    """Remove a task from the scheduler."""
    job_id = f"task_{task_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
