from flask import Blueprint, render_template
from models import Asset

# Corrected Blueprint definition
assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

@assets_bp.route('/')
def list_assets():
    assets = Asset.query.all()
    return render_template('assets.html', assets=assets)
