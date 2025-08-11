from flask import Blueprint, render_template, redirect, url_for, flash, session

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login')
def login():
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('auth.login'))
