"""Payment choice precedes authentication; provider readiness is server enforced."""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

CHOICES = (
    ('card', 'Pay by card', 'Debit or credit card', '▣'),
    ('paystack', 'Paystack', 'Continue to Paystack', '≋'),
    ('ozow', 'Ozow', 'Continue to Ozow', '◎'),
    ('pep', 'PEP pickup + bank payment', 'Pay Isazi by Capitec transfer. Collect at PEP.', '⌂'),
)


def register_checkout_journey(app, db, eco):
    bp = Blueprint('journey', __name__)

    def available(method):
        if method == 'pep':
            return True
        if method not in ('card', 'paystack', 'ozow'):
            return False
        if app.config.get('DEMO_MODE') or app.config.get('DEMO_PAYMENTS_ENABLED'):
            return True
        # Paystack and Ozow do not yet have live adapters. Never simulate a
        # successful real payment or redirect to a caller-supplied payment URL.
        return method == 'card' and eco['payfast_config']()['ready']

    @app.context_processor
    def context():
        method = session.get('checkout_method', '')
        row = next((r for r in CHOICES if r[0] == method), None)
        return dict(checkout_method=method, checkout_method_name=row[1] if row else '',
                    checkout_choices=[dict(key=k, name=n, description=d, icon=i, available=available(k))
                                      for k, n, d, i in CHOICES])

    @bp.route('/checkout/payment-choice', methods=['GET', 'POST'])
    def choose():
        if not session.get('cart') and not session.get('quick_product'):
            flash('Add a product before checking out.', 'error')
            return redirect(url_for('shop'))
        if request.method == 'GET':
            # A GET renders options and never changes the selected route or cart.
            return render_template('checkout_payment_choice.html', title='Choose how to pay', lines=[])
        method = request.form.get('payment_method', '')
        if not any(r[0] == method for r in CHOICES):
            abort(400, 'Choose a listed payment option.')
        if not available(method):
            abort(409, 'This payment provider is not connected for real payments.')
        if session.get('checkout_method') != method:
            session.pop('checkout_key', None)
        session['checkout_method'] = method
        session['after_auth_checkout'] = True
        return redirect(url_for('checkout'))

    app.register_blueprint(bp)
    return dict(available=available)
