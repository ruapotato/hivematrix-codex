from flask import Blueprint, render_template
from models import Company

# Corrected Blueprint definition
companies_bp = Blueprint('companies', __name__, url_prefix='/companies')

@companies_bp.route('/')
def list_companies():
    companies = Company.query.all()
    return render_template('companies.html', companies=companies)

@companies_bp.route('/<int:company_id>')
def company_details(company_id):
    company = Company.query.get_or_404(company_id)
    return render_template('company_details.html', company=company)
