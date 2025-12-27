from flask import Blueprint, request, jsonify, current_app

# Create blueprints for different API groups
dt_api = Blueprint("dt_api", __name__, url_prefix="/api/dt")
dr_api = Blueprint("dr_api", __name__, url_prefix="/api/dr")
dt_management_api = Blueprint(
    "dt_management_api", __name__, url_prefix="/api/dt-management"
)
emergency_contact_api = Blueprint(
    "emergency_contact_api", __name__, url_prefix="/api/emergency-contacts"
)


# Digital Twin APIs
@dt_api.route("/", methods=["POST"])
def create_digital_twin():
    """Create a new Digital Twin"""
    try:
        data = request.get_json()
        required_fields = ["name", "description"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        dt_id = current_app.config["DT_FACTORY"].create_dt(
            name=data["name"], description=data["description"]
        )
        return jsonify({"dt_id": dt_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dt_api.route("/<dt_id>", methods=["GET"])
def get_digital_twin(dt_id):
    """Get Digital Twin details"""
    try:
        dt = current_app.config["DT_FACTORY"].get_dt(dt_id)
        if not dt:
            return jsonify({"error": "Digital Twin not found"}), 404
        return jsonify(dt), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dt_api.route("/", methods=["GET"])
def list_digital_twins():
    """List all Digital Twins"""
    try:
        dts = current_app.config["DT_FACTORY"].list_dts()
        return jsonify(dts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Generic Digital Replica APIs
@dr_api.route("/<dr_type>/<dr_id>", methods=["GET"])
def get_digital_replica(dr_type, dr_id):
    """Get Digital Replica details"""
    try:
        dr = current_app.config["DB_SERVICE"].get_dr(dr_type, dr_id)
        if not dr:
            return jsonify({"error": "Digital Replica not found"}), 404
        return jsonify(dr), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Digital Twin Management APIs
@dt_management_api.route("/assign/<dt_id>", methods=["POST"])
def assign_dr_to_dt(dt_id):
    """Assign a Digital Replica to a Digital Twin"""
    try:
        data = request.get_json()
        required_fields = ["dr_type", "dr_id"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        current_app.config["DT_FACTORY"].add_digital_replica(
            dt_id, data["dr_type"], data["dr_id"]
        )

        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dt_management_api.route("/stats/<dt_id>", methods=["GET"])
def get_dt_stats(dt_id):
    """Get statistics from a Digital Twin's services"""
    try:
        dt = current_app.config["DT_FACTORY"].get_dt(dt_id)
        if not dt:
            return jsonify({"error": "Digital Twin not found"}), 404

        params = request.args.to_dict()
        dr_type = params.get("dr_type")
        measure_type = params.get("measure_type")

        stats = (
            current_app.config["DT_FACTORY"]
            .get_dt_instance(dt_id)
            .execute_service(
                "AggregationService", dr_type=dr_type, attribute=measure_type
            )
        )

        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dt_api.route("/<dt_id>/services", methods=["POST"])
def add_service_to_dt(dt_id):
    """Add a service to Digital Twin"""
    try:
        data = request.get_json()
        if not data or "name" not in data:
            return jsonify({"error": "Missing service name"}), 400

        current_app.config["DT_FACTORY"].add_service(
            dt_id=dt_id,
            service_name=data["name"],
            service_config=data.get("config", {}),
        )
        return jsonify(
            {"status": "success", "message": f"Service {data['name']} added"}
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def register_api_blueprints(app):
    """Register all API blueprints with the Flask app"""
    app.register_blueprint(dt_api)
    app.register_blueprint(dr_api)
    app.register_blueprint(dt_management_api)
    app.register_blueprint(emergency_contact_api)


# Emergency Contact APIs
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
