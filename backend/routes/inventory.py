from flask import Flask, request, jsonify, Blueprint

app = Flask(__name__)
inventory_bp = Blueprint('inventory', __name__)
inventory = {}

@inventory_bp.route('/inventory', methods=['GET'])
def get_inventory():
    user_id = request.args.get('user_id')
    return jsonify(inventory.get(user_id, []))

@inventory_bp.route('/inventory', methods=['POST'])
def add_item():
    user_id = request.json.get('user_id')
    item = request.json.get('item')
    if user_id not in inventory:
        inventory[user_id] = []
    inventory[user_id].append(item)
    return jsonify(success=True)

app.register_blueprint(inventory_bp)

if __name__ == '__main__':
    app.run()