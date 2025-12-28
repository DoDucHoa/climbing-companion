from flask import Blueprint, request, jsonify, current_app
from src.virtualization.digital_replica.dr_factory import DRFactory

dr_api = Blueprint("dr_api", __name__, url_prefix="/api/dr")


@dr_api.route("/<dr_type>", methods=["POST"])
def create_digital_replica(dr_type):
    """Create a new Digital Replica"""
    try:
        data = request.get_json()

        # Get the appropriate DRFactory from config
        factory_key = f"{dr_type.upper()}_DR_FACTORY"
        dr_factory = current_app.config.get(factory_key)

        # If factory not in config, create one dynamically
        if not dr_factory:
            schema_path = f"config/{dr_type}_schema.yaml"
            dr_factory = DRFactory(schema_path)

        # Create DR using factory
        dr = dr_factory.create_dr(dr_type, data)

        # Save to database
        dr_id = current_app.config["DB_SERVICE"].save_dr(dr_type, dr)

        return jsonify(
            {"id": dr_id, "message": "Digital Replica created successfully"}
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
