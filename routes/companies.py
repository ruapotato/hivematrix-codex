# ruapotato/hivematrix-nexus/hivematrix-nexus-main/routes/companies.py
from flask import Blueprint, render_template
from models import Company

companies_bp = Blueprint('companies', __name__, url_prefix='/companies')

@companies_bp.route('/')
def list_companies():
    companies = Company.query.all()
    return render_template('companies.html', companies=companies)

@companies_bp.route('/<string:account_number>')
def company_details(account_number):
    company = Company.query.get_or_404(account_number)
    return render_template('company_details.html', company=company)
