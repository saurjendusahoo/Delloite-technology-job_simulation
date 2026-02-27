import json
import sys
from datetime import datetime, timezone

# =============================================================================
# Telemetry Unification Script
# =============================================================================
# This script reads two telemetry JSON files that use different schemas and
# converts them both into a single unified format.
#
# Format 1 (data-1.json):  Flat structure. Timestamp is already in epoch ms.
#                          Location is a single slash-separated string.
#                          Device fields live at the top level (deviceID, deviceType).
#                          Sensor readings use short keys (temp, operationStatus).
#
# Format 2 (data-2.json):  Nested structure. Timestamp is ISO 8601 (UTC).
#                          Location is split across separate keys (country, city, …).
#                          Device info is nested under a "device" object.
#                          Sensor readings are nested under a "data" object.
#
# Unified output (data-result.json):
#   - deviceID, deviceType at top level
#   - timestamp as milliseconds since epoch
#   - location as a structured object { country, city, area, factory, section }
#   - data as a structured object { status, temperature }
# =============================================================================


def convert_format1(data: dict) -> dict:
    """Convert Format 1 (flat, epoch ms timestamp) to the unified format."""

    # Format 1 stores location as a single slash-delimited string, e.g.
    #   "japan/tokyo/keiyō-industrial-zone/daikibo-factory-meiyo/section-1"
    # We split it into its 5 known components so the unified format has a
    # structured location object that's easier to query and filter on.
    location_parts = data["location"].split("/")
    location = {
        "country": location_parts[0],
        "city": location_parts[1],
        "area": location_parts[2],
        "factory": location_parts[3],
        "section": location_parts[4],
    }

    # Format 1 uses shorthand field names ("temp", "operationStatus") that
    # differ from the unified schema ("temperature", "status"). We map them
    # to the canonical names here so consumers only deal with one vocabulary.
    return {
        "deviceID": data["deviceID"],
        "deviceType": data["deviceType"],
        "timestamp": data["timestamp"],  # already in epoch ms — no conversion needed
        "location": location,
        "data": {
            "status": data["operationStatus"],
            "temperature": data["temp"],
        },
    }


def convert_format2(data: dict) -> dict:
    """Convert Format 2 (nested, ISO timestamp) to the unified format."""

    # Format 2 uses an ISO 8601 timestamp like "2021-06-23T10:57:17.783Z".
    # The unified format expects milliseconds since the Unix epoch (Jan 1 1970).
    # Steps:
    #   1. Replace the trailing "Z" with "+00:00" so fromisoformat() can parse
    #      it as a timezone-aware UTC datetime.
    #   2. Call .timestamp() to get seconds since epoch (as a float).
    #   3. Multiply by 1000 and truncate to int to get milliseconds.
    dt = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    epoch_ms = int(dt.timestamp() * 1000)

    # Format 2 nests device info under a "device" object and location fields
    # are separate top-level keys. We flatten device info and group location
    # fields into a single object to match the unified schema.
    return {
        "deviceID": data["device"]["id"],
        "deviceType": data["device"]["type"],
        "timestamp": epoch_ms,
        "location": {
            "country": data["country"],
            "city": data["city"],
            "area": data["area"],
            "factory": data["factory"],
            "section": data["section"],
        },
        "data": {
            "status": data["data"]["status"],
            "temperature": data["data"]["temperature"],
        },
    }


def detect_and_convert(data: dict) -> dict:
    """Detect the telemetry format and convert to the unified format."""
    # We distinguish the two formats by checking for a key unique to each:
    #   - "deviceID" at the top level → Format 1 (flat)
    #   - "device" (an object) at the top level → Format 2 (nested)
    # This lets us process any mix of files without the caller needing to
    # know which format each file uses.
    if "deviceID" in data:
        return convert_format1(data)
    elif "device" in data:
        return convert_format2(data)
    else:
        raise ValueError("Unknown telemetry format")


def main():
    # Read both input files
    with open("data-1.json", "r", encoding="utf-8") as f:
        data1 = json.load(f)

    with open("data-2.json", "r", encoding="utf-8") as f:
        data2 = json.load(f)

    # Convert both to the unified format
    unified1 = detect_and_convert(data1)
    unified2 = detect_and_convert(data2)

    # Sanity check: since both files describe the same device event, their
    # unified representations should be identical. If they aren't, something
    # went wrong in the conversion logic.
    assert unified1 == unified2, "Unified results do not match!"

    # Write the unified result to data-result.json using UTF-8 encoding
    # and ensure_ascii=False so special characters (e.g. ō in keiyō) are
    # preserved as-is rather than escaped to \u sequences.
    with open("data-result.json", "w", encoding="utf-8") as f:
        json.dump(unified1, f, indent=4, ensure_ascii=False)

    # Print confirmation and the result to stdout
    print("Successfully unified telemetry data into data-result.json")
    # Reconfigure stdout to UTF-8 to avoid Windows cp1252 encoding errors
    # when printing characters like ō that aren't in the default codepage.
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(unified1, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
