from flask import Blueprint, request, jsonify, current_app

emergency_contact_api = Blueprint(
    "emergency_contact_api", __name__, url_prefix="/api/emergency-contacts"
)


@emergency_contact_api.route("/", methods=["POST"])
def create_emergency_contact():
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["name", "phone", "user_id"]
        if not all(field in data for field in required_fields):
            return jsonify(
                {"error": "Missing required fields: name, phone, user_id"}
            ), 400

        # Get DRFactory from schema registry
        from src.virtualization.digital_replica.dr_factory import DRFactory

        dr_factory = DRFactory("config/emergency_contact_schema.yaml")

        # Build initial data structure
        initial_data = {
            "profile": {
                "name": data["name"],
                "phone": data["phone"],
                "email": data.get("email", ""),
                "telegram_chat_id": data.get("telegram_chat_id", ""),
            },
            "data": {
                "user_id": data["user_id"],
                "relationship_type": data.get("relationship_type", "other"),
                "priority": data.get("priority", 1),
                "is_active": data.get("is_active", True),
                "notes": data.get("notes", ""),
            },
        }

        # Create DR using factory (validates with Pydantic)
        dr_data = dr_factory.create_dr("emergency_contact", initial_data)

        # Save to database (validates with MongoDB schema)
        contact_id = current_app.config["DB_SERVICE"].save_dr(
            "emergency_contact", dr_data
        )

        return jsonify(
            {
                "contact_id": contact_id,
                "message": "Emergency contact created successfully",
            }
        ), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@emergency_contact_api.route("/<contact_id>", methods=["GET"])
def get_emergency_contact(contact_id):
    try:
        contact = current_app.config["DB_SERVICE"].get_dr(
            "emergency_contact", contact_id
        )
        if not contact:
            return jsonify({"error": "Emergency contact not found"}), 404
        return jsonify(contact), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@emergency_contact_api.route("/user/<user_id>", methods=["GET"])
def get_user_emergency_contacts(user_id):
    try:
        contacts = current_app.config["DB_SERVICE"].query_drs(
            "emergency_contact", {"data.user_id": user_id, "data.is_active": True}
        )
        return jsonify(contacts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@emergency_contact_api.route("/<contact_id>", methods=["PUT"])
def update_emergency_contact(contact_id):
    try:
        data = request.get_json()

        # Build update structure
        update_data = {}

        if "profile" in data:
            update_data["profile"] = data["profile"]

        if "data" in data:
            update_data["data"] = data["data"]

        # Update in database
        current_app.config["DB_SERVICE"].update_dr(
            "emergency_contact", contact_id, update_data
        )

        return jsonify({"message": "Emergency contact updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@emergency_contact_api.route("/<contact_id>", methods=["DELETE"])
def delete_emergency_contact(contact_id):
    try:
        # Soft delete by setting is_active to False
        update_data = {"data": {"is_active": False}}
        current_app.config["DB_SERVICE"].update_dr(
            "emergency_contact", contact_id, update_data
        )

        return jsonify({"message": "Emergency contact deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@emergency_contact_api.route("/<contact_id>/hard-delete", methods=["DELETE"])
def hard_delete_emergency_contact(contact_id):
    try:
        current_app.config["DB_SERVICE"].delete_dr("emergency_contact", contact_id)
        return jsonify({"message": "Emergency contact permanently deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
