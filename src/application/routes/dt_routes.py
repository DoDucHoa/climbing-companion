from flask import Blueprint, request, jsonify, current_app

dt_api = Blueprint("dt_api", __name__, url_prefix="/api/dt")


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
