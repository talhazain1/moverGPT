from flask import Blueprint, jsonify
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

metrics_bp = Blueprint('metrics_api', __name__)

@metrics_bp.route('/json', methods=['GET'])
def get_metrics_json():
    raw_metrics = generate_latest()  # returns bytes
    metrics_text = raw_metrics.decode('utf-8')
    metrics_data = {}
    for family in text_string_to_metric_families(metrics_text):
        metrics_data[family.name] = []
        for sample in family.samples:
            metrics_data[family.name].append({
                "name": sample[0],
                "labels": sample[1],
                "value": sample[2],
                "timestamp": sample[3]
            })
    return jsonify(metrics_data)
