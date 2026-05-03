from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
import json
from datetime import datetime
from models import db, Task, ExecutionLog
from forms import TaskForm
from executor import execute_script, test_db_connection

main_bp = Blueprint("main", __name__)


def _parse_form_variables():
    """Parse dynamic variable rows from form submission."""
    variables = []
    names = request.form.getlist("var_name[]")
    values = request.form.getlist("var_value[]")
    for n, v in zip(names, values):
        n = n.strip()
        if n:
            variables.append({"name": n, "value": v})
    return json.dumps(variables) if variables else None


def _get_variables_dict(variables_json):
    """Convert stored JSON variables to a dict for executor."""
    if not variables_json:
        return None
    try:
        var_list = json.loads(variables_json)
        return {v["name"]: v["value"] for v in var_list if v.get("name")}
    except (json.JSONDecodeError, KeyError):
        return None


def _get_db_config(task):
    """Build db_config dict from task's SQL connection fields."""
    if task.script_type != "sql" or not task.sql_type:
        return None
    return {
        "sql_type": task.sql_type,
        "server": task.db_server or "localhost",
        "port": task.db_port,
        "database": task.db_name or "",
        "username": task.db_username or "",
        "password": task.db_password or "",
        "win_auth": task.db_win_auth or False,
    }


@main_bp.route("/")
def index():
    sort_by = request.args.get("sort", "scheduled_date")
    filter_status = request.args.get("status", "all")

    query = Task.query
    if filter_status != "all":
        query = query.filter_by(status=filter_status)

    if sort_by == "priority":
        priority_order = db.case(
            (Task.priority == "high", 1),
            (Task.priority == "medium", 2),
            (Task.priority == "low", 3),
        )
        query = query.order_by(priority_order)
    else:
        query = query.order_by(Task.scheduled_date, Task.scheduled_time)

    tasks = query.all()
    return render_template("index.html", tasks=tasks, filter_status=filter_status, sort_by=sort_by)


@main_bp.route("/task/new", methods=["GET", "POST"])
def create_task():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(
            title=form.title.data,
            description=form.description.data,
            script_type=form.script_type.data,
            script_code=form.script_code.data,
            schedule_type=form.schedule_type.data,
            scheduled_date=form.scheduled_date.data,
            scheduled_time=form.scheduled_time.data,
            end_date=form.end_date.data,
            end_time=form.end_time.data,
            custom_interval_value=form.custom_interval_value.data if form.schedule_type.data == 'custom' else None,
            custom_interval_unit=form.custom_interval_unit.data if form.schedule_type.data == 'custom' else None,
            priority=form.priority.data,
            status=form.status.data,
            notify_email=form.notify_email.data or None,
            variables=_parse_form_variables(),
            sql_type=request.form.get("sql_type") if form.script_type.data == "sql" else None,
            db_server=request.form.get("db_server") if form.script_type.data == "sql" else None,
            db_port=int(request.form.get("db_port") or 0) or None if form.script_type.data == "sql" else None,
            db_name=request.form.get("db_name") if form.script_type.data == "sql" else None,
            db_username=request.form.get("db_username") if form.script_type.data == "sql" else None,
            db_password=request.form.get("db_password") if form.script_type.data == "sql" else None,
            db_win_auth=(request.form.get("db_win_auth") == "on") if form.script_type.data == "sql" else False,
        )
        db.session.add(task)
        db.session.commit()

        # Register with scheduler if recurring
        if task.schedule_type in ("daily", "weekly", "custom") and task.script_code:
            from flask import current_app
            from scheduler import schedule_task
            schedule_task(current_app._get_current_object(), task)

        flash("Task created successfully!", "success")
        return redirect(url_for("main.index"))
    return render_template("task_form.html", form=form, title="New Task")


@main_bp.route("/task/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data
        task.script_type = form.script_type.data
        task.script_code = form.script_code.data
        task.schedule_type = form.schedule_type.data
        task.scheduled_date = form.scheduled_date.data
        task.scheduled_time = form.scheduled_time.data
        task.end_date = form.end_date.data
        task.end_time = form.end_time.data
        task.custom_interval_value = form.custom_interval_value.data if form.schedule_type.data == 'custom' else None
        task.custom_interval_unit = form.custom_interval_unit.data if form.schedule_type.data == 'custom' else None
        task.priority = form.priority.data
        task.status = form.status.data
        task.notify_email = form.notify_email.data or None
        task.variables = _parse_form_variables()
        if form.script_type.data == "sql":
            task.sql_type = request.form.get("sql_type")
            task.db_server = request.form.get("db_server")
            task.db_port = int(request.form.get("db_port") or 0) or None
            task.db_name = request.form.get("db_name")
            task.db_username = request.form.get("db_username")
            task.db_password = request.form.get("db_password")
            task.db_win_auth = (request.form.get("db_win_auth") == "on")
        else:
            task.sql_type = None
            task.db_server = None
            task.db_port = None
            task.db_name = None
            task.db_username = None
            task.db_password = None
            task.db_win_auth = False
        db.session.commit()

        # Update scheduler
        from flask import current_app
        from scheduler import schedule_task, remove_task_schedule
        if task.schedule_type in ("daily", "weekly", "custom") and task.script_code:
            schedule_task(current_app._get_current_object(), task)
        else:
            remove_task_schedule(task.id)

        flash("Task updated successfully!", "success")
        return redirect(url_for("main.index"))

    existing_vars = []
    if task.variables:
        try:
            existing_vars = json.loads(task.variables)
        except json.JSONDecodeError:
            pass
    return render_template("task_form.html", form=form, title="Edit Task", existing_vars=existing_vars, task=task)


@main_bp.route("/task/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    from scheduler import remove_task_schedule
    remove_task_schedule(task.id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("main.index"))


@main_bp.route("/task/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.status == "completed":
        task.status = "pending"
    else:
        task.status = "completed"
    db.session.commit()
    return redirect(url_for("main.index"))


@main_bp.route("/task/<int:task_id>/run", methods=["POST"])
def run_task(task_id):
    """Manually execute a task's Python script and show results."""
    task = Task.query.get_or_404(task_id)

    if not task.script_code or not task.script_code.strip():
        flash("No script code to execute.", "info")
        return redirect(url_for("main.index"))

    variables = _get_variables_dict(task.variables)
    db_config = _get_db_config(task)
    status, output, error = execute_script(task.script_code, task.script_type, variables=variables, db_config=db_config)

    log = ExecutionLog(
        task_id=task.id,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        status=status,
        output=output,
        error=error,
    )
    db.session.add(log)

    task.last_run_at = log.finished_at
    task.last_run_status = status
    task.last_run_output = output if status == "success" else error
    db.session.commit()

    # Send email if configured
    if task.notify_email:
        try:
            from notifier import send_notification
            send_notification(task.notify_email, task.title, status, output, error)
        except Exception:
            pass

    if status == "success":
        flash("Script executed successfully!", "success")
    else:
        flash("Script execution failed.", "danger")

    return redirect(url_for("main.task_result", task_id=task.id))


@main_bp.route("/task/<int:task_id>/result")
def task_result(task_id):
    """Show the execution result of a task."""
    task = Task.query.get_or_404(task_id)
    logs = ExecutionLog.query.filter_by(task_id=task.id).order_by(
        ExecutionLog.started_at.desc()
    ).limit(20).all()
    return render_template("task_result.html", task=task, logs=logs)


@main_bp.route("/api/test-script", methods=["POST"])
def test_script():
    """Test-run a script from the task form and return results as JSON."""
    data = request.get_json()
    if not data or not data.get("script_code", "").strip():
        return jsonify(status="failure", output="", error="No script code provided."), 400

    script_code = data["script_code"]
    script_type = data.get("script_type", "python")

    # Parse variables from test request
    variables = None
    raw_vars = data.get("variables", [])
    if raw_vars:
        variables = {v["name"]: v["value"] for v in raw_vars if v.get("name")}

    # Parse db_config from test request
    db_config = None
    if script_type == "sql" and data.get("sql_type"):
        db_config = {
            "sql_type": data.get("sql_type", "sqlite"),
            "server": data.get("db_server", "localhost"),
            "port": data.get("db_port"),
            "database": data.get("db_name", ""),
            "username": data.get("db_username", ""),
            "password": data.get("db_password", ""),
            "win_auth": data.get("db_win_auth", False),
        }

    status, output, error = execute_script(script_code, script_type, timeout=30, variables=variables, db_config=db_config)
    return jsonify(status=status, output=output, error=error)


@main_bp.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    """Test a database connection and return results as JSON."""
    data = request.get_json()
    if not data or not data.get("sql_type"):
        return jsonify(status="failure", message="No SQL type specified."), 400

    db_config = {
        "sql_type": data.get("sql_type", "sqlite"),
        "server": data.get("db_server", "localhost"),
        "port": data.get("db_port"),
        "database": data.get("db_name", ""),
        "username": data.get("db_username", ""),
        "password": data.get("db_password", ""),
        "win_auth": data.get("db_win_auth", False),
    }

    status, message = test_db_connection(db_config)
    return jsonify(status=status, message=message)


@main_bp.route("/api/task/<int:task_id>/run", methods=["POST"])
def api_run_task(task_id):
    """Run a task and return results as JSON for inline display."""
    task = Task.query.get_or_404(task_id)

    if not task.script_code or not task.script_code.strip():
        return jsonify(status="failure", output="", error="No script code to execute."), 400

    variables = _get_variables_dict(task.variables)
    db_config = _get_db_config(task)
    status, output, error = execute_script(task.script_code, task.script_type, variables=variables, db_config=db_config)

    log = ExecutionLog(
        task_id=task.id,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        status=status,
        output=output,
        error=error,
    )
    db.session.add(log)

    task.last_run_at = log.finished_at
    task.last_run_status = status
    task.last_run_output = output if status == "success" else error
    db.session.commit()

    if task.notify_email:
        try:
            from notifier import send_notification
            send_notification(task.notify_email, task.title, status, output, error)
        except Exception:
            pass

    return jsonify(status=status, output=output, error=error)
