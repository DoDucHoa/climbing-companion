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
from bson import ObjectId

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
            return render_template("login.html", error="Wrong email or password!")

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

    # Get full user data from database
    db_service = current_app.config["DB_SERVICE"]

    # Convert string ID back to ObjectId for MongoDB query
    try:
        user = db_service.db["users"].find_one(
            {"_id": ObjectId(session.get("user_id"))}
        )
    except:
        # If conversion fails, clear session and redirect to login
        session.clear()
        return redirect(url_for("auth.login"))

    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    # Get success/error messages from query params
    success_message = request.args.get("success")
    error_message = request.args.get("error")

    return render_template(
        "home.html", user=user, success=success_message, error=error_message
    )


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/update-profile", methods=["POST"])
def update_profile():
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        name = request.form.get("name")
        phone = request.form.get("phone")
        dob = request.form.get("dob")

        # Get database service
        db_service = current_app.config["DB_SERVICE"]

        # Update user in database
        update_data = {
            "name": name,
            "phone": phone,
            "dob": dob,
            "updated_at": datetime.utcnow(),
        }

        db_service.db["users"].update_one(
            {"_id": ObjectId(session.get("user_id"))}, {"$set": update_data}
        )

        # Update session name
        session["user_name"] = name

        return redirect(url_for("auth.home", success="Profile updated successfully!"))
    except Exception as e:
        return redirect(
            url_for("auth.home", error=f"Failed to update profile: {str(e)}")
        )


@auth_bp.route("/register-device", methods=["POST"])
def register_device():
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # Placeholder - just redirect back for now
    serial_number = request.form.get("serial_number")
    return redirect(
        url_for(
            "auth.home",
            success=f"Device registration feature coming soon! (Serial: {serial_number})",
        )
    )


@auth_bp.route("/add-emergency-contact", methods=["POST"])
def add_emergency_contact():
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # Placeholder - just redirect back for now
    contact_name = request.form.get("contact_name")
    return redirect(
        url_for(
            "auth.home",
            success=f"Emergency contact feature coming soon! (Contact: {contact_name})",
        )
    )
