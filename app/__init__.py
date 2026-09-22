"""MiroFish Backend - Flask application factory.

This version initializes the service container and keeps the legacy blueprints
available while also exposing the service-based BOI RSU routes.
"""

import os
import warnings

warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def initialize_services(app, logger):
    """Initialize and register all services with the dependency injection container."""
    from .services.container import get_container
    from .services.boirsu_service import BoiRsuService
    from .services.domain_services import (
        GraphService, SimulationService, ReportService, YouTubeService
    )

    container = get_container()
    container.register(BoiRsuService)
    container.register(GraphService)
    container.register(SimulationService)
    container.register(ReportService)
    container.register(YouTubeService)
    app.service_container = container

    logger.info("Service container initialized with %s domain services", 5)
    return container


def create_app(config_class=Config):
    """Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    logger = setup_logger('mirofish')

    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动中 (service-enabled)...")
        logger.info("=" * 50)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    initialize_services(app, logger)

    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")

    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")

    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response

    from .api import graph_bp, simulation_bp, report_bp, youtube_mirror_fish_bp
    from .api.boirsu_v2 import bp as boirsu_bp_v2
    from .api.courses import bp as courses_bp

    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(youtube_mirror_fish_bp, url_prefix='/api/youtube/mirror-fish')
    app.register_blueprint(boirsu_bp_v2, url_prefix='/api/boirsu')
    # World-wide course search for the boi-school registration page
    # (/api/courses/search?q=... — proxied from the Vite dev server).
    app.register_blueprint(courses_bp, url_prefix='/api')

    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend', 'architecture': 'service-enabled'}

    @app.route('/api/videos')
    def youtube_videos():
        """Return live Apify-backed YouTube recommendations for the classroom."""
        topic = (request.args.get('topic') or '').strip()
        if not topic:
            return {'videos': []}
        try:
            limit = max(1, min(int(request.args.get('limit') or 3), 10))
        except ValueError:
            limit = 3
        level = (request.args.get('level') or 'beginner').strip()
        try:
            from .services.domain_services import YouTubeService
            service = app.service_container.get(YouTubeService)
            videos = service.get_video_recommendations(topic, level)[:limit]
            return {'success': True, 'topic': topic, 'videos': videos}
        except Exception as exc:
            logger.exception('Live classroom YouTube lookup failed')
            return {'success': False, 'error': str(exc)[:300], 'videos': []}, 502

    @app.route('/health/services')
    def services_health():
        from .services.container import get_container
        container = get_container()
        statuses = {}
        for service_name in ['BoiRsuService', 'GraphService', 'SimulationService', 'ReportService', 'YouTubeService']:
            try:
                service_map = {
                    'BoiRsuService': __import__('app.services.boirsu_service', fromlist=['BoiRsuService']).BoiRsuService,
                    'GraphService': __import__('app.services.domain_services', fromlist=['GraphService']).GraphService,
                    'SimulationService': __import__('app.services.domain_services', fromlist=['SimulationService']).SimulationService,
                    'ReportService': __import__('app.services.domain_services', fromlist=['ReportService']).ReportService,
                    'YouTubeService': __import__('app.services.domain_services', fromlist=['YouTubeService']).YouTubeService,
                }
                container.get(service_map[service_name])
                statuses[service_name] = 'healthy'
            except Exception as exc:  # pragma: no cover
                statuses[service_name] = f'error: {exc}'
        return {'status': 'ok', 'services': statuses}

    @app.teardown_appcontext
    def shutdown_services(exception=None):
        if hasattr(app, 'service_container'):
            try:
                app.service_container.shutdown_all()
            except Exception as exc:
                logger.error(f"Error during service shutdown: {exc}")

    if should_log_startup:
        logger.info("MiroFish Backend 启动完成")

    return app

