from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    session,
    current_app,
)
from datetime import datetime

# Create blueprint for authentication
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Get database service from app config
        db_service = current_app.config["DB_SERVICE"]

        # Find user in database
        user = db_service.db["users"].find_one({"email": email, "password": password})

        if user:
            # Store user info in session
            session["user_id"] = str(user["_id"])
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            return redirect(url_for("auth.home"))
        else:
            return render_template(
                "login.html", error="Wrong email or password!"
            )

    success_message = request.args.get("success")
    return render_template("login.html", success=success_message)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Get database service from app config
        db_service = current_app.config["DB_SERVICE"]

        # Check if email already exists
        existing_user = db_service.db["users"].find_one({"email": email})
        if existing_user:
            return render_template("register.html", error="Email has been used!")

        # Create new user document
        user_doc = {
            "name": name,
            "email": email,
            "password": password,  # No encryption for demo purposes
            "created_at": datetime.utcnow(),
        }

        # Insert user into database
        db_service.db["users"].insert_one(user_doc)

        # Redirect to login with success message
        return redirect(
            url_for("auth.login", success="Register success! Please login.")
        )

    return render_template("register.html")


@auth_bp.route("/home")
def home():
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # Create user object from session
    user = {"name": session.get("user_name"), "email": session.get("user_email")}

    return render_template("home.html", user=user)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
