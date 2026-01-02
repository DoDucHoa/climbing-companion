from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    session,
    current_app,
    jsonify,
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

        # Find user in database using proper collection name
        user = db_service.db["user_collection"].find_one(
            {"profile.email": email, "data.password": password}
        )

        if user:
            # Store user info in session
            session["user_id"] = user["_id"]
            session["user_name"] = user["profile"]["name"]
            session["user_email"] = user["profile"]["email"]
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

        # Get database service and DR factory from app config
        db_service = current_app.config["DB_SERVICE"]
        user_dr_factory = current_app.config["USER_DR_FACTORY"]

        # Check if email already exists
        existing_users = db_service.query_drs("user", {"profile.email": email})
        if existing_users:
            return render_template("register.html", error="Email has been used!")

        # Create new user using DR Factory pattern
        initial_data = {
            "profile": {
                "name": name,
                "email": email,
            },
            "data": {
                "password": password,  # No encryption for demo purposes
            },
        }

        # Create DR using factory (validates with Pydantic)
        user_dr = user_dr_factory.create_dr("user", initial_data)

        # Save to database using proper method
        db_service.save_dr("user", user_dr)

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

    # Get user from database using proper collection
    try:
        user = db_service.db["user_collection"].find_one(
            {"_id": session.get("user_id")}
        )
    except Exception as e:
        # If query fails, clear session and redirect to login
        print(f"Error fetching user: {e}")
        session.clear()
        return redirect(url_for("auth.login"))

    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    # Get emergency contacts for the user
    emergency_contacts = []
    try:
        emergency_contacts = db_service.query_drs(
            "emergency_contact",
            {"data.user_id": session.get("user_id"), "data.is_active": True},
        )
    except Exception as e:
        print(f"Error fetching emergency contacts: {e}")

    # Get user's devices
    devices = []
    try:
        # Get all pairings for user
        pairing_collection = db_service.db["device_pairing_collection"]
        pairings = list(
            pairing_collection.find(
                {
                    "data.user_id": session.get("user_id"),
                    "data.pairing_status": "active",
                }
            )
        )

        # Get device details
        device_collection = db_service.db["device_collection"]
        for pairing in pairings:
            device_serial = pairing["data"]["device_serial"]
            device = device_collection.find_one({"_id": device_serial})

            if device:
                devices.append(
                    {
                        "_id": device["_id"],
                        "serial_number": device["profile"]["serial_number"],
                        "status": device["data"].get("status", "inactive"),
                        "battery_level": device["data"].get("battery_level", 0),
                        "last_sync_at": device["data"].get("last_sync_at"),
                        "paired_at": pairing["profile"].get("paired_at"),
                    }
                )
    except Exception as e:
        print(f"Error fetching devices: {e}")

    # Get user's climbing sessions
    sessions = []
    try:
        session_collection = db_service.db["climbing_session_collection"]
        sessions = list(
            session_collection.find({"data.user_id": session.get("user_id")}).sort(
                "profile.start_at", -1
            )  # Most recent first
        )
    except Exception as e:
        print(f"Error fetching sessions: {e}")

    # Get success/error messages from query params
    success_message = request.args.get("success")
    error_message = request.args.get("error")

    return render_template(
        "home.html",
        user=user,
        emergency_contacts=emergency_contacts,
        devices=devices,
        sessions=sessions,
        success=success_message,
        error=error_message,
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

        # Convert date string to datetime if provided
        date_of_birth = None
        if dob:
            try:
                date_of_birth = datetime.strptime(dob, "%Y-%m-%d")
            except ValueError:
                pass

        # Update user in database using proper DR structure
        update_data = {
            "profile": {
                "name": name,
            },
        }

        # Only add optional fields if they have values
        if phone:
            update_data["profile"]["phone"] = phone
        if date_of_birth:
            update_data["profile"]["date_of_birth"] = date_of_birth

        db_service.update_dr("user", session.get("user_id"), update_data)

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


@auth_bp.route("/unregister-device/<device_serial>", methods=["POST"])
def unregister_device(device_serial):
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        user_id = session["user_id"]
        db_service = current_app.config["DB_SERVICE"]

        # Find pairing
        pairing_collection = db_service.db["device_pairing_collection"]
        pairing = pairing_collection.find_one(
            {
                "data.device_serial": device_serial,
                "data.user_id": user_id,
                "data.pairing_status": "active",
            }
        )

        if not pairing:
            return redirect(
                url_for("auth.home", error="Device not found or not authorized")
            )

        # Update pairing status to unpaired
        pairing_collection.update_one(
            {"_id": pairing["_id"]},
            {
                "$set": {
                    "data.pairing_status": "unpaired",
                    "data.unpaired_at": datetime.utcnow(),
                    "metadata.updated_at": datetime.utcnow(),
                }
            },
        )

        return redirect(
            url_for("auth.home", success="Device unregistered successfully!")
        )
    except Exception as e:
        return redirect(
            url_for("auth.home", error=f"Failed to unregister device: {str(e)}")
        )


@auth_bp.route("/add-emergency-contact", methods=["POST"])
def add_emergency_contact():
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        # Get form data
        contact_name = request.form.get("contact_name")
        contact_phone = request.form.get("contact_phone")
        contact_email = request.form.get("contact_email", "")
        telegram_id = request.form.get("telegram_id", "")
        relationship_type = request.form.get("relationship_type", "other")
        priority = int(request.form.get("priority", 1))
        notes = request.form.get("notes", "")

        # Validate required fields
        if not contact_name or not contact_phone:
            return redirect(
                url_for("auth.home", error="Contact name and phone are required")
            )

        # Get DRFactory and create emergency contact
        from src.virtualization.digital_replica.dr_factory import DRFactory

        dr_factory = DRFactory("config/emergency_contact_schema.yaml")

        # Build initial data structure
        initial_data = {
            "profile": {
                "name": contact_name,
                "phone": contact_phone,
                "email": contact_email,
                "telegram_chat_id": telegram_id,
            },
            "data": {
                "user_id": session.get("user_id"),
                "relationship_type": relationship_type,
                "priority": priority,
                "is_active": True,
                "notes": notes,
            },
        }

        # Create DR using factory (validates with Pydantic)
        dr_data = dr_factory.create_dr("emergency_contact", initial_data)

        # Save to database
        db_service = current_app.config["DB_SERVICE"]
        contact_id = db_service.save_dr("emergency_contact", dr_data)

        return redirect(
            url_for(
                "auth.home",
                success=f"Emergency contact '{contact_name}' added successfully!",
            )
        )
    except Exception as e:
        return redirect(
            url_for("auth.home", error=f"Failed to add emergency contact: {str(e)}")
        )


@auth_bp.route("/update-emergency-contact/<contact_id>", methods=["POST"])
def update_emergency_contact(contact_id):
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        # Get form data
        contact_name = request.form.get("contact_name")
        contact_phone = request.form.get("contact_phone")
        contact_email = request.form.get("contact_email", "")
        telegram_id = request.form.get("telegram_id", "")
        relationship_type = request.form.get("relationship_type", "other")
        priority = int(request.form.get("priority", 1))
        notes = request.form.get("notes", "")

        # Build update structure
        update_data = {
            "profile": {
                "name": contact_name,
                "phone": contact_phone,
                "email": contact_email,
                "telegram_chat_id": telegram_id,
            },
            "data": {
                "relationship_type": relationship_type,
                "priority": priority,
                "notes": notes,
            },
        }

        # Update in database
        db_service = current_app.config["DB_SERVICE"]
        db_service.update_dr("emergency_contact", contact_id, update_data)

        return redirect(
            url_for("auth.home", success="Emergency contact updated successfully!")
        )
    except Exception as e:
        return redirect(
            url_for("auth.home", error=f"Failed to update emergency contact: {str(e)}")
        )


@auth_bp.route("/delete-emergency-contact/<contact_id>", methods=["POST"])
def delete_emergency_contact(contact_id):
    # Check if user is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        # Verify the contact belongs to the user
        db_service = current_app.config["DB_SERVICE"]
        contact = db_service.get_dr("emergency_contact", contact_id)

        if not contact or contact["data"]["user_id"] != session.get("user_id"):
            return redirect(
                url_for("auth.home", error="Contact not found or unauthorized")
            )

        # Soft delete by setting is_active to False
        update_data = {"data": {"is_active": False}}
        db_service.update_dr("emergency_contact", contact_id, update_data)

        return redirect(
            url_for("auth.home", success="Emergency contact deleted successfully!")
        )
    except Exception as e:
        return redirect(
            url_for("auth.home", error=f"Failed to delete emergency contact: {str(e)}")
        )


@auth_bp.route("/api/session-events/<session_id>")
def get_session_events(session_id):
    """API endpoint to get session events for visualization"""
    # Check if user is logged in
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        db_service = current_app.config["DB_SERVICE"]

        # Verify session belongs to user
        session_collection = db_service.db["climbing_session_collection"]
        climbing_session = session_collection.find_one(
            {"data.session_id": session_id, "data.user_id": session.get("user_id")}
        )

        if not climbing_session:
            return jsonify({"error": "Session not found"}), 404

        # Get all events for this session
        event_collection = db_service.db["session_event_collection"]
        events = list(
            event_collection.find({"data.session_id": session_id}).sort(
                "profile.create_at", 1
            )  # Sort by time ascending
        )

        # Format data for chart
        chart_data = {
            "labels": [],
            "altitudes": [],
            "session_info": {
                "session_id": session_id,
                "start_at": climbing_session["profile"]["start_at"].isoformat()
                if climbing_session["profile"]["start_at"]
                else None,
                "session_state": climbing_session["profile"]["session_state"],
                "start_alt": climbing_session["data"].get("start_alt"),
                "end_alt": climbing_session["data"].get("end_alt"),
                "temp": climbing_session["data"].get("temp"),
                "humidity": climbing_session["data"].get("humidity"),
            },
        }

        for event in events:
            create_at = event["profile"]["create_at"]
            alt = event["data"]["alt"]

            # Format time label
            if isinstance(create_at, datetime):
                time_label = create_at.strftime("%H:%M:%S")
            else:
                time_label = str(create_at)

            chart_data["labels"].append(time_label)
            chart_data["altitudes"].append(alt)

        return jsonify(chart_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
