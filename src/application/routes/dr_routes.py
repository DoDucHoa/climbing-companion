from flask import Blueprint, request, jsonify, current_app

dr_api = Blueprint("dr_api", __name__, url_prefix="/api/dr")


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
