from flask import Blueprint, make_response, request, current_app
import random
import time

security_bp = Blueprint('security', __name__)

# List of common bot probes to "sink"
BOT_PATHS = [
    '/.git/config',
    '/.env',
    '/wp-login.php',
    '/wp-admin/install.php',
    '/wp-admin/setup-config.php',
    '/xmlrpc.php',
    '/wlwmanifest.xml',
    '/phpmyadmin',
    '/shell',
    '/backup',
    '/config.php',
    '/admin.php',
    '/wordpress/wp-admin/install.php',
    '/wp-content/plugins/hellopress/wp_filemanager.php',
    '/wp-content/r.php'
]

@security_bp.route('/wp-admin/<path:p>')
@security_bp.route('/wp-content/<path:p>')
@security_bp.route('/wp-includes/<path:p>')
@security_bp.route('/wordpress/<path:p>')
@security_bp.route('/.git/<path:p>')
@security_bp.route('/xmlrpc.php')
@security_bp.route('/wlwmanifest.xml')
@security_bp.route('/.env')
@security_bp.route('/phpmyadmin/<path:p>')
def bot_sink(p=None):
    """
    Sinks common bot probes by returning 200 OK with decoy content.
    This prevents these probes from inflating the 404/500 error rate.
    """
    time.sleep(random.uniform(0.05, 0.2))
    return "<html><body><!-- System Node: 104.2 --><!-- Auth: Rejected --></body></html>", 200
