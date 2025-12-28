from flask import Blueprint, request, jsonify, current_app, session, redirect, url_for
from datetime import datetime
import uuid

device_api = Blueprint("device_api", __name__)


@device_api.route("/register-device", methods=["POST"])
def register_device():
    try:
        # Check if user is logged in
        if "user_id" not in session:
            return redirect(url_for("auth.login"))

        user_id = session["user_id"]

        # Get form data
        serial_number = request.form.get("serial_number")

        if not serial_number:
            return jsonify({"error": "Serial number is required"}), 400

        # Get services from app config
        db_service = current_app.config["DB_SERVICE"]
        device_dr_factory = current_app.config["DEVICE_DR_FACTORY"]
        pairing_dr_factory = current_app.config["DEVICE_PAIRING_DR_FACTORY"]

        # Check if device already exists
        device_collection = db_service.db["device_collection"]
        existing_device = device_collection.find_one(
            {"profile.serial_number": serial_number}
        )

        if existing_device:
            # Check if already paired with this user
            pairing_collection = db_service.db["device_pairing_collection"]
            existing_pairing = pairing_collection.find_one(
                {"data.device_serial": serial_number, "data.user_id": user_id}
            )

            if existing_pairing:
                return redirect(
                    url_for(
                        "auth.home", error="Device already registered to your account"
                    )
                )
            else:
                return redirect(
                    url_for(
                        "auth.home",
                        error="Device is already registered to another user",
                    )
                )

        # Create device DR using DRFactory
        device_data = {
            "profile": {"serial_number": serial_number},
            "data": {
                "status": "inactive",  # Will become active when device connects
                "battery_level": 100,
                "settings": {"sync_interval": 300},
            },
        }

        device_dr = device_dr_factory.create_dr("device", device_data)
        # Use serial_number as _id for device
        device_dr["_id"] = serial_number
        db_service.save_dr("device", device_dr)

        # Create device-user pairing using DRFactory
        pairing_data = {
            "profile": {"paired_at": datetime.utcnow()},
            "data": {
                "user_id": user_id,
                "device_serial": serial_number,
                "pairing_status": "active",
                "pairing_method": "manual",
            },
        }

        pairing_dr = pairing_dr_factory.create_dr("device_pairing", pairing_data)
        db_service.save_dr("device_pairing", pairing_dr)

        return redirect(
            url_for(
                "auth.home",
                success="Device registered successfully. Waiting for device to connect...",
            )
        )

    except Exception as e:
        current_app.logger.error(f"Error registering device: {str(e)}")
        return redirect(
            url_for("auth.home", error=f"Failed to register device: {str(e)}")
        )


@device_api.route("/devices", methods=["GET"])
def get_user_devices():
    try:
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401

        user_id = session["user_id"]
        db_service = current_app.config["DB_SERVICE"]

        # Get all pairings for user
        pairing_collection = db_service.db["device_pairing_collection"]
        pairings = list(
            pairing_collection.find(
                {"data.user_id": user_id, "data.pairing_status": "active"}
            )
        )

        # Get device details
        device_collection = db_service.db["device_collection"]
        devices = []

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

        return jsonify(devices), 200

    except Exception as e:
        current_app.logger.error(f"Error getting devices: {str(e)}")
        return jsonify({"error": str(e)}), 500


@device_api.route("/device/<device_serial>", methods=["GET"])
def get_device(device_serial):
    try:
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401

        user_id = session["user_id"]
        db_service = current_app.config["DB_SERVICE"]

        # Verify user owns this device
        pairing_collection = db_service.db["device_pairing_collection"]
        pairing = pairing_collection.find_one(
            {
                "data.device_serial": device_serial,
                "data.user_id": user_id,
                "data.pairing_status": "active",
            }
        )

        if not pairing:
            return jsonify({"error": "Device not found or not authorized"}), 404

        # Get device
        device_collection = db_service.db["device_collection"]
        device = device_collection.find_one({"_id": device_serial})

        if not device:
            return jsonify({"error": "Device not found"}), 404

        return jsonify(device), 200

    except Exception as e:
        current_app.logger.error(f"Error getting device: {str(e)}")
        return jsonify({"error": str(e)}), 500


@device_api.route("/device/<device_serial>", methods=["DELETE"])
def unregister_device(device_serial):
    try:
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401

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
            return jsonify({"error": "Device not found or not authorized"}), 404

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

        return jsonify({"message": "Device unregistered successfully"}), 200

    except Exception as e:
        current_app.logger.error(f"Error unregistering device: {str(e)}")
        return jsonify({"error": str(e)}), 500
