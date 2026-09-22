"""Updated Flask app factory with service-based architecture.

This is the new version of __init__.py that initializes services.
Replace the original app/__init__.py with this file.
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def initialize_services(app, logger):
    """Initialize and register all services in the DI container.
    
    Args:
        app: Flask application instance
        logger: Logger instance
    """
    from .services.container import get_container, set_container
    from .services.boirsu_service import BoiRsuService
    from .services.domain_services import (
        GraphService, SimulationService, ReportService, YouTubeService
    )
    
    # Create and configure container
    container = get_container()
    
    # Register services
    container.register(BoiRsuService)
    container.register(GraphService)
    container.register(SimulationService)
    container.register(ReportService)
    container.register(YouTubeService)
    
    # Store container in app for lifecycle management
    app.service_container = container
    
    logger.info("Service container initialized with 5 domain services")
    return container


def create_app(config_class=Config):
    """Flask应用工厂函数 (Service-based architecture)."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('mirofish')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 60)
        logger.info("MiroFish Backend 启动中 (Service-based Architecture)...")
        logger.info("=" * 60)
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 初始化服务容器
    if should_log_startup:
        logger.info("初始化服务容器...")
    initialize_services(app, logger)
    
    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")
    
    # 请求日志中间件
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
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp, youtube_mirror_fish_bp
    # Use new service-based BOI RSU blueprint
    from .api.boirsu_v2 import bp as boirsu_bp_v2
    
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(youtube_mirror_fish_bp, url_prefix='/api/youtube/mirror-fish')
    # Register new service-based BOI RSU routes
    app.register_blueprint(boirsu_bp_v2, url_prefix='/api/boirsu')

    # 健康检查（主应用级别）
    @app.route('/health')
    def health():
        return {
            'status': 'ok',
            'service': 'MiroFish Backend',
            'architecture': 'service-based'
        }
    
    # 服务状态检查
    @app.route('/health/services')
    def services_health():
        """Check health of all registered services."""
        try:
            from .services.container import get_container
            container = get_container()
            
            services_status = {}
            for service_class in [
                'BoiRsuService', 'GraphService', 'SimulationService',
                'ReportService', 'YouTubeService'
            ]:
                try:
                    # Check if service can be instantiated
                    from .services.boirsu_service import BoiRsuService
                    from .services.domain_services import (
                        GraphService, SimulationService, ReportService, YouTubeService
                    )
                    
                    service_map = {
                        'BoiRsuService': BoiRsuService,
                        'GraphService': GraphService,
                        'SimulationService': SimulationService,
                        'ReportService': ReportService,
                        'YouTubeService': YouTubeService,
                    }
                    
                    if service_class in service_map:
                        svc = container.get(service_map[service_class])
                        services_status[service_class] = 'healthy'
                except Exception as e:
                    services_status[service_class] = f'error: {str(e)}'
            
            return {
                'status': 'ok',
                'services': services_status
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 500
    
    # Graceful shutdown
    @app.teardown_appcontext
    def shutdown_services(exception=None):
        """Shutdown all services on app teardown."""
        if hasattr(app, 'service_container'):
            try:
                app.service_container.shutdown_all()
            except Exception as e:
                logger.error(f"Error during service shutdown: {e}")
    
    if should_log_startup:
        logger.info("MiroFish Backend 启动完成 (Service-based Architecture)")
    
    return app
