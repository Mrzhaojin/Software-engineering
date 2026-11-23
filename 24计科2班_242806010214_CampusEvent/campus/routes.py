from functools import wraps
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from .db import get_db
from .repositories import (StudentRepository, ActivityRepository,
                           RegistrationRepository, MessageRepository)
from .policies import PolicyRegistry
from .capacity import CapacityChecker
from .events import RegistrationEventPublisher, MessageObserver
from .services import ActivityService, RegistrationService, MessageService
from .errors import DomainError

bp = Blueprint("main", __name__)

ACCOUNTS = {
    "admin": {"password": "admin123", "role": "admin", "name": "管理员", "student_id": None},
    "S001": {"password": "123456", "role": "student", "name": "张三", "student_id": "S001"},
    "S002": {"password": "123456", "role": "student", "name": "李四", "student_id": "S002"},
    "S003": {"password": "123456", "role": "student", "name": "王五", "student_id": "S003"},
}


def _services():
    db = get_db()
    student_repo = StudentRepository(db)
    activity_repo = ActivityRepository(db)
    registration_repo = RegistrationRepository(db)
    message_repo = MessageRepository(db)
    publisher = RegistrationEventPublisher([MessageObserver(message_repo)])
    capacity = CapacityChecker(registration_repo)
    return {
        "db": db,
        "student_repo": student_repo,
        "activity_repo": activity_repo,
        "registration_repo": registration_repo,
        "message_repo": message_repo,
        "capacity": capacity,
        "activity": ActivityService(activity_repo, db),
        "registration": RegistrationService(
            student_repo, activity_repo, registration_repo,
            PolicyRegistry.default(), capacity, publisher, db,
        ),
        "message": MessageService(message_repo, db),
    }


def _activity_view(activity, reg_repo):
    data = dict(activity)
    data["remaining"] = max(0, data["capacity"] - reg_repo.count_approved(data["activity_id"]))
    return data


@bp.before_app_request
def load_logged_in_user():
    username = session.get("username")
    account = ACCOUNTS.get(username) if username else None
    g.user = None
    if account:
        g.user = {
            "username": username,
            "role": account["role"],
            "name": account["name"],
            "student_id": account["student_id"],
        }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("main.login"))
        if g.user["role"] != "admin":
            flash("需要管理员权限", "error")
            return redirect(url_for("main.activities"))
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("main.login"))
        if g.user["role"] != "student":
            flash("需要学生账号", "error")
            return redirect(url_for("main.activities"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("main.activities"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        account = ACCOUNTS.get(username)
        if account is None or account["password"] != password:
            flash("账号或密码错误", "error")
        else:
            session.clear()
            session["username"] = username
            return redirect(url_for("main.activities"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/")
def index():
    return redirect(url_for("main.activities"))


@bp.route("/activities")
@login_required
def activities():
    svc = _services()
    name = request.args.get("name", "").strip()
    rows = svc["activity"].list(name or None)
    items = [_activity_view(row, svc["registration_repo"]) for row in rows]
    return render_template("activities.html", activities=items, name=name)


@bp.route("/activities/<activity_id>")
@login_required
def activity_detail(activity_id):
    svc = _services()
    try:
        activity = svc["activity"].get(activity_id)
    except DomainError as e:
        flash(str(e), "error")
        return redirect(url_for("main.activities"))
    item = _activity_view(activity, svc["registration_repo"])
    my_registration = None
    if g.user["role"] == "student":
        my_registration = svc["registration_repo"].find_active(g.user["student_id"], activity_id)
    return render_template("activity_detail.html", activity=item, my_registration=my_registration)


@bp.route("/activities/new", methods=("GET", "POST"))
@admin_required
def activity_new():
    if request.method == "POST":
        svc = _services()
        try:
            activity = svc["activity"].create(request.form.to_dict())
        except DomainError as e:
            flash(str(e), "error")
            return render_template("activity_form.html", activity=request.form.to_dict(), is_new=True)
        flash("活动创建成功", "success")
        return redirect(url_for("main.activity_detail", activity_id=activity["activity_id"]))
    return render_template("activity_form.html", activity={"policy_type": "direct", "capacity": 30}, is_new=True)


@bp.route("/activities/<activity_id>/edit", methods=("GET", "POST"))
@admin_required
def activity_edit(activity_id):
    svc = _services()
    try:
        activity = svc["activity"].get(activity_id)
    except DomainError as e:
        flash(str(e), "error")
        return redirect(url_for("main.activities"))
    if request.method == "POST":
        try:
            svc["activity"].update(activity_id, request.form.to_dict())
        except DomainError as e:
            flash(str(e), "error")
            return render_template("activity_form.html", activity=request.form.to_dict(), is_new=False)
        flash("活动修改成功", "success")
        return redirect(url_for("main.activity_detail", activity_id=activity_id))
    return render_template("activity_form.html", activity=dict(activity), is_new=False)


@bp.route("/activities/<activity_id>/delete", methods=("POST",))
@admin_required
def activity_delete(activity_id):
    svc = _services()
    try:
        svc["activity"].soft_delete(activity_id)
        flash("活动已下线（软删除），报名与消息保留", "success")
    except DomainError as e:
        flash(str(e), "error")
    return redirect(url_for("main.activities"))


@bp.route("/activities/<activity_id>/register", methods=("POST",))
@student_required
def register(activity_id):
    svc = _services()
    try:
        registration = svc["registration"].submit(g.user["student_id"], activity_id)
        if registration["status"] == "APPROVED":
            flash("报名成功，已通过", "success")
        else:
            flash("报名已提交，等待管理员审核", "success")
    except DomainError as e:
        flash(str(e), "error")
    return redirect(url_for("main.activity_detail", activity_id=activity_id))


@bp.route("/my/registrations")
@student_required
def my_registrations():
    svc = _services()
    rows = svc["registration_repo"].list_by_student(g.user["student_id"])
    return render_template("my_registrations.html", registrations=rows)


@bp.route("/registrations/<registration_id>/cancel", methods=("POST",))
@student_required
def cancel_registration(registration_id):
    svc = _services()
    try:
        svc["registration"].cancel(registration_id, g.user["student_id"])
        flash("报名已取消", "success")
    except DomainError as e:
        flash(str(e), "error")
    return redirect(url_for("main.my_registrations"))


@bp.route("/admin/pending")
@admin_required
def pending():
    svc = _services()
    rows = svc["registration_repo"].list_pending()
    items = []
    for row in rows:
        data = dict(row)
        data["remaining"] = max(0, data["activity_capacity"] - svc["registration_repo"].count_approved(data["activity_id"]))
        items.append(data)
    return render_template("pending.html", registrations=items)


@bp.route("/admin/registrations/<registration_id>/approve", methods=("POST",))
@admin_required
def approve(registration_id):
    svc = _services()
    try:
        svc["registration"].approve(registration_id, g.user["username"])
        flash("已批准", "success")
    except DomainError as e:
        flash(str(e), "error")
    return redirect(url_for("main.pending"))


@bp.route("/admin/registrations/<registration_id>/reject", methods=("POST",))
@admin_required
def reject(registration_id):
    svc = _services()
    try:
        svc["registration"].reject(registration_id, g.user["username"])
        flash("已拒绝", "success")
    except DomainError as e:
        flash(str(e), "error")
    return redirect(url_for("main.pending"))


@bp.route("/admin/reviewed")
@admin_required
def reviewed():
    svc = _services()
    rows = svc["registration_repo"].list_reviewed()
    return render_template("reviewed.html", registrations=rows)


@bp.route("/admin/stats")
@admin_required
def stats():
    svc = _services()
    activities_rows = svc["activity"].list()
    activities = [dict(row) for row in activities_rows]
    selected_id = request.args.get("activity_id") or (activities[0]["activity_id"] if activities else None)
    selected = None
    if selected_id:
        for item in activities:
            if item["activity_id"] == selected_id:
                selected = item
                break
    approved = svc["registration_repo"].count_approved(selected_id) if selected else 0
    pending_count = svc["registration_repo"].count_pending(selected_id) if selected else 0
    remaining = max(0, selected["capacity"] - approved) if selected else 0
    participants = svc["registration_repo"].list_by_activity(selected_id) if selected else []
    return render_template("stats.html", activities=activities, selected=selected,
                           approved=approved, pending_count=pending_count, remaining=remaining,
                           participants=participants)


@bp.route("/messages")
@student_required
def messages():
    svc = _services()
    rows = svc["message"].list(g.user["student_id"])
    return render_template("messages.html", messages=rows)


@bp.route("/messages/<message_id>/read", methods=("POST",))
@student_required
def read_message(message_id):
    svc = _services()
    try:
        svc["message"].mark_read(message_id, g.user["student_id"])
    except DomainError as e:
        flash(str(e), "error")
    return redirect(url_for("main.messages"))


@bp.app_template_filter("dt")
def format_datetime(value):
    if not value:
        return ""
    return str(value).replace("T", " ")[:16]
