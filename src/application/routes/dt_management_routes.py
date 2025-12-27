from flask import Blueprint, request, jsonify, current_app

dt_management_api = Blueprint(
    "dt_management_api", __name__, url_prefix="/api/dt-management"
)


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
