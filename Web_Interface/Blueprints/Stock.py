from flask import Blueprint, jsonify, request, session, current_app
from MultiStockTraderInstance import MultiStockTradeStatus

def create_stock_blueprint(state: MultiStockTradeStatus) -> Blueprint:
    bp = Blueprint('stock_api', __name__)

    @bp.route('/api/stocks', methods=['POST'])
    def add_stock():
        if(session.get('username') is None or session['username'] not in current_app.config['VALID_USERS']):
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
