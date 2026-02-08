from flask import Blueprint, jsonify, request, session
from MultiStockTraderInstance import MultiStockTradeStatus

def create_stock_blueprint(state: MultiStockTradeStatus):
    bp = Blueprint('stock_api', __name__)

    @bp.route('/api/stocks', methods=['POST'])
    def add_stock():
        if(session.get('username') is None):
            print("Unauthorized Access Attempted To Add Stock")
            return jsonify({'error': 'Unauthorized'}), 401

        try:
            data = request.get_json(force=True)
        except Exception:
            data = request.form or {}

        name = data.get('ticker')

        if not name:
            print("No Ticker Provided In Request")
            return jsonify({'error': 'Missing stock name'}), 400

        entry = {
            'key': name,
        }

        print(f"Adding Stock: {entry} To Ticker List")

        data = state.SnapshotData()
        state.AddNewStock(name)
        print(data)
            
        return jsonify(entry), 201

    return bp
